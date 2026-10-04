import { prisma } from "../lib/prisma";
import { AppError } from "../lib/errors";

export const ROLES = ["architect", "drafter", "developer", "homeowner", "admin"] as const;
export const PLANS = ["free", "pro", "studio"] as const;
export const SUBSCRIPTION_STATUSES = ["active", "trialing", "past_due", "canceled"] as const;

type UserWithExtras = {
  id: string;
  email: string;
  name: string;
  role: string;
  status: string;
  organization: string | null;
  createdAt: Date;
  subscription: {
    plan: string;
    status: string;
    seats: number;
    renewsAt: Date | null;
  } | null;
  _count: { projects: number };
};

function serializeUser(user: UserWithExtras) {
  return {
    id: user.id,
    email: user.email,
    name: user.name,
    role: user.role,
    status: user.status,
    organization: user.organization ?? undefined,
    projectCount: user._count.projects,
    subscription: user.subscription
      ? {
          plan: user.subscription.plan,
          status: user.subscription.status,
          seats: user.subscription.seats,
          renewsAt: user.subscription.renewsAt?.toISOString() ?? null,
        }
      : null,
    createdAt: user.createdAt.toISOString(),
  };
}

async function requireUser(userId: string) {
  const user = await prisma.user.findUnique({ where: { id: userId } });
  if (!user) {
    throw new AppError(404, "User not found", "USER_NOT_FOUND");
  }
  return user;
}

async function adminCount() {
  return prisma.user.count({ where: { role: "admin" } });
}

async function audit(
  actorId: string,
  action: string,
  targetType: string,
  targetId: string,
  metadata?: Record<string, unknown>
) {
  await prisma.auditLog.create({
    data: { actorId, action, targetType, targetId, metadata: (metadata ?? null) as never },
  });
}

export async function getAdminStats() {
  const [users, suspendedUsers, projects, jobs, candidates, plans] = await Promise.all([
    prisma.user.count(),
    prisma.user.count({ where: { status: "suspended" } }),
    prisma.project.count(),
    prisma.generationJob.count(),
    prisma.candidate.count(),
    prisma.subscription.groupBy({ by: ["plan"], _count: { plan: true } }),
  ]);
  return {
    users,
    suspendedUsers,
    projects,
    jobs,
    candidates,
    plans: Object.fromEntries(plans.map((p) => [p.plan, p._count.plan])),
  };
}

export async function listUsers(params: { q?: string; page: number; limit: number }) {
  const where = params.q
    ? {
        OR: [
          { email: { contains: params.q, mode: "insensitive" as const } },
          { name: { contains: params.q, mode: "insensitive" as const } },
        ],
      }
    : {};
  const [total, users] = await Promise.all([
    prisma.user.count({ where }),
    prisma.user.findMany({
      where,
      orderBy: { createdAt: "desc" },
      skip: (params.page - 1) * params.limit,
      take: params.limit,
      include: { subscription: true, _count: { select: { projects: true } } },
    }),
  ]);
  return {
    total,
    page: params.page,
    limit: params.limit,
    users: users.map(serializeUser),
  };
}

export async function getUserDetail(userId: string) {
  const user = await prisma.user.findUnique({
    where: { id: userId },
    include: {
      subscription: true,
      _count: { select: { projects: true } },
    },
  });
  if (!user) {
    throw new AppError(404, "User not found", "USER_NOT_FOUND");
  }
  return serializeUser(user);
}

export async function setUserRole(actorId: string, userId: string, role: (typeof ROLES)[number]) {
  const target = await requireUser(userId);
  if (target.id === actorId) {
    throw new AppError(400, "You cannot change your own role", "SELF_ROLE_CHANGE");
  }
  if (target.role === "admin" && role !== "admin" && (await adminCount()) <= 1) {
    throw new AppError(400, "Cannot demote the last admin", "LAST_ADMIN");
  }
  const user = await prisma.user.update({
    where: { id: userId },
    data: { role },
    include: { subscription: true, _count: { select: { projects: true } } },
  });
  await audit(actorId, "role_change", "user", userId, { from: target.role, to: role });
  return serializeUser(user);
}

export async function setUserStatus(actorId: string, userId: string, status: "active" | "suspended") {
  const target = await requireUser(userId);
  if (target.id === actorId) {
    throw new AppError(400, "You cannot change your own status", "SELF_STATUS_CHANGE");
  }
  if (status === "suspended" && target.role === "admin" && (await adminCount()) <= 1) {
    throw new AppError(400, "Cannot suspend the last admin", "LAST_ADMIN");
  }
  const user = await prisma.user.update({
    where: { id: userId },
    data: { status },
    include: { subscription: true, _count: { select: { projects: true } } },
  });
  await audit(actorId, "status_change", "user", userId, { from: target.status, to: status });
  return serializeUser(user);
}

export async function setUserSubscription(
  actorId: string,
  userId: string,
  input: {
    plan?: (typeof PLANS)[number];
    status?: (typeof SUBSCRIPTION_STATUSES)[number];
    seats?: number;
    renewsAt?: Date | null;
  }
) {
  await requireUser(userId);
  const subscription = await prisma.subscription.upsert({
    where: { userId },
    create: {
      userId,
      plan: input.plan ?? "free",
      status: input.status ?? "active",
      seats: input.seats ?? 1,
      renewsAt: input.renewsAt ?? null,
    },
    update: {
      plan: input.plan,
      status: input.status,
      seats: input.seats,
      renewsAt: input.renewsAt,
    },
  });
  await audit(actorId, "plan_change", "subscription", userId, {
    plan: subscription.plan,
    status: subscription.status,
    seats: subscription.seats,
  });
  return {
    plan: subscription.plan,
    status: subscription.status,
    seats: subscription.seats,
    renewsAt: subscription.renewsAt?.toISOString() ?? null,
  };
}

export async function deleteUser(actorId: string, userId: string) {
  const target = await requireUser(userId);
  if (target.id === actorId) {
    throw new AppError(400, "You cannot delete your own account", "SELF_DELETE");
  }
  if (target.role === "admin" && (await adminCount()) <= 1) {
    throw new AppError(400, "Cannot delete the last admin", "LAST_ADMIN");
  }
  await prisma.$transaction(async (tx) => {
    const projects = await tx.project.findMany({ where: { ownerId: userId }, select: { id: true } });
    const projectIds = projects.map((p) => p.id);
    const jobs = await tx.generationJob.findMany({
      where: { projectId: { in: projectIds } },
      select: { id: true },
    });
    const jobIds = jobs.map((j) => j.id);
    const candidates = await tx.candidate.findMany({
      where: { jobId: { in: jobIds } },
      select: { id: true },
    });
    const candidateIds = candidates.map((c) => c.id);
    await tx.complianceViolation.deleteMany({ where: { candidateId: { in: candidateIds } } });
    await tx.room.deleteMany({ where: { candidateId: { in: candidateIds } } });
    await tx.candidate.deleteMany({ where: { jobId: { in: jobIds } } });
    await tx.generationJob.deleteMany({ where: { projectId: { in: projectIds } } });
    await tx.editHistory.deleteMany({ where: { projectId: { in: projectIds } } });
    await tx.exportRecord.deleteMany({ where: { projectId: { in: projectIds } } });
    await tx.subscription.deleteMany({ where: { userId } });
    await tx.project.deleteMany({ where: { ownerId: userId } });
    await tx.user.delete({ where: { id: userId } });
  });
  await audit(actorId, "user_delete", "user", userId, { email: target.email });
}

export async function listUserProjects(userId: string) {
  await requireUser(userId);
  const projects = await prisma.project.findMany({
    where: { ownerId: userId },
    orderBy: { createdAt: "desc" },
    select: {
      id: true,
      name: true,
      status: true,
      jurisdiction: true,
      createdAt: true,
      _count: { select: { generationJobs: true } },
    },
  });
  return projects.map((p) => ({
    id: p.id,
    name: p.name,
    status: p.status,
    jurisdiction: p.jurisdiction,
    jobCount: p._count.generationJobs,
    createdAt: p.createdAt.toISOString(),
  }));
}

export async function listAuditLog(limit = 100) {
  const entries = await prisma.auditLog.findMany({
    orderBy: { createdAt: "desc" },
    take: Math.min(limit, 500),
  });
  const actorIds = [...new Set(entries.map((e) => e.actorId))];
  const actors = await prisma.user.findMany({
    where: { id: { in: actorIds } },
    select: { id: true, email: true },
  });
  const actorMap = new Map(actors.map((a) => [a.id, a.email]));
  return entries.map((e) => ({
    id: e.id,
    actor: actorMap.get(e.actorId) ?? e.actorId,
    action: e.action,
    targetType: e.targetType,
    targetId: e.targetId,
    metadata: e.metadata,
    createdAt: e.createdAt.toISOString(),
  }));
}
