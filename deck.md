# BrickJewels — AI-Native Growth Concierge
### An end-to-end Databricks build for D2C fine-jewelry retail
*Field Engineering AI Build · Anuj Lathi · 100% synthetic data*

---

## 1. The business problem (before any tooling)

BrickJewels is a direct-to-consumer fine-jewelry retailer at Tanishq/CaratLane scale. Four challenges specific to jewelry — not generic retail — cap its growth:

- **Discovery is high-consideration and visual.** Shoppers describe intent in natural language ("a diamond pendant for my anniversary under ₹2 lakh"), not SKUs. Keyword search misses.
- **Pricing is volatile.** Product prices are pegged to **daily gold/silver rates**; static pricing erodes margin or loses the sale.
- **Retention beats acquisition — but it's blunt.** Marketing sends one rule-based nudge ("10% off") to all ~23,000 customers, wasting discount margin on those who'd buy anyway and missing those who need a reason.
- **The growth team is blocked on analysts.** Merchandising waits days for a dashboard change to answer a simple question.

---

## 2. The outcome (lead with the money)

On a book of **~23,400 customers worth ~₹3,900 crore in lifetime value**, the model shows spend is mis-allocated: only **~4,700 customers are high-intent** and **~9,400 will not respond** this cycle. Concentrating on the high-propensity tier (**97% precision**) and suppressing the dead-weight third lifts campaign ROI and protects margin.

> **Headline:** even a **1-point lift in repeat-purchase rate** across that LTV book is **~₹39 crore** in incremental lifetime revenue *(illustrative; assumption stated)*. The build is designed to capture a multiple of that.

---

## 3. Value for the **CFO / funding executive**

*What the person who funds the investment cares about: margin, revenue, risk, cost.*

| Lever | Impact |
|---|---|
| **Incremental revenue** | ~₹39 cr per 1-pt repeat-rate lift on a ~₹3,900 cr LTV book (illustrative). |
| **Margin protection** | Stop discounting the **~9,400 low-propensity** customers who won't convert; live per-product pricing replaces blanket markdowns. |
| **Concentration of spend** | Target the top decile (converts ~97%) instead of spraying all 23,400 — higher return per rupee. |
| **Low incremental cost** | Runs entirely on the **existing Databricks platform** — no new stack to fund or staff. |
| **De-risked & auditable** | Model is measured (PR-AUC 0.837), explainable (SHAP), and monitored for drift; PII is masked, row-filtered, and blocked at the AI Gateway — audit-safe by construction. |

**CFO takeaway:** a governed, measurable revenue-and-margin lever on the current platform — quantified, caveated, and low-risk.

---

## 4. Value for the **Growth / Merchandising lead**

*What the person who runs the day-to-day loop cares about: who to target, what changes on the ground.*

- **A ranked action list every morning.** The ~4,678 **High**-propensity customers, each with a recommended next-best-offer and the **SHAP "why"** (frequency, recency, monetary, wishlist, diamond affinity) — not a spreadsheet to interpret.
- **The daily loop changes.** The blanket "10% to everyone" blast becomes a **targeted, occasion-aware motion**: anniversary-window, diamond-affinity shoppers with high-value abandoned carts surface automatically; the Low tier is suppressed.
- **Self-serve answers, no analyst queue.** Ask Genie in plain English — "revenue by category," "High vs Low segment count and LTV" — and get governed, consistent numbers in seconds.
- **Segments you can act on.** High-segment customers carry **~6× the lifetime value** of the Low segment (₹38.3L vs ₹6.2L — confirmed live in Genie), so effort goes where it compounds.

**Growth-lead takeaway:** a concrete, explainable target list and a self-serve BI room that replaces guesswork and ticket queues.

---

## 5. How it works — one connected journey (the "golden thread")

One seeded cohort (anniversary-window, diamond-affinity, abandoned high-value carts) flows through **every** layer:

```
Raw events/catalog/metal rates
  -> Lakeflow Declarative Pipeline (Auto Loader -> Bronze -> Silver DQ+quarantine -> Gold)
  -> Unity Catalog governance (column masks, region row filter, lineage)
  -> ML: Next-Best-Offer propensity (LightGBM -> MLflow -> UC -> Model Serving -> SHAP)
  -> Gen AI Agent (6 governed UC-function tools, MLflow-evaluated, AI-Gateway-governed)
  -> Genie room (self-serve BI over metric views)
  -> Databricks App "Growth Concierge" (shopper + growth-owner surfaces)
```

The ML model **predicts**, the agent **acts**, and every foundation-model call is **governed**.

---

## 6. Proof it's real (committed, text-readable evidence)

- **Lakeflow:** Auto Loader ingested **216,485** raw orders -> silver (DQ-validated) -> gold **23,391** feature rows.
- **ML:** PR-AUC **0.837** vs 0.455 base; precision@top-decile **0.969**; live serving endpoint returned **0.9993** for a specific customer (matches batch + agent tool).
- **Agent:** 6 governed UC-function tools; MLflow eval groundedness **0.8** / correctness **0.8** / safety **1.0**.
- **Genie:** deployed room; real Q&A with Genie-generated `MEASURE()` SQL (revenue by category; High-vs-Low LTV).
- **Governance:** PII column masks + region row filter; AI Gateway PII guardrail (blocks card/Aadhaar) + usage/inference logging.

---

## 7. The ask

Run a **focused pilot on the next anniversary campaign**: target the High decile, suppress the Low, and measure lift against a holdout. It runs on the existing platform with governance built in — bring the CFO the measured revenue/margin lift, and give the growth lead a target list they act on the same day.
