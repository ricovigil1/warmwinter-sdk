"""
Warm Winter — Python SDK for the live trust gate.

The smallest wrapper around an AI/agent call that asks the one question the gate
exists to answer: *is this cheap answer trustworthy enough to act on — or should
we escalate, or abstain?* You keep executing; we only judge.

Zero dependencies (stdlib `urllib`), so it drops into any environment.

Quickstart
----------
    from warmwinter import WarmWinter

    ww = WarmWinter(api_key="ww_...")        # mint at /api/v1/gate/keys

    # 1) ask the gate before spending on the expensive path
    d = ww.decide(domain="compute", decision_type="model_route",
                  stated_confidence=0.82, stakes="medium")

    if d.verdict == "act":
        answer = cheap_model(prompt)          # trust the cheap path
    else:                                      # "escalate" / "abstain"
        answer = strong_model(prompt)          # or a human

    # 2) when you learn whether it held, close the loop so the cell sharpens
    ww.outcome(d.decision_id, "success" if answer_was_good else "failure")

The `guard()` helper does both ends in one call when you can supply both paths
and a verifier — see its docstring.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Optional

__version__ = "0.3.0"
__all__ = ["WarmWinter", "Decision", "WarmWinterError", "DEFAULT_BASE_URL", "__version__"]

DEFAULT_BASE_URL = "https://api.warmwinter.io"


class WarmWinterError(RuntimeError):
    def __init__(self, status: int, detail: str):
        super().__init__(f"[{status}] {detail}")
        self.status = status
        self.detail = detail


@dataclass
class Decision:
    decision_id: str
    verdict: str            # "act" | "escalate" | "abstain"
    cell_state: str         # "verified" | "provisional" | "ungrounded"
    calibrated_confidence: Optional[float]
    stated_confidence: float
    stakes: str
    reasons: list
    cell: dict
    replayed: bool = False

    @property
    def act(self) -> bool:
        """True when the gate says the cheap/proposed path is trustworthy."""
        return self.verdict == "act"


class WarmWinter:
    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL, timeout: float = 10.0,
                 log_verdicts: bool = True,
                 logger: Optional[Callable[[str], None]] = None):
        if not api_key:
            raise ValueError("api_key is required (mint one at /api/v1/gate/keys)")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.log_verdicts = log_verdicts
        self.logger = logger or print
        self._policy: Optional[dict] = None      # cached decision boundary (local mode)
        self._buffer: list = []                  # outcomes pending a flush

    def _log_decision(self, decision: Decision, domain: str, decision_type: str) -> None:
        """Emit a prompt-blind branded verdict line. Never include context or actions."""
        if not self.log_verdicts:
            return
        self.logger(
            f"[warmwinter] {decision.verdict.upper()} | {domain}/{decision_type} | "
            f"{decision.cell_state} | {decision.stakes} stakes"
        )

    # ── low-level ──────────────────────────────────────────────────────────────
    def _post(self, path: str, body: dict) -> dict:
        return self._request("POST", path, body)

    def _request(self, method: str, path: str, body: Optional[dict]) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            self.base_url + path, data=data, method=method,
            headers={"X-Api-Key": self.api_key, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            try:
                detail = json.loads(detail).get("detail", detail)
            except Exception:
                pass
            raise WarmWinterError(e.code, detail) from None

    def consultation_capabilities(self) -> dict:
        """Discover admitted calculations using an explicit consultation-only grant."""
        return self._request("GET", "/api/v1/gate/consultations/capabilities", None)

    def consult_queue(self, *, arrival_rate: float, service_capacity: float,
                      rate_unit: str, source_ref: str, usefulness_confidence: float,
                      task_ref: Optional[str] = None, run_id: Optional[str] = None) -> dict:
        """Descriptive native queue reading. No action authority or verified outcome."""
        return self._post("/api/v1/gate/consultations", {
            "capability": "queue-pressure", "arrival_rate": arrival_rate,
            "service_capacity": service_capacity, "rate_unit": rate_unit,
            "source_ref": source_ref, "usefulness_confidence": usefulness_confidence,
            "task_ref": task_ref, "run_id": run_id,
        })

    def consult_conservation(self, *, inflows: list, outflows: list,
                             generation: list, consumption: list,
                             rate_unit: str, source_ref: str, usefulness_confidence: float,
                             task_ref: Optional[str] = None, run_id: Optional[str] = None) -> dict:
        """Native flow accounting. All categories explicit; [] declares no flows.

        Result is descriptive and caller-sourced, with no execution authority.
        """
        return self._post("/api/v1/gate/consultations", {
            "capability": "conservation-balance", "inflows": inflows, "outflows": outflows,
            "generation": generation, "consumption": consumption, "rate_unit": rate_unit,
            "source_ref": source_ref, "usefulness_confidence": usefulness_confidence,
            "task_ref": task_ref, "run_id": run_id,
        })

    def consult_tail_risk(self, *, losses: list, alpha: float, loss_unit: str,
                          sample_basis: str, source_ref: str, usefulness_confidence: float,
                          task_ref: Optional[str] = None, run_id: Optional[str] = None) -> dict:
        """Empirical CVaR for supplied losses; no population forecast or action authority."""
        return self._post("/api/v1/gate/consultations", {
            "capability": "empirical-tail-risk", "losses": losses, "alpha": alpha,
            "loss_unit": loss_unit, "sample_basis": sample_basis, "source_ref": source_ref,
            "usefulness_confidence": usefulness_confidence, "task_ref": task_ref, "run_id": run_id,
        })

    def consult_calibration(self, *, pairs: list, cohort_ref: str, sample_basis: str,
                            source_ref: str, usefulness_confidence: float,
                            task_ref: Optional[str] = None, run_id: Optional[str] = None) -> dict:
        """Describe supplied {confidence, outcome} pairs; no calibration certification."""
        return self._post("/api/v1/gate/consultations", {
            "capability": "cohort-calibration", "pairs": pairs, "cohort_ref": cohort_ref,
            "sample_basis": sample_basis, "source_ref": source_ref,
            "usefulness_confidence": usefulness_confidence, "task_ref": task_ref, "run_id": run_id,
        })

    def consult_value_of_information(self, *, branches: list, current_best_utility: float,
                                      evidence_cost: float, utility_unit: str, scenario_ref: str,
                                      scenario_basis: str, source_ref: str, usefulness_confidence: float,
                                      task_ref: Optional[str] = None, run_id: Optional[str] = None) -> dict:
        """Modeled evidence value minus declared all-in cost; no spending/action authority."""
        return self._post("/api/v1/gate/consultations", {
            "capability": "value-of-information", "branches": branches,
            "current_best_utility": current_best_utility, "evidence_cost": evidence_cost,
            "utility_unit": utility_unit, "scenario_ref": scenario_ref, "scenario_basis": scenario_basis,
            "source_ref": source_ref, "usefulness_confidence": usefulness_confidence,
            "task_ref": task_ref, "run_id": run_id,
        })

    def consult_scenarios(self, *, scenarios: list, baseline_ref: str, horizon_ref: str,
                          alpha: float, loss_unit: str, scenario_basis: str,
                          generating_model_ref: str, generating_model_version: str,
                          generating_seed: Optional[int], source_ref: str, usefulness_confidence: float,
                          task_ref: Optional[str] = None, run_id: Optional[str] = None) -> dict:
        """Compare supplied loss samples plus overhead; does not execute/validate their generator."""
        return self._post("/api/v1/gate/consultations", {
            "capability": "scenario-risk-comparison", "scenarios": scenarios,
            "baseline_ref": baseline_ref, "horizon_ref": horizon_ref, "alpha": alpha,
            "loss_unit": loss_unit, "scenario_basis": scenario_basis,
            "generating_model_ref": generating_model_ref, "generating_model_version": generating_model_version,
            "generating_seed": generating_seed, "source_ref": source_ref,
            "usefulness_confidence": usefulness_confidence, "task_ref": task_ref, "run_id": run_id,
        })

    def consult_resolution_time(self, *, observations: list, horizons: list, time_unit: str,
                                cohort_ref: str, event_ref: str, sample_basis: str,
                                source_ref: str, usefulness_confidence: float,
                                task_ref: Optional[str] = None, run_id: Optional[str] = None) -> dict:
        """Describe right-censored follow-up; no verified resolution or population forecast."""
        return self._post("/api/v1/gate/consultations", {
            "capability": "resolution-time", "observations": observations, "horizons": horizons,
            "time_unit": time_unit, "cohort_ref": cohort_ref, "event_ref": event_ref,
            "sample_basis": sample_basis, "source_ref": source_ref,
            "usefulness_confidence": usefulness_confidence, "task_ref": task_ref, "run_id": run_id,
        })

    def consultation_feedback(self, consultation_id: str, usefulness: str) -> dict:
        """Report usefulness only; never an independently verified task success."""
        from urllib.parse import quote
        return self._post("/api/v1/gate/consultations/" + quote(consultation_id, safe="")
                          + "/feedback", {"usefulness": usefulness})

    # ── the gate ───────────────────────────────────────────────────────────────
    def decide(self, *, domain: str, decision_type: str, stated_confidence: float,
               context: Optional[dict] = None, stakes: Optional[str] = None,
               candidate_action: Optional[str] = None,
               idempotency_key: Optional[str] = None,
               on_ungrounded: Optional[str] = None) -> Decision:
        """Ask whether a proposed action is trustworthy enough to act on."""
        body = {"domain": domain, "decision_type": decision_type,
                "stated_confidence": stated_confidence}
        for k, v in (("context", context), ("stakes", stakes),
                     ("candidate_action", candidate_action),
                     ("idempotency_key", idempotency_key),
                     ("on_ungrounded", on_ungrounded)):
            if v is not None:
                body[k] = v
        r = self._post("/api/v1/gate/decide", body)
        decision = Decision(
            decision_id=r["decision_id"], verdict=r["verdict"], cell_state=r["cell_state"],
            calibrated_confidence=r.get("calibrated_confidence"),
            stated_confidence=r.get("stated_confidence", stated_confidence),
            stakes=r.get("stakes", stakes or "medium"),
            reasons=r.get("reasons", []), cell=r.get("cell", {}),
            replayed=r.get("replayed", False),
        )
        self._log_decision(decision, domain, decision_type)
        return decision

    def outcome(self, decision_id: str, outcome: str,
                observed: Optional[dict] = None) -> dict:
        """Close the loop. `outcome` ∈ {success, failure, abstained}."""
        body = {"decision_id": decision_id, "outcome": outcome}
        if observed is not None:
            body["observed"] = observed
        return self._post("/api/v1/gate/outcome", body)

    def outcome_by_ref(self, commit_sha: str, outcome: str,
                       observed: Optional[dict] = None,
                       decision_type: Optional[str] = None) -> dict:
        """Resolve a decision by commit SHA from CI or a deploy health check."""
        body = {"commit_sha": commit_sha, "outcome": outcome}
        if observed is not None:
            body["observed"] = observed
        if decision_type is not None:
            body["decision_type"] = decision_type
        return self._post("/api/v1/gate/outcome/by-ref", body)

    def frontier(self) -> dict:
        """This account's live competence map (+ the cold-start backtest seed)."""
        return self._request("GET", "/api/v1/gate/frontier", None)

    # ── local-decide mode — decide at the edge, learn in batches ────────────────
    # Pull the policy ONCE, then decide() in-process at ~microsecond latency with
    # no per-call round-trip; buffer outcomes and flush them in one batch. The
    # policy ships states only, never calibration.
    def pull_policy(self) -> dict:
        """Fetch + cache the signed decision boundary. Call once, then periodically."""
        self._policy = self._request("GET", "/api/v1/gate/policy", None)
        return self._policy

    def decide_local(self, *, domain: str, decision_type: str,
                     stakes: str = "medium", on_ungrounded: str = "escalate") -> str:
        """Reproduce the gate verdict from the cached policy alone — no network.
        Auto-pulls the policy on first use. Returns act | escalate | abstain."""
        if self._policy is None:
            self.pull_policy()
        p = self._policy
        state = p.get("default_state", "ungrounded")
        max_stakes = "high"
        for c in p.get("cells", []):
            if c["domain"] == domain and c["decision_type"] == decision_type:
                state = c["state"]
                max_stakes = c.get("max_stakes", "high")
                break
        if state == "ungrounded" and on_ungrounded == "abstain":
            return "abstain"
        if state == "verified" and stakes == "high" and max_stakes != "high":
            return "escalate"
        return p["stakes_rule"][state][stakes]

    def report_local(self, *, domain: str, decision_type: str,
                     stated_confidence: float, outcome: str,
                     stakes: str = "medium") -> None:
        """Buffer a resolved outcome locally (no network). Flush in a batch."""
        self._buffer.append({"domain": domain, "decision_type": decision_type,
                             "stated_confidence": stated_confidence,
                             "outcome": outcome, "stakes": stakes})

    def flush(self) -> dict:
        """Send buffered outcomes in one call. If the server reports a newer policy
        version, refresh the cache automatically (self-healing edge)."""
        if not self._buffer:
            return {"ingested": 0, "stale": False}
        version = (self._policy or {}).get("version")
        body = {"rows": self._buffer, "policy_version": version}
        res = self._post("/api/v1/gate/outcome/bulk", body)
        self._buffer = []
        if res.get("stale"):
            self.pull_policy()
        return res

    # ── one-call convenience ────────────────────────────────────────────────────
    def guard(self, *, domain: str, decision_type: str, stated_confidence: float,
              cheap: Callable[[], Any], escalate: Callable[[], Any],
              verify: Optional[Callable[[Any], bool]] = None,
              stakes: Optional[str] = None, context: Optional[dict] = None) -> Any:
        """Gate, run the chosen path, and (if `verify` is given) auto-report the
        outcome — the whole loop in one call.

          result = ww.guard(
              domain="compute", decision_type="model_route", stated_confidence=0.82,
              cheap=lambda: small_model(prompt),
              escalate=lambda: big_model(prompt),
              verify=lambda out: out is not None,   # your success test
          )

        `act` → run `cheap`; anything else → run `escalate`. When `verify` is
        supplied we report success/failure so the cell learns; otherwise resolve
        it yourself with `outcome(...)`.
        """
        d = self.decide(domain=domain, decision_type=decision_type,
                        stated_confidence=stated_confidence, stakes=stakes,
                        context=context)
        took_cheap = d.act
        result = (cheap if took_cheap else escalate)()
        if verify is not None:
            ok = bool(verify(result))
            # Only the cheap path's correctness scores the cell — escalation is the
            # safe fallback, not a prediction we're grading.
            if took_cheap:
                self.outcome(d.decision_id, "success" if ok else "failure")
            else:
                self.outcome(d.decision_id, "abstained")
        return result
