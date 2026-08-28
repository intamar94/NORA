"""NORA strict data-quality gate for Alto Xingu.

The gate is deliberately conservative: it never fills missing scientific values.
It validates structure, temporal/spatial coverage, null rates and physical ranges.
A FAIL blocks downstream discovery.
"""
import json
import os
import sys
import pandas as pd
from supabase import create_client

URL = os.environ["SUPABASE_URL"]
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
TABLE = os.getenv("NORA_DATA_SOURCE", "nora_ingesta_alto_xingu")
REGION = os.getenv("NORA_REGION_ID", "alto_xingu")
EXPECTED_CELLS = int(os.getenv("NORA_EXPECTED_CELLS", "1880"))
START_YEAR = int(os.getenv("NORA_START_YEAR", "2001"))
END_YEAR = int(os.getenv("NORA_END_YEAR", "2024"))

sb = create_client(URL, KEY)
required = ["cell_id", "year", "month", "centroid_lon", "centroid_lat"]
scientific = ["ndvi", "precip_mm", "temp_c", "burned_fraction"]
select_cols = ",".join(required + scientific)

rows = []
start = 0
batch = 5000
while True:
    r = (sb.table(TABLE).select(select_cols)
         .order("cell_id").order("year").order("month")
         .range(start, start + batch - 1).execute())
    data = r.data or []
    rows.extend(data)
    if len(data) < batch:
        break
    start += batch

if not rows:
    raise RuntimeError(f"Fuente vacia: {TABLE}")

df = pd.DataFrame(rows)
for c in required:
    if c not in df.columns:
        raise RuntimeError(f"Falta columna obligatoria: {c}")

for c in ["year", "month", "cell_id", "centroid_lon", "centroid_lat"] + scientific:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

checks = {
    "rows": int(len(df)),
    "cells": int(df.cell_id.nunique()),
    "expected_cells": EXPECTED_CELLS,
    "period_start": int(df.year.min()),
    "period_end": int(df.year.max()),
    "distinct_year_month": int(df[["year", "month"]].drop_duplicates().shape[0]),
    "expected_year_month": (END_YEAR - START_YEAR + 1) * 12,
    "null_keys": int(df[required].isna().any(axis=1).sum()),
    "invalid_month": int((~df.month.between(1, 12)).sum()),
    "invalid_year": int((~df.year.between(START_YEAR, END_YEAR)).sum()),
    "duplicate_cell_month": int(df.duplicated(["cell_id", "year", "month"]).sum()),
    "invalid_lon": int((~df.centroid_lon.between(-55.3, -51.2)).sum()),
    "invalid_lat": int((~df.centroid_lat.between(-15.3, -10.4)).sum()),
}

# Completeness is reported per variable. For variables expected in the base ingest,
# excessive missingness is a hard failure; water is explicitly exempt after 2021.
null_rates = {}
for c in scientific:
    if c in df.columns:
        null_rates[c] = round(float(df[c].isna().mean()), 6)

checks["null_rates"] = null_rates

range_failures = {}
ranges = {
    "ndvi": (-1.0, 1.0),
    "precip_mm": (0.0, 5000.0),
    "temp_c": (-80.0, 80.0),
    "burned_fraction": (0.0, 1.0),
}
for c, (lo, hi) in ranges.items():
    if c in df.columns:
        bad = int((df[c].notna() & ~df[c].between(lo, hi)).sum())
        range_failures[c] = bad
checks["range_failures"] = range_failures

failures = []
for key in (
    "null_keys", "invalid_month", "invalid_year", "duplicate_cell_month",
    "invalid_lon", "invalid_lat"
):
    if checks[key] != 0:
        failures.append(key)
if checks["cells"] != EXPECTED_CELLS:
    failures.append("cell_coverage")
if checks["period_start"] != START_YEAR or checks["period_end"] != END_YEAR:
    failures.append("year_coverage")
if checks["distinct_year_month"] != checks["expected_year_month"]:
    failures.append("month_coverage")
for c, bad in range_failures.items():
    if bad:
        failures.append(f"range:{c}")
for c in ("ndvi", "precip_mm", "temp_c", "burned_fraction"):
    if c in null_rates and null_rates[c] > 0.20:
        failures.append(f"null_rate:{c}")

# Water is expected to be unavailable after 2021 in the current JRC source.
if "water_fraction" in df.columns:
    post_2021 = df[df.year > 2021]
    pre_2022 = df[df.year <= 2021]
    checks["water_null_rate_pre_2022"] = round(float(pre_2022.water_fraction.isna().mean()), 6) if len(pre_2022) else None
    checks["water_null_rate_post_2021"] = round(float(post_2021.water_fraction.isna().mean()), 6) if len(post_2021) else None

result = {
    "region": REGION,
    "source": TABLE,
    "status": "PASS" if not failures else "FAIL",
    "checks": checks,
    "failures": failures,
    "policy": "No imputation; missing/unsupported source data remains missing and is never presented as measured."
}
with open("nora_quality_report.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(json.dumps(result, ensure_ascii=False, indent=2))
if failures:
    sys.exit(1)
