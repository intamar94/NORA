"""
Ingesta de datos multidominio - Cuenca Alto Xingu (Mato Grosso, Brasil)
Proyecto: IA de descubrimiento cientifico - Earth System
Bloque 1 de 2: Suelo, Vegetacion, Precipitacion, Temperatura (2001-2024, mensual)

Sentinel-5P, VIIRS y GRACE quedan para el bloque 2.

REQUISITOS:
    pip install earthengine-api pandas numpy supabase
    Cuenta de Google Earth Engine activada (https://earthengine.google.com/)
    Un proyecto de Google Cloud asociado a esa cuenta (obligatorio desde 2024)
    Ejecutar ee.Authenticate() una vez por maquina (abre navegador)
    Variables de entorno SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY exportadas
    (ver mas abajo, cerca de donde se usan, para no dejarlas escritas aca)

CHECKPOINT / REANUDACION:
    Este script guarda en Supabase mes a mes, no al final. Si se corta o lo
    parás a mitad de camino, podés volver a correrlo tal cual -- primero
    consulta que meses ya estan guardados y arranca desde donde quedo, sin
    duplicar filas (usa upsert sobre la clave unica cell_id+year+month).
"""

import ee
import pandas as pd
import numpy as np
import time
import os
import json
from supabase import create_client

print("=== NORA ingesta_alto_xingu.py -- version Supabase-checkpoint (2026-08) ===")

# ---------------------------------------------------------------
# SUPABASE -- credenciales via variables de entorno, NUNCA hardcodeadas
# ---------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "Faltan las variables de entorno SUPABASE_URL y/o "
        "SUPABASE_SERVICE_ROLE_KEY."
    )

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
TABLE_NAME = "nora_ingesta_alto_xingu"

# ---------------------------------------------------------------
# 0. INICIALIZACION
# ---------------------------------------------------------------
PROJECT_ID = "nora-506511"

# Autenticacion:
# - En GitHub Actions (automatizado): usa la cuenta de servicio, via el
#   secret GEE_SERVICE_ACCOUNT_KEY (contenido JSON completo de la clave).
# - En Codespaces / uso local (manual): si no encuentra ese secret, cae
#   al login interactivo de siempre (ee.Authenticate()).
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
        print("No habia sesion activa, iniciando autenticacion interactiva...")
        ee.Authenticate()
        ee.Initialize(project=PROJECT_ID)
        print("Conexion a Earth Engine: OK (tras autenticar)")

# ---------------------------------------------------------------
# 1. AREA DE ESTUDIO: cuenca Alto Xingu (Mato Grosso, Brasil)
# ---------------------------------------------------------------
# Bounding box RECTANGULAR que aproxima la cuenca del Alto Xingu
# (~176.000 km2 segun Coe et al. 2013, "The Forests of the Amazon and
# Cerrado Moderate Regional Climate and Are the Key to the Future").
#
# OJO: esto NO es el poligono real de la cuenca. Un rectangulo va a
# incluir celdas que en realidad drenan hacia cuencas vecinas
# (Teles Pires/Tapajos al oeste, Araguaia al este). Para el piloto es
# aceptable -- sirve para probar que la ingesta funciona -- pero antes
# de interpretar resultados como "de la cuenca del Alto Xingu" habria
# que recortar con un poligono real (HydroSHEDS nivel 6/7, o las
# ottobacias de la ANA de Brasil) y volver a correr este script.
AOI_BOUNDS = {
    "lon_min": -55.2,
    "lon_max": -51.3,
    "lat_min": -15.2,
    "lat_max": -10.5,
}
aoi = ee.Geometry.Rectangle(
    [AOI_BOUNDS["lon_min"], AOI_BOUNDS["lat_min"],
     AOI_BOUNDS["lon_max"], AOI_BOUNDS["lat_max"]]
)

# ---------------------------------------------------------------
# 2. GRILLA DE ANALISIS
# ---------------------------------------------------------------
# Resolucion comun elegida: 0.1 grados (~11 km), que es la resolucion
# nativa de ERA5-Land -- el mas grueso de los cuatro datasets de este
# bloque. Decision explicita: en vez de resamplear todo a la
# resolucion mas fina (SoilGrids, 250m) e inventar precision que no
# existe, se agrega todo a la resolucion del dato mas grueso.
#
# Con este bounding box y 0.1 grados salen ~1.400-1.500 celdas.
# Esto ES ingestable, pero para el bloque de PCMCI (siguiente etapa)
# 1.400+ series temporales por variable es demasiado para Tigramite
# de forma directa -- va a hacer falta agregar a subregiones o
# clusters antes de correr causal discovery. Ese ajuste queda para
# el bloque 2, no se resuelve aca.
CELL_SIZE_DEG = 0.1


def build_grid(bounds, cell_size):
    lons = np.arange(bounds["lon_min"], bounds["lon_max"], cell_size)
    lats = np.arange(bounds["lat_min"], bounds["lat_max"], cell_size)
    features = []
    centroids = {}
    cell_id = 0
    for lon in lons:
        for lat in lats:
            rect = ee.Geometry.Rectangle(
                [float(lon), float(lat), float(lon + cell_size), float(lat + cell_size)]
            )
            centroid_lon = float(lon + cell_size / 2)
            centroid_lat = float(lat + cell_size / 2)
            feat = ee.Feature(rect, {
                "cell_id": cell_id,
                "centroid_lon": centroid_lon,
                "centroid_lat": centroid_lat,
            })
            features.append(feat)
            centroids[cell_id] = (centroid_lon, centroid_lat)
            cell_id += 1
    return ee.FeatureCollection(features), centroids


grid, cell_centroids = build_grid(AOI_BOUNDS, CELL_SIZE_DEG)
n_cells = grid.size().getInfo()
print(f"Grilla construida: {n_cells} celdas de {CELL_SIZE_DEG} grados "
      f"(~{CELL_SIZE_DEG*111:.0f} km de lado)")

# ---------------------------------------------------------------
# 3. RANGO TEMPORAL
# ---------------------------------------------------------------
START_YEAR = 2001
END_YEAR = 2024
months = pd.date_range(f"{START_YEAR}-01-01", f"{END_YEAR}-12-01", freq="MS")

# ---------------------------------------------------------------
# 4. DATASETS
# ---------------------------------------------------------------

# 4.1 SoilGrids (ISRIC) -- ES ESTATICO, no es serie temporal.
#
# CORRECCION AL DOCUMENTO BASE: en la tabla de "dominios fuertes
# (temporales, densos, listos)" del documento de proyecto, SoilGrids
# aparece junto a datasets que si tienen series temporales
# (NDVI, CHIRPS, ERA5-Land, etc). Eso es un error -- SoilGrids es un
# mapa de una unica epoca (no hay "SoilGrids de 2015" vs "SoilGrids
# de 2020"). Se trata aca como covariable fija por celda, igual que
# geologia/topografia en la seccion de "dominios debiles/estaticos"
# del documento. Esto tiene una consecuencia para el bloque de PCMCI:
# el suelo puede entrar como confusor/covariable de contexto, pero NO
# como nodo con dinamica temporal propia en el grafo causal.
SOIL_PROPS = ["clay", "sand", "soc", "phh2o"]
SOIL_DEPTHS = ["0-5cm", "5-15cm", "15-30cm", "30-60cm", "60-100cm", "100-200cm"]

# SUPUESTO SIN VERIFICAR: se asume que cada imagen
# projects/soilgrids-isric/{prop}_mean contiene una banda por
# profundidad con el nombre "{prop}_{depth}_mean". No pude confirmar
# esto contra el catalogo real (solo confirme que el asset raiz
# existe). ANTES de correr el resto del script, correr el bloque de
# abajo y comparar contra SOIL_DEPTHS/SOIL_PROPS:
#
#   img = ee.Image("projects/soilgrids-isric/clay_mean")
#   print(img.bandNames().getInfo())
#
# y ajustar los nombres de banda si no coinciden.

def get_soilgrids_image():
    bands = []
    for prop in SOIL_PROPS:
        img = ee.Image(f"projects/soilgrids-isric/{prop}_mean")
        for depth in SOIL_DEPTHS:
            band_name = f"{prop}_{depth}_mean"
            bands.append(img.select(band_name))
    return ee.Image.cat(bands)


soil_image = get_soilgrids_image()


# 4.2 MODIS NDVI mensual -- MOD13A3.061 (Terra, 1 km, mensual nativo)
# Rango confirmado en catalogo EE: 2000-02-01 a 2026, cubre 2001-2024
# sin problema. Factor de escala oficial NDVI: 0.0001 (banda viene
# como entero escalado, rango real post-escala es -1 a 1).
def get_ndvi_monthly(year, month):
    start = ee.Date.fromYMD(year, month, 1)
    end = start.advance(1, "month")
    coll = (ee.ImageCollection("MODIS/061/MOD13A3")
            .filterDate(start, end)
            .select("NDVI"))
    # MOD13A3 ya es mensual (deberia haber 1 imagen por mes). Se usa
    # mean() como salvaguarda si hubiera mas de una.
    return coll.mean().multiply(0.0001).rename("ndvi")


# 4.3 CHIRPS precipitacion -- UCSB-CHG/CHIRPS/PENTAD (0.05 grados, ~5.5km)
# Nativamente pentadal (6 pentadas por mes calendario, la ultima con
# dias sobrantes). Se agrega a mensual sumando las pentadas del mes.
# Rango confirmado: 1981-2025+, cubre 2001-2024.
def get_chirps_monthly(year, month):
    start = ee.Date.fromYMD(year, month, 1)
    end = start.advance(1, "month")
    coll = (ee.ImageCollection("UCSB-CHG/CHIRPS/PENTAD")
            .filterDate(start, end)
            .select("precipitation"))
    return coll.sum().rename("precip_mm")


# 4.4 ERA5-Land temperatura -- ECMWF/ERA5_LAND/MONTHLY_AGGR (0.1 grados,
# ~11km, agregado mensual nativo). Rango confirmado: 1950-2026.
# Banda temperature_2m viene en Kelvin -> se convierte a Celsius.
def get_era5_monthly(year, month):
    start = ee.Date.fromYMD(year, month, 1)
    end = start.advance(1, "month")
    coll = (ee.ImageCollection("ECMWF/ERA5_LAND/MONTHLY_AGGR")
            .filterDate(start, end)
            .select("temperature_2m"))
    return coll.mean().subtract(273.15).rename("temp_c")


# ---------------------------------------------------------------
# 5. EXTRACCION (reduccion espacial celda por celda, mes por mes)
# ---------------------------------------------------------------
def reduce_image_to_grid(image, grid_fc, scale):
    return image.reduceRegions(
        collection=grid_fc,
        reducer=ee.Reducer.mean(),
        scale=scale,
    )


def fc_to_records(fc, value_col):
    features = fc.getInfo()["features"]
    records = []
    for f in features:
        props = f["properties"]
        records.append({
            "cell_id": props.get("cell_id"),
            "centroid_lon": props.get("centroid_lon"),
            "centroid_lat": props.get("centroid_lat"),
            value_col: props.get("mean"),
        })
    return records


def get_soil_records():
    """Extrae SoilGrids una sola vez (es estatico). Devuelve dict
    cell_id -> {columnas de suelo}."""
    print("Extrayendo SoilGrids (estatico, escala 250m)...")
    soil_reduced = reduce_image_to_grid(soil_image, grid, 250)
    soil_features = soil_reduced.getInfo()["features"]
    soil_by_cell = {}
    for f in soil_features:
        props = f["properties"]
        cell_id = props.get("cell_id")
        rec = {}
        for prop in SOIL_PROPS:
            for depth in SOIL_DEPTHS:
                band = f"{prop}_{depth}_mean"
                # Los nombres de columna en Supabase usan "_" en vez de "-"
                # (SQL no acepta guiones sin comillas) -- se ajusta aca.
                col_name = band.replace("-", "_")
                rec[col_name] = props.get(band)
        soil_by_cell[cell_id] = rec
    print(f"  SoilGrids: {len(soil_by_cell)} celdas")
    return soil_by_cell


def get_already_processed_months():
    """Consulta que meses ya estan guardados en Supabase, para poder
    retomar la corrida si se corto antes -- evita repetir trabajo y
    evita duplicar filas."""
    result = supabase.table(TABLE_NAME).select("year, month").execute()
    done = set()
    for row in result.data:
        done.add((row["year"], row["month"]))
    return done


# ---------------------------------------------------------------
# 6. EXTRACCION POR MES, CON CHECKPOINT A SUPABASE
# ---------------------------------------------------------------
soil_by_cell = get_soil_records()
already_done = get_already_processed_months()
if already_done:
    print(f"Retomando corrida: {len(already_done)} meses ya estaban en Supabase, se van a saltar.")

meses_pendientes = [m for m in months if (m.year, m.month) not in already_done]
print(f"Meses a procesar en esta corrida: {len(meses_pendientes)} de {len(months)}")

if not meses_pendientes:
    print("Nada pendiente -- la ingesta ya esta completa. Fin.")
    exit(0)

for i, ts in enumerate(meses_pendientes):
    year, month = ts.year, ts.month

    ndvi_img = get_ndvi_monthly(year, month)
    precip_img = get_chirps_monthly(year, month)
    temp_img = get_era5_monthly(year, month)

    ndvi_feats = reduce_image_to_grid(ndvi_img, grid, 1000).getInfo()["features"]
    precip_feats = reduce_image_to_grid(precip_img, grid, 5000).getInfo()["features"]
    temp_feats = reduce_image_to_grid(temp_img, grid, 11132).getInfo()["features"]

    # Union por cell_id de las 3 variables + suelo
    by_cell = {}
    for f in ndvi_feats:
        cid = f["properties"]["cell_id"]
        by_cell.setdefault(cid, {})["ndvi"] = f["properties"].get("mean")
    for f in precip_feats:
        cid = f["properties"]["cell_id"]
        by_cell.setdefault(cid, {})["precip_mm"] = f["properties"].get("mean")
    for f in temp_feats:
        cid = f["properties"]["cell_id"]
        by_cell.setdefault(cid, {})["temp_c"] = f["properties"].get("mean")

    records = []
    for cid, vals in by_cell.items():
        centroid_lon, centroid_lat = cell_centroids.get(cid, (None, None))
        rec = {
            "cell_id": cid,
            "centroid_lon": centroid_lon,
            "centroid_lat": centroid_lat,
            "year": year,
            "month": month,
            **vals,
            **soil_by_cell.get(cid, {}),
        }
        records.append(rec)

    # Upsert: si (cell_id, year, month) ya existe, actualiza; si no, inserta.
    # Esto es lo que hace posible retomar sin duplicar datos.
    supabase.table(TABLE_NAME).upsert(records, on_conflict="cell_id,year,month").execute()

    if (i + 1) % 6 == 0 or (i + 1) == len(meses_pendientes):
        print(f"  Guardado en Supabase: {i + 1}/{len(meses_pendientes)} meses de esta corrida "
              f"({year}-{month:02d}, {len(records)} celdas)")

    time.sleep(0.2)  # margen frente a rate limits de la API de EE

print("\nCorrida terminada.")
total = supabase.table(TABLE_NAME).select("id", count="exact").execute()
print(f"Filas totales en Supabase ({TABLE_NAME}): {total.count}")
print(f"Filas esperadas (celdas x meses): {n_cells * len(months)}")
