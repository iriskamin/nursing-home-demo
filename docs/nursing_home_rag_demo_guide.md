# NURSING HOME RAG DEMO
## Complete Build Guide: From Data Download to Live Testing
**Stack: Dify.ai · Supabase · Langfuse · CMS Open Data**

---

## Project Overview

This guide walks you through building a no-code AI demo that showcases the power of combining three retrieval modes: vector search, keyword search, and direct SQL queries. The domain is nursing home quality data from CMS — real, publicly available, emotionally resonant, and perfectly structured to demonstrate why hybrid search matters.

### Architecture at a Glance

| Component | Tool | Purpose | Cost |
|---|---|---|---|
| Data Source | CMS data.cms.gov | 3 free CSVs, CC0 license | Free |
| Database | Supabase | PostgreSQL + REST API for SQL queries | Free tier |
| RAG + Workflow | Dify.ai | Hybrid search + workflow orchestration | Free tier |
| Observability | Langfuse | Tracing, evals, LLM monitoring | Free tier |
| LLM | Claude Sonnet / GPT-4o | Query routing + answer generation | Pay per use |

### The Three Query Types Your Demo Will Handle

**💬 Pure Semantic (Vector) Search**
> User asks: "Find facilities where residents felt emotionally neglected"
> → No exact keyword exists for this concept. The LLM embeds the query and finds semantically similar passages in inspector narratives.

**🔤 Pure Keyword (BM25) Search**
> User asks: "Find deficiency reports mentioning elopement or wandering"
> → These are precise clinical terms. BM25 finds exact matches that semantic search might dilute or miss entirely.

**🗄️ Pure SQL Query**
> User asks: "Show me 5-star facilities in Florida with fewer than 3 penalties"
> → Pure structured filtering. No text search needed — the LLM writes SQL against your Supabase tables.

**⚡ Hybrid Query (Your Best Demo Moment)**
> User asks: "Find nursing homes in California with memory care violations, rated below 3 stars, with more than 5 deficiencies in the last 2 years"
> → "memory care violations" hits vector search over narratives
> → "below 3 stars" and "5 deficiencies" hits SQL — impossible to answer well without both

---

## Phase 1 — Data Download & Preparation
**~1-2 hours · No tools required**

### Step 1.1 — Download the Three CMS Datasets

Go to each URL below and click the CSV Download button. No account required.

| Dataset | URL | Save As |
|---|---|---|
| Provider Info (Facility metadata) | data.cms.gov/provider-data/dataset/4pq5-n9py | providers.csv |
| Health Deficiencies (Narrative inspection text) | data.cms.gov/provider-data/dataset/r5ix-sfxw | deficiencies.csv |
| Quality Measures (Numeric scores) | data.cms.gov/provider-data/dataset/djen-97ju | quality_measures.csv |

> **💡 Tip:** The Health Deficiencies dataset is the most important for your demo — it contains inspector narrative text like "staff failed to reposition resident resulting in stage 3 pressure ulcer". This is what makes vector search come alive. The common linking key across all 3 files is: `federal_provider_number`

### Step 1.2 — Key Columns to Know

| Column Name | Dataset & Description |
|---|---|
| federal_provider_number | All 3 datasets — the primary key linking everything |
| provider_name, city, state | providers.csv — facility identity and location |
| overall_rating (1-5) | providers.csv — the Five Star rating |
| total_amount_of_fines_in_dollars | providers.csv — financial penalties |
| deficiency_description | deficiencies.csv — YOUR VECTOR SEARCH TARGET |
| deficiency_category | deficiencies.csv — category tag for keyword search |
| survey_date | deficiencies.csv — for date-based SQL filtering |
| measure_description | quality_measures.csv — human-readable measure name |
| score | quality_measures.csv — facility's score on that measure |
| national_average | quality_measures.csv — for comparison SQL queries |

---

## Phase 2 — Supabase Setup
**~1 hour · Database for SQL queries**

### Step 2.1 — Create Your Supabase Account

1. Go to supabase.com and click Start for free
2. Sign up with GitHub (recommended) or email
3. Click New Project — name it `nursing-home-demo`
4. Choose a region closest to you, set a database password, save it
5. Wait ~2 minutes for the project to spin up

### Step 2.2 — Import the CSV Files

Supabase has a built-in CSV importer. For each of your 3 files:

1. In the left sidebar, click Table Editor
2. Click New Table → name it `providers` (then repeat for `deficiencies` and `quality_measures`)
3. Click Import data from CSV
4. Upload your CSV file — Supabase will auto-detect columns and types
5. Click Save

> **⚠️ Important — Fix Column Types After Importing**
> - `overall_rating` → int4 (integer)
> - `score`, `national_average` → float8 (decimal)
> - `survey_date` → date
> - `total_amount_of_fines_in_dollars` → float8
> - `federal_provider_number` → text (NOT integer — it has leading zeros)

### Step 2.3 — Get Your Supabase API Credentials

1. In the left sidebar, click Project Settings → API
2. Copy and save:
   - **Project URL** — looks like: `https://abcdefgh.supabase.co`
   - **anon public key** — long JWT string starting with `eyJ...`
   - **service_role key** — needed for Claude Code to create tables programmatically

### Step 2.4 — Test the REST API

Open your browser and visit (replace with your values):
```
https://YOUR_PROJECT_ID.supabase.co/rest/v1/providers?select=*&limit=3
```
Add header: `apikey: YOUR_ANON_KEY` — you should see JSON rows returned.

---

## Phase 3 — Dify.ai Setup & Knowledge Base
**~2 hours · The RAG + workflow engine**

### Step 3.1 — Create Your Dify Account

1. Go to dify.ai and click Get Started
2. Sign up and log in
3. You'll land on the Studio dashboard

### Step 3.2 — Create the Knowledge Base (Hybrid Search)

1. In the top navigation, click **Knowledge**
2. Click **Create Knowledge** → name it `Nursing Home Deficiencies`
3. Click **Upload Files** → upload your `deficiencies.csv`
4. In Indexing Mode, select **High Quality** (uses embeddings)
5. In Retrieval Settings, select **Hybrid Search** — enables both vector and BM25 simultaneously
6. Set Chunk Size to **500 tokens**, Overlap to **50**
7. Click **Save and Process** — Dify will embed all narratives (takes 5-15 min)

> **💡 Why These Chunk Settings**
> 500 tokens is roughly 2-3 inspection narrative paragraphs — enough context without being too broad. The 50-token overlap ensures no narrative gets cut off at chunk boundaries.

### Step 3.3 — Add Supabase as a Custom Tool

1. Click your avatar (top right) → Settings → Tools → Custom Tools
2. Click **Add Custom Tool**, name it `Supabase SQL Tool`
3. In Schema, paste this OpenAPI spec (replace YOUR_PROJECT_ID):

```yaml
openapi: 3.0.0
info:
  title: Supabase Nursing Home Query
  version: 1.0.0
servers:
  - url: https://YOUR_PROJECT_ID.supabase.co/rest/v1
paths:
  /providers:
    get:
      operationId: query_providers
      summary: Query nursing home facility data
      parameters:
        - name: select
          in: query
          schema: { type: string }
        - name: state
          in: query
          schema: { type: string }
        - name: overall_rating
          in: query
          schema: { type: string }
        - name: limit
          in: query
          schema: { type: integer }
      responses:
        '200': { description: Array of nursing home facilities }
  /deficiencies:
    get:
      operationId: query_deficiencies
      summary: Query inspection deficiency records
      parameters:
        - name: select
          in: query
          schema: { type: string }
        - name: federal_provider_number
          in: query
          schema: { type: string }
        - name: limit
          in: query
          schema: { type: integer }
      responses:
        '200': { description: Array of deficiency records }
  /quality_measures:
    get:
      operationId: query_quality_measures
      summary: Query quality measure scores
      parameters:
        - name: select
          in: query
          schema: { type: string }
        - name: federal_provider_number
          in: query
          schema: { type: string }
        - name: limit
          in: query
          schema: { type: integer }
      responses:
        '200': { description: Array of quality measure records }
```

4. In Authentication, select **API Key** → header name: `apikey` → value: your Supabase anon key
5. Click Test → should return JSON → Click Save

---

## Phase 4 — Build the Dify Workflow
**~2-3 hours · The core AI logic**

### Step 4.1 — Create a New Chatflow

1. From Dify dashboard, click Studio → Create App
2. Select **Chatflow** (not Agent or Completion)
3. Name it: `Nursing Home Assistant`
4. Click Create

### Step 4.2 — The System Prompt (Schema Grounding)

Click the system prompt field and paste exactly this:

```
You are an expert assistant helping users search and analyze US nursing home data.
You have access to three retrieval methods and must choose the right one:

1. KNOWLEDGE BASE (Hybrid Search) — use for:
   - Conceptual or qualitative questions about care quality
   - Finding specific types of violations or incidents
   - Questions using descriptive language like 'emotional neglect', 'unsafe conditions'

2. SUPABASE SQL TOOL — use for:
   - Filtering by state, city, star rating, penalty counts, dates
   - Counting, ranking, or comparing facilities numerically
   - Any question with numbers, thresholds, or geographic filters

3. BOTH — use for hybrid queries that combine qualitative concepts with numeric filters

DATABASE SCHEMA (for SQL queries):

TABLE: providers
  federal_provider_number TEXT (primary key)
  provider_name TEXT
  city TEXT
  state TEXT (2-letter code, e.g. 'FL', 'CA')
  overall_rating INTEGER (1-5, Five Star rating)
  health_inspection_rating INTEGER (1-5)
  staffing_rating INTEGER (1-5)
  total_amount_of_fines_in_dollars FLOAT
  number_of_facility_reported_incidents INTEGER

TABLE: deficiencies
  federal_provider_number TEXT (foreign key → providers)
  deficiency_description TEXT (inspector narrative — searched via Knowledge Base)
  deficiency_category TEXT
  scope_severity_code TEXT
  survey_date DATE

TABLE: quality_measures
  federal_provider_number TEXT (foreign key → providers)
  measure_description TEXT
  score FLOAT
  national_average FLOAT

SUPABASE API FILTER SYNTAX:
- Equals: column=eq.VALUE
- Greater than: column=gt.VALUE
- Less than: column=lt.VALUE
- Text search: column=like.*TERM*
- Always include select=* or specific columns
- Always add limit=20 unless user asks for more

RESPONSE FORMAT:
- Always cite which retrieval method(s) you used and why
- Include facility name, location, and key finding for each result
- If combining methods, clearly show what each method contributed
- Only mention facilities that appear in retrieved results — do not invent any data
- If no results found, explain why and suggest a refined query
```

### Step 4.3 — Build the Workflow Nodes

**Node 1 — Start Node**
Already exists. No changes needed.

**Node 2 — LLM Node: Query Classifier**
- Add an LLM node. Model: Claude Sonnet or GPT-4o. Max tokens: 10
- Prompt:
```
Classify this user query. Output ONLY one of: SQL, VECTOR, HYBRID

Query: {{#sys.query#}}
```

**Node 3 — Condition Node: Route the Query**
Add an IF/ELSE node with 3 branches:
- Branch A: classifier output contains `SQL` → Supabase Tool node
- Branch B: classifier output contains `VECTOR` → Knowledge Retrieval node
- Branch C: classifier output contains `HYBRID` → BOTH nodes in parallel

**Node 4 — Knowledge Retrieval Node**
- Knowledge Base: `Nursing Home Deficiencies`
- Query variable: `{{#sys.query#}}`
- Top K: 5
- Score threshold: 0.5

**Node 5 — Supabase Tool Node**
- Add a Tool node → select `Supabase SQL Tool`
- Wrap in an Agent node so the LLM decides which endpoint and parameters to use
- The system prompt's schema grounding guides parameter generation automatically

**Node 6 — Final LLM Node: Answer Synthesizer**
- Receives outputs from all active branches
- Prompt:
```
User question: {{#sys.query#}}

Knowledge base results: {{#knowledge.result#}}

SQL results: {{#tool.output#}}

Synthesize a clear, helpful answer. Cite which retrieval method(s) you used and why.
Only mention facilities that appear in the retrieved results — do not invent any names or data.
```

---

## Phase 5 — Langfuse Integration
**~45 minutes · Observability & tracing**

### Step 5.1 — Create Your Langfuse Account

1. Go to langfuse.com → Sign up for free
2. Create a new project: `nursing-home-demo`
3. Go to Settings → API Keys → Create new API key pair
4. Save your **Public Key** and **Secret Key**

### Step 5.2 — Connect Langfuse to Dify

1. In Dify, click your avatar → Settings → **Monitoring**
2. Click **Add monitoring** → select **Langfuse**
3. Fill in:
   - Host: `https://cloud.langfuse.com`
   - Public Key: paste from Langfuse
   - Secret Key: paste from Langfuse
4. Click **Save and Test Connection** — green checkmark = success
5. Enable monitoring and click Save

> **✅ What Gets Traced Automatically**
> - Full LLM input/output for every node
> - Token usage and cost per node
> - Latency for each step
> - Which retrieval branch was triggered
> - The final answer and any errors

### Step 5.3 — Add Custom Metadata for Better Tracing

In your classifier LLM node in Dify, add this to the metadata field:

```json
{
  "project": "nursing-home-demo",
  "retrieval_type": "{{#classifier.output#}}",
  "user_query_length": "{{#sys.query.length#}}"
}
```

### Step 5.4 — Set Up Langfuse Dashboards

1. **Traces view** — full node-by-node breakdown of every conversation
2. **Metrics** → chart: Average latency by `retrieval_type` tag
3. **Metrics** → chart: Token cost per query over time
4. **Sessions** → group traces by conversation for multi-turn patterns

---

## Phase 6 — Evaluation Framework

### Step 6.1 — Golden Test Set (15 queries)

Save as `golden_test_set.csv`:

| Query | Expected Type | Expected Result Contains | Pass Criteria |
|---|---|---|---|
| Find all facilities in TX with overall_rating < 2 | SQL | Texas facilities, low ratings | Returns structured list |
| Show CA nursing homes with fines > $50,000 | SQL | California, fine amounts | Correct SQL filter applied |
| Which states have the most deficiencies in 2023? | SQL | State ranking with counts | Aggregation correct |
| List the 10 lowest rated facilities in New York | SQL | NY facilities ranked | Correct ordering |
| Find facilities with zero penalties in the last year | SQL | Clean facilities | Date filter works |
| Find reports mentioning resident falls | VECTOR | Fall-related narratives | Semantically relevant chunks |
| Facilities where residents felt emotionally neglected | VECTOR | Neglect-related narratives | Captures concept not keyword |
| Poor hygiene or unsanitary conditions in inspections | VECTOR | Hygiene violation narratives | Finds related language |
| Facilities with inadequate dementia care | VECTOR | Dementia care narratives | Semantic match works |
| Inspections where staff were verbally abusive | VECTOR | Abuse narratives | Finds emotional language |
| Find elopement incidents reported in 2023 | KEYWORD | Elopement exact matches | Exact term found |
| Reports citing scope severity code J or K | KEYWORD | Severity code matches | Exact code matched |
| Memory care facilities below 3 stars in FL | HYBRID | FL + low rating + memory care | Both SQL + vector used |
| Understaffed California homes with abuse reports | HYBRID | CA + staffing + abuse narratives | Both retrievals combined |
| High fine facilities in Texas with fall violations | HYBRID | TX + fines + fall narratives | SQL filters + vector retrieves |

### Step 6.2 — Classifier Accuracy

Target: **> 85% accuracy**

1. Run all 15 queries through your app
2. In Langfuse, check the classifier node output for each trace
3. Compare to Expected Type column
4. Score: Correct / 15

If below 85%, add few-shot examples to the classifier prompt.

### Step 6.3 — Retrieval Quality Metrics

| Metric | Target | How to Measure |
|---|---|---|
| Relevance@5 | > 3/5 relevant | For each VECTOR query, manually score top 5 returned chunks |
| SQL correctness | > 90% | Verify returned facilities actually match filter criteria |
| Hybrid completeness | 100% | All HYBRID responses show evidence of both retrieval methods |
| Faithfulness | > 0.8 | LLM-as-judge in Langfuse Evals |

### Step 6.4 — Langfuse Score Types to Create

Go to Langfuse → project Settings → Scores → add these:

| Score Name | Scale | Measures |
|---|---|---|
| faithfulness | 0-1 | Answer only uses retrieved content (no hallucination) |
| relevance | 0-1 | Answer addresses the user's actual question |
| retrieval_mode_correct | 0 or 1 | Used the right retrieval method |
| sql_accuracy | 0 or 1 | SQL filter returned correct results |
| answer_completeness | 0-1 | Captured all key findings from retrieved content |

> **🤖 Automated LLM-as-Judge**
> Langfuse → Evals → Create Eval Template → select 'Hallucination' or 'Relevance'
> Langfuse runs an LLM judge against your traces automatically.
> Run after every workflow change to catch regressions.

### Step 6.5 — A/B Testing

1. Duplicate your chatflow in Dify → name it `v2`
2. Change one variable (Top K, chunk size, classifier prompt, etc.)
3. Run all 15 golden queries against both versions
4. Compare average Langfuse scores between versions
5. Keep whichever scores better on faithfulness + relevance

### Step 6.6 — Stakeholder Metrics Summary

| Metric | Target | Where to Find |
|---|---|---|
| Classifier accuracy | > 85% | Manual check vs. golden set |
| Vector relevance@5 | > 3/5 | Manual scoring in Langfuse |
| SQL correctness | > 90% | Manual result verification |
| Faithfulness | > 0.8 | Langfuse LLM-as-judge |
| Avg. latency | < 8 seconds | Langfuse Metrics tab |
| Cost per query | Track trend | Langfuse token tracking |

---

## Phase 7 — Testing Your Demo
**~1 hour · Go live and validate**

### Step 7.1 — Publish Your Dify App

1. In Dify, click **Publish** → **Web App**
2. Toggle public access → copy the shareable URL
3. Open in a new browser tab — this is your demo interface

### Step 7.2 — The Demo Script (8 queries in order)

**Query 1 — Pure SQL (warm up)**
```
Show me all 5-star nursing homes in Texas
```

**Query 2 — Pure SQL with aggregation**
```
Which state has the highest average number of fines?
```

**Query 3 — Pure Keyword**
```
Find inspection reports that mention elopement
```

**Query 4 — Pure Vector (the wow moment)**
```
Find facilities where residents felt like they had no dignity
```

**Query 5 — Vector shows its gap**
```
Find reports mentioning F-tag F684
```
Show audience how exact codes need keyword search, not semantic.

**Query 6 — Hybrid (the main event)**
```
Find nursing homes in California with memory care problems, rated below 3 stars
```

**Query 7 — Complex Hybrid**
```
What are the most common safety violations in Florida's lowest-rated facilities?
```

**Query 8 — Live Langfuse walkthrough**
After Query 7, switch to Langfuse and show the trace live:
- Classifier node output
- Which retrieval branch fired
- Token cost and latency per node
- The synthesized answer

### Step 7.3 — Common Issues & Fixes

| Problem | Fix |
|---|---|
| Classifier always returns VECTOR | Add few-shot SQL and HYBRID examples to classifier prompt |
| SQL queries return no results | Verify Supabase column names exactly match system prompt schema |
| Vector results irrelevant | Lower score threshold from 0.5 to 0.3, or increase Top K to 8 |
| Langfuse not receiving traces | Re-check API keys in Dify Settings → Monitoring, no trailing spaces |
| Hybrid only uses one method | Verify HYBRID branch connects to BOTH retrieval nodes |
| Answers hallucinate facility names | Add to system prompt: "Only mention facilities in retrieved results" |

---

## Quick Reference Summary

| Phase | What You Do | Time | Output |
|---|---|---|---|
| 1 — Data | Download 3 CMS CSVs | 30 min | providers.csv, deficiencies.csv, quality_measures.csv |
| 2 — Supabase | Import CSVs, get credentials | 60 min | Live PostgreSQL DB with REST API |
| 3 — Dify KB | Upload deficiencies, enable hybrid search | 60 min | Indexed knowledge base with vector+BM25 |
| 4 — Workflow | Build classifier + retrieval + synthesis nodes | 2-3 hrs | Working chatflow with 3 retrieval modes |
| 5 — Langfuse | Connect monitoring, add trace metadata | 45 min | Full observability dashboard |
| 6 — Evaluation | Run golden test set, score with LLM judge | 2 hrs | Accuracy metrics + A/B test results |
| 7 — Testing | Publish, run demo script, fix issues | 60 min | Shareable demo URL |

**Total: 8-12 hours across 2-3 days. No code required.**

---

*Built with CMS Open Data · CC0 License · No scraping required*