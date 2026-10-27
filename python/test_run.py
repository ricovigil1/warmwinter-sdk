"""Offline SDK run-lineage contract: no network, account, key or production writes."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

import warmwinter as sdk


class RunContractTests(unittest.TestCase):
    def setUp(self):
        self.client = sdk.WarmWinter(api_key="test-runtime-bound-placeholder", log_verdicts=False)
        self.requests = []

        def record(path, body):
            self.requests.append((path, body))
            if path.endswith("/agent-runs/start"):
                return {"id": "run-001", "events": [], "replayed": False}
            if path.endswith("/gate/decide"):
                return {
                    "decision_id": "decision-001", "verdict": "escalate",
                    "cell_state": "ungrounded", "reasons": [], "cell": {},
                    "stated_confidence": 0.8, "stakes": "medium",
                }
            return {"event_id": "event-001", "replayed": False}
        self.client._post = Mock(side_effect=record)

    def test_start_run_uses_runtime_endpoint_and_stable_external_id(self):
        first = self.client.run(objective_ref="task", authority_ref="bounded",
                                external_run_ref="task-123", agent_ref="test-runtime")
        self.assertEqual(first["id"], "run-001")
        self.assertEqual(self.requests[0][0], "/api/v1/observatory/agent-runs/start")
        self.assertEqual(self.requests[0][1]["external_run_ref"], "task-123")
        self.assertEqual(self.requests[0][1]["retention_days"], 30)
        with self.assertRaises(ValueError):
            self.client.run(objective_ref="task", authority_ref="", external_run_ref="ref")

    def test_outcome_is_only_weak_and_trace_payload_is_rejected(self):
        self.client.run_event("run-001", "outcome", idempotency_key="outcome:1", outcome=1.0)
        path, body = self.requests[-1]
        self.assertEqual(path, "/api/v1/observatory/agent-runs/run-001/events/ingest")
        self.assertEqual(body["label_strength"], "weak")
        self.assertEqual(body["outcome"], 1.0)
        for supplied in ("strong", "unclassified"):
            with self.assertRaises(ValueError):
                self.client.run_event("run-001", "outcome", idempotency_key="false",
                                      outcome=1.0, label_strength=supplied)
        with self.assertRaises(ValueError):
            self.client.run_event("run-001", "action", idempotency_key="trace",
                                  trace_ref="private-prompt")
        self.assertEqual(len(self.requests), 1)

    def test_guard_records_same_key_gate_lineage_before_action(self):
        executed = []
        self.client.guard(
            domain="compute", decision_type="route", stated_confidence=0.8,
            cheap=lambda: executed.append("cheap"), escalate=lambda: executed.append("fallback"),
            run_id="run-001",
        )
        self.assertEqual(executed, ["fallback"])
        self.assertEqual([p for p, _ in self.requests], [
            "/api/v1/gate/decide",
            "/api/v1/observatory/agent-runs/run-001/events/ingest",
        ])
        event = self.requests[-1][1]
        self.assertEqual(event["event_type"], "gate")
        self.assertEqual(event["gate_decision_id"], "decision-001")
        self.assertEqual(event["idempotency_key"], "gate:decision-001")

    def test_link_failure_prevents_execution(self):
        executed = []
        def fail_gate(path, body):
            if path.endswith("/gate/decide"):
                return {"decision_id": "decision-002", "verdict": "act",
                        "cell_state": "provisional", "reasons": [], "cell": {}}
            raise sdk.WarmWinterError(404, "run belongs to another host")
        self.client._post = Mock(side_effect=fail_gate)
        with self.assertRaises(sdk.WarmWinterError):
            self.client.guard(
                domain="compute", decision_type="route", stated_confidence=0.7,
                cheap=lambda: executed.append("cheap"),
                escalate=lambda: executed.append("fallback"),
                run_id="foreign-run",
            )
        self.assertEqual(executed, [])


if __name__ == "__main__":
    unittest.main()
