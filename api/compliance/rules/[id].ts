import { z } from "zod";
import { validateBody } from "../../_lib/validate";
import { requireAuth, checkRole } from "../../_lib/auth";
import { handleError } from "../../_lib/errors";
import { updateRule, deleteRule } from "../../../apps/api/src/services/compliance";

const schema = z.object({
  jurisdiction: z.string().min(1).optional(),
  ruleType: z.string().min(1).optional(),
  parameters: z.record(z.unknown()).optional(),
  version: z.string().min(1).optional(),
  effectiveDate: z.coerce.date().optional(),
});

export default async function handler(req: any, res: any) {
  try {
    const user = await requireAuth(req, res);
    if (!user) return;
    checkRole(user, res, "admin");

    const { id } = req.query;

    if (req.method === "PATCH") {
      const validation = validateBody(schema, req.body);
      if (validation.error) {
        res.status(400).json(validation);
        return;
      }
      const rule = await updateRule(id, validation.data as any);
      res.json(rule);
      return;
    }

    if (req.method === "DELETE") {
      await deleteRule(id);
      res.status(204).end();
      return;
    }

    res.status(405).json({ error: "Method not allowed" });
  } catch (err) {
    handleError(err, res);
  }
}
