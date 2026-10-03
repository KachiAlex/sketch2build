import { Router } from "express";
import { z } from "zod";
import { authenticate, AuthenticatedRequest } from "../middleware/auth";
import { validateBody } from "../middleware/validate";
import { getProject } from "../services/projects";
import { uploadFile } from "../lib/storage";
import { createGenerationJob } from "../services/jobs";
import { handleError, AppError } from "../lib/errors";

const router = Router();

const mimeByType: Record<string, string> = {
  "image/jpeg": "jpg",
  "image/png": "png",
  "application/pdf": "pdf",
};

const sketchSchema = z.object({
  projectId: z.string().uuid(),
  fileData: z.string().min(1),
  fileType: z.enum(["image/jpeg", "image/png", "application/pdf"]),
  referenceLength: z.number().positive(),
  referencePixels: z.number().positive().optional(),
  unit: z.enum(["m", "ft", "cm", "mm"]),
});

router.post(
  "/",
  authenticate,
  validateBody(sketchSchema),
  async (req: AuthenticatedRequest, res) => {
    try {
      const { projectId, fileData, fileType, referenceLength, referencePixels, unit } = req.body;

      const buffer = Buffer.from(fileData, "base64");
      if (!buffer.length) {
        throw new AppError(400, "Sketch file is required", "MISSING_FILE");
      }
      if (buffer.length > 25 * 1024 * 1024) {
        throw new AppError(400, "Sketch file exceeds 25 MB limit", "FILE_TOO_LARGE");
      }

      const project = await getProject(projectId, req.user!.id);
      const { key } = await uploadFile(buffer, fileType, mimeByType[fileType], "sketches");

      const job = await createGenerationJob({
        projectId: project.id,
        sourceType: "sketch",
        inputReference: key,
        payload: {
          referenceLength,
          referencePixels,
          unit,
        },
      });

      res.status(201).json({ job });
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

export default router;
