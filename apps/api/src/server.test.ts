import { describe, it, expect, vi } from "vitest";
import request from "supertest";
import { createServer } from "./server";

vi.mock("./lib/prisma", () => ({
  prisma: {},
}));

describe("API Gateway", () => {
  it("returns health status", async () => {
    const app = createServer();
    const res = await request(app).get("/health");
    expect(res.status).toBe(200);
    expect(res.body.status).toBe("ok");
  });

  it("returns docs payload", async () => {
    const app = createServer();
    const res = await request(app).get("/api/docs");
    expect(res.status).toBe(200);
    expect(res.body.modules).toContain("auth");
    expect(res.body.modules).toContain("projects");
  });
});
