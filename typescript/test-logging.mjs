import assert from "node:assert/strict";
import { VERSION, WarmWinter } from "./dist/warmwinter.js";

assert.equal(VERSION, "0.3.0");

globalThis.fetch = async () => new Response(JSON.stringify({
  decision_id: "dec_test",
  verdict: "act",
  cell_state: "verified",
  calibrated_confidence: 0.91,
  stated_confidence: 0.82,
  stakes: "medium",
  reasons: [],
  cell: {},
}));

const lines = [];
const client = new WarmWinter({ apiKey: "ww_test", logger: (line) => lines.push(line) });
await client.decide({
  domain: "compute",
  decisionType: "model_route",
  statedConfidence: 0.82,
  context: { prompt: "TOP SECRET" },
  candidateAction: "private action",
});
assert.deepEqual(lines, ["[warmwinter] ACT | compute/model_route | verified | medium stakes"]);
assert.ok(!lines[0].includes("TOP SECRET"));
assert.ok(!lines[0].includes("private action"));

const silentLines = [];
const silent = new WarmWinter({
  apiKey: "ww_test",
  logVerdicts: false,
  logger: (line) => silentLines.push(line),
});
await silent.decide({
  domain: "compute",
  decisionType: "model_route",
  statedConfidence: 0.82,
});
assert.deepEqual(silentLines, []);

console.log("SDK 0.3.0 checks passed");
