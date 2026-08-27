"""Decisión de vigilancia para señales convergentes de NORA."""
from __future__ import annotations
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class Alerta:
    nivel: str
    puntuacion: float
    fuentes_independientes: int
    tendencia: str
    confianza: float
    accion: str
    limitaciones: tuple[str, ...]

def evaluar_alerta(senales: list[dict], tendencia: float = 0.0, cobertura: float = 1.0) -> dict:
    activas=[s for s in senales if float(s.get("evidencia",0)) >= 0.5]
    fuentes={s.get("fuente") for s in activas if s.get("fuente")}
    independientes=len(fuentes)
    base=min(1.0,len(activas)/max(4,len(senales)))
    convergencia=min(1.0,independientes/3)
    tr=max(-1.0,min(1.0,float(tendencia)))
    cov=max(0.0,min(1.0,float(cobertura)))
    score=round(100*(.45*base+.35*convergencia+.10*max(tr,0)+.10*cov),2)
    if score>=80 and independientes>=3: nivel="critica"
    elif score>=60 and independientes>=2: nivel="alta"
    elif score>=35: nivel="vigilancia"
    else: nivel="baja"
    confianza=round(min(1.0,.6*convergencia+.4*cov),3)
    accion=("verificar inmediatamente y contrastar con sistemas oficiales/locales" if nivel in ("critica","alta") else "mantener vigilancia y buscar señales adicionales")
    return asdict(Alerta(nivel,score,independientes,"ascendente" if tr>0.2 else "estable" if tr>=-0.2 else "descendente",confianza,accion,("las señales no prueban causalidad","la alerta es orientativa","requiere validación local y fuentes oficiales")))
