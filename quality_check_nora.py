"""NORA data quality gate.

Validates the generic NORA ingest view before discovery. It does not alter
scientific data. It exits non-zero when structural/quality conditions fail.
"""
import json
import os
import sys
import pandas as pd
from supabase import create_client

URL = os.environ["SUPABASE_URL"]
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
TABLE = os.getenv("NORA_DATA_SOURCE", "nora_data_ingest")
REGION = os.getenv("NORA_REGION_ID", "alto_xingu")
sb = create_client(URL, KEY)

required = ["cell_id", "year", "month"]
select_cols = ",".join(required)
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
    if c not in df:
        raise RuntimeError(f"Falta columna obligatoria: {c}")

df["year"] = pd.to_numeric(df["year"], errors="coerce")
df["month"] = pd.to_numeric(df["month"], errors="coerce")
checks = {}
checks["rows"] = int(len(df))
checks["cells"] = int(df.cell_id.nunique())
checks["null_keys"] = int(df[required].isna().any(axis=1).sum())
checks["invalid_month"] = int((~df.month.between(1, 12)).sum())
checks["invalid_year"] = int((~df.year.between(1900, 2100)).sum())
checks["duplicate_cell_month"] = int(df.duplicated(required).sum())
checks["period_start"] = int(df.year.min())
checks["period_end"] = int(df.year.max())
checks["year_months"] = int(df[["year", "month"]].drop_duplicates().shape[0])

failures = [k for k in ("null_keys", "invalid_month", "invalid_year", "duplicate_cell_month") if checks[k] != 0]
result = {"region": REGION, "source": TABLE, "status": "PASS" if not failures else "FAIL", "checks": checks, "failures": failures}
with open("nora_quality_report.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(json.dumps(result, ensure_ascii=False, indent=2))
if failures:
    sys.exit(1)
