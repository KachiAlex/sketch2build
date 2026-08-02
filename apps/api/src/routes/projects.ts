import { Router } from "express";
import { z } from "zod";
import { validateBody } from "../middleware/validate";
import { authenticate, AuthenticatedRequest, requireRole } from "../middleware/auth";
import { createProject, listProjectsByOwner, getProject, updateProject, deleteProject } from "../services/projects";
import { handleError } from "../lib/errors";

const router = Router();

const projectSchema = z.object({
  name: z.string().min(1),
  description: z.string().optional(),
  jurisdiction: z.string().min(1),
  plotWidth: z.number().positive().optional(),
  plotDepth: z.number().positive().optional(),
  plotUnit: z.enum(["m", "ft"]).optional(),
  orientation: z.number().optional(),
});

const updateProjectSchema = projectSchema.partial();

router.post(
  "/",
  authenticate,
  validateBody(projectSchema),
  async (req: AuthenticatedRequest, res) => {
    try {
      const project = await createProject({ ownerId: req.user!.id, ...req.body });
      res.status(201).json(project);
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
      const projects = await listProjectsByOwner(req.user!.id);
      res.json({ projects });
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
      const project = await getProject(req.params.id, req.user!.id);
      res.json(project);
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

router.patch(
  "/:id",
  authenticate,
  validateBody(updateProjectSchema),
  async (req: AuthenticatedRequest, res) => {
    try {
      const project = await updateProject(req.params.id, req.user!.id, req.body);
      res.json(project);
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

router.delete(
  "/:id",
  authenticate,
  requireRole("architect", "admin"),
  async (req: AuthenticatedRequest, res) => {
    try {
      await deleteProject(req.params.id, req.user!.id);
      res.status(204).send();
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

export default router;
