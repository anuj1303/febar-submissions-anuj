# Databricks notebook source
# MAGIC %md # FE Bar — BrickJewels — Layer 4: build, log, register & evaluate the Gen AI agent
# COMMAND ----------
# install WITHOUT -U (upgrading on the pinned serverless env sends pip into a resolver backtrack)
# MAGIC %pip install -q mlflow databricks-langchain langgraph "unitycatalog-langchain[databricks]" databricks-agents
# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
import json, time, signal
summary = {"phases": []}
def log(msg): summary["phases"].append(msg); print(msg)
def with_timeout(sec, fn, *a, **k):
    def h(s, f): raise TimeoutError(f"timeout {sec}s")
    signal.signal(signal.SIGALRM, h); signal.alarm(sec)
    try: return fn(*a, **k)
    finally: signal.alarm(0)

# agent definition (models-from-code)
agent_code = r'''
import mlflow, pandas as pd
from databricks_langchain import ChatDatabricks
try:
    from databricks_langchain import UCFunctionToolkit
except Exception:
    from unitycatalog.ai.langchain.toolkit import UCFunctionToolkit
from langgraph.prebuilt import create_react_agent
CATALOG, SCHEMA = "anuj_vm_workspace_catalog", "febar_ml"
FUNCS = [f"{CATALOG}.{SCHEMA}.{n}" for n in ["get_customer_propensity","get_customer_profile","recommend_next_best_offer","get_top_prospects","search_products","get_category_performance"]]
SYSTEM_PROMPT = ("You are the BrickJewels growth & merchandising concierge for a D2C fine-jewelry retailer. "
"Always use the provided tools to ground answers in real data — never invent product names, prices, propensity "
"scores, segments or customer facts. For a specific customer, look up their propensity and profile and recommend "
"the best offer with a one-line rationale. For catalog questions, search products. For business questions, use "
"category performance. Answer concisely; if a tool returns nothing, say so.")
class BrickJewelsAgent(mlflow.pyfunc.PythonModel):
    def load_context(self, context):
        self.agent = create_react_agent(ChatDatabricks(endpoint="databricks-claude-sonnet-4-6"),
                                         UCFunctionToolkit(function_names=FUNCS).tools)
    def _ask(self, question, user_id=None):
        if user_id is not None and str(user_id).lower() not in ("nan","none",""):
            question = f"[customer user_id={int(float(user_id))}] {question}"
        msgs = [{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":question}]
        return self.agent.invoke({"messages": msgs})["messages"][-1].content
    def predict(self, context, model_input):
        if isinstance(model_input, dict): model_input = pd.DataFrame([model_input])
        uid = "user_id" in model_input.columns
        return [self._ask(r["question"], r["user_id"] if uid else None) for _, r in model_input.iterrows()]
mlflow.models.set_model(BrickJewelsAgent())
'''
open("agent.py","w").write(agent_code); log("agent.py written")

# pin UC function client (execute tools via warehouse; warehouse is running)
try:
    from unitycatalog.ai.core.databricks import DatabricksFunctionClient
    from unitycatalog.ai.core.base import set_uc_function_client
    set_uc_function_client(DatabricksFunctionClient(warehouse_id="0f16ae8ffb7cdef3"))
    log("uc function client set (warehouse)")
except Exception as e:
    log(f"uc client default: {str(e)[:120]}")

# COMMAND ----------
# local smoke test (timeout-guarded so it can never hang the job)
import importlib, agent as agent_mod
importlib.reload(agent_mod)
a = agent_mod.BrickJewelsAgent(); a.load_context(None)
try:
    t=time.time(); ans1 = with_timeout(150, a._ask, "What is the single best offer for this customer and why?", 350)
    summary["smoke_customer"] = ans1[:500]; log(f"smoke1 ok [{time.time()-t:.0f}s]")
except Exception as e:
    summary["smoke_customer_error"] = repr(e)[:300]; log("smoke1 FAILED")
try:
    t=time.time(); ans2 = with_timeout(150, a._ask, "Show me two diamond necklaces we sell.")
    summary["smoke_catalog"] = ans2[:500]; log(f"smoke2 ok [{time.time()-t:.0f}s]")
except Exception as e:
    summary["smoke_catalog_error"] = repr(e)[:300]; log("smoke2 FAILED")

# COMMAND ----------
# log + register to UC
import mlflow, pandas as pd
from mlflow.models.resources import DatabricksServingEndpoint, DatabricksFunction
mlflow.set_registry_uri("databricks-uc")
CATALOG, SCHEMA = "anuj_vm_workspace_catalog", "febar_ml"
MODEL = f"{CATALOG}.{SCHEMA}.nbo_agent"
FUNCS = [f"{CATALOG}.{SCHEMA}.{n}" for n in ["get_customer_propensity","get_customer_profile","recommend_next_best_offer","get_top_prospects","search_products","get_category_performance"]]
resources = [DatabricksServingEndpoint(endpoint_name="databricks-claude-sonnet-4-6")] + [DatabricksFunction(function_name=f) for f in FUNCS]
try:
    with mlflow.start_run(run_name="nbo_agent") as run:
        info = mlflow.pyfunc.log_model(name="agent", python_model="agent.py", resources=resources,
            input_example=pd.DataFrame([{"question":"Best offer for this customer?","user_id":350}]),
            pip_requirements=["mlflow","databricks-langchain","langgraph","unitycatalog-langchain[databricks]","databricks-sdk"],
            registered_model_name=MODEL)
        summary["model"] = MODEL; summary["model_uri"] = info.model_uri; summary["run_id"] = run.info.run_id
        log("model registered")
except Exception as e:
    summary["register_error"] = repr(e)[:400]; log("register FAILED")

# COMMAND ----------
# best-effort GenAI eval (groundedness/safety) — never fail the job
try:
    m = mlflow.pyfunc.load_model(summary["model_uri"])
    qs = [{"question":"Best offer for this customer and why?","user_id":350},
          {"question":"How is the Necklace category performing?","user_id":None},
          {"question":"Give me 3 top prospects to target.","user_id":None}]
    ans = [with_timeout(150, m.predict, pd.DataFrame([q]))[0] for q in qs]
    summary["eval_samples"] = [a2[:200] for a2 in ans]
    try:
        from databricks.agents.evals import judges
        def _p(x): return 1.0 if str(getattr(x,"value",x)).lower() in ("yes","true","pass") else 0.0
        gr = [_p(judges.groundedness(request=q["question"], response=a2)) for q,a2 in zip(qs,ans)]
        sf = [_p(judges.safety(request=q["question"], response=a2)) for q,a2 in zip(qs,ans)]
        with mlflow.start_run(run_id=summary["run_id"]):
            mlflow.log_metrics({"groundedness_rate": sum(gr)/len(gr), "safety_rate": sum(sf)/len(sf)})
        summary["groundedness_rate"] = sum(gr)/len(gr); summary["safety_rate"] = sum(sf)/len(sf)
        log("judges scored")
    except Exception as e:
        summary["eval_judge_error"] = str(e)[:200]; log("judges unavailable")
except Exception as e:
    summary["eval_error"] = repr(e)[:300]; log("eval FAILED")

# COMMAND ----------
dbutils.notebook.exit(json.dumps(summary))
