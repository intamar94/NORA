"""Motor de cascadas de peligro para NORA.

Modela cadenas de eventos como hipótesis verificables: inestabilidad de hielo/permafrost -> avalancha -> bloqueo de río -> acumulación -> liberación -> inundación. No demuestra causalidad ni sustituye alertas oficiales.
"""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Senal:
    variable: str
    valor: float
    umbral: float
    direccion: str = "aumenta"
    fuente: str = ""

ETAPAS = ("inestabilidad_criosfera", "avalancha_hielo_roca", "bloqueo_cauce", "acumulacion_agua", "liberacion_surge", "inundacion_aguas_abajo")

def evaluar_senal(senal: Senal) -> float:
    if senal.umbral <= 0: return 0.0
    ratio = senal.valor / senal.umbral if senal.direccion == "aumenta" else senal.umbral / max(senal.valor, 1e-9)
    return max(0.0, min(1.0, ratio - 1.0))

def evaluar_cascada(senales: list[Senal], cobertura_datos: float = 1.0) -> dict:
    evidencias={s.variable:evaluar_senal(s) for s in senales}
    fuertes=[k for k,v in evidencias.items() if v >= .5]
    cobertura=max(0.0,min(1.0,float(cobertura_datos)))
    score=round(100*(.7*(len(fuertes)/max(len(senales),1))+.3*cobertura),2)
    nivel="critico" if score>=80 else "alto" if score>=60 else "vigilancia" if score>=35 else "bajo"
    faltantes=[s.variable for s in senales if s.variable not in fuertes]
    return {"modelo":"cascada_criosfera-hidrologia","etapas":list(ETAPAS),"puntuacion":score,"nivel":nivel,"senales_fuertes":fuertes,"variables_por_confirmar":faltantes,"accion":"verificar en tiempo casi real y contrastar con protocolo local" if nivel in ("alto","critico") else "continuar vigilancia","advertencia":"indicador de riesgo; no sustituye una alerta oficial ni demuestra causalidad"}

def generar_sensores_minimos() -> list[str]:
    return ["cambio_geometria_glaciar","temperatura_superficie","temperatura_permafrost","precipitacion","acumulacion_nieve_hielo","deformacion_terreno","nivel_caudal_rio","velocidad_cambio_nivel","bloqueo_cauce_detectado","cambio_superficie_agua"]
