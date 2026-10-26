import type { ReactNode } from "react";
import type { Health } from "../lib/types";
import { cx } from "./ui";
import { DashboardIcon, LockIcon, ScanIcon, UploadIcon } from "./Icons";

export type Route =
  | { name: "dashboard" }
  | { name: "upload" }
  | { name: "case"; id: string };

function modelLabel(health: Health | null): string {
  if (!health) return "checking API";
  if (!health.model_configured) return "fixture mode";
  const model = health.model_name.split("/").pop() ?? health.model_name;
  return model.length > 22 ? `${model.slice(0, 22)}…` : model;
}

export default function Shell({
  health,
  route,
  onNavigate,
  onRefreshHealth,
  children,
}: {
  health: Health | null;
  route: Route;
  onNavigate: (route: Route) => void;
  onRefreshHealth: () => void;
  children: ReactNode;
}) {
  const nav = [
    {
      key: "dashboard" as const,
      label: "Dashboard",
      icon: DashboardIcon,
    },
    {
      key: "upload" as const,
      label: "Upload invoice",
      icon: UploadIcon,
    },
  ];

  const active = route.name === "upload" ? "upload" : "dashboard";

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[248px_minmax(0,1fr)]">
      <aside className="relative z-20 border-b border-white/[0.07] bg-ink-950/80 backdrop-blur-xl lg:sticky lg:top-0 lg:h-screen lg:border-b-0 lg:border-r">
        <div className="flex items-center justify-between px-5 py-4 lg:block lg:px-6 lg:py-7">
          <button
            className="focus-ring group flex items-center gap-3 rounded-xl"
            onClick={() => onNavigate({ name: "dashboard" })}
          >
            <span className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-signal/25 bg-signal/10 text-signal">
              <ScanIcon className="h-5 w-5" />
              <span className="absolute -right-0.5 -top-0.5 h-1.5 w-1.5 rounded-full bg-signal animate-pulseSoft" />
            </span>
            <span className="text-left">
              <span className="block font-mono text-[10px] uppercase tracking-[0.28em] text-slate-500">
                OpenFire
              </span>
              <span className="block text-[15px] font-semibold tracking-tight text-white">
                DocuPilot <span className="text-signal">AI</span>
              </span>
            </span>
          </button>

          <div className="flex items-center gap-2 lg:hidden">
            <button
              className={cx(
                "btn-ghost",
                active === "dashboard" && "bg-white/[0.06] text-white",
              )}
              onClick={() => onNavigate({ name: "dashboard" })}
            >
              <DashboardIcon className="h-4 w-4" />
              Desk
            </button>
            <button
              className={cx(
                "btn-ghost",
                active === "upload" && "bg-white/[0.06] text-white",
              )}
              onClick={() => onNavigate({ name: "upload" })}
            >
              <UploadIcon className="h-4 w-4" />
              Upload
            </button>
          </div>
        </div>

        <nav className="hidden px-3 lg:block">
          <div className="mb-2 px-3 font-mono text-[9px] uppercase tracking-[0.22em] text-slate-600">
            Workspace
          </div>
          {nav.map((item) => {
            const Icon = item.icon;
            const isActive = active === item.key;
            return (
              <button
                key={item.key}
                onClick={() => onNavigate({ name: item.key })}
                className={cx(
                  "focus-ring group relative mb-1 flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition",
                  isActive
                    ? "bg-white/[0.06] text-white"
                    : "text-slate-400 hover:bg-white/[0.035] hover:text-slate-200",
                )}
              >
                {isActive ? (
                  <span className="absolute left-0 top-2 h-[calc(100%-16px)] w-0.5 rounded-full bg-signal" />
                ) : null}
                <Icon
                  className={cx(
                    "h-4 w-4",
                    isActive ? "text-signal" : "text-slate-500 group-hover:text-slate-300",
                  )}
                />
                {item.label}
              </button>
            );
          })}

          <div className="mt-7 rounded-2xl border border-white/[0.07] bg-white/[0.025] p-4">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-slate-500">
                Runtime
              </span>
              <button
                onClick={onRefreshHealth}
                className="font-mono text-[9px] uppercase tracking-[0.16em] text-slate-500 hover:text-signal"
              >
                refresh
              </button>
            </div>
            <div className="mt-3 space-y-2.5 text-[11px]">
              <div className="flex items-center gap-2">
                <span
                  className={cx(
                    "h-1.5 w-1.5 rounded-full",
                    health?.model_configured ? "bg-signal" : "bg-amber-300",
                  )}
                />
                <span className="text-slate-400">Model</span>
                <span className="ml-auto truncate font-mono text-[10px] text-slate-300">
                  {modelLabel(health)}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className={cx(
                    "h-1.5 w-1.5 rounded-full",
                    health?.alan_workflow_configured ? "bg-cyan-300" : "bg-slate-600",
                  )}
                />
                <span className="text-slate-400">Alan workflow</span>
                <span className="ml-auto font-mono text-[10px] text-slate-300">
                  {health?.alan_workflow_configured ? "ready" : "off"}
                </span>
              </div>
            </div>
          </div>
        </nav>

        <div className="hidden px-6 pb-6 pt-10 lg:absolute lg:inset-x-0 lg:bottom-0 lg:block">
          <div className="rounded-xl border border-ember/20 bg-ember/[0.05] p-3">
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-ember">
              <LockIcon className="h-3.5 w-3.5" />
              Demo only
            </div>
            <p className="mt-1.5 text-[10px] leading-4 text-slate-500">
              No payment approval, scheduling, or execution. Synthetic documents
              only.
            </p>
          </div>
          <p className="mt-4 font-mono text-[9px] uppercase tracking-[0.16em] text-slate-700">
            OpenFire Hackathon · v{health?.version ?? "0.1.0"}
          </p>
        </div>
      </aside>

      <div className="relative min-w-0">
        <header className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.06] bg-ink-950/70 px-5 py-3.5 backdrop-blur-xl lg:px-10">
          <div className="flex items-center gap-3">
            <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-slate-600">
              Recon desk
            </span>
            <span className="h-3 w-px bg-white/10" />
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-slate-400">
              {route.name === "case" ? route.id : route.name}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden items-center gap-1.5 rounded-full border border-signal/25 bg-signal/[0.07] px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.14em] text-signal sm:inline-flex">
              <span className="h-1 w-1 rounded-full bg-signal" />
              {health?.model_configured ? "Live open model" : "Fixture fallback"}
            </span>
            <span className="hidden items-center gap-1.5 rounded-full border border-white/10 px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.14em] text-slate-400 sm:inline-flex">
              Alan {health?.alan_workflow_configured ? "MCP ready" : "chat model"}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-ember/25 bg-ember/[0.06] px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.14em] text-ember">
              <LockIcon className="h-3 w-3" />
              No payments
            </span>
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1500px] px-5 pb-16 pt-6 lg:px-10 lg:pt-8">
          {children}
        </main>
      </div>
    </div>
  );
}