import { Router } from "express";
import { z } from "zod";
import { authenticate, AuthenticatedRequest, requireRole } from "../middleware/auth";
import { validateBody } from "../middleware/validate";
import {
  ROLES,
  PLANS,
  SUBSCRIPTION_STATUSES,
  getAdminStats,
  listUsers,
  getUserDetail,
  setUserRole,
  setUserStatus,
  setUserSubscription,
  deleteUser,
} from "../services/admin";
import { handleError } from "../lib/errors";

const router = Router();

router.use(authenticate, requireRole("admin"));

const roleSchema = z.object({ role: z.enum(ROLES) });
const statusSchema = z.object({ status: z.enum(["active", "suspended"]) });
const subscriptionSchema = z.object({
  plan: z.enum(PLANS).optional(),
  status: z.enum(SUBSCRIPTION_STATUSES).optional(),
  seats: z.number().int().min(1).max(100).optional(),
  renewsAt: z.string().datetime().nullable().optional(),
});

router.get("/stats", async (_req: AuthenticatedRequest, res) => {
  try {
    res.json(await getAdminStats());
  } catch (err) {
    const { statusCode, body } = handleError(err);
    res.status(statusCode).json(body);
  }
});

router.get("/users", async (req: AuthenticatedRequest, res) => {
  try {
    const page = Math.max(1, parseInt(String(req.query.page ?? "1"), 10) || 1);
    const limit = Math.min(100, Math.max(1, parseInt(String(req.query.limit ?? "20"), 10) || 20));
    const q = typeof req.query.q === "string" && req.query.q.trim() ? req.query.q.trim() : undefined;
    res.json(await listUsers({ q, page, limit }));
  } catch (err) {
    const { statusCode, body } = handleError(err);
    res.status(statusCode).json(body);
  }
});

router.get("/users/:id", async (req: AuthenticatedRequest, res) => {
  try {
    res.json(await getUserDetail(req.params.id));
  } catch (err) {
    const { statusCode, body } = handleError(err);
    res.status(statusCode).json(body);
  }
});

router.patch("/users/:id/role", validateBody(roleSchema), async (req: AuthenticatedRequest, res) => {
  try {
    res.json(await setUserRole(req.user!.id, req.params.id, req.body.role));
  } catch (err) {
    const { statusCode, body } = handleError(err);
    res.status(statusCode).json(body);
  }
});

router.patch("/users/:id/status", validateBody(statusSchema), async (req: AuthenticatedRequest, res) => {
  try {
    res.json(await setUserStatus(req.user!.id, req.params.id, req.body.status));
  } catch (err) {
    const { statusCode, body } = handleError(err);
    res.status(statusCode).json(body);
  }
});

router.patch(
  "/users/:id/subscription",
  validateBody(subscriptionSchema),
  async (req: AuthenticatedRequest, res) => {
    try {
      const input = {
        ...req.body,
        renewsAt:
          req.body.renewsAt === undefined ? undefined : req.body.renewsAt ? new Date(req.body.renewsAt) : null,
      };
      res.json(await setUserSubscription(req.params.id, input));
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

router.delete("/users/:id", async (req: AuthenticatedRequest, res) => {
  try {
    await deleteUser(req.user!.id, req.params.id);
    res.status(204).send();
  } catch (err) {
    const { statusCode, body } = handleError(err);
    res.status(statusCode).json(body);
  }
});

export default router;
