"""Contrato común para series y capas territoriales de NORA."""
from __future__ import annotations
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class RegistroDato:
    variable: str
    fuente: str
    fecha: str
    valor: float | None
    unidad: str
    lat: float | None = None
    lon: float | None = None
    calidad: float | None = None
    estado: str = "valido"

def normalizar_registro(raw: dict, variable: str, fuente: str) -> dict:
    valor = raw.get("valor")
    try:
        valor = None if valor is None else float(valor)
    except (TypeError, ValueError):
        valor = None
    estado = "valido" if valor is not None else "sin_valor"
    return asdict(RegistroDato(variable=variable, fuente=fuente, fecha=str(raw.get("fecha", "")), valor=valor, unidad=str(raw.get("unidad", "")), lat=raw.get("lat"), lon=raw.get("lon"), calidad=raw.get("calidad"), estado=estado))
