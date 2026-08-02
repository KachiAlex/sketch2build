import { Router } from "express";
import { z } from "zod";
import { authenticate, AuthenticatedRequest, requireRole } from "../middleware/auth";
import { validateBody } from "../middleware/validate";
import {
  validateCandidate,
  getActiveRules,
  createRule,
  updateRule,
  deleteRule,
} from "../services/compliance";
import { handleError } from "../lib/errors";

const router = Router();

const validateSchema = z.object({
  candidateId: z.string().uuid(),
});

const ruleSchema = z.object({
  jurisdiction: z.string().min(1),
  ruleType: z.string().min(1),
  parameters: z.record(z.unknown()),
  version: z.string().min(1),
  effectiveDate: z.coerce.date(),
});

router.post(
  "/validate",
  authenticate,
  validateBody(validateSchema),
  async (req: AuthenticatedRequest, res) => {
    try {
      const result = await validateCandidate(req.body.candidateId);
      res.json(result);
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

router.get(
  "/rules",
  authenticate,
  requireRole("architect", "admin"),
  async (req: AuthenticatedRequest, res) => {
    try {
      const jurisdiction = typeof req.query.jurisdiction === "string" ? req.query.jurisdiction : "Nigeria";
      const rules = await getActiveRules(jurisdiction);
      res.json({ rules });
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

router.post(
  "/rules",
  authenticate,
  requireRole("admin"),
  validateBody(ruleSchema),
  async (req: AuthenticatedRequest, res) => {
    try {
      const rule = await createRule(req.body);
      res.status(201).json(rule);
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

router.patch(
  "/rules/:id",
  authenticate,
  requireRole("admin"),
  validateBody(ruleSchema.partial()),
  async (req: AuthenticatedRequest, res) => {
    try {
      const rule = await updateRule(req.params.id, req.body);
      res.json(rule);
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

router.delete(
  "/rules/:id",
  authenticate,
  requireRole("admin"),
  async (req: AuthenticatedRequest, res) => {
    try {
      await deleteRule(req.params.id);
      res.status(204).send();
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

export default router;
