"""Motor explicable de relaciones entre variables territoriales."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from math import sqrt
from statistics import mean, stdev

@dataclass(frozen=True)
class Hallazgo:
    variable_a: str
    variable_b: str
    metodo: str
    medida: float
    muestras: int
    confianza: float
    evidencia: str
    limitaciones: tuple[str, ...]
    siguiente_prueba: str

def _pearson(a, b):
    ma, mb = mean(a), mean(b)
    da = sqrt(sum((x-ma)**2 for x in a)); db = sqrt(sum((y-mb)**2 for y in b))
    return 0.0 if not da or not db else sum((x-ma)*(y-mb) for x,y in zip(a,b))/(da*db)

def correlacion(a, b, nombre_a, nombre_b):
    bm={r.get("periodo",r.get("fecha")):r.get("valor") for r in b if r.get("valor") is not None}
    pares=[(float(r["valor"]),float(bm[r.get("periodo",r.get("fecha"))])) for r in a if r.get("valor") is not None and r.get("periodo",r.get("fecha")) in bm]
    if len(pares)<5: return None
    x,y=zip(*pares); r=_pearson(x,y); conf=min(.99,max(.05,abs(r)*min(1,len(pares)/30)))
    return asdict(Hallazgo(nombre_a,nombre_b,"pearson",round(r,4),len(pares),round(conf,4),f"Asociación observada r={r:.3f}",( "correlación no implica causalidad","posibles variables de confusión"),"Repetir en otra zona/período y controlar confusores."))

def desfase(a,b,nombre_a,nombre_b,max_lag=6):
    av={r.get("periodo"):r.get("valor") for r in a if r.get("valor") is not None}; bv={r.get("periodo"):r.get("valor") for r in b if r.get("valor") is not None}; fechas=sorted(set(av)&set(bv)); out=[]
    for lag in range(1,max_lag+1):
        pares=[(float(av[fechas[i-lag]]),float(bv[fechas[i]])) for i in range(lag,len(fechas))]
        if len(pares)>=5:
            x,y=zip(*pares); out.append({"lag":lag,"correlacion":round(_pearson(x,y),4),"muestras":len(pares)})
    return sorted(out,key=lambda z:abs(z["correlacion"]),reverse=True)

def anomalias(serie,umbral=3.0):
    vals=[float(r["valor"]) for r in serie if r.get("valor") is not None]
    if len(vals)<5:return []
    m,s=mean(vals),stdev(vals)
    if not s:return []
    return [{**r,"z":round((float(r["valor"])-m)/s,3)} for r in serie if r.get("valor") is not None and abs((float(r["valor"])-m)/s)>=umbral]
