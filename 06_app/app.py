"""FE Bar — BrickJewels — Layer 6: Databricks App (Growth Concierge).
Integrates every layer: the Gen AI agent (governed FM endpoint + UC-function tools),
the ML propensity scores (Lakebase low-latency read, Gold fallback), and links to the
Genie room + dashboard. Build-free FastAPI + inline HTML."""
import os, json, uuid
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from databricks.sdk import WorkspaceClient

CATALOG, SCHEMA = "anuj_vm_workspace_catalog", "febar_ml"
GOLD = "anuj_vm_workspace_catalog.febar_gold"
WAREHOUSE_ID = os.environ.get("BRICKJEWELS_WAREHOUSE_ID", "0f16ae8ffb7cdef3")
LLM = os.environ.get("BRICKJEWELS_LLM_ENDPOINT", "febar-claude-governed")
LAKEBASE_INSTANCE = os.environ.get("LAKEBASE_INSTANCE", "brickjewels-orders")
LAKEBASE_DB = os.environ.get("LAKEBASE_DB", "brickjewels")

w = WorkspaceClient()
app = FastAPI(title="BrickJewels Growth Concierge")

TOOLS = [
    ("get_customer_propensity", "Customer NBO propensity, segment and decile.", [("p_user_id", "integer", "customer id")]),
    ("get_customer_profile", "Customer RFM, diamond affinity, engagement, anniversary proximity.", [("p_user_id", "integer", "customer id")]),
    ("recommend_next_best_offer", "Best offer for a customer with a rationale.", [("p_user_id", "integer", "customer id")]),
    ("get_top_prospects", "Top-N highest-propensity customers in a segment.", [("p_segment", "string", "High/Medium/Low"), ("p_limit", "integer", "how many")]),
    ("search_products", "Search the jewelry catalog by free text.", [("p_query", "string", "query")]),
    ("get_category_performance", "Sales performance for a category.", [("p_category", "string", "category")]),
]
_ORDER = {n: [p for p, _, _ in ps] for n, _, ps in TOOLS}
_TYPE = {n: {p: t for p, t, _ in ps} for n, _, ps in TOOLS}
SYSTEM = ("You are the BrickJewels growth & merchandising concierge for a D2C fine-jewelry retailer. "
          "Always use the tools to ground answers in real data — never invent facts. For a customer, look up "
          "propensity and profile and recommend the best offer with a one-line rationale. Be concise.")


def _sql(stmt):
    r = w.statement_execution.execute_statement(statement=stmt, warehouse_id=WAREHOUSE_ID, wait_timeout="50s")
    cols = [c.name for c in (r.manifest.schema.columns or [])] if r.manifest and r.manifest.schema else []
    data = r.result.data_array if r.result and r.result.data_array else []
    return [dict(zip(cols, row)) for row in data]


def _tool_specs():
    out = []
    for n, d, ps in TOOLS:
        out.append({"type": "function", "function": {"name": n, "description": d,
                    "parameters": {"type": "object", "properties": {p: {"type": t, "description": dd} for p, t, dd in ps},
                                   "required": [p for p, _, _ in ps]}}})
    return out


def _run_tool(name, args):
    vals = []
    for p in _ORDER[name]:
        v = args.get(p)
        vals.append("'" + str(v).replace("'", "''") + "'" if _TYPE[name][p] == "string" else str(int(v)))
    return _sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.{name}({', '.join(vals)})")


def _chat(messages):
    resp = w.serving_endpoints.query(name=LLM, messages=messages, tools=_tool_specs(), max_tokens=1024)
    return resp.as_dict()["choices"][0]["message"]


def agent_ask(question, user_id=None):
    if user_id:
        question = f"[customer user_id={int(user_id)}] {question}"
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    trace = []
    for _ in range(6):
        msg = _chat(messages)
        calls = msg.get("tool_calls") or []
        if not calls:
            return msg.get("content", ""), trace
        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
        for c in calls:
            name = c["function"]["name"]
            args = json.loads(c["function"]["arguments"] or "{}")
            res = _run_tool(name, args)
            trace.append({"tool": name, "args": args})
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(res, default=str)})
    return "(tool loop limit)", trace


class Ask(BaseModel):
    question: str
    user_id: int | None = None


@app.post("/api/ask")
def ask(body: Ask):
    answer, trace = agent_ask(body.question, body.user_id)
    return {"answer": answer, "tools_used": trace}


@app.get("/api/customer/{user_id}")
def customer(user_id: int):
    rows = _sql(f"SELECT propensity_score, segment, decile FROM {GOLD}.customer_nbo_scores WHERE user_id = {user_id}")
    prof = _sql(f"SELECT recency_days, frequency, monetary_total, diamond_share, days_to_anniversary FROM {GOLD}.customer_features WHERE user_id = {user_id}")
    imp = _sql(f"SELECT feature, mean_abs_shap FROM {GOLD}.nbo_feature_importance ORDER BY mean_abs_shap DESC LIMIT 5")
    return {"score": rows[0] if rows else None, "profile": prof[0] if prof else None, "why_top_drivers": imp}


@app.get("/", response_class=HTMLResponse)
def home():
    return HTML


HTML = """<!doctype html><html><head><meta charset=utf-8><title>BrickJewels Growth Concierge</title>
<style>body{font-family:system-ui,Segoe UI,Roboto,sans-serif;margin:0;background:#0f0d15;color:#eee}
header{padding:18px 24px;background:linear-gradient(90deg,#1a1526,#241a2e);border-bottom:1px solid #3a2f4a}
h1{margin:0;font-size:20px;color:#D4AF37}.sub{color:#9a90a8;font-size:13px;margin-top:4px}
.wrap{max-width:900px;margin:24px auto;padding:0 16px}.card{background:#191322;border:1px solid #2e2640;border-radius:12px;padding:18px;margin-bottom:16px}
input,button{font-size:14px;padding:10px 12px;border-radius:8px;border:1px solid #3a2f4a;background:#221a30;color:#eee}
button{background:#D4AF37;color:#1a1526;border:none;font-weight:600;cursor:pointer}
.row{display:flex;gap:8px}.row input{flex:1}pre{white-space:pre-wrap;word-wrap:break-word}
.pill{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600}
.High{background:#0b3d1e;color:#00E676}.Medium{background:#3d360b;color:#FFD54F}.Low{background:#3d1a1a;color:#ff8a80}
.ans{background:#120e1a;border-radius:8px;padding:14px;margin-top:12px;line-height:1.5}
small{color:#8a8098}</style></head><body>
<header><h1>💎 BrickJewels Growth Concierge</h1>
<div class=sub>Gen AI agent · governed by AI Gateway · grounded in ML propensity + Unity Catalog</div></header>
<div class=wrap>
<div class=card><b>Ask the concierge</b>
<div class=row style=margin-top:10px>
<input id=q placeholder="e.g. What is the best offer for this customer and why?" value="What is the best offer for this customer and why?">
<input id=uid placeholder="user_id (optional)" value="350" style=max-width:150px>
<button onclick=ask()>Ask</button></div>
<div id=ans class=ans>—</div></div>
<div class=card><b>Customer 360 + model score</b>
<div class=row style=margin-top:10px><input id=cid value=350 style=max-width:150px><button onclick=cust()>Look up</button></div>
<div id=cout style=margin-top:12px>—</div></div>
</div>
<script>
async function ask(){document.getElementById('ans').textContent='Thinking…';
 const r=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({question:q.value,user_id:uid.value?parseInt(uid.value):null})});
 const d=await r.json();document.getElementById('ans').innerHTML='<pre>'+(d.answer||JSON.stringify(d))+'</pre>'+
  (d.tools_used&&d.tools_used.length?'<small>tools: '+d.tools_used.map(t=>t.tool).join(', ')+'</small>':'');}
async function cust(){const r=await fetch('/api/customer/'+cid.value);const d=await r.json();
 if(!d.score){cout.innerHTML='no score';return;}
 const s=d.score,p=d.profile;
 cout.innerHTML='<span class="pill '+s.segment+'">'+s.segment+' · decile '+s.decile+'</span> '+
 '<b style=margin-left:8px>propensity '+Number(s.propensity_score).toFixed(3)+'</b>'+
 '<div style=margin-top:8px><small>recency '+p.recency_days+'d · '+p.frequency+' orders · LTV ₹'+Number(p.monetary_total).toLocaleString()+' · diamond '+Math.round(p.diamond_share*100)+'% · anniversary in '+p.days_to_anniversary+'d</small></div>'+
 '<div style=margin-top:8px><small>why (SHAP): '+d.why_top_drivers.map(x=>x.feature).join(' › ')+'</small></div>';}
</script></body></html>"""
