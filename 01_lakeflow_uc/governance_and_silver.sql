-- FE Bar — BrickJewels — Layer 1 (Lakeflow + UC): Silver data-quality + governance
-- (1) Silver clean/quarantine split (expectations), (2) Gold customer dim with PII column
-- masking + region row filter. Bronze source = the analytics star schema.

-- (1) Silver: expectations + quarantine ------------------------------------------------
CREATE OR REPLACE TABLE anuj_vm_workspace_catalog.febar_silver.orders_clean AS
SELECT * FROM anuj_vm_workspace_catalog.brickjewels_analytics.fact_orders
WHERE total_amount > 0 AND user_id IS NOT NULL AND order_id IS NOT NULL
  AND status IS NOT NULL AND order_date IS NOT NULL;

CREATE OR REPLACE TABLE anuj_vm_workspace_catalog.febar_silver.orders_quarantine AS
SELECT *,
  concat_ws('; ',
    CASE WHEN total_amount <= 0 OR total_amount IS NULL THEN 'invalid_amount' END,
    CASE WHEN user_id IS NULL   THEN 'null_user' END,
    CASE WHEN order_id IS NULL  THEN 'null_order' END,
    CASE WHEN status IS NULL    THEN 'null_status' END,
    CASE WHEN order_date IS NULL THEN 'null_date' END) AS dq_reason
FROM anuj_vm_workspace_catalog.brickjewels_analytics.fact_orders
WHERE NOT (total_amount > 0 AND user_id IS NOT NULL AND order_id IS NOT NULL
           AND status IS NOT NULL AND order_date IS NOT NULL);

-- (2) Gold customer dimension with a (synthetic) region for row-level security ----------
CREATE OR REPLACE TABLE anuj_vm_workspace_catalog.febar_gold.dim_customers AS
SELECT user_id, first_name, last_name, email, mobile,
       element_at(array('North','South','East','West'), pmod(abs(hash(user_id)),4)+1) AS region,
       date_of_birth, anniversary_date, created_at
FROM anuj_vm_workspace_catalog.brickjewels_analytics.dim_users;

-- Column masks: reveal PII only to admins ----------------------------------------------
CREATE OR REPLACE FUNCTION anuj_vm_workspace_catalog.febar_gold.mask_email(e STRING)
  RETURNS STRING
  RETURN CASE WHEN is_account_group_member('admins') THEN e
              ELSE concat(substr(e,1,2), '***', regexp_extract(e,'(@.*)$',1)) END;

CREATE OR REPLACE FUNCTION anuj_vm_workspace_catalog.febar_gold.mask_mobile(m STRING)
  RETURNS STRING
  RETURN CASE WHEN is_account_group_member('admins') THEN m
              ELSE concat('******', substr(m, -4)) END;

ALTER TABLE anuj_vm_workspace_catalog.febar_gold.dim_customers
  ALTER COLUMN email SET MASK anuj_vm_workspace_catalog.febar_gold.mask_email;
ALTER TABLE anuj_vm_workspace_catalog.febar_gold.dim_customers
  ALTER COLUMN mobile SET MASK anuj_vm_workspace_catalog.febar_gold.mask_mobile;

-- Row filter: analysts see only the 'South' region; admins see all ---------------------
CREATE OR REPLACE FUNCTION anuj_vm_workspace_catalog.febar_gold.region_filter(region STRING)
  RETURNS BOOLEAN
  RETURN is_account_group_member('admins') OR region = 'South';

ALTER TABLE anuj_vm_workspace_catalog.febar_gold.dim_customers
  SET ROW FILTER anuj_vm_workspace_catalog.febar_gold.region_filter ON (region);
