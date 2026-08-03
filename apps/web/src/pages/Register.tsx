import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select } from "../components/ui/select";

const roles = [
  { value: "homeowner", label: "Homeowner" },
  { value: "drafter", label: "Drafter" },
  { value: "architect", label: "Architect" },
  { value: "developer", label: "Developer" },
  { value: "admin", label: "Admin" },
];

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    email: "",
    password: "",
    name: "",
    role: "homeowner",
    organization: "",
  });
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await register(form);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-vellum-grid">
      <form
        onSubmit={handleSubmit}
        className="relative w-full max-w-sm space-y-5 border-[1.5px] border-ink bg-white p-8 shadow-sheet"
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
          <h1 className="font-display text-xl font-bold text-ink">Create account</h1>
          <p className="font-mono-tech text-xs text-muted">
            SHEET AUTH-200 · USER REGISTRATION
          </p>
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <div className="space-y-2">
          <Label htmlFor="name">Full name</Label>
          <Input id="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
        </div>
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input id="password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
        </div>
        <div className="space-y-2">
          <Label htmlFor="role">Role</Label>
          <Select
            id="role"
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
          >
            {roles.map((role) => (
              <option key={role.value} value={role.value}>
                {role.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="organization">Organization (optional)</Label>
          <Input id="organization" value={form.organization} onChange={(e) => setForm({ ...form, organization: e.target.value })} />
        </div>
        <Button type="submit" className="w-full">Create account</Button>
        <p className="text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <a href="/login" className="font-medium text-blueprint hover:underline">
            Sign in
          </a>
        </p>
      </form>
    </div>
  );
}
