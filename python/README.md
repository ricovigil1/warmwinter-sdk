# warmwinter (Python SDK)

The smallest wrapper around an AI/agent call that asks the one question the Warm
Winter gate exists to answer: **is this cheap answer trustworthy enough to act on
— or should we escalate, or abstain?** You keep executing; we only judge. Zero
dependencies (stdlib `urllib`).

```bash
pip install warmwinter
```

```python
from warmwinter import WarmWinter

ww = WarmWinter(api_key="ww_...")          # mint at /api/v1/gate/keys

# one call gates, runs the chosen path, and auto-reports the outcome
answer = ww.guard(
    domain="compute", decision_type="model_route", stated_confidence=0.82,
    cheap=lambda: small_model(prompt),
    escalate=lambda: big_model(prompt),
    verify=lambda out: out is not None,     # your success test
)
```

Every decision prints a prompt-blind verdict line:

```text
[warmwinter] ACT | compute/model_route | verified | medium stakes
```

Only decision coordinates and gate metadata are logged—never prompts, context,
candidate actions, or outputs. Pass `log_verdicts=False` to silence it, or
`logger=my_logger.info` to use your application logger.

Or drive the two halves yourself with `decide(...)` and `outcome(...)`. See the
module docstring for the full surface.

Seamless alternative: point your existing OpenAI/Anthropic client's `base_url`
at the gateway and change nothing else — see https://warmwinter.io/gate.

## Native computational consultation (source only)

These helpers are in this repository's source and are **not included in the
published 0.2.0 package**. From `python/`, run the source module directly. A future
release needs its own reviewed version and publishing decision.

Use a consultation-only key explicitly granted by a signed-in human through the
existing key-management flow (`scopes: "consultation"` with `host_type` and
`host_ref`). Existing Gate/observer keys do not gain consultation access. Keep the
key in your environment; these helpers do not mint grants or enable automatic
consultation.

```python
import os
from warmwinter import WarmWinter

ww = WarmWinter(api_key=os.environ["WARMWINTER_CONSULTATION_KEY"])
capabilities = ww.consultation_capabilities()
reading = ww.consult_queue(
    arrival_rate=8.0, service_capacity=10.0, rate_unit="tasks/minute",
    source_ref="my-task:rates", usefulness_confidence=0.6,
    # task_ref="my-task:capacity", run_id="existing-owned-run-id",
)
# Only after actually assessing this reading's usefulness:
# ww.consultation_feedback(reading["consultation_id"], "useful")
```

Units are `tasks/second`, `tasks/minute` or `tasks/hour`. Optional task/run
references are preserved; creating or authenticating a run remains a separate
host flow. `usefulness_confidence` forecasts usefulness, not input certainty or
authority. Feedback accepts `useful`, `already_known`, `incorrect` or
`missing_context`; it remains self-reported and does not verify a task outcome.

Responses retain the complete server envelope: assumptions, units, provenance,
unknown uncertainty, limits, advisory status and pending independent outcome.
Overload pressure can be `None` with an explicit `nonfinite_values` marker; do not
interpret it as zero. Server denials (including revocation, missing scope, invalid
input and exhausted limits) raise the existing `WarmWinterError`; helpers do not
retry or fall back to ordinary Gate decisions. A revoked key blocks subsequent
requests but does not cancel an admitted request or erase retained evidence.

Offline verification: `python -m unittest discover -v` from `python/`.
