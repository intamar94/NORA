"""
Ingesta de datos multidominio - Cuenca Alto Xingu (Mato Grosso, Brasil)
Proyecto: IA de descubrimiento cientifico - Earth System
Bloque 1 de 2: Suelo, Vegetacion, Precipitacion, Temperatura (2001-2024, mensual)

Sentinel-5P, VIIRS y GRACE quedan para el bloque 2.

REQUISITOS:
    pip install earthengine-api pandas numpy
    Cuenta de Google Earth Engine activada (https://earthengine.google.com/)
    Un proyecto de Google Cloud asociado a esa cuenta (obligatorio desde 2024)
    Ejecutar ee.Authenticate() una vez por maquina (abre navegador)

NO SE PUDO EJECUTAR NI PROBAR ESTE SCRIPT EN EL ENTORNO DONDE FUE ESCRITO
(sin acceso a red / sin credenciales GEE). Los IDs de dataset, rangos de
fechas y unidades fueron verificados contra el catalogo publico de Earth
Engine (agosto 2026), pero el script en si no fue corrido end-to-end.
Correlo en tu maquina y revisa la seccion de "red flags" al final del
mensaje que acompana este archivo antes de confiar en los resultados.
"""

import ee
import pandas as pd
import numpy as np
import time

# ---------------------------------------------------------------
# 0. INICIALIZACION
# ---------------------------------------------------------------
PROJECT_ID = "nora-506511"

try:
    ee.Initialize(project=PROJECT_ID)
except Exception:
    ee.Authenticate()
    ee.Initialize(project=PROJECT_ID)

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
    cell_id = 0
    for lon in lons:
        for lat in lats:
            rect = ee.Geometry.Rectangle(
                [float(lon), float(lat), float(lon + cell_size), float(lat + cell_size)]
            )
            feat = ee.Feature(rect, {
                "cell_id": cell_id,
                "centroid_lon": float(lon + cell_size / 2),
                "centroid_lat": float(lat + cell_size / 2),
            })
            features.append(feat)
            cell_id += 1
    return ee.FeatureCollection(features)


grid = build_grid(AOI_BOUNDS, CELL_SIZE_DEG)
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


def extract_monthly_variable(get_image_fn, value_col, scale, months, grid_fc):
    all_records = []
    for i, ts in enumerate(months):
        year, month = ts.year, ts.month
        img = get_image_fn(year, month)
        reduced = reduce_image_to_grid(img, grid_fc, scale)
        recs = fc_to_records(reduced, value_col)
        for r in recs:
            r["year"] = year
            r["month"] = month
        all_records.extend(recs)
        if (i + 1) % 24 == 0:
            print(f"  {value_col}: {i + 1}/{len(months)} meses procesados")
        time.sleep(0.2)  # margen frente a rate limits de la API de EE
    return pd.DataFrame(all_records)


print("Extrayendo NDVI (MOD13A3, escala 1000m)...")
df_ndvi = extract_monthly_variable(get_ndvi_monthly, "ndvi", 1000, months, grid)

print("Extrayendo precipitacion (CHIRPS, escala 5000m)...")
df_precip = extract_monthly_variable(get_chirps_monthly, "precip_mm", 5000, months, grid)

print("Extrayendo temperatura (ERA5-Land, escala 11132m)...")
df_temp = extract_monthly_variable(get_era5_monthly, "temp_c", 11132, months, grid)

print("Extrayendo SoilGrids (estatico, escala 250m)...")
soil_reduced = reduce_image_to_grid(soil_image, grid, 250)
soil_features = soil_reduced.getInfo()["features"]
soil_records = []
for f in soil_features:
    props = f["properties"]
    rec = {"cell_id": props.get("cell_id")}
    for prop in SOIL_PROPS:
        for depth in SOIL_DEPTHS:
            band = f"{prop}_{depth}_mean"
            rec[band] = props.get(band)
    soil_records.append(rec)
df_soil = pd.DataFrame(soil_records)

# ---------------------------------------------------------------
# 6. MERGE FINAL
# ---------------------------------------------------------------
merge_keys = ["cell_id", "centroid_lon", "centroid_lat", "year", "month"]
df = df_ndvi.merge(df_precip, on=merge_keys, how="outer")
df = df.merge(df_temp, on=merge_keys, how="outer")
df = df.merge(df_soil, on="cell_id", how="left")  # estatico: mismo valor todos los meses

df["date"] = pd.to_datetime(df[["year", "month"]].assign(day=1))
df = df.sort_values(["cell_id", "date"]).reset_index(drop=True)

# ---------------------------------------------------------------
# 7. EXPORT
# ---------------------------------------------------------------
OUTPUT_PATH = "alto_xingu_ingesta_2001_2024.csv"
df.to_csv(OUTPUT_PATH, index=False)
print(f"Guardado: {OUTPUT_PATH}")
print(f"Filas: {len(df)} | Celdas unicas: {df['cell_id'].nunique()} | "
      f"Meses esperados: {len(months)}")
print(f"Filas esperadas (celdas x meses): {n_cells * len(months)}")
