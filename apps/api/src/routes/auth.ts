import { Router } from "express";
import { z } from "zod";
import { validateBody } from "../middleware/validate";
import { authenticate, AuthenticatedRequest } from "../middleware/auth";
import { authLimiter } from "../middleware/rateLimit";
import { registerUser, loginUser, getUserById } from "../services/auth";
import { handleError } from "../lib/errors";

const router = Router();

const registerSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  name: z.string().min(1),
  role: z.enum(["architect", "drafter", "developer", "homeowner", "admin"]),
  organization: z.string().optional(),
});

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

router.post(
  "/register",
  authLimiter,
  validateBody(registerSchema),
  async (req, res) => {
    try {
      const result = await registerUser(req.body);
      res.status(201).json(result);
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

router.post(
  "/login",
  authLimiter,
  validateBody(loginSchema),
  async (req, res) => {
    try {
      const result = await loginUser(req.body);
      res.json(result);
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

router.get(
  "/me",
  authenticate,
  async (req: AuthenticatedRequest, res) => {
    try {
      const user = await getUserById(req.user!.id);
      res.json({ user });
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

export default router;
