"""
INGESTA ROBUSTA - Cuenca Alto Xingu (Mato Grosso, Brasil)
Proyecto NORA - Earth System / descubrimiento cientifico

Bloque 1: NDVI, precipitacion, temperatura y SoilGrids.
Periodo temporal: 2001-2024, mensual.

Esta version esta preparada para Codespaces y conexiones inestables:
- Reanuda desde el ultimo mes completado.
- Guarda un checkpoint CSV despues de CADA mes.
- Guarda un estado JSON con el ultimo mes procesado.
- Reintenta automaticamente errores transitorios de Earth Engine.
- No pierde toda la corrida si Codespaces se desconecta.
- No modifica ni borra checkpoints existentes al arrancar.
- Al terminar, genera el CSV final.

IMPORTANTE:
Los checkpoints son archivos LOCALES del Codespace y no se deben subir a Git.
El AOI sigue siendo un bounding box de piloto, NO el poligono hidrologico
real de la cuenca. Antes de interpretar resultados cientificos de la cuenca,
habra que sustituirlo por un poligono HydroSHEDS/ottobacias ANA.
"""

import json
import os
import time
from pathlib import Path

import ee
import numpy as np
import pandas as pd

# ---------------------------------------------------------------
# 0. CONFIGURACION
# ---------------------------------------------------------------
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

# ---------------------------------------------------------------
# 1. EARTH ENGINE
# ---------------------------------------------------------------
def initialize_ee():
    try:
        ee.Initialize(project=PROJECT_ID)
        print("Conexion a Earth Engine: OK")
    except Exception:
        print("No habia sesion activa; iniciando autenticacion...")
        ee.Authenticate()
        ee.Initialize(project=PROJECT_ID)
        print("Conexion a Earth Engine: OK (tras autenticar)")


initialize_ee()

# ---------------------------------------------------------------
# 2. AREA DE ESTUDIO - PILOTO
# ---------------------------------------------------------------
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

# ---------------------------------------------------------------
# 3. GRILLA
# ---------------------------------------------------------------
def build_grid(bounds, cell_size):
    lons = np.arange(bounds["lon_min"], bounds["lon_max"], cell_size)
    lats = np.arange(bounds["lat_min"], bounds["lat_max"], cell_size)
    features = []
    cell_id = 0

    for lon in lons:
        for lat in lats:
            rect = ee.Geometry.Rectangle([
                float(lon), float(lat),
                float(lon + cell_size), float(lat + cell_size)
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
print(
    f"Grilla construida: {n_cells} celdas de {CELL_SIZE_DEG} grados "
    f"(~{CELL_SIZE_DEG * 111:.0f} km de lado)"
)

# ---------------------------------------------------------------
# 4. PERIODO
# ---------------------------------------------------------------
months = pd.date_range(
    f"{START_YEAR}-01-01",
    f"{END_YEAR}-12-01",
    freq="MS"
)
TOTAL_MONTHS = len(months)

# ---------------------------------------------------------------
# 5. DATASETS
# ---------------------------------------------------------------
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
    end = start.advance(1, "month")
    return (
        ee.ImageCollection("MODIS/061/MOD13A3")
        .filterDate(start, end)
        .select("NDVI")
        .mean()
        .multiply(0.0001)
        .rename("ndvi")
    )


def get_chirps_monthly(year, month):
    start = ee.Date.fromYMD(year, month, 1)
    end = start.advance(1, "month")
    return (
        ee.ImageCollection("UCSB-CHG/CHIRPS/PENTAD")
        .filterDate(start, end)
        .select("precipitation")
        .sum()
        .rename("precip_mm")
    )


def get_era5_monthly(year, month):
    start = ee.Date.fromYMD(year, month, 1)
    end = start.advance(1, "month")
    return (
        ee.ImageCollection("ECMWF/ERA5_LAND/MONTHLY_AGGR")
        .filterDate(start, end)
        .select("temperature_2m")
        .mean()
        .subtract(273.15)
        .rename("temp_c")
    )

# ---------------------------------------------------------------
# 6. UTILIDADES DE ROBUSTEZ
# ---------------------------------------------------------------
def format_duration(seconds):
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def checkpoint_path(value_col):
    return CHECKPOINT_DIR / f"{value_col}_partial.csv"


def state_path(value_col):
    return CHECKPOINT_DIR / f"{value_col}_state.json"


def load_checkpoint(value_col):
    path = checkpoint_path(value_col)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
        print(f"Checkpoint encontrado: {path} ({len(df):,} filas)")
        return df
    except Exception as exc:
        print(f"ATENCION: no se pudo leer {path}: {exc}")
        return pd.DataFrame()


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
    state_path(value_col).write_text(
        json.dumps(state, indent=2),
        encoding="utf-8"
    )


def run_with_retries(fn, description):
    delay = INITIAL_RETRY_DELAY
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn()
        except Exception as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                break
            print(
                f"  Error temporal en {description}. "
                f"Reintento {attempt}/{MAX_RETRIES - 1} en {delay}s..."
            )
            time.sleep(delay)
            delay *= 2

    raise RuntimeError(
        f"Fallo definitivo en {description} despues de {MAX_RETRIES} intentos: {last_error}"
    )


def reduce_image_to_grid(image, scale):
    return image.reduceRegions(
        collection=grid,
        reducer=ee.Reducer.mean(),
        scale=scale,
        tileScale=TILE_SCALE,
    )


def fc_to_records(fc, value_col):
    features = fc.getInfo()["features"]
    records = []
    for feature in features:
        props = feature["properties"]
        records.append({
            "cell_id": props.get("cell_id"),
            "centroid_lon": props.get("centroid_lon"),
            "centroid_lat": props.get("centroid_lat"),
            value_col: props.get("mean"),
        })
    return records

# ---------------------------------------------------------------
# 7. EXTRACCION TEMPORAL REANUDABLE
# ---------------------------------------------------------------
def extract_monthly_variable(get_image_fn, value_col, scale):
    existing = load_checkpoint(value_col)
    completed = set()

    if not existing.empty and {"year", "month"}.issubset(existing.columns):
        completed = set(
            zip(existing["year"].astype(int), existing["month"].astype(int))
        )

    print(f"\n>>> {value_col.upper()}: {len(completed)}/{TOTAL_MONTHS} meses ya completados")

    started = time.time()
    processed_this_run = 0

    for ts in months:
        year, month = int(ts.year), int(ts.month)
        key = (year, month)

        if key in completed:
            continue

        description = f"{value_col} {year}-{month:02d}"
        print(f"  Procesando {description}...")
        month_started = time.time()

        image = get_image_fn(year, month)
        reduced = run_with_retries(
            lambda: reduce_image_to_grid(image, scale),
            description
        )
        recs = run_with_retries(
            lambda: fc_to_records(reduced, value_col),
            f"lectura {description}"
        )

        for rec in recs:
            rec["year"] = year
            rec["month"] = month

        month_df = pd.DataFrame(recs)
        if existing.empty:
            existing = month_df
        else:
            existing = pd.concat([existing, month_df], ignore_index=True)

        save_checkpoint(value_col, existing, year, month)
        completed.add(key)
        processed_this_run += 1

        total_completed = len(completed)
        elapsed = time.time() - started
        rate = processed_this_run / elapsed if elapsed > 0 else 0
        remaining = (TOTAL_MONTHS - total_completed) / rate if rate > 0 else 0
        pct = total_completed / TOTAL_MONTHS * 100

        print(
            f"    OK | {total_completed:3d}/{TOTAL_MONTHS} | {pct:5.1f}% "
            f"| mes {format_duration(time.time() - month_started)} "
            f"| restante aprox. {format_duration(remaining)} "
            f"| checkpoint guardado"
        )

    print(f"<<< {value_col.upper()}: COMPLETO | {TOTAL_MONTHS}/{TOTAL_MONTHS} | 100.0%")
    return existing

# ---------------------------------------------------------------
# 8. EJECUCION
# ---------------------------------------------------------------
print("\n=== NORA: INGESTA REANUDABLE ALTO XINGU ===")
print(f"Periodo: {START_YEAR}-{END_YEAR} | meses: {TOTAL_MONTHS} | celdas: {n_cells}")
print(f"Checkpoints: {CHECKPOINT_DIR.resolve()}")

df_ndvi = extract_monthly_variable(get_ndvi_monthly, "ndvi", 1000)
df_precip = extract_monthly_variable(get_chirps_monthly, "precip_mm", 5000)
df_temp = extract_monthly_variable(get_era5_monthly, "temp_c", 11132)

# ---------------------------------------------------------------
# 9. SOILGRIDS ESTATICO, TAMBIEN REANUDABLE
# ---------------------------------------------------------------
soil_checkpoint = CHECKPOINT_DIR / "soilgrids.csv"

if soil_checkpoint.exists():
    print("SoilGrids: checkpoint encontrado; reutilizando datos existentes.")
    df_soil = pd.read_csv(soil_checkpoint)
else:
    print("\n>>> SOILGRIDS: extraccion estatica...")
    soil_image = get_soilgrids_image()
    soil_reduced = run_with_retries(
        lambda: reduce_image_to_grid(soil_image, 250),
        "SoilGrids"
    )
    soil_features = run_with_retries(
        lambda: soil_reduced.getInfo()["features"],
        "lectura SoilGrids"
    )

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
    print(f"SoilGrids: COMPLETO | {len(df_soil)} celdas | checkpoint guardado")

# ---------------------------------------------------------------
# 10. FUSION FINAL
# ---------------------------------------------------------------
print("\n>>> Fusionando checkpoints...")
merge_keys = ["cell_id", "centroid_lon", "centroid_lat", "year", "month"]

df = df_ndvi.merge(df_precip, on=merge_keys, how="outer")
df = df.merge(df_temp, on=merge_keys, how="outer")
df = df.merge(df_soil, on="cell_id", how="left")

df["date"] = pd.to_datetime(df[["year", "month"]].assign(day=1))
df = df.sort_values(["cell_id", "date"]).reset_index(drop=True)

expected_rows = n_cells * TOTAL_MONTHS
unique_months = df[["year", "month"]].drop_duplicates().shape[0]
unique_cells = df["cell_id"].nunique()

print(f"Filas finales: {len(df):,}")
print(f"Celdas unicas: {unique_cells} / {n_cells}")
print(f"Meses presentes: {unique_months} / {TOTAL_MONTHS}")
print(f"Filas teoricas esperadas: {expected_rows:,}")

if unique_cells != n_cells or unique_months != TOTAL_MONTHS:
    raise RuntimeError(
        "VALIDACION FALLIDA: faltan celdas o meses. "
        "No se genera el CSV final para evitar presentar una ingesta incompleta como valida."
    )

final_tmp = Path(OUTPUT_PATH).with_suffix(".tmp")
df.to_csv(final_tmp, index=False)
os.replace(final_tmp, OUTPUT_PATH)

print(f"Guardado: {OUTPUT_PATH}")
print("\n=== INGESTA ALTO XINGU FINALIZADA Y VALIDADA ===")
