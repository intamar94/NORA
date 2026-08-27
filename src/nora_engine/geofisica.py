"""Indicadores geofísicos para la propagación espacial de NORA."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Celda:
    id: str
    elevacion_m: float
    pendiente_pct: float
    direccion_flujo: str | None = None
    acumulacion: float = 0.0

def derivar_indicadores(celdas: list[Celda]) -> dict:
    """Resume un DEM ya procesado; no sustituye un modelo hidrológico."""
    if not celdas:
        return {"estado":"sin_datos","celdas":0,"limitaciones":["se necesita DEM"]}
    bajas=sorted(celdas,key=lambda c:c.elevacion_m)[:max(1,len(celdas)//10)]
    flujo=sorted(celdas,key=lambda c:c.acumulacion,reverse=True)[:max(1,len(celdas)//10)]
    return {"estado":"calculado","celdas":len(celdas),"elevacion_min_m":min(c.elevacion_m for c in celdas),"elevacion_max_m":max(c.elevacion_m for c in celdas),"pendiente_media_pct":sum(c.pendiente_pct for c in celdas)/len(celdas),"acumulacion_max":max(c.acumulacion for c in celdas),"zonas_bajas":[c.id for c in bajas],"corredores_alta_acumulacion":[c.id for c in flujo],"limitaciones":["requiere DEM y dirección de flujo válidos","requiere modelo hidrológico/hidráulico calibrado para decisiones operativas"]}
