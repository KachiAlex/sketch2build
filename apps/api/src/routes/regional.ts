import { Router } from "express";
import { authenticate, AuthenticatedRequest } from "../middleware/auth";
import { handleError } from "../lib/errors";

const router = Router();

// Mirrors REGIONAL_PROFILES in the AI service (services/ai/src/regional/profiles.py).
// `id` is the profile key submitted back as `regional_profile` in job payloads.
const PROFILES = [
  { id: "us_default", name: "US Default (IBC)", climate_zone: "temperate", country: "United States" },
  { id: "nordic", name: "Nordic (Eurocode)", climate_zone: "nordic", country: "Nordic countries" },
  { id: "middle_east", name: "Middle East (GCC)", climate_zone: "middle_east", country: "GCC states" },
  { id: "tropical", name: "Tropical (NBC India)", climate_zone: "tropical", country: "India" },
  { id: "japan", name: "Japan (JIS)", climate_zone: "temperate", country: "Japan" },
  { id: "australia", name: "Australia (AS/NZS)", climate_zone: "temperate", country: "Australia" },
  { id: "continental", name: "Continental Europe (Eurocode)", climate_zone: "continental", country: "Europe" },
  { id: "arid", name: "Arid (GCC)", climate_zone: "arid", country: "Arid regions" },
  { id: "mountain", name: "Mountain (Eurocode)", climate_zone: "mountain", country: "Alpine regions" },
];

router.get(
  "/profiles",
  authenticate,
  async (_req: AuthenticatedRequest, res) => {
    try {
      res.json({ count: PROFILES.length, profiles: PROFILES });
    } catch (err) {
      const { statusCode, body } = handleError(err);
      res.status(statusCode).json(body);
    }
  }
);

export default router;
