import jwt from "jsonwebtoken";
import { prisma } from "../../apps/api/src/lib/prisma";
import { JWT_SECRET } from "../../apps/api/src/lib/config";
import { AppError } from "../../apps/api/src/lib/errors";

export async function getUserFromRequest(req: any) {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith("Bearer ")) return null;
  const token = authHeader.split(" ")[1];
  try {
    const payload = jwt.verify(token, JWT_SECRET) as { userId: string };
    return await prisma.user.findUnique({ where: { id: payload.userId } });
  } catch {
    return null;
  }
}

export async function requireAuth(req: any, res: any) {
  const user = await getUserFromRequest(req);
  if (!user) {
    res.status(401).json({ error: "Unauthorized" });
    return null;
  }
  return user;
}

export function checkRole(user: any, res: any, ...roles: string[]) {
  if (!roles.includes(user.role)) {
    throw new AppError(403, "Forbidden", "FORBIDDEN");
  }
}
