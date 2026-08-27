"""Decisión de alerta por convergencia de señales independientes."""
from __future__ import annotations
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class Alerta:
    nivel: str
    puntuacion: float
    senales_activas: int
    fuentes_independientes: int
    tendencia: str
    confianza: float
    accion: str
    limitaciones: tuple[str, ...]

def evaluar_alerta(senales: list[dict], tendencia: float = 0.0, cobertura: float = 1.0) -> dict:
    """Evalúa convergencia; nunca declara por sí sola un evento como cierto."""
    cobertura=max(0.0,min(1.0,float(cobertura)))
    activas=[s for s in senales if float(s.get("evidencia",0.0)) >= 0.5]
    fuentes={s.get("fuente","desconocida") for s in activas}
    independencia=min(1.0,len(fuentes)/3)
    densidad=min(1.0,len(activas)/max(4,len(senales)))
    t=max(-1.0,min(1.0,float(tendencia)))
    score=round(100*(0.45*densidad+0.35*independencia+0.10*max(t,0)+0.10*cobertura),2)
    if score>=80 and len(fuentes)>=3: nivel="critica"
    elif score>=60 and len(fuentes)>=2: nivel="alta"
    elif score>=35: nivel="vigilancia"
    else: nivel="baja"
    confianza=round(min(1.0,0.6*independencia+0.4*cobertura),3)
    accion=("verificar inmediatamente y contrastar con sistemas oficiales/locales" if nivel in ("critica","alta") else "mantener vigilancia y buscar señales adicionales")
    return asdict(Alerta(nivel,score,len(activas),len(fuentes),"ascendente" if t>0.2 else "estable" if t>=-0.2 else "descendente",confianza,accion,("no demuestra causalidad","requiere validación local","no sustituye una alerta oficial")))
