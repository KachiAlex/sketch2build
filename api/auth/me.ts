import { VercelRequest, VercelResponse } from "@vercel/node";
import { requireAuth } from "../_lib/auth";
import { handleError } from "../_lib/errors";
import { getUserById } from "../../apps/api/src/services/auth";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== "GET") {
    res.status(405).json({ error: "Method not allowed" });
    return;
  }
  try {
    const user = await requireAuth(req, res);
    if (!user) return;
    const data = await getUserById(user.id);
    res.json({ user: data });
  } catch (err) {
    handleError(err, res);
  }
}
