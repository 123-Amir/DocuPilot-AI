import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../lib/api";
import type { ChatMessage, Health } from "../lib/types";
import { Badge, Mono, Panel, Spinner, cx } from "./ui";
import { ArrowRightIcon, ChatIcon, ShieldIcon, SparkIcon } from "./Icons";

const SUGGESTIONS = [
  "Why is the total different?",
  "Which values caused each flag?",
  "What should a human reviewer check next?",
];

export default function ChatPanel({
  caseId,
  initialMessages,
  health,
}: {
  caseId: string;
  initialMessages: ChatMessage[];
  health: Health | null;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages(initialMessages);
  }, [initialMessages]);

  useEffect(() => {
    const node = scrollRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages, busy]);

  const lastAssistant = [...messages].reverse().find((item) => item.role === "assistant");
  const followUps = lastAssistant?.follow_ups?.length ? lastAssistant.follow_ups : SUGGESTIONS;

  async function send(text: string) {
    const question = text.trim();
    if (!question || busy) return;
    setDraft("");
    setError(null);
    setBusy(true);
    const optimistic: ChatMessage = {
      id: `local-${Date.now()}`,
      case_id: caseId,
      role: "user",
      content: question,
      created_at: new Date().toISOString(),
      citations: [],
      follow_ups: [],
      source: null,
    };
    setMessages((current) => [...current, optimistic]);
    try {
      const response = await api.chat(caseId, question);
      try {
        const refreshed = await api.messages(caseId);
        setMessages(refreshed);
      } catch {
        setMessages((current) => [...current, response.message]);
      }
    } catch (err: unknown) {
      const message =
        err instanceof ApiError ? err.message : "The investigation assistant did not answer.";
      setError(message);
      setMessages((current) => current.filter((item) => item.id !== optimistic.id));
      setDraft(question);
    } finally {
      setBusy(false);
    }
  }

  function jumpToFlag(flagId: string) {
    const node = document.getElementById(`flag-${flagId}`);
    node?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  return (
    <Panel className="overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-white/[0.07] px-4 py-3.5">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-signal">
            <ChatIcon className="h-3.5 w-3.5" />
          </span>
          <div>
            <h2 className="text-xs font-semibold text-white">Investigate</h2>
            <p className="font-mono text-[9px] uppercase tracking-[0.1em] text-slate-600">
              grounded in case facts
            </p>
          </div>
        </div>
        <Badge tone={health?.model_configured ? "signal" : "warn"}>
          <SparkIcon className="h-3 w-3" />
          {health?.model_configured ? "Alan model" : "explainer"}
        </Badge>
      </div>

      <div
        ref={scrollRef}
        className="max-h-[420px] min-h-[160px] space-y-3 overflow-y-auto px-4 py-4"
      >
        {messages.length === 0 ? (
          <div className="rounded-xl border border-white/[0.06] bg-ink-950/40 p-4">
            <div className="flex items-center gap-2 text-[11px] font-medium text-slate-300">
              <SparkIcon className="h-3.5 w-3.5 text-signal" />
              Ask about the evidence
            </div>
            <p className="mt-2 text-[11px] leading-5 text-slate-500">
              The assistant reads the same flag values and evidence you see. It never
              recalculates totals and never approves payment.
            </p>
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={cx(
                "flex",
                message.role === "user" ? "justify-end" : "justify-start",
              )}
            >
              <div
                className={cx(
                  "max-w-[92%] rounded-xl px-3.5 py-2.5 text-[12px] leading-5",
                  message.role === "user"
                    ? "bg-signal/[0.09] text-slate-100 ring-1 ring-signal/20"
                    : "bg-white/[0.035] text-slate-300 ring-1 ring-white/[0.06]",
                )}
              >
                <p className="whitespace-pre-wrap">{message.content}</p>
                {message.citations.length ? (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {message.citations.map((citation) => (
                      <button
                        key={citation}
                        onClick={() => jumpToFlag(citation)}
                        className="rounded border border-signal/25 bg-signal/[0.07] px-1.5 py-0.5 font-mono text-[9px] text-signal transition hover:bg-signal/[0.14]"
                      >
                        {citation}
                      </button>
                    ))}
                  </div>
                ) : null}
                {message.role === "assistant" && message.source ? (
                  <div className="mt-2 font-mono text-[8px] uppercase tracking-[0.08em] text-slate-600">
                    {message.source}
                  </div>
                ) : null}
              </div>
            </div>
          ))
        )}
        {busy ? (
          <div className="flex justify-start">
            <div className="rounded-xl bg-white/[0.03] px-3.5 py-2.5 ring-1 ring-white/[0.06]">
              <Spinner label="Reading the case evidence" />
            </div>
          </div>
        ) : null}
      </div>

      {error ? (
        <div className="mx-4 mb-3 rounded-lg border border-rose-300/25 bg-rose-300/[0.06] px-3 py-2 text-[11px] leading-5 text-rose-100">
          {error}
        </div>
      ) : null}

      {messages.length > 0 ? (
        <div className="flex flex-wrap gap-1.5 px-4 pb-3">
          {followUps.slice(0, 3).map((question) => (
            <button
              key={question}
              onClick={() => send(question)}
              disabled={busy}
              className="group inline-flex items-center gap-1 rounded-full border border-white/[0.08] bg-white/[0.02] px-2.5 py-1 text-[10px] text-slate-400 transition hover:border-signal/30 hover:text-signal disabled:opacity-40"
            >
              {question}
              <ArrowRightIcon className="h-2.5 w-2.5 opacity-0 transition group-hover:opacity-100" />
            </button>
          ))}
        </div>
      ) : null}

      <div className="border-t border-white/[0.07] p-3">
        <div className="flex items-end gap-2">
          <textarea
            className="input max-h-28 min-h-[42px] resize-y py-2.5"
            rows={2}
            placeholder="Ask about a value, flag, or next step…"
            value={draft}
            disabled={busy}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void send(draft);
              }
            }}
          />
          <button
            className="btn-primary h-[42px] px-3.5"
            onClick={() => void send(draft)}
            disabled={busy || !draft.trim()}
            aria-label="Send investigation question"
          >
            <ArrowRightIcon className="h-4 w-4" />
          </button>
        </div>
        <div className="mt-2 flex items-center gap-1.5 px-1">
          <ShieldIcon className="h-3 w-3 text-slate-600" />
          <Mono className="text-[8px] tracking-[0.08em]">
            Explains evidence only · never approves or pays
          </Mono>
        </div>
      </div>
    </Panel>
  );
}