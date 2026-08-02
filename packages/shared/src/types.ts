export type UserRole = "architect" | "drafter" | "developer" | "homeowner" | "admin";

export type User = {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  organization?: string;
  createdAt: string;
  updatedAt: string;
};

export type ProjectStatus = "draft" | "processing" | "review" | "finalized";

export type Project = {
  id: string;
  ownerId: string;
  name: string;
  description?: string;
  jurisdiction: string;
  plotDimensions?: { width: number; depth: number; unit: "m" | "ft" };
  orientation?: number;
  status: ProjectStatus;
  createdAt: string;
  updatedAt: string;
};

export type GenerationJobStatus =
  | "queued"
  | "processing"
  | "candidates_ready"
  | "under_review"
  | "finalized"
  | "failed";

export type GenerationJob = {
  id: string;
  projectId: string;
  sourceType: "sketch" | "prompt";
  status: GenerationJobStatus;
  inputReference?: string;
  errorMessage?: string;
  createdAt: string;
  updatedAt: string;
};

export type RoomType =
  | "living"
  | "bedroom"
  | "kitchen"
  | "bathroom"
  | "dining"
  | "corridor"
  | "entrance"
  | "store"
  | "other";

export type Room = {
  id: string;
  candidateId: string;
  type: RoomType;
  label?: string;
  area: number;
  boundaryGeometry: number[][];
  adjacentRoomIds: string[];
};

export type Candidate = {
  id: string;
  jobId: string;
  rank: number;
  score: number;
  scoreRationale?: Record<string, number | string>;
  geometryReference?: string;
  complianceStatus: "pending" | "passed" | "failed";
  rooms?: Room[];
};

export type ComplianceRule = {
  id: string;
  jurisdiction: string;
  ruleType: string;
  parameters: Record<string, unknown>;
  version: string;
  effectiveDate: string;
};

export type ComplianceViolation = {
  ruleId: string;
  message: string;
  location?: string;
  severity: "error" | "warning";
};

export type EditHistory = {
  id: string;
  projectId: string;
  editorId: string;
  changeDescription: string;
  timestamp: string;
  previousStateReference?: string;
};

export type ExportFormat = "DXF" | "IFC" | "PDF" | "PNG";

export type ExportRecord = {
  id: string;
  projectId: string;
  format: ExportFormat;
  fileReference: string;
  exportedAt: string;
};

export type DesignProgram = {
  site: {
    width: number;
    depth: number;
    unit: "m" | "ft";
    setbacks?: { front: number; rear: number; left: number; right: number };
    orientation?: number;
  };
  rooms: Array<{
    type: RoomType;
    count?: number;
    minArea?: number;
    targetArea?: number;
    preferredAdjacencies?: string[];
  }>;
  style?: string;
  budget?: string;
};
