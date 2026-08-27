"""Motor temporal de NORA para evolución, velocidad y tiempos entre etapas."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class Observacion:
    etapa: str
    timestamp: str
    valor: float
    unidad: str = ""
    fuente: str = ""

ETAPAS_CASCADA=("inestabilidad_criosfera","avalancha_hielo_roca","bloqueo_cauce","acumulacion_agua","liberacion_surge","inundacion_aguas_abajo")

def _dt(value:str)->datetime:
    return datetime.fromisoformat(value.replace("Z","+00:00"))

def analizar_evolucion(observaciones:list[Observacion])->dict:
    """Calcula evolución observada; no convierte velocidad en predicción física."""
    if not observaciones:
        return {"estado":"sin_datos","etapas":[],"intervalos":[],"limitaciones":["no hay observaciones"]}
    orden=sorted(observaciones,key=lambda x:_dt(x.timestamp)); por_etapa={}
    for o in orden: por_etapa.setdefault(o.etapa,[]).append(o)
    etapas=[]
    for etapa,serie in por_etapa.items():
        velocidad=None
        if len(serie)>=2:
            a,b=serie[-2],serie[-1]; horas=(_dt(b.timestamp)-_dt(a.timestamp)).total_seconds()/3600
            if horas>0: velocidad=(b.valor-a.valor)/horas
        etapas.append({"etapa":etapa,"observaciones":len(serie),"ultimo_timestamp":serie[-1].timestamp,"valor_actual":serie[-1].valor,"velocidad_por_hora":velocidad,"fuentes":sorted({x.fuente for x in serie if x.fuente})})
    primeras={e:min(_dt(x.timestamp) for x in serie) for e,serie in por_etapa.items()}; intervalos=[]; prev=None
    for etapa in ETAPAS_CASCADA:
        if etapa in primeras:
            if prev is not None: intervalos.append({"desde":prev[0],"hasta":etapa,"horas":round((primeras[etapa]-prev[1]).total_seconds()/3600,3)})
            prev=(etapa,primeras[etapa])
    return {"estado":"analizado","etapas":etapas,"intervalos":intervalos,"secuencia_observada":[x[0] for x in sorted(primeras.items(),key=lambda p:p[1])],"limitaciones":["intervalos observados, no predicciones","se necesita suficiente frecuencia temporal","la predicción requiere modelos físicos calibrados y validación local"]}
