"""Adaptador Earth Engine con semántica científica y trazabilidad."""
from __future__ import annotations

import os
from dataclasses import dataclass

DATASETS = {
    "precipitacion": {
        "id": "UCSB-CHC/CHIRPS/V3/DAILY_RNL",
        "band": "precipitation",
        "unidad": "mm",
        "operacion_temporal": "sum",
        "escala_m": 5566,
    },
    "sentinel2": {
        "id": "COPERNICUS/S2_SR_HARMONIZED",
        "band": "B4",
        "unidad": "reflectancia",
        "operacion_temporal": "mean",
        "escala_m": 10,
    },
    "evi": {
        "id": "LANDSAT/COMPOSITES/C02/T1_L2_8DAY_EVI",
        "band": "EVI",
        "unidad": "indice",
        "operacion_temporal": "mean",
        "escala_m": 30,
    },
}


@dataclass(frozen=True)
class EEConfig:
    project: str
    scale_m: int | None = None


def inicializar(config: EEConfig):
    try:
        import ee
    except ImportError as exc:
        raise RuntimeError("Instala earthengine-api") from exc
    ee.Initialize(project=config.project)
    return ee


def _roi(ee, region: dict):
    if "coordinates" in region:
        return ee.Geometry.Polygon(region["coordinates"])
    return ee.Geometry.Point([region["lon"], region["lat"]]).buffer(
        region.get("buffer_m", 5000)
    )


def _mask_sentinel2(ee, image):
    """Elimina sombra de nube, nubes, cirrus y nieve/hielo mediante SCL."""
    scl = image.select("SCL")
    valid = (
        scl.neq(3)   # cloud shadow
        .And(scl.neq(8))   # medium probability cloud
        .And(scl.neq(9))   # high probability cloud
        .And(scl.neq(10))  # cirrus
        .And(scl.neq(11))  # snow/ice
    )
    return image.updateMask(valid)


def _prepare_collection(ee, variable: str, meta: dict, inicio: str, fin: str, roi):
    col = (
        ee.ImageCollection(meta["id"])
        .filterDate(inicio, fin)
        .filterBounds(roi)
    )
    if variable == "sentinel2":
        col = col.map(lambda image: _mask_sentinel2(ee, image))
    return col


def _aggregate(ee, variable: str, meta: dict, col, roi):
    band = meta["band"]
    if variable == "precipitacion":
        # CHIRPS es diario (mm/d). Primero acumulamos en el tiempo y
        # después calculamos la media espacial: mm acumulados en la región.
        image = col.select(band).sum()
    else:
        image = col.select(band).mean()
        if variable == "sentinel2":
            # Sentinel-2 almacena reflectancia con escala 0.0001.
            image = image.multiply(0.0001)
    scale = config_scale = meta["escala_m"]
    return image.clip(roi).reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=roi,
        scale=scale,
        maxPixels=1e8,
    ).getInfo(), scale


def extraer(
    config: EEConfig,
    region: dict,
    inicio: str,
    fin: str,
    variables: list[str],
) -> dict:
    ee = inicializar(config)
    roi = _roi(ee, region)
    salida = {}

    for variable in variables:
        meta = DATASETS.get(variable)
        if not meta:
            salida[variable] = {"estado": "no_soportada"}
            continue

        col = _prepare_collection(ee, variable, meta, inicio, fin, roi)
        count = int(col.size().getInfo())
        item = {
            "estado": "ok" if count else "sin_datos",
            "dataset": meta["id"],
            "banda": meta["band"],
            "unidad": meta["unidad"],
            "imagenes": count,
            "operacion_temporal": meta["operacion_temporal"],
            "estadistica_espacial": "mean",
            "escala_m": config.scale_m or meta["escala_m"],
        }

        if count:
            estadistica, escala = _aggregate(ee, variable, meta, col, roi)
            item["estadistica"] = estadistica
            item["escala_m"] = config.scale_m or escala

        salida[variable] = item

    return {
        "estado": "ok",
        "region": region,
        "inicio": inicio,
        "fin": fin,
        "fuentes": salida,
        "provenance": {
            "origen": "Google Earth Engine",
            "proyecto": config.project,
            "escala_m": config.scale_m,
            "metodo": "agregacion temporal seguida de estadistica espacial",
        },
    }


def config_desde_entorno() -> EEConfig:
    project = os.environ.get("EE_PROJECT")
    if not project:
        raise RuntimeError("Falta EE_PROJECT")
    scale_raw = os.environ.get("EE_SCALE_M")
    scale = int(scale_raw) if scale_raw else None
    return EEConfig(project=project, scale_m=scale)
