import { Job } from "bullmq";
import { createGenerationWorker } from "../lib/queue";
import { updateJobStatus, persistCandidates } from "../services/jobs";

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

async function processGenerationJob(job: Job<GenerationJobData>) {
  const { jobId, sourceType } = job.data;

  await updateJobStatus(jobId, "processing");

  try {
    let result: Record<string, unknown> = {};
    if (sourceType === "sketch") {
      result = await callSketchDigitization(job.data);
    } else if (sourceType === "prompt") {
      result = await callPromptGeneration(job.data);
    }

    const candidates = normalizeCandidates(sourceType, result);
    if (candidates.length > 0) {
      await persistCandidates(jobId, candidates);
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
  rooms: Array<{
    type: string;
    label?: string;
    area: number;
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
      rooms: ((candidate.rooms as Array<Record<string, unknown>>) || []).map((room) => ({
        type: (room.type as string) || "room",
        label: room.label as string | undefined,
        area: (room.area as number) || 0,
        boundaryGeometry: room.boundaryGeometry,
      })),
    }));
  }

  // Sketch digitization returns a single set of geometry; wrap it as one candidate.
  const rooms = (result.rooms as Array<Record<string, unknown>>) || [];
  const walls = (result.walls as Array<Record<string, unknown>>) || [];
  return [
    {
      rank: 1,
      score: undefined,
      rationale: { source: "sketch-digitization", wallsDetected: walls.length },
      rooms: rooms.length
        ? rooms.map((room) => ({
            type: (room.type as string) || "room",
            label: room.label as string | undefined,
            area: (room.area as number) || 0,
            boundaryGeometry: room.boundaryGeometry,
          }))
        : [
            {
              type: "sketch-region",
              label: "Detected sketch region",
              area: 0,
              boundaryGeometry: walls,
            },
          ],
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
