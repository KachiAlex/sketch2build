import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";

type Point = { x: number; y: number };
type VectorGraph = {
  walls: { start: Point; end: Point }[];
  doors: unknown[];
  windows: unknown[];
  rooms: unknown[];
};

export default function Sketch() {
  const [searchParams] = useSearchParams();
  const projectId = searchParams.get("projectId") || "";
  const fileInputRef = useRef<HTMLInputElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageSize, setImageSize] = useState<{ width: number; height: number } | null>(null);
  const [startPoint, setStartPoint] = useState<Point | null>(null);
  const [endPoint, setEndPoint] = useState<Point | null>(null);
  const [referenceLength, setReferenceLength] = useState("");
  const [unit, setUnit] = useState<"m" | "ft" | "cm" | "mm">("m");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<{ job: { id: string; status: string } } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [vectorGraph, setVectorGraph] = useState<VectorGraph | null>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    setImageUrl(url);
    setStartPoint(null);
    setEndPoint(null);
    setVectorGraph(null);
    const img = new Image();
    img.onload = () => {
      setImageSize({ width: img.naturalWidth, height: img.naturalHeight });
    };
    img.src = url;
  }

  function getCanvasPoint(e: React.MouseEvent<HTMLCanvasElement>): Point {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    };
  }

  function handleMouseDown(e: React.MouseEvent<HTMLCanvasElement>) {
    const point = getCanvasPoint(e);
    setStartPoint(point);
    setEndPoint(point);
  }

  function handleMouseMove(e: React.MouseEvent<HTMLCanvasElement>) {
    if (!startPoint) return;
    setEndPoint(getCanvasPoint(e));
  }

  function handleMouseUp() {
    if (startPoint && endPoint) {
      // Snap to right angles if close enough
      const dx = Math.abs(endPoint.x - startPoint.x);
      const dy = Math.abs(endPoint.y - startPoint.y);
      if (Math.abs(dx - dy) > Math.max(dx, dy) * 0.15) {
        if (dx < dy * 0.15) {
          setEndPoint({ x: startPoint.x, y: endPoint.y });
        } else if (dy < dx * 0.15) {
          setEndPoint({ x: endPoint.x, y: startPoint.y });
        }
      }
    }
    setStartPoint(null);
  }

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !imageSize) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const displayWidth = canvas.clientWidth;
    const displayHeight = canvas.clientHeight;
    canvas.width = displayWidth;
    canvas.height = displayHeight;

    ctx.clearRect(0, 0, displayWidth, displayHeight);

    if (startPoint && endPoint) {
      ctx.strokeStyle = "#ef4444";
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(startPoint.x, startPoint.y);
      ctx.lineTo(endPoint.x, endPoint.y);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = "#ef4444";
      ctx.beginPath();
      ctx.arc(startPoint.x, startPoint.y, 4, 0, Math.PI * 2);
      ctx.arc(endPoint.x, endPoint.y, 4, 0, Math.PI * 2);
      ctx.fill();
    }

    if (vectorGraph) {
      ctx.strokeStyle = "#3b82f6";
      ctx.lineWidth = 3;
      const scaleX = displayWidth / (imageSize.width || 1);
      const scaleY = displayHeight / (imageSize.height || 1);
      for (const wall of vectorGraph.walls) {
        ctx.beginPath();
        ctx.moveTo(wall.start.x * scaleX, wall.start.y * scaleY);
        ctx.lineTo(wall.end.x * scaleX, wall.end.y * scaleY);
        ctx.stroke();
      }
    }
  }, [startPoint, endPoint, vectorGraph, imageSize]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!fileInputRef.current?.files?.[0]) {
      setError("Please select a sketch file.");
      return;
    }
    if (!endPoint) {
      setError("Please draw a reference line on the sketch.");
      return;
    }
    const length = parseFloat(referenceLength);
    if (!length || length <= 0) {
      setError("Enter a positive reference length.");
      return;
    }

    setIsUploading(true);
    setError(null);
    try {
      const file = fileInputRef.current.files[0];
      const base64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve((reader.result as string).split(",")[1]);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
      const result = await api.post<{ job: { id: string; status: string } }>(`/sketch`, {
        projectId,
        fileData: base64,
        fileType: file.type,
        referenceLength: parseFloat(referenceLength),
        unit,
      });
      setUploadResult(result);
      setVectorGraph({
        walls: [
          { start: { x: 0, y: 0 }, end: { x: imageSize?.width || 100, y: 0 } },
          { start: { x: imageSize?.width || 100, y: 0 }, end: { x: imageSize?.width || 100, y: imageSize?.height || 80 } },
          { start: { x: imageSize?.width || 100, y: imageSize?.height || 80 }, end: { x: 0, y: imageSize?.height || 80 } },
          { start: { x: 0, y: imageSize?.height || 80 }, end: { x: 0, y: 0 } },
        ],
        doors: [],
        windows: [],
        rooms: [],
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  }

  const referencePixels = startPoint && endPoint ? Math.hypot(endPoint.x - startPoint.x, endPoint.y - startPoint.y) : 0;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Upload sketch</h1>
      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle>1. Select sketch image</CardTitle>
        </CardHeader>
        <CardContent>
          <Input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,application/pdf"
            onChange={handleFileChange}
          />
        </CardContent>
      </Card>

      {imageUrl && imageSize && (
        <Card>
          <CardHeader>
            <CardTitle>2. Draw a known reference line</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div
              ref={containerRef}
              className="relative inline-block max-w-full overflow-hidden rounded-md border"
            >
              <img
                src={imageUrl}
                alt="Sketch preview"
                className="max-h-[60vh] w-auto object-contain"
                style={{ display: "block" }}
              />
              <canvas
                ref={canvasRef}
                className="absolute inset-0 h-full w-full cursor-crosshair"
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
              />
            </div>
            {endPoint && (
              <p className="text-sm text-muted-foreground">
                Reference pixels: {referencePixels.toFixed(1)}
              </p>
            )}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="referenceLength">Real-world length</Label>
                  <Input
                    id="referenceLength"
                    type="number"
                    value={referenceLength}
                    onChange={(e) => setReferenceLength(e.target.value)}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="unit">Unit</Label>
                  <select
                    id="unit"
                    value={unit}
                    onChange={(e) => setUnit(e.target.value as "m" | "ft" | "cm" | "mm")}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  >
                    <option value="m">Metres</option>
                    <option value="ft">Feet</option>
                    <option value="cm">Centimetres</option>
                    <option value="mm">Millimetres</option>
                  </select>
                </div>
              </div>
              <Button type="submit" disabled={isUploading || !endPoint}>
                {isUploading ? "Uploading…" : "Submit for digitization"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {uploadResult && (
        <Card>
          <CardHeader>
            <CardTitle>Digitization job</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm">Job ID: {uploadResult.job.id}</p>
            <p className="text-sm">Status: {uploadResult.job.status}</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
