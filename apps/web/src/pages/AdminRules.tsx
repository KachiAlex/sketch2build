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
import { ScrollText } from "lucide-react";

interface Rule {
  id: string;
  jurisdiction: string;
  ruleType: string;
  parameters: Record<string, unknown>;
  version: string;
  effectiveDate: string;
}

const RULE_TYPES = [
  { value: "setback", label: "Setback" },
  { value: "height_limit", label: "Height Limit" },
  { value: "plot_coverage", label: "Plot Coverage" },
  { value: "parking", label: "Parking Requirement" },
  { value: "room_size", label: "Minimum Room Size" },
  { value: "ventilation", label: "Ventilation" },
];

export default function AdminRules() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({
    jurisdiction: "Nigeria",
    ruleType: "setback",
    parameters: "",
    version: "",
    effectiveDate: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { toast } = useToast();

  async function loadRules() {
    setLoading(true);
    try {
      const data = await api.get<{ rules: Rule[] }>("/compliance/rules");
      setRules(data.rules);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadRules();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const parameters = JSON.parse(form.parameters || "{}") as Record<string, unknown>;
      await api.post("/compliance/rules", {
        jurisdiction: form.jurisdiction,
        ruleType: form.ruleType,
        parameters,
        version: form.version,
        effectiveDate: form.effectiveDate,
      });
      setForm({ jurisdiction: "Nigeria", ruleType: "setback", parameters: "", version: "", effectiveDate: "" });
      await loadRules();
      toast({ title: "Rule created", description: `${form.ruleType} — ${form.jurisdiction}`, variant: "success" });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to create rule";
      setError(msg);
      toast({ title: "Failed to create rule", description: msg, variant: "error" });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="font-display text-2xl font-bold text-ink">Compliance Rules Admin</h1>
        <p className="font-mono-tech text-xs text-muted">
          SHEET A-200 · RULES MANAGEMENT
        </p>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle>Add rule</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="jurisdiction">Jurisdiction</Label>
              <Input id="jurisdiction" value={form.jurisdiction} onChange={(e) => setForm({ ...form, jurisdiction: e.target.value })} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ruleType">Rule type</Label>
              <Select
                id="ruleType"
                value={form.ruleType}
                onChange={(e) => setForm({ ...form, ruleType: e.target.value })}
              >
                {RULE_TYPES.map((rt) => (
                  <option key={rt.value} value={rt.value}>
                    {rt.label}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="parameters">Parameters (JSON)</Label>
              <Input id="parameters" value={form.parameters} onChange={(e) => setForm({ ...form, parameters: e.target.value })} placeholder='{"distance": 6}' />
            </div>
            <div className="space-y-2">
              <Label htmlFor="version">Version</Label>
              <Input id="version" value={form.version} onChange={(e) => setForm({ ...form, version: e.target.value })} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="effectiveDate">Effective date</Label>
              <Input id="effectiveDate" type="datetime-local" value={form.effectiveDate} onChange={(e) => setForm({ ...form, effectiveDate: e.target.value })} required />
            </div>
            <div className="sm:col-span-2">
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? "Creating…" : "Create rule"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <div className="space-y-4">
        <h2 className="font-display text-xl font-semibold text-ink">Rules</h2>
        {loading ? (
          <div className="space-y-4">
            <Skeleton className="h-28" />
            <Skeleton className="h-28" />
            <Skeleton className="h-28" />
          </div>
        ) : rules.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center gap-3 py-12">
              <ScrollText className="h-8 w-8 text-muted" />
              <p className="text-sm text-muted-foreground">
                No compliance rules yet. Add one above to get started.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4">
            {rules.map((rule) => (
              <Card key={rule.id} className="border-[1.5px] border-vellum-line">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">
                      {rule.ruleType} — {rule.jurisdiction}
                    </CardTitle>
                    <Badge variant="blueprint" className="text-xs">
                      v{rule.version}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <pre className="overflow-x-auto rounded-md bg-muted p-2 text-xs">
                    {JSON.stringify(rule.parameters, null, 2)}
                  </pre>
                  <p className="mt-2 font-mono-tech text-xs text-muted">
                    Effective: {new Date(rule.effectiveDate).toLocaleString()}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
