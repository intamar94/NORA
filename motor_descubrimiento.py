"""Motor exploratorio de descubrimiento para NORA.

Busca relaciones multivariables, retardos temporales, anomalías y similitud
regional sin afirmar causalidad. Produce un JSON compacto para la interfaz.
"""
import json, math, os
from itertools import combinations
import numpy as np
import pandas as pd
from supabase import create_client

URL = os.environ["SUPABASE_URL"]
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
REGION = os.getenv("NORA_REGION_ID", "alto_xingu")
MAX_LAG = int(os.getenv("NORA_MAX_LAG", "6"))
MIN_POINTS = int(os.getenv("NORA_MIN_POINTS", "24"))
OUT = os.getenv("NORA_OUTPUT", "nora_discoveries.json")

sb = create_client(URL, KEY)

def fetch_all(table, columns="*"):
    rows=[]
    start=0
    while True:
        r=sb.table(table).select(columns).range(start,start+999).execute()
        batch=r.data or []
        rows.extend(batch)
        if len(batch)<1000: break
        start += 1000
    return rows

regions=fetch_all("nora_regions")
region=next((r for r in regions if r.get("region_id")==REGION), None)
if not region:
    raise RuntimeError(f"Región no encontrada: {REGION}")

region_db_id=region["id"]
vars_rows=fetch_all("nora_variables", "id,key,unit,source_id")
var={v["id"]:v for v in vars_rows}
obs=[]
start=0
while True:
    r=(sb.table("nora_observations").select("variable_id,cell_id,observed_at,value")
       .eq("region_id",region_db_id).range(start,start+9999).execute())
    batch=r.data or []
    obs.extend(batch)
    if len(batch)<10000: break
    start += 10000

if not obs:
    raise RuntimeError("No hay observaciones para ejecutar descubrimiento")

df=pd.DataFrame(obs)
df["observed_at"]=pd.to_datetime(df["observed_at"])
df=df.join(df["variable_id"].map(pd.Series({k:v["key"] for k,v in var.items()}, name="variable")), on="variable_id")

# cell x month x variable cube
cube=df.pivot_table(index=["cell_id","observed_at"], columns="variable", values="value", aggfunc="mean")

# robust z-score anomaly by cell and variable
anomalies={}
for col in cube.columns:
    x=cube[col]
    med=x.groupby(level=0).transform("median")
    mad=(x-med).abs().groupby(level=0).transform("median")
    z=(x-med)/(1.4826*mad.replace(0,np.nan))
    anomalies[col]=z
anom=pd.DataFrame(anomalies,index=cube.index)

pairs=[]
cols=[c for c in cube.columns if cube[c].notna().sum()>=MIN_POINTS]
for a,b in combinations(cols,2):
    xa=cube[a]; xb=cube[b]
    for lag in range(0,MAX_LAG+1):
        # b at t versus a at t-lag months, within each cell
        left=xa.groupby(level=0).shift(lag)
        pair=pd.concat([left.rename("a"),xb.rename("b")],axis=1).dropna()
        if len(pair)<MIN_POINTS: continue
        r=float(pair["a"].corr(pair["b"]))
        if math.isfinite(r):
            pairs.append({"a":a,"b":b,"lag_months":lag,"correlation":r,"n":int(len(pair))})

pairs.sort(key=lambda x:abs(x["correlation"]),reverse=True)

# Spatially normalized fingerprints: average standardized monthly profile per cell.
finger=[]
for col in cols:
    x=cube[col]
    mu=x.mean(); sd=x.std()
    finger.append(((x-mu)/sd).rename(col))
f=pd.concat(finger,axis=1).groupby(level=0).mean()

similar=[]
if len(f)>=2:
    arr=f.fillna(0).to_numpy()
    norms=np.linalg.norm(arr,axis=1)
    ids=f.index.to_list()
    for i in range(len(ids)):
        sims=arr[i]@arr.T/(norms[i]*norms+1e-12)
        order=np.argsort(-sims)
        for j in order[1:4]:
            similar.append({"cell_a":int(ids[i]),"cell_b":int(ids[j]),"similarity":float(sims[j])})

# A small set of high-value hypotheses. They are explicitly exploratory.
hyp=[]
for p in pairs[:20]:
    if abs(p["correlation"])<0.35: break
    direction="positiva" if p["correlation"]>0 else "negativa"
    lag=p["lag_months"]
    text=f"{p['a']} presenta relación {direction} con {p['b']}"
    if lag: text += f" con un desfase aproximado de {lag} meses"
    hyp.append({"statement":text,"evidence":p,"status":"exploratoria","causality":"no_determinada"})

result={
    "region":REGION,
    "period_start":str(cube.index.get_level_values(1).min().date()),
    "period_end":str(cube.index.get_level_values(1).max().date()),
    "cells":int(cube.index.get_level_values(0).nunique()),
    "variables":cols,
    "observations":int(len(df)),
    "top_relations":pairs[:100],
    "anomaly_summary":{
        c:{"mean_abs_z":float(np.nanmean(np.abs(anom[c])))} for c in cols if c in anom
    },
    "similar_cells":similar[:100],
    "hypotheses":hyp,
    "method":"Pearson correlation by temporal lag, robust cell anomalies, standardized spatial fingerprints; exploratory only."
}
with open(OUT,"w",encoding="utf-8") as fh:
    json.dump(result,fh,ensure_ascii=False,indent=2)
print(f"NORA discovery: {len(cols)} variables, {len(df)} observations, {len(pairs)} lagged relations")
print(f"Top relation: {pairs[0] if pairs else 'none'}")
