import { z } from "zod";
import { validateBody } from "../../../_lib/validate";
import { requireAuth, checkRole } from "../../../_lib/auth";
import { handleError } from "../../../_lib/errors";
import { updateCandidateGeometry } from "../../../../apps/api/src/services/jobs";
import { validateCandidate } from "../../../../apps/api/src/services/compliance";
import { getCandidateById } from "../../../../apps/api/src/services/jobs";

const schema = z.object({
  rooms: z.array(
    z.object({
      id: z.string().uuid(),
      type: z.string().optional(),
      label: z.string().optional(),
      area: z.number(),
      boundaryGeometry: z.array(z.array(z.number())).or(z.record(z.unknown())),
    })
  ),
});

export default async function handler(req: any, res: any) {
  try {
    const user = await requireAuth(req, res);
    if (!user) return;
    checkRole(user, res, "architect", "drafter", "admin");

    if (req.method !== "PATCH") {
      res.status(405).json({ error: "Method not allowed" });
      return;
    }

    const validation = validateBody(schema, req.body);
    if (validation.error) {
      res.status(400).json(validation);
      return;
    }

    const { candidateId } = req.query;
    await updateCandidateGeometry(candidateId, validation.data.rooms, user.id);
    await validateCandidate(candidateId);
    const updated = await getCandidateById(candidateId);
    res.json(updated);
  } catch (err) {
    handleError(err, res);
  }
}
