import { useState, useEffect, useMemo } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Sparkles, Wand2, Globe, Loader2, FolderKanban, Compass } from "lucide-react";
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
  { value: "NBC", label: "Nigerian Building Code (NBC)", suggestedProfile: "tropical" },
  { value: "IBC", label: "International Building Code (IBC)", suggestedProfile: "us_default" },
  { value: "GCC", label: "Gulf Construction Code (GCC)", suggestedProfile: "middle_east" },
  { value: "EURO", label: "Eurocode", suggestedProfile: "continental" },
];

const ROOM_PRESETS = [
  { label: "Studio apartment", prompt: "A studio apartment with an open kitchen, bathroom, and combined living-sleeping area" },
  { label: "1-bedroom flat", prompt: "A 1-bedroom flat with a living room, kitchen, bedroom, and bathroom" },
  { label: "2-bedroom bungalow", prompt: "A 2-bedroom bungalow with living room, kitchen, dining, 2 bedrooms, 2 bathrooms, and entrance" },
  { label: "3-bedroom family home", prompt: "A 3-bedroom family home with a spacious living room, open kitchen, dining area, master bedroom with en-suite, 2 additional bedrooms, a shared bathroom, and a guest toilet" },
  { label: "Office space", prompt: "An office space with a reception, open workspace, 2 private offices, a meeting room, kitchenette, and 2 restrooms" },
];

const CONSTRAINT_CHIPS = [
  "en-suite master bedroom",
  "open kitchen",
  "living room faces north",
  "guest toilet",
  "balcony off the living room",
  "home office",
];

const COMPASS_DIRECTIONS = [
  { label: "N", deg: 0 },
  { label: "NE", deg: 45 },
  { label: "E", deg: 90 },
  { label: "SE", deg: 135 },
  { label: "S", deg: 180 },
  { label: "SW", deg: 225 },
  { label: "W", deg: 270 },
  { label: "NW", deg: 315 },
];

const UNIT_SUFFIX: Record<string, string> = { m: "m", ft: "ft", cm: "cm", mm: "mm" };

type FormState = {
  plotWidth: string;
  plotDepth: string;
  unit: "m" | "ft" | "cm" | "mm";
  orientation: string;
  roomCount: string;
  prompt: string;
  style: string;
  complianceStandard: string;
  alternatives: string;
  floors: string;
  regionalProfile: string;
};

type FieldErrors = Partial<Record<"plotWidth" | "plotDepth" | "orientation" | "roomCount", string>>;

const INITIAL_FORM: FormState = {
  plotWidth: "",
  plotDepth: "",
  unit: "m",
  orientation: "",
  roomCount: "",
  prompt: "",
  style: "modern",
  complianceStandard: "NBC",
  alternatives: "3",
  floors: "1",
  regionalProfile: "none",
};

interface Project {
  id: string;
  name: string;
}

function validateForm(form: FormState): FieldErrors {
  const errors: FieldErrors = {};

  for (const key of ["plotWidth", "plotDepth"] as const) {
    const value = parseFloat(form[key]);
    if (!form[key] || isNaN(value) || value <= 0) {
      errors[key] = "Must be a positive number";
    } else if (value > 1000) {
      errors[key] = "Unusually large — check the unit";
    }
  }

  if (form.orientation !== "") {
    const o = parseFloat(form.orientation);
    if (isNaN(o) || o < 0 || o >= 360) {
      errors.orientation = "Enter a bearing between 0 and 360";
    }
  }

  if (form.roomCount !== "") {
    const r = Number(form.roomCount);
    if (!Number.isInteger(r) || r < 1 || r > 30) {
      errors.roomCount = "Whole number between 1 and 30";
    }
  }

  return errors;
}

function draftKey(projectId: string) {
  return `s2b:prompt-draft:${projectId}`;
}

function loadDraft(projectId: string): FormState | null {
  try {
    const raw = localStorage.getItem(draftKey(projectId));
    return raw ? { ...INITIAL_FORM, ...(JSON.parse(raw) as Partial<FormState>) } : null;
  } catch {
    return null;
  }
}

export default function Prompt() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const projectId = searchParams.get("projectId") || "";

  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [touched, setTouched] = useState<Set<string>>(new Set());
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [regionalProfiles, setRegionalProfiles] = useState<{ id: string; name: string; climate_zone: string }[]>([]);
  const [profileTouched, setProfileTouched] = useState(false);

  const activeProject = useMemo(
    () => projects.find((p) => p.id === projectId),
    [projects, projectId]
  );

  // Load projects + regional profiles.
  useEffect(() => {
    api
      .get<{ projects: Project[] }>("/projects")
      .then((data) => setProjects(data.projects || []))
      .catch(() => {})
      .finally(() => setProjectsLoading(false));

    api
      .get<{ profiles: { id: string; name: string; climate_zone: string }[] }>("/regional/profiles")
      .then((data) => setRegionalProfiles(data.profiles))
      .catch(() => {});
  }, []);

  // Auto-select the project when there is exactly one.
  useEffect(() => {
    if (!projectId && !projectsLoading && projects.length === 1) {
      navigate(`/prompt?projectId=${projects[0].id}`, { replace: true });
    }
  }, [projectId, projects, projectsLoading, navigate]);

  // Restore the draft whenever the project changes.
  useEffect(() => {
    if (!projectId) {
      setForm(INITIAL_FORM);
      return;
    }
    setForm(loadDraft(projectId) ?? INITIAL_FORM);
    setTouched(new Set());
    setSubmitAttempted(false);
    setError(null);
  }, [projectId]);

  // Persist the draft on every change.
  useEffect(() => {
    if (!projectId) return;
    try {
      localStorage.setItem(draftKey(projectId), JSON.stringify(form));
    } catch {
      // storage full/blocked — non-fatal
    }
  }, [form, projectId]);

  const fieldErrors = validateForm(form);
  const showError = (field: keyof FieldErrors) =>
    (submitAttempted || touched.has(field)) && fieldErrors[field];

  const plotArea = useMemo(() => {
    const w = parseFloat(form.plotWidth);
    const d = parseFloat(form.plotDepth);
    if (isNaN(w) || isNaN(d) || w <= 0 || d <= 0) return null;
    return w * d;
  }, [form.plotWidth, form.plotDepth]);

  function markTouched(field: string) {
    setTouched((prev) => (prev.has(field) ? prev : new Set(prev).add(field)));
  }

  function applyComplianceStandard(value: string) {
    const update: Partial<FormState> = { complianceStandard: value };
    // Suggest a matching regional profile unless the user picked one manually.
    if (!profileTouched) {
      const suggested = COMPLIANCE_STANDARDS.find((c) => c.value === value)?.suggestedProfile;
      if (suggested) update.regionalProfile = suggested;
    }
    setForm({ ...form, ...update });
  }

  function insertPromptText(text: string) {
    if (!form.prompt.trim()) {
      setForm({ ...form, prompt: text });
      return;
    }
    if (form.prompt.includes(text)) return;
    const separator = /[.!?\n]\s*$/.test(form.prompt.trim()) ? " " : ". ";
    setForm({ ...form, prompt: form.prompt.trimEnd() + separator + text });
  }

  function applyPreset(preset: (typeof ROOM_PRESETS)[number]) {
    if (form.prompt.includes(preset.prompt)) {
      // Toggle off: remove this preset's text.
      const next = form.prompt.replace(preset.prompt, "").replace(/\s{2,}/g, " ").replace(/^[.,\s]+|[.,\s]+$/g, "");
      setForm({ ...form, prompt: next });
      return;
    }
    insertPromptText(preset.prompt);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitAttempted(true);
    if (!projectId) {
      setError("Please select or create a project first.");
      return;
    }
    if (Object.keys(fieldErrors).length > 0) {
      setError("Please fix the highlighted fields.");
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
      localStorage.removeItem(draftKey(projectId));
      toast({
        title: "Generation started",
        description: `Job ${data.job.id} is being processed`,
        variant: "success",
      });
      navigate(`/results/${data.job.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  const orientationDeg = parseFloat(form.orientation);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Sparkles className="h-6 w-6 text-redline" />
          <div>
            <h1 className="font-display text-2xl font-bold text-ink">Prompt Studio</h1>
            <p className="font-mono-tech text-xs text-muted">
              SHEET P-100 · TEXT-TO-DESIGN
            </p>
          </div>
        </div>
        {activeProject && (
          <div className="flex items-center gap-2 rounded-md border border-vellum-line bg-vellum px-3 py-1.5">
            <FolderKanban className="h-3.5 w-3.5 text-blueprint" />
            <span className="text-xs font-medium text-ink">{activeProject.name}</span>
          </div>
        )}
      </div>

      {!projectId && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Select a project</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {projectsLoading ? (
              <p className="text-sm text-muted-foreground">Loading your projects…</p>
            ) : projects.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No projects yet.{" "}
                <a href="/projects" className="font-semibold text-blueprint underline">
                  Create one first
                </a>
                .
              </p>
            ) : (
              <>
                <Select
                  aria-label="Select project"
                  value=""
                  onChange={(e) => {
                    if (e.target.value) navigate(`/prompt?projectId=${e.target.value}`);
                  }}
                >
                  <option value="">Choose a project…</option>
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </Select>
                <p className="text-xs text-muted-foreground">
                  Or{" "}
                  <a href="/projects" className="font-semibold text-blueprint underline">
                    create a new project
                  </a>
                  .
                </p>
              </>
            )}
          </CardContent>
        </Card>
      )}

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

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
            {/* Free-text prompt — the primary input */}
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="prompt">Describe your design</Label>
              <textarea
                id="prompt"
                value={form.prompt}
                onChange={(e) => setForm({ ...form, prompt: e.target.value })}
                rows={5}
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder="e.g. I need a 3-bedroom bungalow with the living room facing north, an open kitchen, and a large master bedroom with an en-suite bathroom..."
              />
              <p className="text-xs text-muted-foreground">
                Mention rooms, counts, and must-haves — e.g. "3 bedrooms", "open kitchen", "en-suite master". The more specific, the better the layout.
              </p>
              <div className="flex flex-wrap gap-1.5">
                {CONSTRAINT_CHIPS.map((chip) => (
                  <button
                    key={chip}
                    type="button"
                    onClick={() => insertPromptText(chip)}
                    className="rounded-full border border-vellum-line bg-vellum px-2.5 py-1 text-[11px] font-medium text-ink-soft transition-colors hover:border-blueprint hover:text-blueprint"
                  >
                    + {chip}
                  </button>
                ))}
              </div>
            </div>

            {/* Quick presets — insert into the prompt, toggle to remove */}
            <div className="space-y-2 sm:col-span-2">
              <Label>Quick presets</Label>
              <div className="flex flex-wrap gap-2">
                {ROOM_PRESETS.map((preset) => {
                  const active = form.prompt.includes(preset.prompt);
                  return (
                    <button
                      key={preset.label}
                      type="button"
                      aria-pressed={active}
                      onClick={() => applyPreset(preset)}
                      className={
                        active
                          ? "rounded-md border border-blueprint bg-blueprint/10 px-3 py-1.5 text-xs font-medium text-blueprint transition-colors"
                          : "rounded-md border border-vellum-line bg-vellum px-3 py-1.5 text-xs font-medium text-ink-soft transition-colors hover:border-blueprint hover:text-blueprint"
                      }
                    >
                      {preset.label}
                    </button>
                  );
                })}
              </div>
              <p className="text-xs text-muted-foreground">
                Presets add to your brief — click again to remove.
              </p>
            </div>

            {/* Plot dimensions + unit, grouped */}
            <div className="space-y-2 sm:col-span-2">
              <Label>Plot dimensions</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="plotWidth"
                  aria-label="Plot width"
                  type="number"
                  min="0"
                  step="any"
                  value={form.plotWidth}
                  onBlur={() => markTouched("plotWidth")}
                  onChange={(e) => setForm({ ...form, plotWidth: e.target.value })}
                  placeholder="Width"
                  className="w-28"
                />
                <span className="text-muted">×</span>
                <Input
                  id="plotDepth"
                  aria-label="Plot depth"
                  type="number"
                  min="0"
                  step="any"
                  value={form.plotDepth}
                  onBlur={() => markTouched("plotDepth")}
                  onChange={(e) => setForm({ ...form, plotDepth: e.target.value })}
                  placeholder="Depth"
                  className="w-28"
                />
                <Select
                  id="unit"
                  aria-label="Unit"
                  value={form.unit}
                  onChange={(e) => setForm({ ...form, unit: e.target.value as FormState["unit"] })}
                  className="w-32"
                >
                  <option value="m">Metres</option>
                  <option value="ft">Feet</option>
                  <option value="cm">Centimetres</option>
                  <option value="mm">Millimetres</option>
                </Select>
                {plotArea !== null && (
                  <span className="ml-1 whitespace-nowrap font-mono-tech text-xs text-muted">
                    ≈ {plotArea >= 100 ? Math.round(plotArea).toLocaleString() : plotArea.toFixed(1)} {UNIT_SUFFIX[form.unit]}²
                  </span>
                )}
              </div>
              {(showError("plotWidth") || showError("plotDepth")) && (
                <p className="text-xs text-destructive">
                  {fieldErrors.plotWidth || fieldErrors.plotDepth}
                </p>
              )}
            </div>

            {/* Orientation: compass picker + degrees input */}
            <div className="space-y-2 sm:col-span-2">
              <Label className="flex items-center gap-1.5">
                <Compass className="h-3.5 w-3.5 text-blueprint" />
                Orientation (optional)
              </Label>
              <div className="flex items-center gap-2">
                <div className="flex overflow-hidden rounded-md border border-vellum-line">
                  {COMPASS_DIRECTIONS.map((d) => (
                    <button
                      key={d.label}
                      type="button"
                      onClick={() => setForm({ ...form, orientation: String(d.deg) })}
                      className={
                        orientationDeg === d.deg
                          ? "bg-blueprint px-2.5 py-2 text-xs font-semibold text-white"
                          : "bg-vellum px-2.5 py-2 text-xs font-medium text-ink-soft transition-colors hover:text-blueprint"
                      }
                      title={`${d.label} — ${d.deg}°`}
                    >
                      {d.label}
                    </button>
                  ))}
                </div>
                <Input
                  id="orientation"
                  type="number"
                  min="0"
                  max="360"
                  step="any"
                  value={form.orientation}
                  onBlur={() => markTouched("orientation")}
                  onChange={(e) => setForm({ ...form, orientation: e.target.value })}
                  placeholder="0–360°"
                  className="w-28"
                />
                {form.orientation !== "" && (
                  <button
                    type="button"
                    onClick={() => setForm({ ...form, orientation: "" })}
                    className="text-xs text-muted-foreground underline hover:text-ink"
                  >
                    clear
                  </button>
                )}
              </div>
              {showError("orientation") && (
                <p className="text-xs text-destructive">{fieldErrors.orientation}</p>
              )}
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
                onChange={(e) => applyComplianceStandard(e.target.value)}
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
                min="1"
                max="30"
                step="1"
                value={form.roomCount}
                onBlur={() => markTouched("roomCount")}
                onChange={(e) => setForm({ ...form, roomCount: e.target.value })}
                placeholder="Auto-detect from brief"
              />
              {showError("roomCount") && (
                <p className="text-xs text-destructive">{fieldErrors.roomCount}</p>
              )}
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
                onChange={(e) => {
                  setProfileTouched(true);
                  setForm({ ...form, regionalProfile: e.target.value });
                }}
              >
                <option value="none">No regional adjustment</option>
                {regionalProfiles.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} — {p.climate_zone}
                  </option>
                ))}
              </Select>
              <p className="text-xs text-muted-foreground">
                Adapts room sizes, ventilation, and compliance rules to local climate and cultural norms.{" "}
                {!profileTouched && "Suggested automatically from your compliance standard."}
              </p>
            </div>

            <div className="sm:col-span-2">
              <Button
                type="submit"
                disabled={isSubmitting || !projectId}
                className="w-full"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
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
