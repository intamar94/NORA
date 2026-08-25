"""
INGESTA ROBUSTA - Cuenca Alto Xingu (Mato Grosso, Brasil)
Proyecto NORA - Earth System / descubrimiento cientifico

Bloque 1: NDVI, precipitacion, temperatura y SoilGrids.
Periodo temporal: 2001-2024, mensual.
"""

import json
import os
import time
from pathlib import Path

import ee
import numpy as np
import pandas as pd

PROJECT_ID = "nora-506511"
START_YEAR = 2001
END_YEAR = 2024
CELL_SIZE_DEG = 0.1
CHECKPOINT_DIR = Path("checkpoints_alto_xingu")
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 3
TILE_SCALE = 4
OUTPUT_PATH = "alto_xingu_ingesta_2001_2024.csv"


def initialize_ee():
    """Inicializa Earth Engine sin autenticacion interactiva."""
    raw_key = os.environ.get("GEE_SERVICE_ACCOUNT_KEY")
    if not raw_key:
        raise RuntimeError("Falta el secret GEE_SERVICE_ACCOUNT_KEY.")

    try:
        key_info = json.loads(raw_key)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GEE_SERVICE_ACCOUNT_KEY no contiene JSON valido.") from exc

    client_email = key_info.get("client_email")
    if not client_email:
        raise RuntimeError("La clave GEE_SERVICE_ACCOUNT_KEY no contiene client_email.")

    credentials = ee.ServiceAccountCredentials(client_email, key_data=raw_key)
    ee.Initialize(credentials=credentials, project=PROJECT_ID)
    print(f"Conexion a Earth Engine: OK (service account {client_email})")


initialize_ee()

AOI_BOUNDS = {
    "lon_min": -55.2,
    "lon_max": -51.3,
    "lat_min": -15.2,
    "lat_max": -10.5,
}

aoi = ee.Geometry.Rectangle([
    AOI_BOUNDS["lon_min"], AOI_BOUNDS["lat_min"],
    AOI_BOUNDS["lon_max"], AOI_BOUNDS["lat_max"]
])


def build_grid(bounds, cell_size):
    lons = np.arange(bounds["lon_min"], bounds["lon_max"], cell_size)
    lats = np.arange(bounds["lat_min"], bounds["lat_max"], cell_size)
    features = []
    cell_id = 0
    for lon in lons:
        for lat in lats:
            rect = ee.Geometry.Rectangle([
                float(lon), float(lat), float(lon + cell_size), float(lat + cell_size)
            ])
            features.append(ee.Feature(rect, {
                "cell_id": cell_id,
                "centroid_lon": float(lon + cell_size / 2),
                "centroid_lat": float(lat + cell_size / 2),
            }))
            cell_id += 1
    return ee.FeatureCollection(features)


grid = build_grid(AOI_BOUNDS, CELL_SIZE_DEG)
n_cells = grid.size().getInfo()
months = pd.date_range(f"{START_YEAR}-01-01", f"{END_YEAR}-12-01", freq="MS")
TOTAL_MONTHS = len(months)
SOIL_PROPS = ["clay", "sand", "soc", "phh2o"]
SOIL_DEPTHS = ["0-5cm", "5-15cm", "15-30cm", "30-60cm", "60-100cm", "100-200cm"]


def get_soilgrids_image():
    bands = []
    for prop in SOIL_PROPS:
        img = ee.Image(f"projects/soilgrids-isric/{prop}_mean")
        for depth in SOIL_DEPTHS:
            bands.append(img.select(f"{prop}_{depth}_mean"))
    return ee.Image.cat(bands)


def get_ndvi_monthly(year, month):
    start = ee.Date.fromYMD(year, month, 1)
    return ee.ImageCollection("MODIS/061/MOD13A3").filterDate(start, start.advance(1, "month")).select("NDVI").mean().multiply(0.0001).rename("ndvi")


def get_chirps_monthly(year, month):
    start = ee.Date.fromYMD(year, month, 1)
    return ee.ImageCollection("UCSB-CHG/CHIRPS/PENTAD").filterDate(start, start.advance(1, "month")).select("precipitation").sum().rename("precip_mm")


def get_era5_monthly(year, month):
    start = ee.Date.fromYMD(year, month, 1)
    return ee.ImageCollection("ECMWF/ERA5_LAND/MONTHLY_AGGR").filterDate(start, start.advance(1, "month")).select("temperature_2m").mean().subtract(273.15).rename("temp_c")


def checkpoint_path(value_col):
    return CHECKPOINT_DIR / f"{value_col}_partial.csv"


def state_path(value_col):
    return CHECKPOINT_DIR / f"{value_col}_state.json"


def load_checkpoint(value_col):
    path = checkpoint_path(value_col)
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    required = {"cell_id", "year", "month"}
    if not required.issubset(df.columns):
        raise RuntimeError(f"Checkpoint invalido para {value_col}: faltan {required - set(df.columns)}")
    if df.duplicated(subset=["cell_id", "year", "month"]).any():
        raise RuntimeError(f"Checkpoint invalido para {value_col}: hay duplicados")
    return df


def save_checkpoint(value_col, df, year, month):
    path = checkpoint_path(value_col)
    tmp = path.with_suffix(".tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)
    state = {
        "variable": value_col,
        "last_year": int(year),
        "last_month": int(month),
        "months_completed": int(df[["year", "month"]].drop_duplicates().shape[0]),
        "rows": int(len(df)),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    state_path(value_col).write_text(json.dumps(state, indent=2), encoding="utf-8")


def run_with_retries(fn, description):
    delay = INITIAL_RETRY_DELAY
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn()
        except Exception as exc:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"Fallo definitivo en {description}: {exc}") from exc
            print(f"Error temporal en {description}. Reintento {attempt}/{MAX_RETRIES - 1} en {delay}s...")
            time.sleep(delay)
            delay *= 2


def reduce_image_to_grid(image, scale):
    return image.reduceRegions(collection=grid, reducer=ee.Reducer.mean(), scale=scale, tileScale=TILE_SCALE)


def fc_to_records(fc, value_col):
    records = []
    for feature in fc.getInfo()["features"]:
        props = feature["properties"]
        records.append({
            "cell_id": props.get("cell_id"),
            "centroid_lon": props.get("centroid_lon"),
            "centroid_lat": props.get("centroid_lat"),
            value_col: props.get("mean"),
        })
    return records


def extract_monthly_variable(get_image_fn, value_col, scale):
    existing = load_checkpoint(value_col)
    completed = set()
    if not existing.empty:
        completed = set(zip(existing["year"].astype(int), existing["month"].astype(int)))
    print(f">>> {value_col.upper()}: {len(completed)}/{TOTAL_MONTHS} meses ya completados")
    for ts in months:
        year, month = int(ts.year), int(ts.month)
        if (year, month) in completed:
            continue
        description = f"{value_col} {year}-{month:02d}"
        print(f"Procesando {description}...")
        image = get_image_fn(year, month)
        reduced = run_with_retries(lambda: reduce_image_to_grid(image, scale), description)
        recs = run_with_retries(lambda: fc_to_records(reduced, value_col), f"lectura {description}")
        if len(recs) != n_cells:
            raise RuntimeError(f"{description}: Earth Engine devolvio {len(recs)} celdas; se esperaban {n_cells}.")
        for rec in recs:
            rec["year"] = year
            rec["month"] = month
        month_df = pd.DataFrame(recs)
        existing = month_df if existing.empty else pd.concat([existing, month_df], ignore_index=True)
        save_checkpoint(value_col, existing, year, month)
        completed.add((year, month))
        print(f"OK | {len(completed)}/{TOTAL_MONTHS} | checkpoint guardado")
    return existing


print("=== NORA: INGESTA REANUDABLE ALTO XINGU ===")
print(f"Periodo: {START_YEAR}-{END_YEAR} | meses: {TOTAL_MONTHS} | celdas: {n_cells}")

df_ndvi = extract_monthly_variable(get_ndvi_monthly, "ndvi", 1000)
df_precip = extract_monthly_variable(get_chirps_monthly, "precip_mm", 5000)
df_temp = extract_monthly_variable(get_era5_monthly, "temp_c", 11132)

soil_checkpoint = CHECKPOINT_DIR / "soilgrids.csv"
if soil_checkpoint.exists():
    df_soil = pd.read_csv(soil_checkpoint)
else:
    soil_image = get_soilgrids_image()
    soil_reduced = run_with_retries(lambda: reduce_image_to_grid(soil_image, 250), "SoilGrids")
    soil_features = run_with_retries(lambda: soil_reduced.getInfo()["features"], "lectura SoilGrids")
    if len(soil_features) != n_cells:
        raise RuntimeError(f"SoilGrids devolvio {len(soil_features)} celdas; se esperaban {n_cells}.")
    soil_records = []
    for feature in soil_features:
        props = feature["properties"]
        rec = {"cell_id": props.get("cell_id")}
        for prop in SOIL_PROPS:
            for depth in SOIL_DEPTHS:
                band = f"{prop}_{depth}_mean"
                rec[band] = props.get(band)
        soil_records.append(rec)
    df_soil = pd.DataFrame(soil_records)
    tmp = soil_checkpoint.with_suffix(".tmp")
    df_soil.to_csv(tmp, index=False)
    os.replace(tmp, soil_checkpoint)

df = df_ndvi.merge(df_precip, on=["cell_id", "centroid_lon", "centroid_lat", "year", "month"], how="outer")
df = df.merge(df_temp, on=["cell_id", "centroid_lon", "centroid_lat", "year", "month"], how="outer")
df = df.merge(df_soil, on="cell_id", how="left")
df["date"] = pd.to_datetime(df[["year", "month"]].assign(day=1))
df = df.sort_values(["cell_id", "date"]).reset_index(drop=True)
expected_rows = n_cells * TOTAL_MONTHS
if len(df) != expected_rows:
    raise RuntimeError(f"Validacion final: {len(df)} filas; se esperaban {expected_rows}.")

df.to_csv(OUTPUT_PATH, index=False)
print(f"=== INGESTA COMPLETA: {OUTPUT_PATH} | {len(df):,} filas ===")
