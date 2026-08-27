"""Alineación temporal y espacial determinista de registros NORA."""
from __future__ import annotations
from collections import defaultdict
from datetime import date
from math import floor

def _dia(fecha: str) -> str:
    return date.fromisoformat(fecha[:10]).isoformat()

def alinear_temporal(registros: list[dict], frecuencia: str = "diaria") -> list[dict]:
    grupos = defaultdict(list)
    for r in registros:
        if not r.get("fecha"): continue
        clave = _dia(r["fecha"]) if frecuencia == "diaria" else r["fecha"][:7]
        grupos[clave].append(r)
    salida = []
    for periodo, filas in sorted(grupos.items()):
        valores = [float(r["valor"]) for r in filas if r.get("valor") is not None]
        if valores: salida.append({"periodo": periodo, "valor": sum(valores)/len(valores), "n": len(valores)})
    return salida

def _celda(lat: float, lon: float, resolucion: float) -> tuple[int, int]:
    return floor(lat / resolucion), floor(lon / resolucion)

def alinear_espacial(registros: list[dict], resolucion: float = 0.1) -> list[dict]:
    grupos = defaultdict(list)
    for r in registros:
        if r.get("lat") is None or r.get("lon") is None or r.get("valor") is None: continue
        grupos[_celda(float(r["lat"]), float(r["lon"]), resolucion)].append(r)
    salida = []
    for celda, filas in grupos.items():
        valores = [float(r["valor"]) for r in filas]
        salida.append({"celda": celda, "valor": sum(valores)/len(valores), "n": len(valores), "resolucion": resolucion})
    return salida
