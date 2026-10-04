import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../contexts/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { useToast } from "../components/ui/toast";
import { Loader2 } from "lucide-react";

interface Entitlements {
  plan: string;
  jobsPerMonth: number | null;
  jobsUsed: number;
  projectsAllowed: number | null;
  projectsUsed: number;
  exportFormats: string[];
  renewsAt: string | null;
}

interface OrgMember {
  id: string;
  name: string;
  email: string;
  role: string;
  projects: Array<{ id: string; name: string; status: string }>;
}

interface Organization {
  id: string;
  name: string;
  ownerId: string;
  members: OrgMember[];
}

export default function Settings() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [form, setForm] = useState({ currentPassword: "", newPassword: "", confirm: "" });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [entitlements, setEntitlements] = useState<Entitlements | null>(null);
  const [org, setOrg] = useState<Organization | null>(null);
  const [orgLoaded, setOrgLoaded] = useState(false);
  const [orgName, setOrgName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [orgBusy, setOrgBusy] = useState(false);

  async function loadOrg() {
    try {
      const data = await api.get<{ organization: Organization | null }>("/organizations/mine");
      setOrg(data.organization);
    } catch {
      // no org is a normal state
    } finally {
      setOrgLoaded(true);
    }
  }

  useEffect(() => {
    api.get<Entitlements>("/me/entitlements").then(setEntitlements).catch(() => {});
    loadOrg();
  }, []);

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

  async function createOrg(e: React.FormEvent) {
    e.preventDefault();
    setOrgBusy(true);
    try {
      await api.post("/organizations", { name: orgName });
      setOrgName("");
      await loadOrg();
      toast({ title: "Organization created", variant: "success" });
    } catch (err) {
      toast({ title: "Failed", description: err instanceof Error ? err.message : "Could not create organization", variant: "error" });
    } finally {
      setOrgBusy(false);
    }
  }

  async function invite(e: React.FormEvent) {
    e.preventDefault();
    setOrgBusy(true);
    try {
      await api.post("/organizations/invite", { email: inviteEmail });
      setInviteEmail("");
      await loadOrg();
      toast({ title: "Member added", variant: "success" });
    } catch (err) {
      toast({ title: "Failed", description: err instanceof Error ? err.message : "Invite failed", variant: "error" });
    } finally {
      setOrgBusy(false);
    }
  }

  async function leaveOrg() {
    if (!window.confirm("Leave this organization?")) return;
    setOrgBusy(true);
    try {
      await api.post("/organizations/leave", {});
      setOrg(null);
      toast({ title: "Left organization", variant: "success" });
    } catch (err) {
      toast({ title: "Failed", description: err instanceof Error ? err.message : "Could not leave", variant: "error" });
    } finally {
      setOrgBusy(false);
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

      {entitlements && (
        <Card className="border-[1.5px] border-vellum-line">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Plan & usage</CardTitle>
              <Badge variant="blueprint">{entitlements.plan}</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Generations this month</span>
              <span className="font-mono-tech text-ink">
                {entitlements.jobsUsed} / {entitlements.jobsPerMonth ?? "∞"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Projects</span>
              <span className="font-mono-tech text-ink">
                {entitlements.projectsUsed} / {entitlements.projectsAllowed ?? "∞"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Export formats</span>
              <span className="font-mono-tech text-ink">{entitlements.exportFormats.join(", ")}</span>
            </div>
            {entitlements.renewsAt && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Renews</span>
                <span className="font-mono-tech text-ink">
                  {new Date(entitlements.renewsAt).toLocaleDateString()}
                </span>
              </div>
            )}
            {entitlements.plan === "free" && (
              <p className="pt-1 text-xs text-muted-foreground">
                Upgrade for higher limits and IFC/GLB exports — contact your admin.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {orgLoaded && (
        <Card className="border-[1.5px] border-vellum-line">
          <CardHeader>
            <CardTitle className="text-base">Organization</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {!org ? (
              <form onSubmit={createOrg} className="flex items-end gap-2">
                <div className="flex-1 space-y-2">
                  <Label htmlFor="orgName">Create a workspace</Label>
                  <Input
                    id="orgName"
                    value={orgName}
                    onChange={(e) => setOrgName(e.target.value)}
                    placeholder="Studio name"
                    required
                    minLength={2}
                  />
                </div>
                <Button type="submit" disabled={orgBusy}>Create</Button>
              </form>
            ) : (
              <>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-display text-sm font-semibold text-ink">{org.name}</p>
                    <p className="font-mono-tech text-xs text-muted">
                      {org.members.length} member{org.members.length === 1 ? "" : "s"}
                      {org.ownerId === user?.id ? " · you own this workspace" : ""}
                    </p>
                  </div>
                  {org.ownerId !== user?.id && (
                    <Button variant="outline" size="sm" onClick={leaveOrg} disabled={orgBusy}>
                      Leave
                    </Button>
                  )}
                </div>

                <ul className="space-y-1.5">
                  {org.members.map((m) => (
                    <li key={m.id} className="flex items-center justify-between text-xs">
                      <span className="font-medium text-ink">
                        {m.name}
                        {m.id === org.ownerId ? " (owner)" : ""}
                      </span>
                      <span className="font-mono-tech text-muted">
                        {m.email} · {m.projects.length} project{m.projects.length === 1 ? "" : "s"}
                      </span>
                    </li>
                  ))}
                </ul>

                {org.ownerId === user?.id && (
                  <form onSubmit={invite} className="flex items-end gap-2">
                    <div className="flex-1 space-y-2">
                      <Label htmlFor="inviteEmail">Add member by email</Label>
                      <Input
                        id="inviteEmail"
                        type="email"
                        value={inviteEmail}
                        onChange={(e) => setInviteEmail(e.target.value)}
                        placeholder="teammate@studio.com"
                        required
                      />
                    </div>
                    <Button type="submit" variant="outline" disabled={orgBusy}>Add</Button>
                  </form>
                )}
              </>
            )}
          </CardContent>
        </Card>
      )}

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
