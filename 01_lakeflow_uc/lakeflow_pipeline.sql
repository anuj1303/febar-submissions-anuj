-- Databricks notebook source
-- FE Bar — BrickJewels — Layer 1: Lakeflow Declarative Pipeline (real ingestion)
-- Genuine raw -> bronze -> silver -> gold medallion built with Lakeflow:
--   * Bronze = Auto Loader (STREAM read_files) over raw JSON landed in a UC Volume
--   * Silver = streaming tables with DECLARATIVE DATA-QUALITY EXPECTATIONS + a quarantine stream
--   * Gold   = a materialized view producing the customer feature table for the ML model
-- Target catalog/schema: anuj_vm_workspace_catalog.febar_lakeflow

-- COMMAND ----------
-- ===== BRONZE (Auto Loader ingestion of raw files) =====
CREATE OR REFRESH STREAMING TABLE anuj_vm_workspace_catalog.febar_lakeflow.orders_bronze
  COMMENT "Raw shopper order events, Auto Loader-ingested from the landing volume"
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _bronze_ingested_at
   FROM STREAM read_files(
     '/Volumes/anuj_vm_workspace_catalog/febar_bronze/landing/orders',
     format => 'json');

-- COMMAND ----------
CREATE OR REFRESH STREAMING TABLE anuj_vm_workspace_catalog.febar_lakeflow.order_items_bronze
  COMMENT "Raw order line items, Auto Loader-ingested"
AS SELECT *, current_timestamp() AS _bronze_ingested_at
   FROM STREAM read_files(
     '/Volumes/anuj_vm_workspace_catalog/febar_bronze/landing/order_items',
     format => 'json');

-- COMMAND ----------
CREATE OR REFRESH STREAMING TABLE anuj_vm_workspace_catalog.febar_lakeflow.users_bronze
  COMMENT "Raw customer master, Auto Loader-ingested"
AS SELECT *, current_timestamp() AS _bronze_ingested_at
   FROM STREAM read_files(
     '/Volumes/anuj_vm_workspace_catalog/febar_bronze/landing/users',
     format => 'json');

-- COMMAND ----------
-- ===== SILVER (declarative data-quality expectations; clean rows only) =====
CREATE OR REFRESH STREAMING TABLE anuj_vm_workspace_catalog.febar_lakeflow.orders_silver (
  CONSTRAINT valid_amount EXPECT (total_amount > 0) ON VIOLATION DROP ROW,
  CONSTRAINT has_user     EXPECT (user_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT has_order    EXPECT (order_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT has_status   EXPECT (status IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT has_date     EXPECT (order_date IS NOT NULL) ON VIOLATION DROP ROW
)
  COMMENT "Validated orders — Lakeflow drops+counts rows failing DQ expectations"
AS SELECT order_id, user_id, total_amount, status,
          CAST(order_date AS DATE) AS order_date, item_count, created_at
   FROM STREAM(anuj_vm_workspace_catalog.febar_lakeflow.orders_bronze);

-- COMMAND ----------
-- Quarantine stream: rows that FAIL the same rules are captured with a reason (not dropped)
CREATE OR REFRESH STREAMING TABLE anuj_vm_workspace_catalog.febar_lakeflow.orders_quarantine
  COMMENT "Rows violating DQ rules, retained for audit with a dq_reason"
AS SELECT *,
     concat_ws('; ',
       CASE WHEN total_amount <= 0 OR total_amount IS NULL THEN 'invalid_amount' END,
       CASE WHEN user_id IS NULL  THEN 'null_user' END,
       CASE WHEN order_id IS NULL THEN 'null_order' END,
       CASE WHEN status IS NULL   THEN 'null_status' END,
       CASE WHEN order_date IS NULL THEN 'null_date' END) AS dq_reason
   FROM STREAM(anuj_vm_workspace_catalog.febar_lakeflow.orders_bronze)
   WHERE NOT (total_amount > 0 AND user_id IS NOT NULL AND order_id IS NOT NULL
              AND status IS NOT NULL AND order_date IS NOT NULL);

-- COMMAND ----------
-- ===== GOLD (materialized view: the customer feature table for the ML model) =====
CREATE OR REFRESH MATERIALIZED VIEW anuj_vm_workspace_catalog.febar_lakeflow.customer_features_gold
  COMMENT "Per-customer RFM + affinity + occasion features, produced by the Lakeflow medallion"
AS
WITH ref AS (SELECT max(order_date) AS ref_date FROM anuj_vm_workspace_catalog.febar_lakeflow.orders_silver),
ord AS (
  SELECT user_id, count(DISTINCT order_id) AS frequency, sum(total_amount) AS monetary_total,
         avg(total_amount) AS aov, avg(item_count) AS avg_item_count,
         max(order_date) AS last_order_date, min(order_date) AS first_order_date
  FROM anuj_vm_workspace_catalog.febar_lakeflow.orders_silver GROUP BY user_id),
itm AS (
  SELECT user_id, count(*) AS total_items, count(DISTINCT category) AS distinct_categories,
         avg(CASE WHEN material ILIKE '%diamond%' THEN 1.0 ELSE 0.0 END) AS diamond_share,
         avg(CASE WHEN material ILIKE '%gold%' THEN 1.0 ELSE 0.0 END) AS gold_share
  FROM anuj_vm_workspace_catalog.febar_lakeflow.order_items_bronze GROUP BY user_id),
usr AS (
  SELECT u.user_id,
         CASE WHEN u.anniversary_date IS NULL THEN 365 ELSE pmod(datediff(
           coalesce(try_to_date(concat(year(r.ref_date),'-',lpad(month(u.anniversary_date),2,'0'),'-',lpad(day(u.anniversary_date),2,'0'))), r.ref_date), r.ref_date),365) END AS days_to_anniversary,
         CASE WHEN u.milestone_date IS NOT NULL THEN 1 ELSE 0 END AS has_milestone
  FROM anuj_vm_workspace_catalog.febar_lakeflow.users_bronze u CROSS JOIN ref r)
SELECT o.user_id,
  datediff(r.ref_date, o.last_order_date)  AS recency_days,
  datediff(r.ref_date, o.first_order_date) AS tenure_days,
  o.frequency, o.monetary_total, round(o.aov,2) AS aov, round(o.avg_item_count,3) AS avg_item_count,
  coalesce(i.total_items,0) AS total_items, coalesce(i.distinct_categories,0) AS distinct_categories,
  round(coalesce(i.diamond_share,0),4) AS diamond_share, round(coalesce(i.gold_share,0),4) AS gold_share,
  coalesce(us.days_to_anniversary,365) AS days_to_anniversary,
  coalesce(us.has_milestone,0) AS has_milestone, r.ref_date AS feature_asof_date
FROM ord o CROSS JOIN ref r
LEFT JOIN itm i  ON o.user_id=i.user_id
LEFT JOIN usr us ON o.user_id=us.user_id;
