"""Generador explicable de hipótesis a partir de hallazgos NORA."""
from __future__ import annotations
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class Hipotesis:
    id: str
    observacion: str
    hipotesis: str
    variables: tuple[str, ...]
    prediccion: str
    controles: tuple[str, ...]
    pruebas: tuple[str, ...]
    nivel: str

def generar(hallazgo: dict) -> dict:
    a,b=hallazgo["variable_a"],hallazgo["variable_b"]
    medida=float(hallazgo["medida"])
    direccion="positiva" if medida>0 else "negativa"
    nivel="candidata" if abs(medida)>=.5 and hallazgo.get("muestras",0)>=10 else "exploratoria"
    return asdict(Hipotesis(
        id=f"H-{a}-{b}-{hallazgo.get('metodo','analisis')}",
        observacion=f"Se observa una asociación {direccion} entre {a} y {b}.",
        hipotesis=f"Los cambios de {a} podrían estar relacionados con cambios posteriores en {b}.",
        variables=(a,b),
        prediccion=f"Si la relación se mantiene, variaciones de {a} deberían preceder cambios consistentes en {b}.",
        controles=("estacionalidad","tendencia temporal","variables ambientales relevantes","autocorrelación"),
        pruebas=("replicar en otro período","replicar en otra zona","evaluar desfases","comparar con variables de control"),
        nivel=nivel))
