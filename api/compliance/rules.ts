import { z } from "zod";
import { validateBody } from "../_lib/validate";
import { requireAuth, checkRole } from "../_lib/auth";
import { handleError } from "../_lib/errors";
import { getActiveRules, createRule } from "../../apps/api/src/services/compliance";

const schema = z.object({
  jurisdiction: z.string().min(1),
  ruleType: z.string().min(1),
  parameters: z.record(z.unknown()),
  version: z.string().min(1),
  effectiveDate: z.coerce.date(),
});

export default async function handler(req: any, res: any) {
  try {
    const user = await requireAuth(req, res);
    if (!user) return;

    if (req.method === "GET") {
      checkRole(user, res, "architect", "admin");
      const jurisdiction = typeof req.query.jurisdiction === "string" ? req.query.jurisdiction : "Nigeria";
      const rules = await getActiveRules(jurisdiction);
      res.json({ rules });
      return;
    }

    if (req.method === "POST") {
      checkRole(user, res, "admin");
      const validation = validateBody(schema, req.body);
      if (validation.error) {
        res.status(400).json(validation);
        return;
      }
      const rule = await createRule(validation.data as any);
      res.status(201).json(rule);
      return;
    }

    res.status(405).json({ error: "Method not allowed" });
  } catch (err) {
    handleError(err, res);
  }
}
