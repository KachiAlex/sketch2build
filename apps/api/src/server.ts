import express, { Request, Response } from "express";
import cors from "cors";
import helmet from "helmet";
import morgan from "morgan";
import { apiLimiter } from "./middleware/rateLimit";
import authRoutes from "./routes/auth";
import projectRoutes from "./routes/projects";
import jobRoutes from "./routes/jobs";
import sketchRoutes from "./routes/sketch";
import complianceRoutes from "./routes/compliance";
import reviewRoutes from "./routes/review";
import exportRoutes from "./routes/exports";

export function createServer() {
  const app = express();

  app.use(helmet());
  app.use(cors());
  app.use(morgan("dev"));
  app.use(express.json({ limit: "10mb" }));
  app.use(express.urlencoded({ extended: true }));
  app.use("/api", apiLimiter);

  app.get("/health", (_req: Request, res: Response) => {
    res.json({ status: "ok", service: "api-gateway" });
  });

  app.get("/api/docs", (_req: Request, res: Response) => {
    res.json({
      name: "Sketch2Build API",
      version: "0.1.0",
      modules: ["auth", "projects", "jobs", "compliance", "review", "exports"],
      note: "OpenAPI spec will be published once Phase 1 endpoints are finalized.",
    });
  });

  app.use("/api/auth", authRoutes);
  app.use("/api/projects", projectRoutes);
  app.use("/api/jobs", jobRoutes);
  app.use("/api/projects", sketchRoutes);
  app.use("/api/compliance", complianceRoutes);
  app.use("/api/review", reviewRoutes);
  app.use("/api/exports", exportRoutes);

  app.use((_req: Request, res: Response) => {
    res.status(404).json({ error: "Not found" });
  });

  return app;
}
