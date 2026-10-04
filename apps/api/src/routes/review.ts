import { Router } from "express";
import { z } from "zod";
import { authenticate, AuthenticatedRequest, requireRole } from "../middleware/auth";
import { validateBody } from "../middleware/validate";
import {
  getCandidateById,
  updateCandidateGeometry,
  revertCandidateToHistory,
  finalizeJobWithReview,
} from "../services/jobs";
import { validateCandidate } from "../services/compliance";
import { prisma } from "../lib/prisma";
import { handleError, AppError } from "../lib/errors";

const router = Router();

async function assertCandidateAccess(candidateId: string, userId: string, role: string) {
  const candidate = await getCandidateById(candidateId);
  if (!candidate) {
    throw new AppError(404, "Candidate not found", "CANDIDATE_NOT_FOUND");
  }
  if (candidate.job.project.ownerId !== userId && role !== "admin") {
    throw new AppError(403, "Forbidden", "FORBIDDEN");
  }
  return candidate;
}

const geometrySchema = z.object({
  rooms: z.array(
    z.object({
      id: z.string().uuid(),
      type: z.string().optional(),
      label: z.string().optional(),
      area: z.number(),
      boundaryGeometry: z.array(z.array(z.number())).or(z.record(z.unknown())),
    })
  ),
});

router.get(
  "/candidates/:candidateId",
  authenticate,
  async (req: AuthenticatedRequest, res) => {
    try {
      const candidate = await assertCandidateAccess(
        req.params.candidateId,
        req.user!.id,
        req.user!.role
      );
      res.json(candidate);
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

router.patch(
  "/candidates/:candidateId/geometry",
  authenticate,
  requireRole("architect", "drafter", "admin"),
  validateBody(geometrySchema),
  async (req: AuthenticatedRequest, res) => {
    try {
      await assertCandidateAccess(req.params.candidateId, req.user!.id, req.user!.role);
      await updateCandidateGeometry(
        req.params.candidateId,
        req.body.rooms,
        req.user!.id
      );
      // Re-run compliance validation automatically after any edit.
      await validateCandidate(req.params.candidateId);
      const updated = await getCandidateById(req.params.candidateId);
      res.json(updated);
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

router.post(
  "/candidates/:candidateId/revert",
  authenticate,
  requireRole("architect", "drafter", "admin"),
  validateBody(z.object({ historyId: z.string().uuid() })),
  async (req: AuthenticatedRequest, res) => {
    try {
      await assertCandidateAccess(req.params.candidateId, req.user!.id, req.user!.role);
      await revertCandidateToHistory(
        req.params.candidateId,
        req.body.historyId,
        req.user!.id
      );
      await validateCandidate(req.params.candidateId);
      const updated = await getCandidateById(req.params.candidateId);
      res.json(updated);
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

router.get(
  "/candidates/:candidateId/history",
  authenticate,
  async (req: AuthenticatedRequest, res) => {
    try {
      await assertCandidateAccess(req.params.candidateId, req.user!.id, req.user!.role);
      const history = await prisma.editHistory.findMany({
        where: { previousStateReference: req.params.candidateId },
        orderBy: { timestamp: "desc" },
      });
      res.json({ history });
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

router.post(
  "/jobs/:jobId/finalize",
  authenticate,
  requireRole("architect", "admin"),
  async (req: AuthenticatedRequest, res) => {
    try {
      const jobForAccess = await prisma.generationJob.findUnique({
        where: { id: req.params.jobId },
        include: { project: true },
      });
      if (!jobForAccess) {
        throw new AppError(404, "Job not found", "JOB_NOT_FOUND");
      }
      if (jobForAccess.project.ownerId !== req.user!.id && req.user!.role !== "admin") {
        throw new AppError(403, "Forbidden", "FORBIDDEN");
      }
      const job = await finalizeJobWithReview(req.params.jobId, req.user!.name);
      res.json(job);
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

export default router;
