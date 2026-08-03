import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
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
          <div className="flex items-center gap-[9px] font-display font-bold text-[17px]">
            <span className="relative h-5 w-5 border-2 border-ink">
              <span className="absolute -right-1 -bottom-1 h-2 w-2 bg-redline" />
            </span>
            <span className="text-ink">Sketch2Build</span>
          </div>
          <h1 className="font-display text-xl font-bold text-ink">Sign in</h1>
          <p className="font-mono-tech text-xs text-muted">
            SHEET AUTH-100 · ACCESS CONTROL
          </p>
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        <Button type="submit" className="w-full">Sign in</Button>
        <p className="text-center text-sm text-muted-foreground">
          No account?{" "}
          <a href="/register" className="font-medium text-blueprint hover:underline">
            Create one
          </a>
        </p>
      </form>
    </div>
  );
}
