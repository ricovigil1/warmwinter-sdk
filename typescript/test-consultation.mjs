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
