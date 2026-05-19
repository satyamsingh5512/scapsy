import { AlertTriangle, CheckCircle2, CircleSlash } from "lucide-react";

import { useWebIntelStore } from "../../store/useWebIntelStore";
import { Badge } from "../ui/badge";

const statusMeta = {
  ok: { label: "Working", tone: "good" as const, Icon: CheckCircle2 },
  degraded: { label: "Degraded", tone: "warn" as const, Icon: AlertTriangle },
  down: { label: "Broken", tone: "bad" as const, Icon: CircleSlash }
};

export function ReadinessMatrix() {
  const readiness = useWebIntelStore((state) => state.readiness);

  return (
    <section className="rounded-md border border-border bg-white p-4 shadow-panel">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-black">Readiness Matrix</h2>
          <p className="text-sm text-muted">Live checks for working, degraded, and broken platform capabilities.</p>
        </div>
        <Badge tone={readiness?.status === "ok" ? "good" : readiness?.status === "down" ? "bad" : "warn"}>
          {readiness?.status ?? "unknown"}
        </Badge>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {(readiness?.checks ?? []).map((check) => {
          const meta = statusMeta[check.status] ?? statusMeta.degraded;
          const Icon = meta.Icon;
          return (
            <article key={check.name} className="min-h-[128px] rounded-md border border-border bg-stone-50 p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  <Icon size={17} className={check.status === "ok" ? "text-signal" : check.status === "down" ? "text-danger" : "text-warning"} />
                  <h3 className="truncate text-sm font-black">{check.name.replace(/_/g, " ")}</h3>
                </div>
                <Badge tone={meta.tone}>{meta.label}</Badge>
              </div>
              <p className="mt-2 text-sm text-foreground">{check.detail}</p>
              {check.remediation ? <p className="mt-2 text-xs font-semibold text-muted">{check.remediation}</p> : null}
            </article>
          );
        })}
        {!readiness ? <p className="text-sm text-muted">Waiting for readiness response.</p> : null}
      </div>
    </section>
  );
}
