import { Activity, Ban, Database, RotateCw } from "lucide-react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";

import { useWebIntelStore } from "../store/useWebIntelStore";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader } from "./ui/card";

const demoTrend = [
  { t: "00", pages: 18 },
  { t: "04", pages: 42 },
  { t: "08", pages: 37 },
  { t: "12", pages: 74 },
  { t: "16", pages: 68 },
  { t: "20", pages: 96 }
];

export function JobManager() {
  const { jobs, feed, refreshAll, cancelJob, loading } = useWebIntelStore();
  const activeJobs = jobs.filter((job) => job.status === "running" || job.status === "pending");
  const trend = jobs.slice(0, 8).reverse().map((job) => ({
    t: new Date(job.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    pages: job.pages_processed
  }));
  const chartData = trend.length > 0 ? trend : demoTrend;

  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold">Active Scrapers</h2>
          <p className="text-sm text-muted">{activeJobs.length} running pipeline{activeJobs.length === 1 ? "" : "s"}</p>
        </div>
        <Button variant="secondary" onClick={refreshAll} disabled={loading} title="Refresh operations data">
          <RotateCw size={16} />
          Refresh
        </Button>
      </CardHeader>
      <CardContent className="grid gap-4 lg:grid-cols-[1fr_220px]">
        <div className="space-y-3">
          {jobs.length === 0 ? (
            <div className="rounded-md border border-dashed border-border p-5 text-sm text-muted">
              No jobs yet. Start a seed-URL extraction from the command panel.
            </div>
          ) : (
            jobs.map((job) => (
              <div key={job.id} className="grid gap-3 rounded-md border border-border bg-white p-3 sm:grid-cols-[1fr_auto]">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <Activity size={16} className="text-accent" />
                    <h3 className="truncate text-sm font-bold">{job.name}</h3>
                  </div>
                  <p className="mt-1 truncate text-xs text-muted">{job.seed_urls.join(", ")}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={job.status === "failed" ? "bad" : job.status === "completed" ? "good" : "warn"}>
                    {job.status}
                  </Badge>
                  <span className="text-xs text-muted">{job.pages_processed}/{job.pages_discovered}</span>
                  {(job.status === "running" || job.status === "pending") ? (
                    <Button variant="ghost" className="h-8 px-2" onClick={() => void cancelJob(job.id)} title="Cancel job">
                      <Ban size={14} />
                    </Button>
                  ) : null}
                </div>
              </div>
            ))
          )}
        </div>
        <div className="rounded-md border border-border bg-stone-50 p-3">
          <div className="mb-2 flex items-center gap-2 text-sm font-bold">
            <Database size={16} className="text-signal" />
            Page Flow
          </div>
          <div className="h-36">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="flow" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="5%" stopColor="#208079" stopOpacity={0.55} />
                    <stop offset="95%" stopColor="#208079" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="t" tickLine={false} axisLine={false} fontSize={11} />
                <Tooltip />
                <Area type="monotone" dataKey="pages" stroke="#208079" fill="url(#flow)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="lg:col-span-2 rounded-md border border-border bg-stone-50 p-3 text-sm text-muted">
          {jobs.length} jobs tracked, {activeJobs.length} active, {feed.length} extracted records loaded.
        </div>
      </CardContent>
    </Card>
  );
}
