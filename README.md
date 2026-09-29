# BrickJewels — FE Bar AI Build (D2C fine-jewelry, Growth Concierge)

An end-to-end, Databricks-native AI build for a **D2C fine-jewelry retailer**: one connected data
journey from governed data → an ML propensity model → a Gen AI agent → self-serve BI → an app, with
**AI Gateway** governing the app's Foundation Model usage. 100% synthetic data.

**Live app:** https://febar-concierge-4203758776894418.aws.databricksapps.com
**Catalog:** `anuj_vm_workspace_catalog`, schemas `febar_bronze / febar_silver / febar_gold / febar_ml`

## The six layers

| # | Layer | What it does | Where |
|---|-------|--------------|-------|
| 1 | **Lakeflow + Unity Catalog** | **Lakeflow Declarative Pipeline** — Auto Loader (`STREAM read_files`) over raw JSON in a UC Volume → Bronze → Silver (declarative DQ EXPECT + quarantine) → Gold materialized view. Plus UC governance: PII column masks + region row filter + Lakehouse Monitor | `01_lakeflow_uc/` |
| 2 | **Lakebase** | Reverse-ETL of model scores → Lakebase `febar_nbo_scores` (low-latency reads), OAuth credential | `02_lakebase/` |
| 3 | **ML** | Next-Best-Offer propensity (LightGBM → MLflow → UC `febar_ml.nbo_propensity`, Model Serving, SHAP, batch scores). **PR-AUC 0.837 vs 0.455 base** | `03_ml/` |
| 4 | **Gen AI Agent** | Claude + 6 governed UC-function tools (grounded, action-capable), GenAI eval | `04_agent/` |
| 5 | **Genie** | **Deployed Genie room** (space `01f1bc1f903f1fee81d4fcbd8d35b026`) over metric views (`mv_sales`, `mv_customer_propensity`); real Q&A transcript in `evidence/GENIE_TRANSCRIPT.md` | `05_genie/` |
| 6 | **Databricks App** | Growth Concierge — agent chat + customer-360/propensity/SHAP, integrates every layer | `06_app/` |

## AI Gateway (governs the app's FM usage)
`febar-claude-governed` endpoint (wraps the shared Claude FM endpoint) with **usage tracking +
inference tables + per-user rate limit (60/min) + PII guardrails (BLOCK)**. The app and agent route
all FM calls through it. Config: `resources/ai_gateway_config.json`.

## How to run / reproduce
1. **Layer 1 (Lakeflow):** land raw files into the `febar_bronze.landing` volume, then run the **Lakeflow Declarative Pipeline** `01_lakeflow_uc/lakeflow_pipeline.sql` (Auto Loader → bronze → silver DQ → gold). UC governance: `governance_and_silver.sql`; feature table for ML: `gold_customer_features.sql`.
2. **Layer 3:** run notebook `03_ml/training_dataset.sql` then `train_nbo_propensity.py` (serverless).
3. **Layer 4:** UC tools `04_agent/uc_function_tools.sql`; agent `04_agent/agent_local.py`; eval `eval_agent.py`.
4. **Layer 5:** `05_genie/metric_views.sql`; build the Genie room from `05_genie/seed_questions.md`.
5. **Layer 2:** `02_lakebase/reverse_etl_scores.py` (serverless).
6. **Layer 6:** deploy `06_app/` as a Databricks App (`app.yaml` sets warehouse + governed endpoint).

## Repo layout
```
01_lakeflow_uc/  lakeflow_pipeline.sql (Declarative Pipeline), gold_customer_features.sql, governance_and_silver.sql
02_lakebase/     reverse_etl_scores.py
03_ml/           training_dataset.sql, train_nbo_propensity.py
04_agent/        uc_function_tools.sql, agent_local.py, eval_agent.py
05_genie/        metric_views.sql, kpi_views.sql, seed_questions.md
06_app/          app.py, app.yaml, requirements.txt   (deployed = febar-concierge)
resources/       ai_gateway_config.json
evidence/        EXECUTION_EVIDENCE.md (text run output), GENIE_TRANSCRIPT.md, agent_eval.json, gen_execution_evidence.py
deck.md          two-persona (CFO + growth lead) outcome-led deck  →  BrickJewels_FEBar_Overview.pdf
BUILD.md         AI-assisted workflow & key decisions
```

## Data safety
100% synthetic / scraped-public product data; no real customer data. PII masked in UC; PII guardrails
block PII at the gateway; credentials are not committed.
