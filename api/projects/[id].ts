import { z } from "zod";
import { validateBody } from "../_lib/validate";
import { requireAuth, checkRole } from "../_lib/auth";
import { handleError } from "../_lib/errors";
import { getProject, updateProject, deleteProject } from "../../apps/api/src/services/projects";

const schema = z.object({
  name: z.string().min(1).optional(),
  description: z.string().optional(),
  jurisdiction: z.string().min(1).optional(),
  plotWidth: z.number().positive().optional(),
  plotDepth: z.number().positive().optional(),
  plotUnit: z.enum(["m", "ft"]).optional(),
  orientation: z.number().optional(),
  status: z.string().optional(),
});

export default async function handler(req: any, res: any) {
  try {
    const user = await requireAuth(req, res);
    if (!user) return;

    const { id } = req.query;

    if (req.method === "GET") {
      const project = await getProject(id, user.id);
      res.json(project);
      return;
    }

    if (req.method === "PATCH") {
      const validation = validateBody(schema, req.body);
      if (validation.error) {
        res.status(400).json(validation);
        return;
      }
      const project = await updateProject(id, user.id, validation.data as any);
      res.json(project);
      return;
    }

    if (req.method === "DELETE") {
      await deleteProject(id, user.id);
      res.status(204).end();
      return;
    }

    res.status(405).json({ error: "Method not allowed" });
  } catch (err) {
    handleError(err, res);
  }
}
