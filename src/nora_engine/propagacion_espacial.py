"""Estimación geoespacial conservadora de exposición para NORA."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Nodo:
    id: str
    lat: float
    lon: float
    elevacion_m: float
    poblacion: float = 0.0
    nombre: str = ""

@dataclass(frozen=True)
class Enlace:
    desde: str
    hasta: str
    distancia_km: float
    velocidad_kmh: float
    riesgo: float = 1.0

def propagar(nodos: list[Nodo], enlaces: list[Enlace], origen: str, horizonte_h: float | None = None) -> dict:
    """Estima conectividad, llegada y exposición; no simula física de fluidos."""
    by_id={n.id:n for n in nodos}; adj={n.id:[] for n in nodos}
    for e in enlaces:
        if e.desde in adj and e.hasta in by_id and e.distancia_km>=0 and e.velocidad_kmh>0:
            adj[e.desde].append(e)
    if origen not in by_id:
        return {"estado":"error","error":"origen inexistente"}
    dist={origen:0.0}; queue=[origen]
    while queue:
        actual=queue.pop(0)
        for e in adj[actual]:
            llegada=dist[actual]+e.distancia_km/e.velocidad_kmh
            if horizonte_h is not None and llegada>horizonte_h: continue
            if e.hasta not in dist or llegada<dist[e.hasta]:
                dist[e.hasta]=llegada; queue.append(e.hasta)
    exposiciones=[]
    for nid,horas in dist.items():
        n=by_id[nid]
        exposiciones.append({"nodo":nid,"nombre":n.nombre,"lat":n.lat,"lon":n.lon,"elevacion_m":n.elevacion_m,"tiempo_llegada_h":round(horas,3),"poblacion":n.poblacion})
    exposiciones.sort(key=lambda x:x["tiempo_llegada_h"])
    return {"estado":"estimado","origen":origen,"exposiciones":exposiciones,"poblacion_expuesta":sum(x["poblacion"] for x in exposiciones),"limitaciones":["requiere red geoespacial válida","no representa hidráulica ni dinámica de avalanchas","requiere modelo físico calibrado para decisiones operativas"]}
