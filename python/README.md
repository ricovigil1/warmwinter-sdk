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

Or drive the two halves yourself with `decide(...)` and `outcome(...)`. See the
module docstring for the full surface.

Seamless alternative: point your existing OpenAI/Anthropic client's `base_url`
at the gateway and change nothing else — see https://warmwinter.io/gate.
