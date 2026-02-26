"""
Step 2: Create tables in Supabase and load cleaned CSV data.
Uses the Supabase REST API with service_role key.
"""
import requests
import pandas as pd
import numpy as np
import json
import sys
import os
import time

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

def run_sql(sql):
    """Execute raw SQL via Supabase's pg REST endpoint."""
    url = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"
    # Supabase doesn't have exec_sql by default. Use the SQL editor API instead.
    # We'll use the management API endpoint for SQL.
    pass

def run_sql_via_pg(sql):
    """Execute SQL via Supabase's /pg endpoint (requires service_role)."""
    url = f"{SUPABASE_URL}/pg/query"
    headers = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, json={"query": sql}, headers=headers)
    if resp.status_code == 200:
        return resp.json()
    else:
        # Try alternative endpoint
        return None

# ── Step 1: Create tables via SQL ────────────────────────────────────────────
print("=== CREATING TABLES VIA SQL ===")

# Try using the Supabase Management API to run SQL
# The endpoint is: POST /v1/projects/{ref}/database/query
# But that requires a management API key, not service_role.
#
# Alternative: Use the PostgREST rpc endpoint with a custom function.
# Or: Use the Supabase client library.
#
# Simplest approach: Create a temporary SQL function, or use the
# Supabase SQL endpoint that's available with service_role.

# Let's try the newer Supabase endpoint
def try_sql_endpoints(sql):
    """Try multiple SQL execution endpoints."""

    # Endpoint 1: /rest/v1/rpc/ with a custom function
    # Endpoint 2: Direct pg endpoint (newer Supabase versions)

    # Try the pg/query endpoint (available on newer Supabase instances)
    endpoints = [
        f"{SUPABASE_URL}/pg/query",
    ]

    for endpoint in endpoints:
        headers = {
            "apikey": SERVICE_KEY,
            "Authorization": f"Bearer {SERVICE_KEY}",
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(endpoint, json={"query": sql}, headers=headers)
            if resp.status_code in (200, 201):
                print(f"  SQL executed via {endpoint}")
                return resp.json()
            else:
                print(f"  {endpoint}: {resp.status_code} - {resp.text[:200]}")
        except Exception as e:
            print(f"  {endpoint}: Error - {e}")

    return None

# First, let's create an RPC function that lets us run arbitrary SQL
# This is the most reliable approach
create_exec_fn = """
CREATE OR REPLACE FUNCTION exec_sql(query text)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result json;
BEGIN
    EXECUTE query;
    RETURN '{"status": "ok"}'::json;
END;
$$;
"""

# Try creating via pg endpoint first
result = try_sql_endpoints(create_exec_fn)
if result is None:
    print("\n  pg/query endpoint not available. Trying alternative approach...")

    # Alternative: We'll create tables through the REST API approach
    # by first dropping any existing tables and recreating
    # We need to use a different approach - let's try the Supabase
    # Management API v1

    # Actually, the simplest reliable approach is to use the
    # PostgREST API to insert data, and create tables via
    # a stored procedure that we create first.

    # Let's try the Supabase SQL API endpoint
    sql_url = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"

    # First check if exec_sql already exists
    resp = requests.post(
        sql_url,
        json={"query": "SELECT 1"},
        headers=HEADERS
    )
    print(f"  exec_sql RPC test: {resp.status_code}")

    if resp.status_code == 404:
        print("\n  NOTE: Cannot create tables via API alone.")
        print("  We need to create tables first via Supabase Dashboard SQL Editor.")
        print("  But let's try another approach - using the Supabase client library.")

# ── Alternative: Use PostgREST directly ──────────────────────────────────────
# PostgREST can create tables if we use the right approach
# Actually, PostgREST is read/write for existing tables only.
# For DDL (CREATE TABLE), we need SQL access.

# Let's check what tables already exist
print("\n=== CHECKING EXISTING TABLES ===")
for table in ['providers', 'deficiencies', 'quality_measures']:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}?select=*&limit=1",
        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
    )
    print(f"  {table}: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"    -> Exists, has {len(data)} sample rows")
    else:
        print(f"    -> Does not exist or not accessible")

# ── Try to create tables via the Management API ─────────────────────────────
print("\n=== ATTEMPTING TABLE CREATION ===")

# The Supabase Management API requires a different auth token
# (personal access token from dashboard.supabase.com)
# With just service_role key, we can only use PostgREST and Realtime.

# However, we can use the pg-meta API which is bundled with Supabase
# Endpoint: GET/POST {SUPABASE_URL}/pg-meta/default/query

pg_meta_url = f"{SUPABASE_URL}/pg/query"
pg_headers = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
    "X-REQUEST-ID": "create-tables",
}

# Try the pg endpoint
create_providers_sql = """
DROP TABLE IF EXISTS quality_measures CASCADE;
DROP TABLE IF EXISTS deficiencies CASCADE;
DROP TABLE IF EXISTS providers CASCADE;

CREATE TABLE providers (
    federal_provider_number TEXT PRIMARY KEY,
    provider_name TEXT,
    city TEXT,
    state TEXT,
    overall_rating INTEGER,
    health_inspection_rating INTEGER,
    staffing_rating INTEGER,
    total_amount_of_fines_in_dollars FLOAT,
    number_of_facility_reported_incidents INTEGER
);

CREATE TABLE deficiencies (
    id SERIAL PRIMARY KEY,
    federal_provider_number TEXT REFERENCES providers(federal_provider_number),
    deficiency_description TEXT,
    deficiency_category TEXT,
    scope_severity_code TEXT,
    survey_date DATE
);

CREATE TABLE quality_measures (
    id SERIAL PRIMARY KEY,
    federal_provider_number TEXT REFERENCES providers(federal_provider_number),
    measure_description TEXT,
    score FLOAT,
    national_average FLOAT
);
"""

resp = requests.post(pg_meta_url, json={"query": create_providers_sql}, headers=pg_headers)
print(f"  Create tables response: {resp.status_code}")
if resp.status_code in (200, 201):
    print(f"  Tables created successfully!")
    print(f"  Response: {resp.text[:500]}")
else:
    print(f"  Response: {resp.text[:500]}")
    print("\n  Trying alternative pg endpoint...")

    # Try /pg-meta/default/query
    alt_url = f"{SUPABASE_URL}/pg-meta/default/query"
    resp = requests.post(alt_url, json={"query": create_providers_sql}, headers=pg_headers)
    print(f"  Alt endpoint response: {resp.status_code}")
    if resp.status_code in (200, 201):
        print(f"  Tables created via alt endpoint!")
    else:
        print(f"  Alt response: {resp.text[:500]}")

# Verify tables exist now
print("\n=== VERIFYING TABLES ===")
for table in ['providers', 'deficiencies', 'quality_measures']:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}?select=*&limit=1",
        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
    )
    print(f"  {table}: {resp.status_code} {'EXISTS' if resp.status_code == 200 else 'NOT FOUND'}")

# ── Step 2: Load data ───────────────────────────────────────────────────────
print("\n=== LOADING DATA ===")

def load_csv_to_supabase(csv_path, table_name, batch_size=500):
    """Load a CSV file into a Supabase table using REST API batch inserts."""
    df = pd.read_csv(csv_path)

    # Replace NaN with None for JSON serialization
    df = df.where(df.notna(), None)

    # For tables with serial 'id' column, don't include it
    if 'id' in df.columns:
        df = df.drop(columns=['id'])

    total = len(df)
    inserted = 0
    errors = 0

    print(f"\n  Loading {table_name}: {total:,} rows in batches of {batch_size}")

    for i in range(0, total, batch_size):
        batch = df.iloc[i:i+batch_size]
        records = batch.to_dict(orient='records')

        # Clean up None values for JSON
        for record in records:
            for key, val in record.items():
                if isinstance(val, float) and np.isnan(val):
                    record[key] = None

        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/{table_name}",
            json=records,
            headers=HEADERS
        )

        if resp.status_code in (200, 201):
            inserted += len(records)
        else:
            errors += 1
            if errors <= 3:
                print(f"    Error at batch {i//batch_size}: {resp.status_code} - {resp.text[:200]}")
            elif errors == 4:
                print(f"    (suppressing further error messages...)")

        if (i // batch_size) % 20 == 0:
            print(f"    Progress: {min(i+batch_size, total):,}/{total:,} ({min(100, (i+batch_size)*100//total)}%)")

    print(f"  {table_name}: {inserted:,} rows inserted, {errors} batch errors")
    return inserted

# Check if tables are accessible before loading
resp = requests.get(
    f"{SUPABASE_URL}/rest/v1/providers?select=*&limit=1",
    headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
)

if resp.status_code == 200:
    # Tables exist, load data
    # Load providers first (parent table)
    prov_count = load_csv_to_supabase(os.path.join(OUT, "providers_clean.csv"), "providers", batch_size=500)

    # Load deficiencies (references providers)
    defi_count = load_csv_to_supabase(os.path.join(OUT, "deficiencies_clean.csv"), "deficiencies", batch_size=500)

    # Load quality measures (references providers)
    qual_count = load_csv_to_supabase(os.path.join(OUT, "quality_measures_clean.csv"), "quality_measures", batch_size=500)

    # ── Step 3: Verify row counts ────────────────────────────────────────────
    print("\n=== VERIFYING ROW COUNTS ===")
    for table, expected in [('providers', 14713), ('deficiencies', 417293), ('quality_measures', 250121)]:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}?select=count",
            headers={
                "apikey": SERVICE_KEY,
                "Authorization": f"Bearer {SERVICE_KEY}",
                "Prefer": "count=exact",
            }
        )
        count = resp.headers.get('content-range', 'unknown')
        print(f"  {table}: {count} (expected ~{expected:,})")

    # ── Step 4: Run validation queries ───────────────────────────────────────
    print("\n=== VALIDATION QUERIES ===")

    # Query 1: State distribution
    print("\n  Query 1: Top 10 states by provider count")
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/providers?select=state&order=state",
        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
    )
    if resp.status_code == 200:
        data = resp.json()
        from collections import Counter
        state_counts = Counter(r['state'] for r in data)
        for state, count in state_counts.most_common(10):
            print(f"    {state}: {count}")

    # Query 2: Top deficiency categories
    print("\n  Query 2: Top 10 deficiency categories")
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/deficiencies?select=deficiency_category&limit=50000",
        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
    )
    if resp.status_code == 200:
        data = resp.json()
        cat_counts = Counter(r['deficiency_category'] for r in data)
        for cat, count in cat_counts.most_common(10):
            print(f"    {cat}: {count}")
    else:
        print(f"    Error: {resp.status_code}")

    # Query 3: Quality measures avg scores
    print("\n  Query 3: Sample quality measures with avg scores")
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/quality_measures?select=measure_description,score,national_average&limit=5",
        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
    )
    if resp.status_code == 200:
        data = resp.json()
        for r in data:
            desc = r['measure_description'][:60] if r['measure_description'] else 'N/A'
            print(f"    {desc}: score={r['score']}, nat_avg={r['national_average']:.2f}")
    else:
        print(f"    Error: {resp.status_code}")

else:
    print(f"\n  ERROR: Tables not accessible (status {resp.status_code})")
    print(f"  Response: {resp.text[:300]}")
    print("\n  Tables need to be created manually via Supabase Dashboard SQL Editor.")
    print("  SQL to run:")
    print(create_providers_sql)

print("\n=== DONE ===")
