import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {
  // Seed initial NBC ruleset placeholder
  await prisma.complianceRule.upsert({
    where: { id: "rule-setback-default" },
    update: {},
    create: {
      id: "rule-setback-default",
      jurisdiction: "NBC-Nigeria",
      ruleType: "setback",
      parameters: {
        front: 6,
        rear: 3,
        left: 3,
        right: 3,
        unit: "m",
      },
      version: "2024.1",
      effectiveDate: new Date("2024-01-01"),
    },
  });

  // eslint-disable-next-line no-console
  console.log("Seeded initial compliance rules.");
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
