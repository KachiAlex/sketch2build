import { AppError } from "../../apps/api/src/lib/errors";

export function handleError(error: unknown, res: any) {
  if (error instanceof AppError) {
    res.status(error.statusCode).json({ error: error.message, code: error.code });
  } else if (error instanceof Error) {
    console.error("Unexpected error:", error);
    res.status(500).json({ error: error.message, code: "INTERNAL_ERROR" });
  } else {
    console.error("Unexpected error:", error);
    res.status(500).json({ error: "Internal server error", code: "INTERNAL_ERROR" });
  }
}
