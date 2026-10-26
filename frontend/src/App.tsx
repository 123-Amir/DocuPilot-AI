import { useCallback, useEffect, useState } from "react";
import { api } from "./lib/api";
import type { Health } from "./lib/types";
import Shell, { type Route } from "./components/Shell";
import DashboardPage from "./pages/DashboardPage";
import UploadPage from "./pages/UploadPage";
import CasePage from "./pages/CasePage";

function parseHash(): Route {
  const raw = window.location.hash.replace(/^#\/?/, "");
  if (raw.startsWith("upload")) return { name: "upload" };
  if (raw.startsWith("cases/")) {
    const id = decodeURIComponent(raw.slice("cases/".length));
    if (id) return { name: "case", id };
  }
  return { name: "dashboard" };
}

function hashFor(route: Route): string {
  if (route.name === "upload") return "#/upload";
  if (route.name === "case") return `#/cases/${encodeURIComponent(route.id)}`;
  return "#/dashboard";
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseHash());
  const [health, setHealth] = useState<Health | null>(null);

  const refreshHealth = useCallback(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    refreshHealth();
  }, [refreshHealth]);

  useEffect(() => {
    const onHashChange = () => setRoute(parseHash());
    window.addEventListener("hashchange", onHashChange);
    if (!window.location.hash) {
      window.history.replaceState(null, "", "#/dashboard");
    }
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const navigate = useCallback((next: Route) => {
    const nextHash = hashFor(next);
    if (window.location.hash === nextHash) {
      setRoute(next);
    } else {
      window.location.hash = nextHash;
    }
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  }, []);

  return (
    <Shell
      health={health}
      route={route}
      onNavigate={navigate}
      onRefreshHealth={refreshHealth}
    >
      {route.name === "dashboard" ? (
        <DashboardPage health={health} onNavigate={navigate} />
      ) : null}
      {route.name === "upload" ? (
        <UploadPage health={health} onNavigate={navigate} />
      ) : null}
      {route.name === "case" ? (
        <CasePage caseId={route.id} health={health} onNavigate={navigate} />
      ) : null}
    </Shell>
  );
}