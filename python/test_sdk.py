import io
import unittest

from warmwinter import WarmWinter, __version__


DECISION = {
    "decision_id": "dec_test",
    "verdict": "act",
    "cell_state": "verified",
    "calibrated_confidence": 0.91,
    "stated_confidence": 0.82,
    "stakes": "medium",
    "reasons": [],
    "cell": {},
}


class SdkTests(unittest.TestCase):
    def client(self, **kwargs):
        client = WarmWinter("ww_test", **kwargs)
        client._post = lambda _path, _body: DECISION
        return client

    def test_version(self):
        self.assertEqual(__version__, "0.2.0")

    def test_verdict_line_is_branded_and_prompt_blind(self):
        output = io.StringIO()
        client = self.client(logger=lambda line: print(line, file=output))
        client.decide(
            domain="compute",
            decision_type="model_route",
            stated_confidence=0.82,
            context={"prompt": "TOP SECRET"},
            candidate_action="private action",
        )
        line = output.getvalue().strip()
        self.assertEqual(
            line,
            "[warmwinter] ACT | compute/model_route | verified | medium stakes",
        )
        self.assertNotIn("TOP SECRET", line)
        self.assertNotIn("private action", line)

    def test_logging_can_be_disabled(self):
        lines = []
        client = self.client(log_verdicts=False, logger=lines.append)
        client.decide(
            domain="compute",
            decision_type="model_route",
            stated_confidence=0.82,
        )
        self.assertEqual(lines, [])

    def test_outcome_by_ref_uses_strong_label_endpoint(self):
        calls = []
        client = WarmWinter("ww_test", log_verdicts=False)
        client._post = lambda path, body: calls.append((path, body)) or {"ok": True}
        client.outcome_by_ref(
            "abc123",
            "success",
            observed={"ci": "green"},
            decision_type="git_push",
        )
        self.assertEqual(calls, [(
            "/api/v1/gate/outcome/by-ref",
            {
                "commit_sha": "abc123",
                "outcome": "success",
                "observed": {"ci": "green"},
                "decision_type": "git_push",
            },
        )])

    def test_local_decide_honors_cell_stakes_ceiling(self):
        client = WarmWinter("ww_test", log_verdicts=False)
        client._policy = {
            "default_state": "ungrounded",
            "cells": [{
                "domain": "agent_ops",
                "decision_type": "deploy",
                "state": "verified",
                "max_stakes": "medium",
            }],
            "stakes_rule": {
                "verified": {"low": "act", "medium": "act", "high": "act"},
            },
        }
        self.assertEqual(
            client.decide_local(
                domain="agent_ops",
                decision_type="deploy",
                stakes="high",
            ),
            "escalate",
        )


if __name__ == "__main__":
    unittest.main()
