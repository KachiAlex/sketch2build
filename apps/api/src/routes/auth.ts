import { Router } from "express";
import { z } from "zod";
import { validateBody } from "../middleware/validate";
import { authenticate, AuthenticatedRequest } from "../middleware/auth";
import { authLimiter } from "../middleware/rateLimit";
import {
  registerUser,
  loginUser,
  getUserById,
  changePassword,
  requestPasswordReset,
  resetPassword,
} from "../services/auth";
import { handleError } from "../lib/errors";

const router = Router();

const registerSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  name: z.string().min(1),
  role: z.enum(["architect", "drafter", "developer", "homeowner"]),
  organization: z.string().optional(),
});

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

const changePasswordSchema = z.object({
  currentPassword: z.string().min(1),
  newPassword: z.string().min(8),
});

const forgotPasswordSchema = z.object({ email: z.string().email() });
const resetPasswordSchema = z.object({
  token: z.string().min(1),
  newPassword: z.string().min(8),
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

router.post(
  "/forgot-password",
  authLimiter,
  validateBody(forgotPasswordSchema),
  async (req, res) => {
    try {
      await requestPasswordReset(req.body.email);
      res.json({ ok: true }); // always 200 — don't leak account existence
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

router.post(
  "/reset-password",
  authLimiter,
  validateBody(resetPasswordSchema),
  async (req, res) => {
    try {
      await resetPassword(req.body.token, req.body.newPassword);
      res.json({ ok: true });
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

router.post(
  "/change-password",
  authenticate,
  validateBody(changePasswordSchema),
  async (req: AuthenticatedRequest, res) => {
    try {
      await changePassword(req.user!.id, req.body.currentPassword, req.body.newPassword);
      res.json({ ok: true });
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
