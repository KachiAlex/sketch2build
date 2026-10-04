import bcrypt from "bcryptjs";
import crypto from "crypto";
import jwt from "jsonwebtoken";
import { prisma } from "../lib/prisma";
import { JWT_SECRET, JWT_EXPIRES_IN } from "../lib/config";
import { AppError } from "../lib/errors";
import { UserRole } from "@sketch2build/shared";

const SALT_ROUNDS = 10;

export interface RegisterInput {
  email: string;
  password: string;
  name: string;
  role: UserRole;
  organization?: string;
}

export interface LoginInput {
  email: string;
  password: string;
}

export function sanitizeUser(user: { id: string; email: string; name: string; role: string; status?: string; organization?: string | null }) {
  return {
    id: user.id,
    email: user.email,
    name: user.name,
    role: user.role,
    status: user.status ?? "active",
    organization: user.organization ?? undefined,
  };
}

export async function registerUser(input: RegisterInput) {
  const existing = await prisma.user.findUnique({ where: { email: input.email } });
  if (existing) {
    throw new AppError(409, "Email already registered", "EMAIL_EXISTS");
  }

  const passwordHash = await bcrypt.hash(input.password, SALT_ROUNDS);
  const user = await prisma.user.create({
    data: {
      email: input.email,
      name: input.name,
      role: input.role,
      organization: input.organization,
      passwordHash,
    },
  });

  const token = jwt.sign(
    { userId: user.id, email: user.email, role: user.role },
    JWT_SECRET,
    { expiresIn: JWT_EXPIRES_IN }
  );

  return { user: sanitizeUser(user), token };
}

export async function loginUser(input: LoginInput) {
  const user = await prisma.user.findUnique({ where: { email: input.email } });
  if (!user) {
    throw new AppError(401, "Invalid email or password", "INVALID_CREDENTIALS");
  }

  const valid = await bcrypt.compare(input.password, user.passwordHash);
  if (!valid) {
    throw new AppError(401, "Invalid email or password", "INVALID_CREDENTIALS");
  }
  if (user.status === "suspended") {
    throw new AppError(403, "Account suspended", "ACCOUNT_SUSPENDED");
  }

  const token = jwt.sign(
    { userId: user.id, email: user.email, role: user.role },
    JWT_SECRET,
    { expiresIn: JWT_EXPIRES_IN }
  );

  return { user: sanitizeUser(user), token };
}

export async function changePassword(userId: string, currentPassword: string, newPassword: string) {
  const user = await prisma.user.findUnique({ where: { id: userId } });
  if (!user) {
    throw new AppError(404, "User not found", "USER_NOT_FOUND");
  }
  const valid = await bcrypt.compare(currentPassword, user.passwordHash);
  if (!valid) {
    throw new AppError(400, "Current password is incorrect", "INVALID_PASSWORD");
  }
  const passwordHash = await bcrypt.hash(newPassword, SALT_ROUNDS);
  await prisma.user.update({ where: { id: userId }, data: { passwordHash } });
}

const RESET_TOKEN_TTL_MS = 60 * 60 * 1000; // 1 hour

export async function requestPasswordReset(email: string) {
  const user = await prisma.user.findUnique({ where: { email } });
  if (!user) {
    return; // don't leak whether the account exists
  }
  const token = crypto.randomBytes(32).toString("hex");
  await prisma.passwordResetToken.create({
    data: { userId: user.id, token, expiresAt: new Date(Date.now() + RESET_TOKEN_TTL_MS) },
  });
  const appUrl = process.env.APP_URL || "https://sketch2build-web.vercel.app";
  const resetUrl = `${appUrl}/reset-password?token=${token}`;
  await sendResetEmail(user.email, resetUrl);
}

async function sendResetEmail(email: string, resetUrl: string) {
  const apiKey = process.env.BREVO_API_KEY;
  if (!apiKey) {
    // No mail provider configured — log the link so reset still works in dev/ops.
    // eslint-disable-next-line no-console
    console.log(`[password-reset] ${email}: ${resetUrl}`);
    return;
  }
  try {
    await fetch("https://api.brevo.com/v3/smtp/email", {
      method: "POST",
      headers: { "api-key": apiKey, "Content-Type": "application/json" },
      body: JSON.stringify({
        sender: {
          email: process.env.BREVO_SENDER_EMAIL || "noreply@sketch2build.com",
          name: "Sketch2Build",
        },
        to: [{ email }],
        subject: "Reset your Sketch2Build password",
        htmlContent: `<p>You requested a password reset for your Sketch2Build account.</p><p><a href="${resetUrl}">Reset your password</a> — the link is valid for 1 hour.</p><p>If you didn't request this, ignore this email.</p>`,
      }),
    });
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error("[password-reset] email send failed:", err);
  }
}

export async function resetPassword(token: string, newPassword: string) {
  const record = await prisma.passwordResetToken.findUnique({ where: { token } });
  if (!record || record.usedAt || record.expiresAt < new Date()) {
    throw new AppError(400, "Invalid or expired reset token", "INVALID_RESET_TOKEN");
  }
  const passwordHash = await bcrypt.hash(newPassword, SALT_ROUNDS);
  await prisma.user.update({ where: { id: record.userId }, data: { passwordHash } });
  await prisma.passwordResetToken.update({
    where: { id: record.id },
    data: { usedAt: new Date() },
  });
}

export async function getUserById(id: string) {
  const user = await prisma.user.findUnique({ where: { id } });
  if (!user) {
    throw new AppError(404, "User not found", "USER_NOT_FOUND");
  }
  return sanitizeUser(user);
}
