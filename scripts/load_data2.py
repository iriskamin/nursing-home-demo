"""
Load cleaned CSV data into Supabase tables via REST API.
Uses unbuffered output for progress tracking.
"""
import requests
import pandas as pd
import numpy as np
import json
import sys
import os
import time
import math

sys.stdout.reconfigure(encoding='utf-8')

BASE = r"C:\Users\irisk\OneDrive\Antigravity\nursing-home-demo"
OUT = os.path.join(BASE, "outputs")

SUPABASE_URL = "https://fdxduktfejmwivsuzonx.supabase.co"
SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZkeGR1a3RmZWptd2l2c3V6b254Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTc0OTAyMCwiZXhwIjoyMDg3MzI1MDIwfQ.gA_RyXbK6JS4FZfmIl3sWdj274PhFvT6WKA8O18V4Uw"

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

def p(msg):
    print(msg, flush=True)

INT_COLS = {
    'overall_rating', 'health_inspection_rating', 'staffing_rating',
    'number_of_facility_reported_incidents'
}

def clean_val(val, col_name=None):
    if val is None:
        return None
    # Handle both Python float and numpy float
    if isinstance(val, (float, np.floating)):
        if math.isnan(val) or math.isinf(val):
            return None
        if col_name and col_name in INT_COLS:
            return int(val)
        return float(val)
    if isinstance(val, (int, np.integer)):
        return int(val)
    if hasattr(val, 'item'):
        return clean_val(val.item(), col_name)
    # pd.NA / pd.NaT
    if pd.isna(val):
        return None
    return val

def load_table(csv_path, table_name, batch_size=500):
    df = pd.read_csv(csv_path, dtype={'federal_provider_number': str}, low_memory=False)
    if 'id' in df.columns:
        df = df.drop(columns=['id'])

    total = len(df)
    inserted = 0
    errors = 0

    p(f"  {table_name}: {total:,} rows, batch_size={batch_size}")

    for i in range(0, total, batch_size):
        batch = df.iloc[i:i + batch_size]
        records = []
        for _, row in batch.iterrows():
            records.append({k: clean_val(v, col_name=k) for k, v in row.items()})

        try:
            resp = requests.post(
                f"{SUPABASE_URL}/rest/v1/{table_name}",
                json=records,
                headers=HEADERS,
                timeout=120
            )
            if resp.status_code in (200, 201):
                inserted += len(records)
            else:
                errors += 1
                if errors <= 3:
                    p(f"    ERR batch {i//batch_size}: {resp.status_code} - {resp.text[:200]}")
        except Exception as e:
            errors += 1
            if errors <= 3:
                p(f"    ERR batch {i//batch_size}: {e}")

        if (i // batch_size) % 50 == 0:
            pct = min(100, (i + batch_size) * 100 // total)
            p(f"    {min(i + batch_size, total):,}/{total:,} ({pct}%)")

    p(f"  DONE: {inserted:,}/{total:,} inserted, {errors} errors")
    return inserted

# ── Clear any existing data first ────────────────────────────────────────────
p("=== CLEARING EXISTING DATA ===")
for table in ['quality_measures', 'deficiencies', 'providers']:
    resp = requests.delete(
        f"{SUPABASE_URL}/rest/v1/{table}?id=gte.0" if table != 'providers'
        else f"{SUPABASE_URL}/rest/v1/{table}?federal_provider_number=neq.IMPOSSIBLE",
        headers={
            "apikey": SERVICE_KEY,
            "Authorization": f"Bearer {SERVICE_KEY}",
        },
        timeout=120
    )
    p(f"  Cleared {table}: {resp.status_code}")

# ── Load all tables ──────────────────────────────────────────────────────────
p("\n=== LOADING DATA INTO SUPABASE ===")

t0 = time.time()
p("\n--- PROVIDERS ---")
load_table(os.path.join(OUT, "providers_clean.csv"), "providers", 500)
p(f"  Time: {time.time()-t0:.0f}s")

t1 = time.time()
p("\n--- DEFICIENCIES ---")
load_table(os.path.join(OUT, "deficiencies_clean.csv"), "deficiencies", 500)
p(f"  Time: {time.time()-t1:.0f}s")

t2 = time.time()
p("\n--- QUALITY MEASURES ---")
load_table(os.path.join(OUT, "quality_measures_clean.csv"), "quality_measures", 500)
p(f"  Time: {time.time()-t2:.0f}s")

p(f"\nTotal time: {time.time()-t0:.0f}s")

# ── Verify ───────────────────────────────────────────────────────────────────
p("\n=== VERIFICATION ===")
for table in ['providers', 'deficiencies', 'quality_measures']:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}?select=*",
        headers={
            "apikey": SERVICE_KEY,
            "Authorization": f"Bearer {SERVICE_KEY}",
            "Prefer": "count=exact",
            "Range": "0-0",
        }
    )
    cr = resp.headers.get('content-range', '?')
    p(f"  {table}: {cr}")

p("\n=== VALIDATION QUERIES ===")

from collections import Counter

p("\nQuery 1: Top 10 states by provider count")
resp = requests.get(
    f"{SUPABASE_URL}/rest/v1/providers?select=state&limit=100000",
    headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
)
if resp.status_code == 200:
    sc = Counter(r['state'] for r in resp.json())
    for s, c in sc.most_common(10):
        p(f"  {s}: {c}")

p("\nQuery 2: Top 10 deficiency categories (sample of 50K)")
resp = requests.get(
    f"{SUPABASE_URL}/rest/v1/deficiencies?select=deficiency_category&limit=50000",
    headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
)
if resp.status_code == 200:
    cc = Counter(r['deficiency_category'] for r in resp.json() if r.get('deficiency_category'))
    for c, n in cc.most_common(10):
        p(f"  {c}: {n}")

p("\nQuery 3: Sample quality measures")
resp = requests.get(
    f"{SUPABASE_URL}/rest/v1/quality_measures?select=measure_description,score,national_average&limit=5",
    headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
)
if resp.status_code == 200:
    for r in resp.json():
        d = (r.get('measure_description') or '')[:60]
        s = r.get('score', 'N/A')
        n = r.get('national_average')
        n = f"{n:.2f}" if isinstance(n, float) else 'N/A'
        p(f"  {d}: score={s}, nat_avg={n}")

p("\n=== ALL DONE ===")
