import type { CaseStatus, ReviewStatus, Severity } from "./types";

const amountFormatter = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** Display-only formatting. The backend owns every calculation. */
export function formatAmount(value: string | null | undefined, currency?: string | null): string {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  if (!Number.isFinite(number)) return value;
  const formatted = amountFormatter.format(number);
  return currency ? `${currency} ${formatted}` : formatted;
}

export function formatQuantity(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  if (!Number.isFinite(number)) return value;
  return Number.isInteger(number) ? String(number) : String(number);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value.length <= 10 ? `${value}T00:00:00` : value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export const severityCopy: Record<Severity, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Info",
};

export const caseStatusCopy: Record<CaseStatus, string> = {
  needs_review: "Needs review",
  no_mismatch: "Clean match",
  failed: "Extraction failed",
};

export const reviewStatusCopy: Record<ReviewStatus, string> = {
  pending_review: "Pending review",
  in_review: "In review",
  reviewed_ok: "Reviewed · OK",
  needs_vendor_contact: "Vendor contact",
  rejected: "Rejected",
};

export function relativeTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const diffMinutes = Math.round((date.getTime() - Date.now()) / 60000);
  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  if (Math.abs(diffMinutes) < 60) return formatter.format(diffMinutes, "minute");
  const hours = Math.round(diffMinutes / 60);
  if (Math.abs(hours) < 24) return formatter.format(hours, "hour");
  return formatter.format(Math.round(hours / 24), "day");
}

export function shortField(value: string | null): string {
  if (!value) return "field";
  return value.replace(/^line_items\[(\d+)\]\.?/, "line $1 · ").replace(/_/g, " ");
}