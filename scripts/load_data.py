"""
Load cleaned CSV data into Supabase tables via REST API.
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


def clean_record(record):
    """Clean a record dict for JSON serialization."""
    cleaned = {}
    for key, val in record.items():
        if val is None:
            cleaned[key] = None
        elif isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            cleaned[key] = None
        elif isinstance(val, (np.integer,)):
            cleaned[key] = int(val)
        elif isinstance(val, (np.floating,)):
            if math.isnan(val) or math.isinf(val):
                cleaned[key] = None
            else:
                cleaned[key] = float(val)
        elif hasattr(val, 'item'):  # numpy scalar
            cleaned[key] = val.item()
        else:
            cleaned[key] = val
    return cleaned


def load_table(csv_path, table_name, batch_size=500):
    """Load CSV into Supabase table via REST API batch inserts."""
    df = pd.read_csv(csv_path)

    # Don't send 'id' column for tables with SERIAL id
    if 'id' in df.columns:
        df = df.drop(columns=['id'])

    total = len(df)
    inserted = 0
    errors = 0
    error_msgs = []

    print(f"\n  Loading {table_name}: {total:,} rows in batches of {batch_size}")

    for i in range(0, total, batch_size):
        batch = df.iloc[i:i + batch_size]
        records = [clean_record(r) for r in batch.to_dict(orient='records')]

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
            msg = f"Batch {i // batch_size}: {resp.status_code} - {resp.text[:300]}"
            error_msgs.append(msg)
            if errors <= 5:
                print(f"    ERROR: {msg}")
            elif errors == 6:
                print(f"    (suppressing further errors...)")

        # Progress every 10 batches
        batch_num = i // batch_size
        if batch_num % 10 == 0:
            pct = min(100, (i + batch_size) * 100 // total)
            print(f"    Progress: {min(i + batch_size, total):,}/{total:,} ({pct}%)")

    print(f"  RESULT: {inserted:,}/{total:,} rows inserted, {errors} batch errors")
    return inserted, errors


# ── Verify tables exist ──────────────────────────────────────────────────────
print("=== VERIFYING TABLES EXIST ===")
all_ok = True
for table in ['providers', 'deficiencies', 'quality_measures']:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}?select=*&limit=1",
        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
    )
    status = "OK" if resp.status_code == 200 else f"FAILED ({resp.status_code})"
    print(f"  {table}: {status}")
    if resp.status_code != 200:
        all_ok = False

if not all_ok:
    print("\nERROR: Not all tables are accessible. Please create them first.")
    sys.exit(1)

# ── Load data ────────────────────────────────────────────────────────────────
print("\n=== LOADING DATA ===")

# Load providers FIRST (parent table, referenced by FK)
t0 = time.time()
prov_ins, prov_err = load_table(os.path.join(OUT, "providers_clean.csv"), "providers", batch_size=500)
print(f"  Time: {time.time() - t0:.0f}s")

# Load deficiencies (417K rows - use larger batches for speed)
t0 = time.time()
defi_ins, defi_err = load_table(os.path.join(OUT, "deficiencies_clean.csv"), "deficiencies", batch_size=500)
print(f"  Time: {time.time() - t0:.0f}s")

# Load quality measures (250K rows)
t0 = time.time()
qual_ins, qual_err = load_table(os.path.join(OUT, "quality_measures_clean.csv"), "quality_measures", batch_size=500)
print(f"  Time: {time.time() - t0:.0f}s")

# ── Verify row counts ───────────────────────────────────────────────────────
print("\n=== VERIFYING ROW COUNTS ===")
for table, expected in [('providers', 14713), ('deficiencies', 417293), ('quality_measures', 250121)]:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}?select=*",
        headers={
            "apikey": SERVICE_KEY,
            "Authorization": f"Bearer {SERVICE_KEY}",
            "Prefer": "count=exact",
            "Range": "0-0",
        }
    )
    content_range = resp.headers.get('content-range', 'unknown')
    print(f"  {table}: {content_range} (expected {expected:,})")

# ── Validation queries ───────────────────────────────────────────────────────
print("\n=== VALIDATION QUERIES ===")

# Query 1: Top states
print("\n  Query 1: Top 10 states by provider count")
resp = requests.get(
    f"{SUPABASE_URL}/rest/v1/providers?select=state",
    headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}",
             "Prefer": "count=exact", "Range": "0-99999"}
)
if resp.status_code == 200:
    from collections import Counter
    data = resp.json()
    state_counts = Counter(r['state'] for r in data)
    for state, count in state_counts.most_common(10):
        print(f"    {state}: {count}")

# Query 2: Top deficiency categories (sample)
print("\n  Query 2: Top deficiency categories (from first 50K rows)")
resp = requests.get(
    f"{SUPABASE_URL}/rest/v1/deficiencies?select=deficiency_category&limit=50000",
    headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
)
if resp.status_code == 200:
    data = resp.json()
    cat_counts = Counter(r['deficiency_category'] for r in data if r.get('deficiency_category'))
    for cat, count in cat_counts.most_common(10):
        print(f"    {cat}: {count}")

# Query 3: Sample quality measures
print("\n  Query 3: Sample quality measures with avg scores")
resp = requests.get(
    f"{SUPABASE_URL}/rest/v1/quality_measures?select=measure_description,score,national_average&limit=5",
    headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
)
if resp.status_code == 200:
    data = resp.json()
    for r in data:
        desc = (r.get('measure_description') or 'N/A')[:60]
        score = r.get('score', 'N/A')
        navg = r.get('national_average', 'N/A')
        if isinstance(navg, float):
            navg = f"{navg:.2f}"
        print(f"    {desc}: score={score}, nat_avg={navg}")

print("\n=== ALL DONE ===")
