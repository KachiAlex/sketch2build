import { describe, it, expect, vi, beforeEach } from "vitest";
import bcrypt from "bcryptjs";
import { registerUser, loginUser } from "./auth";

vi.mock("../lib/prisma", () => ({
  prisma: {
    user: {
      findUnique: vi.fn(),
      create: vi.fn(),
    },
  },
}));

import { prisma } from "../lib/prisma";

const mockPrisma = prisma as unknown as {
  user: {
    findUnique: ReturnType<typeof vi.fn>;
    create: ReturnType<typeof vi.fn>;
  };
};

describe("Auth service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("registers a new user", async () => {
    mockPrisma.user.findUnique.mockResolvedValue(null);
    mockPrisma.user.create.mockResolvedValue({
      id: "user-1",
      email: "architect@example.com",
      name: "Ada Architect",
      role: "architect",
      organization: "Kreatix",
      passwordHash: "hashed",
    });

    const result = await registerUser({
      email: "architect@example.com",
      password: "password123",
      name: "Ada Architect",
      role: "architect",
      organization: "Kreatix",
    });

    expect(result.user.email).toBe("architect@example.com");
    expect(result.token).toBeDefined();
    expect(mockPrisma.user.create).toHaveBeenCalledOnce();
  });

  it("throws when email already exists", async () => {
    mockPrisma.user.findUnique.mockResolvedValue({ id: "existing" });

    await expect(
      registerUser({
        email: "architect@example.com",
        password: "password123",
        name: "Ada Architect",
        role: "architect",
      })
    ).rejects.toThrow("Email already registered");
  });

  it("logs in an existing user", async () => {
    const passwordHash = await bcrypt.hash("password123", 10);
    mockPrisma.user.findUnique.mockResolvedValue({
      id: "user-1",
      email: "architect@example.com",
      name: "Ada Architect",
      role: "architect",
      organization: null,
      passwordHash,
    });

    const result = await loginUser({
      email: "architect@example.com",
      password: "password123",
    });

    expect(result.user.email).toBe("architect@example.com");
    expect(result.token).toBeDefined();
  });

  it("throws on invalid login", async () => {
    mockPrisma.user.findUnique.mockResolvedValue(null);

    await expect(
      loginUser({ email: "missing@example.com", password: "password123" })
    ).rejects.toThrow("Invalid email or password");
  });
});
