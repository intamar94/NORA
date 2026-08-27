"""Planificador adaptativo de análisis territorial."""
from __future__ import annotations
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class Variable:
    nombre: str
    motivo: str
    prioridad: int
    fuentes_preferidas: tuple[str, ...]
    requiere_medicion_directa: bool = False

CATALOGO = {
    "agua": (
        Variable("precipitacion", "balance hídrico y eventos extremos", 1, ("GPM", "CHIRPS")),
        Variable("humedad_suelo", "disponibilidad de agua", 1, ("SMAP",)),
        Variable("cobertura_vegetal", "protección y estado de cuenca", 1, ("Sentinel-2", "Landsat")),
        Variable("pendiente", "erosión y escorrentía", 2, ("SRTM", "Copernicus DEM")),
        Variable("calidad_agua", "validar contaminación real", 1, ("medicion_in_situ",), True),
    ),
    "riesgo_natural": (
        Variable("sismo", "forzamiento geológico reciente", 1, ("USGS", "EMSC")),
        Variable("precipitacion", "saturación y desencadenamiento", 1, ("GPM", "CHIRPS")),
        Variable("pendiente", "susceptibilidad topográfica", 1, ("SRTM", "Copernicus DEM")),
        Variable("cobertura_vegetal", "estabilidad del terreno", 2, ("Sentinel-2", "Landsat")),
        Variable("temperatura", "condiciones de nieve/hielo", 2, ("ERA5-Land",)),
    ),
    "restauracion": (
        Variable("cobertura_vegetal", "línea base y recuperación", 1, ("Sentinel-2", "Landsat")),
        Variable("humedad_suelo", "condición edáfica", 1, ("SMAP",)),
        Variable("precipitacion", "régimen hídrico", 2, ("GPM", "CHIRPS")),
        Variable("temperatura", "estrés climático", 2, ("ERA5-Land",)),
        Variable("pendiente", "erosión potencial", 1, ("SRTM", "Copernicus DEM")),
        Variable("uso_suelo", "presiones y compatibilidad", 1, ("ESA WorldCover",)),
    ),
    "energia": (
        Variable("radiacion_solar", "recurso solar", 1, ("ERA5-Land",)),
        Variable("viento", "recurso eólico", 1, ("ERA5-Land",)),
        Variable("topografia", "emplazamiento", 2, ("SRTM", "Copernicus DEM")),
        Variable("cobertura_vegetal", "restricción ambiental", 1, ("Sentinel-2", "ESA WorldCover")),
        Variable("hidrologia", "potencial hidroenergético", 2, ("HydroSHEDS",)),
    ),
}

def construir_plan(caso: str, zona: dict) -> dict:
    variables = CATALOGO.get(caso, ())
    return {"caso": caso, "zona": zona, "variables": [asdict(v) for v in sorted(variables, key=lambda x: x.prioridad)], "regla": "resolver_fuentes_antes_de_analizar"}
