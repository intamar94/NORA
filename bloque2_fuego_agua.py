import ee
import pandas as pd
import numpy as np
import time
import os
import json
from supabase import create_client

print("=== NORA bloque2_fuego_agua.py -- version 1 (2026-08) ===")

# ---------------------------------------------------------------
# SUPABASE
# ---------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Faltan SUPABASE_URL y/o SUPABASE_SERVICE_ROLE_KEY.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
TABLE_NAME = "nora_ingesta_alto_xingu"

# ---------------------------------------------------------------
# EARTH ENGINE
# ---------------------------------------------------------------
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

# ---------------------------------------------------------------
# MISMA AREA Y GRILLA QUE EL BLOQUE 1 -- tiene que coincidir exacto
# para que los cell_id sean los mismos.
# ---------------------------------------------------------------
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
            rect = ee.Geometry.Rectangle(
                [float(lon), float(lat), float(lon + cell_size), float(lat + cell_size)]
            )
            feat = ee.Feature(rect, {"cell_id": cell_id})
            features.append(feat)
            cell_id += 1
    return ee.FeatureCollection(features)


grid = build_grid(AOI_BOUNDS, CELL_SIZE_DEG)
n_cells = grid.size().getInfo()
print(f"Grilla: {n_cells} celdas (debe coincidir con el bloque 1: 1880)")

START_YEAR = 2001
END_YEAR = 2024
JRC_WATER_LAST_YEAR = 2021  # limite real del dataset mensual
months = pd.date_range(f"{START_YEAR}-01-01", f"{END_YEAR}-12-01", freq="MS")


# ---------------------------------------------------------------
# DATASETS
# ---------------------------------------------------------------
def get_burned_fraction_monthly(year, month):
    """Fraccion de la celda quemada ese mes. MCD64A1, banda BurnDate
    (0 = no quemado, >0 = dia del año en que se quemo). Se binariza y
    se promedia -- el promedio de una mascara 0/1 es la fraccion.

    IMPORTANTE: unmask(0) es obligatorio aca. Sin esto, Earth Engine
    excluye del promedio cualquier pixel que haya quedado enmascarado
    (lo cual incluye zonas no quemadas segun como viene la banda),
    y el resultado da 1.0 siempre que hay al menos un pixel quemado
    -- un error real que se detecto revisando los datos ya cargados
    (promedio exactamente 1.0000 en todos los años, imposible en la
    practica). unmask(0) fuerza a que "sin dato quemado" cuente como
    0 en el promedio, no que se excluya."""
    start = ee.Date.fromYMD(year, month, 1)
    end = start.advance(1, "month")
    coll = (ee.ImageCollection("MODIS/061/MCD64A1")
            .filterDate(start, end)
            .select("BurnDate"))
    img = coll.mosaic()
    burned_mask = img.gt(0).unmask(0).rename("burned_fraction")
    return burned_mask


def get_water_fraction_monthly(year, month):
    """Fraccion de la celda con agua superficial ese mes. JRC
    MonthlyHistory, banda 'water' (0=sin dato, 1=no agua, 2=agua).
    Se aisla el valor 2 y se promedia -- igual logica que burned."""
    img = ee.Image(f"JRC/GSW1_4/MonthlyHistory/{year}_{month:02d}")
    water_mask = img.select("water").eq(2).rename("water_fraction")
    return water_mask


def reduce_and_get(image, scale):
    reduced = image.reduceRegions(collection=grid, reducer=ee.Reducer.mean(), scale=scale)
    return reduced.getInfo()["features"]


def get_already_done_months():
    """Meses que YA tienen burned_fraction cargado -- para retomar sin
    repetir trabajo si se corta a mitad de camino."""
    result = (supabase.table(TABLE_NAME)
              .select("year, month")
              .not_.is_("burned_fraction", "null")
              .execute())
    done = set()
    for row in result.data:
        done.add((row["year"], row["month"]))
    return done


# ---------------------------------------------------------------
# EXTRACCION POR MES, CON CHECKPOINT
# ---------------------------------------------------------------
already_done = get_already_done_months()
if already_done:
    print(f"Retomando: {len(already_done)} meses ya tienen burned_fraction cargado, se saltan.")

meses_pendientes = [m for m in months if (m.year, m.month) not in already_done]
print(f"Meses a procesar en esta corrida: {len(meses_pendientes)} de {len(months)}")

if not meses_pendientes:
    print("Nada pendiente -- bloque 2 ya esta completo. Fin.")
    exit(0)

for i, ts in enumerate(meses_pendientes):
    year, month = ts.year, ts.month

    burned_img = get_burned_fraction_monthly(year, month)
    burned_feats = reduce_and_get(burned_img, 500)

    water_feats = []
    if year <= JRC_WATER_LAST_YEAR:
        try:
            water_img = get_water_fraction_monthly(year, month)
            water_feats = reduce_and_get(water_img, 100)
        except Exception as e:
            print(f"  Aviso: no se pudo extraer JRC water para {year}-{month:02d}: {e}")

    burned_by_cell = {f["properties"]["cell_id"]: f["properties"].get("mean") for f in burned_feats}
    water_by_cell = {f["properties"]["cell_id"]: f["properties"].get("mean") for f in water_feats}

    records = []
    for cid in burned_by_cell:
        rec = {
            "cell_id": cid,
            "year": year,
            "month": month,
            "burned_fraction": burned_by_cell.get(cid),
        }
        if cid in water_by_cell:
            rec["water_fraction"] = water_by_cell[cid]
        records.append(rec)

    # Upsert parcial: solo actualiza las columnas incluidas, no toca
    # ndvi/precip_mm/temp_c/suelo que ya estaban cargados por el bloque 1.
    supabase.table(TABLE_NAME).upsert(records, on_conflict="cell_id,year,month").execute()

    if (i + 1) % 6 == 0 or (i + 1) == len(meses_pendientes):
        water_note = "con agua" if year <= JRC_WATER_LAST_YEAR else "sin agua (>2021)"
        print(f"  Guardado: {i + 1}/{len(meses_pendientes)} meses de esta corrida "
              f"({year}-{month:02d}, {len(records)} celdas, {water_note})")

    time.sleep(0.2)

print("\nBloque 2 terminado.")
total = (supabase.table(TABLE_NAME)
         .select("id", count="exact")
         .not_.is_("burned_fraction", "null")
         .execute())
print(f"Filas con burned_fraction cargado: {total.count}")
total_agua = (supabase.table(TABLE_NAME)
              .select("id", count="exact")
              .not_.is_("water_fraction", "null")
              .execute())
print(f"Filas con water_fraction cargado (deberia ser solo 2001-2021): {total_agua.count}")
