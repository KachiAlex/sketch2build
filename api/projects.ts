import { z } from "zod";
import { validateBody } from "./_lib/validate";
import { requireAuth, checkRole } from "./_lib/auth";
import { handleError } from "./_lib/errors";
import { createProject, listProjectsByOwner } from "../apps/api/src/services/projects";

const schema = z.object({
  name: z.string().min(1),
  description: z.string().optional(),
  jurisdiction: z.string().min(1),
  plotWidth: z.number().positive().optional(),
  plotDepth: z.number().positive().optional(),
  plotUnit: z.enum(["m", "ft"]).optional(),
  orientation: z.number().optional(),
});

export default async function handler(req: any, res: any) {
  try {
    const user = await requireAuth(req, res);
    if (!user) return;

    if (req.method === "GET") {
      const projects = await listProjectsByOwner(user.id);
      res.json({ projects });
      return;
    }

    if (req.method === "POST") {
      const validation = validateBody(schema, req.body);
      if (validation.error) {
        res.status(400).json(validation);
        return;
      }
      const project = await createProject({ ownerId: user.id, ...validation.data } as any);
      res.status(201).json(project);
      return;
    }

    res.status(405).json({ error: "Method not allowed" });
  } catch (err) {
    handleError(err, res);
  }
}
