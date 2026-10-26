import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../lib/api";
import type { CaseSummary, Dashboard, Health } from "../lib/types";
import type { Route } from "../components/Shell";
import {
  Badge,
  CaseStatusBadge,
  EmptyState,
  Mono,
  Panel,
  ReviewBadge,
  Spinner,
  StatCard,
  cx,
} from "../components/ui";
import {
  AlertIcon,
  ArrowRightIcon,
  CheckIcon,
  FileIcon,
  RefreshIcon,
  ShieldIcon,
  SparkIcon,
  UploadIcon,
} from "../components/Icons";
import { formatAmount, relativeTime } from "../lib/format";

type Filter = "all" | "needs_review" | "clean" | "reviewed";

const filters: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "needs_review", label: "Needs review" },
  { key: "clean", label: "Clean" },
  { key: "reviewed", label: "Reviewed" },
];

export default function DashboardPage({
  health,
  onNavigate,
}: {
  health: Health | null;
  onNavigate: (route: Route) => void;
}) {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    Promise.all([api.dashboard(), api.cases()])
      .then(([dash, list]) => {
        if (!active) return;
        setDashboard(dash);
        setCases(list);
      })
      .catch((err: unknown) => {
        if (!active) return;
        setError(err instanceof ApiError ? err.message : "Could not load the dashboard.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [reloadKey]);

  const visibleCases = useMemo(() => {
    return cases.filter((item) => {
      if (filter === "needs_review") return item.status === "needs_review";
      if (filter === "clean") return item.status === "no_mismatch";
      if (filter === "reviewed")
        return item.review_status !== "pending_review" && item.review_status !== "in_review";
      return true;
    });
  }, [cases, filter]);

  const maxFlag = Math.max(1, ...(dashboard?.flag_counts.map((item) => item.count) ?? [0]));

  return (
    <div className="space-y-7 animate-rise">
      <div className="flex flex-wrap items-end justify-between gap-5">
        <div>
          <Mono>Operations · invoice reconciliation</Mono>
          <h1 className="mt-2 max-w-2xl text-3xl font-semibold tracking-tight text-white lg:text-[40px] lg:leading-[1.05]">
            Every invoice, before the money moves.
          </h1>
          <p className="mt-3 max-w-xl text-sm leading-6 text-slate-400">
            DocuPilot extracts invoice fields with an open model, then matches them
            to synthetic purchase orders in Python. Every flag carries the values
            and the evidence behind it.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn-secondary" onClick={() => setReloadKey((key) => key + 1)}>
            <RefreshIcon className="h-4 w-4" />
            Refresh
          </button>
          <button className="btn-primary" onClick={() => onNavigate({ name: "upload" })}>
            <UploadIcon className="h-4 w-4" />
            Upload invoice
          </button>
        </div>
      </div>

      <div className="flex items-start gap-3 rounded-xl border border-ember/20 bg-ember/[0.045] px-4 py-3">
        <ShieldIcon className="mt-0.5 h-4 w-4 shrink-0 text-ember" />
        <p className="text-xs leading-5 text-slate-300">
          <span className="font-semibold text-ember">Demo boundary.</span> This is a
          reconciliation signal, not a payment system. Nothing here approves, schedules,
          or pays an invoice. A human reviewer makes every decision.
        </p>
      </div>

      {error ? (
        <div className="rounded-xl border border-rose-300/25 bg-rose-300/[0.06] px-4 py-3 text-sm text-rose-100">
          {error}
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Documents"
          value={loading ? "—" : (dashboard?.stats.total_documents ?? 0)}
          detail="Synthetic invoices in this workspace"
        />
        <StatCard
          label="Needs review"
          value={loading ? "—" : (dashboard?.stats.needs_review ?? 0)}
          detail="High or medium severity flags"
          tone="warn"
        />
        <StatCard
          label="High severity flags"
          value={loading ? "—" : (dashboard?.stats.high_flags ?? 0)}
          detail="Values a reviewer must inspect"
          tone="danger"
        />
        <StatCard
          label="Reviewed"
          value={loading ? "—" : (dashboard?.stats.reviewed ?? 0)}
          detail="Human review recorded (no payment action)"
          tone="signal"
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.65fr)_minmax(300px,0.85fr)]">
        <Panel className="overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.07] px-5 py-4">
            <div>
              <h2 className="text-sm font-semibold text-white">Review queue</h2>
              <p className="mt-1 text-[11px] text-slate-500">
                Newest first. Open a case to inspect values, evidence, and arithmetic.
              </p>
            </div>
            <div className="flex flex-wrap gap-1 rounded-lg border border-white/[0.07] bg-ink-900/60 p-1">
              {filters.map((item) => (
                <button
                  key={item.key}
                  onClick={() => setFilter(item.key)}
                  className={cx(
                    "rounded-md px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.12em] transition",
                    filter === item.key
                      ? "bg-white/[0.08] text-white"
                      : "text-slate-500 hover:text-slate-300",
                  )}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div className="hidden grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_110px_90px_36px] gap-3 border-b border-white/[0.06] px-5 py-2.5 md:grid">
            {["Document", "Amount", "Flags", "Status", ""].map((label) => (
              <Mono key={label}>{label}</Mono>
            ))}
          </div>

          {loading ? (
            <div className="flex items-center justify-center px-5 py-16">
              <Spinner label="Loading reconciliation queue" />
            </div>
          ) : visibleCases.length === 0 ? (
            <div className="p-5">
              <EmptyState
                title={cases.length === 0 ? "No documents yet" : "Nothing in this filter"}
                body={
                  cases.length === 0
                    ? "Generate the synthetic samples or upload an invoice to populate the queue."
                    : "Switch filters to see the other cases in this workspace."
                }
                action={
                  <button className="btn-primary" onClick={() => onNavigate({ name: "upload" })}>
                    <UploadIcon className="h-4 w-4" />
                    Upload invoice
                  </button>
                }
              />
            </div>
          ) : (
            <div>
              {visibleCases.map((item) => (
                <button
                  key={item.id}
                  onClick={() => onNavigate({ name: "case", id: item.id })}
                  className="group grid w-full grid-cols-1 gap-3 border-b border-white/[0.055] px-5 py-4 text-left transition last:border-0 hover:bg-white/[0.025] md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_110px_90px_36px] md:items-center"
                >
                  <div className="flex min-w-0 items-start gap-3">
                    <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-slate-500 group-hover:text-signal">
                      <FileIcon className="h-4 w-4" />
                    </span>
                    <span className="min-w-0">
                      <span className="flex flex-wrap items-center gap-2">
                        <span className="truncate text-sm font-medium text-slate-100">
                          {item.vendor_name ?? "Unknown vendor"}
                        </span>
                        {item.source === "demo" ? (
                          <Badge tone="muted">synthetic</Badge>
                        ) : null}
                      </span>
                      <span className="mt-1 block truncate font-mono text-[10px] uppercase tracking-[0.1em] text-slate-500">
                        {item.invoice_number ?? "no invoice number"} · {item.filename}
                      </span>
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-3 md:block">
                    <span className="font-mono text-sm text-slate-200">
                      {formatAmount(item.total_amount, item.currency)}
                    </span>
                    <span className="text-[10px] text-slate-600 md:mt-0.5 md:block">
                      {relativeTime(item.created_at)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={cx(
                        "font-mono text-sm",
                        item.high_flag_count > 0
                          ? "text-rose-300"
                          : item.flag_count > 0
                            ? "text-amber-200"
                            : "text-slate-500",
                      )}
                    >
                      {item.flag_count}
                    </span>
                    <span className="text-[10px] text-slate-600">
                      {item.high_flag_count > 0 ? `${item.high_flag_count} high` : "total"}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <CaseStatusBadge status={item.status} />
                    {item.review_status !== "pending_review" ? (
                      <ReviewBadge status={item.review_status} />
                    ) : null}
                  </div>
                  <span className="hidden text-slate-600 transition group-hover:translate-x-0.5 group-hover:text-signal md:block">
                    <ArrowRightIcon className="h-4 w-4" />
                  </span>
                </button>
              ))}
            </div>
          )}
        </Panel>

        <div className="space-y-5">
          <Panel className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-white">Flag mix</h2>
                <p className="mt-1 text-[11px] text-slate-500">What the rules found</p>
              </div>
              <AlertIcon className="h-4 w-4 text-slate-600" />
            </div>
            <div className="mt-5 space-y-3.5">
              {dashboard?.flag_counts.length ? (
                dashboard.flag_counts.slice(0, 7).map((item) => (
                  <div key={item.code}>
                    <div className="mb-1.5 flex items-center justify-between gap-3">
                      <span className="truncate text-[11px] text-slate-400">{item.label}</span>
                      <span className="font-mono text-[10px] text-slate-300">{item.count}</span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.05]">
                      <div
                        className={cx(
                          "h-full rounded-full",
                          item.code.includes("missing") || item.code.includes("not_found")
                            ? "bg-amber-300/70"
                            : item.code.includes("arithmetic") || item.code.includes("total")
                              ? "bg-rose-400/70"
                              : "bg-cyan-300/60",
                        )}
                        style={{ width: `${Math.max(6, (item.count / maxFlag) * 100)}%` }}
                      />
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-xl border border-dashed border-white/10 px-4 py-8 text-center text-[11px] leading-5 text-slate-500">
                  No flags yet. A clean invoice still goes to human review.
                </div>
              )}
            </div>
          </Panel>

          <Panel className="overflow-hidden">
            <div className="border-b border-white/[0.07] px-5 py-4">
              <h2 className="text-sm font-semibold text-white">How a decision is made</h2>
            </div>
            <div className="space-y-0 p-2">
              {[
                {
                  icon: SparkIcon,
                  title: "Model extracts",
                  body: health?.model_configured
                    ? `Open model ${health.model_name} proposes fields and evidence snippets.`
                    : "Fixture mode is active; bundled synthetic samples use deterministic data.",
                },
                {
                  icon: CheckIcon,
                  title: "Python matches",
                  body: "Decimal arithmetic, PO lookup, tolerance rules, and vendor similarity.",
                },
                {
                  icon: ShieldIcon,
                  title: "Human reviews",
                  body: "A reviewer inspects both values and the source evidence. No auto-approval.",
                },
              ].map((step, index) => {
                const Icon = step.icon;
                return (
                  <div
                    key={step.title}
                    className="flex gap-3 rounded-xl px-3 py-3 transition hover:bg-white/[0.025]"
                  >
                    <span className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] bg-ink-900 text-slate-400">
                      <Icon className="h-4 w-4" />
                      {index < 2 ? (
                        <span className="absolute -bottom-3 left-1/2 h-3 w-px -translate-x-1/2 bg-white/10" />
                      ) : null}
                    </span>
                    <div>
                      <div className="text-xs font-medium text-slate-200">{step.title}</div>
                      <p className="mt-1 text-[10px] leading-4 text-slate-500">{step.body}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}