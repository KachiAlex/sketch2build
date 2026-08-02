import { ZodSchema } from "zod";

export function validateBody(schema: ZodSchema, body: any) {
  const result = schema.safeParse(body);
  if (!result.success) {
    return {
      error: "Validation failed",
      issues: result.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`),
    };
  }
  return { data: result.data };
}
