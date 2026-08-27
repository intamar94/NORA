"""Plan de adquisición: convierte fuentes resueltas en tareas verificables."""
from __future__ import annotations
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class TareaDatos:
    variable: str
    fuente: str
    zona: dict
    periodo: dict
    estado: str = "pendiente"
    razon: str = ""

def construir_tareas(resueltas: list[dict], zona: dict, periodo: dict) -> list[dict]:
    return [asdict(TareaDatos(variable=x["variable"], fuente=x["nombre"], zona=zona, periodo=periodo, razon=f"Fuente priorizada para {x['variable']}")) for x in resueltas]

def validar_tarea(tarea: dict) -> tuple[bool, str]:
    if not tarea.get("zona"):
        return False, "zona_no_definida"
    periodo = tarea.get("periodo") or {}
    if not periodo.get("inicio") or not periodo.get("fin"):
        return False, "periodo_no_definido"
    if not tarea.get("fuente") or not tarea.get("variable"):
        return False, "fuente_o_variable_no_definida"
    return True, "ok"
