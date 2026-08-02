import { requireAuth, checkRole } from "../../_lib/auth";
import { handleError } from "../../_lib/errors";
import { generateExport, recordExport } from "../../../apps/api/src/services/exports";
import { getCandidateById } from "../../../apps/api/src/services/jobs";

const ALLOWED_FORMATS = ["dxf", "pdf", "png", "ifc", "3d-massing"];

export default async function handler(req: any, res: any) {
  try {
    const user = await requireAuth(req, res);
    if (!user) return;
    checkRole(user, res, "architect", "drafter", "admin");

    if (req.method !== "POST") {
      res.status(405).json({ error: "Method not allowed" });
      return;
    }

    const { candidateId, format } = req.query;
    if (!ALLOWED_FORMATS.includes(format)) {
      res.status(400).json({ error: "Unsupported export format" });
      return;
    }

    const candidate = await getCandidateById(candidateId);
    if (!candidate) {
      res.status(404).json({ error: "Candidate not found" });
      return;
    }
    const project = candidate.job.project;
    if (project.ownerId !== user.id && user.role !== "admin") {
      res.status(403).json({ error: "Forbidden" });
      return;
    }

    const { contentType, buffer, isBinary } = await generateExport(candidateId, format);
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
    handleError(err, res);
  }
}
