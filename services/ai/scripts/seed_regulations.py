"""Seed building code regulations into the vector store.

Run this script to initialize the regulation vector store with
seed data from IBC, ASHRAE, NFPA, ADA, Eurocode, and local zoning.

Usage:
    python -m scripts.seed_regulations
"""

import structlog

from src.compliance.vector_store import RegulationVectorStore
from src.compliance.regulations_seed import get_all_seed_regulations

logger = structlog.get_logger()


def main():
    logger.info("Seeding regulation vector store")

    store = RegulationVectorStore()
    regulations = get_all_seed_regulations()

    store.add_regulations(regulations)
    store.save()

    logger.info(
        "Regulation vector store seeded successfully",
        count=store.count(),
        persist_dir=str(store.persist_dir),
    )

    print(f"Seeded {store.count()} regulations into vector store")


if __name__ == "__main__":
    main()
