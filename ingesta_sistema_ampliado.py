"""NORA - ingesta mensual multidominio robusta.

Principios:
- una fila larga por celda/variable/mes en nora_observations;
- checkpoint natural region+variable+cell+observed_at;
- una evaluación server-side de Earth Engine por mes;
- datasets con fecha de inicio posterior se omiten explícitamente;
- núcleo climático/vegetación y capas ampliadas de agua, energía, suelo y atmósfera.
"""
import json
import math
import os
import time

import ee
import pandas as pd
from supabase import create_client

PROJECT_ID = os.getenv("GEE_PROJECT_ID", "nora-506511")
REGION_KEY = os.getenv("NORA_REGION_ID", "alto_xingu")
START_YEAR = int(os.getenv("NORA_START_YEAR", "2001"))
END_YEAR = int(os.getenv("NORA_END_YEAR", "2024"))
PROFILE = os.getenv("NORA_PROFILE", "full")
SMOKE_MONTH = os.getenv("NORA_SMOKE_MONTH")
SMOKE_MONTH = int(SMOKE_MONTH) if SMOKE_MONTH else None
BATCH_SIZE = 5000

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

key_data = os.getenv("GEE_SERVICE_ACCOUNT_KEY")
if key_data:
    key = json.loads(key_data)
    credentials = ee.ServiceAccountCredentials(key["client_email"], key_data=key_data)
    ee.Initialize(credentials=credentials, project=PROJECT_ID)
else:
    ee.Initialize(project=PROJECT_ID)


def get_one(table, **filters):
    q = sb.table(table).select("*")
    for name, value in filters.items():
        q = q.eq(name, value)
    result = q.limit(1).execute()
    if not result.data:
        raise RuntimeError(f"No existe {table}: {filters}")
    return result.data[0]


region = get_one("nora_regions", region_id=REGION_KEY)
region_db_id = region["id"]
geom = region.get("geometry") or {}
if geom.get("type") != "bbox":
    raise RuntimeError("La región debe tener geometry tipo bbox: [lon_min, lat_min, lon_max, lat_max].")

lon_min, lat_min, lon_max, lat_max = map(float, geom["coordinates"])
grid_size = float(region.get("grid_size_deg") or 0.1)
lons = [round(lon_min + i * grid_size, 8) for i in range(math.ceil((lon_max - lon_min) / grid_size))]
lats = [round(lat_min + j * grid_size, 8) for j in range(math.ceil((lat_max - lat_min) / grid_size))]
features = []
for i, lon in enumerate(lons):
    for j, lat in enumerate(lats):
        features.append(
            ee.Feature(
                ee.Geometry.Rectangle([lon, lat, min(lon + grid_size, lon_max), min(lat + grid_size, lat_max)]),
                {"cell_id": i * len(lats) + j, "longitude": lon + grid_size / 2, "latitude": lat + grid_size / 2},
            )
        )
grid = ee.FeatureCollection(features)
print(f"NORA | region={REGION_KEY} | cells={len(features)} | years={START_YEAR}-{END_YEAR} | profile={PROFILE} | smoke_month={SMOKE_MONTH}")

vars_db = sb.table("nora_variables").select("id,key,unit,source_id").execute().data
VAR = {row["key"]: row for row in vars_db}


def month_hours(year, month):
    return int(pd.Period(f"{year}-{month:02d}").days_in_month) * 24


def add_collection(image, collection_id, source_band, output_name, start, end, factor=1.0, offset=0.0, reducer="mean"):
    collection = ee.ImageCollection(collection_id).filterDate(start, end).select(source_band)
    value = (collection.sum() if reducer == "sum" else collection.mean()).multiply(factor).add(offset).rename(output_name)
    return image.addBands(value)


def monthly_image(year, month):
    start = ee.Date.fromYMD(year, month, 1)
    end = start.advance(1, "month")
    days = month_hours(year, month) / 24.0

    era = ee.ImageCollection("ECMWF/ERA5_LAND/MONTHLY_AGGR").filterDate(start, end).mean()
    temp_c = era.select("temperature_2m").subtract(273.15)
    dew_c = era.select("dewpoint_temperature_2m").subtract(273.15)
    es = temp_c.expression("0.6108 * exp(17.27*t/(t+237.3))", {"t": temp_c})
    ea = dew_c.expression("0.6108 * exp(17.27*t/(t+237.3))", {"t": dew_c})

    image = ee.Image.cat([
        era.select("total_precipitation_sum").multiply(1000).rename("precip_mm"),
        temp_c.rename("temp_c"),
        era.select("runoff_sum").multiply(1000).rename("runoff_mm"),
        era.select("surface_runoff_sum").multiply(1000).rename("surface_runoff_mm"),
        era.select("sub_surface_runoff_sum").multiply(1000).rename("subsurface_runoff_mm"),
        era.select("total_evaporation_sum").multiply(-1000).rename("evapotranspiration_mm"),
        era.select("potential_evaporation_sum").multiply(1000).rename("potential_evapotranspiration_mm"),
        era.select("volumetric_soil_water_layer_1").rename("soil_moisture_surface"),
        era.select([
            "volumetric_soil_water_layer_1",
            "volumetric_soil_water_layer_2",
            "volumetric_soil_water_layer_3",
        ]).reduce(ee.Reducer.mean()).rename("soil_moisture_rootzone"),
        es.subtract(ea).max(0).rename("vpd_kpa"),
        era.select("u_component_of_wind_10m").pow(2).add(era.select("v_component_of_wind_10m").pow(2)).sqrt().rename("wind_speed_ms"),
        era.select("surface_solar_radiation_downwards_sum").divide(days * 86400).rename("surface_radiation_wm2"),
        era.select("surface_pressure").rename("surface_pressure_pa"),
    ])

    image = add_collection(image, "MODIS/061/MOD13Q1", "NDVI", "ndvi", start, end, factor=0.0001)
    image = add_collection(image, "MODIS/061/MOD13Q1", "EVI", "evi", start, end, factor=0.0001)
    image = add_collection(image, "MODIS/061/MOD11A2", "LST_Day_1km", "lst_day_c", start, end, factor=0.02, offset=-273.15)
    image = add_collection(image, "MODIS/061/MOD11A2", "LST_Night_1km", "lst_night_c", start, end, factor=0.02, offset=-273.15)
    image = add_collection(image, "MODIS/061/MCD15A3H", "Lai", "lai", start, end, factor=0.1)
    image = add_collection(image, "MODIS/061/MCD15A3H", "Fpar", "fpar", start, end, factor=0.01)
    image = add_collection(image, "NASA/GPM_L3/IMERG_V07", "precipitation", "gpm_precip_mm", start, end, factor=days * 24.0)

    if year >= 2015:
        image = add_collection(image, "NASA/SMAP/SPL4SMGP/008", "sm_surface", "smap_surface_soil_moisture", start, end)
        image = add_collection(image, "NASA/SMAP/SPL4SMGP/008", "sm_rootzone", "smap_rootzone_soil_moisture", start, end)
    if year >= 2018:
        image = add_collection(image, "COPERNICUS/S5P/OFFL/L3_CLOUD", "cloud_fraction", "cloud_fraction", start, end)
        image = add_collection(image, "COPERNICUS/S5P/OFFL/L3_CLOUD", "cloud_top_height", "cloud_top_height_m", start, end)
        image = add_collection(image, "COPERNICUS/S5P/OFFL/L3_CLOUD", "cloud_optical_depth", "cloud_optical_depth", start, end)
        image = add_collection(image, "COPERNICUS/S5P/OFFL/L3_CO", "CO_column_number_density", "co_mol_m2", start, end)
        image = add_collection(image, "COPERNICUS/S5P/OFFL/L3_NO2", "tropospheric_NO2_column_number_density", "no2_mol_m2", start, end)
    if year >= 2019:
        image = add_collection(image, "COPERNICUS/S5P/OFFL/L3_CH4", "CH4_column_volume_mixing_ratio_dry_air", "ch4_ppb", start, end)
        image = add_collection(image, "COPERNICUS/S5P/OFFL/L3_CH4", "aerosol_optical_depth", "aod", start, end)
    if year >= 2021:
        image = add_collection(image, "MODIS/061/MOD17A2H", "Gpp", "gpp", start, end, factor=0.0001, reducer="sum")
    return image


BANDS = {
    "precip_mm": "precip_mm", "temp_c": "temp_c", "ndvi": "ndvi", "runoff_mm": "runoff_mm",
    "surface_runoff_mm": "surface_runoff_mm", "subsurface_runoff_mm": "subsurface_runoff_mm",
    "evapotranspiration_mm": "evapotranspiration_mm", "potential_evapotranspiration_mm": "potential_evapotranspiration_mm",
    "soil_moisture_surface": "soil_moisture_surface", "soil_moisture_rootzone": "soil_moisture_rootzone",
    "lst_day_c": "lst_day_c", "lst_night_c": "lst_night_c", "lai": "lai", "fpar": "fpar", "vpd_kpa": "vpd_kpa",
    "wind_speed_ms": "wind_speed_ms", "surface_radiation_wm2": "surface_radiation_wm2", "surface_pressure_pa": "surface_pressure_pa",
    "gpm_precip_mm": "gpm_precip_mm", "smap_surface_soil_moisture": "smap_surface_soil_moisture",
    "smap_rootzone_soil_moisture": "smap_rootzone_soil_moisture", "cloud_fraction": "cloud_fraction",
    "cloud_top_height_m": "cloud_top_height_m", "cloud_optical_depth": "cloud_optical_depth", "co_mol_m2": "co_mol_m2",
    "no2_mol_m2": "no2_mol_m2", "ch4_ppb": "ch4_ppb", "gpp": "gpp", "aod": "aod", "evi": "evi",
}
if PROFILE == "core":
    allowed = {
        "precip_mm", "temp_c", "ndvi", "runoff_mm", "evapotranspiration_mm", "soil_moisture_rootzone",
        "lst_day_c", "lai", "vpd_kpa", "gpm_precip_mm", "cloud_fraction",
    }
    BANDS = {k: v for k, v in BANDS.items() if k in allowed}


def upload_rows(rows):
    for start in range(0, len(rows), BATCH_SIZE):
        sb.table("nora_observations").upsert(rows[start : start + BATCH_SIZE]).execute()


for year in range(START_YEAR, END_YEAR + 1):
    months = [SMOKE_MONTH] if SMOKE_MONTH else range(1, 13)
    for month in months:
        observed_at = f"{year}-{month:02d}-01T00:00:00+00:00"
        existing = (
            sb.table("nora_observations")
            .select("variable_id", count="exact")
            .eq("region_id", region_db_id)
            .eq("observed_at", observed_at)
            .execute()
        )
        existing_ids = {row["variable_id"] for row in (existing.data or [])}
        required_ids = {VAR[k]["id"] for k in BANDS if k in VAR}
        if required_ids and required_ids.issubset(existing_ids):
            print(f"SKIP {observed_at[:7]}: checkpoint completo ({len(required_ids)} variables)")
            continue

        image = monthly_image(year, month)
        band_names = set(image.bandNames().getInfo())
        active = [(key, band) for key, band in BANDS.items() if key in VAR and band in band_names]
        if not active:
            print(f"SKIP {observed_at[:7]}: sin bandas activas")
            continue

        selected = image.select([band for _, band in active])
        reduced = selected.reduceRegions(
            collection=grid,
            reducer=ee.Reducer.mean(),
            scale=11132,
            tileScale=4,
        ).getInfo()["features"]

        rows = []
        for feature in reduced:
            props = feature["properties"]
            cell_id = int(props["cell_id"])
            for key, band in active:
                value = props.get(band)
                if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                    continue
                rows.append({
                    "region_id": region_db_id,
                    "variable_id": VAR[key]["id"],
                    "source_id": VAR[key]["source_id"],
                    "cell_id": cell_id,
                    "longitude": props.get("longitude"),
                    "latitude": props.get("latitude"),
                    "observed_at": observed_at,
                    "value": float(value),
                    "unit": VAR[key]["unit"],
                    "metadata": {
                        "profile": PROFILE,
                        "aggregation": "monthly_mean",
                        "earth_engine_band": band,
                        "source_period": f"{year}-{month:02d}",
                    },
                })

        upload_rows(rows)
        print(f"OK {year}-{month:02d}: {len(reduced)} cells / {len(rows)} observations / {len(active)} variables")
        time.sleep(0.1)

print("NORA: ingesta ampliada completada.")