# Warm Winter SDK — the 5-minute quickstart

A thin wrapper around your AI/agent calls that answers one question before you
spend on the expensive path: **is this cheap answer trustworthy enough to act on
— or should you escalate, or abstain?** You keep executing; Warm Winter only
judges, learns from the reported outcome, and sharpens the competence frontier
for that kind of decision.

Two files, zero dependencies:

- `python/warmwinter.py` — stdlib `urllib`, drops into any Python 3.9+ project.
- `typescript/warmwinter.ts` — built-in `fetch`, Node 18+ / browser / edge.

**Looking for a specific use case?** See [`RECIPES.md`](RECIPES.md) — worked patterns for
RAG grounding, auto-merge/deploy, tool-call gating, and support-bot abstention.

---

## Live API base

The SDK defaults to **`https://api.warmwinter.io`** (the canonical, host-agnostic
endpoint). The service currently runs at `https://warmwinter-backend.onrender.com`, and
`api.warmwinter.io` is a CNAME to it — so once that DNS is live the default just works.

If you're trying it before the custom domain is set up (or self-hosting), point the SDK
at the backend explicitly:

```python
WarmWinter(api_key="ww_...", base_url="https://warmwinter-backend.onrender.com")
```
```ts
new WarmWinter({ apiKey: "ww_...", baseUrl: "https://warmwinter-backend.onrender.com" })
```

(First request may take ~50s if the free-tier server is asleep.)

---

## 1. Get a key

Log in, then mint a gate key (shown **once** — store it):

```bash
curl -X POST https://api.warmwinter.io/api/v1/gate/keys \
  -H "Authorization: Bearer $YOUR_JWT" \
  -H "Content-Type: application/json" \
  -d '{"label":"my-agent"}'
# → { "key": "ww_...", "id": "...", "key_prefix": "ww_abc123", ... }
```

List or revoke: `GET /api/v1/gate/keys`, `DELETE /api/v1/gate/keys/{id}`.

## 2. Gate a call (Python)

```python
from warmwinter import WarmWinter

ww = WarmWinter(api_key="ww_...")

d = ww.decide(domain="compute", decision_type="model_route",
              stated_confidence=0.82, stakes="medium")

if d.verdict == "act":          # the gate trusts the cheap path
    answer = small_model(prompt)
else:                            # "escalate" / "abstain"
    answer = big_model(prompt)   # …or a human

# when you learn whether it held, close the loop so the cell learns:
ww.outcome(d.decision_id, "success" if answer_was_good else "failure")
```

Or the whole loop in one call:

```python
answer = ww.guard(
    domain="compute", decision_type="model_route", stated_confidence=0.82,
    cheap=lambda: small_model(prompt),
    escalate=lambda: big_model(prompt),
    verify=lambda out: out is not None,   # your success test → auto-reports outcome
)
```

## 2b. Gate a call (TypeScript)

```ts
import { WarmWinter } from "./warmwinter";
const ww = new WarmWinter({ apiKey: "ww_..." });

const d = await ww.decide({
  domain: "compute", decisionType: "model_route",
  statedConfidence: 0.82, stakes: "medium",
});
const answer = d.verdict === "act" ? await smallModel(prompt) : await bigModel(prompt);
await ww.outcome(d.decisionId, answerWasGood ? "success" : "failure");
```

## 3. Backfill from existing logs (optional)

Already have routing decisions with known outcomes? Replay them in one batch to
warm up a real cell fast:

```bash
curl -X POST https://api.warmwinter.io/api/v1/gate/ingest/router \
  -H "X-Api-Key: ww_..." -H "Content-Type: application/json" \
  -d '{"rows":[{"domain":"compute","decision_type":"model_route","stated_confidence":0.8,"outcome":"success"}]}'
```

---

## How verdicts are decided

| cell state    | meaning                                              | low stakes | medium     | high stakes |
|---------------|------------------------------------------------------|------------|------------|-------------|
| `verified`    | calibrated, resolving, fresh — trust the cheap path  | **act**    | **act**    | **act**     |
| `provisional` | some signal, not yet callable                        | **act**    | escalate   | escalate    |
| `ungrounded`  | outside the frontier (thin or a known missing driver)| escalate   | escalate   | **abstain** |

Pass `on_ungrounded="abstain"` to force the cautious path at any stakes.

Every account starts **seeded from the backtest portfolio** (the verified compute
cell = 95% quality @ 57% cost, plus the energy / weather proof cells), so `decide`
is calibrated from request #1. As your own resolved outcomes accumulate, your
**live** cell for each `(domain × decision_type)` takes over from the seed — your
own verified record is what compounds; the seed is just the bridge. Read your map
any time: `GET /api/v1/gate/frontier` (or `ww.frontier()`).

We advise; your system executes. The gate never sits in your execution path.

---

## Install & try

```bash
pip install warmwinter        # Python
npm install warmwinter        # TypeScript / JavaScript
```

With a gate key (step 1 above), confirm it talks to the live gate:

```bash
python -c "from warmwinter import WarmWinter; print(WarmWinter(api_key='ww_...').frontier())"
```
