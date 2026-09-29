# Databricks notebook source
# MAGIC %md
# MAGIC # FE Bar — BrickJewels — Layer 3 (ML): Next-Best-Offer Propensity
# MAGIC Trains a gradient-boosted model to predict a customer's propensity to convert on a
# MAGIC targeted offer, from behavioral features (RFM + affinity + engagement + occasion).
# MAGIC Logs to MLflow, registers in Unity Catalog, computes SHAP explainability + PR-AUC,
# MAGIC and batch-scores every customer into a Gold serving table.

# COMMAND ----------
# MAGIC %pip install -q mlflow lightgbm shap
# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
import numpy as np, pandas as pd, mlflow
from mlflow.models.signature import infer_signature
from sklearn.model_selection import train_test_split
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss
import lightgbm as lgb

CATALOG, SCHEMA = "anuj_vm_workspace_catalog", "febar_ml"
MODEL_NAME = f"{CATALOG}.{SCHEMA}.nbo_propensity"
mlflow.set_registry_uri("databricks-uc")

df = spark.table(f"{CATALOG}.febar_ml.training_dataset").toPandas()
LABEL = "label_conversion"
DROP = {"user_id", "propensity_true", LABEL}
FEATURES = [c for c in df.columns if c not in DROP]
print(f"{len(df)} rows | {len(FEATURES)} features | base rate = {df[LABEL].mean():.3f}")
print("features:", FEATURES)

# DECIMAL/bigint columns arrive as pandas 'object' — coerce all features to float for the model
for c in FEATURES:
    df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
X, y = df[FEATURES], df[LABEL].astype(int)
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

# COMMAND ----------
model = lgb.LGBMClassifier(
    n_estimators=400, learning_rate=0.05, num_leaves=31, max_depth=6,
    subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1)

with mlflow.start_run(run_name="nbo_propensity") as run:
    model.fit(Xtr, ytr)
    proba = model.predict_proba(Xte)[:, 1]

    base = float(yte.mean())
    pr_auc = float(average_precision_score(yte, proba))
    roc = float(roc_auc_score(yte, proba))
    brier = float(brier_score_loss(yte, proba))
    order = np.argsort(-proba)
    k = max(1, int(0.10 * len(yte)))
    prec_at_decile = float(yte.iloc[order[:k]].mean())
    lift_at_decile = prec_at_decile / base

    mlflow.log_params({"model": "LightGBM", "n_estimators": 400, "lr": 0.05, "max_depth": 6})
    mlflow.log_metrics({
        "pr_auc": pr_auc, "roc_auc": roc, "base_rate": base, "brier": brier,
        "precision_at_decile": prec_at_decile, "lift_at_decile": lift_at_decile})

    # Log via a pyfunc wrapper (cloudpickle + joblib artifact) so the endpoint returns the
    # positive-class PROPENSITY directly, and to avoid MLflow's skops "untrusted types" gate.
    import joblib
    joblib.dump(model, "/tmp/nbo.joblib")

    class NBOModel(mlflow.pyfunc.PythonModel):
        def load_context(self, context):
            import joblib
            self._m = joblib.load(context.artifacts["model"])
        def predict(self, context, model_input):
            return self._m.predict_proba(model_input)[:, 1]

    sig = infer_signature(Xtr, model.predict_proba(Xtr)[:, 1])
    mlflow.pyfunc.log_model(
        name="model", python_model=NBOModel(),
        artifacts={"model": "/tmp/nbo.joblib"},
        signature=sig, input_example=Xtr.head(3),
        pip_requirements=["lightgbm", "scikit-learn", "joblib", "pandas"],
        registered_model_name=MODEL_NAME)

    print(f"PR-AUC={pr_auc:.4f}  (base rate={base:.4f}, lift={pr_auc/base:.2f}x)")
    print(f"ROC-AUC={roc:.4f}  Brier={brier:.4f}")
    print(f"precision@decile={prec_at_decile:.4f}  lift@decile={lift_at_decile:.2f}x")
    run_id = run.info.run_id

# COMMAND ----------
# MAGIC %md ## SHAP explainability (global drivers)
# COMMAND ----------
import shap, matplotlib.pyplot as plt
samp = Xte.sample(min(800, len(Xte)), random_state=1)
sv = shap.TreeExplainer(model).shap_values(samp)
sv = sv[1] if isinstance(sv, list) else sv
imp = (pd.DataFrame({"feature": FEATURES, "mean_abs_shap": np.abs(sv).mean(0)})
       .sort_values("mean_abs_shap", ascending=False).reset_index(drop=True))
print(imp.to_string(index=False))

plt.figure(figsize=(7, 5))
shap.summary_plot(sv, samp, plot_type="bar", show=False)
plt.tight_layout(); plt.savefig("/tmp/shap_importance.png", dpi=120, bbox_inches="tight")
with mlflow.start_run(run_id=run_id):
    mlflow.log_artifact("/tmp/shap_importance.png", "shap")

# persist global importance for the app "why this offer" panel
(spark.createDataFrame(imp).write.mode("overwrite")
 .saveAsTable(f"{CATALOG}.febar_gold.nbo_feature_importance"))

# COMMAND ----------
# MAGIC %md ## Batch scoring → Gold serving table
# COMMAND ----------
scores = df[["user_id"]].copy()
scores["propensity_score"] = model.predict_proba(X)[:, 1]
scores["decile"] = (pd.qcut(scores["propensity_score"].rank(method="first"), 10, labels=False) + 1).astype(int)
scores["segment"] = np.where(scores["decile"] >= 9, "High", np.where(scores["decile"] >= 5, "Medium", "Low"))
scores["scored_at"] = pd.Timestamp.utcnow().tz_localize(None)

(spark.createDataFrame(scores).write.mode("overwrite").option("overwriteSchema", "true")
 .saveAsTable(f"{CATALOG}.febar_gold.customer_nbo_scores"))
print("scored users:", len(scores))
display(scores.groupby("segment").agg(n=("user_id", "size"), avg_score=("propensity_score", "mean")))

# COMMAND ----------
print("MODEL:", MODEL_NAME, "| run:", run_id)
