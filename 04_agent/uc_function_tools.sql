-- FE Bar — BrickJewels — Layer 4 (Gen AI Agent): governed UC-function tools
-- These SQL functions are registered in Unity Catalog and bound to the agent via
-- UCFunctionToolkit. Function + parameter COMMENTs become the tool descriptions the LLM sees.
-- All are grounded in the Gold layer (single source of truth) — no side data.

-- 1. Model-backed propensity lookup
CREATE OR REPLACE FUNCTION anuj_vm_workspace_catalog.febar_ml.get_customer_propensity(p_user_id INT COMMENT 'customer id')
RETURNS TABLE(user_id INT, propensity_score DOUBLE, segment STRING, decile INT)
COMMENT 'Return the Next-Best-Offer conversion propensity, segment (High/Medium/Low) and decile for a customer, from the ML model batch scores.'
RETURN SELECT user_id, propensity_score, segment, decile
       FROM anuj_vm_workspace_catalog.febar_gold.customer_nbo_scores WHERE user_id = p_user_id;

-- 2. Behavioral profile (RFM + affinity + engagement)
CREATE OR REPLACE FUNCTION anuj_vm_workspace_catalog.febar_ml.get_customer_profile(p_user_id INT COMMENT 'customer id')
RETURNS TABLE(recency_days INT, frequency BIGINT, lifetime_value BIGINT, aov DECIMAL(20,2),
              diamond_share DECIMAL(10,4), wishlist_count BIGINT, cart_adds BIGINT, days_to_anniversary INT)
COMMENT 'Return a customer behavioral profile: recency, order frequency, lifetime spend, average order value, diamond affinity, wishlist and cart activity, and days to their next anniversary.'
RETURN SELECT recency_days, frequency, monetary_total, aov, diamond_share, wishlist_count, cart_adds, days_to_anniversary
       FROM anuj_vm_workspace_catalog.febar_gold.customer_features WHERE user_id = p_user_id;

-- 3. Next-best-offer recommendation (propensity + affinity + occasion logic)
CREATE OR REPLACE FUNCTION anuj_vm_workspace_catalog.febar_ml.recommend_next_best_offer(p_user_id INT COMMENT 'customer id')
RETURNS TABLE(recommended_offer STRING, rationale STRING, propensity_score DOUBLE)
COMMENT 'Recommend the single best offer for a customer based on their model propensity, diamond affinity and anniversary proximity, with a short rationale.'
RETURN
  SELECT
    CASE WHEN f.days_to_anniversary <= 30 THEN 'Anniversary: 40% off making charges on diamond sets'
         WHEN f.diamond_share >= 0.6      THEN 'Diamond loyalty: complimentary certification + 25% off making'
         WHEN s.segment = 'High'          THEN 'VIP early access to new collection + free resizing'
         WHEN f.cart_adds >= 3            THEN 'Cart nudge: 5% off cart above Rs.1L'
         ELSE 'Welcome-back: 3% off next purchase' END AS recommended_offer,
    concat('segment=', s.segment, ', propensity=', round(s.propensity_score,3),
           ', diamond_share=', round(f.diamond_share,2),
           ', days_to_anniversary=', f.days_to_anniversary) AS rationale,
    s.propensity_score
  FROM anuj_vm_workspace_catalog.febar_gold.customer_nbo_scores s
  JOIN anuj_vm_workspace_catalog.febar_gold.customer_features  f ON s.user_id = f.user_id
  WHERE s.user_id = p_user_id;

-- 4. Top prospects for a campaign
CREATE OR REPLACE FUNCTION anuj_vm_workspace_catalog.febar_ml.get_top_prospects(p_segment STRING COMMENT 'High, Medium or Low', p_limit INT COMMENT 'how many to return')
RETURNS TABLE(user_id INT, propensity_score DOUBLE)
COMMENT 'Return the top-N highest-propensity customers within a segment (High/Medium/Low), for targeting a campaign.'
RETURN SELECT user_id, propensity_score FROM (
         SELECT user_id, propensity_score,
                row_number() OVER (ORDER BY propensity_score DESC) rn
         FROM anuj_vm_workspace_catalog.febar_gold.customer_nbo_scores
         WHERE segment = p_segment)
       WHERE rn <= p_limit;

-- 5. Product search (grounded keyword retrieval over the catalog)
CREATE OR REPLACE FUNCTION anuj_vm_workspace_catalog.febar_ml.search_products(p_query STRING COMMENT 'free-text product query, e.g. diamond necklace')
RETURNS TABLE(product_id STRING, name STRING, category STRING, material STRING, price_inr INT)
COMMENT 'Search the jewelry catalog by free text over product name, description and tags. Returns up to 8 matching products.'
RETURN SELECT product_id, name, category, material, price_inr
       FROM anuj_vm_workspace_catalog.caratlane_jewelry.enriched_jewelry_products
       WHERE name ILIKE '%' || p_query || '%' OR description ILIKE '%' || p_query || '%' OR tags ILIKE '%' || p_query || '%'
       ORDER BY price_inr DESC LIMIT 8;

-- 6. Category performance (for the business/merchandising persona)
CREATE OR REPLACE FUNCTION anuj_vm_workspace_catalog.febar_ml.get_category_performance(p_category STRING COMMENT 'jewelry category, e.g. Necklace')
RETURNS TABLE(category STRING, units BIGINT, revenue BIGINT, avg_unit_price BIGINT, diamond_mix DECIMAL(10,3))
COMMENT 'Return sales performance for a jewelry category: units sold, revenue, average unit price and diamond mix.'
RETURN SELECT category, units, revenue, avg_unit_price, diamond_mix
       FROM anuj_vm_workspace_catalog.febar_gold.kpi_category_performance WHERE category = p_category;
