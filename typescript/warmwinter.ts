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

export const VERSION = "0.1.0";

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
}

const DEFAULT_BASE_URL = "https://api.warmwinter.io";

export class WarmWinter {
  private apiKey: string;
  private baseUrl: string;
  private timeoutMs: number;

  constructor(opts: WarmWinterOptions) {
    if (!opts.apiKey) throw new Error("apiKey is required (mint one at /api/v1/gate/keys)");
    this.apiKey = opts.apiKey;
    this.baseUrl = (opts.baseUrl ?? DEFAULT_BASE_URL).replace(/\/$/, "");
    this.timeoutMs = opts.timeoutMs ?? 10_000;
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
    return {
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
