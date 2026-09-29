-- FE Bar — BrickJewels — Layer 3 (ML), training dataset
-- Seeds a LEARNABLE Next-Best-Offer propensity pattern: a latent propensity is a
-- deterministic function of real behavioral features (RFM + diamond affinity + engagement
-- + anniversary proximity); the binary label is a per-user Bernoulli draw from that propensity
-- (deterministic via hash → reproducible). The model learns the pattern (PR-AUC >> base rate);
-- the Bernoulli draw provides irreducible error so it is realistic, not perfectly separable.
-- Feature standardization is computed inline (self-contained). propensity_true is kept for
-- diagnostics ONLY and must be excluded from model features (leakage).

CREATE OR REPLACE TABLE anuj_vm_workspace_catalog.febar_ml.training_dataset AS
WITH f AS (SELECT * FROM anuj_vm_workspace_catalog.febar_gold.customer_features),
s AS (
  SELECT avg(recency_days) rec_m, stddev(recency_days) rec_s,
         avg(frequency) fq_m,     stddev(frequency) fq_s,
         avg(ln(monetary_total+1)) lm_m, stddev(ln(monetary_total+1)) lm_s,
         avg(wishlist_count) wi_m, stddev(wishlist_count) wi_s,
         avg(cart_adds) ca_m,     stddev(cart_adds) ca_s,
         avg(tenure_days) te_m,   stddev(tenure_days) te_s
  FROM f
),
z AS (
  SELECT f.*,
    (f.recency_days       - s.rec_m)/nullif(s.rec_s,0) AS z_recency,
    (f.frequency          - s.fq_m )/nullif(s.fq_s ,0) AS z_freq,
    (ln(f.monetary_total+1) - s.lm_m)/nullif(s.lm_s,0) AS z_lmon,
    (f.wishlist_count     - s.wi_m )/nullif(s.wi_s ,0) AS z_wish,
    (f.cart_adds          - s.ca_m )/nullif(s.ca_s ,0) AS z_cart,
    (f.tenure_days        - s.te_m )/nullif(s.te_s ,0) AS z_tenure
  FROM f CROSS JOIN s
),
p AS (
  SELECT z.*,
    ( -0.60
      + 0.70*z_freq
      - 0.70*z_recency
      + 0.50*z_lmon
      + 1.20*(z.diamond_share - 0.4)
      + 0.50*z_wish
      + 0.40*z_cart
      + 0.20*z_tenure
      + 0.80*(CASE WHEN z.days_to_anniversary <= 30 THEN 1 ELSE 0 END)
    ) AS latent
  FROM z
)
SELECT
  user_id, recency_days, tenure_days, frequency, monetary_total, aov, avg_item_count,
  total_items, distinct_categories, diamond_share, gold_share, cart_adds, cart_value,
  wishlist_count, wishlist_value, days_to_anniversary, days_to_birthday, has_milestone,
  round(1.0/(1.0+exp(-latent)), 6) AS propensity_true,
  CASE WHEN (pmod(hash(user_id, 'febar_nbo_seed'), 100000)/100000.0)
            < 1.0/(1.0+exp(-latent))
       THEN 1 ELSE 0 END AS label_conversion
FROM p;
