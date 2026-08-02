import { prisma } from "../lib/prisma";
import { AppError } from "../lib/errors";

const AI_SERVICE_URL = process.env.AI_SERVICE_URL || "http://localhost:8000";

export async function getCandidateWithProject(candidateId: string) {
  return prisma.candidate.findUnique({
    where: { id: candidateId },
    include: {
      rooms: true,
      job: { include: { project: true } },
    },
  });
}

export async function generateExport(candidateId: string, format: string) {
  const candidate = await getCandidateWithProject(candidateId);
  if (!candidate) {
    throw new AppError(404, "Candidate not found", "CANDIDATE_NOT_FOUND");
  }

  const layout = {
    site: candidate.job.project.plotWidth && candidate.job.project.plotDepth
      ? [
          [0, 0],
          [candidate.job.project.plotWidth, 0],
          [candidate.job.project.plotWidth, candidate.job.project.plotDepth],
          [0, candidate.job.project.plotDepth],
        ]
      : [],
    rooms: candidate.rooms.map((room) => ({
      type: room.type,
      label: room.label,
      area: room.area,
      boundaryGeometry: room.boundaryGeometry,
    })),
  };

  const endpoint = format === "3d-massing" ? "3d-massing" : format;
  const response = await fetch(`${AI_SERVICE_URL}/export/${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ layout, format }),
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => "Export service error");
    throw new AppError(502, detail, "EXPORT_SERVICE_ERROR");
  }

  const contentType = response.headers.get("content-type") || "application/octet-stream";
  const buffer = Buffer.from(await response.arrayBuffer());

  return {
    candidate,
    contentType,
    buffer,
    isBinary: contentType !== "application/json",
  };
}

export async function recordExport(
  projectId: string,
  format: string,
  fileReference: string
) {
  return prisma.exportRecord.create({
    data: { projectId, format, fileReference },
  });
}
