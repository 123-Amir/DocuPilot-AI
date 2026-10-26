import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import type { CaseDetail, ReviewStatus } from "../lib/types";
import { Mono, Panel } from "./ui";
import { CheckIcon, ShieldIcon } from "./Icons";
import { reviewStatusCopy } from "../lib/format";

const OPTIONS: ReviewStatus[] = [
  "pending_review",
  "in_review",
  "reviewed_ok",
  "needs_vendor_contact",
  "rejected",
];

export default function ReviewPanel({
  detail,
  onUpdated,
}: {
  detail: CaseDetail;
  onUpdated: (next: CaseDetail) => void;
}) {
  const [status, setStatus] = useState<ReviewStatus>(detail.review.status);
  const [note, setNote] = useState(detail.review.note ?? "");
  const [reviewer, setReviewer] = useState(detail.review.reviewer ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setStatus(detail.review.status);
    setNote(detail.review.note ?? "");
    setReviewer(detail.review.reviewer ?? "");
  }, [detail.id, detail.review.status, detail.review.note, detail.review.reviewer]);

  async function save() {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const next = await api.review(detail.id, status, note, reviewer);
      onUpdated(next);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2400);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Could not save the review.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel className="overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-white/[0.07] px-4 py-3.5">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-signal">
            <ShieldIcon className="h-3.5 w-3.5" />
          </span>
          <div>
            <h2 className="text-xs font-semibold text-white">Human review</h2>
            <p className="font-mono text-[9px] uppercase tracking-[0.1em] text-slate-600">
              decision log
            </p>
          </div>
        </div>
      </div>
      <div className="p-4">
        <label className="block">
          <Mono>Review status</Mono>
          <select
            className="input mt-2 text-[11px]"
            value={status}
            onChange={(event) => setStatus(event.target.value as ReviewStatus)}
          >
            {OPTIONS.map((option) => (
              <option key={option} value={option}>
                {reviewStatusCopy[option]}
              </option>
            ))}
          </select>
        </label>

        <label className="mt-3 block">
          <Mono>Reviewer name (optional)</Mono>
          <input
            className="input mt-2 text-[11px]"
            value={reviewer}
            onChange={(event) => setReviewer(event.target.value)}
            placeholder="e.g. A. Hussain"
            maxLength={120}
          />
        </label>

        <label className="mt-3 block">
          <Mono>Note</Mono>
          <textarea
            className="input mt-2 min-h-[70px] resize-y text-[11px]"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="What did you verify? What is still open?"
            maxLength={2000}
          />
        </label>

        <button className="btn-primary mt-3 w-full" onClick={() => void save()} disabled={busy}>
          <CheckIcon className="h-4 w-4" />
          {busy ? "Saving…" : "Record review"}
        </button>

        {saved ? (
          <p className="mt-2 text-center text-[10px] text-signal">Review recorded.</p>
        ) : null}
        {error ? (
          <p className="mt-2 rounded-lg border border-rose-300/25 bg-rose-300/[0.06] px-2.5 py-2 text-[10px] leading-5 text-rose-100">
            {error}
          </p>
        ) : null}
        <p className="mt-3 border-t border-white/[0.06] pt-2.5 text-[9px] leading-4 text-slate-600">
          Recording a review is a note, not an approval to pay. DocuPilot has no
          payment capability.
        </p>
      </div>
    </Panel>
  );
}