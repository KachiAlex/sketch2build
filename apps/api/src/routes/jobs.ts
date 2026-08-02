import { Router } from "express";
import { z } from "zod";
import { authenticate, AuthenticatedRequest, requireRole } from "../middleware/auth";
import { validateBody } from "../middleware/validate";
import {
  createGenerationJob,
  getGenerationJob,
  listGenerationJobsByProject,
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
      res.status(201).json(job);
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

router.get(
  "/:id",
  authenticate,
  async (req: AuthenticatedRequest, res) => {
    try {
      const job = await getGenerationJob(req.params.id);
      if (job.projectId !== req.user!.id) {
        // In a real system, check project ownership. Here we reuse getProject for ownership.
        await getProject(job.projectId, req.user!.id);
      }
      res.json(job);
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
