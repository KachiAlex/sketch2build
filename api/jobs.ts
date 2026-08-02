import { z } from "zod";
import { validateBody } from "./_lib/validate";
import { requireAuth } from "./_lib/auth";
import { handleError } from "./_lib/errors";
import { prisma } from "../apps/api/src/lib/prisma";
import { getProject } from "../apps/api/src/services/projects";

const schema = z.object({
  projectId: z.string().uuid(),
  sourceType: z.enum(["sketch", "prompt"]),
  inputReference: z.string().optional(),
  payload: z.record(z.unknown()).optional(),
});

export default async function handler(req: any, res: any) {
  try {
    const user = await requireAuth(req, res);
    if (!user) return;

    if (req.method === "POST") {
      const validation = validateBody(schema, req.body);
      if (validation.error) {
        res.status(400).json(validation);
        return;
      }
      const { projectId, sourceType, inputReference, payload } = validation.data as any;
      await getProject(projectId, user.id);
      const job = await prisma.generationJob.create({
        data: {
          projectId,
          sourceType,
          status: "queued",
          inputReference,
        },
      });
      res.status(201).json({ ...job, payload });
      return;
    }

    res.status(405).json({ error: "Method not allowed" });
  } catch (err) {
    handleError(err, res);
  }
}
