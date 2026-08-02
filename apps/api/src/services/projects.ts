import { prisma } from "../lib/prisma";
import { AppError } from "../lib/errors";

export interface CreateProjectInput {
  ownerId: string;
  name: string;
  description?: string;
  jurisdiction: string;
  plotWidth?: number;
  plotDepth?: number;
  plotUnit?: "m" | "ft";
  orientation?: number;
}

export interface UpdateProjectInput {
  name?: string;
  description?: string;
  jurisdiction?: string;
  plotWidth?: number;
  plotDepth?: number;
  plotUnit?: "m" | "ft";
  orientation?: number;
  status?: string;
}

function serializeProject(project: {
  id: string;
  ownerId: string;
  name: string;
  description: string | null;
  jurisdiction: string;
  plotWidth: number | null;
  plotDepth: number | null;
  plotUnit: string | null;
  orientation: number | null;
  status: string;
  createdAt: Date;
  updatedAt: Date;
}) {
  return {
    id: project.id,
    ownerId: project.ownerId,
    name: project.name,
    description: project.description ?? undefined,
    jurisdiction: project.jurisdiction,
    plotDimensions:
      project.plotWidth && project.plotDepth
        ? {
            width: project.plotWidth,
            depth: project.plotDepth,
            unit: project.plotUnit as "m" | "ft",
          }
        : undefined,
    orientation: project.orientation ?? undefined,
    status: project.status,
    createdAt: project.createdAt.toISOString(),
    updatedAt: project.updatedAt.toISOString(),
  };
}

export async function createProject(input: CreateProjectInput) {
  const project = await prisma.project.create({
    data: {
      ownerId: input.ownerId,
      name: input.name,
      description: input.description,
      jurisdiction: input.jurisdiction,
      plotWidth: input.plotWidth,
      plotDepth: input.plotDepth,
      plotUnit: input.plotUnit,
      orientation: input.orientation,
    },
  });
  return serializeProject(project);
}

export async function listProjectsByOwner(ownerId: string) {
  const projects = await prisma.project.findMany({
    where: { ownerId },
    orderBy: { createdAt: "desc" },
  });
  return projects.map(serializeProject);
}

export async function getProject(id: string, ownerId: string) {
  const project = await prisma.project.findFirst({ where: { id, ownerId } });
  if (!project) {
    throw new AppError(404, "Project not found", "PROJECT_NOT_FOUND");
  }
  return serializeProject(project);
}

export async function updateProject(id: string, ownerId: string, input: UpdateProjectInput) {
  await getProject(id, ownerId);
  const project = await prisma.project.update({
    where: { id },
    data: {
      name: input.name,
      description: input.description,
      jurisdiction: input.jurisdiction,
      plotWidth: input.plotWidth,
      plotDepth: input.plotDepth,
      plotUnit: input.plotUnit,
      orientation: input.orientation,
      status: input.status,
    },
  });
  return serializeProject(project);
}

export async function deleteProject(id: string, ownerId: string) {
  await getProject(id, ownerId);
  await prisma.project.delete({ where: { id } });
}
