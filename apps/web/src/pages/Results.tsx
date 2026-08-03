import { useEffect, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  Clock,
  Download,
  Eye,
  AlertTriangle,
  Box,
  FileText,
  Layers,
} from "lucide-react";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Progress } from "../components/ui/progress";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { Skeleton } from "../components/ui/skeleton";

interface Room {
  id?: string;
  type: string;
  label?: string;
  area: number;
  boundary?: number[][];
  bbox?: { x: number; y: number; width: number; depth: number };
}

interface ComplianceViolation {
  ruleId: string;
  message: string;
  severity: string;
}

interface Alternative {
  index: number;
  floor_plan: {
    rooms: Room[];
    plot?: { width: number; depth: number };
  };
  compliance: {
    status: string;
    score: number;
    violations: ComplianceViolation[];
  };
  three_d_model?: {
    summary: string;
    format: string;
  };
  preview_3d?: string;
  score: number;
  explainability?: {
    design_rationale: Array<{ room: string; rationale: string }>;
  };
}

interface JobResult {
  job: {
    id: string;
    status: string;
    inputType: string;
    style: string;
    complianceStandard: string;
    createdAt: string;
  };
  alternatives: Alternative[];
}

export default function Results() {
  const { jobId } = useParams<{ jobId: string }>();
  const [result, setResult] = useState<JobResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAlt, setSelectedAlt] = useState(0);

  const pollJob = useCallback(async () => {
    if (!jobId) return;
    try {
      const data = await api.get<JobResult>(`/jobs/${jobId}`);
      setResult(data);
      if (data.job.status === "pending" || data.job.status === "processing") {
        setTimeout(pollJob, 3000);
      }
      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load job");
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    pollJob();
  }, [pollJob]);

  const isProcessing =
    result?.job.status === "pending" || result?.job.status === "processing";

  function handleExport(altIndex: number, format: string) {
    if (!jobId) return;
    api
      .download(
        `/exports/${jobId}/${format}?alt=${altIndex}`,
        `design-alt-${altIndex + 1}.${format}`
      )
      .catch(() => {});
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-full" />
        <div className="grid gap-4 md:grid-cols-3">
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12">
            <XCircle className="h-10 w-10 text-destructive" />
            <p className="text-sm text-destructive">{error}</p>
            <Button variant="outline" asChild>
              <Link to="/dashboard">Back to dashboard</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!result) return null;

  const statusConfig: Record<string, { icon: typeof Clock; color: string; label: string }> = {
    pending: { icon: Clock, color: "text-amber-600", label: "Queued" },
    processing: { icon: Clock, color: "text-blueprint", label: "Generating" },
    completed: { icon: CheckCircle2, color: "text-green-600", label: "Complete" },
    failed: { icon: XCircle, color: "text-destructive", label: "Failed" },
  };

  const StatusIcon = statusConfig[result.job.status]?.icon || Clock;
  const statusColor = statusConfig[result.job.status]?.color || "text-muted";
  const statusLabel = statusConfig[result.job.status]?.label || result.job.status;

  return (
    <div className="mx-auto max-w-[1200px] space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link to="/dashboard">
              <ArrowLeft className="h-5 w-5" />
            </Link>
          </Button>
          <div>
            <h1 className="font-display text-2xl font-bold text-ink">
              Design Results
            </h1>
            <p className="font-mono-tech text-xs text-muted">
              JOB — {jobId} · {result.job.inputType.toUpperCase()}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <StatusIcon className={`h-5 w-5 ${statusColor}`} />
          <Badge
            variant={
              result.job.status === "completed"
                ? "success"
                : result.job.status === "failed"
                ? "destructive"
                : "warning"
            }
          >
            {statusLabel}
          </Badge>
        </div>
      </div>

      {/* Processing state */}
      {isProcessing && (
        <Card>
          <CardContent className="space-y-4 py-8">
            <div className="flex items-center gap-3">
              <Clock className="h-5 w-5 animate-pulse text-blueprint" />
              <p className="text-sm font-medium text-ink">
                AI engine is generating your design…
              </p>
            </div>
            <Progress value={45} />
            <p className="font-mono-tech text-xs text-muted">
              This typically takes 30-60 seconds. Page will auto-refresh.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {result.job.status === "completed" && result.alternatives.length > 0 && (
        <>
          {/* Alternative selector tabs */}
          <Tabs
            value={String(selectedAlt)}
            onValueChange={(v) => setSelectedAlt(parseInt(v, 10))}
          >
            <div className="flex items-center justify-between">
              <TabsList>
                {result.alternatives.map((alt, i) => (
                  <TabsTrigger key={i} value={String(i)}>
                    Option {i + 1}
                    <span className="ml-2 text-xs text-muted">
                      {alt.score.toFixed(1)}
                    </span>
                  </TabsTrigger>
                ))}
              </TabsList>
            </div>

            {result.alternatives.map((alt, i) => (
              <TabsContent key={i} value={String(i)}>
                <AlternativeView
                  alt={alt}
                  onExport={(fmt) => handleExport(i, fmt)}
                />
              </TabsContent>
            ))}
          </Tabs>
        </>
      )}

      {result.job.status === "completed" && result.alternatives.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <AlertTriangle className="mx-auto mb-3 h-8 w-8 text-amber-500" />
            <p className="text-sm text-muted-foreground">
              No alternatives were generated. Try adjusting your parameters.
            </p>
          </CardContent>
        </Card>
      )}

      {result.job.status === "failed" && (
        <Card>
          <CardContent className="py-12 text-center">
            <XCircle className="mx-auto mb-3 h-8 w-8 text-destructive" />
            <p className="text-sm text-destructive">
              Generation failed. Please try again.
            </p>
            <Button variant="outline" className="mt-4" asChild>
              <Link to="/prompt">New generation</Link>
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function AlternativeView({
  alt,
  onExport,
}: {
  alt: Alternative;
  onExport: (format: string) => void;
}) {
  const rooms = alt.floor_plan?.rooms || [];
  const violations = alt.compliance?.violations || [];
  const plot = alt.floor_plan?.plot;

  // Compute SVG bounds
  const allPoints = rooms.flatMap((r) => r.boundary || []);
  const bounds = allPoints.length > 0 ? {
    minX: Math.min(...allPoints.map((p) => p[0])),
    minY: Math.min(...allPoints.map((p) => p[1])),
    maxX: Math.max(...allPoints.map((p) => p[0])),
    maxY: Math.max(...allPoints.map((p) => p[1])),
  } : { minX: 0, minY: 0, maxX: 100, maxY: 100 };

  const pad = Math.max(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY) * 0.1;
  const viewBox = `${bounds.minX - pad} ${bounds.minY - pad} ${bounds.maxX - bounds.minX + pad * 2} ${bounds.maxY - bounds.minY + pad * 2}`;

  function roomCentroid(points: number[][]): [number, number] {
    const n = points.length;
    if (n === 0) return [0, 0];
    let cx = 0, cy = 0;
    for (const [x, y] of points) { cx += x; cy += y; }
    return [cx / n, cy / n];
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      {/* Floor plan visualization */}
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">Floor Plan</CardTitle>
              <div className="flex items-center gap-2">
                <Badge variant={alt.compliance?.status === "pass" ? "success" : "warning"}>
                  {alt.compliance?.status === "pass" ? "Compliant" : "Has Issues"}
                </Badge>
                <Badge variant="blueprint">
                  Score: {alt.score.toFixed(1)}
                </Badge>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="relative aspect-[4/3] w-full overflow-hidden rounded-md border border-vellum-line bg-vellum">
              <span className="tick tick-tl" />
              <span className="tick tick-tr" />
              <span className="tick tick-bl" />
              <span className="tick tick-br" />
              <svg
                viewBox={viewBox}
                className="h-full w-full"
                preserveAspectRatio="xMidYMid meet"
              >
                {/* Plot boundary */}
                {plot && (
                  <rect
                    x={0}
                    y={0}
                    width={plot.width}
                    height={plot.depth}
                    fill="none"
                    stroke="hsl(var(--vellum-line))"
                    strokeWidth={0.3}
                    strokeDasharray="2 2"
                  />
                )}
                {/* Rooms */}
                {rooms.map((room, i) => {
                  const pts = room.boundary;
                  if (!pts || pts.length < 3) return null;
                  const colors = [
                    "#E7EEF8", "#F0E7F8", "#F8F0E7", "#E7F8F0",
                    "#F8E7EC", "#E7ECF8", "#F0F8E7", "#F8E7F0",
                  ];
                  return (
                    <g key={i}>
                      <polygon
                        points={pts.map((p) => `${p[0]},${p[1]}`).join(" ")}
                        fill={colors[i % colors.length]}
                        stroke="hsl(var(--ink))"
                        strokeWidth={0.4}
                      />
                      <text
                        x={roomCentroid(pts)[0]}
                        y={roomCentroid(pts)[1]}
                        textAnchor="middle"
                        fontSize={Math.max(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY) * 0.025}
                        fill="hsl(var(--ink))"
                        className="select-none font-display"
                      >
                        {room.label || room.type}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>
            {plot && (
              <p className="mt-2 font-mono-tech text-xs text-muted">
                PLOT — {plot.width}m × {plot.depth}m · {rooms.length} rooms ·{" "}
                {rooms.reduce((sum, r) => sum + r.area, 0).toFixed(1)}m² total
              </p>
            )}
          </CardContent>
        </Card>

        {/* 3D preview if available */}
        {alt.preview_3d && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Box className="h-5 w-5 text-blueprint" />
                3D Preview
              </CardTitle>
            </CardHeader>
            <CardContent>
              <img
                src={alt.preview_3d}
                alt="3D preview"
                className="w-full rounded-md border border-vellum-line"
              />
              {alt.three_d_model?.summary && (
                <p className="mt-2 font-mono-tech text-xs text-muted">
                  {alt.three_d_model.summary}
                </p>
              )}
            </CardContent>
          </Card>
        )}
      </div>

      {/* Sidebar: rooms, compliance, exports, explainability */}
      <div className="space-y-4">
        {/* Room list */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Layers className="h-4 w-4 text-blueprint" />
              Rooms ({rooms.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {rooms.map((room, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between border-b border-vellum-line pb-2 last:border-0"
                >
                  <div>
                    <p className="text-sm font-medium text-ink">
                      {room.label || room.type}
                    </p>
                    <p className="font-mono-tech text-xs text-muted">
                      {room.area.toFixed(1)} m²
                    </p>
                  </div>
                  <Badge variant="outline" className="text-xs">
                    {room.type}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Compliance */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              Compliance
            </CardTitle>
          </CardHeader>
          <CardContent>
            {violations.length === 0 ? (
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-green-600" />
                <p className="text-sm text-green-700">
                  All checks passed
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {violations.map((v, i) => (
                  <div
                    key={i}
                    className={`rounded-md border p-2 text-xs ${
                      v.severity === "error"
                        ? "border-destructive/30 bg-destructive/5 text-destructive"
                        : "border-amber-300 bg-amber-50 text-amber-800"
                    }`}
                  >
                    <p className="font-medium">{v.ruleId}</p>
                    <p className="mt-0.5">{v.message}</p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Explainability */}
        {alt.explainability?.design_rationale &&
          alt.explainability.design_rationale.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <FileText className="h-4 w-4 text-blueprint" />
                  Design Rationale
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {alt.explainability.design_rationale.map((r, i) => (
                    <div key={i} className="border-b border-vellum-line pb-2 last:border-0">
                      <p className="text-xs font-semibold text-ink">{r.room}</p>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {r.rationale}
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

        {/* Exports */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Download className="h-4 w-4 text-blueprint" />
              Export
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-2">
              <Button variant="outline" size="sm" onClick={() => onExport("dxf")}>
                DXF
              </Button>
              <Button variant="outline" size="sm" onClick={() => onExport("ifc")}>
                IFC
              </Button>
              <Button variant="outline" size="sm" onClick={() => onExport("glb")}>
                GLB (3D)
              </Button>
              <Button variant="outline" size="sm" onClick={() => onExport("png")}>
                PNG
              </Button>
            </div>
            <Button
              variant="default"
              size="sm"
              className="mt-3 w-full"
              asChild
            >
              <Link to={`/review?candidateId=${alt.index}`}>
                <Eye className="mr-2 h-4 w-4" />
                Review & Edit
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
