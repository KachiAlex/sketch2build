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
  floor?: number;
  boundary?: number[][];
  bbox?: { x: number; y: number; width: number; depth: number };
}

interface ComplianceViolation {
  ruleId: string;
  message: string;
  severity: string;
}

interface Opening {
  x: number;
  y: number;
  orientation: "h" | "v";
  floor?: number;
}

interface Alternative {
  index: number;
  candidateId: string;
  floor_plan: {
    rooms: Room[];
    plot?: { width: number; depth: number };
    floors?: number;
    doors?: Opening[];
    windows?: Opening[];
    unit?: string;
    repairLog?: string[];
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
    rawStatus?: string;
    inputType: string;
    errorMessage?: string | null;
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
  const [pollElapsed, setPollElapsed] = useState(0);
  const [busyAction, setBusyAction] = useState(false);

  const pollJob = useCallback(async () => {
    if (!jobId) return;
    try {
      const data = await api.get<JobResult>(`/jobs/${jobId}`);
      setResult(data);
      if (data.job.status === "pending" || data.job.status === "processing") {
        setPollElapsed((e) => e + 3);
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

  function handleExport(candidateId: string, format: string) {
    const ext = format === "3d-massing" ? "glb" : format;
    api
      .download(`/exports/${candidateId}/${format}`, `design-${candidateId}.${ext}`)
      .catch(() => {});
  }

  async function handleRetry() {
    if (!jobId || busyAction) return;
    setBusyAction(true);
    try {
      await api.post(`/jobs/${jobId}/retry`, {});
      setPollElapsed(0);
      setResult((r) => r && { ...r, job: { ...r.job, status: "pending" } });
      setTimeout(pollJob, 1000);
    } catch {
      // surfaced on next poll
    } finally {
      setBusyAction(false);
    }
  }

  async function handleCancel() {
    if (!jobId || busyAction) return;
    setBusyAction(true);
    try {
      await api.post(`/jobs/${jobId}/cancel`, {});
      pollJob();
    } finally {
      setBusyAction(false);
    }
  }

  async function handleDelete() {
    if (!jobId || !window.confirm("Delete this job and its candidates?")) return;
    try {
      await api.delete(`/jobs/${jobId}`);
      window.location.href = "/dashboard";
    } catch {
      // stay on page
    }
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
            {pollElapsed > 90 && (
              <div className="flex items-center justify-between rounded-md border border-amber-300 bg-amber-50 px-3 py-2">
                <p className="text-xs text-amber-800">
                  Taking longer than usual — the queue may be backed up.
                </p>
                <Button variant="outline" size="sm" onClick={handleCancel} disabled={busyAction}>
                  Cancel job
                </Button>
              </div>
            )}
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
                  onExport={(fmt) => handleExport(alt.candidateId, fmt)}
                  onRevalidate={async () => {
                    await api.post(`/compliance/validate`, { candidateId: alt.candidateId });
                    pollJob();
                  }}
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
              {result.job.errorMessage || "Generation failed. Please try again."}
            </p>
            <div className="mt-4 flex items-center justify-center gap-2">
              <Button variant="default" size="sm" onClick={handleRetry} disabled={busyAction}>
                {busyAction ? "Retrying…" : "Retry generation"}
              </Button>
              <Button variant="outline" size="sm" asChild>
                <Link to="/prompt">New generation</Link>
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="text-destructive hover:text-destructive"
                onClick={handleDelete}
              >
                Delete job
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function AlternativeView({
  alt,
  onExport,
  onRevalidate,
}: {
  alt: Alternative;
  onExport: (format: string) => void;
  onRevalidate: () => Promise<void>;
}) {
  const [revalidating, setRevalidating] = useState(false);
  const allRooms = alt.floor_plan?.rooms || [];
  const floorNums = [...new Set(allRooms.map((r) => r.floor ?? 1))].sort((a, b) => a - b);
  const [activeFloor, setActiveFloor] = useState(floorNums[0] ?? 1);
  const rooms = allRooms.filter((r) => (r.floor ?? 1) === activeFloor);
  const violations = alt.compliance?.violations || [];
  const plot = alt.floor_plan?.plot;
  const doors = (alt.floor_plan?.doors || []).filter((d) => (d.floor ?? 1) === activeFloor);
  const windows = (alt.floor_plan?.windows || []).filter((w) => (w.floor ?? 1) === activeFloor);
  const repairLog = alt.floor_plan?.repairLog || [];
  const unit = alt.floor_plan?.unit || "m";

  // Compute SVG bounds — prefer the plot rect, fall back to room extents
  const allPoints = rooms.flatMap((r) => r.boundary || []);
  const bounds = plot
    ? { minX: 0, minY: 0, maxX: plot.width, maxY: plot.depth }
    : allPoints.length > 0
    ? {
        minX: Math.min(...allPoints.map((p) => p[0])),
        minY: Math.min(...allPoints.map((p) => p[1])),
        maxX: Math.max(...allPoints.map((p) => p[0])),
        maxY: Math.max(...allPoints.map((p) => p[1])),
      }
    : { minX: 0, minY: 0, maxX: 100, maxY: 100 };

  const span = Math.max(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY);
  const pad = span * 0.14; // room for dimension lines
  const viewBox = `${bounds.minX - pad} ${bounds.minY - pad} ${bounds.maxX - bounds.minX + pad * 2} ${bounds.maxY - bounds.minY + pad * 2}`;
  const wall = span * 0.014;
  const doorW = span * 0.045;
  const winW = span * 0.06;
  const dimOff = span * 0.06;
  const fontSize = span * 0.028;

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
        {floorNums.length > 1 && (
          <div className="flex gap-2">
            {floorNums.map((f) => (
              <Button
                key={f}
                variant={f === activeFloor ? "default" : "outline"}
                size="sm"
                onClick={() => setActiveFloor(f)}
              >
                {f === 1 ? "Ground floor" : `Floor ${f}`}
              </Button>
            ))}
          </div>
        )}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">
                Floor Plan{floorNums.length > 1 ? ` — ${activeFloor === 1 ? "Ground" : `F${activeFloor}`}` : ""}
              </CardTitle>
              <div className="flex items-center gap-2">
                <Badge
                  variant={
                    alt.compliance?.status === "pass"
                      ? "success"
                      : alt.compliance?.status === "fail"
                      ? "warning"
                      : "outline"
                  }
                >
                  {alt.compliance?.status === "pass"
                    ? "Compliant"
                    : alt.compliance?.status === "fail"
                    ? "Has Issues"
                    : "Not validated"}
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
                {/* Plot boundary — dashed site line */}
                {plot && (
                  <rect
                    x={0}
                    y={0}
                    width={plot.width}
                    height={plot.depth}
                    fill="#FBFAF7"
                    stroke="hsl(var(--vellum-line))"
                    strokeWidth={wall * 0.4}
                    strokeDasharray={`${wall * 1.6} ${wall * 0.8}`}
                  />
                )}

                {/* Room fills */}
                {rooms.map((room, i) => {
                  const pts = room.boundary;
                  if (!pts || pts.length < 3) return null;
                  const colors = [
                    "#E7EEF8", "#F0E7F8", "#F8F0E7", "#E7F8F0",
                    "#F8E7EC", "#E7ECF8", "#F0F8E7", "#F8E7F0",
                  ];
                  return (
                    <polygon
                      key={i}
                      points={pts.map((p) => `${p[0]},${p[1]}`).join(" ")}
                      fill={colors[i % colors.length]}
                      stroke="none"
                    />
                  );
                })}

                {/* Walls — drawn once per room edge, thick ink stroke */}
                {rooms.map((room, i) => {
                  const pts = room.boundary;
                  if (!pts || pts.length < 3) return null;
                  return (
                    <polygon
                      key={`w${i}`}
                      points={pts.map((p) => `${p[0]},${p[1]}`).join(" ")}
                      fill="none"
                      stroke="hsl(var(--ink))"
                      strokeWidth={wall}
                      strokeLinejoin="miter"
                    />
                  );
                })}

                {/* Door openings: white gap + leaf line + swing arc */}
                {doors.map((d, i) => {
                  const horiz = d.orientation === "h";
                  const gapProps = horiz
                    ? { x: d.x - doorW / 2, y: d.y - wall, width: doorW, height: wall * 2 }
                    : { x: d.x - wall, y: d.y - doorW / 2, width: wall * 2, height: doorW };
                  // Leaf extends perpendicular into the room below/right of the gap.
                  const leaf = horiz
                    ? `M ${d.x - doorW / 2} ${d.y} L ${d.x - doorW / 2} ${d.y + doorW}`
                    : `M ${d.x} ${d.y - doorW / 2} L ${d.x + doorW} ${d.y - doorW / 2}`;
                  const arc = horiz
                    ? `M ${d.x - doorW / 2} ${d.y + doorW} A ${doorW} ${doorW} 0 0 1 ${d.x + doorW / 2} ${d.y}`
                    : `M ${d.x + doorW} ${d.y - doorW / 2} A ${doorW} ${doorW} 0 0 1 ${d.x} ${d.y + doorW / 2}`;
                  return (
                    <g key={`d${i}`}>
                      <rect {...gapProps} fill="#FBFAF7" stroke="none" />
                      <path d={leaf} stroke="hsl(var(--ink))" strokeWidth={wall * 0.45} fill="none" />
                      <path d={arc} stroke="hsl(var(--muted))" strokeWidth={wall * 0.3} fill="none" strokeDasharray={`${wall * 0.5} ${wall * 0.3}`} />
                    </g>
                  );
                })}

                {/* Windows: white gap + blue double line */}
                {windows.map((w, i) => {
                  const horiz = w.orientation === "h";
                  const gapProps = horiz
                    ? { x: w.x - winW / 2, y: w.y - wall * 0.8, width: winW, height: wall * 1.6 }
                    : { x: w.x - wall * 0.8, y: w.y - winW / 2, width: wall * 1.6, height: winW };
                  const lineProps = horiz
                    ? { x1: w.x - winW / 2, y1: w.y, x2: w.x + winW / 2, y2: w.y }
                    : { x1: w.x, y1: w.y - winW / 2, x2: w.x, y2: w.y + winW / 2 };
                  return (
                    <g key={`win${i}`}>
                      <rect {...gapProps} fill="#FBFAF7" stroke="none" />
                      <line {...lineProps} stroke="#4A7EC2" strokeWidth={wall * 0.5} />
                      {horiz ? (
                        <>
                          <line x1={w.x - winW / 2} y1={w.y - wall * 0.35} x2={w.x + winW / 2} y2={w.y - wall * 0.35} stroke="#4A7EC2" strokeWidth={wall * 0.22} />
                          <line x1={w.x - winW / 2} y1={w.y + wall * 0.35} x2={w.x + winW / 2} y2={w.y + wall * 0.35} stroke="#4A7EC2" strokeWidth={wall * 0.22} />
                        </>
                      ) : (
                        <>
                          <line x1={w.x - wall * 0.35} y1={w.y - winW / 2} x2={w.x - wall * 0.35} y2={w.y + winW / 2} stroke="#4A7EC2" strokeWidth={wall * 0.22} />
                          <line x1={w.x + wall * 0.35} y1={w.y - winW / 2} x2={w.x + wall * 0.35} y2={w.y + winW / 2} stroke="#4A7EC2" strokeWidth={wall * 0.22} />
                        </>
                      )}
                    </g>
                  );
                })}

                {/* Room labels + areas */}
                {rooms.map((room, i) => {
                  const pts = room.boundary;
                  if (!pts || pts.length < 3) return null;
                  const [cx, cy] = roomCentroid(pts);
                  return (
                    <g key={`t${i}`} className="select-none">
                      <text
                        x={cx}
                        y={cy - fontSize * 0.3}
                        textAnchor="middle"
                        fontSize={fontSize}
                        fontWeight={600}
                        fill="hsl(var(--ink))"
                        className="font-display"
                      >
                        {room.label || room.type}
                      </text>
                      <text
                        x={cx}
                        y={cy + fontSize * 0.9}
                        textAnchor="middle"
                        fontSize={fontSize * 0.72}
                        fill="hsl(var(--muted))"
                        className="font-mono-tech"
                      >
                        {room.area.toFixed(1)} {unit}²
                      </text>
                    </g>
                  );
                })}

                {/* Dimension lines: width along bottom, depth along left */}
                {plot && (
                  <g stroke="hsl(var(--muted))" strokeWidth={wall * 0.3}>
                    {/* bottom width dimension */}
                    <line x1={0} y1={plot.depth + dimOff} x2={plot.width} y2={plot.depth + dimOff} />
                    <line x1={0} y1={plot.depth + dimOff - wall} x2={0} y2={plot.depth + dimOff + wall} />
                    <line x1={plot.width} y1={plot.depth + dimOff - wall} x2={plot.width} y2={plot.depth + dimOff + wall} />
                    <text
                      x={plot.width / 2}
                      y={plot.depth + dimOff + fontSize * 1.2}
                      textAnchor="middle"
                      fontSize={fontSize * 0.85}
                      fill="hsl(var(--muted))"
                      stroke="none"
                      className="font-mono-tech"
                    >
                      {plot.width} {unit}
                    </text>
                    {/* left depth dimension */}
                    <line x1={-dimOff} y1={0} x2={-dimOff} y2={plot.depth} />
                    <line x1={-dimOff - wall} y1={0} x2={-dimOff + wall} y2={0} />
                    <line x1={-dimOff - wall} y1={plot.depth} x2={-dimOff + wall} y2={plot.depth} />
                    <text
                      x={-dimOff - fontSize * 0.9}
                      y={plot.depth / 2}
                      textAnchor="middle"
                      fontSize={fontSize * 0.85}
                      fill="hsl(var(--muted))"
                      stroke="none"
                      className="font-mono-tech"
                      transform={`rotate(-90 ${-dimOff - fontSize * 0.9} ${plot.depth / 2})`}
                    >
                      {plot.depth} {unit}
                    </text>
                  </g>
                )}

                {/* North arrow */}
                <g transform={`translate(${bounds.maxX + pad * 0.45}, ${bounds.minY - pad * 0.35})`}>
                  <circle r={fontSize * 0.95} fill="none" stroke="hsl(var(--muted))" strokeWidth={wall * 0.25} />
                  <polygon
                    points={`0,${-fontSize * 0.7} ${fontSize * 0.3},${fontSize * 0.35} 0,${fontSize * 0.1} ${-fontSize * 0.3},${fontSize * 0.35}`}
                    fill="hsl(var(--ink))"
                  />
                  <text y={-fontSize * 1.15} textAnchor="middle" fontSize={fontSize * 0.7} fill="hsl(var(--ink))" className="font-mono-tech">
                    N
                  </text>
                </g>
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
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-base">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                Compliance
              </CardTitle>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs"
                onClick={() => {
                  setRevalidating(true);
                  onRevalidate().finally(() => setRevalidating(false));
                }}
                disabled={revalidating}
              >
                {revalidating ? "Checking…" : "Re-check"}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {repairLog.length > 0 && (
              <div className="mb-3 space-y-1 rounded-md border border-blueprint/30 bg-blueprint-pale/40 p-2">
                <p className="font-mono-tech text-[11px] font-semibold uppercase text-blueprint">
                  Auto-repaired
                </p>
                {repairLog.map((entry, i) => (
                  <p key={i} className="text-xs text-muted-foreground">
                    {entry}
                  </p>
                ))}
              </div>
            )}
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
              <Button variant="outline" size="sm" onClick={() => onExport("3d-massing")}>
                3D Massing
              </Button>
              <Button variant="outline" size="sm" onClick={() => onExport("png")}>
                PNG
              </Button>
              <Button variant="outline" size="sm" onClick={() => onExport("pdf")}>
                PDF
              </Button>
            </div>
            <Button
              variant="default"
              size="sm"
              className="mt-3 w-full"
              asChild
            >
              <Link to={`/review?candidateId=${alt.candidateId}`}>
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
