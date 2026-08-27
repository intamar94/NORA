"""Adaptador Earth Engine con trazabilidad y semántica por variable."""
from __future__ import annotations
import os
from dataclasses import dataclass

DATASETS={
    "precipitacion":{"id":"UCSB-CHC/CHIRPS/V3/DAILY_RNL","band":"precipitation","reducer":"sum","unidad":"mm"},
    "sentinel2":{"id":"COPERNICUS/S2_HARMONIZED","band":"B4","reducer":"mean","unidad":"reflectancia"},
    "evi":{"id":"LANDSAT/COMPOSITES/C02/T1_L2_8DAY_EVI","band":"EVI","reducer":"mean","unidad":"indice"},
}

@dataclass(frozen=True)
class EEConfig:
    project:str
    scale_m:int=1000

def inicializar(config:EEConfig):
    try: import ee
    except ImportError as exc: raise RuntimeError("Instala earthengine-api") from exc
    ee.Initialize(project=config.project); return ee

def _roi(ee,region):
    if "coordinates" in region: return ee.Geometry.Polygon(region["coordinates"])
    return ee.Geometry.Point([region["lon"],region["lat"]]).buffer(region.get("buffer_m",5000))

def extraer(config:EEConfig,region:dict,inicio:str,fin:str,variables:list[str])->dict:
    ee=inicializar(config); roi=_roi(ee,region); salida={}
    for variable in variables:
        meta=DATASETS.get(variable)
        if not meta: salida[variable]={"estado":"no_soportada"}; continue
        col=ee.ImageCollection(meta["id"]).filterDate(inicio,fin).filterBounds(roi)
        count=int(col.size().getInfo()); item={"estado":"ok","dataset":meta["id"],"banda":meta["band"],"unidad":meta["unidad"],"imagenes":count}
        if count:
            imagen=col.mean().clip(roi)
            reducer=ee.Reducer.sum() if meta["reducer"]=="sum" else ee.Reducer.mean()
            item["estadistica"]=imagen.select(meta["band"]).reduceRegion(reducer=reducer,geometry=roi,scale=config.scale_m,maxPixels=1e8).getInfo()
        salida[variable]=item
    return {"estado":"ok","region":region,"inicio":inicio,"fin":fin,"fuentes":salida,"provenance":{"origen":"Google Earth Engine","proyecto":config.project,"escala_m":config.scale_m}}

def config_desde_entorno()->EEConfig:
    project=os.environ.get("EE_PROJECT")
    if not project: raise RuntimeError("Falta EE_PROJECT")
    return EEConfig(project=project,scale_m=int(os.environ.get("EE_SCALE_M","1000")))
