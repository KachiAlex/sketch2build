import { Router } from "express";
import { z } from "zod";
import { authenticate, AuthenticatedRequest } from "../middleware/auth";
import { validateBody } from "../middleware/validate";
import { prisma } from "../lib/prisma";
import { AppError, handleError } from "../lib/errors";

const router = Router();

const createSchema = z.object({ name: z.string().min(2).max(80) });
const inviteSchema = z.object({ email: z.string().email() });

router.post(
  "/",
  authenticate,
  validateBody(createSchema),
  async (req: AuthenticatedRequest, res) => {
    try {
      const existing = await prisma.organization.findUnique({ where: { name: req.body.name } });
      if (existing) {
        throw new AppError(409, "Organization name is taken", "ORG_EXISTS");
      }
      const user = await prisma.user.findUnique({ where: { id: req.user!.id } });
      if (user?.organizationId) {
        throw new AppError(400, "Leave your current organization before creating one", "ALREADY_IN_ORG");
      }
      const org = await prisma.organization.create({
        data: { name: req.body.name, ownerId: req.user!.id },
      });
      await prisma.user.update({
        where: { id: req.user!.id },
        data: { organizationId: org.id },
      });
      res.status(201).json({ organization: org });
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

router.get("/mine", authenticate, async (req: AuthenticatedRequest, res) => {
  try {
    const user = await prisma.user.findUnique({ where: { id: req.user!.id } });
    if (!user?.organizationId) {
      res.json({ organization: null });
      return;
    }
    const org = await prisma.organization.findUnique({
      where: { id: user.organizationId },
      include: {
        members: {
          select: {
            id: true,
            name: true,
            email: true,
            role: true,
            projects: { select: { id: true, name: true, status: true, createdAt: true } },
          },
        },
      },
    });
    res.json({
      organization: org && {
        id: org.id,
        name: org.name,
        ownerId: org.ownerId,
        members: org.members.map((m) => ({
          id: m.id,
          name: m.name,
          email: m.email,
          role: m.role,
          projects: m.projects,
        })),
      },
    });
  } catch (err) {
    const { statusCode, body } = handleError(err);
    res.status(statusCode).json(body);
  }
});

router.post(
  "/invite",
  authenticate,
  validateBody(inviteSchema),
  async (req: AuthenticatedRequest, res) => {
    try {
      const me = await prisma.user.findUnique({ where: { id: req.user!.id } });
      if (!me?.organizationId) {
        throw new AppError(400, "Create an organization first", "NO_ORG");
      }
      const org = await prisma.organization.findUnique({ where: { id: me.organizationId } });
      if (org?.ownerId !== me.id) {
        throw new AppError(403, "Only the organization owner can invite members", "NOT_ORG_OWNER");
      }
      const target = await prisma.user.findUnique({ where: { email: req.body.email } });
      if (!target) {
        throw new AppError(404, "No account with that email", "USER_NOT_FOUND");
      }
      if (target.organizationId === org.id) {
        throw new AppError(400, "User is already a member", "ALREADY_MEMBER");
      }
      await prisma.user.update({
        where: { id: target.id },
        data: { organizationId: org.id },
      });
      res.json({ ok: true });
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

router.post("/leave", authenticate, async (req: AuthenticatedRequest, res) => {
  try {
    const me = await prisma.user.findUnique({ where: { id: req.user!.id } });
    const org = me?.organizationId
      ? await prisma.organization.findUnique({ where: { id: me.organizationId } })
      : null;
    if (org?.ownerId === me?.id) {
      throw new AppError(
        400,
        "Transfer ownership or delete the organization before leaving",
        "OWNER_CANNOT_LEAVE"
      );
    }
    await prisma.user.update({
      where: { id: req.user!.id },
      data: { organizationId: null },
    });
    res.json({ ok: true });
  } catch (err) {
    const { statusCode, body } = handleError(err);
    res.status(statusCode).json(body);
  }
});

export default router;
