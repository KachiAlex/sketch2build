import "dotenv/config";
import { createServer } from "./server";
import { startGenerationWorker } from "./workers/generationWorker";

const PORT = process.env.PORT ? parseInt(process.env.PORT, 10) : 3000;

const app = createServer();

app.listen(PORT, () => {
  // eslint-disable-next-line no-console
  console.log(`API Gateway listening on http://localhost:${PORT}`);
});

if (process.env.DISABLE_WORKER !== "true") {
  startGenerationWorker();
  // eslint-disable-next-line no-console
  console.log("Generation worker started");
}
