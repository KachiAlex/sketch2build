import { Router } from "express";
import { authenticate, AuthenticatedRequest } from "../middleware/auth";
import { handleError } from "../lib/errors";
import { prisma } from "../lib/prisma";
import { getUserPlan, PLAN_QUOTAS } from "../services/entitlements";

const router = Router();

// Current plan + live usage, so the frontend can show quotas honestly.
router.get("/entitlements", authenticate, async (req: AuthenticatedRequest, res) => {
  try {
    const plan = await getUserPlan(req.user!.id);
    const monthStart = new Date();
    monthStart.setDate(1);
    monthStart.setHours(0, 0, 0, 0);
    const [jobsUsed, projectsUsed] = await Promise.all([
      prisma.generationJob.count({
        where: { project: { ownerId: req.user!.id }, createdAt: { gte: monthStart } },
      }),
      prisma.project.count({ where: { ownerId: req.user!.id } }),
    ]);
    const quotas = PLAN_QUOTAS[plan];
    const toLimit = (n: number) => (Number.isFinite(n) ? n : null);
    res.json({
      plan,
      jobsPerMonth: toLimit(quotas.jobsPerMonth),
      jobsUsed,
      projectsAllowed: toLimit(quotas.projects),
      projectsUsed,
      exportFormats: quotas.exportFormats,
      renewsAt:
        (await prisma.subscription.findUnique({
          where: { userId: req.user!.id },
          select: { renewsAt: true },
        }))?.renewsAt ?? null,
    });
  } catch (err) {
    const { statusCode, body } = handleError(err);
    res.status(statusCode).json(body);
  }
});

export default router;
