"""Catálogo de fuentes y resolución de disponibilidad para NORA."""
from __future__ import annotations
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class Fuente:
    nombre: str
    tipo: str
    variables: tuple[str, ...]
    cobertura: str
    autoridad: str
    requiere_credencial: bool = False

FUENTES = (
    Fuente("Sentinel-2", "satellite", ("cobertura_vegetal",), "global", "ESA/Copernicus"),
    Fuente("Landsat", "satellite", ("cobertura_vegetal",), "global", "USGS/NASA"),
    Fuente("GPM", "clima", ("precipitacion",), "global", "NASA"),
    Fuente("CHIRPS", "clima", ("precipitacion",), "global", "Climate Hazards Center"),
    Fuente("SMAP", "satellite", ("humedad_suelo",), "global", "NASA"),
    Fuente("ERA5-Land", "reanalisis", ("temperatura", "radiacion_solar", "viento"), "global", "ECMWF/Copernicus"),
    Fuente("SRTM", "elevacion", ("pendiente", "topografia"), "global", "NASA/USGS"),
    Fuente("Copernicus DEM", "elevacion", ("pendiente", "topografia"), "global", "Copernicus"),
    Fuente("ESA WorldCover", "cobertura", ("uso_suelo", "cobertura_vegetal"), "global", "ESA"),
    Fuente("HydroSHEDS", "hidrologia", ("hidrologia",), "global", "WWF/USGS/EC JRC"),
    Fuente("USGS", "sismologia", ("sismo",), "global", "USGS"),
    Fuente("EMSC", "sismologia", ("sismo",), "global", "EMSC"),
)

def resolver_fuentes(variables: list[str], cobertura: str = "global") -> list[dict]:
    resultado = []
    for variable in variables:
        for fuente in FUENTES:
            if variable in fuente.variables and (fuente.cobertura == cobertura or fuente.cobertura == "global"):
                resultado.append({"variable": variable, **asdict(fuente)})
    return resultado
