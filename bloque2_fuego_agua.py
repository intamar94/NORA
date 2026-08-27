import ee
import pandas as pd
import numpy as np
import time
import os
import json
from supabase import create_client

print("=== NORA bloque2_fuego_agua.py -- version 2 (2026-08) ===")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Faltan SUPABASE_URL y/o SUPABASE_SERVICE_ROLE_KEY.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
TABLE_NAME = "nora_ingesta_alto_xingu"

PROJECT_ID = "nora-506511"
service_account_json = os.environ.get("GEE_SERVICE_ACCOUNT_KEY")
if service_account_json:
    key_data = json.loads(service_account_json)
    credentials = ee.ServiceAccountCredentials(key_data["client_email"], key_data=service_account_json)
    ee.Initialize(credentials, project=PROJECT_ID)
    print("Conexion a Earth Engine: OK (cuenta de servicio)")
else:
    try:
        ee.Initialize(project=PROJECT_ID)
        print("Conexion a Earth Engine: OK (sesion existente)")
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=PROJECT_ID)
        print("Conexion a Earth Engine: OK (tras autenticar)")

AOI_BOUNDS = {
    "lon_min": -55.2,
    "lon_max": -51.3,
    "lat_min": -15.2,
    "lat_max": -10.5,
}
CELL_SIZE_DEG = 0.1


def build_grid(bounds, cell_size):
    lons = np.arange(bounds["lon_min"], bounds["lon_max"], cell_size)
    lats = np.arange(bounds["lat_min"], bounds["lat_max"], cell_size)
    features = []
    cell_id = 0
    for lon in lons:
        for lat in lats:
            rect = ee.Geometry.Rectangle([float(lon), float(lat), float(lon + cell_size), float(lat + cell_size)])
            features.append(ee.Feature(rect, {"cell_id": cell_id}))
            cell_id += 1
    return ee.FeatureCollection(features)


grid = build_grid(AOI_BOUNDS, CELL_SIZE_DEG)
n_cells = grid.size().getInfo()
print(f"Grilla: {n_cells} celdas (debe coincidir con el bloque 1: 1880)")

START_YEAR = 2001
END_YEAR = 2024
JRC_WATER_LAST_YEAR = 2021
months = pd.date_range(f"{START_YEAR}-01-01", f"{END_YEAR}-12-01", freq="MS")


def get_burned_fraction_monthly(year, month):
    start = ee.Date.fromYMD(year, month, 1)
    end = start.advance(1, "month")
    coll = (ee.ImageCollection("MODIS/061/MCD64A1")
            .filterDate(start, end)
            .select("BurnDate"))
    img = coll.mosaic()
    burned_mask = img.gt(0).unmask(0).rename("burned_fraction")
    return burned_mask


def get_water_fraction_monthly(year, month):
    img = ee.Image(f"JRC/GSW1_4/MonthlyHistory/{year}_{month:02d}")
    return img.select("water").eq(2).rename("water_fraction")


def reduce_and_get(image, scale):
    reduced = image.reduceRegions(collection=grid, reducer=ee.Reducer.mean(), scale=scale)
    return reduced.getInfo()["features"]


def get_already_done_months():
    result = (supabase.table(TABLE_NAME)
              .select("year, month")
              .not_.is_("burned_fraction", "null")
              .execute())
    return {(row["year"], row["month"]) for row in result.data}


already_done = get_already_done_months()
if already_done:
    print(f"Retomando: {len(already_done)} meses ya tienen burned_fraction cargado, se saltan.")

meses_pendientes = [m for m in months if (m.year, m.month) not in already_done]
print(f"Meses a procesar en esta corrida: {len(meses_pendientes)} de {len(months)}")

if not meses_pendientes:
    print("Nada pendiente -- bloque 2 ya esta completo. Fin.")
    raise SystemExit(0)

for i, ts in enumerate(meses_pendientes):
    year, month = ts.year, ts.month
    burned_feats = reduce_and_get(get_burned_fraction_monthly(year, month), 500)

    water_feats = []
    if year <= JRC_WATER_LAST_YEAR:
        try:
            water_feats = reduce_and_get(get_water_fraction_monthly(year, month), 100)
        except Exception as e:
            print(f"  Aviso: no se pudo extraer JRC water para {year}-{month:02d}: {e}")

    burned_by_cell = {f["properties"]["cell_id"]: f["properties"].get("mean") for f in burned_feats}
    water_by_cell = {f["properties"]["cell_id"]: f["properties"].get("mean") for f in water_feats}

    records = []
    for cid in burned_by_cell:
        rec = {"cell_id": cid, "year": year, "month": month, "burned_fraction": burned_by_cell.get(cid)}
        if cid in water_by_cell:
            rec["water_fraction"] = water_by_cell[cid]
        records.append(rec)

    supabase.table(TABLE_NAME).upsert(records, on_conflict="cell_id,year,month").execute()

    if (i + 1) % 6 == 0 or (i + 1) == len(meses_pendientes):
        water_note = "con agua" if year <= JRC_WATER_LAST_YEAR else "sin agua (>2021)"
        print(f"  Guardado: {i + 1}/{len(meses_pendientes)} meses de esta corrida ({year}-{month:02d}, {len(records)} celdas, {water_note})")
    time.sleep(0.2)

print("\nBloque 2 terminado.")
print("Verificacion final: se omiten COUNT(*) exactos para evitar statement timeout de Supabase.")
