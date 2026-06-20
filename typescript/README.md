# warmwinter (TypeScript / JavaScript SDK)

The smallest wrapper around an AI/agent call that asks the one question the Warm
Winter gate exists to answer: **is this cheap answer trustworthy enough to act on
— or should we escalate, or abstain?** You keep executing; we only judge. Zero
runtime dependencies (built-in `fetch`; Node 18+ or any browser/edge runtime).

```bash
npm install warmwinter
```

```ts
import { WarmWinter } from "warmwinter";

const ww = new WarmWinter({ apiKey: "ww_..." });   // mint at /api/v1/gate/keys

const answer = await ww.guard({
  domain: "compute", decisionType: "model_route", statedConfidence: 0.82,
  cheap: () => smallModel(prompt),
  escalate: () => bigModel(prompt),
  verify: (out) => out != null,
});
```

Or drive the halves yourself with `decide(...)` / `outcome(...)`.

Seamless alternative: point your existing OpenAI/Anthropic client's `baseURL`
at the gateway and change nothing else — see https://warmwinter.io/gate.
