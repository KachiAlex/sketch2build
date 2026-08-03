import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";

interface Room {
  id: string;
  type: string;
  label?: string;
  area: number;
  boundaryGeometry: number[][];
}

interface Candidate {
  id: string;
  rank: number;
  score?: number;
  complianceStatus: string;
  jobId: string;
  rooms: Room[];
  complianceViolations: Array<{ ruleId: string; message: string; severity: string }>;
}

interface EditHistoryItem {
  id: string;
  changeDescription: string;
  timestamp: string;
}

export default function Review() {
  const [searchParams] = useSearchParams();
  const candidateId = searchParams.get("candidateId") || "";

  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [history, setHistory] = useState<EditHistoryItem[]>([]);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [dragging, setDragging] = useState<{ index: number; offset: [number, number] } | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const bounds = useMemo(() => {
    const allPoints = rooms.flatMap((r) => r.boundaryGeometry);
    if (!allPoints.length) return { minX: 0, minY: 0, width: 100, height: 100 };
    const xs = allPoints.map((p) => p[0]);
    const ys = allPoints.map((p) => p[1]);
    const minX = Math.min(...xs);
    const minY = Math.min(...ys);
    const width = Math.max(...xs) - minX;
    const height = Math.max(...ys) - minY;
    return { minX, minY, width: Math.max(width, 1), height: Math.max(height, 1) };
  }, [rooms]);

  const loadCandidate = useCallback(async () => {
    if (!candidateId) return;
    setError(null);
    try {
      const data = await api.get<Candidate>(`/review/candidates/${candidateId}`);
      setCandidate(data);
      setRooms(data.rooms);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load candidate");
    }
  }, [candidateId]);

  const loadHistory = useCallback(async () => {
    if (!candidateId) return;
    try {
      const data = await api.get<{ history: EditHistoryItem[] }>(`/review/candidates/${candidateId}/history`);
      setHistory(data.history);
    } catch {
      // ignore
    }
  }, [candidateId]);

  useEffect(() => {
    loadCandidate();
    loadHistory();
  }, [loadCandidate, loadHistory]);

  function getSvgPoint(clientX: number, clientY: number): [number, number] {
    const svg = svgRef.current;
    if (!svg) return [0, 0];
    const pt = svg.createSVGPoint();
    pt.x = clientX;
    pt.y = clientY;
    const ctm = svg.getScreenCTM();
    if (!ctm) return [0, 0];
    const svgP = pt.matrixTransform(ctm.inverse());
    return [svgP.x, svgP.y];
  }

  function handleMouseDown(e: React.MouseEvent, index: number) {
    e.preventDefault();
    const [x, y] = getSvgPoint(e.clientX, e.clientY);
    const room = rooms[index];
    const centroid = roomCentroid(room.boundaryGeometry);
    setDragging({ index, offset: [x - centroid[0], y - centroid[1]] });
    setSelectedIndex(index);
  }

  function handleMouseMove(e: React.MouseEvent) {
    if (!dragging) return;
    const [x, y] = getSvgPoint(e.clientX, e.clientY);
    const dx = x - dragging.offset[0];
    const dy = y - dragging.offset[1];
    const centroid = roomCentroid(rooms[dragging.index].boundaryGeometry);
    const delta: [number, number] = [dx - centroid[0], dy - centroid[1]];

    setRooms((prev) => {
      const next = [...prev];
      const room = next[dragging.index];
      room.boundaryGeometry = room.boundaryGeometry.map(([px, py]) => [px + delta[0], py + delta[1]]);
      return next;
    });
  }

  function handleMouseUp() {
    setDragging(null);
  }

  async function saveGeometry() {
    if (!candidateId) return;
    setIsSaving(true);
    setError(null);
    try {
      const payload = rooms.map((room) => ({
        id: room.id,
        type: room.type,
        label: room.label,
        area: polygonArea(room.boundaryGeometry),
        boundaryGeometry: room.boundaryGeometry,
      }));
      await api.patch(`/review/candidates/${candidateId}/geometry`, { rooms: payload });
      await loadCandidate();
      await loadHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleRevert(historyId: string) {
    if (!candidateId) return;
    setError(null);
    try {
      await api.post(`/review/candidates/${candidateId}/revert`, { historyId });
      await loadCandidate();
      await loadHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Revert failed");
    }
  }

  async function handleFinalize() {
    if (!candidate?.jobId) return;
    if (!window.confirm("I confirm this layout has been reviewed by a licensed architect and is ready for export.")) return;
    setError(null);
    try {
      await api.post(`/review/jobs/${candidate.jobId}/finalize`, {});
      await loadCandidate();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Finalize failed");
    }
  }

  async function handleExport(format: string, filename: string) {
    if (!candidateId) return;
    setError(null);
    try {
      await api.download(`/exports/${candidateId}/${format}`, filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    }
  }

  function updateRoomField(index: number, field: "type" | "label", value: string) {
    setRooms((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: value };
      return next;
    });
  }

  const padding = Math.max(bounds.width, bounds.height) * 0.1;
  const viewBox = `${bounds.minX - padding} ${bounds.minY - padding} ${bounds.width + padding * 2} ${bounds.height + padding * 2}`;

  if (!candidateId) {
    return <div className="p-6">No candidate selected.</div>;
  }

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6 lg:flex-row">
      <div className="flex-1 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display text-2xl font-bold text-ink">Review Candidate #{candidate?.rank}</h1>
            <p className="font-mono-tech text-xs text-muted">
              SHEET R-100 · ARCHITECT REVIEW · SCORE: {candidate?.score ?? "—"} · {candidate?.complianceStatus}
            </p>
          </div>
          <div className="flex gap-2">
            <Button onClick={saveGeometry} disabled={isSaving}>
              {isSaving ? "Saving…" : "Save edits"}
            </Button>
            <Button variant="outline" onClick={handleFinalize}>
              Finalize
            </Button>
          </div>
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}

        <Card>
          <CardContent className="p-0">
            <svg
              ref={svgRef}
              viewBox={viewBox}
              className="h-[500px] w-full cursor-crosshair bg-muted/30"
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
            >
              {rooms.map((room, index) => (
                <g key={room.id} onMouseDown={(e) => handleMouseDown(e, index)}>
                  <polygon
                    points={room.boundaryGeometry.map((p) => `${p[0]},${p[1]}`).join(" ")}
                    fill={selectedIndex === index ? "hsl(var(--primary) / 0.2)" : "hsl(var(--card))"}
                    stroke="hsl(var(--foreground))"
                    strokeWidth={0.5}
                    className="cursor-move"
                  />
                  <text
                    x={roomCentroid(room.boundaryGeometry)[0]}
                    y={roomCentroid(room.boundaryGeometry)[1]}
                    textAnchor="middle"
                    className="pointer-events-none select-none fill-foreground text-[3px]"
                  >
                    {room.label || room.type}
                  </text>
                </g>
              ))}
            </svg>
          </CardContent>
        </Card>
      </div>

      <div className="w-full space-y-4 lg:w-80">
        <Card>
          <CardHeader>
            <CardTitle>Room properties</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {selectedIndex === null ? (
              <p className="text-sm text-muted-foreground">Select a room to edit.</p>
            ) : (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Type</Label>
                  <Input
                    value={rooms[selectedIndex].type}
                    onChange={(e) => updateRoomField(selectedIndex, "type", e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Label</Label>
                  <Input
                    value={rooms[selectedIndex].label || ""}
                    onChange={(e) => updateRoomField(selectedIndex, "label", e.target.value)}
                  />
                </div>
                <p className="text-sm text-muted-foreground">
                  Area: {polygonArea(rooms[selectedIndex].boundaryGeometry).toFixed(2)} m²
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Compliance violations</CardTitle>
          </CardHeader>
          <CardContent>
            {candidate?.complianceViolations?.length ? (
              <ul className="space-y-2 text-sm">
                {candidate.complianceViolations.map((v) => (
                  <li key={v.ruleId} className="rounded-md border border-destructive/30 p-2 text-destructive">
                    {v.message}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">No violations reported.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Edit history</CardTitle>
          </CardHeader>
          <CardContent>
            {history.length === 0 ? (
              <p className="text-sm text-muted-foreground">No edits yet.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {history.map((h) => (
                  <li key={h.id} className="flex items-center justify-between">
                    <span>{h.changeDescription}</span>
                    <Button size="sm" variant="outline" onClick={() => handleRevert(h.id)}>
                      Revert
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Exports</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-2">
              <Button variant="outline" onClick={() => handleExport("dxf", `layout-${candidateId}.dxf`)}>
                DXF (2D)
              </Button>
              <Button variant="outline" onClick={() => handleExport("dxf3d", `layout-${candidateId}-3d.dxf`)}>
                DXF (3D)
              </Button>
              <Button variant="outline" onClick={() => handleExport("ifc", `layout-${candidateId}.ifc`)}>
                IFC (BIM)
              </Button>
              <Button variant="outline" onClick={() => handleExport("glb", `layout-${candidateId}.glb`)}>
                GLB (3D)
              </Button>
              <Button variant="outline" onClick={() => handleExport("png", `layout-${candidateId}.png`)}>
                PNG
              </Button>
              <Button variant="outline" onClick={() => handleExport("preview3d", `preview-${candidateId}.png`)}>
                3D Preview
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function roomCentroid(points: number[][]): [number, number] {
  const n = points.length;
  let cx = 0;
  let cy = 0;
  for (const [x, y] of points) {
    cx += x;
    cy += y;
  }
  return [cx / n, cy / n];
}

function polygonArea(points: number[][]): number {
  let area = 0;
  const n = points.length;
  for (let i = 0; i < n; i++) {
    const [x1, y1] = points[i];
    const [x2, y2] = points[(i + 1) % n];
    area += x1 * y2 - x2 * y1;
  }
  return Math.abs(area) / 2;
}
