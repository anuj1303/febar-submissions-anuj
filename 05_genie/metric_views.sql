-- FE Bar — BrickJewels — Layer 5 (Genie): UC Metric Views for consistent KPI definitions
-- Queried with MEASURE(<measure>). Backing tables for the Genie room.

-- customer_360: features + model scores (also read by the app)
CREATE OR REPLACE VIEW anuj_vm_workspace_catalog.febar_gold.customer_360 AS
SELECT f.*, s.propensity_score, s.segment, s.decile
FROM anuj_vm_workspace_catalog.febar_gold.customer_features f
LEFT JOIN anuj_vm_workspace_catalog.febar_gold.customer_nbo_scores s ON f.user_id = s.user_id;

-- Sales metric view
CREATE OR REPLACE VIEW anuj_vm_workspace_catalog.febar_gold.mv_sales WITH METRICS
LANGUAGE YAML AS $$
version: 0.1
source: anuj_vm_workspace_catalog.brickjewels_analytics.fact_order_items
dimensions:
  - name: Category
    expr: category
  - name: Order Month
    expr: date_trunc('MONTH', order_date)
measures:
  - name: Revenue
    expr: SUM(line_total)
  - name: Units Sold
    expr: SUM(quantity)
  - name: Avg Unit Price
    expr: AVG(unit_price)
  - name: Diamond Mix
    expr: AVG(CASE WHEN material ILIKE '%diamond%' THEN 1.0 ELSE 0.0 END)
$$;

-- Customer propensity metric view
CREATE OR REPLACE VIEW anuj_vm_workspace_catalog.febar_gold.mv_customer_propensity WITH METRICS
LANGUAGE YAML AS $$
version: 0.1
source: anuj_vm_workspace_catalog.febar_gold.customer_360
dimensions:
  - name: Segment
    expr: segment
  - name: Engagement State
    expr: CASE WHEN recency_days <= 14 THEN 'Active' WHEN recency_days <= 45 THEN 'Cooling' ELSE 'Dormant' END
measures:
  - name: Customers
    expr: COUNT(DISTINCT user_id)
  - name: Avg Propensity
    expr: AVG(propensity_score)
  - name: Avg Lifetime Value
    expr: AVG(monetary_total)
$$;
