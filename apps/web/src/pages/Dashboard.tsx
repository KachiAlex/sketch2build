import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Plus,
  Upload,
  Sparkles,
  FolderKanban,
  Clock,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
} from "lucide-react";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Skeleton } from "../components/ui/skeleton";

interface Project {
  id: string;
  name: string;
  jurisdiction: string;
  status: string;
  createdAt: string;
}

interface Job {
  id: string;
  status: string;
  inputType: string;
  createdAt: string;
  project?: { name: string };
}

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        const [projData, jobData] = await Promise.all([
          api.get<{ projects: Project[] }>("/projects"),
          api.get<{ jobs: Job[] }>("/jobs?limit=5").catch(() => ({ jobs: [] })),
        ]);
        setProjects(projData.projects);
        setJobs(jobData.jobs);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load data");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const stats = {
    totalProjects: projects.length,
    activeJobs: jobs.filter((j) => j.status === "pending" || j.status === "processing").length,
    completedJobs: jobs.filter((j) => j.status === "completed").length,
    failedJobs: jobs.filter((j) => j.status === "failed").length,
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-[1200px] space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-4 md:grid-cols-4">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
        <Skeleton className="h-64" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1200px] space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold text-ink">Dashboard</h1>
          <p className="font-mono-tech text-xs text-muted">
            SHEET D-100 · PROJECT OVERVIEW
          </p>
        </div>
        <Button asChild>
          <Link to="/projects">
            <Plus className="mr-2 h-4 w-4" />
            New Project
          </Link>
        </Button>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Stats row */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={<FolderKanban className="h-5 w-5 text-blueprint" />}
          label="Projects"
          value={stats.totalProjects}
        />
        <StatCard
          icon={<Clock className="h-5 w-5 text-amber-500" />}
          label="Active Jobs"
          value={stats.activeJobs}
        />
        <StatCard
          icon={<CheckCircle2 className="h-5 w-5 text-green-600" />}
          label="Completed"
          value={stats.completedJobs}
        />
        <StatCard
          icon={<AlertTriangle className="h-5 w-5 text-destructive" />}
          label="Failed"
          value={stats.failedJobs}
        />
      </div>

      {/* Quick actions */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Card className="border-[1.5px] border-vellum-line bg-vellum transition-colors hover:border-blueprint">
          <CardContent className="flex items-center gap-4 py-6">
            <div className="grid h-12 w-12 place-items-center rounded-md border-[1.5px] border-redline bg-white">
              <Upload className="h-6 w-6 text-redline" />
            </div>
            <div className="flex-1">
              <h3 className="font-display text-base font-semibold text-ink">
                Upload Sketch
              </h3>
              <p className="text-xs text-muted-foreground">
                Digitize a hand-drawn floor plan
              </p>
            </div>
            <Button variant="ghost" size="icon" asChild>
              <Link to="/sketch">
                <ArrowRight className="h-5 w-5" />
              </Link>
            </Button>
          </CardContent>
        </Card>
        <Card className="border-[1.5px] border-vellum-line bg-vellum transition-colors hover:border-blueprint">
          <CardContent className="flex items-center gap-4 py-6">
            <div className="grid h-12 w-12 place-items-center rounded-md border-[1.5px] border-blueprint bg-white">
              <Sparkles className="h-6 w-6 text-blueprint" />
            </div>
            <div className="flex-1">
              <h3 className="font-display text-base font-semibold text-ink">
                Prompt Studio
              </h3>
              <p className="text-xs text-muted-foreground">
                Generate designs from a text brief
              </p>
            </div>
            <Button variant="ghost" size="icon" asChild>
              <Link to="/prompt">
                <ArrowRight className="h-5 w-5" />
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Recent projects */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-lg font-semibold text-ink">
            Recent Projects
          </h2>
          {projects.length > 0 && (
            <Button variant="ghost" size="sm" asChild>
              <Link to="/projects">
                View all
                <ArrowRight className="ml-1 h-3 w-3" />
              </Link>
            </Button>
          )}
        </div>
        {projects.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center gap-3 py-12">
              <FolderKanban className="h-8 w-8 text-muted" />
              <p className="text-sm text-muted-foreground">
                No projects yet. Create one to get started.
              </p>
              <Button asChild>
                <Link to="/projects">
                  <Plus className="mr-2 h-4 w-4" />
                  Create project
                </Link>
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {projects.slice(0, 6).map((project) => (
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
                  <p className="font-mono-tech text-xs text-muted">
                    {project.jurisdiction}
                  </p>
                  <div className="mt-4 flex gap-2">
                    <Button variant="outline" size="sm" className="flex-1" asChild>
                      <Link to={`/sketch?projectId=${project.id}`}>Sketch</Link>
                    </Button>
                    <Button variant="outline" size="sm" className="flex-1" asChild>
                      <Link to={`/prompt?projectId=${project.id}`}>Prompt</Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Recent jobs */}
      {jobs.length > 0 && (
        <div className="space-y-4">
          <h2 className="font-display text-lg font-semibold text-ink">
            Recent Jobs
          </h2>
          <Card>
            <CardContent className="divide-y divide-vellum-line p-0">
              {jobs.map((job) => (
                <div
                  key={job.id}
                  className="flex items-center justify-between px-4 py-3"
                >
                  <div className="flex items-center gap-3">
                    {job.inputType === "sketch" ? (
                      <Upload className="h-4 w-4 text-muted" />
                    ) : (
                      <Sparkles className="h-4 w-4 text-muted" />
                    )}
                    <div>
                      <p className="text-sm font-medium text-ink">
                        {job.project?.name || "Untitled"}
                      </p>
                      <p className="font-mono-tech text-xs text-muted">
                        {job.id.slice(0, 8)} · {job.inputType}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge
                      variant={
                        job.status === "completed"
                          ? "success"
                          : job.status === "failed"
                          ? "destructive"
                          : "warning"
                      }
                      className="text-xs"
                    >
                      {job.status}
                    </Badge>
                    <Button variant="ghost" size="sm" asChild>
                      <Link to={`/results/${job.id}`}>
                        <ArrowRight className="h-4 w-4" />
                      </Link>
                    </Button>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
}) {
  return (
    <Card className="border-[1.5px] border-vellum-line">
      <CardContent className="flex items-center gap-3 py-4">
        <div className="grid h-10 w-10 place-items-center rounded-md bg-vellum">
          {icon}
        </div>
        <div>
          <p className="font-display text-2xl font-bold text-ink">{value}</p>
          <p className="font-mono-tech text-xs text-muted">{label}</p>
        </div>
      </CardContent>
    </Card>
  );
}
