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

Every decision prints a prompt-blind verdict line:

```text
[warmwinter] ACT | compute/model_route | verified | medium stakes
```

Only decision coordinates and gate metadata are logged—never prompts, context,
candidate actions, or outputs. Pass `logVerdicts: false` to silence it, or
`logger: (line) => appLogger.info(line)` to use your application logger.

Or drive the halves yourself with `decide(...)` / `outcome(...)`.

Seamless alternative: point your existing OpenAI/Anthropic client's `baseURL`
at the gateway and change nothing else — see https://warmwinter.io/gate.

## Native computational consultation

Requires SDK **0.3.0** or the current source checkout; published 0.2.0 does not
include these helpers. For source verification, build from `typescript/` with
`npm ci` and `npm run build` and import the local output below. For an accepted
registry release at 0.3.0 or later, import from `warmwinter` instead. Registry
availability follows the separately accepted release, not a source merge.

Use a consultation-only key explicitly granted by a signed-in human through the
existing key-management flow (`scopes: "consultation"` with `host_type` and
`host_ref`). Gate/observer keys do not gain consultation access. No automatic
grants or consultation hooks are installed.

```ts
import { WarmWinter } from "./dist/warmwinter.js";

const apiKey = process.env.WARMWINTER_CONSULTATION_KEY;
if (!apiKey) throw new Error("Set an explicitly granted consultation key");
const ww = new WarmWinter({ apiKey });
const capabilities = await ww.consultationCapabilities();
const reading = await ww.consultQueue({
  arrivalRate: 8, serviceCapacity: 10, rateUnit: "tasks/minute",
  sourceRef: "my-task:rates", usefulnessConfidence: 0.6,
  // taskRef: "my-task:capacity", runId: "existing-owned-run-id",
});
// Only after actually assessing this reading's usefulness:
// await ww.consultationFeedback(String(reading.consultation_id), "useful");
```

Inputs use camelCase; consultation responses keep the complete **snake_case**
server envelope, including future metadata. Units are `tasks/second`,
`tasks/minute` or `tasks/hour`. Optional task/run references do not create or
authenticate a host run. `usefulnessConfidence` forecasts usefulness, not input
certainty or authority. Feedback accepts `useful`, `already_known`, `incorrect`
or `missing_context`; it remains self-reported, not a verified task outcome.

Preserve assumptions, provenance, uncertainty, limits and advisory status when
using the reading. Overload pressure can be `null` with an explicit
`nonfinite_values` marker; it is not zero. Server denials (including revocation,
missing scope, invalid input and exhausted limits) throw the existing
`WarmWinterError`; there are no automatic retries or fallback Gate decisions.
Revocation blocks subsequent requests, without cancelling admitted requests or
erasing retained evidence.

Offline verification: `npm test` from `typescript/` (build, legacy logging tests
and consultation contracts).
