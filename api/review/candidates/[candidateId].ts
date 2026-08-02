import { requireAuth } from "../../_lib/auth";
import { handleError } from "../../_lib/errors";
import { getCandidateById } from "../../../apps/api/src/services/jobs";

export default async function handler(req: any, res: any) {
  try {
    const user = await requireAuth(req, res);
    if (!user) return;

    if (req.method === "GET") {
      const candidate = await getCandidateById(req.query.candidateId);
      if (!candidate) {
        res.status(404).json({ error: "Candidate not found" });
        return;
      }
      res.json(candidate);
      return;
    }

    res.status(405).json({ error: "Method not allowed" });
  } catch (err) {
    handleError(err, res);
  }
}
