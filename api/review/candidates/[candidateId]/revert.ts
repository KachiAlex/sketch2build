import { z } from "zod";
import { validateBody } from "../../../_lib/validate";
import { requireAuth, checkRole } from "../../../_lib/auth";
import { handleError } from "../../../_lib/errors";
import { revertCandidateToHistory } from "../../../../apps/api/src/services/jobs";

const schema = z.object({ historyId: z.string().uuid() });

export default async function handler(req: any, res: any) {
  try {
    const user = await requireAuth(req, res);
    if (!user) return;
    checkRole(user, res, "architect", "drafter", "admin");

    if (req.method !== "POST") {
      res.status(405).json({ error: "Method not allowed" });
      return;
    }

    const validation = validateBody(schema, req.body);
    if (validation.error) {
      res.status(400).json(validation);
      return;
    }

    const { candidateId } = req.query;
    const updated = await revertCandidateToHistory(candidateId, validation.data.historyId, user.id);
    res.json(updated);
  } catch (err) {
    handleError(err, res);
  }
}
