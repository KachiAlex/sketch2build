import { requireAuth } from "../_lib/auth";
import { handleError } from "../_lib/errors";
import { getGenerationJob } from "../../apps/api/src/services/jobs";

export default async function handler(req: any, res: any) {
  try {
    const user = await requireAuth(req, res);
    if (!user) return;

    if (req.method === "GET") {
      const job = await getGenerationJob(req.query.id);
      res.json(job);
      return;
    }

    res.status(405).json({ error: "Method not allowed" });
  } catch (err) {
    handleError(err, res);
  }
}
