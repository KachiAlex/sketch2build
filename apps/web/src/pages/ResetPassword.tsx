import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    setSubmitting(true);
    try {
      await api.post("/auth/reset-password", { token, newPassword: password });
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-vellum-grid">
      <form
        onSubmit={handleSubmit}
        className="relative w-full max-w-sm space-y-6 border-[1.5px] border-ink bg-white p-8 shadow-sheet"
      >
        <span className="tick tick-tl" />
        <span className="tick tick-tr" />
        <span className="tick tick-bl" />
        <span className="tick tick-br" />

        <div className="space-y-1">
          <h1 className="font-display text-xl font-bold text-ink">Choose a new password</h1>
          <p className="font-mono-tech text-xs text-muted">
            SHEET AUTH-111 · RECOVERY
          </p>
        </div>

        {!token ? (
          <div className="space-y-4">
            <p className="text-sm text-destructive">
              This reset link is missing its token. Request a new one.
            </p>
            <Button asChild variant="outline" className="w-full">
              <Link to="/forgot-password">Request reset link</Link>
            </Button>
          </div>
        ) : done ? (
          <div className="space-y-4">
            <p className="text-sm text-ink">Password updated. You can sign in now.</p>
            <Button asChild className="w-full">
              <Link to="/login">Sign in</Link>
            </Button>
          </div>
        ) : (
          <>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="space-y-2">
              <Label htmlFor="password">New password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={8}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm">Confirm password</Label>
              <Input
                id="confirm"
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? "Updating…" : "Set new password"}
            </Button>
          </>
        )}
      </form>
    </div>
  );
}
