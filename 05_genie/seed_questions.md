# FE Bar — BrickJewels — Layer 5 (Genie): Room configuration

**Room name:** BrickJewels Growth & Merchandising Intelligence
**Backing tables (Gold):** `febar_gold.customer_360`, `febar_gold.customer_nbo_scores`, `febar_gold.mv_sales`, `febar_gold.mv_customer_propensity`, `brickjewels_analytics.fact_order_items`, `febar_gold.kpi_daily_sales`

## Instructions (for the room)
- This is a D2C fine-jewelry retailer. "Propensity" = the ML model's Next-Best-Offer conversion score (0–1). Segments: High (decile 9–10), Medium (5–8), Low (1–4).
- Prefer the metric views (`mv_sales`, `mv_customer_propensity`) for revenue/units/propensity so KPI definitions stay consistent; wrap measures in `MEASURE()`.
- Currency is INR. "Diamond mix" = share of items whose material contains "diamond".

## Join hints
- `customer_360.user_id` = `customer_nbo_scores.user_id` = `fact_order_items.user_id`.

## Seed questions
1. What is total revenue by category this year, and which category has the highest diamond mix?
2. How many customers are in the High propensity segment, and what is their average lifetime value vs. the Low segment?
3. Show monthly revenue trend for Necklaces over the last 6 months.
4. Which engagement state (Active / Cooling / Dormant) has the most High-propensity customers?
5. What is the average order value for diamond buyers vs. non-diamond buyers?
6. List the top 10 highest-propensity customers and their lifetime value.
7. What share of revenue comes from the top propensity decile?
8. How does average unit price differ across Ring, Necklace and Earring categories?
