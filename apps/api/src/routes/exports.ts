import { Router } from "express";
import { authenticate, AuthenticatedRequest, requireRole } from "../middleware/auth";
import { generateExport, recordExport } from "../services/exports";
import { handleError } from "../lib/errors";

const router = Router();

const ALLOWED_FORMATS = ["dxf", "pdf", "png", "ifc", "3d-massing"];

router.post(
  "/:candidateId/:format",
  authenticate,
  async (req: AuthenticatedRequest, res) => {
    try {
      const { candidateId, format } = req.params;
      if (!ALLOWED_FORMATS.includes(format)) {
        res.status(400).json({ error: "Unsupported export format" });
        return;
      }

      const { candidate, contentType, buffer, isBinary } = await generateExport(candidateId, format);
      const project = candidate.job.project;
      if (project.ownerId !== req.user!.id && req.user!.role !== "admin") {
        res.status(403).json({ error: "Forbidden" });
        return;
      }

      await recordExport(project.id, format, `export-${format}-${candidateId}`);

      if (isBinary) {
        const filename = `layout-${candidateId}.${format === "3d-massing" ? "json" : format}`;
        res.setHeader("Content-Type", contentType);
        res.setHeader("Content-Disposition", `attachment; filename="${filename}"`);
        res.send(buffer);
      } else {
        res.setHeader("Content-Type", "application/json");
        res.send(buffer);
      }
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

export default router;
