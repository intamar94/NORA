"""Puente geoespacial del pipeline NORA."""
from __future__ import annotations
from .geofisica import Celda, derivar_indicadores
from .propagacion_espacial import Nodo, Enlace, propagar

def evaluar_exposicion(celdas: list[Celda], nodos: list[Nodo], enlaces: list[Enlace], origen: str, horizonte_h: float | None = None) -> dict:
    """Combina indicadores del terreno y propagación sobre una red espacial."""
    terreno=derivar_indicadores(celdas)
    exposicion=propagar(nodos,enlaces,origen,horizonte_h)
    return {"estado":"ok" if terreno.get("estado")=="calculado" and exposicion.get("estado")=="estimado" else "incompleto","terreno":terreno,"exposicion":exposicion}
