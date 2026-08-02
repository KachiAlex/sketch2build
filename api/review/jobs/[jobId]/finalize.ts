import { requireAuth, checkRole } from "../../../_lib/auth";
import { handleError } from "../../../_lib/errors";
import { finalizeJobWithReview } from "../../../../apps/api/src/services/jobs";

export default async function handler(req: any, res: any) {
  try {
    const user = await requireAuth(req, res);
    if (!user) return;
    checkRole(user, res, "architect", "admin");

    if (req.method !== "POST") {
      res.status(405).json({ error: "Method not allowed" });
      return;
    }

    const { jobId } = req.query;
    const result = await finalizeJobWithReview(jobId, user.name);
    res.json(result);
  } catch (err) {
    handleError(err, res);
  }
}
