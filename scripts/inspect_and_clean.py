"""
Step 1: Inspect and clean the 3 CMS nursing home datasets.
"""
import pandas as pd
import numpy as np
import os
import sys

# Fix Windows encoding
sys.stdout.reconfigure(encoding='utf-8')

BASE = r"C:\Users\irisk\OneDrive\Antigravity\nursing-home-demo"
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "outputs")
os.makedirs(OUT, exist_ok=True)

# Load raw CSVs
print("Loading CSVs...")
prov_raw = pd.read_csv(os.path.join(DATA, "providers.csv"), dtype=str, low_memory=False)
defi_raw = pd.read_csv(os.path.join(DATA, "deficiencies.csv"), dtype=str, low_memory=False)
qual_raw = pd.read_csv(os.path.join(DATA, "quality_measures.csv"), dtype=str, low_memory=False)

print(f"  providers raw: {len(prov_raw):,} rows, {len(prov_raw.columns)} cols")
print(f"  deficiencies raw: {len(defi_raw):,} rows, {len(defi_raw.columns)} cols")
print(f"  quality_measures raw: {len(qual_raw):,} rows, {len(qual_raw.columns)} cols")

# ── PROVIDERS ────────────────────────────────────────────────────────────────
print("\n=== CLEANING PROVIDERS ===")

prov_rename = {
    'CMS Certification Number (CCN)': 'federal_provider_number',
    'Provider Name': 'provider_name',
    'City/Town': 'city',
    'State': 'state',
    'Overall Rating': 'overall_rating',
    'Health Inspection Rating': 'health_inspection_rating',
    'Staffing Rating': 'staffing_rating',
    'Total Amount of Fines in Dollars': 'total_amount_of_fines_in_dollars',
    'Number of Facility Reported Incidents': 'number_of_facility_reported_incidents',
}

prov = prov_raw[list(prov_rename.keys())].rename(columns=prov_rename).copy()

# Strip whitespace from all text columns
for col in prov.select_dtypes(include='object').columns:
    prov[col] = prov[col].str.strip()

# Preserve leading zeros in federal_provider_number (should be 6 chars)
prov['federal_provider_number'] = prov['federal_provider_number'].str.zfill(6)

# Convert types
for col in ['overall_rating', 'health_inspection_rating', 'staffing_rating', 'number_of_facility_reported_incidents']:
    prov[col] = pd.to_numeric(prov[col], errors='coerce').astype('Int64')

prov['total_amount_of_fines_in_dollars'] = pd.to_numeric(
    prov['total_amount_of_fines_in_dollars'].str.replace('$', '', regex=False).str.replace(',', '', regex=False),
    errors='coerce'
)

# Remove empty rows and rows without provider number
before = len(prov)
prov = prov.dropna(how='all')
prov = prov.dropna(subset=['federal_provider_number'])
prov = prov.drop_duplicates(subset=['federal_provider_number'], keep='first')
after = len(prov)
print(f"  Rows: {before:,} -> {after:,} (removed {before-after:,})")
print(f"  Columns: {list(prov.columns)}")
print(f"  Dtypes:\n{prov.dtypes.to_string()}")
print(f"  Null %:")
for col in prov.columns:
    pct = prov[col].isnull().mean() * 100
    print(f"    {col}: {pct:.1f}%")

# ── DEFICIENCIES ─────────────────────────────────────────────────────────────
print("\n=== CLEANING DEFICIENCIES ===")

defi_rename = {
    'CMS Certification Number (CCN)': 'federal_provider_number',
    'Deficiency Description': 'deficiency_description',
    'Deficiency Category': 'deficiency_category',
    'Scope Severity Code': 'scope_severity_code',
    'Survey Date': 'survey_date',
}

defi = defi_raw[list(defi_rename.keys())].rename(columns=defi_rename).copy()

for col in defi.select_dtypes(include='object').columns:
    defi[col] = defi[col].str.strip()

defi['federal_provider_number'] = defi['federal_provider_number'].str.zfill(6)
defi['survey_date'] = pd.to_datetime(defi['survey_date'], errors='coerce').dt.date

before = len(defi)
defi = defi.dropna(how='all')
defi = defi.dropna(subset=['federal_provider_number'])
after = len(defi)
print(f"  Rows: {before:,} -> {after:,} (removed {before-after:,})")
print(f"  Columns: {list(defi.columns)}")
print(f"  Dtypes:\n{defi.dtypes.to_string()}")
print(f"  Null %:")
for col in defi.columns:
    pct = defi[col].isnull().mean() * 100
    print(f"    {col}: {pct:.1f}%")

# ── QUALITY MEASURES ─────────────────────────────────────────────────────────
print("\n=== CLEANING QUALITY MEASURES ===")

# Use four_quarter_average_score as "score", compute national_average per measure
qual_rename = {
    'CMS Certification Number (CCN)': 'federal_provider_number',
    'Measure Description': 'measure_description',
    'Four Quarter Average Score': 'score',
}

qual = qual_raw[list(qual_rename.keys())].rename(columns=qual_rename).copy()

for col in qual.select_dtypes(include='object').columns:
    qual[col] = qual[col].str.strip()

qual['federal_provider_number'] = qual['federal_provider_number'].str.zfill(6)
qual['score'] = pd.to_numeric(qual['score'], errors='coerce')

before = len(qual)
qual = qual.dropna(how='all')
qual = qual.dropna(subset=['federal_provider_number'])
after = len(qual)
print(f"  Rows: {before:,} -> {after:,} (removed {before-after:,})")

# Compute national_average per measure
nat_avg = qual.groupby('measure_description')['score'].mean().reset_index()
nat_avg.columns = ['measure_description', 'national_average']
qual = qual.merge(nat_avg, on='measure_description', how='left')

print(f"  Final rows (with national_average): {len(qual):,}")
print(f"  Columns: {list(qual.columns)}")
print(f"  Dtypes:\n{qual.dtypes.to_string()}")
print(f"  Null %:")
for col in qual.columns:
    pct = qual[col].isnull().mean() * 100
    print(f"    {col}: {pct:.1f}%")

# ── SAVE ─────────────────────────────────────────────────────────────────────
print("\n=== SAVING CLEANED CSVs ===")
prov.to_csv(os.path.join(OUT, "providers_clean.csv"), index=False)
defi.to_csv(os.path.join(OUT, "deficiencies_clean.csv"), index=False)
qual.to_csv(os.path.join(OUT, "quality_measures_clean.csv"), index=False)

print(f"  providers_clean.csv:        {len(prov):,} rows")
print(f"  deficiencies_clean.csv:     {len(defi):,} rows")
print(f"  quality_measures_clean.csv: {len(qual):,} rows")

# ── SAMPLES ──────────────────────────────────────────────────────────────────
print("\n=== SAMPLE DATA ===")
print("\nProviders (first 3):")
print(prov.head(3).to_string(max_colwidth=40))
print("\nDeficiencies (first 3):")
print(defi.head(3).to_string(max_colwidth=60))
print("\nQuality Measures (first 3):")
print(qual.head(3).to_string(max_colwidth=60))

print("\n=== DONE ===")
