import { prisma } from "../lib/prisma";
import { AppError } from "../lib/errors";

export type Plan = "free" | "pro" | "studio";

interface Quotas {
  jobsPerMonth: number;
  projects: number;
  exportFormats: string[];
}

export const PLAN_QUOTAS: Record<Plan, Quotas> = {
  free: {
    jobsPerMonth: 5,
    projects: 2,
    exportFormats: ["dxf", "png", "pdf"],
  },
  pro: {
    jobsPerMonth: 100,
    projects: 25,
    exportFormats: ["dxf", "png", "pdf", "ifc", "glb", "3d-massing"],
  },
  studio: {
    jobsPerMonth: Number.POSITIVE_INFINITY,
    projects: Number.POSITIVE_INFINITY,
    exportFormats: ["dxf", "png", "pdf", "ifc", "glb", "3d-massing"],
  },
};

export async function getUserPlan(userId: string): Promise<Plan> {
  const subscription = await prisma.subscription.findUnique({ where: { userId } });
  const plan = subscription?.plan;
  return plan === "pro" || plan === "studio" ? plan : "free";
}

export async function assertJobQuota(userId: string) {
  const plan = await getUserPlan(userId);
  const quota = PLAN_QUOTAS[plan].jobsPerMonth;
  const monthStart = new Date();
  monthStart.setDate(1);
  monthStart.setHours(0, 0, 0, 0);
  const used = await prisma.generationJob.count({
    where: { project: { ownerId: userId }, createdAt: { gte: monthStart } },
  });
  if (used >= quota) {
    throw new AppError(
      403,
      `Plan limit reached: ${quota} generations per month on the ${plan} plan. Upgrade to continue.`,
      "QUOTA_EXCEEDED"
    );
  }
}

export async function assertProjectQuota(userId: string) {
  const plan = await getUserPlan(userId);
  const quota = PLAN_QUOTAS[plan].projects;
  const used = await prisma.project.count({ where: { ownerId: userId } });
  if (used >= quota) {
    throw new AppError(
      403,
      `Plan limit reached: ${quota} projects on the ${plan} plan. Upgrade to continue.`,
      "QUOTA_EXCEEDED"
    );
  }
}

export async function assertExportAllowed(userId: string, format: string) {
  const plan = await getUserPlan(userId);
  if (!PLAN_QUOTAS[plan].exportFormats.includes(format)) {
    throw new AppError(
      403,
      `The ${format} export requires a pro or studio plan. Current plan: ${plan}.`,
      "PLAN_REQUIRED"
    );
  }
}
