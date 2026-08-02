import { describe, it, expect } from "vitest";

// Minimal smoke test to ensure the test suite runs.
// Component rendering tests can be added once routing/auth are wired.
describe("App placeholder", () => {
  it("has a project title", () => {
    expect("Sketch2Build").toBe("Sketch2Build");
  });
});
