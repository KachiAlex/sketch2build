import { Request, Response, NextFunction } from "express";
import { ZodSchema, ZodError } from "zod";

export function validateBody(schema: ZodSchema<unknown>) {
  return (req: Request, res: Response, next: NextFunction) => {
    const result = schema.safeParse(req.body);
    if (!result.success) {
      const issues = result.error.issues.map((issue) => `${issue.path.join(".")}: ${issue.message}`);
      res.status(400).json({ error: "Validation failed", issues });
      return;
    }
    next();
  };
}

export function formatZodError(error: ZodError) {
  return error.issues.map((issue) => `${issue.path.join(".")}: ${issue.message}`);
}
