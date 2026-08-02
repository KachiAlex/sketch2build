import { z } from "zod";
import { validateBody } from "./_lib/validate";
import { requireAuth } from "./_lib/auth";
import { handleError } from "./_lib/errors";
import { prisma } from "../apps/api/src/lib/prisma";
import { AppError } from "../apps/api/src/lib/errors";
import { uploadFile } from "../apps/api/src/lib/storage";

const schema = z.object({
  projectId: z.string().uuid(),
  fileData: z.string().min(1),
  fileType: z.enum(["image/jpeg", "image/png", "application/pdf"]),
  referenceLength: z.number().positive(),
  unit: z.enum(["m", "ft", "cm", "mm"]),
});

export default async function handler(req: any, res: any) {
  try {
    const user = await requireAuth(req, res);
    if (!user) return;

    if (req.method !== "POST") {
      res.status(405).json({ error: "Method not allowed" });
      return;
    }

    const validation = validateBody(schema, req.body);
    if (validation.error) {
      res.status(400).json(validation);
      return;
    }

    const { projectId, fileData, fileType, referenceLength, unit } = validation.data as any;

    const project = await prisma.project.findFirst({
      where: { id: projectId, ownerId: user.id },
    });
    if (!project) {
      throw new AppError(404, "Project not found", "PROJECT_NOT_FOUND");
    }

    const buffer = Buffer.from(fileData, "base64");
    const extension = fileType === "application/pdf" ? "pdf" : "jpg";
    const { key } = await uploadFile(buffer, fileType, extension, "sketches");

    const job = await prisma.generationJob.create({
      data: {
        projectId,
        sourceType: "sketch",
        status: "queued",
        inputReference: key,
      },
    });

    res.status(201).json({ job, referenceLength, unit });
  } catch (err) {
    handleError(err, res);
  }
}
