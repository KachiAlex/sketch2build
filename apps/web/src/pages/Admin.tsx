import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../contexts/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Select } from "../components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Skeleton } from "../components/ui/skeleton";
import { useToast } from "../components/ui/toast";
import {
  ChevronDown,
  ChevronRight,
  Loader2,
  Search,
  ShieldCheck,
  Trash2,
  UserCheck,
  Users,
  FolderKanban,
  Layers,
  ScrollText,
  Shapes,
  UserX,
} from "lucide-react";

interface Subscription {
  plan: string;
  status: string;
  seats: number;
  renewsAt: string | null;
}

interface AdminUser {
  id: string;
  email: string;
  name: string;
  role: string;
  status: string;
  organization?: string;
  projectCount: number;
  subscription: Subscription | null;
  createdAt: string;
}

interface Stats {
  users: number;
  suspendedUsers: number;
  projects: number;
  jobs: number;
  candidates: number;
  plans: Record<string, number>;
}

interface UserProject {
  id: string;
  name: string;
  jurisdiction: string;
  status: string;
  jobCount: number;
  createdAt: string;
}

interface UserDetail {
  user: AdminUser;
  projects: UserProject[];
}

interface AuditEntry {
  id: string;
  actor: string;
  action: string;
  targetType: string;
  targetId: string;
  metadata: Record<string, unknown> | null;
  createdAt: string;
}

const ROLES = ["architect", "drafter", "developer", "homeowner", "admin"];
const PLANS = ["free", "pro", "studio"];
const PAGE_SIZE = 20;

export default function Admin() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [stats, setStats] = useState<Stats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [expandedUser, setExpandedUser] = useState<string | null>(null);
  const [detail, setDetail] = useState<UserDetail | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, u, a] = await Promise.all([
        api.get<Stats>("/admin/stats"),
        api.get<{ total: number; users: AdminUser[] }>(
          `/admin/users?page=${page}&limit=${PAGE_SIZE}${query ? `&q=${encodeURIComponent(query)}` : ""}`
        ),
        api.get<{ entries: AuditEntry[] }>("/admin/audit?limit=50"),
      ]);
      setStats(s);
      setUsers(u.users);
      setTotal(u.total);
      setAudit(a.entries);
    } catch {
      // non-admin or network error — page guard handles the former
    } finally {
      setLoading(false);
    }
  }, [page, query]);

  useEffect(() => {
    if (user?.role === "admin") {
      load();
    }
  }, [user, load]);

  if (user && user.role !== "admin") {
    return <Navigate to="/dashboard" replace />;
  }

  function patchUser(updated: AdminUser) {
    setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
  }

  async function handleRole(u: AdminUser, role: string) {
    setBusy(u.id);
    try {
      patchUser(await api.patch<AdminUser>(`/admin/users/${u.id}/role`, { role }));
      toast({ title: "Role updated", description: `${u.email} → ${role}`, variant: "success" });
    } catch (err) {
      toast({ title: "Failed", description: err instanceof Error ? err.message : "Role update failed", variant: "error" });
    } finally {
      setBusy(null);
    }
  }

  async function handleStatus(u: AdminUser) {
    const status = u.status === "suspended" ? "active" : "suspended";
    setBusy(u.id);
    try {
      patchUser(await api.patch<AdminUser>(`/admin/users/${u.id}/status`, { status }));
      toast({ title: status === "suspended" ? "User suspended" : "User reactivated", description: u.email, variant: "success" });
    } catch (err) {
      toast({ title: "Failed", description: err instanceof Error ? err.message : "Status update failed", variant: "error" });
    } finally {
      setBusy(null);
    }
  }

  async function handlePlan(u: AdminUser, plan: string) {
    setBusy(u.id);
    try {
      const subscription = await api.patch<Subscription>(`/admin/users/${u.id}/subscription`, { plan });
      patchUser({ ...u, subscription });
      toast({ title: "Plan updated", description: `${u.email} → ${plan}`, variant: "success" });
    } catch (err) {
      toast({ title: "Failed", description: err instanceof Error ? err.message : "Plan update failed", variant: "error" });
    } finally {
      setBusy(null);
    }
  }

  async function toggleExpand(id: string) {
    if (expandedUser === id) {
      setExpandedUser(null);
      setDetail(null);
      return;
    }
    setExpandedUser(id);
    setDetail(null);
    try {
      const [user, proj] = await Promise.all([
        api.get<AdminUser>(`/admin/users/${id}`),
        api.get<{ projects: UserProject[] }>(`/admin/users/${id}/projects`),
      ]);
      setDetail({ user, projects: proj.projects });
    } catch {
      setDetail(null);
    }
  }

  async function handleDelete(u: AdminUser) {
    if (!window.confirm(`Delete ${u.email} and all their projects? This cannot be undone.`)) {
      return;
    }
    setBusy(u.id);
    try {
      await api.delete(`/admin/users/${u.id}`);
      setUsers((prev) => prev.filter((x) => x.id !== u.id));
      setTotal((t) => t - 1);
      toast({ title: "User deleted", description: u.email, variant: "success" });
    } catch (err) {
      toast({ title: "Failed", description: err instanceof Error ? err.message : "Delete failed", variant: "error" });
    } finally {
      setBusy(null);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-bold text-ink">Platform Admin</h1>
        <p className="font-mono-tech text-xs text-muted">SHEET A-000 · USER &amp; PLAN MANAGEMENT</p>
      </div>

      {loading && !stats ? (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      ) : stats ? (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
          {[
            { label: "Users", value: stats.users, icon: Users },
            { label: "Suspended", value: stats.suspendedUsers, icon: UserX },
            { label: "Projects", value: stats.projects, icon: FolderKanban },
            { label: "Jobs", value: stats.jobs, icon: Layers },
            { label: "Candidates", value: stats.candidates, icon: Shapes },
          ].map(({ label, value, icon: Icon }) => (
            <Card key={label} className="border-[1.5px] border-vellum-line">
              <CardContent className="flex items-center gap-3 p-4">
                <Icon className="h-5 w-5 text-muted" />
                <div>
                  <p className="font-display text-xl font-bold text-ink">{value}</p>
                  <p className="font-mono-tech text-[11px] uppercase text-muted">{label}</p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : null}

      {stats && Object.keys(stats.plans).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(stats.plans).map(([plan, count]) => (
            <Badge key={plan} variant="blueprint" className="text-xs">
              {plan}: {count}
            </Badge>
          ))}
        </div>
      )}

      <Card className="border-[1.5px] border-vellum-line">
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle className="text-base">Users ({total})</CardTitle>
            <form
              className="flex items-center gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                setPage(1);
                setQuery(search.trim());
              }}
            >
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search name or email"
                className="w-56"
              />
              <Button type="submit" variant="outline" size="sm">
                <Search className="h-4 w-4" />
              </Button>
            </form>
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {loading ? (
            <div className="space-y-2">
              <Skeleton className="h-16" />
              <Skeleton className="h-16" />
              <Skeleton className="h-16" />
            </div>
          ) : users.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">No users found.</p>
          ) : (
            users.map((u) => {
              const isSelf = u.id === user?.id;
              const expanded = expandedUser === u.id;
              return (
                <div key={u.id}>
                <div
                  className="flex flex-wrap items-center gap-3 rounded-[2px] border-[1.5px] border-vellum-line bg-white/60 px-4 py-3"
                >
                  <button
                    type="button"
                    onClick={() => toggleExpand(u.id)}
                    className="text-muted hover:text-ink"
                    aria-label={expanded ? "Collapse details" : "Expand details"}
                  >
                    {expanded ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4" />
                    )}
                  </button>
                  <div className="min-w-[220px] flex-1">
                    <div className="flex items-center gap-2">
                      <p className="font-display text-sm font-semibold text-ink">{u.name}</p>
                      {u.role === "admin" && <ShieldCheck className="h-3.5 w-3.5 text-redline" />}
                      {u.status === "suspended" && (
                        <Badge variant="destructive" className="text-[10px]">
                          suspended
                        </Badge>
                      )}
                      {isSelf && (
                        <Badge variant="blueprint" className="text-[10px]">
                          you
                        </Badge>
                      )}
                    </div>
                    <p className="font-mono-tech text-xs text-muted">
                      {u.email}
                      {u.organization ? ` · ${u.organization}` : ""} · {u.projectCount} project
                      {u.projectCount === 1 ? "" : "s"}
                    </p>
                  </div>

                  <Select
                    value={u.role}
                    disabled={isSelf || busy === u.id}
                    onChange={(e) => handleRole(u, e.target.value)}
                    className="w-32"
                    aria-label="Role"
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </Select>

                  <Select
                    value={u.subscription?.plan ?? "free"}
                    disabled={busy === u.id}
                    onChange={(e) => handlePlan(u, e.target.value)}
                    className="w-28"
                    aria-label="Plan"
                  >
                    {PLANS.map((p) => (
                      <option key={p} value={p}>
                        {p}
                      </option>
                    ))}
                  </Select>

                  <div className="flex items-center gap-1">
                    {busy === u.id && <Loader2 className="h-4 w-4 animate-spin text-muted" />}
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={isSelf || busy === u.id}
                      onClick={() => handleStatus(u)}
                      title={u.status === "suspended" ? "Reactivate" : "Suspend"}
                    >
                      {u.status === "suspended" ? <UserCheck className="h-4 w-4" /> : <UserX className="h-4 w-4" />}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={isSelf || busy === u.id}
                      onClick={() => handleDelete(u)}
                      title="Delete user"
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                {expanded && (
                  <div className="mx-4 mb-1 rounded-b-[2px] border-[1.5px] border-t-0 border-vellum-line bg-vellum/40 px-4 py-3">
                    {!detail ? (
                      <p className="font-mono-tech text-xs text-muted">Loading details…</p>
                    ) : (
                      <div className="space-y-2">
                        <p className="font-mono-tech text-[11px] uppercase text-muted">
                          joined {new Date(detail.user.createdAt).toLocaleDateString()}
                          {detail.user.subscription
                            ? ` · ${detail.user.subscription.plan} (${detail.user.subscription.status}) · ${detail.user.subscription.seats} seat(s)`
                            : " · no subscription"}
                          {detail.user.subscription?.renewsAt
                            ? ` · renews ${new Date(detail.user.subscription.renewsAt).toLocaleDateString()}`
                            : ""}
                        </p>
                        {detail.projects.length === 0 ? (
                          <p className="text-xs text-muted-foreground">No projects.</p>
                        ) : (
                          <ul className="space-y-1">
                            {detail.projects.map((p) => (
                              <li
                                key={p.id}
                                className="flex items-center justify-between text-xs"
                              >
                                <span className="font-medium text-ink">{p.name}</span>
                                <span className="font-mono-tech text-muted">
                                  {p.jurisdiction} · {p.jobCount} job{p.jobCount === 1 ? "" : "s"} · {p.status}
                                </span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}
                  </div>
                )}
                </div>
              );
            })
          )}

          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-2">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                Previous
              </Button>
              <span className="font-mono-tech text-xs text-muted">
                page {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border-[1.5px] border-vellum-line">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <ScrollText className="h-4 w-4 text-blueprint" />
            Audit log
          </CardTitle>
        </CardHeader>
        <CardContent>
          {audit.length === 0 ? (
            <p className="text-sm text-muted-foreground">No admin actions recorded yet.</p>
          ) : (
            <div className="space-y-1">
              {audit.map((e) => (
                <div
                  key={e.id}
                  className="flex flex-wrap items-baseline justify-between gap-2 border-b border-vellum-line pb-1.5 text-xs last:border-0"
                >
                  <div>
                    <span className="font-medium text-ink">{e.actor}</span>{" "}
                    <span className="text-muted-foreground">{e.action.replace(/_/g, " ")}</span>{" "}
                    <span className="font-mono-tech text-muted">{e.targetType}:{e.targetId.slice(0, 8)}</span>
                    {e.metadata && Object.keys(e.metadata).length > 0 && (
                      <span className="font-mono-tech text-muted"> — {JSON.stringify(e.metadata)}</span>
                    )}
                  </div>
                  <span className="font-mono-tech text-muted">
                    {new Date(e.createdAt).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
