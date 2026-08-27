"""Orquestador central del pipeline NORA."""
from __future__ import annotations
from dataclasses import dataclass
from .analisis_adaptativo import construir_plan
from .fuentes import resolver_fuentes
from .data_fabric import Necesidad, estado_datos
from .adquisicion import construir_tareas, validar_tarea
from .calidad import evaluar as evaluar_calidad
from .alineacion import alinear_temporal
from .relaciones import correlacion
from .hipotesis import generar as generar_hipotesis
from .escenarios import simular, comparar
from .evaluacion import evaluar as evaluar_escenario, ranking

@dataclass
class EstadoPipeline:
    estado: str = "listo"
    etapa: str = "inicio"
    progreso: int = 0
    errores: list[str] | None = None
    resultados: dict | None = None
    def __post_init__(self):
        self.errores = [] if self.errores is None else self.errores
        self.resultados = {} if self.resultados is None else self.resultados

class Orquestador:
    def __init__(self): self.estado = EstadoPipeline()
    def _set(self, etapa, progreso, resultado=None):
        self.estado.estado="procesando"; self.estado.etapa=etapa; self.estado.progreso=progreso
        if resultado is not None: self.estado.resultados[etapa]=resultado
    def planificar(self, caso, zona, periodo):
        self._set("planificacion",10); plan=construir_plan(caso,zona)
        variables=[v["nombre"] for v in plan["variables"]]
        necesidades=[Necesidad(variable=v, inicio=periodo.get("inicio"), fin=periodo.get("fin")) for v in variables]
        fabric=estado_datos(necesidades)
        fuentes=resolver_fuentes(variables)
        tareas=construir_tareas(fuentes,zona,periodo)
        valid=[validar_tarea(t) for t in tareas]
        self._set("adquisicion",25,{"plan":plan,"data_fabric":fabric,"fuentes":fuentes,"tareas":tareas,"validaciones":valid})
        return self.estado
    def integrar(self, datos):
        self._set("calidad",40); calidad={k:evaluar_calidad(v,k) for k,v in datos.items()}
        aptos={k:v for k,v in datos.items() if calidad[k]["estado"]=="apto"}
        alineados={k:alinear_temporal(v) for k,v in aptos.items()}
        self._set("alineacion",55,{"calidad":calidad,"variables_alineadas":list(alineados)})
        return alineados
    def analizar(self, datos):
        self._set("relaciones",70); nombres=list(datos); hallazgos=[]
        for i,a in enumerate(nombres):
            for b in nombres[i+1:]:
                h=correlacion(datos[a],datos[b],a,b)
                if h: hallazgos.append(h)
        hips=[generar_hipotesis(h) for h in hallazgos]
        self._set("hipotesis",80,{"hallazgos":hallazgos,"hipotesis":hips}); return hallazgos,hips
    def escenarios(self, linea_base, hipotesis, cambios):
        self._set("escenarios",90)
        esc=[simular(linea_base,cambios.get(h["id"],{}),h["id"]) for h in hipotesis]
        comp=comparar(linea_base,esc); evals=[evaluar_escenario(e) for e in esc]; orden=ranking(evals)
        self._set("escenarios",100,{"escenarios":esc,"comparacion":comp,"ranking":orden})
        self.estado.estado="listo"; self.estado.etapa="completado"; return self.estado
