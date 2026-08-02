import { Queue, Worker, Job } from "bullmq";
import IORedis from "ioredis";

const redisUrl = process.env.REDIS_URL || "redis://localhost:6379";
const connection = new IORedis(redisUrl, { maxRetriesPerRequest: null });

export const generationQueue = new Queue("generation-jobs", { connection });

export function createGenerationWorker(processor: (job: Job) => Promise<void>) {
  return new Worker(
    "generation-jobs",
    async (job: Job) => {
      await processor(job);
    },
    { connection }
  );
}
