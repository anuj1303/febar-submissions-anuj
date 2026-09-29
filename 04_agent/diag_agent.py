# Databricks notebook source
# MAGIC %pip install -q -U mlflow databricks-langchain langgraph "unitycatalog-langchain[databricks]"
# COMMAND ----------
dbutils.library.restartPython()
# COMMAND ----------
import time, signal
t0=time.time()
from databricks_langchain import ChatDatabricks
try:
    from databricks_langchain import UCFunctionToolkit
    src="databricks_langchain"
except Exception:
    from unitycatalog.ai.langchain.toolkit import UCFunctionToolkit
    src="unitycatalog.ai"
from langgraph.prebuilt import create_react_agent
print(f"[{time.time()-t0:.1f}s] imports ok (UCFunctionToolkit from {src})")

# Pin the UC function client to serverless execution so tool calls don't block on a warehouse
try:
    from unitycatalog.ai.core.databricks import DatabricksFunctionClient
    from unitycatalog.ai.core.base import set_uc_function_client
    client = DatabricksFunctionClient()
    set_uc_function_client(client)
    print(f"[{time.time()-t0:.1f}s] UC function client set")
except Exception as e:
    print("client set skipped:", str(e)[:150])

# COMMAND ----------
CATALOG, SCHEMA = "anuj_vm_workspace_catalog", "febar_ml"
FUNCS=[f"{CATALOG}.{SCHEMA}.{n}" for n in ["get_customer_propensity","recommend_next_best_offer","search_products","get_category_performance","get_customer_profile","get_top_prospects"]]
t=time.time()
llm = ChatDatabricks(endpoint="databricks-claude-sonnet-4-6")
tk = UCFunctionToolkit(function_names=FUNCS)
tools = tk.tools
print(f"[{time.time()-t:.1f}s] toolkit built with {len(tools)} tools: {[getattr(x,'name','?') for x in tools]}")

# COMMAND ----------
# Test raw tool execution FIRST (isolates UC-function exec latency from the LLM loop)
def _timeout(sec):
    def deco(fn):
        def wrap(*a,**k):
            def h(s,f): raise TimeoutError(f"timeout after {sec}s")
            signal.signal(signal.SIGALRM,h); signal.alarm(sec)
            try: return fn(*a,**k)
            finally: signal.alarm(0)
        return wrap
    return deco

@_timeout(90)
def raw_tool_call():
    tool = [x for x in tools if "recommend_next_best_offer" in getattr(x,'name','')][0]
    return tool.invoke({"p_user_id": 350})

t=time.time()
try:
    print("RAW TOOL RESULT:", str(raw_tool_call())[:300], f"  [{time.time()-t:.1f}s]")
except Exception as e:
    print(f"RAW TOOL FAILED after {time.time()-t:.1f}s:", repr(e)[:300])

# COMMAND ----------
# Now test the full react agent with a hard timeout
@_timeout(120)
def agent_call():
    agent = create_react_agent(llm, tools)
    r = agent.invoke({"messages":[{"role":"user","content":"What is the best offer for customer user_id=350 and why? Use the tools."}]})
    return r["messages"][-1].content

t=time.time()
try:
    print("AGENT RESULT:", str(agent_call())[:400], f"  [{time.time()-t:.1f}s]")
except Exception as e:
    print(f"AGENT FAILED after {time.time()-t:.1f}s:", repr(e)[:400])
print("DIAG DONE")
