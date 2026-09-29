"""FE Bar — BrickJewels — Layer 4 (Gen AI Agent), models-from-code definition.
A LangGraph tool-calling agent over the 6 governed UC-function tools, using Claude via
the Foundation Model API. Grounded (tools only), action-capable, servable as pyfunc."""
import mlflow
import pandas as pd
from databricks_langchain import ChatDatabricks
try:
    from databricks_langchain import UCFunctionToolkit
except Exception:  # fallback for older package layout
    from unitycatalog.ai.langchain.toolkit import UCFunctionToolkit
from langgraph.prebuilt import create_react_agent

CATALOG, SCHEMA = "anuj_vm_workspace_catalog", "febar_ml"
LLM_ENDPOINT = "databricks-claude-sonnet-4-6"
FUNCS = [f"{CATALOG}.{SCHEMA}.{n}" for n in [
    "get_customer_propensity", "get_customer_profile", "recommend_next_best_offer",
    "get_top_prospects", "search_products", "get_category_performance"]]

SYSTEM_PROMPT = (
    "You are the BrickJewels growth & merchandising concierge for a D2C fine-jewelry retailer. "
    "Always use the provided tools to ground answers in real data — never invent product names, "
    "prices, propensity scores, segments, or customer facts. For a specific customer, look up their "
    "propensity and profile and recommend the best offer with a one-line rationale. For catalog "
    "questions, search products. For business questions, use category performance. "
    "Answer concisely in business-ready language; if a tool returns nothing, say so plainly."
)


class BrickJewelsAgent(mlflow.pyfunc.PythonModel):
    def load_context(self, context):
        self.llm = ChatDatabricks(endpoint=LLM_ENDPOINT)
        self.tools = UCFunctionToolkit(function_names=FUNCS).tools
        self.agent = create_react_agent(self.llm, self.tools)

    def _ask(self, question: str, user_id=None) -> str:
        if user_id is not None and str(user_id).lower() not in ("nan", "none", ""):
            question = f"[customer user_id={int(float(user_id))}] {question}"
        msgs = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question}]
        result = self.agent.invoke({"messages": msgs})
        return result["messages"][-1].content

    def predict(self, context, model_input):
        if isinstance(model_input, dict):
            model_input = pd.DataFrame([model_input])
        uid_col = "user_id" in model_input.columns
        return [self._ask(row["question"], row["user_id"] if uid_col else None)
                for _, row in model_input.iterrows()]


mlflow.models.set_model(BrickJewelsAgent())
