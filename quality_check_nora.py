"""NORA strict data-quality gate for Alto Xingu.

Audit the complete dataset without relying on large PostgREST offsets. The
previous global pagination reached >320k rows and hit PostgreSQL statement
timeout. We partition reads by year, so every query has a bounded offset while
preserving complete coverage and duplicate detection.
"""
import json, os, sys
import pandas as pd
from supabase import create_client

URL=os.environ["SUPABASE_URL"]; KEY=os.environ["SUPABASE_SERVICE_ROLE_KEY"]
TABLE=os.getenv("NORA_DATA_SOURCE","nora_ingesta_alto_xingu")
REGION=os.getenv("NORA_REGION_ID","alto_xingu")
EXPECTED_CELLS=int(os.getenv("NORA_EXPECTED_CELLS","1880")); START_YEAR=int(os.getenv("NORA_START_YEAR","2001")); END_YEAR=int(os.getenv("NORA_END_YEAR","2024"))
sb=create_client(URL,KEY)
required=["cell_id","year","month","centroid_lon","centroid_lat"]
scientific=["ndvi","precip_mm","temp_c","burned_fraction","water_fraction"]
select_cols=",".join(required+scientific)

rows=[]; page_size=1000
for year in range(START_YEAR, END_YEAR + 1):
    start=0
    while True:
        data=(sb.table(TABLE).select(select_cols)
              .eq("year", year)
              .order("cell_id").order("month")
              .range(start,start+page_size-1).execute().data or [])
        rows.extend(data)
        print(f"Calidad: year={year} start={start} rows={len(data)} total={len(rows)}")
        if len(data)<page_size: break
        start += page_size

if not rows: raise RuntimeError(f"Fuente vacia: {TABLE}")
df=pd.DataFrame(rows)
for c in required:
    if c not in df.columns: raise RuntimeError(f"Falta columna obligatoria: {c}")
for c in required+scientific: df[c]=pd.to_numeric(df[c],errors="coerce")
expected_rows=EXPECTED_CELLS*(END_YEAR-START_YEAR+1)*12
checks={
 "rows":len(df),"expected_rows":expected_rows,"cells":int(df.cell_id.nunique()),"expected_cells":EXPECTED_CELLS,
 "period_start":int(df.year.min()),"period_end":int(df.year.max()),
 "distinct_year_month":int(df[["year","month"]].drop_duplicates().shape[0]),"expected_year_month":(END_YEAR-START_YEAR+1)*12,
 "null_keys":int(df[required].isna().any(axis=1).sum()),"invalid_month":int((~df.month.between(1,12)).sum()),
 "invalid_year":int((~df.year.between(START_YEAR,END_YEAR)).sum()),"duplicate_cell_month":int(df.duplicated(["cell_id","year","month"]).sum()),
 "invalid_lon":int((~df.centroid_lon.between(-55.3,-51.2)).sum()),"invalid_lat":int((~df.centroid_lat.between(-15.3,-10.4)).sum())}
null_rates={c:round(float(df[c].isna().mean()),6) for c in scientific}; checks["null_rates"]=null_rates
ranges={"ndvi":(-1,1),"precip_mm":(0,5000),"temp_c":(-80,80),"burned_fraction":(0,1),"water_fraction":(0,1)}
range_failures={c:int((df[c].notna() & ~df[c].between(lo,hi)).sum()) for c,(lo,hi) in ranges.items()}; checks["range_failures"]=range_failures
failures=[]
for k in ("null_keys","invalid_month","invalid_year","duplicate_cell_month","invalid_lon","invalid_lat"):
    if checks[k]: failures.append(k)
if checks["rows"]!=expected_rows: failures.append("row_coverage")
if checks["cells"]!=EXPECTED_CELLS: failures.append("cell_coverage")
if checks["period_start"]!=START_YEAR or checks["period_end"]!=END_YEAR: failures.append("year_coverage")
if checks["distinct_year_month"]!=checks["expected_year_month"]: failures.append("month_coverage")
for c,bad in range_failures.items():
    if bad: failures.append(f"range:{c}")
for c in ("ndvi","precip_mm","temp_c","burned_fraction"):
    if null_rates[c]>.20: failures.append(f"null_rate:{c}")
pre=df[df.year<=2021]; post=df[df.year>2021]
checks["water_null_rate_pre_2022"]=round(float(pre.water_fraction.isna().mean()),6) if len(pre) else None
checks["water_null_rate_post_2021"]=round(float(post.water_fraction.isna().mean()),6) if len(post) else None
if len(pre) and checks["water_null_rate_pre_2022"]>.20: failures.append("null_rate:water_fraction_pre_2022")
result={"region":REGION,"source":TABLE,"status":"PASS" if not failures else "FAIL","checks":checks,"failures":failures,"policy":"No imputation; unsupported or missing source data remains missing and blocks downstream use where required."}
with open("nora_quality_report.json","w",encoding="utf-8") as f: json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps(result,ensure_ascii=False,indent=2))
if failures: sys.exit(1)
