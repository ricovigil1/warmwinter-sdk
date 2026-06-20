# Warm Winter — Agent-reliability recipes

*Four first-class patterns for the live trust gate, each a worked example over the existing
SDK (`decide` / `outcome` / `guard`). These are the Tier-1 application surfaces in
`docs/APPLICATIONS.md` — the real product surface of the wedge: calibrated trust in an
**action**. Same engine, four shapes.*

The whole idea in one line: **wrap any AI action in a gate that says act / escalate / abstain,
then report what actually happened so the cell for that action type sharpens.**

Conventions used below:
- `domain` groups a product area (`"agent"`, `"rag"`, `"support"`); `decision_type` names the
  action. Free-form — your usage defines the ontology; the frontier is per `(domain ×
  decision_type)`.
- `stated_confidence` ∈ [0,1] is *your* model's confidence (a retrieval score, a CI signal, an
  LLM self-rated certainty). The gate recalibrates it against your verified outcomes.
- `stakes` shifts the bar: `"high"` demands a stronger cell before it says `act`, and makes an
  ungrounded cell **abstain** rather than escalate. Use it for irreversible actions.
- Report outcomes with `success` / `failure` (the cheap/proposed path was right / wrong) or
  `abstained` (you escalated — no probability to score).

```python
from warmwinter import WarmWinter
ww = WarmWinter(api_key="ww_...")        # mint at /api/v1/gate/keys
```

---

## 1 · RAG / answer grounding — "answer, or admit you don't know?"

The hallucination problem *as a trust gate.* Before letting the model answer from retrieved
context, ask whether the retrieval is grounded enough; if not, abstain (say "I don't know" or
hand off) instead of confabulating.

```python
def answer_with_rag(question):
    hits = retrieve(question)
    grounding = retrieval_score(hits)          # your confidence the context supports an answer

    d = ww.decide(domain="rag", decision_type="rag_answer",
                  stated_confidence=grounding, stakes="medium",
                  on_ungrounded="abstain")      # don't guess outside the frontier

    if d.verdict == "act":
        return generate(question, hits)         # grounded — answer
    return "I don't have a grounded answer for that."   # abstain / escalate to a human

# When you learn whether the answer held (a thumbs-down, a correction, an eval):
ww.outcome(decision_id, "success" if not user_corrected else "failure")
```

Outcome signal: was the answer right / did the user correct it. The most valuable behavior
here is the *abstention* — the cell that learns where your RAG is not trustworthy.

---

## 2 · Auto-merge / auto-deploy — "ship it unsupervised, or ask a human?"

The cleanest instrumented feedback that exists: CI tells you, automatically, whether the call
was right.

```python
def maybe_auto_merge(pr):
    confidence = ci_confidence(pr)             # tests green, diff size, risk heuristics → [0,1]

    merged = ww.guard(
        domain="agent", decision_type="auto_merge",
        stated_confidence=confidence, stakes="high",   # a bad merge is costly
        cheap=lambda: auto_merge(pr),                  # the trusted path
        escalate=lambda: request_human_review(pr),     # the safe fallback
        verify=lambda _r: ci_passes_on_main(pr) and not reverted_within(pr, days=2),
    )
    return merged
```

`guard` gates, runs the chosen path, and auto-reports: if it auto-merged and stayed green →
`success`; if it auto-merged and got reverted → `failure`; if it escalated → `abstained`. The
`auto_merge` cell only earns "verified" once your merges actually hold.

---

## 3 · Tool-call / action gate — "is this action safe to execute?"

For agents that take real-world actions (run code, send email, move money). Scale `stakes` to
reversibility; irreversible actions on an ungrounded cell should **abstain**.

```python
def run_tool(tool_name, args, agent_confidence):
    irreversible = tool_name in {"transfer_funds", "delete_resource", "send_email"}

    d = ww.decide(domain="agent", decision_type=f"tool:{tool_name}",
                  stated_confidence=agent_confidence,
                  stakes="high" if irreversible else "medium",
                  candidate_action=f"{tool_name}({args})",
                  on_ungrounded="abstain" if irreversible else None)

    if d.verdict == "act":
        result = execute(tool_name, args)
        ww.outcome(d.decision_id, "success" if action_succeeded(result) else "failure")
        return result
    return escalate_to_human(tool_name, args)   # escalate / abstain — never execute on a guess
```

Outcome signal: did the action succeed / was it reversed. Each tool gets its own cell, so the
agent earns autonomy *per tool*, exactly where it's been verified.

---

## 4 · Support-bot abstention — "auto-reply, or route to a human?"

Calibrated triage against the two failure modes of support automation: confidently wrong
auto-replies, and escalating everything (which defeats the point).

```python
def handle_ticket(ticket):
    draft, confidence = draft_reply(ticket)    # model's reply + its self-rated confidence

    return ww.guard(
        domain="support", decision_type="support_reply",
        stated_confidence=confidence, stakes="medium",
        cheap=lambda: send_reply(ticket, draft),       # auto-resolve
        escalate=lambda: route_to_human(ticket),       # safe fallback
        verify=lambda _r: not reopened(ticket) and csat(ticket) >= 4,
    )
```

Outcome signal: no escalation / CSAT. The `support_reply` cell learns which ticket types it can
safely auto-resolve, and which to always hand off.

---

## The pattern, abstracted

Every recipe is the same three moves:

1. **Score** — produce a `stated_confidence` from whatever signal you already have.
2. **Gate** — `decide`/`guard` returns `act` (proceed), `escalate` (stronger path / human), or
   `abstain` (don't act). `stakes` sets how strong the cell must be to earn `act`.
3. **Report** — `outcome` (or `guard`'s `verify`) binds what actually happened, so the cell for
   that action type sharpens. The verified record is the moat.

New use case? Pick a `decision_type`, wire a confidence in and an outcome out, and the gate does
the rest. See `docs/APPLICATIONS.md` for the Tier-2/3 surfaces we'll reach later.
