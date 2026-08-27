"""Evaluación reproducible y ranking de escenarios NORA."""
from __future__ import annotations
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class Evaluacion:
    escenario_id: str
    puntuacion: float
    evidencia: float
    impacto: float
    factibilidad: float
    incertidumbre: float
    prioridad: str
    motivos: tuple[str, ...]
    siguiente_prueba: str

def _clip(x): return max(0.0, min(1.0, float(x)))

def evaluar(escenario, evidencia=0.0, impacto=0.5, factibilidad=0.5, incertidumbre=0.5):
    e,i,f,u=map(_clip,(evidencia,impacto,factibilidad,incertidumbre))
    puntuacion=round(100*(.35*e+.30*i+.20*f+.15*(1-u)),2)
    motivos=[]
    if e<.5: motivos.append("evidencia_limitada")
    if i>=.7: motivos.append("impacto_potencial_alto")
    if f>=.7: motivos.append("factibilidad_alta")
    if u>=.6: motivos.append("incertidumbre_alta")
    prioridad="alta" if puntuacion>=70 else "media" if puntuacion>=45 else "baja"
    return asdict(Evaluacion(escenario.get("id","sin-id"),puntuacion,e,i,f,u,prioridad,tuple(motivos),"Validar variables críticas y repetir con datos independientes."))

def ranking(escenarios):
    return sorted(escenarios,key=lambda x:float(x.get("puntuacion",0)),reverse=True)
