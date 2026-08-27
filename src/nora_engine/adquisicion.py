"""Plan de adquisición y verificación de datos territoriales."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import date

@dataclass(frozen=True)
class TareaDatos:
    variable: str
    fuente: str
    zona: dict
    periodo: dict
    estado: str = "pendiente"
    razon: str = ""
    cobertura_requerida: str = "global"
    calidad_minima: float = 0.0


def construir_tareas(resueltas: list[dict], zona: dict, periodo: dict) -> list[dict]:
    return [asdict(TareaDatos(variable=x["variable"], fuente=x["nombre"], zona=zona, periodo=periodo, razon=f"Fuente priorizada para {x['variable']}", cobertura_requerida=x.get("cobertura", "global"))) for x in resueltas]


def validar_tarea(tarea: dict) -> tuple[bool, str]:
    if not tarea.get("zona"):
        return False, "zona_no_definida"
    periodo = tarea.get("periodo") or {}
    if not periodo.get("inicio") or not periodo.get("fin"):
        return False, "periodo_no_definido"
    try:
        inicio, fin = date.fromisoformat(periodo["inicio"]), date.fromisoformat(periodo["fin"])
        if inicio > fin:
            return False, "periodo_invertido"
    except (TypeError, ValueError):
        return False, "periodo_invalido"
    if not tarea.get("fuente") or not tarea.get("variable"):
        return False, "fuente_o_variable_no_definida"
    return True, "ok"


def evaluar_cobertura(tarea: dict, cobertura: dict) -> tuple[bool, str]:
    if cobertura.get("variable") != tarea.get("variable"):
        return False, "variable_no_coincide"
    if not cobertura.get("disponible", False):
        return False, "fuente_no_disponible"
    if cobertura.get("fecha_inicio") and cobertura.get("fecha_fin"):
        p = tarea["periodo"]
        if p["inicio"] < cobertura["fecha_inicio"] or p["fin"] > cobertura["fecha_fin"]:
            return False, "periodo_fuera_de_cobertura"
    return True, "cobertura_ok"
