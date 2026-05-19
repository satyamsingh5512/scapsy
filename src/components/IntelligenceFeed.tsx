import { ExternalLink, Layers } from "lucide-react";

import { useWebIntelStore } from "../store/useWebIntelStore";
import { Badge } from "./ui/badge";
import { Card, CardContent, CardHeader } from "./ui/card";

export function IntelligenceFeed() {
  const { feed } = useWebIntelStore();

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Layers size={18} className="text-accent" />
          <h2 className="text-lg font-bold">Intelligence Feed</h2>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {feed.length === 0 ? (
          <div className="rounded-md border border-dashed border-border p-5 text-sm text-muted">
            Extracted records will appear after workers publish structured data.
          </div>
        ) : (
          feed.map((record) => (
            <article key={record.id} className="rounded-md border border-border p-3">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <a className="inline-flex min-w-0 items-center gap-2 text-sm font-bold text-accent" href={record.url}>
                  <ExternalLink size={14} />
                  <span className="truncate">{record.url}</span>
                </a>
                <Badge tone={Number(record.confidence) >= 0.82 ? "good" : "warn"}>
                  {Math.round(Number(record.confidence) * 100)}%
                </Badge>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                {Object.entries(record.data).map(([key, value]) => (
                  <div key={key} className="rounded border border-border bg-stone-50 p-2">
                    <div className="text-xs font-bold uppercase tracking-wide text-muted">{key}</div>
                    <div className="mt-1 break-words text-sm">{String(value)}</div>
                  </div>
                ))}
              </div>
              <details className="mt-3 rounded border border-border bg-stone-950 p-3 text-xs text-stone-100">
                <summary className="cursor-pointer font-semibold text-stone-200">Raw JSON</summary>
                <pre className="mt-2 max-h-64 overflow-auto">{JSON.stringify(record, null, 2)}</pre>
              </details>
            </article>
          ))
        )}
      </CardContent>
    </Card>
  );
}
