"""Control de calidad previo al análisis conjunto."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from math import isfinite

@dataclass(frozen=True)
class ResultadoCalidad:
    variable: str
    total: int
    validos: int
    nulos: int
    duplicados: int
    cobertura: float
    estado: str
    incidencias: tuple[str, ...]

def evaluar(registros: list[dict], variable: str, minimo_cobertura: float = 0.7) -> dict:
    vistos = set(); validos = 0; nulos = 0; duplicados = 0; incidencias = []
    for r in registros:
        clave = (r.get("fecha"), r.get("lat"), r.get("lon"))
        if clave in vistos: duplicados += 1
        vistos.add(clave)
        valor = r.get("valor")
        try: ok = valor is not None and isfinite(float(valor))
        except (TypeError, ValueError): ok = False
        if ok: validos += 1
        else: nulos += 1
    total = len(registros); cobertura = validos / total if total else 0.0
    if duplicados: incidencias.append("duplicados_detectados")
    if cobertura < minimo_cobertura: incidencias.append("cobertura_insuficiente")
    estado = "apto" if total and cobertura >= minimo_cobertura else "requiere_revision"
    return asdict(ResultadoCalidad(variable, total, validos, nulos, duplicados, round(cobertura, 4), estado, tuple(incidencias)))
