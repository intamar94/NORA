"""
PRUEBA MINIMA - Ingesta Alto Xingu
Proyecto NORA (Earth System)

Confirma conexion a Earth Engine, respuesta de los 4 datasets y nombres de
bandas de SoilGrids antes de ejecutar la ingesta completa.
"""

import os
import json
import ee
import pandas as pd
import numpy as np
from google.oauth2 import service_account

PROJECT_ID = "nora-506511"
SERVICE_ACCOUNT_KEY = os.environ.get("GEE_SERVICE_ACCOUNT_KEY")

# En GitHub Actions usamos la cuenta de servicio guardada en el secret.
# Solo usamos autenticacion interactiva como fallback para ejecucion local.
if SERVICE_ACCOUNT_KEY:
    print("Credenciales GEE: secret GEE_SERVICE_ACCOUNT_KEY detectado")
    key_info = json.loads(SERVICE_ACCOUNT_KEY)
    credentials = service_account.Credentials.from_service_account_info(
        key_info,
        scopes=["https://www.googleapis.com/auth/earthengine"],
    )
    ee.Initialize(credentials=credentials, project=PROJECT_ID)
    print("Conexion a Earth Engine: OK (cuenta de servicio)")
else:
    print("GEE_SERVICE_ACCOUNT_KEY no encontrado; intentando autenticacion local...")
    try:
        ee.Initialize(project=PROJECT_ID)
        print("Conexion a Earth Engine: OK")
    except Exception:
        print("No habia sesion activa, iniciando autenticacion interactiva...")
        ee.Authenticate()
        ee.Initialize(project=PROJECT_ID)
        print("Conexion a Earth Engine: OK (tras autenticar)")

# ---------------------------------------------------------------
# 1. RECORTE CHICO DE PRUEBA (5x5 celdas)
# ---------------------------------------------------------------
CELL_SIZE_DEG = 0.1
CENTER_LON = -53.25
CENTER_LAT = -12.85

lons = np.arange(CENTER_LON - 5 * CELL_SIZE_DEG / 2, CENTER_LON + 5 * CELL_SIZE_DEG / 2, CELL_SIZE_DEG)
lats = np.arange(CENTER_LAT - 5 * CELL_SIZE_DEG / 2, CENTER_LAT + 5 * CELL_SIZE_DEG / 2, CELL_SIZE_DEG)

features = []
cell_id = 0
for lon in lons:
    for lat in lats:
        rect = ee.Geometry.Rectangle([float(lon), float(lat), float(lon + CELL_SIZE_DEG), float(lat + CELL_SIZE_DEG)])
        features.append(ee.Feature(rect, {"cell_id": cell_id}))
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
reduce_and_print(chirps_img, 5000, "Precipitacion CHIRPS (mm del mes)")

# ---------------------------------------------------------------
# 6. ERA5-Land
# ---------------------------------------------------------------
era5_img = (ee.ImageCollection("ECMWF/ERA5_LAND/MONTHLY_AGGR")
            .filterDate(start, end)
            .select("temperature_2m")
            .mean()
            .subtract(273.15)
            .rename("temp_c"))
reduce_and_print(era5_img, 11132, "Temperatura ERA5-Land (C)")

# ---------------------------------------------------------------
# 7. SoilGrids -- verificar nombres de banda reales
# ---------------------------------------------------------------
print("\n--- SoilGrids: verificando nombres de banda reales ---")
try:
    test_img = ee.Image("projects/soilgrids-isric/clay_mean")
    band_names = test_img.bandNames().getInfo()
    print(f"Bandas reales encontradas en clay_mean: {band_names}")
except Exception as e:
    print(f"ERROR al acceder a SoilGrids: {e}")
    band_names = []
