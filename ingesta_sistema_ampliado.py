"""NORA - ingesta mensual multidominio robusta."""
import json, math, os, time
import ee
import pandas as pd
from supabase import create_client

PROJECT_ID=os.getenv("GEE_PROJECT_ID","nora-506511")
REGION_KEY=os.getenv("NORA_REGION_ID","alto_xingu")
START_YEAR=int(os.getenv("NORA_START_YEAR","2001")); END_YEAR=int(os.getenv("NORA_END_YEAR","2024"))
PROFILE=os.getenv("NORA_PROFILE","full"); SMOKE_MONTH=os.getenv("NORA_SMOKE_MONTH")
SMOKE_MONTH=int(SMOKE_MONTH) if SMOKE_MONTH else None
BATCH_SIZE=1000; RETRIES=5
SUPABASE_URL=os.environ["SUPABASE_URL"]; SUPABASE_KEY=os.environ["SUPABASE_SERVICE_ROLE_KEY"]
sb=create_client(SUPABASE_URL,SUPABASE_KEY)
key_data=os.getenv("GEE_SERVICE_ACCOUNT_KEY")
if key_data:
    key=json.loads(key_data); ee.Initialize(credentials=ee.ServiceAccountCredentials(key["client_email"],key_data=key_data),project=PROJECT_ID)
else: ee.Initialize(project=PROJECT_ID)

def sb_exec(fn):
    delay=2
    for attempt in range(RETRIES):
        try: return fn()
        except Exception as exc:
            if attempt==RETRIES-1: raise
            print(f"Supabase retry {attempt+1}/{RETRIES}: {type(exc).__name__}"); time.sleep(delay); delay*=2

def get_one(table,**filters):
    q=sb.table(table).select("*")
    for n,v in filters.items(): q=q.eq(n,v)
    r=sb_exec(lambda:q.limit(1).execute())
    if not r.data: raise RuntimeError(f"No existe {table}: {filters}")
    return r.data[0]

region=get_one("nora_regions",region_id=REGION_KEY); region_db_id=region["id"]
geom=region.get("geometry") or {}
if geom.get("type")!="bbox": raise RuntimeError("La región debe tener geometry tipo bbox.")
lon_min,lat_min,lon_max,lat_max=map(float,geom["coordinates"]); grid_size=float(region.get("grid_size_deg") or .1)
lons=[round(lon_min+i*grid_size,8) for i in range(math.ceil((lon_max-lon_min)/grid_size))]
lats=[round(lat_min+j*grid_size,8) for j in range(math.ceil((lat_max-lat_min)/grid_size))]
features=[]
for i,lon in enumerate(lons):
    for j,lat in enumerate(lats):
        features.append(ee.Feature(ee.Geometry.Rectangle([lon,lat,min(lon+grid_size,lon_max),min(lat+grid_size,lat_max)]),{"cell_id":i*len(lats)+j,"longitude":lon+grid_size/2,"latitude":lat+grid_size/2}))
grid=ee.FeatureCollection(features)
print(f"NORA | region={REGION_KEY} | cells={len(features)} | years={START_YEAR}-{END_YEAR} | profile={PROFILE} | smoke_month={SMOKE_MONTH}")
vars_db=sb_exec(lambda:sb.table("nora_variables").select("id,key,unit,source_id").execute()).data; VAR={r["key"]:r for r in vars_db}

def month_hours(y,m): return int(pd.Period(f"{y}-{m:02d}").days_in_month)*24
def add_collection(image,cid,band,out,start,end,factor=1.,offset=0.,reducer="mean"):
    c=ee.ImageCollection(cid).filterDate(start,end).select(band); v=(c.sum() if reducer=="sum" else c.mean()).multiply(factor).add(offset).rename(out); return image.addBands(v)
def monthly_image(y,m):
    start=ee.Date.fromYMD(y,m,1); end=start.advance(1,"month"); days=month_hours(y,m)/24.; era=ee.ImageCollection("ECMWF/ERA5_LAND/MONTHLY_AGGR").filterDate(start,end).mean()
    temp=era.select("temperature_2m").subtract(273.15); dew=era.select("dewpoint_temperature_2m").subtract(273.15)
    es=temp.expression("0.6108 * exp(17.27*t/(t+237.3)",{"t":temp}); ea=dew.expression("0.6108 * exp(17.27*t/(t+237.3)",{"t":dew})
    img=ee.Image.cat([era.select("total_precipitation_sum").multiply(1000).rename("precip_mm"),temp.rename("temp_c"),era.select("runoff_sum").multiply(1000).rename("runoff_mm"),era.select("surface_runoff_sum").multiply(1000).rename("surface_runoff_mm"),era.select("sub_surface_runoff_sum").multiply(1000).rename("subsurface_runoff_mm"),era.select("total_evaporation_sum").multiply(-1000).rename("evapotranspiration_mm"),era.select("potential_evaporation_sum").multiply(1000).rename("potential_evapotranspiration_mm"),era.select("volumetric_soil_water_layer_1").rename("soil_moisture_surface"),era.select(["volumetric_soil_water_layer_1","volumetric_soil_water_layer_2","volumetric_soil_water_layer_3"]).reduce(ee.Reducer.mean()).rename("soil_moisture_rootzone"),es.subtract(ea).max(0).rename("vpd_kpa"),era.select("u_component_of_wind_10m").pow(2).add(era.select("v_component_of_wind_10m").pow(2)).sqrt().rename("wind_speed_ms"),era.select("surface_solar_radiation_downwards_sum").divide(days*86400).rename("surface_radiation_wm2"),era.select("surface_pressure").rename("surface_pressure_pa")])
    img=add_collection(img,"MODIS/061/MOD13Q1","NDVI","ndvi",start,end,.0001); img=add_collection(img,"MODIS/061/MOD13Q1","EVI","evi",start,end,.0001)
    img=add_collection(img,"MODIS/061/MOD11A2","LST_Day_1km","lst_day_c",start,end,.02,-273.15); img=add_collection(img,"MODIS/061/MOD11A2","LST_Night_1km","lst_night_c",start,end,.02,-273.15)
    img=add_collection(img,"MODIS/061/MCD15A3H","Lai","lai",start,end,.1); img=add_collection(img,"MODIS/061/MCD15A3H","Fpar","fpar",start,end,.01); img=add_collection(img,"NASA/GPM_L3/IMERG_V07","precipitation","gpm_precip_mm",start,end,days*24.)
    if y>=2015:
        img=add_collection(img,"NASA/SMAP/SPL4SMGP/008","sm_surface","smap_surface_soil_moisture",start,end); img=add_collection(img,"NASA/SMAP/SPL4SMGP/008","sm_rootzone","smap_rootzone_soil_moisture",start,end)
    if y>=2018:
        for cid,band,out in [("COPERNICUS/S5P/OFFL/L3_CLOUD","cloud_fraction","cloud_fraction"),("COPERNICUS/S5P/OFFL/L3_CLOUD","cloud_top_height","cloud_top_height_m"),("COPERNICUS/S5P/OFFL/L3_CLOUD","cloud_optical_depth","cloud_optical_depth"),("COPERNICUS/S5P/OFFL/L3_CO","CO_column_number_density","co_mol_m2"),("COPERNICUS/S5P/OFFL/L3_NO2","tropospheric_NO2_column_number_density","no2_mol_m2")]: img=add_collection(img,cid,band,out,start,end)
    if y>=2019:
        img=add_collection(img,"COPERNICUS/S5P/OFFL/L3_CH4","CH4_column_volume_mixing_ratio_dry_air","ch4_ppb",start,end); img=add_collection(img,"COPERNICUS/S5P/OFFL/L3_CH4","aerosol_optical_depth","aod",start,end)
    if y>=2021: img=add_collection(img,"MODIS/061/MOD17A2H","Gpp","gpp",start,end,.0001,reducer="sum")
    return img

BANDS={"precip_mm":"precip_mm","temp_c":"temp_c","ndvi":"ndvi","evi":"evi","runoff_mm":"runoff_mm","surface_runoff_mm":"surface_runoff_mm","subsurface_runoff_mm":"subsurface_runoff_mm","evapotranspiration_mm":"evapotranspiration_mm","potential_evapotranspiration_mm":"potential_evapotranspiration_mm","soil_moisture_surface":"soil_moisture_surface","soil_moisture_rootzone":"soil_moisture_rootzone","lst_day_c":"lst_day_c","lst_night_c":"lst_night_c","lai":"lai","fpar":"fpar","vpd_kpa":"vpd_kpa","wind_speed_ms":"wind_speed_ms","surface_radiation_wm2":"surface_radiation_wm2","surface_pressure_pa":"surface_pressure_pa","gpm_precip_mm":"gpm_precip_mm","smap_surface_soil_moisture":"smap_surface_soil_moisture","smap_rootzone_soil_moisture":"smap_rootzone_soil_moisture","cloud_fraction":"cloud_fraction","cloud_top_height_m":"cloud_top_height_m","cloud_optical_depth":"cloud_optical_depth","co_mol_m2":"co_mol_m2","no2_mol_m2":"no2_mol_m2","ch4_ppb":"ch4_ppb","gpp":"gpp","aod":"aod","lst_day_c":"lst_day_c","lst_night_c":"lst_night_c"}
if PROFILE=="core": BANDS={k:v for k,v in BANDS.items() if k in {"precip_mm","temp_c","ndvi","runoff_mm","evapotranspiration_mm","soil_moisture_rootzone","lst_day_c","lai","vpd_kpa","gpm_precip_mm","cloud_fraction"}}

def upload_rows(rows):
    for start in range(0,len(rows),BATCH_SIZE):
        batch=rows[start:start+BATCH_SIZE]
        for attempt in range(RETRIES):
            try:
                sb.table("nora_observations").upsert(batch,on_conflict="region_id,variable_id,cell_id,observed_at",ignore_duplicates=False).execute(); break
            except Exception as exc:
                if attempt==RETRIES-1: raise
                print(f"Supabase batch retry {attempt+1}/{RETRIES}: {type(exc).__name__}"); time.sleep(2**attempt)

for year in range(START_YEAR,END_YEAR+1):
    for month in ([SMOKE_MONTH] if SMOKE_MONTH else range(1,13)):
        observed_at=f"{year}-{month:02d}-01T00:00:00+00:00"
        existing=sb_exec(lambda:sb.table("nora_observations").select("variable_id").eq("region_id",region_db_id).eq("observed_at",observed_at).execute()).data or []
        existing_ids={r["variable_id"] for r in existing}; required={VAR[k]["id"] for k in BANDS if k in VAR}
        if required and required.issubset(existing_ids): print(f"SKIP {observed_at[:7]}: checkpoint completo ({len(required)} variables)"); continue
        image=monthly_image(year,month); band_names=set(image.bandNames().getInfo()); active=[(k,b) for k,b in BANDS.items() if k in VAR and b in band_names]
        if not active: print(f"SKIP {observed_at[:7]}: sin bandas activas"); continue
        reduced=image.select([b for _,b in active]).reduceRegions(collection=grid,reducer=ee.Reducer.mean(),scale=11132,tileScale=4).getInfo()["features"]
        rows=[]
        for f in reduced:
            p=f["properties"]; cid=int(p["cell_id"])
            for k,b in active:
                v=p.get(b)
                if v is None or not isinstance(v,(int,float)) or not math.isfinite(float(v)): continue
                rows.append({"region_id":region_db_id,"variable_id":VAR[k]["id"],"source_id":VAR[k]["source_id"],"cell_id":cid,"longitude":p.get("longitude"),"latitude":p.get("latitude"),"observed_at":observed_at,"value":float(v),"unit":VAR[k]["unit"],"metadata":{"profile":PROFILE,"aggregation":"monthly_mean","earth_engine_band":b,"source_period":f"{year}-{month:02d}"}})
        upload_rows(rows); print(f"OK {year}-{month:02d}: {len(reduced)} cells / {len(rows)} observations / {len(active)} variables")
print("NORA: ingesta ampliada completada.")