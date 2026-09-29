# Databricks notebook source
# MAGIC %md # FE Bar — BrickJewels — Layer 2: reverse-ETL model scores → Lakebase
# MAGIC Syncs Gold `customer_nbo_scores` into Lakebase Postgres so the app reads propensity
# MAGIC at low latency. Uses OAuth (generated database credential) — no static password.
# COMMAND ----------
# MAGIC %pip install -q psycopg2-binary
# COMMAND ----------
dbutils.library.restartPython()
# COMMAND ----------
import json, uuid, psycopg2
from psycopg2.extras import execute_values
from databricks.sdk import WorkspaceClient

INSTANCE = "brickjewels-orders"
DBNAME = "brickjewels"
w = WorkspaceClient()
# SDK here lacks w.database — use REST via api_client.do
inst = w.api_client.do("GET", f"/api/2.0/database/instances/{INSTANCE}")
host = inst["read_write_dns"]
user = w.current_user.me().user_name
cred = w.api_client.do("POST", "/api/2.0/database/credentials",
                       body={"request_id": str(uuid.uuid4()), "instance_names": [INSTANCE]})
pw = cred["token"]
print("Lakebase host:", host, "| user:", user)

# COMMAND ----------
df = spark.table("anuj_vm_workspace_catalog.febar_gold.customer_nbo_scores") \
          .select("user_id", "propensity_score", "segment", "decile").toPandas()
rows = [(int(r.user_id), float(r.propensity_score), str(r.segment), int(r.decile)) for r in df.itertuples()]
print("rows to sync:", len(rows))

# COMMAND ----------
conn = psycopg2.connect(host=host, port=5432, dbname=DBNAME, user=user, password=pw, sslmode="require")
conn.autocommit = True
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS febar_nbo_scores (
  user_id INT PRIMARY KEY,
  propensity_score DOUBLE PRECISION,
  segment TEXT,
  decile INT,
  scored_at TIMESTAMP DEFAULT now()
)""")
execute_values(cur, """
INSERT INTO febar_nbo_scores (user_id, propensity_score, segment, decile) VALUES %s
ON CONFLICT (user_id) DO UPDATE SET
  propensity_score = EXCLUDED.propensity_score,
  segment = EXCLUDED.segment,
  decile = EXCLUDED.decile,
  scored_at = now()
""", rows, page_size=1000)

cur.execute("SELECT count(*), round(avg(propensity_score)::numeric,4) FROM febar_nbo_scores")
n, avg = cur.fetchone()
cur.execute("SELECT segment, count(*) FROM febar_nbo_scores GROUP BY segment ORDER BY 2 DESC")
seg = cur.fetchall()
cur.close(); conn.close()

result = {"synced_rows": n, "avg_propensity": float(avg), "segments": {s: c for s, c in seg}}
print("REVERSE-ETL DONE:", result)
dbutils.notebook.exit(json.dumps(result))
