# BrickJewels — FE Bar AI Demo Roleplay Script

**Presenter:** Anuj Lathi · **Duration target:** ~17–18 min (hard cap 20)
**Room:** two stakeholders — **Priya, VP Growth / Chief Digital Officer** (business sponsor, funds the decision) and **Rahul, Head of Data & Platform** (technical owner who has to live with the build).
**Delivery note:** one-sided walkthrough — deliver straight through. Altitude cues in *[italics]* tell you when to speak to the business sponsor vs. the technical owner. Time budgets are per section; keep pace and you land at ~18 minutes.

---

## 0 · Demo setup — frame it before diving in  *(~1.5 min)*

Priya, Rahul — thank you both for the time. Let me set the stage in one breath, then show you something working.

You run a direct-to-consumer fine-jewelry business — think Tanishq or CaratLane scale. Three things make growth hard in your world, and they're specific to jewelry, not generic retail. First, **discovery is high-consideration and visual** — a customer doesn't search "SKU-4471," she says "a diamond pendant for my anniversary under two lakh." Second, **your pricing moves every day** because it's pegged to live gold and silver rates — get that wrong and you either lose the sale or lose the margin. Third, **repeat purchase is occasion-driven** — anniversaries, birthdays, weddings, festival buying — and today your team blasts the same offer to everyone and hopes.

What I've built is one integrated platform I call the **Growth Concierge**. In the next fifteen minutes I'll show you a single customer journey running end to end — raw data all the way to a live app — and I'll be explicit about the business outcome at each step. I'm going to show, not tell. Let's start with why this matters to the P&L.

---

## 1 · Lead with the outcome  *(~1.5 min)*

*[To Priya — executive altitude, money first.]*

Here's the headline. You have roughly **23,400 active customers**, and on this book the **average customer lifetime value is about ₹16.6 lakh** — so we're talking about a customer book worth on the order of **₹3,900 crore in lifetime value**. Today your marketing spend is sprayed across all 23,400 more or less evenly.

My model says that's the wrong allocation. It identifies that only about **4,700 customers are genuinely high-intent right now**, and about **9,400 will not respond at all** to an offer this cycle. So we're spending discount margin on people who won't convert, and under-serving the ones who would.

The outcome: by concentrating spend on the high-propensity customers — where my targeting is **97% precise** — and suppressing the dead-weight third, you lift campaign ROI and protect margin. To put a number on it, with clearly stated assumptions: **even a one-percentage-point improvement in repeat-purchase rate across that lifetime-value book is about ₹39 crore in incremental lifetime revenue.** The whole point of this build is to capture a multiple of that. Now let me show you how it actually works.

---

## 2 · The golden thread  *(~1 min)*

*[Neutral altitude — orient both personas.]*

Everything you're about to see follows **one thread**: a real, traceable customer segment — *anniversary-window shoppers with a diamond affinity and high-value items sitting abandoned in their cart.* You'll watch that exact cohort flow through every layer: raw events become governed features, features become a model score, the score drives an agent's action, the business team can ask about it in plain English, and it all surfaces in one app. It is one journey, not six disconnected demos — and that integration is the thing that makes it real.

---

## 3 · The governed data foundation  *(~2 min)*

*[To Rahul — technical altitude, but keep Priya oriented.]*

Rahul, this is for you. It all sits on **one Unity Catalog catalog** with a proper medallion architecture — Bronze, Silver, Gold. Let me show the Gold feature table.

**[SHOW]** `febar_gold.customer_features` — **23,391 customers**, each with RFM signals, category and metal affinity, cart and wishlist behavior, and occasion proximity like days-to-anniversary. This is the single source of truth every downstream layer reads.

**[SHOW]** Data quality is enforced, not assumed. My Silver layer ran **216,485 clean orders** through declarative quality expectations, with any rule violation routed to a quarantine table — so bad data never silently poisons a model score.

**[SHOW]** And it's governed. The customer dimension carries **column masks on email and phone** and a **row filter by region**, so an analyst sees masked PII while an admin sees clear — enforced at the catalog, not bolted on in the app.

*[One line up to Priya.]* Priya, the reason this matters to you: this is the difference between a demo and something you can actually put customer data into. Governance and lineage are built in from the raw layer, so this is auditable and safe by construction.

---

## 4 · The intelligence — turning guesswork into a model  *(~3 min)*

*[Back to Priya's altitude — this is the core business redesign — with technical proof for Rahul.]*

This is the heart of it. Your nudge engine today is rule-based — "send everyone a 10% anniversary offer." I replaced the guesswork with a real machine-learning model: a **Next-Best-Offer propensity model** that predicts, per customer, the probability they'll convert on a targeted offer.

**[SHOW]** The model is trained with LightGBM, logged to MLflow, and registered in Unity Catalog. On held-out data it scores a **PR-AUC of 0.84 against a base rate of 0.46** — so it's materially better than chance — with a **ROC of 0.85** and, most importantly for you, **97% precision in the top decile.** That top-decile number is the business lever: when we target the top tier, 97% of them are genuine.

**[SHOW]** Here's the model's output committed across the whole base: **4,678 customers scored High** with an average score of 0.92, **9,356 Medium**, and **9,357 Low** at 0.13. That is your spend map. Concentrate on the High tier, nurture the Medium, stop wasting margin on the Low.

*[To Rahul — prove it's live, not a slide.]* Rahul, this isn't a static table. The model is behind a **live serving endpoint**. I just called it in real time for customer 350 — a top-tier anniversary shopper — and it returned a propensity of **0.9993**, which matches the batch score exactly. Real-time, batch, and the agent all read the same model. One model, three consumption paths, consistent answers.

**[SHOW]** And it's explainable — no black box. **SHAP** tells us the top drivers are purchase **frequency, recency, monetary value, wishlist count, and diamond affinity**. So when the app says "target this customer," it can also say *why* — which is exactly what a merchandiser needs to trust it.

---

## 5 · The agent that acts  *(~2.5 min)*

*[Neutral-to-technical altitude.]*

A score is only useful if something acts on it. So the assistant in this platform is a **Gen AI agent**, not a chatbot wrapper. It's grounded in your data and it takes action through **six governed Unity Catalog function tools** — real, permissioned SQL functions, not free-text guessing.

**[SHOW]** For example, the agent can call `get_top_prospects` and pull the highest-propensity customers live — here it returns the top High-segment customers with scores above 0.998. It can look up a customer's profile, recommend the next best offer, and search the product catalog semantically. Every one of those tools is governed by Unity Catalog permissions, so the agent can only ever do what it's authorized to do.

**[SHOW]** And I evaluated it properly with MLflow — on a curated question set it scores **0.8 on groundedness, 0.8 on correctness, and 1.0 on safety.** I'm not asking you to trust the vibes; I measured it.

*[To Rahul — the governance point he'll care about most.]* Rahul, one thing I want to flag because I know you'll ask about it: every LLM call in this system routes through **my own governed model endpoint behind AI Gateway.** That gives us usage tracking, inference logging to a table, a per-user rate limit, and a **PII guardrail that blocks** things like credit-card and Aadhaar numbers before they ever reach the model. So when your CISO asks "what stops this thing from leaking a customer's data" — the answer is a hard guardrail at the gateway, not a policy document.

---

## 6 · Self-serve for the business team  *(~1.5 min)*

*[To Priya — she owns this outcome.]*

Priya, your growth team shouldn't have to file a ticket to ask a question. So the same Gold data is exposed through **Genie** — natural-language BI — sitting on **governed metric views** so everyone gets the *same* definition of revenue, margin, and conversion. No two dashboards disagreeing in a meeting.

**[SHOW]** Live, the metric view reports **total revenue of about ₹3,890 crore, 485,000 units, and a 68% diamond mix.** Your merchandiser can just type "how did diamond sales trend this quarter" and get a governed, consistent answer — no analyst in the loop, no metric drift.

---

## 7 · Where it all lands — the app  *(~1 min)*

*[Neutral altitude — the payoff surface.]*

All of this converges in **one Databricks App — the Growth Concierge — deployed and running.** It serves two audiences from one build. For the shopper: conversational, occasion-aware discovery. For your growth owner: a console that shows each customer's propensity, their profile, and the SHAP "why" behind every recommendation — so they act with confidence.

**[SHOW]** It's identity-aware and OAuth-gated, so who you are decides what you see — the same governance we built at the data layer, carried all the way to the screen.

---

## 8 · Value recap — assumptions on the table  *(~2 min)*

*[To Priya — land the money, be honest about assumptions.]*

So let me bring it back to the P&L, and I'll be explicit about my assumptions so you can pressure-test them.

- **Concentration.** Today: offers sprayed across 23,400 customers. Now: precisely targeted at the ~4,700 high-propensity customers at 97% precision, with the ~9,400 low-propensity customers suppressed. That's less discount leakage and higher conversion per rupee spent.
- **The number.** On a lifetime-value book of about ₹3,900 crore, my stated assumption is that better targeting lifts repeat-purchase rate by at least one percentage point. **That alone is roughly ₹39 crore in incremental lifetime revenue** — and top-decile precision this high is designed to deliver several points, not one.
- **Margin protection.** Suppressing offers to the 9,400 who won't convert stops discount margin from walking out the door on customers who'd never have bought — pure savings.
- **Speed.** Because it's all one governed platform, your team asks questions in plain English and acts the same day, instead of waiting on a reporting backlog.

Better discovery lifts conversion; live governed pricing protects margin; the propensity model lifts repeat purchase; self-serve BI speeds decisions. That's the value chain, end to end.

---

## 9 · Close  *(~1 min)*

*[Both personas — confident, specific ask.]*

To summarize: this is one integrated, governed journey — raw jewelry data, through a medallion lakehouse, made intelligent with a propensity model, made actionable by a governed agent, made self-serve through Genie, and surfaced in a live app. It is real ML with measured performance, real governance with a hard PII guardrail, and a clear line to incremental revenue and protected margin.

Priya, the ask is a **focused pilot on your next anniversary campaign** — target the High decile, suppress the Low, and we measure the lift against a holdout. Rahul, everything you saw runs on your existing Databricks platform with governance built in from the raw layer, so there's no new stack to stand up. I'd love to run that pilot and bring you the numbers. Thank you.

---

# Appendix — anticipated objections (not part of the 20-min run)

*Use only if the personas do push back. Each answer is ~20 seconds.*

**Business — "Isn't this just a fancy dashboard?"**
No — a dashboard reports the past. This predicts who to act on next and the agent takes the action. The model output changes what your team does tomorrow morning, not just what they look at.

**Business — "How do I trust numbers built on synthetic data?"**
The data is synthetic by design so nothing customer-identifying is exposed, but the *pipeline is real* — the same model, governance, and endpoints run identically on your production data. We prove the mechanism here and point it at your data in the pilot.

**Business — "What's the actual ROI and how fast?"**
The one-point-of-repeat-rate assumption is ~₹39 crore of lifetime revenue; the pilot measures real lift against a holdout in a single campaign cycle, so you see signal in weeks, not quarters.

**Technical — "Why not just prompt an LLM with the data?"**
Because that's ungrounded and unauditable. Here the agent only acts through six permissioned UC functions, every call is logged through AI Gateway, and I have MLflow eval scores — groundedness 0.8, safety 1.0. It's governed and measured.

**Technical — "How do you handle data quality and drift?"**
DQ expectations quarantine bad rows before they reach a model — 216,485 clean orders, zero bad rows leaked. And Lakehouse Monitoring generates profile metrics on the scored table so we catch drift after go-live.

**Technical — "What about PII and security?"**
Column masks and row filters at the catalog, OAuth identity-aware access to the app, and a PII guardrail at the gateway that blocks card and Aadhaar numbers before they reach the model. Governance is enforced by the platform, not by convention.
