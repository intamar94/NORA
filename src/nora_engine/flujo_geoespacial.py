"""Integración geoespacial para el pipeline NORA."""
from __future__ import annotations
from .geofisica import Celda, derivar_indicadores
from .propagacion_espacial import Nodo, Enlace, propagar

def evaluar_geografia(celdas:list[Celda], nodos:list[Nodo], enlaces:list[Enlace], origen:str, horizonte_h:float|None=None)->dict:
    terreno=derivar_indicadores(celdas)
    exposicion=propagar(nodos,enlaces,origen,horizonte_h)
    ok=terreno.get("estado")=="calculado" and exposicion.get("estado")=="estimado"
    return {"estado":"ok" if ok else "incompleto","terreno":terreno,"exposicion":exposicion}
