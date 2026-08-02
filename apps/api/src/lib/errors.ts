export class AppError extends Error {
  constructor(
    public statusCode: number,
    message: string,
    public code: string = "INTERNAL_ERROR"
  ) {
    super(message);
    this.name = "AppError";
  }
}

export function handleError(err: unknown) {
  if (err instanceof AppError) {
    return { statusCode: err.statusCode, body: { error: err.message, code: err.code } };
  }
  if (err instanceof Error) {
    return { statusCode: 500, body: { error: err.message, code: "INTERNAL_ERROR" } };
  }
  return { statusCode: 500, body: { error: "Internal server error", code: "INTERNAL_ERROR" } };
}
