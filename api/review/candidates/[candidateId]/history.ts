import { requireAuth } from "../../../_lib/auth";
import { handleError } from "../../../_lib/errors";
import { prisma } from "../../../../apps/api/src/lib/prisma";

export default async function handler(req: any, res: any) {
  try {
    const user = await requireAuth(req, res);
    if (!user) return;

    if (req.method !== "GET") {
      res.status(405).json({ error: "Method not allowed" });
      return;
    }

    const { candidateId } = req.query;
    const history = await prisma.editHistory.findMany({
      where: { previousStateReference: candidateId },
      orderBy: { timestamp: "desc" },
    });
    res.json({ history });
  } catch (err) {
    handleError(err, res);
  }
}
