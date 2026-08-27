"""Adaptador Earth Engine para datos ambientales reales de NORA.

La autenticación y el proyecto se suministran fuera del código (EE_PROJECT).
El adaptador devuelve metadatos y estadísticas regionales normalizadas.
"""
from __future__ import annotations
import os
from dataclasses import dataclass

DATASETS={
    "precipitacion":"UCSB-CHC/CHIRPS/V3/DAILY_RNL",
    "sentinel2":"COPERNICUS/S2_HARMONIZED",
    "evi":"LANDSAT/COMPOSITES/C02/T1_L2_8DAY_EVI",
}

@dataclass(frozen=True)
class EEConfig:
    project: str
    scale_m: int = 1000

def inicializar(config: EEConfig):
    try:
        import ee
    except ImportError as exc:
        raise RuntimeError("Instala earthengine-api para usar Earth Engine") from exc
    ee.Initialize(project=config.project)
    return ee

def _roi(ee, region: dict):
    if "coordinates" in region:
        return ee.Geometry.Polygon(region["coordinates"])
    return ee.Geometry.Point([region["lon"], region["lat"]]).buffer(region.get("buffer_m",5000))

def extraer(config: EEConfig, region: dict, inicio: str, fin: str, variables: list[str]) -> dict:
    ee=inicializar(config); roi=_roi(ee,region); salida={}
    for variable in variables:
        if variable not in DATASETS: salida[variable]={"estado":"no_soportada"}; continue
        col=ee.ImageCollection(DATASETS[variable]).filterDate(inicio,fin).filterBounds(roi)
        count=col.size().getInfo()
        salida[variable]={"estado":"ok","dataset":DATASETS[variable],"imagenes":count}
        if count:
            imagen=col.mean().clip(roi)
            band={"precipitacion":"precipitation","evi":"EVI","sentinel2":"B4"}[variable]
            stat=imagen.select(band).reduceRegion(reducer=ee.Reducer.mean(),geometry=roi,scale=config.scale_m,maxPixels=1e8).getInfo()
            salida[variable]["media_regional"]=stat
    return {"estado":"ok","region":region,"inicio":inicio,"fin":fin,"variables":salida}

def config_desde_entorno() -> EEConfig:
    project=os.environ.get("EE_PROJECT")
    if not project: raise RuntimeError("Falta EE_PROJECT")
    return EEConfig(project=project,scale_m=int(os.environ.get("EE_SCALE_M","1000")))
