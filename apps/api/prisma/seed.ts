import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {
  // Nigerian Building Code residential setbacks — one rule record per edge so
  // the AI validator's DB-rule merge can consume them (see build_ruleset).
  // Jurisdiction must be the canonical key "Nigeria"; aliases like
  // "NBC-Nigeria" resolve to this at validation time.
  const setbacks: Array<{ id: string; edge: string; distance: number }> = [
    { id: "rule-setback-front", edge: "front", distance: 6 },
    { id: "rule-setback-side", edge: "side", distance: 3 },
    { id: "rule-setback-rear", edge: "rear", distance: 3 },
  ];
  for (const rule of setbacks) {
    await prisma.complianceRule.upsert({
      where: { id: rule.id },
      update: {
        jurisdiction: "Nigeria",
        parameters: { edge: rule.edge, distance: rule.distance, unit: "m" },
      },
      create: {
        id: rule.id,
        jurisdiction: "Nigeria",
        ruleType: "setback",
        parameters: { edge: rule.edge, distance: rule.distance, unit: "m" },
        version: "2024.1",
        effectiveDate: new Date("2024-01-01"),
      },
    });
  }

  // eslint-disable-next-line no-console
  console.log("Seeded NBC setback rules.");
}

main()
  .catch((e) => {
    // eslint-disable-next-line no-console
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
