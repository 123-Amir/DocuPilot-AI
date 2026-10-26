import type { ReactNode } from "react";
import type { CaseStatus, ReviewStatus, Severity } from "../lib/types";
import { caseStatusCopy, reviewStatusCopy, severityCopy } from "../lib/format";
import { AlertIcon, CheckIcon, FileIcon } from "./Icons";

export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

export function Panel({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cx(
        "rounded-2xl border border-white/[0.08] bg-white/[0.035] shadow-panel",
        className,
      )}
    >
      {children}
    </section>
  );
}

export function Mono({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span className={cx("font-mono text-[10px] uppercase tracking-[0.16em] text-slate-500", className)}>
      {children}
    </span>
  );
}

type Tone = "neutral" | "signal" | "info" | "warn" | "danger" | "muted";

const toneClasses: Record<Tone, string> = {
  neutral: "border-white/15 bg-white/[0.06] text-slate-200",
  signal: "border-signal/30 bg-signal/10 text-signal",
  info: "border-cyan-300/25 bg-cyan-300/10 text-cyan-200",
  warn: "border-amber-300/30 bg-amber-300/10 text-amber-200",
  danger: "border-rose-300/30 bg-rose-300/10 text-rose-200",
  muted: "border-white/10 bg-white/[0.03] text-slate-400",
};

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.12em]",
        toneClasses[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

const severityTone: Record<Severity, Tone> = {
  high: "danger",
  medium: "warn",
  low: "info",
  info: "muted",
};

const severityDot: Record<Severity, string> = {
  high: "bg-rose-400",
  medium: "bg-amber-300",
  low: "bg-cyan-300",
  info: "bg-slate-400",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <Badge tone={severityTone[severity]}>
      <span className={cx("h-1.5 w-1.5 rounded-full", severityDot[severity])} />
      {severityCopy[severity]}
    </Badge>
  );
}

const caseTone: Record<CaseStatus, Tone> = {
  needs_review: "warn",
  no_mismatch: "signal",
  failed: "danger",
};

const caseDot: Record<CaseStatus, string> = {
  needs_review: "bg-amber-300",
  no_mismatch: "bg-signal",
  failed: "bg-rose-400",
};

export function CaseStatusBadge({ status }: { status: CaseStatus }) {
  return (
    <Badge tone={caseTone[status]}>
      <span className={cx("h-1.5 w-1.5 rounded-full", caseDot[status])} />
      {caseStatusCopy[status]}
    </Badge>
  );
}

const reviewTone: Record<ReviewStatus, Tone> = {
  pending_review: "muted",
  in_review: "info",
  reviewed_ok: "signal",
  needs_vendor_contact: "warn",
  rejected: "danger",
};

export function ReviewBadge({ status }: { status: ReviewStatus }) {
  return <Badge tone={reviewTone[status]}>{reviewStatusCopy[status]}</Badge>;
}

export function StatCard({
  label,
  value,
  detail,
  tone = "neutral",
}: {
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  tone?: Tone;
}) {
  return (
    <div className="group relative overflow-hidden rounded-2xl border border-white/[0.08] bg-ink-850/80 p-5">
      <div
        className={cx(
          "absolute inset-x-0 top-0 h-px",
          tone === "danger" && "bg-gradient-to-r from-transparent via-rose-400/60 to-transparent",
          tone === "warn" && "bg-gradient-to-r from-transparent via-amber-300/60 to-transparent",
          tone === "signal" && "bg-gradient-to-r from-transparent via-signal/60 to-transparent",
          tone === "info" && "bg-gradient-to-r from-transparent via-cyan-300/60 to-transparent",
          tone === "neutral" && "bg-gradient-to-r from-transparent via-white/20 to-transparent",
          tone === "muted" && "bg-transparent",
        )}
      />
      <Mono>{label}</Mono>
      <div className="mt-3 font-mono text-3xl tracking-tight text-white">{value}</div>
      {detail ? <div className="mt-2 text-xs leading-5 text-slate-500">{detail}</div> : null}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-xs text-slate-400">
      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/20 border-t-signal" />
      {label}
    </span>
  );
}

export function Alert({
  tone = "warn",
  title,
  children,
  className,
}: {
  tone?: "warn" | "danger" | "info" | "signal";
  title: string;
  children?: ReactNode;
  className?: string;
}) {
  const styles = {
    warn: "border-amber-300/25 bg-amber-300/[0.06] text-amber-100",
    danger: "border-rose-300/25 bg-rose-300/[0.06] text-rose-100",
    info: "border-cyan-300/25 bg-cyan-300/[0.05] text-cyan-100",
    signal: "border-signal/25 bg-signal/[0.05] text-signal",
  }[tone];
  return (
    <div className={cx("rounded-xl border px-4 py-3 text-sm leading-6", styles, className)}>
      <div className="flex gap-3">
        <AlertIcon className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <div className="font-medium">{title}</div>
          {children ? <div className="mt-1 text-[13px] opacity-80">{children}</div> : null}
        </div>
      </div>
    </div>
  );
}

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 px-6 py-14 text-center">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full border border-white/10 bg-white/[0.03] text-slate-500">
        <FileIcon className="h-5 w-5" />
      </div>
      <h3 className="text-sm font-medium text-slate-200">{title}</h3>
      <p className="mt-2 max-w-sm text-xs leading-5 text-slate-500">{body}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function CheckRow({
  status,
  label,
  detail,
}: {
  status: "pass" | "fail" | "info";
  label: string;
  detail: string;
}) {
  const icon =
    status === "pass" ? (
      <CheckIcon className="h-3.5 w-3.5 text-signal" />
    ) : status === "fail" ? (
      <span className="text-xs font-semibold text-rose-300">!</span>
    ) : (
      <span className="text-xs text-slate-500">i</span>
    );
  return (
    <div className="flex items-start gap-3 border-b border-white/[0.05] py-2.5 last:border-0">
      <span className="mt-0.5 flex h-4 w-4 items-center justify-center">{icon}</span>
      <div className="min-w-0">
        <div className="text-xs font-medium text-slate-200">{label}</div>
        <div className="mt-0.5 text-[11px] leading-5 text-slate-500">{detail}</div>
      </div>
    </div>
  );
}