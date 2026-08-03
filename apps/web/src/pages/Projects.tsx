import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select } from "../components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Skeleton } from "../components/ui/skeleton";
import { useToast } from "../components/ui/toast";
import { ChevronLeft, ChevronRight, FolderKanban } from "lucide-react";

interface Project {
  id: string;
  name: string;
  jurisdiction: string;
  status: string;
  createdAt: string;
}

const PAGE_SIZE = 6;

export default function Projects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ name: "", jurisdiction: "Nigeria", plotWidth: "", plotDepth: "", plotUnit: "m" as "m" | "ft" });
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [page, setPage] = useState(0);
  const { toast } = useToast();

  async function loadProjects() {
    setLoading(true);
    try {
      const data = await api.get<{ projects: Project[] }>("/projects");
      setProjects(data.projects);
    } catch {
      // ignore load errors
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadProjects();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
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
      toast({ title: "Project created", description: form.name, variant: "success" });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to create project";
      setError(msg);
      toast({ title: "Failed to create project", description: msg, variant: "error" });
    } finally {
      setIsSubmitting(false);
    }
  }

  const totalPages = Math.ceil(projects.length / PAGE_SIZE);
  const pagedProjects = projects.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

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
              <Select
                id="plotUnit"
                value={form.plotUnit}
                onChange={(e) => setForm({ ...form, plotUnit: e.target.value as "m" | "ft" })}
              >
                <option value="m">Metres</option>
                <option value="ft">Feet</option>
              </Select>
            </div>
            {error && <p className="text-sm text-destructive sm:col-span-2">{error}</p>}
            <div className="sm:col-span-2">
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? "Creating…" : "Create project"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <div className="space-y-4">
        <h2 className="font-display text-xl font-semibold text-ink">Your projects</h2>
        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
          </div>
        ) : projects.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center gap-3 py-12">
              <FolderKanban className="h-8 w-8 text-muted" />
              <p className="text-sm text-muted-foreground">No projects yet. Create one above to get started.</p>
            </CardContent>
          </Card>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              {pagedProjects.map((project) => (
                <Card key={project.id} className="border-[1.5px] border-vellum-line">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <CardTitle className="text-base">{project.name}</CardTitle>
                      <Badge
                        variant={project.status === "active" ? "success" : "outline"}
                        className="text-xs"
                      >
                        {project.status}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="font-mono-tech text-xs text-muted">{project.jurisdiction}</p>
                    <div className="mt-4 flex gap-2">
                      <Button variant="outline" size="sm" className="flex-1" asChild>
                        <a href={`/sketch?projectId=${project.id}`}>Upload sketch</a>
                      </Button>
                      <Button variant="outline" size="sm" className="flex-1" asChild>
                        <a href={`/prompt?projectId=${project.id}`}>Prompt design</a>
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-4 pt-2">
                <Button
                  variant="outline"
                  size="icon"
                  disabled={page === 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="font-mono-tech text-xs text-muted">
                  Page {page + 1} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="icon"
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
