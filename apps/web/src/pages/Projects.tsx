import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";

interface Project {
  id: string;
  name: string;
  jurisdiction: string;
  status: string;
  createdAt: string;
}

export default function Projects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [form, setForm] = useState({ name: "", jurisdiction: "Nigeria", plotWidth: "", plotDepth: "", plotUnit: "m" as "m" | "ft" });
  const [error, setError] = useState<string | null>(null);

  async function loadProjects() {
    const data = await api.get<{ projects: Project[] }>("/projects");
    setProjects(data.projects);
  }

  useEffect(() => {
    loadProjects();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/projects", {
        name: form.name,
        jurisdiction: form.jurisdiction,
        plotWidth: form.plotWidth ? parseFloat(form.plotWidth) : undefined,
        plotDepth: form.plotDepth ? parseFloat(form.plotDepth) : undefined,
        plotUnit: form.plotUnit,
      });
      setForm({ name: "", jurisdiction: "Nigeria", plotWidth: "", plotDepth: "", plotUnit: "m" });
      await loadProjects();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <div>
        <h1 className="font-display text-2xl font-bold text-ink">Projects</h1>
        <p className="font-mono-tech text-xs text-muted">
          SHEET PRJ-100 · PROJECT MANAGEMENT
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>New project</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="name">Project name</Label>
              <Input id="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="jurisdiction">Jurisdiction</Label>
              <Input id="jurisdiction" value={form.jurisdiction} onChange={(e) => setForm({ ...form, jurisdiction: e.target.value })} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="plotWidth">Plot width</Label>
              <Input id="plotWidth" type="number" value={form.plotWidth} onChange={(e) => setForm({ ...form, plotWidth: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="plotDepth">Plot depth</Label>
              <Input id="plotDepth" type="number" value={form.plotDepth} onChange={(e) => setForm({ ...form, plotDepth: e.target.value })} />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="plotUnit">Unit</Label>
              <select
                id="plotUnit"
                value={form.plotUnit}
                onChange={(e) => setForm({ ...form, plotUnit: e.target.value as "m" | "ft" })}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="m">Metres</option>
                <option value="ft">Feet</option>
              </select>
            </div>
            {error && <p className="text-sm text-destructive sm:col-span-2">{error}</p>}
            <div className="sm:col-span-2">
              <Button type="submit">Create project</Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Your projects</h2>
        {projects.length === 0 ? (
          <p className="text-muted-foreground">No projects yet.</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {projects.map((project) => (
              <Card key={project.id}>
                <CardHeader>
                  <CardTitle>{project.name}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">{project.jurisdiction}</p>
                  <p className="text-sm text-muted-foreground">Status: {project.status}</p>
                  <div className="mt-4 flex gap-2">
                    <Button variant="outline" className="flex-1" asChild>
                      <a href={`/sketch?projectId=${project.id}`}>Upload sketch</a>
                    </Button>
                    <Button variant="outline" className="flex-1" asChild>
                      <a href={`/prompt?projectId=${project.id}`}>Prompt design</a>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
