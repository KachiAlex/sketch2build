import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";

interface Candidate {
  rank: number;
  score: number;
  rationale: Record<string, number>;
  rooms: Array<{
    type: string;
    label: string;
    area: number;
  }>;
}

export default function Prompt() {
  const [searchParams] = useSearchParams();
  const projectId = searchParams.get("projectId") || "";

  const [form, setForm] = useState({
    plotWidth: "",
    plotDepth: "",
    unit: "m" as "m" | "ft" | "cm" | "mm",
    orientation: "",
    roomCount: "",
    prompt: "",
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<{ job?: { id: string; status: string }; candidates?: Candidate[]; validation?: { unit_ambiguity_flags?: string[] } } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const data = await api.post("/jobs", {
        projectId,
        sourceType: "prompt",
        payload: {
          site: {
            width: parseFloat(form.plotWidth),
            depth: parseFloat(form.plotDepth),
            unit: form.unit,
          },
          orientation: form.orientation ? parseFloat(form.orientation) : undefined,
          room_count: form.roomCount ? parseInt(form.roomCount, 10) : undefined,
          prompt: form.prompt,
        },
      });
      setResult({ job: data as { id: string; status: string } });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Prompt Studio</h1>
      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle>Describe your design brief</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="plotWidth">Plot width</Label>
              <Input id="plotWidth" type="number" value={form.plotWidth} onChange={(e) => setForm({ ...form, plotWidth: e.target.value })} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="plotDepth">Plot depth</Label>
              <Input id="plotDepth" type="number" value={form.plotDepth} onChange={(e) => setForm({ ...form, plotDepth: e.target.value })} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="unit">Unit</Label>
              <select
                id="unit"
                value={form.unit}
                onChange={(e) => setForm({ ...form, unit: e.target.value as "m" | "ft" | "cm" | "mm" })}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="m">Metres</option>
                <option value="ft">Feet</option>
                <option value="cm">Centimetres</option>
                <option value="mm">Millimetres</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="orientation">Orientation (degrees, optional)</Label>
              <Input id="orientation" type="number" value={form.orientation} onChange={(e) => setForm({ ...form, orientation: e.target.value })} />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="roomCount">Room count</Label>
              <Input id="roomCount" type="number" value={form.roomCount} onChange={(e) => setForm({ ...form, roomCount: e.target.value })} />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="prompt">Free-text elaboration</Label>
              <textarea
                id="prompt"
                value={form.prompt}
                onChange={(e) => setForm({ ...form, prompt: e.target.value })}
                rows={4}
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                placeholder="e.g. I need a 3-bedroom bungalow with the living room facing north..."
              />
            </div>
            <div className="sm:col-span-2">
              <Button type="submit" disabled={isSubmitting || !projectId}>
                {isSubmitting ? "Generating…" : "Generate layouts"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {result?.job && (
        <Card>
          <CardHeader>
            <CardTitle>Generation job</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm">Job ID: {result.job.id}</p>
            <p className="text-sm">Status: {result.job.status}</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
