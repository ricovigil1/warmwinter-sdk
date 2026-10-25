/**
 * Warm Winter — TypeScript / JavaScript SDK for the live trust gate.
 *
 * The smallest wrapper around an AI/agent call that asks the one question the
 * gate exists to answer: is this cheap answer trustworthy enough to act on — or
 * should we escalate, or abstain? You keep executing; we only judge.
 *
 * Zero dependencies (uses the built-in `fetch`; Node 18+ or any browser/edge runtime).
 *
 * Quickstart:
 *
 *   import { WarmWinter } from "./warmwinter";
 *   const ww = new WarmWinter({ apiKey: "ww_..." });   // mint at /api/v1/gate/keys
 *
 *   const d = await ww.decide({
 *     domain: "compute", decisionType: "model_route",
 *     statedConfidence: 0.82, stakes: "medium",
 *   });
 *   const answer = d.verdict === "act" ? await cheapModel(prompt)
 *                                      : await strongModel(prompt);
 *   await ww.outcome(d.decisionId, answerWasGood ? "success" : "failure");
 */

export const VERSION = "0.2.0";

export type Verdict = "act" | "escalate" | "abstain";
export type CellState = "verified" | "provisional" | "ungrounded";
export type Stakes = "low" | "medium" | "high";
export type Outcome = "success" | "failure" | "abstained";

export interface Decision {
  decisionId: string;
  verdict: Verdict;
  cellState: CellState;
  calibratedConfidence: number | null;
  statedConfidence: number;
  stakes: Stakes;
  reasons: string[];
  cell: Record<string, unknown>;
  replayed: boolean;
}

export class WarmWinterError extends Error {
  constructor(public status: number, public detail: string) {
    super(`[${status}] ${detail}`);
    this.name = "WarmWinterError";
  }
}

export interface WarmWinterOptions {
  apiKey: string;
  baseUrl?: string;
  timeoutMs?: number;
  /** Emit one prompt-blind branded line for each verdict. Defaults to true. */
  logVerdicts?: boolean;
  /** Replace console.info with an application logger. */
  logger?: (message: string) => void;
}

const DEFAULT_BASE_URL = "https://api.warmwinter.io";

export class WarmWinter {
  private apiKey: string;
  private baseUrl: string;
  private timeoutMs: number;
  private logVerdicts: boolean;
  private logger: (message: string) => void;

  constructor(opts: WarmWinterOptions) {
    if (!opts.apiKey) throw new Error("apiKey is required (mint one at /api/v1/gate/keys)");
    this.apiKey = opts.apiKey;
    this.baseUrl = (opts.baseUrl ?? DEFAULT_BASE_URL).replace(/\/$/, "");
    this.timeoutMs = opts.timeoutMs ?? 10_000;
    this.logVerdicts = opts.logVerdicts ?? true;
    this.logger = opts.logger ?? console.info;
  }

  private logDecision(decision: Decision, domain: string, decisionType: string): void {
    if (!this.logVerdicts) return;
    this.logger(
      `[warmwinter] ${decision.verdict.toUpperCase()} | ${domain}/${decisionType} | ` +
      `${decision.cellState} | ${decision.stakes} stakes`,
    );
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), this.timeoutMs);
    try {
      const resp = await fetch(this.baseUrl + path, {
        method,
        headers: { "X-Api-Key": this.apiKey, "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: ctrl.signal,
      });
      const text = await resp.text();
      const data = text ? JSON.parse(text) : {};
      if (!resp.ok) throw new WarmWinterError(resp.status, data?.detail ?? text);
      return data as T;
    } finally {
      clearTimeout(t);
    }
  }

  /** Discover admitted calculations using an explicit consultation-only grant. */
  async consultationCapabilities(): Promise<Record<string, unknown>> {
    return this.request("GET", "/api/v1/gate/consultations/capabilities");
  }

  /** Descriptive native queue reading; preserve the complete snake_case server envelope. */
  async consultQueue(args: {
    arrivalRate: number;
    serviceCapacity: number;
    rateUnit: "tasks/second" | "tasks/minute" | "tasks/hour";
    sourceRef: string;
    usefulnessConfidence: number;
    taskRef?: string;
    runId?: string;
  }): Promise<Record<string, unknown>> {
    return this.request("POST", "/api/v1/gate/consultations", {
      capability: "queue-pressure",
      arrival_rate: args.arrivalRate,
      service_capacity: args.serviceCapacity,
      rate_unit: args.rateUnit,
      source_ref: args.sourceRef,
      usefulness_confidence: args.usefulnessConfidence,
      task_ref: args.taskRef ?? null,
      run_id: args.runId ?? null,
    });
  }

  /** Report usefulness only; never an independently verified task success. */
  async consultationFeedback(
    consultationId: string,
    usefulness: "useful" | "already_known" | "incorrect" | "missing_context",
  ): Promise<Record<string, unknown>> {
    return this.request("POST", "/api/v1/gate/consultations/" + encodeURIComponent(consultationId)
      + "/feedback", { usefulness });
  }

  /** Ask whether a proposed action is trustworthy enough to act on. */
  async decide(args: {
    domain: string;
    decisionType: string;
    statedConfidence: number;
    context?: Record<string, unknown>;
    stakes?: Stakes;
    candidateAction?: string;
    idempotencyKey?: string;
    onUngrounded?: "escalate" | "abstain";
  }): Promise<Decision> {
    const r = await this.request<any>("POST", "/api/v1/gate/decide", {
      domain: args.domain,
      decision_type: args.decisionType,
      stated_confidence: args.statedConfidence,
      context: args.context,
      stakes: args.stakes,
      candidate_action: args.candidateAction,
      idempotency_key: args.idempotencyKey,
      on_ungrounded: args.onUngrounded,
    });
    const decision: Decision = {
      decisionId: r.decision_id,
      verdict: r.verdict,
      cellState: r.cell_state,
      calibratedConfidence: r.calibrated_confidence ?? null,
      statedConfidence: r.stated_confidence ?? args.statedConfidence,
      stakes: r.stakes ?? args.stakes ?? "medium",
      reasons: r.reasons ?? [],
      cell: r.cell ?? {},
      replayed: r.replayed ?? false,
    };
    this.logDecision(decision, args.domain, args.decisionType);
    return decision;
  }

  /** Close the loop so the cell sharpens. */
  async outcome(decisionId: string, outcome: Outcome, observed?: Record<string, unknown>) {
    return this.request<any>("POST", "/api/v1/gate/outcome", {
      decision_id: decisionId,
      outcome,
      observed,
    });
  }

  /** This account's live competence map (+ the cold-start backtest seed). */
  async frontier() {
    return this.request<any>("GET", "/api/v1/gate/frontier");
  }

  /**
   * Gate, run the chosen path, and (if `verify` is given) auto-report the
   * outcome — the whole loop in one call. `act` runs `cheap`; anything else
   * runs `escalate`.
   */
  async guard<T>(args: {
    domain: string;
    decisionType: string;
    statedConfidence: number;
    cheap: () => Promise<T> | T;
    escalate: () => Promise<T> | T;
    verify?: (result: T) => boolean;
    stakes?: Stakes;
    context?: Record<string, unknown>;
  }): Promise<T> {
    const d = await this.decide({
      domain: args.domain,
      decisionType: args.decisionType,
      statedConfidence: args.statedConfidence,
      stakes: args.stakes,
      context: args.context,
    });
    const tookCheap = d.verdict === "act";
    const result = await (tookCheap ? args.cheap() : args.escalate());
    if (args.verify) {
      // Only the cheap path's correctness scores the cell; escalation is the safe
      // fallback, not a prediction we grade.
      if (tookCheap) {
        await this.outcome(d.decisionId, args.verify(result) ? "success" : "failure");
      } else {
        await this.outcome(d.decisionId, "abstained");
      }
    }
    return result;
  }
}
