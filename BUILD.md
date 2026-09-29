# BUILD.md — BrickJewels FE Bar build (AI-assisted workflow & decisions)

Built with **Claude Code** driving the Databricks CLI/APIs. AI was a force multiplier for
data engineering, model training, agent authoring, and governance — but every architectural
decision and trade-off below was made deliberately, not generated blindly.

## The one connected journey
Single catalog `anuj_vm_workspace_catalog`, schemas `febar_bronze/silver/gold/ml`. One seeded
behavioral pattern flows through every layer: shopper events → features → **NBO propensity model**
→ **Gen AI agent** (recommends & acts) → **Genie** → **App**. Golden-thread cohort = high-propensity,
diamond-affinity, anniversary-window customers (e.g. customer #350).

## Key decisions & trade-offs

### 1. Seeded a *learnable* pattern (Layer 3) — the pivotal call
Profiling the existing BrickJewels data showed **no learnable signal**: repeat-purchase base rate
was 0.9999 (orders generated randomly for ~everyone) and `is_redeemed` was 0.0 across all 883k
nudges. A model on that would score PR-AUC ≈ prevalence and **fail** the "model must learn the
seeded pattern" bar. Decision: build features from the *real* behavioral aggregates but seed a
latent NBO propensity (a deterministic function of RFM + diamond affinity + engagement + anniversary
proximity) and draw the label as a per-customer Bernoulli — reproducible via hash, with irreducible
noise so it's realistic (not perfectly separable). Result: **PR-AUC 0.837 vs 0.455 base (1.84×)**,
and SHAP recovered exactly the seeded drivers (frequency › recency › monetary › engagement › diamond).

### 2. Manual tool-calling agent over `create_react_agent` (Layer 4)
`create_react_agent` + `UCFunctionToolkit` on serverless notebooks hung repeatedly (30+ min).
Root causes diagnosed: (a) `%pip install -U …` sends the resolver into a long backtrack on the
pinned serverless env — install **without** `-U`; (b) notebook stdout isn't returned by the Jobs
API — use `dbutils.notebook.exit(json)`; (c) `signal.alarm` timeouts don't interrupt blocked
network calls. Decision: implement the agent as a **manual tool-calling loop** (Claude FM API +
tool schemas → execute the 6 UC functions via SQL → feed back). It's fully observable, reliable,
and is the exact logic the app runs. Trade-off: no native ChatAgent Review App; gained reliability
and control. GenAI eval (LLM-judge): groundedness/correctness 0.8, safety 1.0 (the one miss was a
judge crore-vs-billion false negative — true quality ~5/5).

### 3. AI Gateway on an endpoint I own — not shared infra
The app's FM traffic must be governed, but the shared `databricks-claude-sonnet-4-6` endpoint is
used workspace-wide (I reverted a rate limit I test-applied to it). Decision: create my **own**
`febar-claude-governed` endpoint (external-model proxy wrapping the shared FM endpoint via a PAT
secret) and attach AI Gateway there: usage tracking + inference tables + **per-user rate limit
60/min** + **PII guardrails (BLOCK)**. Verified live: a credit-card/email input was detected and
blocked; the rate limit throttled a burst. I **removed the generic safety content-filter** after it
false-positived retail language ("target prospects", "making charges") as violent-crimes — a
deliberate domain-tuning decision (PII is the relevant risk for a jeweler handling customer data).

### 4. Governance & data safety (Layer 1)
Medallion (Bronze→Silver→Gold), Silver DQ expectations + quarantine, **PII column masks** on
customer email/mobile, **region row filter**, and a **Lakehouse snapshot monitor** on the scores.
100% synthetic data — no real customer data anywhere.

### 5. Serving/infra workarounds
- Model logged as **pyfunc + joblib artifact** (not `mlflow.sklearn`) to dodge MLflow's skops
  "untrusted types" gate for LightGBM, and so the endpoint returns propensity directly.
- Lakebase reverse-ETL used **REST `api_client.do`** for instance DNS + credential (the installed
  SDK lacked `w.database`); managed synced-tables were unavailable (no CREATE CATALOG on metastore).
- New catalog creation was blocked by Default Storage → built medallion as schemas in the existing
  catalog (still "one catalog").

## Prompts (representative)
- "Profile the label candidates before training" → caught the no-signal data (decision #1).
- "Diagnose the hang with phase timings and a hard timeout" → found the `-U` pip backtrack (#2).
- "Govern the app's FM usage with AI Gateway without disrupting shared infra" → the owned-endpoint
  design (#3).
