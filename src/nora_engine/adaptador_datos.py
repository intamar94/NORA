"""Adaptador común para adquisidores reales de NORA."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from .normalizacion import normalizar_registro

@dataclass(frozen=True)
class ResultadoAdquisicion:
    tarea_id: str
    variable: str
    fuente: str
    estado: str
    registros: int
    inicio: str
    fin: str
    error: str | None = None

class AdaptadorAdquisicion:
    nombre = "generico"
    def adquirir(self, tarea: dict) -> list[dict]:
        raise NotImplementedError
    def ejecutar(self, tarea: dict):
        inicio=datetime.now(timezone.utc).isoformat()
        try:
            raw=self.adquirir(tarea)
            registros=[normalizar_registro(r,tarea["variable"],tarea["fuente"]) for r in raw]
            return asdict(ResultadoAdquisicion(tarea.get("id",tarea.get("variable","sin-id")),tarea["variable"],tarea["fuente"],"completado",len(registros),inicio,datetime.now(timezone.utc).isoformat())),registros
        except Exception as exc:
            return asdict(ResultadoAdquisicion(tarea.get("id",tarea.get("variable","sin-id")),tarea.get("variable",""),tarea.get("fuente",self.nombre),"error",0,inicio,datetime.now(timezone.utc).isoformat(),str(exc))),[]

class AdaptadorFuncion(AdaptadorAdquisicion):
    """Puente para conectar funciones de adquisición existentes."""
    def __init__(self, funcion, nombre="existente"):
        self.funcion=funcion; self.nombre=nombre
    def adquirir(self,tarea):
        return self.funcion(tarea)
