"""
PRUEBA MINIMA - Ingesta Alto Xingu
Proyecto NORA (Earth System)

Objetivo de este script: NO es generar datos utiles todavia. Es confirmar
que la conexion a Earth Engine funciona, que los 4 datasets responden, y
que los supuestos sin verificar (sobre todo los nombres de banda de
SoilGrids) son correctos -- ANTES de lanzar la corrida completa de
24 anios x ~1.500 celdas del script "ingesta_alto_xingu.py".

Que hace distinto de la version completa:
- Un solo mes (enero 2020, elegido al azar dentro del rango, sin ninguna
  razon especial mas que tener un mes con datos completos).
- Un recorte MUY chico de la grilla: 5x5 celdas (25 celdas) en el centro
  del area de estudio, no las ~1.500 completas.
- Imprime cada resultado en pantalla para que los revises a ojo, en vez
  de guardar directo a CSV.

REQUISITOS (correr en la terminal de Codespaces):
    pip install earthengine-api pandas numpy
"""

import ee
import pandas as pd
import numpy as np

# ---------------------------------------------------------------
# 0. INICIALIZACION
# ---------------------------------------------------------------
PROJECT_ID = "nora-506511"

try:
    ee.Initialize(project=PROJECT_ID)
    print("Conexion a Earth Engine: OK")
except Exception:
    print("No habia sesion activa, iniciando autenticacion...")
    ee.Authenticate()
    ee.Initialize(project=PROJECT_ID)
    print("Conexion a Earth Engine: OK (tras autenticar)")

# ---------------------------------------------------------------
# 1. RECORTE CHICO DE PRUEBA (5x5 celdas, centro del area de estudio)
# ---------------------------------------------------------------
CELL_SIZE_DEG = 0.1
# Centro aproximado del bounding box completo (-55.2,-51.3 / -15.2,-10.5)
CENTER_LON = -53.25
CENTER_LAT = -12.85

lons = np.arange(CENTER_LON - 5 * CELL_SIZE_DEG / 2, CENTER_LON + 5 * CELL_SIZE_DEG / 2, CELL_SIZE_DEG)
lats = np.arange(CENTER_LAT - 5 * CELL_SIZE_DEG / 2, CENTER_LAT + 5 * CELL_SIZE_DEG / 2, CELL_SIZE_DEG)

features = []
cell_id = 0
for lon in lons:
    for lat in lats:
        rect = ee.Geometry.Rectangle([float(lon), float(lat), float(lon + CELL_SIZE_DEG), float(lat + CELL_SIZE_DEG)])
        feat = ee.Feature(rect, {"cell_id": cell_id})
        features.append(feat)
        cell_id += 1

grid = ee.FeatureCollection(features)
print(f"Grilla de prueba: {grid.size().getInfo()} celdas (deberia ser 25)")

# ---------------------------------------------------------------
# 2. MES DE PRUEBA
# ---------------------------------------------------------------
YEAR, MONTH = 2020, 1
start = ee.Date.fromYMD(YEAR, MONTH, 1)
end = start.advance(1, "month")

# ---------------------------------------------------------------
# 3. HELPER
# ---------------------------------------------------------------
def reduce_and_print(image, scale, label):
    reduced = image.reduceRegions(collection=grid, reducer=ee.Reducer.mean(), scale=scale)
    feats = reduced.getInfo()["features"]
    vals = [f["properties"].get("mean") for f in feats if f["properties"].get("mean") is not None]
    print(f"\n{label}:")
    print(f"  Celdas con dato: {len(vals)}/{len(feats)}")
    if vals:
        print(f"  Min: {min(vals):.4f} | Max: {max(vals):.4f} | Promedio: {np.mean(vals):.4f}")
    else:
        print("  ATENCION: ninguna celda devolvio dato -- revisar dataset/fechas/escala")
    return feats

# ---------------------------------------------------------------
# 4. NDVI
# ---------------------------------------------------------------
ndvi_img = (ee.ImageCollection("MODIS/061/MOD13A3")
            .filterDate(start, end)
            .select("NDVI")
            .mean()
            .multiply(0.0001)
            .rename("ndvi"))
reduce_and_print(ndvi_img, 1000, "NDVI (esperado: entre -1 y 1, tipico 0.3-0.9 en esta zona)")

# ---------------------------------------------------------------
# 5. CHIRPS
# ---------------------------------------------------------------
chirps_img = (ee.ImageCollection("UCSB-CHG/CHIRPS/PENTAD")
              .filterDate(start, end)
              .select("precipitation")
              .sum()
              .rename("precip_mm"))
reduce_and_print(chirps_img, 5000, "Precipitacion CHIRPS (mm del mes, enero=lluviosa, deberia ser alta)")

# ---------------------------------------------------------------
# 6. ERA5-Land
# ---------------------------------------------------------------
era5_img = (ee.ImageCollection("ECMWF/ERA5_LAND/MONTHLY_AGGR")
            .filterDate(start, end)
            .select("temperature_2m")
            .mean()
            .subtract(273.15)
            .rename("temp_c"))
reduce_and_print(era5_img, 11132, "Temperatura ERA5-Land (esperado 20-30 C aprox)")

# ---------------------------------------------------------------
# 7. SoilGrids -- ESTE ES EL QUE TIENE EL SUPUESTO SIN VERIFICAR
# ---------------------------------------------------------------
print("\n--- SoilGrids: verificando nombres de banda reales ---")
try:
    test_img = ee.Image("projects/soilgrids-isric/clay_mean")
    band_names = test_img.bandNames().getInfo()
    print(f"Bandas reales encontradas en clay_mean: {band_names}")
except Exception as e:
    print(f"ERROR al acceder a SoilGrids: {e}")
    band_names = []

# Si el print de arriba muestra nombres distintos a "clay_0-5cm_mean" etc,
# hay que ajustar SOIL_PROPS/SOIL_DEPTHS en el script completo antes de
# correrlo -- no asumir que va a andar igual.