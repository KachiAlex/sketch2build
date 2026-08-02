"""Vector store for building code regulations using sentence-transformers.

Uses ChromaDB or FAISS for efficient similarity search.
"""

import json
import structlog
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

from src.compliance.models import Regulation, BuildingCode

logger = structlog.get_logger()


class RegulationVectorStore:
    """Vector store for building code regulations with semantic search."""

    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # 384-dim, fast

    def __init__(self, persist_dir: str = "./data/regulations_db"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.model = SentenceTransformer(self.EMBEDDING_MODEL)

        if HAS_CHROMADB:
            self.client = chromadb.Client(
                Settings(
                    persist_directory=str(self.persist_dir),
                    is_persistent=True,
                )
            )
            self.collection = self.client.get_or_create_collection(
                name="regulations",
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("ChromaDB initialized", persist_dir=str(self.persist_dir))
        else:
            self.client = None
            self.collection = None
            self._faiss_index = None
            self._faiss_metadata = []
            logger.warning("ChromaDB not available, using FAISS fallback")

    def _embed_text(self, text: str) -> list[float]:
        """Generate embedding for a regulation text."""
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def add_regulation(self, regulation: Regulation) -> None:
        """Add a regulation to the vector store."""
        embedding = self._embed_text(regulation.text)
        metadata = {
            "code": regulation.code.value,
            "section": regulation.section,
            "title": regulation.title,
            "constraint_type": regulation.constraint_type.value,
            "unit": regulation.unit,
        }

        if self.collection is not None:
            self.collection.add(
                ids=[regulation.id],
                embeddings=[embedding],
                metadatas=[metadata],
                documents=[regulation.text],
            )
        else:
            # FAISS fallback
            self._faiss_metadata.append({
                "id": regulation.id,
                "embedding": embedding,
                **metadata,
            })

    def add_regulations(self, regulations: list[Regulation]) -> None:
        """Batch add regulations."""
        if not regulations:
            return

        if self.collection is not None:
            embeddings = [self._embed_text(r.text) for r in regulations]
            ids = [r.id for r in regulations]
            metadatas = [{
                "code": r.code.value,
                "section": r.section,
                "title": r.title,
                "constraint_type": r.constraint_type.value,
                "unit": r.unit,
            } for r in regulations]
            documents = [r.text for r in regulations]

            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents,
            )
            logger.info("Regulations added to vector store", count=len(regulations))
        else:
            for r in regulations:
                self.add_regulation(r)

    def query(
        self,
        query_text: str,
        code_filter: BuildingCode | None = None,
        n_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Semantic search for relevant regulations."""
        query_embedding = self._embed_text(query_text)

        if self.collection is not None:
            where_filter = None
            if code_filter:
                where_filter = {"code": code_filter.value}

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter,
            )

            # Format results
            formatted = []
            for i in range(len(results["ids"][0])):
                formatted.append({
                    "id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i],
                })
            return formatted
        else:
            # FAISS fallback (simple cosine similarity)
            if not self._faiss_metadata:
                return []

            query_vec = np.array(query_embedding)
            similarities = []
            for item in self._faiss_metadata:
                vec = np.array(item["embedding"])
                sim = np.dot(query_vec, vec) / (np.linalg.norm(query_vec) * np.linalg.norm(vec))
                if code_filter and item["code"] != code_filter.value:
                    continue
                similarities.append((sim, item))

            similarities.sort(reverse=True)
            return [
                {
                    "id": item["id"],
                    "text": item.get("text", ""),
                    "metadata": {k: v for k, v in item.items() if k not in ("id", "embedding")},
                    "distance": 1.0 - sim,
                }
                for sim, item in similarities[:n_results]
            ]

    def get_regulation(self, regulation_id: str) -> dict[str, Any] | None:
        """Retrieve a specific regulation by ID."""
        if self.collection is not None:
            result = self.collection.get(ids=[regulation_id])
            if result["ids"]:
                return {
                    "id": result["ids"][0],
                    "text": result["documents"][0],
                    "metadata": result["metadatas"][0],
                }
        else:
            for item in self._faiss_metadata:
                if item["id"] == regulation_id:
                    return {
                        "id": item["id"],
                        "text": item.get("text", ""),
                        "metadata": {k: v for k, v in item.items() if k not in ("id", "embedding")},
                    }
        return None

    def count(self) -> int:
        """Number of regulations in the store."""
        if self.collection is not None:
            return self.collection.count()
        return len(self._faiss_metadata)

    def save(self) -> None:
        """Persist the vector store."""
        if self.collection is not None:
            # ChromaDB persists automatically with is_persistent=True
            pass
        else:
            # Save FAISS fallback
            with open(self.persist_dir / "faiss_metadata.json", "w") as f:
                json.dump(self._faiss_metadata, f)

        logger.info("Vector store saved", count=self.count())

    def load(self) -> None:
        """Load from disk."""
        if self.collection is not None:
            # ChromaDB loads automatically
            pass
        else:
            metadata_path = self.persist_dir / "faiss_metadata.json"
            if metadata_path.exists():
                with open(metadata_path) as f:
                    self._faiss_metadata = json.load(f)
                logger.info("FAISS metadata loaded", count=len(self._faiss_metadata))
