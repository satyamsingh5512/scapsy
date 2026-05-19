import { BrainCircuit, Play, Wand2 } from "lucide-react";
import { FormEvent, useState } from "react";

import { useWebIntelStore } from "../store/useWebIntelStore";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader } from "./ui/card";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";

export function AiInstructionBuilder() {
  const [instruction, setInstruction] = useState("Extract company name, price, contact email, and launch date.");
  const [urls, setUrls] = useState("https://example.com");
  const { latestSchema, loading, error, generateSchema, createJobFromInstruction } = useWebIntelStore();

  const seedUrls = urls
    .split(/\r?\n|,/)
    .map((url) => url.trim())
    .filter(Boolean);

  async function handleSchema(event: FormEvent) {
    event.preventDefault();
    await generateSchema(instruction);
  }

  async function handleStart() {
    await createJobFromInstruction(instruction, seedUrls);
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <BrainCircuit size={18} className="text-accent" />
          <h2 className="text-lg font-bold">AI Instruction Builder</h2>
        </div>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={handleSchema}>
          <div className="space-y-2">
            <label className="text-xs font-bold uppercase text-muted">Instruction</label>
            <Textarea value={instruction} onChange={(event) => setInstruction(event.target.value)} />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-bold uppercase text-muted">Seed URLs</label>
            <Input value={urls} onChange={(event) => setUrls(event.target.value)} />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={loading}>
              <Wand2 size={16} />
              Build Schema
            </Button>
            <Button type="button" variant="secondary" disabled={loading || seedUrls.length === 0} onClick={handleStart}>
              <Play size={16} />
              Start Job
            </Button>
          </div>
        </form>
        {error ? <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</div> : null}
        {latestSchema ? (
          <div className="mt-4 space-y-2">
            <div className="text-xs font-bold uppercase text-muted">Schema Preview ({latestSchema.provider})</div>
            <pre className="max-h-80 overflow-auto rounded-md border border-border bg-stone-950 p-3 text-xs text-stone-100">
              {JSON.stringify(latestSchema.extraction_schema, null, 2)}
            </pre>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
