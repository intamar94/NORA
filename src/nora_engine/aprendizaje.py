"""Ciclo de aprendizaje NORA: esperado frente a observado."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from math import isfinite

@dataclass(frozen=True)
class ResultadoPrueba:
    hipotesis_id: str
    escenario_id: str
    variable: str
    esperado: float | None
    observado: float | None
    error_abs: float | None
    error_relativo: float | None
    resultado: str
    confianza_actualizada: float
    evidencia: str
    siguiente_accion: str

def registrar(hipotesis_id, escenario_id, variable, esperado, observado, confianza_previa=0.5, tolerancia=0.2):
    if esperado is None or observado is None:
        return asdict(ResultadoPrueba(hipotesis_id, escenario_id, variable, esperado, observado, None, None, "sin_validacion", float(confianza_previa), "Datos insuficientes.", "Obtener una medición válida."))
    esperado, observado = float(esperado), float(observado)
    if not all(isfinite(x) for x in (esperado, observado)):
        return asdict(ResultadoPrueba(hipotesis_id, escenario_id, variable, esperado, observado, None, None, "sin_validacion", float(confianza_previa), "Valores no finitos.", "Revisar los datos."))
    error_abs=abs(observado-esperado); error_rel=error_abs/max(abs(esperado),1e-9)
    previa=max(0,min(1,float(confianza_previa))); coincide=error_rel<=tolerancia
    actualizada=previa+(1-previa)*.2 if coincide else previa*.7
    return asdict(ResultadoPrueba(hipotesis_id, escenario_id, variable, esperado, observado, round(error_abs,6), round(error_rel,6), "consistente" if coincide else "no_consistente", round(actualizada,4), "Compatible con la predicción." if coincide else "No coincide suficientemente con la predicción.", "Replicar y ampliar la muestra." if coincide else "Revisar supuestos, confusores y recalibrar."))

def actualizar_hipotesis(historial, nueva_confianza):
    vals=[float(x["confianza_actualizada"]) for x in historial if x.get("resultado") in ("consistente","no_consistente")]
    return round(sum(vals)/len(vals),4) if vals else float(nueva_confianza)
