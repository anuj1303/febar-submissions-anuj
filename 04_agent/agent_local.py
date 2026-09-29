"""FE Bar — BrickJewels — Layer 4 Gen AI Agent (manual tool-calling loop).
Claude (Foundation Model API) + 6 governed UC-function tools executed via the SQL API.
This is the exact agent logic the app backend uses; it is grounded (tools only) and
action-capable. Runs locally and inside the Databricks App identically.
"""
import json, subprocess, os

CATALOG, SCHEMA = "anuj_vm_workspace_catalog", "febar_ml"
WAREHOUSE_ID = os.environ.get("BRICKJEWELS_WAREHOUSE_ID", "0f16ae8ffb7cdef3")
PROFILE = os.environ.get("DATABRICKS_PROFILE", "AnujLathi")
LLM = os.environ.get("BRICKJEWELS_LLM_ENDPOINT", "febar-claude-governed")  # AI Gateway-governed

SYSTEM = (
    "You are the BrickJewels growth & merchandising concierge for a D2C fine-jewelry retailer. "
    "Always use the tools to ground answers in real data — never invent product names, prices, "
    "propensity scores, segments or customer facts. For a specific customer, look up their propensity "
    "and profile and recommend the best offer with a one-line rationale. For catalog questions use "
    "search_products; for business questions use get_category_performance. Be concise and business-ready."
)

# Tool schemas (positional arg order matters for SQL invocation)
TOOLS = [
    ("get_customer_propensity", "Get a customer's Next-Best-Offer propensity, segment and decile.",
     [("p_user_id", "integer", "customer id")]),
    ("get_customer_profile", "Get a customer's behavioral profile (RFM, diamond affinity, engagement, anniversary proximity).",
     [("p_user_id", "integer", "customer id")]),
    ("recommend_next_best_offer", "Recommend the best offer for a customer with a rationale.",
     [("p_user_id", "integer", "customer id")]),
    ("get_top_prospects", "Top-N highest-propensity customers in a segment (High/Medium/Low).",
     [("p_segment", "string", "High, Medium or Low"), ("p_limit", "integer", "how many")]),
    ("search_products", "Search the jewelry catalog by free text (name/description/tags).",
     [("p_query", "string", "free-text product query")]),
    ("get_category_performance", "Sales performance for a jewelry category.",
     [("p_category", "string", "category e.g. Necklace")]),
]


def _tool_specs():
    specs = []
    for name, desc, params in TOOLS:
        props = {p: {"type": t, "description": d} for p, t, d in params}
        specs.append({"type": "function", "function": {
            "name": name, "description": desc,
            "parameters": {"type": "object", "properties": props,
                           "required": [p for p, _, _ in params]}}})
    return specs


_PARAM_ORDER = {name: [p for p, _, _ in params] for name, _, params in TOOLS}
_PARAM_TYPE = {name: {p: t for p, t, _ in params} for name, _, params in TOOLS}


def _host_token():
    host = subprocess.run(["databricks", "auth", "env", "--profile", PROFILE],
                          capture_output=True, text=True).stdout
    host = json.loads(host)["env"]["DATABRICKS_HOST"]
    tok = json.loads(subprocess.run(["databricks", "auth", "token", "--profile", PROFILE],
                                    capture_output=True, text=True).stdout)["access_token"]
    return host, tok


def _sql(stmt):
    payload = json.dumps({"statement": stmt, "warehouse_id": WAREHOUSE_ID,
                          "format": "JSON_ARRAY", "wait_timeout": "50s"})
    out = subprocess.run(["databricks", "api", "post", "/api/2.0/sql/statements/",
                          "--json", payload, "--profile", PROFILE],
                         capture_output=True, text=True).stdout
    d = json.loads(out)
    cols = [c["name"] for c in d.get("manifest", {}).get("schema", {}).get("columns", [])]
    rows = d.get("result", {}).get("data_array", []) or []
    return [dict(zip(cols, r)) for r in rows]


def _run_tool(name, args):
    vals = []
    for p in _PARAM_ORDER[name]:
        v = args.get(p)
        if _PARAM_TYPE[name][p] == "string":
            vals.append("'" + str(v).replace("'", "''") + "'")
        else:
            vals.append(str(int(v)))
    return _sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.{name}({', '.join(vals)})")


def _chat(host, tok, messages):
    import time
    payload = json.dumps({"messages": messages, "tools": _tool_specs(),
                          "tool_choice": "auto", "max_tokens": 1024})
    for attempt in range(5):  # retry through transient errors / gateway rate limits
        out = subprocess.run(["curl", "-s", "-m", "60",
                              f"{host}/serving-endpoints/{LLM}/invocations",
                              "-H", f"Authorization: Bearer {tok}",
                              "-H", "Content-Type: application/json", "-d", payload],
                             capture_output=True, text=True).stdout
        try:
            return json.loads(out)["choices"][0]["message"]
        except Exception:
            if attempt == 4:
                raise RuntimeError(f"chat failed: {out[:200]}")
            time.sleep(4 * (attempt + 1))


def ask(question, user_id=None, verbose=False):
    host, tok = _host_token()
    if user_id is not None:
        question = f"[customer user_id={int(user_id)}] {question}"
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    for _ in range(6):  # bounded tool-calling loop
        msg = _chat(host, tok, messages)
        calls = msg.get("tool_calls") or []
        if not calls:
            return msg.get("content", "")
        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
        for c in calls:
            name = c["function"]["name"]
            args = json.loads(c["function"]["arguments"] or "{}")
            result = _run_tool(name, args)
            if verbose:
                print(f"  · tool {name}({args}) -> {json.dumps(result)[:200]}")
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(result, default=str)})
    return "(stopped: tool loop limit)"


if __name__ == "__main__":
    for q, uid in [("What is the single best offer for this customer and why?", 350),
                   ("Show me two diamond necklaces we sell.", None),
                   ("Give me the top 3 prospects to target and the Necklace category performance.", None)]:
        print(f"\n=== Q: {q} (user_id={uid}) ===")
        print(ask(q, uid, verbose=True))
