import { useEffect, useRef, useState } from "react";
import type { DragEvent } from "react";
import { api, ApiError } from "../lib/api";
import type { CaseSummary, Health } from "../lib/types";
import type { Route } from "../components/Shell";
import {
  Alert,
  Badge,
  CaseStatusBadge,
  Mono,
  Panel,
  Spinner,
  cx,
} from "../components/ui";
import {
  ArrowRightIcon,
  CheckIcon,
  FileIcon,
  LockIcon,
  ScanIcon,
  UploadIcon,
} from "../components/Icons";

const ALLOWED = [".pdf", ".png", ".jpg", ".jpeg"];
const MAX_MB = 10;

function extension(name: string): string {
  const index = name.lastIndexOf(".");
  return index >= 0 ? name.slice(index).toLowerCase() : "";
}

function validate(file: File): string | null {
  if (!ALLOWED.includes(extension(file.name))) {
    return "Only PDF, PNG, JPG, and JPEG files are accepted.";
  }
  if (file.size === 0) return "That file is empty.";
  if (file.size > MAX_MB * 1024 * 1024) {
    return `That file is ${(file.size / 1024 / 1024).toFixed(1)} MB. The demo limit is ${MAX_MB} MB.`;
  }
  return null;
}

function bytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

export default function UploadPage({
  health,
  onNavigate,
}: {
  health: Health | null;
  onNavigate: (route: Route) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [serverError, setServerError] = useState<ApiError | null>(null);
  const [uploading, setUploading] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [samples, setSamples] = useState<CaseSummary[]>([]);

  useEffect(() => {
    api
      .cases()
      .then((list) => setSamples(list.filter((item) => item.source === "demo")))
      .catch(() => setSamples([]));
  }, []);

  useEffect(() => {
    if (!uploading) return;
    setSeconds(0);
    const timer = window.setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [uploading]);

  function choose(next: File | null) {
    setServerError(null);
    setLocalError(null);
    if (!next) {
      setFile(null);
      return;
    }
    const problem = validate(next);
    if (problem) {
      setLocalError(problem);
      setFile(null);
      return;
    }
    setFile(next);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragOver(false);
    choose(event.dataTransfer.files?.[0] ?? null);
  }

  async function submit() {
    if (!file || uploading) return;
    setUploading(true);
    setServerError(null);
    try {
      const created = await api.upload(file);
      onNavigate({ name: "case", id: created.id });
    } catch (error: unknown) {
      setServerError(
        error instanceof ApiError
          ? error
          : new ApiError("The upload failed unexpectedly.", "unknown_error", 0),
      );
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="space-y-7 animate-rise">
      <div>
        <Mono>Intake Â· new document</Mono>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white">
          Bring in one invoice.
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">
          The file is validated in the browser and again on the server. The server
          reads bytes only, extracts fields with the open model, and runs the
          deterministic matching rules.
        </p>
      </div>

      <Alert tone="warn" title="Synthetic demo only">
        Upload invented invoices. Do not upload real customer, supplier, or employee
        documents. Uploaded files are stored locally under <code className="font-mono">var/uploads</code>{" "}
        and are never executed.
      </Alert>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.65fr)]">
        <Panel className="overflow-hidden">
          <div className="border-b border-white/[0.07] px-5 py-4">
            <h2 className="text-sm font-semibold text-white">Source document</h2>
            <p className="mt-1 text-[11px] text-slate-500">
              PDF, PNG, JPG, or JPEG Â· up to {MAX_MB} MB Â· 5 PDF pages
            </p>
          </div>

          <div className="p-5">
            <div
              role="button"
              tabIndex={0}
              onClick={() => inputRef.current?.click()}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
              }}
              onDrop={onDrop}
              onDragOver={(event) => {
                event.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              className={cx(
                "focus-ring group flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed px-6 py-12 text-center transition",
                dragOver
                  ? "border-signal/60 bg-signal/[0.06]"
                  : "border-white/15 bg-ink-900/40 hover:border-white/25 hover:bg-white/[0.025]",
              )}
            >
              <span
                className={cx(
                  "flex h-14 w-14 items-center justify-center rounded-2xl border transition",
                  dragOver
                    ? "border-signal/40 bg-signal/10 text-signal"
                    : "border-white/10 bg-white/[0.03] text-slate-500 group-hover:text-slate-300",
                )}
              >
                <UploadIcon className="h-6 w-6" />
              </span>
              <span className="mt-4 text-sm font-medium text-slate-200">
                {dragOver ? "Drop the invoice here" : "Drop a file, or click to browse"}
              </span>
              <span className="mt-2 max-w-sm text-[11px] leading-5 text-slate-500">
                Text PDFs are read directly. Scanned PDFs and images are rendered and
                sent to the vision-capable open model.
              </span>
              <input
                ref={inputRef}
                type="file"
                accept={ALLOWED.join(",")}
                className="hidden"
                onChange={(event) => choose(event.target.files?.[0] ?? null)}
              />
            </div>

            {localError ? (
              <div className="mt-4 rounded-xl border border-rose-300/25 bg-rose-300/[0.06] px-4 py-3 text-xs leading-5 text-rose-100">
                <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-rose-300">
                  validation
                </span>
                <p className="mt-1">{localError}</p>
              </div>
            ) : null}

            {serverError ? (
              <div className="mt-4 rounded-xl border border-rose-300/25 bg-rose-300/[0.06] px-4 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-rose-300">
                    upload rejected
                  </span>
                  <Badge tone="danger">{serverError.code}</Badge>
                  <span className="font-mono text-[10px] text-slate-500">
                    HTTP {serverError.status}
                  </span>
                </div>
                <p className="mt-2 text-xs leading-5 text-rose-100">{serverError.message}</p>
                {serverError.caseId ? (
                  <p className="mt-2 text-[10px] text-slate-500">
                    A failed case was recorded for audit:{" "}
                    <span className="font-mono">{serverError.caseId}</span>
                  </p>
                ) : null}
              </div>
            ) : null}

            {file ? (
              <div className="mt-5 flex flex-wrap items-center gap-4 rounded-xl border border-white/[0.08] bg-ink-900/60 p-4">
                <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-signal">
                  <FileIcon className="h-5 w-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm text-slate-200">{file.name}</div>
                  <div className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.1em] text-slate-500">
                    {bytes(file.size)} Â· {extension(file.name).replace(".", "")}
                  </div>
                </div>
                <button
                  className="btn-ghost"
                  onClick={() => {
                    setFile(null);
                    if (inputRef.current) inputRef.current.value = "";
                  }}
                  disabled={uploading}
                >
                  Remove
                </button>
                <button className="btn-primary" onClick={submit} disabled={uploading}>
                  {uploading ? (
                    <>
                      <Spinner label="Processing" />
                    </>
                  ) : (
                    <>
                      <ScanIcon className="h-4 w-4" />
                      Extract and match
                    </>
                  )}
                </button>
              </div>
            ) : null}

            {uploading ? (
              <div className="mt-5 rounded-xl border border-cyan-300/15 bg-cyan-300/[0.035] p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className="relative flex h-8 w-8 items-center justify-center rounded-full border border-cyan-300/25 text-cyan-200">
                      <span className="absolute inset-0 animate-ping rounded-full border border-cyan-300/20" />
                      <ScanIcon className="h-4 w-4" />
                    </span>
                    <div>
                      <div className="text-xs font-medium text-cyan-100">
                        Reading, extracting, and matching
                      </div>
                      <div className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.12em] text-slate-500">
                        {seconds}s elapsed Â· open model can take up to ~90s
                      </div>
                    </div>
                  </div>
                  <span className="font-mono text-[10px] text-slate-500">do not refresh</span>
                </div>
                <div className="mt-4 h-1 overflow-hidden rounded-full bg-white/[0.06]">
                  <div className="h-full w-1/3 animate-pulseSoft rounded-full bg-gradient-to-r from-transparent via-cyan-300/70 to-transparent" />
                </div>
              </div>
            ) : null}
          </div>
        </Panel>

        <div className="space-y-5">
          <Panel className="p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white">Extraction path</h2>
              <SparkStatus configured={health?.model_configured ?? false} />
            </div>
            <div className="mt-4 space-y-3 text-[11px] leading-5 text-slate-400">
              <div className="flex gap-3">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-white/10 font-mono text-[9px] text-slate-500">
                  1
                </span>
                <p>
                  <span className="text-slate-200">Validate.</span> Extension, magic
                  bytes, size, page count, image dimensions, encryption.
                </p>
              </div>
              <div className="flex gap-3">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-white/10 font-mono text-[9px] text-slate-500">
                  2
                </span>
                <p>
                  <span className="text-slate-200">Extract.</span>{" "}
                  {health?.model_configured
                    ? `Open model ${health.model_name} proposes fields and evidence.`
                    : "No model key is configured, so only bundled synthetic samples can be extracted."}
                </p>
              </div>
              <div className="flex gap-3">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-white/10 font-mono text-[9px] text-slate-500">
                  3
                </span>
                <p>
                  <span className="text-slate-200">Match.</span> Python Decimal rules
                  compare the invoice to the PO. The model never does the math.
                </p>
              </div>
            </div>

            {!health?.model_configured ? (
              <Alert tone="warn" title="Fixture mode" className="mt-4">
                Set <code className="font-mono">ALAN_MODEL_API_KEY</code> on the server for
                arbitrary uploads. Bundled demo samples still work.
              </Alert>
            ) : null}
          </Panel>

          <Panel className="overflow-hidden">
            <div className="border-b border-white/[0.07] px-5 py-4">
              <h2 className="text-sm font-semibold text-white">Demo scenarios</h2>
              <p className="mt-1 text-[11px] text-slate-500">Open a prepared case instead</p>
            </div>
            {samples.length === 0 ? (
              <div className="px-5 py-8 text-center text-[11px] leading-5 text-slate-500">
                No synthetic samples seeded. Run{" "}
                <code className="font-mono text-slate-400">
                  python scripts/generate_samples.py
                </code>{" "}
                and restart the API.
              </div>
            ) : (
              <div>
                {samples.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => onNavigate({ name: "case", id: item.id })}
                    className="group flex w-full items-center gap-3 border-b border-white/[0.055] px-5 py-3.5 text-left transition last:border-0 hover:bg-white/[0.025]"
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-slate-500 group-hover:text-signal">
                      <FileIcon className="h-4 w-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-xs font-medium text-slate-200">
                        {item.vendor_name ?? item.filename}
                      </span>
                      <span className="mt-0.5 block truncate font-mono text-[9px] uppercase tracking-[0.1em] text-slate-600">
                        {item.invoice_number ?? item.filename}
                      </span>
                    </span>
                    <CaseStatusBadge status={item.status} />
                    <ArrowRightIcon className="h-3.5 w-3.5 text-slate-700 group-hover:text-signal" />
                  </button>
                ))}
              </div>
            )}
          </Panel>

          <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
              <LockIcon className="h-3.5 w-3.5" />
              What never happens
            </div>
            <ul className="mt-2 space-y-1.5 text-[10px] leading-4 text-slate-500">
              <li className="flex gap-2">
                <CheckIcon className="mt-0.5 h-3 w-3 shrink-0 text-slate-600" />
                No automatic approval, payment, or ERP write-back.
              </li>
              <li className="flex gap-2">
                <CheckIcon className="mt-0.5 h-3 w-3 shrink-0 text-slate-600" />
                No execution of uploaded files or embedded instructions.
              </li>
              <li className="flex gap-2">
                <CheckIcon className="mt-0.5 h-3 w-3 shrink-0 text-slate-600" />
                No API keys in the browser bundle.
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

function SparkStatus({ configured }: { configured: boolean }) {
  return (
    <Badge tone={configured ? "signal" : "warn"}>
      <span
        className={cx(
          "h-1.5 w-1.5 rounded-full",
          configured ? "bg-signal" : "bg-amber-300",
        )}
      />
      {configured ? "live model" : "fixture mode"}
    </Badge>
  );
}
