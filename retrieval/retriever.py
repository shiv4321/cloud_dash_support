from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from pinecone import Pinecone
from rank_bm25 import BM25Okapi

from retrieval.embedder import EMBED_DIM, embed

log = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.35"))
TOP_K = int(os.getenv("TOP_K_RESULTS", "5"))
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "vikara")
INDEX_HOST = os.getenv("PINECONE_INDEX_HOST", "")


@dataclass
class RetrievedChunk:
    chunk_id: str
    article_id: str
    title: str
    category: str
    chunk_text: str
    score: float
    tags: list[str] = field(default_factory=list)
    applies_to: list[str] = field(default_factory=list)


class HybridRetriever:
    def __init__(self) -> None:
        self._pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
        self._index = self._pc.Index(INDEX_NAME, host=INDEX_HOST) if INDEX_HOST else self._pc.Index(INDEX_NAME)
        self._bm25: BM25Okapi | None = None
        self._corpus: list[dict] = []

    def _ensure_bm25(self) -> None:
        if self._bm25 is not None:
            return
        stats = self._index.describe_index_stats()
        total = stats.total_vector_count
        if total == 0:
            log.warning("retriever pinecone index is empty — run ingest.py first")
            self._bm25 = BM25Okapi([[]])
            return

        result = self._index.query(
            vector=[0.0] * EMBED_DIM,
            top_k=min(total, 1000),
            include_metadata=True,
        )
        self._corpus = [
            {
                "id": m.id,
                "chunk_text": m.metadata.get("chunk_text", ""),
                "article_id": m.metadata.get("article_id", ""),
                "title": m.metadata.get("title", ""),
                "category": m.metadata.get("category", ""),
                "tags": m.metadata.get("tags", []),
                "applies_to": m.metadata.get("applies_to", []),
            }
            for m in result.matches
        ]
        tokenized = [doc["chunk_text"].lower().split() for doc in self._corpus]
        self._bm25 = BM25Okapi(tokenized)
        log.info("retriever bm25_corpus_size=%d", len(self._corpus))

    def retrieve(self, query: str, top_k: int = TOP_K) -> list[RetrievedChunk]:
        self._ensure_bm25()

        query_vec = embed(query)
        dense_result = self._index.query(
            vector=query_vec,
            top_k=top_k * 2,
            include_metadata=True,
        )

        dense_scores: dict[str, float] = {
            m.id: m.score for m in dense_result.matches
        }

        bm25_scores_raw: list[float] = []
        if self._bm25 and self._corpus:
            bm25_scores_raw = self._bm25.get_scores(query.lower().split()).tolist()

        bm25_map: dict[str, float] = {}
        if bm25_scores_raw and self._corpus:
            max_bm25 = max(bm25_scores_raw) or 1.0
            for doc, score in zip(self._corpus, bm25_scores_raw):
                bm25_map[doc["id"]] = score / max_bm25

        candidate_ids = set(dense_scores.keys()) | set(bm25_map.keys())
        combined: list[tuple[str, float]] = []
        for cid in candidate_ids:
            hybrid = 0.7 * dense_scores.get(cid, 0.0) + 0.3 * bm25_map.get(cid, 0.0)
            combined.append((cid, hybrid))

        combined.sort(key=lambda x: x[1], reverse=True)
        top_ids = [cid for cid, _ in combined[:top_k]]

        meta_map: dict[str, dict] = {m.id: m.metadata for m in dense_result.matches}
        for doc in self._corpus:
            if doc["id"] not in meta_map:
                meta_map[doc["id"]] = doc

        chunks: list[RetrievedChunk] = []
        for cid, score in combined[:top_k]:
            if score < SIMILARITY_THRESHOLD:
                continue
            meta = meta_map.get(cid, {})
            chunks.append(
                RetrievedChunk(
                    chunk_id=cid,
                    article_id=meta.get("article_id", ""),
                    title=meta.get("title", ""),
                    category=meta.get("category", ""),
                    chunk_text=meta.get("chunk_text", ""),
                    score=score,
                    tags=meta.get("tags", []),
                    applies_to=meta.get("applies_to", []),
                )
            )

        log.info("retriever query=%r results=%d threshold=%s", query[:60], len(chunks), SIMILARITY_THRESHOLD)
        return chunks
