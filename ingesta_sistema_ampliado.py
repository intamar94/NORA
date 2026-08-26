"""Ingesta ampliada del sistema Tierra para NORA.

Diseño:
- una región por ejecución (NORA_REGION_ID)
- grilla definida en nora_regions.geometry como bbox
- frecuencia mensual común para análisis comparables
- una reducción Earth Engine por mes y región, combinando múltiples dominios
- almacenamiento en nora_observations (modelo largo), no en columnas rígidas

Variables: agua, energía, suelo, vegetación, nubes y atmósfera.
Fuentes: ERA5-Land, Sentinel-5P, MODIS, GPM y SMAP.

La ausencia de datos antes de la fecha de inicio de una misión se conserva como
NULL/no observación; NORA no interpola silenciosamente esos huecos.
"""
import json, math, os, time
from datetime import date
import ee
import pandas as pd
from supabase import create_client

PROJECT_ID = os.getenv("GEE_PROJECT_ID", "nora-506511")
REGION_KEY = os.getenv("NORA_REGION_ID", "alto_xingu")
START_YEAR = int(os.getenv("NORA_START_YEAR", "2001"))
END_YEAR = int(os.getenv("NORA_END_YEAR", "2024"))
PROFILE = os.getenv("NORA_PROFILE", "full")
BATCH_SIZE = 5000

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

key = os.getenv("GEE_SERVICE_ACCOUNT_KEY")
if key:
    data = json.loads(key)
    ee.Initialize(ee.ServiceAccountCredentials(data["client_email"], key_data=key), project=PROJECT_ID)
else:
    try:
        ee.Initialize(project=PROJECT_ID)
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=PROJECT_ID)


def one(table, **kwargs):
    q = sb.table(table).select("*")
    for k, v in kwargs.items():
        q = q.eq(k, v)
    r = q.limit(1).execute()
    if not r.data:
        raise RuntimeError(f"No existe {table}: {kwargs}")
    return r.data[0]

region = one("nora_regions", region_id=REGION_KEY)
region_db_id = region["id"]
geom = region.get("geometry") or {}
if geom.get("type") != "bbox":
    raise RuntimeError("La geometria de la región debe ser {'type':'bbox','coordinates':[lon_min,lat_min,lon_max,lat_max]} para esta ingesta.")
lon_min, lat_min, lon_max, lat_max = geom["coordinates"]
grid_size = float(region.get("grid_size_deg") or 0.1)

lons = [round(lon_min + i * grid_size, 8) for i in range(math.ceil((lon_max-lon_min)/grid_size))]
lats = [round(lat_min + i * grid_size, 8) for i in range(math.ceil((lat_max-lat_min)/grid_size))]
features = []
for i, lon in enumerate(lons):
    for j, lat in enumerate(lats):
        features.append(ee.Feature(ee.Geometry.Rectangle([lon, lat, min(lon+grid_size, lon_max), min(lat+grid_size, lat_max)]), {
            "cell_id": i*len(lats)+j, "lon": lon+grid_size/2, "lat": lat+grid_size/2
        }))
grid = ee.FeatureCollection(features)
print(f"NORA ampliada | región={REGION_KEY} | celdas={len(features)} | perfil={PROFILE}")

# Variable registry already created by Supabase migration.
vars_db = sb.table("nora_variables").select("id,key,unit,source_id").execute().data
VAR = {v["key"]: v for v in vars_db}

def ee_month(collection, band, start, end, reducer="mean"):
    c = ee.ImageCollection(collection).filterDate(start, end).select(band)
    return (c.sum() if reducer == "sum" else c.mean()).rename(band)

def add_if_available(image, collection, band, name, start, end, reducer="mean", scale=11132, factor=1.0, offset=0.0):
    c = ee.ImageCollection(collection).filterDate(start, end).select(band)
    if c.size().getInfo() == 0:
        return image
    x = (c.sum() if reducer == "sum" else c.mean()).multiply(factor).add(offset).rename(name)
    return image.addBands(x)

def monthly_image(year, month):
    start = ee.Date.fromYMD(year, month, 1)
    end = start.advance(1, "month")
    days = ee.Number(end.difference(start, "day"))

    # ERA5-Land: physical backbone. Accumulated water/energy terms are converted to mm.
    era = ee.ImageCollection("ECMWF/ERA5_LAND/MONTHLY_AGGR").filterDate(start, end).mean()
    temp = era.select("temperature_2m").subtract(273.15).rename("_temp")
    dew = era.select("dewpoint_temperature_2m").subtract(273.15)
    es = temp.expression("0.6108 * exp(17.27*t/(t+237.3))", {"t": temp})
    ea = dew.expression("0.6108 * exp(17.27*t/(t+237.3))", {"t": dew})
    vpd = es.subtract(ea).max(0).rename("vpd_kpa")
    wind = era.select("u_component_of_wind_10m").pow(2).add(era.select("v_component_of_wind_10m").pow(2)).sqrt().rename("wind_speed_ms")
    solar = era.select("surface_solar_radiation_downwards_sum").divide(days.multiply(86400)).rename("surface_radiation_wm2")
    root = era.select(["volumetric_soil_water_layer_1","volumetric_soil_water_layer_2","volumetric_soil_water_layer_3"]).reduce(ee.Reducer.mean()).rename("soil_moisture_rootzone")
    img = ee.Image.cat([
        era.select("runoff_sum").multiply(1000).rename("runoff_mm"),
        era.select("surface_runoff_sum").multiply(1000).rename("surface_runoff_mm"),
        era.select("sub_surface_runoff_sum").multiply(1000).rename("subsurface_runoff_mm"),
        era.select("total_evaporation_sum").multiply(-1000).rename("evapotranspiration_mm"),
        era.select("potential_evaporation_sum").multiply(1000).rename("potential_evapotranspiration_mm"),
        era.select("volumetric_soil_water_layer_1").rename("soil_moisture_surface"),
        root, vpd, wind, solar,
        era.select("surface_pressure").rename("surface_pressure_pa")
    ])

    # MODIS: vegetation productivity and thermal state.
    img = add_if_available(img, "MODIS/061/MOD11A2", "LST_Day_1km", "lst_day_c", start, end, factor=0.02, offset=-273.15)
    img = add_if_available(img, "MODIS/061/MOD11A2", "LST_Night_1km", "lst_night_c", start, end, factor=0.02, offset=-273.15)
    img = add_if_available(img, "MODIS/061/MOD16A2GF", "ET", "evapotranspiration_modis", start, end, reducer="sum", factor=0.1)
    img = add_if_available(img, "MODIS/061/MOD16A2GF", "PET", "potential_evapotranspiration_modis", start, end, reducer="sum", factor=0.1)
    img = add_if_available(img, "MODIS/061/MCD15A3H", "Lai", "lai", start, end, factor=0.1)
    img = add_if_available(img, "MODIS/061/MCD15A3H", "Fpar", "fpar", start, end, factor=0.01)

    # Independent precipitation source for cross-sensor validation.
    img = add_if_available(img, "NASA/GPM_L3/IMERG_V07", "precipitation", "gpm_precip_mm", start, end, factor=hours_in_month(year, month))

    # SMAP only exists from 2015; empty collections are skipped.
    img = add_if_available(img, "NASA/SMAP/SPL4SMGP/008", "sm_surface", "smap_surface_soil_moisture", start, end)
    img = add_if_available(img, "NASA/SMAP/SPL4SMGP/008", "sm_rootzone", "smap_rootzone_soil_moisture", start, end)

    # Sentinel-5P atmospheric state. These begin in 2018/2019.
    img = add_if_available(img, "COPERNICUS/S5P/OFFL/L3_CLOUD", "cloud_fraction", "cloud_fraction", start, end)
    img = add_if_available(img, "COPERNICUS/S5P/OFFL/L3_CLOUD", "cloud_top_height", "cloud_top_height_m", start, end)
    img = add_if_available(img, "COPERNICUS/S5P/OFFL/L3_CLOUD", "cloud_optical_depth", "cloud_optical_depth", start, end)
    img = add_if_available(img, "COPERNICUS/S5P/OFFL/L3_CO", "CO_column_number_density", "co_mol_m2", start, end)
    img = add_if_available(img, "COPERNICUS/S5P/OFFL/L3_NO2", "tropospheric_NO2_column_number_density", "no2_mol_m2", start, end)
    img = add_if_available(img, "COPERNICUS/S5P/OFFL/L3_CH4", "CH4_column_volume_mixing_ratio_dry_air", "ch4_ppb", start, end)
    return img

def hours_in_month(year, month):
    return int(pd.Period(f"{year}-{month:02d}").days_in_month) * 24

BANDS = {
    "runoff_mm":"runoff_mm", "surface_runoff_mm":"surface_runoff_mm", "subsurface_runoff_mm":"subsurface_runoff_mm",
    "evapotranspiration_mm":"evapotranspiration_mm", "potential_evapotranspiration_mm":"potential_evapotranspiration_mm",
    "soil_moisture_surface":"soil_moisture_surface", "soil_moisture_rootzone":"soil_moisture_rootzone",
    "lst_day_c":"lst_day_c", "lst_night_c":"lst_night_c", "lai":"lai", "fpar":"fpar", "vpd_kpa":"vpd_kpa",
    "wind_speed_ms":"wind_speed_ms", "surface_radiation_wm2":"surface_radiation_wm2", "surface_pressure_pa":"surface_pressure_pa",
    "gpm_precip_mm":"gpm_precip_mm", "smap_surface_soil_moisture":"smap_surface_soil_moisture", "smap_rootzone_soil_moisture":"smap_rootzone_soil_moisture",
    "cloud_fraction":"cloud_fraction", "cloud_top_height_m":"cloud_top_height_m", "cloud_optical_depth":"cloud_optical_depth",
    "co_mol_m2":"co_mol_m2", "no2_mol_m2":"no2_mol_m2", "ch4_ppb":"ch4_ppb"
}
if PROFILE == "core":
    BANDS = {k:v for k,v in BANDS.items() if k in {"runoff_mm","evapotranspiration_mm","soil_moisture_surface","soil_moisture_rootzone","lst_day_c","lai","vpd_kpa","wind_speed_ms","surface_radiation_wm2","cloud_fraction","gpm_precip_mm"}}


def already_done(year, month):
    # Count one representative variable per month. This is a coarse checkpoint;
    # individual missing variables are still accepted and can be repaired with PROFILE=full.
    r = (sb.table("nora_observations").select("id", count="exact")
         .eq("region_id", region_db_id).eq("observed_at", f"{year}-{month:02d}-01").execute())
    return (r.count or 0) > 0

for year in range(START_YEAR, END_YEAR + 1):
    for month in range(1, 13):
        if already_done(year, month):
            print(f"SKIP {year}-{month:02d}: ya existe observación para la región")
            continue
        start = ee.Date.fromYMD(year, month, 1)
        img = monthly_image(year, month)
        bands = [b for b in BANDS.values() if b in img.bandNames().getInfo()]
        if not bands:
            continue
        reduced = img.select(bands).reduceRegions(collection=grid, reducer=ee.Reducer.mean(), scale=11132).getInfo()["features"]
        rows = []
        for f in reduced:
            p = f["properties"]
            cid = int(p["cell_id"])
            for key, band in BANDS.items():
                if band not in p or p.get(band) is None or key not in VAR:
                    continue
                val = p[band]
                if isinstance(val, (int,float)) and math.isfinite(float(val)):
                    rows.append({
                        "region_id": region_db_id,
                        "variable_id": VAR[key]["id"],
                        "source_id": VAR[key]["source_id"],
                        "cell_id": cid,
                        "longitude": p.get("lon"),
                        "latitude": p.get("lat"),
                        "observed_at": f"{year}-{month:02d}-01",
                        "value": float(val),
                        "unit": VAR[key]["unit"],
                        "metadata": {"profile": PROFILE, "aggregation":"monthly_mean_or_sum", "source_band":band}
                    })
        for i in range(0, len(rows), BATCH_SIZE):
            sb.table("nora_observations").upsert(rows[i:i+BATCH_SIZE]).execute()
        print(f"OK {year}-{month:02d}: {len(reduced)} celdas / {len(rows)} observaciones")
        time.sleep(0.2)

print("NORA: ingesta ampliada terminada.")
