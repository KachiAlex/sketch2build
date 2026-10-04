import { Router } from "express";
import { z } from "zod";
import { authenticate, AuthenticatedRequest, requireRole } from "../middleware/auth";
import { validateBody } from "../middleware/validate";
import {
  createGenerationJob,
  getGenerationJob,
  listGenerationJobsByProject,
  listRecentJobsForUser,
  finalizeJob,
} from "../services/jobs";
import { handleError } from "../lib/errors";
import { getProject } from "../services/projects";

const router = Router();

const createJobSchema = z.object({
  projectId: z.string().uuid(),
  sourceType: z.enum(["sketch", "prompt"]),
  inputReference: z.string().optional(),
  payload: z.record(z.unknown()).optional(),
});

router.post(
  "/",
  authenticate,
  validateBody(createJobSchema),
  async (req: AuthenticatedRequest, res) => {
    try {
      await getProject(req.body.projectId, req.user!.id);
      const job = await createGenerationJob(req.body);
      res.status(201).json({ job });
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

router.get(
  "/",
  authenticate,
  async (req: AuthenticatedRequest, res) => {
    try {
      const limit = Math.min(
        Math.max(parseInt(String(req.query.limit ?? "20"), 10) || 20, 1),
        100
      );
      const jobs = await listRecentJobsForUser(req.user!.id, limit);
      res.json({
        jobs: jobs.map((j) => ({
          id: j.id,
          status: JOB_STATUS_MAP[j.status] ?? j.status,
          rawStatus: j.status,
          inputType: j.sourceType,
          projectId: j.projectId,
          project: j.project,
          candidateCount: j.candidates.length,
          createdAt: j.createdAt,
        })),
      });
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

router.get(
  "/project/:projectId",
  authenticate,
  async (req: AuthenticatedRequest, res) => {
    try {
      await getProject(req.params.projectId, req.user!.id);
      const jobs = await listGenerationJobsByProject(req.params.projectId);
      res.json({ jobs });
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

const JOB_STATUS_MAP: Record<string, string> = {
  queued: "pending",
  processing: "processing",
  candidates_ready: "completed",
  under_review: "completed",
  finalized: "completed",
  failed: "failed",
};

const COMPLIANCE_STATUS_MAP: Record<string, string> = {
  passed: "pass",
  failed: "fail",
};

function serializeJobResult(job: Awaited<ReturnType<typeof getGenerationJob>>) {
  const candidates = [...(job.candidates ?? [])].sort((a, b) => a.rank - b.rank);
  return {
    job: {
      id: job.id,
      status: JOB_STATUS_MAP[job.status] ?? job.status,
      rawStatus: job.status,
      inputType: job.sourceType,
      errorMessage: job.errorMessage,
      createdAt: job.createdAt,
    },
    alternatives: candidates.map((c, i) => ({
      index: i,
      candidateId: c.id,
      score: Math.round((c.score ?? 0) * 1000) / 10,
      scoreRationale: c.scoreRationale,
      floor_plan: {
        plot: (c.planExtras as Record<string, unknown> | null)?.plot,
        doors: (c.planExtras as Record<string, unknown> | null)?.doors ?? [],
        windows: (c.planExtras as Record<string, unknown> | null)?.windows ?? [],
        unit: (c.planExtras as Record<string, unknown> | null)?.unit ?? "m",
        rooms: (c.rooms ?? []).map((r) => ({
          id: r.id,
          type: r.type,
          label: r.label,
          area: r.area,
          boundary: r.boundaryGeometry,
        })),
      },
      compliance: {
        status: COMPLIANCE_STATUS_MAP[c.complianceStatus] ?? "pending",
        violations: (c.complianceViolations ?? []).map((v) => ({
          ruleId: v.ruleId,
          message: v.message,
          severity: v.severity,
        })),
      },
    })),
  };
}

router.get(
  "/:id",
  authenticate,
  async (req: AuthenticatedRequest, res) => {
    try {
      const job = await getGenerationJob(req.params.id);
      await getProject(job.projectId, req.user!.id);
      res.json(serializeJobResult(job));
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

router.post(
  "/:id/finalize",
  authenticate,
  requireRole("architect", "admin"),
  async (req: AuthenticatedRequest, res) => {
    try {
      const job = await getGenerationJob(req.params.id);
      await getProject(job.projectId, req.user!.id);
      const finalized = await finalizeJob(req.params.id);
      res.json(finalized);
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

export default router;
