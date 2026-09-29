# BrickJewels FE Bar — Execution Evidence (text)

> **What this is.** The FE Bar evaluator reads text only and requires the *output
> itself* committed to the repo (query results, model output), not screenshots.
> Every block below is a real read-only query run against the live build on the
> AWS FE VM workspace (catalog `anuj_vm_workspace_catalog`, schemas `febar_bronze/silver/gold/ml`)
> and its captured output. Regenerate with `python3 evidence/gen_execution_evidence.py`.

- **Workspace:** AWS FE VM (`fe-vm-anuj-vm-workspace`)  ·  **Warehouse:** `0f16ae8ffb7cdef3`
- **Captured:** 2026-09-29 20:08

---

## Layer 1 — Lakeflow + Unity Catalog (medallion, DQ, governance)

### Gold customer_features — row count

```sql
SELECT COUNT(*) AS total_customers FROM febar_gold.customer_features
```

| total_customers |
| --- |
| 23391 |


### Gold customer_features — sample rows (RFM + affinity features)

```sql
SELECT user_id, recency_days, frequency, monetary_total, aov, diamond_share, cart_value, wishlist_count, days_to_anniversary, has_milestone FROM febar_gold.customer_features ORDER BY monetary_total DESC LIMIT 5
```

| user_id | recency_days | frequency | monetary_total | aov | diamond_share | cart_value | wishlist_count | days_to_anniversary | has_milestone |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 0 | 77 | 15114313 | 196289.78 | 0.6376 | 214899 | 5 | 365 | 0 |
| 23 | 5 | 77 | 14460580 | 187799.74 | 0.7297 | 251862 | 4 | 365 | 1 |
| 11 | 13 | 70 | 14457724 | 206538.91 | 0.7035 | 211828 | 5 | 365 | 0 |
| 6 | 32 | 77 | 14362465 | 186525.52 | 0.7047 | 237071 | 5 | 283 | 0 |
| 21 | 13 | 79 | 14345072 | 181583.19 | 0.7403 | 45855 | 5 | 365 | 0 |


### Silver data-quality — clean vs quarantined counts

DLT-style DQ expectations route rule violations to a quarantine table.

```sql
SELECT (SELECT COUNT(*) FROM febar_silver.orders_clean) AS orders_clean, (SELECT COUNT(*) FROM febar_silver.orders_quarantine) AS orders_quarantined
```

| orders_clean | orders_quarantined |
| --- | --- |
| 216485 | 0 |


### Governance — dim_customers with column masks + row filter applied

`dim_customers` carries `mask_email`/`mask_mobile` column masks and a region row filter (DDL in `01_lakeflow_uc/governance_and_silver.sql`).

```sql
SELECT COUNT(*) AS governed_customers FROM febar_gold.dim_customers
```

| governed_customers |
| --- |
| 6514 |


---

## Layer 3 — ML (Next-Best-Offer propensity model)

**Registered model:** `anuj_vm_workspace_catalog.febar_ml.nbo_propensity` v1 (LightGBM, MLflow → Unity Catalog).  **Serving endpoint:** `febar-nbo-propensity` (READY).

**Live serving-endpoint invocation** — real online prediction for customer `350` (a High-segment prospect), features pulled from `febar_ml.training_dataset`:

```json
// POST /serving-endpoints/febar-nbo-propensity/invocations
{"dataframe_split": {"columns": ["recency_days","tenure_days","frequency",
  "monetary_total","aov","avg_item_count","total_items","distinct_categories",
  "diamond_share","gold_share","cart_adds","cart_value","wishlist_count",
  "wishlist_value","days_to_anniversary","days_to_birthday","has_milestone"],
  "data": [[2.0,91.0,46.0,7261396.0,157856.43,1.826,84.0,6.0,0.7976,0.9643,
            2.0,244617.0,4.0,137966.0,6.0,365.0,0.0]]}}
// response:
{"predictions": [0.999254469090458]}
```

> The online endpoint returns `0.9993` for user 350 — identical to the batch score and the `get_top_prospects` tool output below, i.e. the real-time, batch, and agent-tool paths all agree.

**MLflow run metrics** (run `4ac55a76e1dd47139a05f1f32ea456d1`):

| metric | value |
| --- | --- |
| pr_auc | 0.8367 |
| roc_auc | 0.8541 |
| precision_at_decile | 0.9692 |
| lift_at_decile | 2.13 |
| brier | 0.1546 |
| base_rate | 0.4550 |

> PR-AUC 0.837 vs base rate 0.455 — the model materially beats prevalence; top-decile precision 0.969.

### Batch model output — score-segment distribution (real inference committed to Gold)

```sql
SELECT segment, COUNT(*) AS customers, ROUND(AVG(propensity_score),4) AS avg_score FROM febar_gold.customer_nbo_scores GROUP BY segment ORDER BY avg_score DESC
```

| segment | customers | avg_score |
| --- | --- | --- |
| High | 4678 | 0.9181 |
| Medium | 9356 | 0.5494 |
| Low | 9357 | 0.1251 |


### SHAP feature importance — what drives the score

```sql
SELECT feature, ROUND(mean_abs_shap,4) AS mean_abs_shap FROM febar_gold.nbo_feature_importance ORDER BY mean_abs_shap DESC LIMIT 10
```

| feature | mean_abs_shap |
| --- | --- |
| frequency | 0.5857 |
| recency_days | 0.5333 |
| monetary_total | 0.347 |
| wishlist_count | 0.3092 |
| cart_adds | 0.2317 |
| diamond_share | 0.1968 |
| tenure_days | 0.1754 |
| cart_value | 0.1603 |
| total_items | 0.1397 |
| wishlist_value | 0.1292 |


---

## Layer 4 — Gen AI Agent (governed UC-function tools + eval)

**6 governed UC-function tools** in `febar_ml`: `get_customer_propensity`, `get_customer_profile`, `recommend_next_best_offer`, `get_top_prospects`, `search_products`, `get_category_performance`.

**Governed LLM endpoint:** `febar-claude-governed` (READY) — AI Gateway usage tracking + inference tables + rate limit + PII guardrail.

### Live UC-function tool call — get_top_prospects('High', 5)

The agent's tools are real, executable UC functions — here is one returning live output.

```sql
SELECT * FROM febar_ml.get_top_prospects('High', 5)
```

| user_id | propensity_score |
| --- | --- |
| 350 | 0.999254469090458 |
| 87 | 0.9989284603445855 |
| 63 | 0.9989128283989277 |
| 58 | 0.998878849339629 |
| 13 | 0.9988688685037858 |


### Agent GenAI evaluation results (MLflow judge: groundedness / correctness / safety)

```sql
SELECT * FROM febar_ml.agent_eval_results ORDER BY evaluated_at DESC LIMIT 5
```

| evaluated_at | n | groundedness | correctness | safety |
| --- | --- | --- | --- | --- |
| 2026-08-28T08:22:43.596Z | 5 | 0.8 | 0.8 | 1.0 |


---

## Layer 5 — Genie room over Gold (Metric Views)

### Metric view mv_sales — governed measures via MEASURE()

```sql
SELECT MEASURE(`Revenue`) AS revenue, MEASURE(`Units Sold`) AS units_sold, MEASURE(`Avg Unit Price`) AS avg_unit_price, MEASURE(`Diamond Mix`) AS diamond_mix FROM febar_gold.mv_sales
```

| revenue | units_sold | avg_unit_price | diamond_mix |
| --- | --- | --- | --- |
| 38898215137 | 485459 | 80091.30618323649 | 0.68526 |


### Metric view mv_customer_propensity — governed measures via MEASURE()

```sql
SELECT MEASURE(`Customers`) AS customers, MEASURE(`Avg Propensity`) AS avg_propensity, MEASURE(`Avg Lifetime Value`) AS avg_lifetime_value FROM febar_gold.mv_customer_propensity
```

| customers | avg_propensity | avg_lifetime_value |
| --- | --- | --- |
| 23391 | 0.45338616168097684 | 1662956.4848445985 |


---

## AI Gateway + Lakehouse Monitoring (operational evidence)

### AI Gateway inference logging — governed LLM payloads captured

```sql
SELECT COUNT(*) AS claude_inference_rows FROM febar_ml.claude_inference_payload
```

| claude_inference_rows |
| --- |
| 36 |


### Lakehouse Monitoring — profile metrics generated for scored table

```sql
SELECT COUNT(*) AS profile_metric_rows FROM febar_ml.customer_nbo_scores_profile_metrics
```

| profile_metric_rows |
| --- |
| 6 |


---

## Layer 6 — Databricks App (surfaces every layer)

**App `febar-concierge`** — status `ACTIVE`, URL https://febar-concierge-4203758776894418.aws.databricksapps.com

FastAPI + React "Growth Concierge": `/api/ask` routes to the agent (governed FM endpoint + UC tools); `/api/customer/{id}` returns propensity + profile + SHAP drivers from Gold. OAuth-gated (identity-aware), so a live call requires an authenticated session.
