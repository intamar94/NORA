"""Motor de escenarios relativos y comparables para NORA."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from math import isfinite

@dataclass(frozen=True)
class Escenario:
    id: str
    nombre: str
    cambios: dict
    supuestos: tuple[str, ...]
    resultado: dict
    incertidumbre: str
    validacion: tuple[str, ...]

def simular(linea_base: dict, cambios: dict, nombre: str = "alternativa") -> dict:
    resultado = {}
    for variable, valor in linea_base.items():
        if isinstance(valor, (int, float)) and isfinite(float(valor)):
            resultado[variable] = float(valor) * (1.0 + float(cambios.get(variable, 0.0)))
        else:
            resultado[variable] = None
    return asdict(Escenario(
        id=f"ESC-{nombre.lower().replace(' ', '-')}", nombre=nombre, cambios=cambios,
        supuestos=("los cambios son relativos", "no representa una predicción causal"),
        resultado=resultado, incertidumbre="alta: requiere calibración con observaciones reales",
        validacion=("comparar con línea base", "medir variables objetivo", "replicar temporalmente", "registrar efectos no previstos")
    ))

def comparar(linea_base: dict, escenarios: list[dict]) -> list[dict]:
    salida = []
    for esc in escenarios:
        diferencias = {}
        for k, v in esc.get("resultado", {}).items():
            b = linea_base.get(k)
            if isinstance(v, (int, float)) and isinstance(b, (int, float)):
                diferencias[k] = round(v - b, 6)
        salida.append({"id": esc.get("id"), "nombre": esc.get("nombre"), "diferencias": diferencias, "incertidumbre": esc.get("incertidumbre")})
    return salida
