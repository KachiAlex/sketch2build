import { requireAuth } from "../../_lib/auth";
import { handleError } from "../../_lib/errors";
import { listGenerationJobsByProject } from "../../../apps/api/src/services/jobs";
import { getProject } from "../../../apps/api/src/services/projects";

export default async function handler(req: any, res: any) {
  try {
    const user = await requireAuth(req, res);
    if (!user) return;

    if (req.method === "GET") {
      const { projectId } = req.query;
      await getProject(projectId, user.id);
      const jobs = await listGenerationJobsByProject(projectId);
      res.json({ jobs });
      return;
    }

    res.status(405).json({ error: "Method not allowed" });
  } catch (err) {
    handleError(err, res);
  }
}
