import { Job } from "bullmq";
import { createGenerationWorker } from "../lib/queue";
import { updateJobStatus, persistCandidates } from "../services/jobs";
import { validateCandidate } from "../services/compliance";
import { prisma } from "../lib/prisma";

export interface GenerationJobData {
  jobId: string;
  projectId: string;
  sourceType: "sketch" | "prompt";
  inputReference?: string;
  payload?: Record<string, unknown>;
}

const AI_SERVICE_URL = process.env.AI_SERVICE_URL || "http://localhost:8000";

async function callSketchDigitization(jobData: GenerationJobData) {
  const response = await fetch(`${AI_SERVICE_URL}/sketch/digitize-from-storage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      storageKey: jobData.inputReference,
      referenceLength: jobData.payload?.referenceLength,
      referencePixels: jobData.payload?.referencePixels,
      unit: jobData.payload?.unit,
      projectId: jobData.projectId,
      jobId: jobData.jobId,
    }),
  });

  if (!response.ok) {
    throw new Error(`AI service returned ${response.status}`);
  }

  return response.json();
}

async function callPromptGeneration(jobData: GenerationJobData) {
  const response = await fetch(`${AI_SERVICE_URL}/prompt/generate-from-program`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      program: jobData.payload,
      projectId: jobData.projectId,
      jobId: jobData.jobId,
    }),
  });

  if (!response.ok) {
    throw new Error(`AI service returned ${response.status}`);
  }

  return response.json();
}

async function isJobActive(jobId: string) {
  const current = await prisma.generationJob.findUnique({
    where: { id: jobId },
    select: { status: true },
  });
  // A cancelled job is marked failed — it must stay failed when the queued
  // BullMQ entry eventually runs.
  return current && (current.status === "queued" || current.status === "processing");
}

async function processGenerationJob(job: Job<GenerationJobData>) {
  const { jobId, sourceType } = job.data;

  if (!(await isJobActive(jobId))) {
    return;
  }
  await updateJobStatus(jobId, "processing");

  try {
    let result: Record<string, unknown> = {};
    if (sourceType === "sketch") {
      result = await callSketchDigitization(job.data);
    } else if (sourceType === "prompt") {
      result = await callPromptGeneration(job.data);
    }

    // The user may have cancelled while the AI service was generating.
    if (!(await isJobActive(jobId))) {
      return;
    }

    const candidates = normalizeCandidates(sourceType, result);
    if (candidates.length > 0) {
      const persisted = await persistCandidates(jobId, candidates);
      // Best-effort compliance validation — a validator failure must not fail the job.
      for (const candidate of persisted) {
        try {
          await validateCandidate(candidate.id);
        } catch (validationErr) {
          // eslint-disable-next-line no-console
          console.error(`Compliance validation failed for candidate ${candidate.id}:`, validationErr);
        }
      }
    }

    await updateJobStatus(jobId, "candidates_ready");
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown processing error";
    await updateJobStatus(jobId, "failed", message);
    throw err;
  }
}

function normalizeCandidates(
  sourceType: "sketch" | "prompt",
  result: Record<string, unknown>
): Array<{
  rank: number;
  score?: number;
  rationale?: Record<string, unknown>;
  planExtras?: Record<string, unknown>;
  rooms: Array<{
    type: string;
    label?: string;
    area: number;
    floor?: number;
    boundaryGeometry: unknown;
    adjacentRoomIds?: string[];
  }>;
}> {
  if (sourceType === "prompt") {
    const rawCandidates = (result.candidates as Array<Record<string, unknown>>) || [];
    return rawCandidates.map((candidate, index) => ({
      rank: (candidate.rank as number) || index + 1,
      score: candidate.score as number | undefined,
      rationale: candidate.rationale as Record<string, unknown> | undefined,
      planExtras: {
        plot: candidate.plot,
        doors: candidate.doors,
        windows: candidate.windows,
        unit: candidate.unit,
        floors: candidate.floors,
      } as Record<string, unknown>,
      rooms: ((candidate.rooms as Array<Record<string, unknown>>) || []).map((room) => ({
        type: (room.type as string) || "room",
        label: room.label as string | undefined,
        area: (room.area as number) || 0,
        floor: (room.floor as number) || 1,
        boundaryGeometry: room.boundaryGeometry,
      })),
    }));
  }

  // Sketch digitization returns a single set of geometry; wrap it as one candidate.
  const rooms = (result.rooms as Array<Record<string, unknown>>) || [];
  if (result.status === "failed" || !rooms.length) {
    throw new Error((result.error as string) || "Sketch digitization produced no rooms");
  }
  return [
    {
      rank: 1,
      score: undefined,
      rationale: {
        source: (result.source as string) || "sketch-digitization",
        scale: result.scale as string | undefined,
      },
      planExtras: {
        plot: result.plot,
        doors: result.doors,
        windows: result.windows,
        unit: result.unit,
      } as Record<string, unknown>,
      rooms: rooms.map((room) => ({
        type: (room.type as string) || "room",
        label: room.label as string | undefined,
        area: (room.area as number) || 0,
        floor: 1,
        boundaryGeometry: room.boundaryGeometry,
      })),
    },
  ];
}

export function startGenerationWorker() {
  const worker = createGenerationWorker(async (job: Job<GenerationJobData>) => {
    await processGenerationJob(job);
  });

  worker.on("failed", (job, err) => {
    // eslint-disable-next-line no-console
    console.error(`Job ${job?.id} failed:`, err);
  });

  return worker;
}
