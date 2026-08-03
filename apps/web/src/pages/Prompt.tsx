import { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Sparkles, Wand2, Globe } from "lucide-react";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select } from "../components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { useToast } from "../components/ui/toast";

const STYLES = [
  { value: "modern", label: "Modern" },
  { value: "scandinavian", label: "Scandinavian" },
  { value: "industrial", label: "Industrial" },
  { value: "japanese", label: "Japanese Minimal" },
  { value: "tropical", label: "Tropical" },
  { value: "mediterranean", label: "Mediterranean" },
  { value: "contemporary", label: "Contemporary" },
  { value: "traditional", label: "Traditional" },
];

const COMPLIANCE_STANDARDS = [
  { value: "NBC", label: "Nigerian Building Code (NBC)" },
  { value: "IBC", label: "International Building Code (IBC)" },
  { value: "GCC", label: "Gulf Construction Code (GCC)" },
  { value: "EURO", label: "Eurocode" },
];

const ROOM_PRESETS = [
  { label: "Studio apartment", prompt: "A studio apartment with an open kitchen, bathroom, and combined living-sleeping area" },
  { label: "1-bedroom flat", prompt: "A 1-bedroom flat with a living room, kitchen, bedroom, and bathroom" },
  { label: "2-bedroom bungalow", prompt: "A 2-bedroom bungalow with living room, kitchen, dining, 2 bedrooms, 2 bathrooms, and entrance" },
  { label: "3-bedroom family home", prompt: "A 3-bedroom family home with a spacious living room, open kitchen, dining area, master bedroom with en-suite, 2 additional bedrooms, a shared bathroom, and a guest toilet" },
  { label: "Office space", prompt: "An office space with a reception, open workspace, 2 private offices, a meeting room, kitchenette, and 2 restrooms" },
];

export default function Prompt() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const projectId = searchParams.get("projectId") || "";

  const [form, setForm] = useState({
    plotWidth: "",
    plotDepth: "",
    unit: "m" as "m" | "ft" | "cm" | "mm",
    orientation: "",
    roomCount: "",
    prompt: "",
    style: "modern",
    complianceStandard: "NBC",
    alternatives: "3",
    floors: "1",
    regionalProfile: "none",
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [regionalProfiles, setRegionalProfiles] = useState<{ id: string; name: string; climate_zone: string }[]>([]);

  useEffect(() => {
    api
      .get<{ profiles: { id: string; name: string; climate_zone: string }[] }>("/regional/profiles")
      .then((data) => setRegionalProfiles(data.profiles))
      .catch(() => {});
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!projectId) {
      setError("Please select or create a project first.");
      return;
    }
    setIsSubmitting(true);
    try {
      const data = await api.post<{ job: { id: string; status: string } }>("/jobs", {
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
          style: form.style,
          compliance_standard: form.complianceStandard,
          generate_alternatives: parseInt(form.alternatives, 10),
          floors: parseInt(form.floors, 10),
          regional_profile: form.regionalProfile !== "none" ? form.regionalProfile : undefined,
        },
      });
      toast({
        title: "Generation started",
        description: `Job ${data.job.id} is being processed`,
        variant: "success",
      });
      navigate(`/results/${data.job.id}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Request failed";
      setError(msg);
      toast({ title: "Generation failed", description: msg, variant: "error" });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Sparkles className="h-6 w-6 text-redline" />
        <div>
          <h1 className="font-display text-2xl font-bold text-ink">Prompt Studio</h1>
          <p className="font-mono-tech text-xs text-muted">
            SHEET P-100 · TEXT-TO-DESIGN
          </p>
        </div>
      </div>

      {!projectId && (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          No project selected.{" "}
          <a href="/projects" className="font-semibold underline">
            Create or select a project
          </a>{" "}
          first.
        </div>
      )}

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Quick presets */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Quick presets</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {ROOM_PRESETS.map((preset) => (
              <button
                key={preset.label}
                type="button"
                onClick={() => setForm({ ...form, prompt: preset.prompt })}
                className="rounded-md border border-vellum-line bg-vellum px-3 py-1.5 text-xs font-medium text-ink-soft transition-colors hover:border-blueprint hover:text-blueprint"
              >
                {preset.label}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Main form */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Wand2 className="h-5 w-5 text-blueprint" />
            Design brief
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2">
            {/* Plot dimensions */}
            <div className="space-y-2">
              <Label htmlFor="plotWidth">Plot width</Label>
              <Input
                id="plotWidth"
                type="number"
                value={form.plotWidth}
                onChange={(e) => setForm({ ...form, plotWidth: e.target.value })}
                required
                placeholder="e.g. 15"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="plotDepth">Plot depth</Label>
              <Input
                id="plotDepth"
                type="number"
                value={form.plotDepth}
                onChange={(e) => setForm({ ...form, plotDepth: e.target.value })}
                required
                placeholder="e.g. 20"
              />
            </div>

            {/* Unit */}
            <div className="space-y-2">
              <Label htmlFor="unit">Unit</Label>
              <Select
                id="unit"
                value={form.unit}
                onChange={(e) => setForm({ ...form, unit: e.target.value as "m" | "ft" | "cm" | "mm" })}
              >
                <option value="m">Metres</option>
                <option value="ft">Feet</option>
                <option value="cm">Centimetres</option>
                <option value="mm">Millimetres</option>
              </Select>
            </div>

            {/* Orientation */}
            <div className="space-y-2">
              <Label htmlFor="orientation">Orientation (degrees, optional)</Label>
              <Input
                id="orientation"
                type="number"
                value={form.orientation}
                onChange={(e) => setForm({ ...form, orientation: e.target.value })}
                placeholder="e.g. 180 (south-facing)"
              />
            </div>

            {/* Style */}
            <div className="space-y-2">
              <Label htmlFor="style">Architectural style</Label>
              <Select
                id="style"
                value={form.style}
                onChange={(e) => setForm({ ...form, style: e.target.value })}
              >
                {STYLES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </Select>
            </div>

            {/* Compliance standard */}
            <div className="space-y-2">
              <Label htmlFor="complianceStandard">Compliance standard</Label>
              <Select
                id="complianceStandard"
                value={form.complianceStandard}
                onChange={(e) => setForm({ ...form, complianceStandard: e.target.value })}
              >
                {COMPLIANCE_STANDARDS.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </Select>
            </div>

            {/* Room count */}
            <div className="space-y-2">
              <Label htmlFor="roomCount">Room count (optional)</Label>
              <Input
                id="roomCount"
                type="number"
                value={form.roomCount}
                onChange={(e) => setForm({ ...form, roomCount: e.target.value })}
                placeholder="Auto-detect from prompt"
              />
            </div>

            {/* Alternatives */}
            <div className="space-y-2">
              <Label htmlFor="alternatives">Alternatives to generate</Label>
              <Select
                id="alternatives"
                value={form.alternatives}
                onChange={(e) => setForm({ ...form, alternatives: e.target.value })}
              >
                <option value="1">1 option</option>
                <option value="2">2 options</option>
                <option value="3">3 options</option>
                <option value="5">5 options</option>
              </Select>
            </div>

            {/* Floors */}
            <div className="space-y-2">
              <Label htmlFor="floors">Number of floors</Label>
              <Select
                id="floors"
                value={form.floors}
                onChange={(e) => setForm({ ...form, floors: e.target.value })}
              >
                <option value="1">Single storey</option>
                <option value="2">Two storeys</option>
                <option value="3">Three storeys</option>
              </Select>
            </div>

            {/* Regional profile */}
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="regionalProfile" className="flex items-center gap-1.5">
                <Globe className="h-3.5 w-3.5 text-blueprint" />
                Regional profile (optional)
              </Label>
              <Select
                id="regionalProfile"
                value={form.regionalProfile}
                onChange={(e) => setForm({ ...form, regionalProfile: e.target.value })}
              >
                <option value="none">No regional adjustment</option>
                {regionalProfiles.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} — {p.climate_zone}
                  </option>
                ))}
              </Select>
              <p className="text-xs text-muted-foreground">
                Adapts room sizes, ventilation, and compliance rules to local climate and cultural norms.
              </p>
            </div>

            {/* Free text prompt */}
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="prompt">Free-text elaboration</Label>
              <textarea
                id="prompt"
                value={form.prompt}
                onChange={(e) => setForm({ ...form, prompt: e.target.value })}
                rows={4}
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder="e.g. I need a 3-bedroom bungalow with the living room facing north, an open kitchen, and a large master bedroom with an en-suite bathroom..."
              />
            </div>

            <div className="sm:col-span-2">
              <Button
                type="submit"
                disabled={isSubmitting || !projectId}
                className="w-full"
              >
                {isSubmitting ? (
                  <>
                    <span className="mr-2 animate-spin">○</span>
                    Generating…
                  </>
                ) : (
                  <>
                    <Wand2 className="mr-2 h-4 w-4" />
                    Generate layouts
                  </>
                )}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
