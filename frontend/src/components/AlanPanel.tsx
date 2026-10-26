import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import type { AlanInvestigation, Health } from "../lib/types";
import { Badge, Mono, Panel, Spinner, cx } from "./ui";
import { ExternalIcon, LockIcon, ScanIcon, SparkIcon } from "./Icons";
import { formatDateTime } from "../lib/format";

const TERMINAL = new Set([
  "succeeded",
  "completed",
  "failed",
  "interrupted",
  "cancelled",
  "timed_out",
  "skipped",
]);

function statusTone(status: string): "signal" | "info" | "danger" | "warn" | "muted" {
  if (status === "succeeded" || status === "completed") return "signal";
  if (status === "running" || status === "awaiting_local") return "info";
  if (["failed", "interrupted", "cancelled", "timed_out"].includes(status)) return "danger";
  if (status === "pending") return "warn";
  return "muted";
}

export default function AlanPanel({
  health,
  caseId,
  initialRuns,
}: {
  health: Health | null;
  caseId: string;
  initialRuns: AlanInvestigation[];
}) {
  const [question, setQuestion] = useState(
    "Explain what should be checked before this invoice is reviewed.",
  );
  const [run, setRun] = useState<AlanInvestigation | null>(initialRuns[0] ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const configured = health?.alan_workflow_configured ?? false;

  useEffect(() => {
    if (!run && initialRuns[0]) setRun(initialRuns[0]);
  }, [initialRuns, run]);

  useEffect(() => {
    if (!run || TERMINAL.has(run.status)) return;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try {
        const next = await api.pollAlan(run.execution_id);
        if (!cancelled) setRun(next);
      } catch (err: unknown) {
        if (!cancelled) {
          setError(
            err instanceof ApiError ? err.message : "Could not read the Alan run status.",
          );
        }
      }
    }, 3000);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [run]);

  async function start() {
    if (!configured || busy) return;
    setBusy(true);
    setError(null);
    try {
      const started = await api.startAlan(caseId, question.trim());
      setRun(started);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "The Alan workflow did not start.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel className="overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-white/[0.07] px-4 py-3.5">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-cyan-200">
            <SparkIcon className="h-3.5 w-3.5" />
          </span>
          <div>
            <h2 className="text-xs font-semibold text-white">Alan workflow</h2>
            <p className="font-mono text-[9px] uppercase tracking-[0.1em] text-slate-600">
              escalation · via MCP
            </p>
          </div>
        </div>
        <Badge tone={configured ? "info" : "muted"}>
          {configured ? "connected" : "off"}
        </Badge>
      </div>

      {!configured ? (
        <div className="p-4">
          <div className="rounded-xl border border-dashed border-white/10 bg-ink-950/40 p-3.5">
            <div className="flex items-center gap-2 text-[11px] font-medium text-slate-300">
              <LockIcon className="h-3.5 w-3.5 text-slate-500" />
              No workflow is configured, so no run is shown.
            </div>
            <p className="mt-2 text-[10px] leading-5 text-slate-500">
              DocuPilot will not fake an Alan button. To enable a real workflow run on
              this account, create an Alan automation and set these server-side values:
            </p>
            <div className="mt-2.5 flex flex-wrap gap-1">
              {(health?.alan_missing ?? [
                "ALAN_MCP_URL",
                "ALAN_MCP_TOKEN",
                "ALAN_CONVERSATION_ID",
                "ALAN_WORKFLOW_ID",
              ]).map((name) => (
                <span
                  key={name}
                  className="rounded border border-white/[0.08] bg-white/[0.03] px-1.5 py-0.5 font-mono text-[9px] text-slate-500"
                >
                  {name}
                </span>
              ))}
            </div>
            <p className="mt-3 text-[10px] leading-5 text-slate-500">
              The chat above still works through{" "}
              {health?.model_configured
                ? "Alan's model gateway"
                : "a deterministic explainer"}
              . Workflow escalation is a separate, optional path.
            </p>
          </div>
          <a
            href="https://docs.tryalan.ai/docs/automations/create-an-automation"
            target="_blank"
            rel="noreferrer"
            className="mt-3 inline-flex items-center gap-1.5 text-[10px] text-slate-500 transition hover:text-cyan-200"
          >
            Alan automation docs
            <ExternalIcon className="h-3 w-3" />
          </a>
        </div>
      ) : (
        <div className="p-4">
          <label className="block">
            <Mono>Question for the Alan automation</Mono>
            <textarea
              className="input mt-2 min-h-[72px] resize-y text-[11px]"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              maxLength={2000}
              disabled={busy}
            />
          </label>
          <button
            className="btn-secondary mt-2.5 w-full"
            onClick={() => void start()}
            disabled={busy || !question.trim()}
          >
            <ScanIcon className="h-4 w-4" />
            {busy ? "Starting real run…" : "Run Alan investigation"}
          </button>
          <p className="mt-2 text-[9px] leading-4 text-slate-600">
            This starts a real run on your Alan account and may consume credits. It
            never approves or pays.
          </p>

          {error ? (
            <div className="mt-3 rounded-lg border border-rose-300/25 bg-rose-300/[0.06] px-3 py-2 text-[10px] leading-5 text-rose-100">
              {error}
            </div>
          ) : null}

          {run ? (
            <div className="mt-3 rounded-xl border border-white/[0.07] bg-ink-950/50 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Badge tone={statusTone(run.status)}>{run.status}</Badge>
                <span className="font-mono text-[9px] text-slate-600">
                  {formatDateTime(run.updated_at)}
                </span>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-slate-600">
                  execution
                </span>
                <span className="font-mono text-[9px] text-slate-400">
                  {run.execution_id}
                </span>
                {run.url ? (
                  <a
                    href={run.url}
                    target="_blank"
                    rel="noreferrer"
                    className="ml-auto inline-flex items-center gap-1 font-mono text-[9px] text-cyan-200 hover:underline"
                  >
                    open run <ExternalIcon className="h-2.5 w-2.5" />
                  </a>
                ) : null}
              </div>
              {!TERMINAL.has(run.status) ? (
                <div className="mt-3">
                  <Spinner label={`Waiting for Alan · poll ${run.polls}`} />
                </div>
              ) : null}
              {run.output ? (
                <p className="mt-3 max-h-64 overflow-y-auto whitespace-pre-wrap border-t border-white/[0.06] pt-3 text-[11px] leading-5 text-slate-300">
                  {run.output}
                </p>
              ) : null}
              {run.error ? (
                <p className="mt-2 whitespace-pre-wrap text-[10px] leading-5 text-rose-200">
                  {run.error}
                </p>
              ) : null}
              <div
                className={cx(
                  "mt-3 border-t border-white/[0.06] pt-2 font-mono text-[8px] uppercase tracking-[0.08em]",
                  TERMINAL.has(run.status) ? "text-slate-600" : "text-cyan-200/70",
                )}
              >
                {TERMINAL.has(run.status)
                  ? "terminal state · polling stopped"
                  : "polling the real Alan execution record"}
              </div>
            </div>
          ) : null}
        </div>
      )}
    </Panel>
  );
}