import type { FieldEvidence, Flag, Severity } from "../lib/types";
import { shortField } from "../lib/format";
import { SeverityBadge, cx } from "./ui";

const accent: Record<Severity, string> = {
  high: "bg-rose-400",
  medium: "bg-amber-300",
  low: "bg-cyan-300",
  info: "bg-slate-500",
};

const halo: Record<Severity, string> = {
  high: "border-rose-300/20 bg-rose-300/[0.035]",
  medium: "border-amber-300/20 bg-amber-300/[0.03]",
  low: "border-cyan-300/15 bg-cyan-300/[0.02]",
  info: "border-white/10 bg-white/[0.02]",
};

function sourceLabel(source: FieldEvidence["source"]): string {
  if (source === "po_record") return "purchase order";
  if (source === "computed") return "computed";
  if (source === "invoice_image") return "invoice image";
  return "invoice text";
}

export default function FlagCard({ flag }: { flag: Flag }) {
  return (
    <article
      id={`flag-${flag.id}`}
      className={cx(
        "relative scroll-mt-24 overflow-hidden rounded-2xl border",
        halo[flag.severity],
      )}
    >
      <span className={cx("absolute inset-y-0 left-0 w-1", accent[flag.severity])} />
      <div className="p-5 pl-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <SeverityBadge severity={flag.severity} />
              <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-slate-500">
                {flag.id}
              </span>
              {flag.field ? (
                <span className="rounded-md border border-white/[0.07] bg-ink-950/50 px-2 py-0.5 font-mono text-[9px] text-slate-500">
                  {shortField(flag.field)}
                </span>
              ) : null}
            </div>
            <h3 className="mt-2 text-sm font-semibold text-white">{flag.title}</h3>
          </div>
          <span className="rounded-md border border-white/[0.06] bg-ink-950/40 px-2 py-1 font-mono text-[9px] uppercase tracking-[0.1em] text-slate-500">
            {flag.code}
          </span>
        </div>

        <p className="mt-2.5 max-w-3xl text-xs leading-5 text-slate-400">{flag.detail}</p>

        <div className="mt-4 grid gap-2 sm:grid-cols-3">
          <ValueBox label="Invoice value" value={flag.invoice_value} emphasis={false} />
          <ValueBox label="Purchase order" value={flag.po_value} emphasis={false} />
          <ValueBox label="Delta" value={flag.delta} emphasis />
        </div>

        <div className="mt-4">
          <div className="mb-2 flex items-center gap-2">
            <span className="font-mono text-[9px] uppercase tracking-[0.16em] text-slate-500">
              Evidence
            </span>
            <span className="h-px flex-1 bg-white/[0.06]" />
          </div>
          {flag.evidence.length === 0 ? (
            <p className="rounded-lg border border-dashed border-white/10 px-3 py-2.5 text-[11px] text-slate-500">
              No evidence captured. Open the source document before deciding.
            </p>
          ) : (
            <div className="space-y-2">
              {flag.evidence.map((item, index) => (
                <div
                  key={`${item.field}-${index}`}
                  className="rounded-lg border border-white/[0.06] bg-ink-950/50 px-3 py-2.5"
                >
                  <div className="flex flex-wrap items-center gap-2 font-mono text-[9px] uppercase tracking-[0.1em] text-slate-600">
                    <span className="text-slate-500">{item.field}</span>
                    {item.page ? <span>page {item.page}</span> : null}
                    <span>· {sourceLabel(item.source)}</span>
                  </div>
                  <p className="mt-1.5 font-mono text-[11px] leading-5 text-slate-300">
                    {item.snippet ? `“${item.snippet}”` : "No verbatim snippet returned."}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="mt-3 border-t border-white/[0.05] pt-2.5">
          <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-slate-600">
            rule
          </span>
          <span className="ml-2 font-mono text-[10px] leading-5 text-slate-500">{flag.rule}</span>
        </div>
      </div>
    </article>
  );
}

function ValueBox({
  label,
  value,
  emphasis,
}: {
  label: string;
  value: string | null;
  emphasis: boolean;
}) {
  return (
    <div className="rounded-xl border border-white/[0.07] bg-ink-950/50 px-3 py-2.5">
      <div className="font-mono text-[9px] uppercase tracking-[0.14em] text-slate-600">
        {label}
      </div>
      <div
        className={cx(
          "mt-1 truncate font-mono text-sm",
          emphasis ? "text-signal" : "text-slate-200",
        )}
      >
        {value ?? "—"}
      </div>
    </div>
  );
}