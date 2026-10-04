import { useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../contexts/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { useToast } from "../components/ui/toast";
import { Loader2 } from "lucide-react";

export default function Settings() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [form, setForm] = useState({ currentPassword: "", newPassword: "", confirm: "" });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (form.newPassword !== form.confirm) {
      setError("New passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      await api.post("/auth/change-password", {
        currentPassword: form.currentPassword,
        newPassword: form.newPassword,
      });
      setForm({ currentPassword: "", newPassword: "", confirm: "" });
      toast({ title: "Password updated", description: "Your new password is active immediately.", variant: "success" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to change password");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div>
        <h1 className="font-display text-2xl font-bold text-ink">Settings</h1>
        <p className="font-mono-tech text-xs text-muted">SHEET A-900 · ACCOUNT</p>
      </div>

      <Card className="border-[1.5px] border-vellum-line">
        <CardHeader>
          <CardTitle className="text-base">Account</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1 font-mono-tech text-sm text-muted">
          <p>{user?.name}</p>
          <p>{user?.email}</p>
          <p>
            role: {user?.role}
            {user?.organization ? ` · ${user.organization}` : ""}
          </p>
        </CardContent>
      </Card>

      <Card className="border-[1.5px] border-vellum-line">
        <CardHeader>
          <CardTitle className="text-base">Change password</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="space-y-2">
              <Label htmlFor="current">Current password</Label>
              <Input
                id="current"
                type="password"
                value={form.currentPassword}
                onChange={(e) => setForm({ ...form, currentPassword: e.target.value })}
                required
                autoComplete="current-password"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new">New password</Label>
              <Input
                id="new"
                type="password"
                minLength={8}
                value={form.newPassword}
                onChange={(e) => setForm({ ...form, newPassword: e.target.value })}
                required
                autoComplete="new-password"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm">Confirm new password</Label>
              <Input
                id="confirm"
                type="password"
                minLength={8}
                value={form.confirm}
                onChange={(e) => setForm({ ...form, confirm: e.target.value })}
                required
                autoComplete="new-password"
              />
            </div>
            <Button type="submit" disabled={submitting}>
              {submitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Updating…
                </>
              ) : (
                "Update password"
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
