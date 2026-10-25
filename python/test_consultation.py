"""Offline wire contracts; no live service, credentials or backend writes."""
import copy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from warmwinter import WarmWinter, WarmWinterError

FIXTURE = json.loads((Path(__file__).resolve().parents[1] / "fixtures/consultation.json").read_text())
BASE = "https://sdk-test.invalid"


class ConsultationTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.lines = []
        self.body = FIXTURE["reading"]
        self.status = 200
        self.client = WarmWinter("synthetic-test-key", base_url=BASE, logger=self.lines.append)
        self.transport = patch("urllib.request.urlopen", self.respond)
        self.transport.start()
        self.addCleanup(self.transport.stop)

    def respond(self, request, timeout):
        self.assertTrue(request.full_url.startswith(BASE + "/"))
        self.calls.append((request.method, request.full_url,
                           json.loads(request.data) if request.data else None))
        self.assertEqual(request.get_header("X-api-key"), "synthetic-test-key")
        self.assertEqual(timeout, 10.0)
        payload = json.dumps(self.body).encode()
        if self.status >= 400:
            raise HTTPError(request.full_url, self.status, "synthetic", {}, io.BytesIO(payload))
        return io.BytesIO(payload)

    def consult(self, **extra):
        return self.client.consult_queue(arrival_rate=8, service_capacity=10,
            rate_unit="tasks/minute", source_ref="synthetic:rates", usefulness_confidence=0.6, **extra)

    def test_discovery_uses_explicit_key_and_preserves_limits(self):
        self.body = FIXTURE["capabilities"]
        self.assertEqual(self.client.consultation_capabilities(), self.body)
        self.assertEqual(self.calls, [("GET", BASE + "/api/v1/gate/consultations/capabilities", None)])

    def test_queue_request_and_full_advisory_response(self):
        reading = self.consult(task_ref="synthetic:task", run_id="synthetic-run")
        self.assertEqual(self.calls, [("POST", BASE + "/api/v1/gate/consultations", FIXTURE["request"])])
        self.assertEqual(reading, FIXTURE["reading"])
        self.assertFalse(reading["authority_granted"])
        self.assertEqual(reading["outcome_status"], "pending_independent_outcome")
        self.assertEqual(self.lines, [])

    def test_optional_lineage_is_null_without_creating_an_identity(self):
        self.consult()
        self.assertEqual(self.calls[0][2], {**FIXTURE["request"], "task_ref": None, "run_id": None})

    def test_overload_null_unknown_and_extensions_survive(self):
        self.body = copy.deepcopy(FIXTURE["reading"])
        self.body["analysis"].update(utilization=1.0, pressure=None, regime="overloaded",
                                     queue_stable=False, nonfinite_values={"pressure": "positive_infinity"})
        self.body["future_metadata"] = {"unknown": None}
        self.assertEqual(self.consult(), self.body)
        self.assertEqual(self.lines, [])

    def test_feedback_encodes_one_path_segment_and_never_reports_task_success(self):
        self.body = FIXTURE["feedback"]
        for usefulness in ("useful", "already_known", "incorrect", "missing_context"):
            with self.subTest(usefulness=usefulness):
                self.assertEqual(self.client.consultation_feedback("id/with space?#%", usefulness), self.body)
                self.assertEqual(self.calls[-1], ("POST",
                    BASE + "/api/v1/gate/consultations/id%2Fwith%20space%3F%23%25/feedback",
                    {"usefulness": usefulness}))
        self.assertEqual(self.lines, [])

    def test_server_denials_propagate_without_retry_or_fallback(self):
        for status in (401, 403, 404, 422, 429, 503):
            for operation in (self.client.consultation_capabilities, self.consult,
                              lambda: self.client.consultation_feedback("synthetic", "useful")):
                with self.subTest(status=status, operation=operation):
                    self.status = status
                    self.body = {"detail": "synthetic denial"}
                    before = len(self.calls)
                    with self.assertRaises(WarmWinterError) as caught:
                        operation()
                    self.assertEqual(caught.exception.status, status)
                    self.assertEqual(caught.exception.detail, "synthetic denial")
                    self.assertEqual(len(self.calls), before + 1)
        self.assertEqual(self.lines, [])


if __name__ == "__main__":
    unittest.main()
