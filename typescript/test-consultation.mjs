import assert from "node:assert/strict";
import fs from "node:fs";
import { test } from "node:test";
import { WarmWinter, WarmWinterError } from "./dist/warmwinter.js";

const fixture = JSON.parse(fs.readFileSync(new URL("../fixtures/consultation.json", import.meta.url), "utf8"));
const base = "https://sdk-test.invalid";

function setup(t, response = fixture.reading, status = 200) {
  const calls = [];
  const lines = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.ok(url.startsWith(base + "/"));
    assert.equal(options.headers["X-Api-Key"], "synthetic-test-key");
    calls.push({ method: options.method, url, body: options.body ? JSON.parse(options.body) : null });
    return new Response(JSON.stringify(response), { status });
  });
  const client = new WarmWinter({ apiKey: "synthetic-test-key", baseUrl: base, logger: line => lines.push(line) });
  return { calls, lines, client };
}

const args = { arrivalRate: 8, serviceCapacity: 10, rateUnit: "tasks/minute", sourceRef: "synthetic:rates", usefulnessConfidence: 0.6 };

test("retained consultation reads preserve grant scope and encode the ID", async t => {
  const {client,calls}=setup(t);
  await client.consultation("reading/with space");
  assert.equal(calls[0].method,"GET");
  assert.equal(calls[0].url,base+"/api/v1/gate/consultations/reading%2Fwith%20space");
});

test("discovery uses explicit key and preserves limits", async t => {
  const { client, calls } = setup(t, fixture.capabilities);
  assert.deepEqual(await client.consultationCapabilities(), fixture.capabilities);
  assert.deepEqual(calls, [{ method: "GET", url: base + "/api/v1/gate/consultations/capabilities", body: null }]);
});

test("queue wire matches Python and preserves the complete advisory envelope", async t => {
  const { client, calls, lines } = setup(t);
  const reading = await client.consultQueue({ ...args, taskRef: "synthetic:task", runId: "synthetic-run" });
  assert.deepEqual(calls, [{ method: "POST", url: base + "/api/v1/gate/consultations", body: fixture.request }]);
  assert.deepEqual(reading, fixture.reading);
  assert.equal(reading.authority_granted, false);
  assert.equal(reading.outcome_status, "pending_independent_outcome");
  assert.deepEqual(lines, []);
});

test("optional lineage is null without creating an identity", async t => {
  const { client, calls } = setup(t);
  await client.consultQueue(args);
  assert.deepEqual(calls[0].body, { ...fixture.request, task_ref: null, run_id: null });
});

test("overload null, unknown uncertainty and extensions survive", async t => {
  const reading = structuredClone(fixture.reading);
  Object.assign(reading.analysis, { utilization: 1, pressure: null, regime: "overloaded", queue_stable: false,
    nonfinite_values: { pressure: "positive_infinity" } });
  reading.future_metadata = { unknown: null };
  const { client, lines } = setup(t, reading);
  assert.deepEqual(await client.consultQueue(args), reading);
  assert.deepEqual(lines, []);
});

test("all seven consultation helpers preserve the exact wire capability and optional lineage", async t => {
  const { client, calls, lines } = setup(t);
  const common = { sourceRef: "synthetic:parity", usefulnessConfidence: 0.7 };
  const cases = [
    ["conservation-balance", () => client.consultConservation({
      inflows: [2], outflows: [1], generation: [], consumption: [],
      rateUnit: "items/hour", ...common,
    })],
    ["empirical-tail-risk", () => client.consultTailRisk({
      losses: [1, 3, 5], alpha: 0.9, lossUnit: "seconds", sampleBasis: "hypothesis", ...common,
    })],
    ["cohort-calibration", () => client.consultCalibration({
      pairs: [{ confidence: 0.8, outcome: 1 }], cohortRef: "cohort:test",
      sampleBasis: "hypothesis", ...common,
    })],
    ["value-of-information", () => client.consultValueOfInformation({
      branches: [{ branch_ref: "evidence:a", probability: 1, best_utility: 10 }],
      currentBestUtility: 8, evidenceCost: 1, utilityUnit: "utility_points",
      scenarioRef: "scenario:test", scenarioBasis: "hypothesis", ...common,
    })],
    ["scenario-risk-comparison", () => client.consultScenarios({
      scenarios: [{ scenario_ref: "base", losses: [2], overhead_loss: 0 },
                  { scenario_ref: "alt", losses: [1], overhead_loss: 1 }],
      baselineRef: "base", horizonRef: "horizon:task", alpha: 0.9,
      lossUnit: "seconds", scenarioBasis: "hypothesis",
      generatingModelRef: "not_applicable", generatingModelVersion: "not_applicable",
      generatingSeed: null, ...common,
    })],
    ["resolution-time", () => client.consultResolutionTime({
      observations: [{ case_ref: "case:a", duration: 1.5, event: 1 }],
      horizons: [1, 7], timeUnit: "days", cohortRef: "cohort:test",
      eventRef: "event:test", sampleBasis: "hypothesis", ...common,
    })],
  ];
  for (const [capability, invoke] of cases) {
    assert.deepEqual(await invoke(), fixture.reading);
    const actual = calls.at(-1);
    assert.equal(actual.method, "POST");
    assert.equal(actual.url, base + "/api/v1/gate/consultations");
    assert.equal(actual.body.capability, capability);
    assert.equal(actual.body.source_ref, "synthetic:parity");
    assert.equal(actual.body.task_ref, null);
    assert.equal(actual.body.run_id, null);
  }
  assert.deepEqual(lines, []);
});

test("feedback encodes one path segment and never reports task success", async t => {
  const { client, calls, lines } = setup(t, fixture.feedback);
  for (const usefulness of ["useful", "already_known", "incorrect", "missing_context"]) {
    assert.deepEqual(await client.consultationFeedback("id/with space?#%", usefulness), fixture.feedback);
    assert.deepEqual(calls.at(-1), { method: "POST",
      url: base + "/api/v1/gate/consultations/id%2Fwith%20space%3F%23%25/feedback", body: { usefulness } });
  }
  assert.deepEqual(lines, []);
});

for (const status of [401, 403, 404, 422, 429, 503]) {
  test(`HTTP ${status} propagates without retry or fallback`, async t => {
    const { client, calls, lines } = setup(t, { detail: "synthetic denial" }, status);
    for (const operation of [() => client.consultationCapabilities(), () => client.consultQueue(args),
      () => client.consultationFeedback("synthetic", "useful")]) {
      const before = calls.length;
      await assert.rejects(operation, error => error instanceof WarmWinterError && error.status === status && error.detail === "synthetic denial");
      assert.equal(calls.length, before + 1);
    }
    assert.deepEqual(lines, []);
  });
}
