import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.post("/auth/forgot-password", { email });
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
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
          <h1 className="font-display text-xl font-bold text-ink">Reset password</h1>
          <p className="font-mono-tech text-xs text-muted">
            SHEET AUTH-110 · RECOVERY
          </p>
        </div>

        {sent ? (
          <div className="space-y-4">
            <p className="text-sm text-ink">
              If an account exists for that email, a reset link is on its way.
              It expires in 60 minutes.
            </p>
            <Button asChild variant="outline" className="w-full">
              <Link to="/login">Back to sign in</Link>
            </Button>
          </div>
        ) : (
          <>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? "Sending…" : "Send reset link"}
            </Button>
            <p className="text-center text-sm text-muted-foreground">
              <Link to="/login" className="font-medium text-blueprint hover:underline">
                Back to sign in
              </Link>
            </p>
          </>
        )}
      </form>
    </div>
  );
}
