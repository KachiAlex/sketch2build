import { Router } from "express";
import multer from "multer";
import { z } from "zod";
import { authenticate, AuthenticatedRequest } from "../middleware/auth";
import { getProject } from "../services/projects";
import { uploadFile } from "../lib/storage";
import { createGenerationJob } from "../services/jobs";
import { handleError, AppError } from "../lib/errors";

const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 25 * 1024 * 1024 } });

const allowedMimeTypes = ["image/jpeg", "image/png", "application/pdf"];

const sketchUploadSchema = z.object({
  referenceLength: z.coerce.number().positive(),
  unit: z.enum(["m", "ft", "cm", "mm"]),
});

const router = Router();

router.post(
  "/:projectId/sketch",
  authenticate,
  upload.single("file"),
  async (req: AuthenticatedRequest, res) => {
    try {
      if (!req.file) {
        throw new AppError(400, "Sketch file is required", "MISSING_FILE");
      }
      if (!allowedMimeTypes.includes(req.file.mimetype)) {
        throw new AppError(400, "Unsupported file type. Use JPEG, PNG, or PDF.", "INVALID_FILE_TYPE");
      }

      const parseResult = sketchUploadSchema.safeParse(req.body);
      if (!parseResult.success) {
        throw new AppError(400, "Reference length and unit are required", "INVALID_SCALE");
      }

      const { referenceLength, unit } = parseResult.data;
      const project = await getProject(req.params.projectId, req.user!.id);

      const extension = req.file.mimetype === "application/pdf" ? "pdf" : "jpg";
      const { key } = await uploadFile(req.file.buffer, req.file.mimetype, extension, "sketches");

      const job = await createGenerationJob({
        projectId: project.id,
        sourceType: "sketch",
        inputReference: key,
        payload: {
          referenceLength,
          unit,
          originalName: req.file.originalname,
        },
      });

      res.status(201).json({ job, referenceLength, unit });
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

export default router;
