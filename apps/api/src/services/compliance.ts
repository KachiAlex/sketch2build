import { prisma } from "../lib/prisma";
import { AppError } from "../lib/errors";

const AI_SERVICE_URL = process.env.AI_SERVICE_URL || "http://localhost:8000";

export async function validateCandidate(candidateId: string) {
  const candidate = await prisma.candidate.findUnique({
    where: { id: candidateId },
    include: {
      rooms: true,
      job: {
        include: { project: true },
      },
    },
  });

  if (!candidate) {
    throw new AppError(404, "Candidate not found", "CANDIDATE_NOT_FOUND");
  }

  const project = candidate.job.project;
  const siteBoundary = project.plotWidth && project.plotDepth
    ? [
        [0, 0],
        [project.plotWidth, 0],
        [project.plotWidth, project.plotDepth],
        [0, project.plotDepth],
      ]
    : [];

  const layout = {
    site: siteBoundary,
    rooms: candidate.rooms.map((room) => ({
      type: room.type,
      label: room.label,
      area: room.area,
      boundaryGeometry: room.boundaryGeometry,
    })),
  };

  const response = await fetch(`${AI_SERVICE_URL}/compliance/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ layout, jurisdiction: project.jurisdiction }),
  });

  if (!response.ok) {
    throw new AppError(502, "Compliance service unavailable", "COMPLIANCE_SERVICE_ERROR");
  }

  const result = (await response.json()) as {
    status: string;
    jurisdiction: string;
    rulesetVersion: string;
    violations: Array<{
      ruleId: string;
      ruleType: string;
      message: string;
      location?: string;
      severity: string;
    }>;
    passed: boolean;
  };

  // Clear previous violations and store new ones
  await prisma.complianceViolation.deleteMany({ where: { candidateId } });
  for (const violation of result.violations) {
    await prisma.complianceViolation.create({
      data: {
        candidateId,
        ruleId: violation.ruleId,
        message: violation.message,
        location: violation.location ?? null,
        severity: violation.severity,
      },
    });
  }

  await prisma.candidate.update({
    where: { id: candidateId },
    data: { complianceStatus: result.passed ? "passed" : "failed" },
  });

  return result;
}

export async function getActiveRules(jurisdiction: string) {
  return prisma.complianceRule.findMany({
    where: { jurisdiction },
    orderBy: { effectiveDate: "desc" },
  });
}

export async function createRule(data: {
  jurisdiction: string;
  ruleType: string;
  parameters: Record<string, unknown>;
  version: string;
  effectiveDate: Date;
}) {
  return prisma.complianceRule.create({ data: { ...data, parameters: data.parameters as never } });
}

export async function updateRule(
  id: string,
  data: Partial<{
    jurisdiction: string;
    ruleType: string;
    parameters: Record<string, unknown>;
    version: string;
    effectiveDate: Date;
  }>
) {
  const existing = await prisma.complianceRule.findUnique({ where: { id } });
  if (!existing) {
    throw new AppError(404, "Rule not found", "RULE_NOT_FOUND");
  }
  return prisma.complianceRule.update({ where: { id }, data: data as never });
}

export async function deleteRule(id: string) {
  const existing = await prisma.complianceRule.findUnique({ where: { id } });
  if (!existing) {
    throw new AppError(404, "Rule not found", "RULE_NOT_FOUND");
  }
  await prisma.complianceRule.delete({ where: { id } });
}
