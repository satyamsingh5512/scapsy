import { Bell, CheckCircle2, ShieldAlert } from "lucide-react";

import { useWebIntelStore } from "../store/useWebIntelStore";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader } from "./ui/card";

const severityTone = {
  info: "good",
  warning: "warn",
  critical: "bad"
} as const;

export function AlertsPanel() {
  const { alerts, acknowledgeAlert, loading } = useWebIntelStore();

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div className="flex items-center gap-2">
          <Bell size={18} className="text-accent" />
          <h2 className="text-lg font-bold">Alerts</h2>
        </div>
        <Badge tone={alerts.length === 0 ? "good" : "warn"}>{alerts.length} open</Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        {alerts.length === 0 ? (
          <div className="rounded-md border border-dashed border-border p-5 text-sm text-muted">
            No active alerts. Change detection and pipeline checks will surface here.
          </div>
        ) : (
          alerts.map((alert) => (
            <div key={alert.id} className="rounded-md border border-border bg-white p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                  {alert.severity === "critical" ? (
                    <ShieldAlert size={16} className="text-danger" />
                  ) : (
                    <CheckCircle2 size={16} className="text-warning" />
                  )}
                  <div>
                    <div className="text-sm font-bold">{alert.title}</div>
                    <div className="text-xs text-muted">{alert.detail ?? "Automated event"}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={severityTone[alert.severity]}>{alert.severity}</Badge>
                  {alert.status !== "acknowledged" ? (
                    <Button
                      variant="ghost"
                      className="h-8 px-2"
                      disabled={loading}
                      onClick={() => void acknowledgeAlert(alert.id)}
                    >
                      Ack
                    </Button>
                  ) : null}
                </div>
              </div>
              <div className="mt-2 text-xs text-muted">{new Date(alert.created_at).toLocaleString()}</div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
