import { generationQueue } from "../lib/queue";
import { prisma } from "../lib/prisma";
import { AppError } from "../lib/errors";

export type JobInput = {
  sourceType: "sketch" | "prompt";
  projectId: string;
  inputReference?: string;
  payload?: Record<string, unknown>;
};

export async function createGenerationJob(input: JobInput) {
  const job = await prisma.generationJob.create({
    data: {
      projectId: input.projectId,
      sourceType: input.sourceType,
      status: "queued",
      inputReference: input.inputReference,
    },
  });

  await generationQueue.add("generate-layout", {
    jobId: job.id,
    projectId: input.projectId,
    sourceType: input.sourceType,
    inputReference: input.inputReference,
    payload: input.payload,
  });

  return job;
}

export async function getGenerationJob(jobId: string) {
  const job = await prisma.generationJob.findUnique({
    where: { id: jobId },
    include: { candidates: true },
  });
  if (!job) {
    throw new AppError(404, "Job not found", "JOB_NOT_FOUND");
  }
  return job;
}

export async function listGenerationJobsByProject(projectId: string) {
  return prisma.generationJob.findMany({
    where: { projectId },
    orderBy: { createdAt: "desc" },
    include: { candidates: true },
  });
}

export async function updateJobStatus(
  jobId: string,
  status: string,
  errorMessage?: string
) {
  return prisma.generationJob.update({
    where: { id: jobId },
    data: { status, errorMessage },
  });
}

export interface CandidateInput {
  rank: number;
  score?: number;
  rationale?: Record<string, unknown>;
  rooms: Array<{
    type: string;
    label?: string;
    area: number;
    boundaryGeometry: unknown;
    adjacentRoomIds?: string[];
  }>;
}

export async function persistCandidates(jobId: string, candidates: CandidateInput[]) {
  for (const candidate of candidates) {
    await prisma.candidate.create({
      data: {
        jobId,
        rank: candidate.rank,
        score: candidate.score,
        scoreRationale: (candidate.rationale ?? null) as never,
        rooms: {
          create: candidate.rooms.map((room) => ({
            type: room.type,
            label: room.label,
            area: room.area,
            boundaryGeometry: room.boundaryGeometry as never,
            adjacentRoomIds: room.adjacentRoomIds ?? [],
          })),
        },
      },
    });
  }
}

export async function finalizeJob(jobId: string) {
  return prisma.generationJob.update({
    where: { id: jobId },
    data: { status: "finalized" },
  });
}

export async function getCandidateById(candidateId: string) {
  return prisma.candidate.findUnique({
    where: { id: candidateId },
    include: {
      rooms: true,
      complianceViolations: true,
      job: { include: { project: true } },
    },
  });
}

export async function updateCandidateGeometry(
  candidateId: string,
  rooms: Array<{ id: string; type?: string; label?: string; area: number; boundaryGeometry: unknown }>,
  editorId: string
) {
  const candidate = await prisma.candidate.findUnique({
    where: { id: candidateId },
    include: { rooms: true, job: true },
  });
  if (!candidate) {
    throw new AppError(404, "Candidate not found", "CANDIDATE_NOT_FOUND");
  }

  // Store a snapshot of the previous state before applying edits.
  await prisma.editHistory.create({
    data: {
      projectId: candidate.job.projectId,
      editorId,
      changeDescription: "Manual geometry edit",
      previousStateReference: candidateId,
      snapshot: { rooms: candidate.rooms } as never,
    },
  });

  // Update each room geometry.
  for (const room of rooms) {
    await prisma.room.update({
      where: { id: room.id },
      data: {
        type: room.type,
        label: room.label,
        area: room.area,
        boundaryGeometry: room.boundaryGeometry as never,
      },
    });
  }

  // Reset compliance status until re-validated.
  await prisma.candidate.update({
    where: { id: candidateId },
    data: { complianceStatus: "pending" },
  });

  return getCandidateById(candidateId);
}

export async function revertCandidateToHistory(
  candidateId: string,
  historyId: string,
  editorId: string
) {
  const candidate = await prisma.candidate.findUnique({ where: { id: candidateId }, include: { rooms: true, job: true } });
  if (!candidate) {
    throw new AppError(404, "Candidate not found", "CANDIDATE_NOT_FOUND");
  }

  const history = await prisma.editHistory.findUnique({ where: { id: historyId } });
  if (!history || history.previousStateReference !== candidateId) {
    throw new AppError(404, "Edit history snapshot not found for this candidate", "HISTORY_NOT_FOUND");
  }

  const snapshot = history.snapshot as { rooms?: Array<{ id: string; type: string; label?: string; area: number; boundaryGeometry: unknown; adjacentRoomIds: string[] }> } | null;
  if (!snapshot?.rooms) {
    throw new AppError(400, "Snapshot has no room data", "INVALID_SNAPSHOT");
  }

  await prisma.editHistory.create({
    data: {
      projectId: candidate.job.projectId,
      editorId,
      changeDescription: `Reverted to edit history ${historyId}`,
      previousStateReference: candidateId,
      snapshot: { rooms: candidate.rooms } as never,
    },
  });

  for (const room of snapshot.rooms) {
    await prisma.room.update({
      where: { id: room.id },
      data: {
        type: room.type,
        label: room.label,
        area: room.area,
        boundaryGeometry: room.boundaryGeometry as never,
        adjacentRoomIds: room.adjacentRoomIds ?? [],
      },
    });
  }

  await prisma.candidate.update({
    where: { id: candidateId },
    data: { complianceStatus: "pending" },
  });

  return getCandidateById(candidateId);
}

export async function finalizeJobWithReview(jobId: string, reviewerName: string) {
  const job = await prisma.generationJob.findUnique({
    where: { id: jobId },
    include: { candidates: true },
  });
  if (!job) {
    throw new AppError(404, "Job not found", "JOB_NOT_FOUND");
  }
  const hasFailedCompliance = job.candidates.some((c) => c.complianceStatus === "failed");
  if (hasFailedCompliance) {
    throw new AppError(400, "Cannot finalize: one or more candidates have failed compliance", "COMPLIANCE_FAILED");
  }
  const hasPending = job.candidates.some((c) => c.complianceStatus === "pending");
  if (hasPending) {
    throw new AppError(400, "Cannot finalize: one or more candidates have not been validated", "COMPLIANCE_PENDING");
  }
  return prisma.generationJob.update({
    where: { id: jobId },
    data: {
      status: "finalized",
      reviewedBy: reviewerName,
      reviewedAt: new Date(),
      finalizedAt: new Date(),
    },
  });
}
