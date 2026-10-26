import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../lib/api";
import type {
  AlanInvestigation,
  CaseDetail,
  ChatMessage,
  Flag,
  Health,
} from "../lib/types";
import type { Route } from "../components/Shell";
import {
  Alert,
  Badge,
  CaseStatusBadge,
  CheckRow,
  Mono,
  Panel,
  ReviewBadge,
  Spinner,
  cx,
} from "../components/ui";
import {
  ArrowLeftIcon,
  CheckIcon,
  ExternalIcon,
  FileIcon,
  ScanIcon,
  ShieldIcon,
} from "../components/Icons";
import {
  formatAmount,
  formatDate,
  formatQuantity,
  relativeTime,
} from "../lib/format";
import FlagCard from "../components/FlagCard";
import ChatPanel from "../components/ChatPanel";
import AlanPanel from "../components/AlanPanel";
import ReviewPanel from "../components/ReviewPanel";

function valuesForFlag(flags: Flag[], field: string): Flag | undefined {
  return flags.find(
    (flag) =>
      flag.field === field ||
      (field === "total_amount" && flag.field === "subtotal"),
  );
}

export default function CasePage({
  caseId,
  health,
  onNavigate,
}: {
  caseId: string;
  health: Health | null;
  onNavigate: (route: Route) => void;
}) {
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [alanRuns, setAlanRuns] = useState<AlanInvestigation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    Promise.all([
      api.case(caseId),
      api.messages(caseId).catch(() => []),
      api.alanRuns(caseId).catch(() => []),
    ])
      .then(([caseDetail, transcript, runs]) => {
        if (!active) return;
        setDetail(caseDetail);
        setMessages(transcript);
        setAlanRuns(runs);
      })
      .catch((err: unknown) => {
        if (!active) return;
        setError(err instanceof ApiError ? err.message : "Could not load this case.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [caseId]);

  const flags = detail?.match?.flags ?? [];
  const flaggedLineIndexes = useMemo(() => {
    const indexes = new Set<number>();
    flags.forEach((flag) => {
      const match = flag.field?.match(/line_items\[(\d+)\]/);
      if (match) indexes.add(Number(match[1]));
    });
    return indexes;
  }, [flags]);

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Spinner label="Loading case, evidence, and transcript" />
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="mx-auto max-w-xl space-y-4 py-20 text-center">
        <h1 className="text-lg font-semibold text-white">Case unavailable</h1>
        <p className="text-sm text-slate-400">{error ?? "That case does not exist."}</p>
        <button className="btn-secondary" onClick={() => onNavigate({ name: "dashboard" })}>
          <ArrowLeftIcon className="h-4 w-4" />
          Back to dashboard
        </button>
      </div>
    );
  }

  const invoice = detail.invoice;
  const po = detail.purchase_order;
  const match = detail.match;
  const isFailed = detail.status === "failed";
  const highCount = flags.filter((flag) => flag.severity === "high").length;
  const mediumCount = flags.filter((flag) => flag.severity === "medium").length;

  const comparisonRows = [
    {
      key: "vendor_name",
      label: "Vendor",
      invoice: invoice?.vendor_name ?? null,
      po: po?.vendor_name ?? null,
      format: (value: string | null) => value,
    },
    {
      key: "invoice_number",
      label: "Invoice number",
      invoice: invoice?.invoice_number ?? null,
      po: null,
      format: (value: string | null) => value,
    },
    {
      key: "invoice_date",
      label: "Invoice date",
      invoice: invoice?.invoice_date ?? null,
      po: po?.issue_date ?? null,
      format: (value: string | null) => formatDate(value),
    },
    {
      key: "currency",
      label: "Currency",
      invoice: invoice?.currency ?? null,
      po: po?.currency ?? null,
      format: (value: string | null) => value,
    },
    {
      key: "total_amount",
      label: "Total",
      invoice: invoice?.total_amount ?? null,
      po: po?.total_amount ?? null,
      format: (value: string | null) =>
        formatAmount(value, invoice?.currency ?? po?.currency),
    },
    {
      key: "po_number",
      label: "PO reference",
      invoice: invoice?.po_number ?? null,
      po: po?.po_number ?? null,
      format: (value: string | null) => value,
    },
  ];

  return (
    <div className="space-y-6 animate-rise">
      <button
        className="btn-ghost -ml-2"
        onClick={() => onNavigate({ name: "dashboard" })}
      >
        <ArrowLeftIcon className="h-4 w-4" />
        Back to review queue
      </button>

      <div className="flex flex-wrap items-start justify-between gap-5">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Mono>{detail.id}</Mono>
            <span className="h-3 w-px bg-white/10" />
            <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-slate-600">
              {detail.source === "demo" ? "synthetic sample" : "uploaded"} Â·{" "}
              {relativeTime(detail.created_at)}
            </span>
          </div>
          <h1 className="mt-2 truncate text-2xl font-semibold tracking-tight text-white lg:text-3xl">
            {detail.vendor_name ?? detail.filename}
          </h1>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <CaseStatusBadge status={detail.status} />
            <ReviewBadge status={detail.review.status} />
            <Badge tone={detail.model.mode === "model" ? "signal" : "warn"}>
              {detail.model.mode === "model" ? "open model" : "fixture"}
            </Badge>
            {detail.po_number ? <Badge tone="muted">PO {detail.po_number}</Badge> : null}
            <span className="font-mono text-[10px] text-slate-500">
              {detail.filename}
            </span>
          </div>
        </div>

        <div className="flex items-end gap-5">
          <div className="text-right">
            <Mono>Invoice total</Mono>
            <div className="mt-1 font-mono text-2xl tracking-tight text-white">
              {formatAmount(detail.total_amount, detail.currency)}
            </div>
            <div className="mt-1 font-mono text-[9px] uppercase tracking-[0.1em] text-slate-600">
              {detail.invoice_number ?? "no invoice number"}
            </div>
          </div>
          {detail.document_url ? (
            <a
              className="btn-secondary"
              href={detail.document_url}
              target="_blank"
              rel="noreferrer"
            >
              <FileIcon className="h-4 w-4" />
              Source
              <ExternalIcon className="h-3 w-3 opacity-60" />
            </a>
          ) : null}
        </div>
      </div>

      {isFailed ? (
        <Alert tone="danger" title="Extraction failed â€” no matching was performed">
          {detail.error ?? detail.model.note ?? "The document could not be processed."}
        </Alert>
      ) : (
        <div className="flex items-start gap-3 rounded-xl border border-ember/20 bg-ember/[0.045] px-4 py-3">
          <ShieldIcon className="mt-0.5 h-4 w-4 shrink-0 text-ember" />
          <p className="text-xs leading-5 text-slate-300">
            <span className="font-semibold text-ember">Review required.</span> Values
            below come from the document and the synthetic PO book. The verdict is
            deterministic Python; the chat explains it. Nothing is approved or paid.
          </p>
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-5">
          {match && invoice ? (
            <>
              <Panel className="overflow-hidden">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.07] px-5 py-4">
                  <div>
                    <h2 className="text-sm font-semibold text-white">Three-way match</h2>
                    <p className="mt-1 text-[11px] text-slate-500">
                      Invoice vs purchase order Â·{" "}
                      {match.po_match_method === "po_number"
                        ? "linked by PO number"
                        : match.po_match_method === "vendor"
                          ? "linked by vendor name"
                          : "no PO linked"}
                      {match.vendor_similarity !== null
                        ? ` Â· vendor similarity ${match.vendor_similarity.toFixed(2)}`
                        : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge tone="muted">Python / Decimal</Badge>
                    <Badge tone={highCount ? "danger" : mediumCount ? "warn" : "signal"}>
                      {flags.length} flag{flags.length === 1 ? "" : "s"}
                    </Badge>
                  </div>
                </div>

                <div className="hidden grid-cols-[150px_1fr_1fr_120px] gap-3 border-b border-white/[0.06] bg-ink-950/30 px-5 py-2.5 md:grid">
                  {["Field", "Invoice", "Purchase order", "Verdict"].map((label) => (
                    <Mono key={label}>{label}</Mono>
                  ))}
                </div>

                {comparisonRows.map((row) => {
                  const flag = valuesForFlag(flags, row.key);
                  const noPo = !po;
                  return (
                    <div
                      key={row.key}
                      className="grid grid-cols-1 gap-2 border-b border-white/[0.055] px-5 py-3 text-xs last:border-0 md:grid-cols-[150px_1fr_1fr_120px] md:items-center md:gap-3"
                    >
                      <div className="font-mono text-[10px] uppercase tracking-[0.1em] text-slate-500">
                        {row.label}
                      </div>
                      <div className="flex items-baseline gap-2">
                        <span className="font-mono text-[9px] uppercase tracking-[0.08em] text-slate-600 md:hidden">
                          invoice
                        </span>
                        <span className="truncate text-slate-200">
                          {row.format(row.invoice) ?? "â€”"}
                        </span>
                      </div>
                      <div className="flex items-baseline gap-2">
                        <span className="font-mono text-[9px] uppercase tracking-[0.08em] text-slate-600 md:hidden">
                          po
                        </span>
                        <span className="truncate text-slate-400">
                          {row.format(row.po) ?? "â€”"}
                        </span>
                      </div>
                      <div>
                        {flag ? (
                          <button
                            onClick={() =>
                              document
                                .getElementById(`flag-${flag.id}`)
                                ?.scrollIntoView({ behavior: "smooth", block: "center" })
                            }
                            className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-2 py-1 font-mono text-[9px] text-slate-300 transition hover:border-signal/30 hover:text-signal"
                          >
                            <span
                              className={cx(
                                "h-1.5 w-1.5 rounded-full",
                                flag.severity === "high"
                                  ? "bg-rose-400"
                                  : flag.severity === "medium"
                                    ? "bg-amber-300"
                                    : "bg-cyan-300",
                              )}
                            />
                            {flag.id}
                          </button>
                        ) : row.key === "invoice_number" ? (
                          <span className="inline-flex items-center gap-1 text-[10px] text-slate-500">
                            <CheckIcon className="h-3 w-3 text-slate-500" />
                            captured
                          </span>
                        ) : noPo ? (
                          <span className="text-[10px] text-slate-600">no PO</span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[10px] text-signal">
                            <CheckIcon className="h-3 w-3" />
                            match
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}

                <div className="grid gap-3 border-t border-white/[0.06] bg-ink-950/30 px-5 py-4 sm:grid-cols-3">
                  <MathBox
                    label="Computed line sum"
                    value={formatAmount(match.computed_line_sum, invoice.currency)}
                    note="sum of line totals"
                  />
                  <MathBox
                    label="Printed subtotal / total"
                    value={formatAmount(
                      invoice.subtotal ?? match.printed_total,
                      invoice.currency,
                    )}
                    note={invoice.subtotal ? "from document" : "no subtotal printed"}
                  />
                  <MathBox
                    label="Arithmetic delta"
                    value={formatAmount(match.arithmetic_delta, invoice.currency)}
                    note={
                      match.arithmetic_delta
                        ? "printed âˆ’ computed"
                        : "within 0.01 tolerance"
                    }
                    danger={Boolean(match.arithmetic_delta)}
                  />
                </div>
              </Panel>

              <section className="space-y-3">
                <div className="flex flex-wrap items-end justify-between gap-3">
                  <div>
                    <h2 className="text-sm font-semibold text-white">Flags and evidence</h2>
                    <p className="mt-1 text-[11px] text-slate-500">
                      Each flag shows the invoice value, the PO value, the delta, the
                      rule, and the source snippet.
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {highCount ? <Badge tone="danger">{highCount} high</Badge> : null}
                    {mediumCount ? <Badge tone="warn">{mediumCount} medium</Badge> : null}
                  </div>
                </div>

                {flags.length === 0 ? (
                  <div className="rounded-2xl border border-signal/20 bg-signal/[0.04] p-5">
                    <div className="flex items-center gap-2 text-sm font-medium text-signal">
                      <CheckIcon className="h-4 w-4" />
                      No mismatch flags
                    </div>
                    <p className="mt-2 text-xs leading-5 text-slate-400">
                      Required fields are present, the vendor and totals agree, line
                      items match, and the invoice arithmetic adds up. This is still not
                      an approval; a human must confirm the source document.
                    </p>
                  </div>
                ) : (
                  flags.map((flag) => <FlagCard key={flag.id} flag={flag} />)
                )}
              </section>

              <Panel className="overflow-hidden">
                <div className="border-b border-white/[0.07] px-5 py-4">
                  <h2 className="text-sm font-semibold text-white">Line items</h2>
                  <p className="mt-1 text-[11px] text-slate-500">
                    Invoice lines and PO lines side by side. Highlighted invoice rows
                    have at least one line-level flag.
                  </p>
                </div>
                <div className="grid gap-0 lg:grid-cols-2">
                  <div className="border-b border-white/[0.07] lg:border-b-0 lg:border-r">
                    <div className="flex items-center justify-between bg-ink-950/30 px-4 py-2">
                      <Mono>Invoice lines</Mono>
                      <span className="font-mono text-[9px] text-slate-600">
                        {invoice.line_items.length}
                      </span>
                    </div>
                    <div className="divide-y divide-white/[0.055]">
                      {invoice.line_items.length === 0 ? (
                        <p className="px-4 py-8 text-center text-[11px] text-slate-500">
                          No line items extracted.
                        </p>
                      ) : (
                        invoice.line_items.map((line, index) => (
                          <div
                            key={`${line.sku ?? line.description}-${index}`}
                            className={cx(
                              "px-4 py-3",
                              flaggedLineIndexes.has(index) && "bg-rose-300/[0.035]",
                            )}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <div className="truncate text-xs text-slate-200">
                                  {line.description}
                                </div>
                                <div className="mt-0.5 flex flex-wrap items-center gap-2 font-mono text-[9px] text-slate-600">
                                  <span>{line.sku ?? "no sku"}</span>
                                  <span>
                                    {formatQuantity(line.quantity)} Ã—{" "}
                                    {formatAmount(line.unit_price, invoice.currency)}
                                  </span>
                                  {line.line_total_source === "computed" ? (
                                    <span className="rounded border border-amber-300/20 bg-amber-300/[0.06] px-1 py-0.5 text-[8px] text-amber-200">
                                      computed by Python
                                    </span>
                                  ) : null}
                                </div>
                              </div>
                              <div className="shrink-0 font-mono text-xs text-slate-200">
                                {formatAmount(line.line_total, invoice.currency)}
                              </div>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between bg-ink-950/30 px-4 py-2">
                      <Mono>Purchase order lines</Mono>
                      <span className="font-mono text-[9px] text-slate-600">
                        {po?.line_items.length ?? 0}
                      </span>
                    </div>
                    <div className="divide-y divide-white/[0.055]">
                      {!po ? (
                        <p className="px-4 py-8 text-center text-[11px] text-slate-500">
                          No purchase order linked.
                        </p>
                      ) : po.line_items.length === 0 ? (
                        <p className="px-4 py-8 text-center text-[11px] text-slate-500">
                          The PO has no line items.
                        </p>
                      ) : (
                        po.line_items.map((line, index) => (
                          <div key={`${line.sku ?? line.description}-${index}`} className="px-4 py-3">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <div className="truncate text-xs text-slate-300">
                                  {line.description}
                                </div>
                                <div className="mt-0.5 flex flex-wrap items-center gap-2 font-mono text-[9px] text-slate-600">
                                  <span>{line.sku ?? "no sku"}</span>
                                  <span>
                                    {formatQuantity(line.quantity)} Ã—{" "}
                                    {formatAmount(line.unit_price, po.currency)}
                                  </span>
                                </div>
                              </div>
                              <div className="shrink-0 font-mono text-xs text-slate-400">
                                {formatAmount(line.line_total, po.currency)}
                              </div>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              </Panel>

              <Panel className="p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-sm font-semibold text-white">Deterministic checks</h2>
                    <p className="mt-1 text-[11px] text-slate-500">
                      Pass/fail outcomes from the Python rules
                    </p>
                  </div>
                  <Badge tone="muted">
                    <ScanIcon className="h-3 w-3" />
                    no model math
                  </Badge>
                </div>
                <div className="mt-3 grid gap-x-8 lg:grid-cols-2">
                  {match.checks.map((check) => (
                    <CheckRow
                      key={check.name}
                      status={check.status}
                      label={check.name}
                      detail={check.detail}
                    />
                  ))}
                </div>
              </Panel>
            </>
          ) : null}

          {isFailed ? (
            <Panel className="p-5">
              <h2 className="text-sm font-semibold text-white">Document</h2>
              <p className="mt-2 text-xs leading-5 text-slate-400">
                The file was accepted but extraction failed, so no invoice or PO
                comparison exists. Open the source document and inspect the error, or
                retry with a clearer copy.
              </p>
              {detail.document_url ? (
                <a
                  className="btn-secondary mt-3"
                  href={detail.document_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  <FileIcon className="h-4 w-4" />
                  Open source document
                </a>
              ) : null}
            </Panel>
          ) : null}
        </div>

        <div className="space-y-4">
          {!isFailed ? (
            <ChatPanel caseId={detail.id} initialMessages={messages} health={health} />
          ) : null}
          <AlanPanel health={health} caseId={detail.id} initialRuns={alanRuns} />
          <ReviewPanel detail={detail} onUpdated={setDetail} />
          <Panel className="p-4">
            <div className="flex items-center justify-between">
              <Mono>Provenance</Mono>
              <Badge tone={detail.model.mode === "model" ? "signal" : "warn"}>
                {detail.model.mode}
              </Badge>
            </div>
            <div className="mt-3 space-y-2 text-[10px] leading-4 text-slate-500">
              <div className="flex justify-between gap-3">
                <span>Extraction</span>
                <span className="text-right font-mono text-[9px] text-slate-400">
                  {detail.model.model ?? "unknown"}
                </span>
              </div>
              <div className="flex justify-between gap-3">
                <span>Provider</span>
                <span className="text-right font-mono text-[9px] text-slate-400">
                  {detail.model.provider}
                </span>
              </div>
              <div className="flex justify-between gap-3">
                <span>Latency</span>
                <span className="font-mono text-[9px] text-slate-400">
                  {detail.model.elapsed_ms != null
                    ? `${(detail.model.elapsed_ms / 1000).toFixed(1)}s`
                    : "instant"}
                </span>
              </div>
              <div className="flex justify-between gap-3">
                <span>Arithmetic</span>
                <span className="font-mono text-[9px] text-signal">Python Decimal</span>
              </div>
              <div className="flex justify-between gap-3">
                <span>Decision</span>
                <span className="font-mono text-[9px] text-slate-400">human</span>
              </div>
            </div>
            {detail.model.note ? (
              <p className="mt-3 border-t border-white/[0.06] pt-2.5 text-[10px] leading-4 text-slate-500">
                {detail.model.note}
              </p>
            ) : null}
            {detail.model.mode === "fixture" ? (
              <div className="mt-3 rounded-lg border border-amber-300/20 bg-amber-300/[0.04] px-2.5 py-2 text-[9px] leading-4 text-amber-100/80">
                Fixture extraction: no live model call produced these fields.
              </div>
            ) : null}
          </Panel>
        </div>
      </div>
    </div>
  );
}

function MathBox({
  label,
  value,
  note,
  danger,
}: {
  label: string;
  value: string;
  note: string;
  danger?: boolean;
}) {
  return (
    <div
      className={cx(
        "rounded-xl border px-3 py-2.5",
        danger
          ? "border-rose-300/20 bg-rose-300/[0.04]"
          : "border-white/[0.07] bg-ink-950/40",
      )}
    >
      <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-slate-600">
        {label}
      </div>
      <div
        className={cx(
          "mt-1 font-mono text-sm",
          danger ? "text-rose-200" : "text-slate-200",
        )}
      >
        {value}
      </div>
      <div className="mt-0.5 text-[9px] text-slate-600">{note}</div>
    </div>
  );
}

