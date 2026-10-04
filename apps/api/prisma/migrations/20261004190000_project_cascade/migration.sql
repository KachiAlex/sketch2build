-- Cascade deletes so removing a Project (or a user via the admin service)
-- cleanly removes the whole job/candidate/room/violation graph.

ALTER TABLE "GenerationJob" DROP CONSTRAINT "GenerationJob_projectId_fkey",
  ADD CONSTRAINT "GenerationJob_projectId_fkey"
    FOREIGN KEY ("projectId") REFERENCES "Project"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "Candidate" DROP CONSTRAINT "Candidate_jobId_fkey",
  ADD CONSTRAINT "Candidate_jobId_fkey"
    FOREIGN KEY ("jobId") REFERENCES "GenerationJob"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "Room" DROP CONSTRAINT "Room_candidateId_fkey",
  ADD CONSTRAINT "Room_candidateId_fkey"
    FOREIGN KEY ("candidateId") REFERENCES "Candidate"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "ComplianceViolation" DROP CONSTRAINT "ComplianceViolation_candidateId_fkey",
  ADD CONSTRAINT "ComplianceViolation_candidateId_fkey"
    FOREIGN KEY ("candidateId") REFERENCES "Candidate"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "EditHistory" DROP CONSTRAINT "EditHistory_projectId_fkey",
  ADD CONSTRAINT "EditHistory_projectId_fkey"
    FOREIGN KEY ("projectId") REFERENCES "Project"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "ExportRecord" DROP CONSTRAINT "ExportRecord_projectId_fkey",
  ADD CONSTRAINT "ExportRecord_projectId_fkey"
    FOREIGN KEY ("projectId") REFERENCES "Project"("id") ON DELETE CASCADE ON UPDATE CASCADE;
