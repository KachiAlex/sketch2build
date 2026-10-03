import { Router, Response } from "express";
import { authenticate, AuthenticatedRequest } from "../middleware/auth";
import { generateExport, recordExport } from "../services/exports";
import { handleError } from "../lib/errors";

const router = Router();

const ALLOWED_FORMATS = ["dxf", "pdf", "png", "ifc", "3d-massing"];

const exportHandler = async (req: AuthenticatedRequest, res: Response) => {
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
};

router.post("/:candidateId/:format", authenticate, exportHandler);
router.get("/:candidateId/:format", authenticate, exportHandler);

export default router;
