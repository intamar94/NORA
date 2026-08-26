"""NORA Discovery Engine.

Usa la matriz real nora_ingesta_alto_xingu (una fila por celda/mes) y separa
variables dinámicas de propiedades estáticas del suelo. Los resultados son
exploratorios y nunca se presentan como causalidad.
"""
import json
import math
import os
from itertools import combinations
import numpy as np
import pandas as pd
from supabase import create_client

URL = os.environ["SUPABASE_URL"]
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
REGION = os.getenv("NORA_REGION_ID", "alto_xingu")
MAX_LAG = int(os.getenv("NORA_MAX_LAG", "6"))
MIN_POINTS = int(os.getenv("NORA_MIN_POINTS", "36"))
OUT = os.getenv("NORA_OUTPUT", "nora_discoveries.json")
BASE_TABLE = "nora_ingesta_alto_xingu"
sb = create_client(URL, KEY)

VARIABLES = [
    "ndvi", "precip_mm", "temp_c", "cloud_fraction", "cloud_top_height_m", "cloud_optical_depth",
    "evapotranspiration_mm", "potential_evapotranspiration_mm", "runoff_mm", "surface_runoff_mm",
    "subsurface_runoff_mm", "soil_moisture_surface", "soil_moisture_rootzone", "lst_day_c", "lst_night_c",
    "lai", "fpar", "vpd_kpa", "wind_speed_ms", "surface_radiation_wm2", "surface_pressure_pa",
    "burned_fraction", "water_fraction", "co_mol_m2", "no2_mol_m2", "ch4_mol_m2", "aerosol_index",
    "gpp", "evi", "gpm_precip_mm", "smap_surface_soil_moisture", "smap_rootzone_soil_moisture",
]
STATIC = ["clay_0_5cm_mean", "sand_0_5cm_mean", "soc_0_5cm_mean", "phh2o_0_5cm_mean"]


def fetch_all(columns, batch_size=5000):
    rows, start = [], 0
    while True:
        r = (sb.table(BASE_TABLE).select(columns)
             .order("cell_id").order("year").order("month")
             .range(start, start + batch_size - 1).execute())
        batch = r.data or []
        rows.extend(batch)
        if len(batch) < batch_size:
            break
        start += batch_size
    return rows

columns = ["cell_id", "year", "month"] + VARIABLES + STATIC
rows = fetch_all(",".join(columns))
if not rows:
    raise RuntimeError(f"No hay datos en {BASE_TABLE}")

df = pd.DataFrame(rows)
df["observed_at"] = pd.to_datetime(dict(year=df.year, month=df.month, day=1))
df = df.sort_values(["cell_id", "observed_at"])
available = [c for c in VARIABLES if c in df.columns and df[c].notna().sum() >= MIN_POINTS]

dynamic = []
for col in available:
    if df.groupby("cell_id")[col].std().fillna(0).gt(1e-12).sum() > 0:
        dynamic.append(col)

pairs = []
for a, b in combinations(dynamic, 2):
    for lag in range(MAX_LAG + 1):
        left = df[["cell_id", "observed_at", a]].copy()
        right = df[["cell_id", "observed_at", b]].copy()
        left["observed_at"] = left["observed_at"] + pd.DateOffset(months=lag)
        pair = left.merge(right, on=["cell_id", "observed_at"], how="inner").dropna(subset=[a, b])
        if len(pair) < MIN_POINTS:
            continue
        rs = pair.groupby("cell_id").apply(
            lambda g: g[a].corr(g[b]) if len(g) >= MIN_POINTS else np.nan
        ).replace([np.inf, -np.inf], np.nan).dropna()
        if len(rs):
            pairs.append({
                "a": a, "b": b, "lag_months": lag,
                "mean_within_cell_r": float(rs.mean()),
                "median_within_cell_r": float(rs.median()),
                "cells": int(len(rs)),
            })
pairs.sort(key=lambda x: abs(x["mean_within_cell_r"]), reverse=True)

# NDVI/precipitation sensitivity by cell, then compare the best-lag sensitivity
# against static soil properties. This reduces simple spatial confounding.
soil_effects = []
if "ndvi" in dynamic and "precip_mm" in dynamic:
    lag_records = []
    for cell_id, g in df.groupby("cell_id", sort=False):
        g = g.sort_values("observed_at")
        if len(g) < MIN_POINTS:
            continue
        for lag in range(MAX_LAG + 1):
            r = g["precip_mm"].shift(lag).corr(g["ndvi"])
            if pd.notna(r):
                lag_records.append((cell_id, lag, float(r)))
    sens = pd.DataFrame(lag_records, columns=["cell_id", "lag", "rain_ndvi_r"])
    if not sens.empty:
        best_idx = sens.groupby("cell_id")["rain_ndvi_r"].apply(lambda s: s.abs().idxmax())
        best = sens.loc[best_idx].copy()
        soil = df.groupby("cell_id")[STATIC].first().reset_index()
        best = best.merge(soil, on="cell_id", how="left")
        for col in STATIC:
            if col in best and best[col].notna().sum() >= MIN_POINTS:
                r = best["rain_ndvi_r"].corr(best[col])
                if pd.notna(r):
                    soil_effects.append({
                        "soil_variable": col,
                        "correlation_with_best_rain_ndvi_sensitivity": float(r),
                        "cells": int(best[["rain_ndvi_r", col]].dropna().shape[0]),
                    })

index = pd.MultiIndex.from_frame(df[["cell_id", "observed_at"]])
cube = df.set_index(index)[dynamic]
anomaly_summary = {}
for col in dynamic:
    x = cube[col]
    med = x.groupby(level=0).transform("median")
    mad = (x - med).abs().groupby(level=0).transform("median")
    z = (x - med) / (1.4826 * mad.replace(0, np.nan))
    anomaly_summary[col] = {
        "mean_abs_z": float(np.nanmean(np.abs(z))) if np.isfinite(z).any() else None,
        "cells_with_anomalies": int(np.isfinite(z).groupby(level=0).any().sum()),
    }

hypotheses = []
for p in pairs[:30]:
    if abs(p["mean_within_cell_r"]) < 0.35:
        break
    direction = "positiva" if p["mean_within_cell_r"] > 0 else "negativa"
    hypotheses.append({
        "statement": f"{p['a']} presenta relación {direction} con {p['b']} con un desfase de {p['lag_months']} meses",
        "evidence": p, "status": "exploratoria", "causality": "no_determinada",
    })

result = {
    "region": REGION,
    "source_table": BASE_TABLE,
    "period_start": str(df.observed_at.min().date()),
    "period_end": str(df.observed_at.max().date()),
    "cells": int(df.cell_id.nunique()),
    "rows": int(len(df)),
    "dynamic_variables": dynamic,
    "static_soil_variables": [c for c in STATIC if c in df.columns],
    "top_relations": pairs[:100],
    "soil_effects": soil_effects,
    "anomaly_summary": anomaly_summary,
    "hypotheses": hypotheses,
    "method": "Within-cell Pearson lag correlations, best-lag NDVI/precipitation sensitivity, static-soil moderation and robust MAD anomalies; exploratory only.",
}
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(result, fh, ensure_ascii=False, indent=2)
print(f"NORA Discovery: {len(dynamic)} dynamic variables, {len(df)} rows, {len(pairs)} lagged relations")
print(f"Top relation: {pairs[0] if pairs else 'none'}")
