"""Data Fabric de NORA: inventario, cobertura, calidad y necesidades de datos.

La capa no adquiere datos. Describe qué datos están disponibles, qué fuente los
proporciona, qué cobertura/resolución tienen y qué falta para ejecutar un plan.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class Dataset:
    nombre: str
    fuente: str
    variables: tuple[str, ...]
    cobertura: str = "global"
    resolucion_temporal: str = ""
    resolucion_espacial: str = ""
    inicio: str | None = None
    fin: str | None = None
    acceso: str = "publico"
    calidad_base: float = 1.0
    requiere_credencial: bool = False
    estado: str = "catalogado"

    def cubre_periodo(self, inicio: str | None, fin: str | None) -> bool:
        if inicio and self.inicio and inicio < self.inicio:
            return False
        if fin and self.fin and fin > self.fin:
            return False
        return True


DATASETS: tuple[Dataset, ...] = (
    Dataset("sentinel_2", "Sentinel-2", ("cobertura_vegetal",), resolucion_temporal="5-10 dias", resolucion_espacial="10-60 m"),
    Dataset("landsat", "Landsat", ("cobertura_vegetal",), resolucion_temporal="16 dias", resolucion_espacial="30 m"),
    Dataset("gpm", "GPM", ("precipitacion",), resolucion_temporal="diaria/subdiaria", resolucion_espacial="~10 km"),
    Dataset("chirps", "CHIRPS", ("precipitacion",), resolucion_temporal="diaria", resolucion_espacial="~5 km"),
    Dataset("smap", "SMAP", ("humedad_suelo",), resolucion_temporal="diaria", resolucion_espacial="~9-36 km"),
    Dataset("era5_land", "ERA5-Land", ("temperatura", "radiacion_solar", "viento"), resolucion_temporal="horaria", resolucion_espacial="~9 km"),
    Dataset("srtm", "SRTM", ("pendiente", "topografia"), resolucion_espacial="30 m"),
    Dataset("copernicus_dem", "Copernicus DEM", ("pendiente", "topografia"), resolucion_espacial="30 m"),
    Dataset("worldcover", "ESA WorldCover", ("uso_suelo", "cobertura_vegetal"), resolucion_temporal="anual", resolucion_espacial="10 m"),
    Dataset("hydrosheds", "HydroSHEDS", ("hidrologia",), resolucion_espacial="30 arcsec"),
)


@dataclass(frozen=True)
class Necesidad:
    variable: str
    inicio: str | None = None
    fin: str | None = None
    cobertura: str = "global"
    resolucion_maxima: str | None = None
    prioridad: int = 1


@dataclass
class ResultadoFabric:
    disponibles: list[dict] = field(default_factory=list)
    faltantes: list[dict] = field(default_factory=list)


def catalogo() -> list[dict]:
    """Devuelve el inventario serializable de datasets conocidos."""
    return [asdict(dataset) for dataset in DATASETS]


def resolver_necesidades(necesidades: Iterable[Necesidad]) -> ResultadoFabric:
    """Relaciona necesidades con datasets y explicita los huecos."""
    resultado = ResultadoFabric()
    for necesidad in necesidades:
        candidatos = [
            d for d in DATASETS
            if necesidad.variable in d.variables
            and (d.cobertura == necesidad.cobertura or d.cobertura == "global")
            and d.cubre_periodo(necesidad.inicio, necesidad.fin)
        ]
        if candidatos:
            for dataset in candidatos:
                resultado.disponibles.append({
                    "variable": necesidad.variable,
                    "dataset": dataset.nombre,
                    "fuente": dataset.fuente,
                    "calidad_base": dataset.calidad_base,
                    "resolucion_temporal": dataset.resolucion_temporal,
                    "resolucion_espacial": dataset.resolucion_espacial,
                })
        else:
            resultado.faltantes.append(asdict(necesidad))
    return resultado


def estado_datos(necesidades: Iterable[Necesidad]) -> dict:
    """Resumen operativo para la interfaz/orquestador."""
    resultado = resolver_necesidades(necesidades)
    total = len(resultado.disponibles) + len(resultado.faltantes)
    cobertura = 1.0 if total == 0 else len(resultado.disponibles) / total
    return {
        "variables_resueltas": len(resultado.disponibles),
        "necesidades_faltantes": len(resultado.faltantes),
        "cobertura": round(cobertura, 3),
        "estado": "completo" if not resultado.faltantes else "parcial",
        "disponibles": resultado.disponibles,
        "faltantes": resultado.faltantes,
    }
