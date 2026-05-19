import { create } from "zustand";

import { AlertRecord, api, AiSchemaResponse, ExtractedRecord, Job, SystemHealth, SystemReadiness } from "../lib/api";

interface WebIntelState {
  jobs: Job[];
  feed: ExtractedRecord[];
  alerts: AlertRecord[];
  latestSchema: AiSchemaResponse | null;
  health: SystemHealth | null;
  readiness: SystemReadiness | null;
  loading: boolean;
  error: string | null;
  refreshAll: () => Promise<void>;
  refreshFeed: () => Promise<void>;
  refreshAlerts: () => Promise<void>;
  refreshJobs: () => Promise<void>;
  refreshHealth: () => Promise<void>;
  generateSchema: (instruction: string) => Promise<AiSchemaResponse>;
  createJobFromInstruction: (instruction: string, seedUrls: string[]) => Promise<void>;
  cancelJob: (jobId: string) => Promise<void>;
  acknowledgeAlert: (alertId: string) => Promise<void>;
}

export const useWebIntelStore = create<WebIntelState>((set, get) => ({
  jobs: [],
  feed: [],
  alerts: [],
  latestSchema: null,
  health: null,
  readiness: null,
  loading: false,
  error: null,
  refreshAll: async () => {
    await Promise.all([get().refreshJobs(), get().refreshFeed(), get().refreshHealth(), get().refreshAlerts()]);
  },
  refreshFeed: async () => {
    set({ loading: true, error: null });
    try {
      const data = await api.listData();
      set({ feed: data.items, loading: false });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : "Unable to load feed", loading: false });
    }
  },
  refreshAlerts: async () => {
    try {
      const data = await api.listAlerts();
      set({ alerts: data.items });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : "Unable to load alerts" });
    }
  },
  refreshJobs: async () => {
    set({ error: null });
    try {
      const data = await api.listJobs();
      set({ jobs: data.items });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : "Unable to load jobs" });
    }
  },
  refreshHealth: async () => {
    try {
      const health = await api.health();
      const readiness = await api.readiness();
      set({ health, readiness });
    } catch (error) {
      set({ health: null, readiness: null, error: error instanceof Error ? error.message : "Unable to load system health" });
    }
  },
  generateSchema: async (instruction: string) => {
    set({ loading: true, error: null });
    try {
      const schema = await api.generateSchema(instruction);
      set({ latestSchema: schema, loading: false });
      return schema;
    } catch (error) {
      set({ error: error instanceof Error ? error.message : "Unable to generate schema", loading: false });
      throw error;
    }
  },
  createJobFromInstruction: async (instruction: string, seedUrls: string[]) => {
    set({ loading: true, error: null });
    try {
      const schema = get().latestSchema ?? (await api.generateSchema(instruction));
      const job = await api.createJob({
        name: instruction.slice(0, 80),
        seed_urls: seedUrls,
        instruction,
        extraction_schema: schema.extraction_schema,
        crawl_config: { requested_from: "dashboard" },
        render_javascript: true
      });
      set((state) => ({ jobs: [job, ...state.jobs], latestSchema: schema, loading: false }));
      await get().refreshAll();
    } catch (error) {
      set({ error: error instanceof Error ? error.message : "Unable to create job", loading: false });
    }
  },
  cancelJob: async (jobId: string) => {
    set({ loading: true, error: null });
    try {
      await api.cancelJob(jobId);
      await get().refreshJobs();
      set({ loading: false });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : "Unable to cancel job", loading: false });
    }
  },
  acknowledgeAlert: async (alertId: string) => {
    set({ loading: true, error: null });
    try {
      await api.ackAlert(alertId);
      await get().refreshAlerts();
      set({ loading: false });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : "Unable to acknowledge alert", loading: false });
    }
  }
}));
