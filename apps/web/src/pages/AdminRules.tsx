import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";

interface Rule {
  id: string;
  jurisdiction: string;
  ruleType: string;
  parameters: Record<string, unknown>;
  version: string;
  effectiveDate: string;
}

export default function AdminRules() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [form, setForm] = useState({
    jurisdiction: "Nigeria",
    ruleType: "setback",
    parameters: "",
    version: "",
    effectiveDate: "",
  });
  const [error, setError] = useState<string | null>(null);

  async function loadRules() {
    const data = await api.get<{ rules: Rule[] }>("/compliance/rules");
    setRules(data.rules);
  }

  useEffect(() => {
    loadRules();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create rule");
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
              <Input id="ruleType" value={form.ruleType} onChange={(e) => setForm({ ...form, ruleType: e.target.value })} required />
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
              <Button type="submit">Create rule</Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Rules</h2>
        {rules.length === 0 ? (
          <p className="text-muted-foreground">No rules yet.</p>
        ) : (
          <div className="grid gap-4">
            {rules.map((rule) => (
              <Card key={rule.id}>
                <CardHeader>
                  <CardTitle className="text-base">{rule.ruleType} — {rule.jurisdiction} ({rule.version})</CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="overflow-x-auto rounded-md bg-muted p-2 text-xs">
                    {JSON.stringify(rule.parameters, null, 2)}
                  </pre>
                  <p className="mt-2 text-sm text-muted-foreground">Effective: {new Date(rule.effectiveDate).toLocaleString()}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
