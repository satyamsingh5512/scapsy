import { ServerCog } from "lucide-react";

import { useWebIntelStore } from "../store/useWebIntelStore";
import { Badge } from "./ui/badge";

export function SystemHealthStrip() {
  const health = useWebIntelStore((state) => state.health);
  const dependencies = health?.dependencies ? Object.entries(health.dependencies) : [];

  return (
    <section className="grid gap-3 rounded-md border border-border bg-white p-3 shadow-panel md:grid-cols-[180px_1fr]">
      <div className="flex items-center gap-2 text-sm font-bold">
        <ServerCog size={17} className={health?.status === "ok" ? "text-signal" : "text-warning"} />
        System Health
        <Badge tone={health?.status === "ok" ? "good" : "warn"}>{health?.status ?? "unknown"}</Badge>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {dependencies.length === 0 ? (
          <span className="text-sm text-muted">Waiting for API health response.</span>
        ) : (
          dependencies.map(([name, dependency]) => (
            <div key={name} className="flex min-w-0 items-center justify-between gap-2 rounded border border-border bg-stone-50 px-3 py-2">
              <span className="truncate text-sm font-semibold">{name}</span>
              <Badge tone={dependency.status === "ok" ? "good" : "bad"}>{dependency.status}</Badge>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
