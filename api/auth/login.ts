import { VercelRequest, VercelResponse } from "@vercel/node";
import { z } from "zod";
import { validateBody } from "../_lib/validate";
import { handleError } from "../_lib/errors";
import { loginUser } from "../../apps/api/src/services/auth";

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== "POST") {
    res.status(405).json({ error: "Method not allowed" });
    return;
  }
  try {
    const validation = validateBody(schema, req.body);
    if (validation.error) {
      res.status(400).json(validation);
      return;
    }
    const result = await loginUser(validation.data as any);
    res.json(result);
  } catch (err) {
    handleError(err, res);
  }
}
