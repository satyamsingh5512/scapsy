import { useEffect } from "react";

import { AiInstructionBuilder } from "./components/AiInstructionBuilder";
import { AlertsPanel } from "./components/AlertsPanel";
import { IntelligenceFeed } from "./components/IntelligenceFeed";
import { JobManager } from "./components/JobManager";
import { SystemHealthStrip } from "./components/SystemHealthStrip";
import { ReadinessMatrix } from "./components/diagnostics/ReadinessMatrix";
import { useWebIntelStore } from "./store/useWebIntelStore";

export default function App() {
  const refreshAll = useWebIntelStore((state) => state.refreshAll);

  useEffect(() => {
    void refreshAll();
    const timer = window.setInterval(() => {
      void refreshAll();
    }, 10_000);
    return () => window.clearInterval(timer);
  }, [refreshAll]);

  return (
    <main className="min-h-screen">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
        <header className="grid gap-3 border-b border-border pb-5 lg:grid-cols-[1fr_auto] lg:items-end">
          <div>
            <div className="text-sm font-bold uppercase tracking-wide text-accent">WebIntel AI</div>
            <h1 className="mt-1 text-3xl font-black sm:text-4xl">Distributed Web Intelligence Console</h1>
          </div>
          <div className="grid grid-cols-3 overflow-hidden rounded-md border border-border bg-white text-center text-sm">
            <div className="p-3">
              <div className="font-black">5</div>
              <div className="text-xs text-muted">Tiers</div>
            </div>
            <div className="border-x border-border p-3">
              <div className="font-black">Kafka</div>
              <div className="text-xs text-muted">Stream</div>
            </div>
            <div className="p-3">
              <div className="font-black">AI</div>
              <div className="text-xs text-muted">Fallback</div>
            </div>
          </div>
        </header>
        <SystemHealthStrip />
        <ReadinessMatrix />
        <section className="grid gap-5 xl:grid-cols-[420px_1fr]">
          <AiInstructionBuilder />
          <JobManager />
        </section>
        <AlertsPanel />
        <IntelligenceFeed />
      </div>
    </main>
  );
}
