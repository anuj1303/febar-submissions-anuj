-- FE Bar — BrickJewels — Layer 1 (Lakeflow + UC), Gold feature table
-- Per-customer behavioral features (RFM + affinity + engagement + occasion proximity)
-- built from the Gold star schema. This is the feature source for the Layer 3 ML model
-- and is read at low latency by the app/agent. NO label here (kept leakage-free).

CREATE OR REPLACE TABLE anuj_vm_workspace_catalog.febar_gold.customer_features AS
WITH ref AS (
  SELECT max(order_date) AS ref_date
  FROM anuj_vm_workspace_catalog.brickjewels_analytics.fact_orders
),
ord AS (
  SELECT user_id,
         count(DISTINCT order_id) AS frequency,
         sum(total_amount)        AS monetary_total,
         avg(total_amount)        AS aov,
         avg(item_count)          AS avg_item_count,
         max(order_date)          AS last_order_date,
         min(order_date)          AS first_order_date
  FROM anuj_vm_workspace_catalog.brickjewels_analytics.fact_orders
  GROUP BY user_id
),
itm AS (
  SELECT user_id,
         count(*)                                                        AS total_items,
         count(DISTINCT category)                                        AS distinct_categories,
         avg(CASE WHEN material ILIKE '%diamond%' THEN 1.0 ELSE 0.0 END) AS diamond_share,
         avg(CASE WHEN material ILIKE '%gold%'    THEN 1.0 ELSE 0.0 END) AS gold_share
  FROM anuj_vm_workspace_catalog.brickjewels_analytics.fact_order_items
  GROUP BY user_id
),
crt AS (
  SELECT user_id, count(*) AS cart_adds, coalesce(sum(price_inr),0) AS cart_value
  FROM anuj_vm_workspace_catalog.brickjewels_analytics.fact_carts GROUP BY user_id
),
wsh AS (
  SELECT user_id, count(*) AS wishlist_count, coalesce(sum(price_inr),0) AS wishlist_value
  FROM anuj_vm_workspace_catalog.brickjewels_analytics.fact_wishlists GROUP BY user_id
),
usr AS (
  SELECT u.user_id, u.anniversary_date, u.date_of_birth, u.milestone_date,
         -- days until next yearly recurrence of anniversary / birthday (0..365); try_to_date guards Feb-29
         CASE WHEN u.anniversary_date IS NULL THEN 365
              ELSE pmod(
                     datediff(
                       coalesce(try_to_date(concat(year(r.ref_date),'-',lpad(month(u.anniversary_date),2,'0'),'-',lpad(day(u.anniversary_date),2,'0'))), r.ref_date),
                       r.ref_date), 365)
         END AS days_to_anniversary,
         CASE WHEN u.date_of_birth IS NULL THEN 365
              ELSE pmod(
                     datediff(
                       coalesce(try_to_date(concat(year(r.ref_date),'-',lpad(month(u.date_of_birth),2,'0'),'-',lpad(day(u.date_of_birth),2,'0'))), r.ref_date),
                       r.ref_date), 365)
         END AS days_to_birthday,
         CASE WHEN u.milestone_date IS NOT NULL THEN 1 ELSE 0 END AS has_milestone
  FROM anuj_vm_workspace_catalog.brickjewels_analytics.dim_users u CROSS JOIN ref r
)
SELECT
  o.user_id,
  datediff(r.ref_date, o.last_order_date)              AS recency_days,
  datediff(r.ref_date, o.first_order_date)             AS tenure_days,
  o.frequency,
  o.monetary_total,
  round(o.aov, 2)                                      AS aov,
  round(o.avg_item_count, 3)                           AS avg_item_count,
  coalesce(i.total_items, 0)                           AS total_items,
  coalesce(i.distinct_categories, 0)                   AS distinct_categories,
  round(coalesce(i.diamond_share, 0), 4)               AS diamond_share,
  round(coalesce(i.gold_share, 0), 4)                  AS gold_share,
  coalesce(c.cart_adds, 0)                             AS cart_adds,
  coalesce(c.cart_value, 0)                            AS cart_value,
  coalesce(w.wishlist_count, 0)                        AS wishlist_count,
  coalesce(w.wishlist_value, 0)                        AS wishlist_value,
  coalesce(us.days_to_anniversary, 365)                AS days_to_anniversary,
  coalesce(us.days_to_birthday, 365)                   AS days_to_birthday,
  coalesce(us.has_milestone, 0)                        AS has_milestone,
  r.ref_date                                           AS feature_asof_date
FROM ord o
CROSS JOIN ref r
LEFT JOIN itm i  ON o.user_id = i.user_id
LEFT JOIN crt c  ON o.user_id = c.user_id
LEFT JOIN wsh w  ON o.user_id = w.user_id
LEFT JOIN usr us ON o.user_id = us.user_id;
