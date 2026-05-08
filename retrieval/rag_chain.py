from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from openai import OpenAI

from api.models import Message
from retrieval.retriever import HybridRetriever, RetrievedChunk

log = logging.getLogger(__name__)
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.35"))


@dataclass
class RAGResult:
    query: str
    rewritten_query: str
    chunks: list[RetrievedChunk]
    sources: list[str]
    needs_escalation: bool

    def format_context(self) -> str:
        if not self.chunks:
            return ""
        parts = []
        for chunk in self.chunks:
            parts.append(
                f"[Source: {chunk.article_id} — {chunk.title}]\n{chunk.chunk_text}"
            )
        return "\n\n".join(parts)


class RAGChain:
    def __init__(self) -> None:
        self.retriever = HybridRetriever()
        self.client = OpenAI()

    def _rewrite_query(self, query: str, history: list[Message]) -> str:
        if not history:
            return query

        recent = history[-4:]
        history_text = "\n".join(f"{m.role}: {m.content}" for m in recent)

        prompt = (
            "Given the conversation history below and a follow-up query, "
            "rewrite the query to be a standalone, self-contained search query "
            "for a cloud infrastructure monitoring knowledge base. "
            "Output ONLY the rewritten query, nothing else.\n\n"
            f"Conversation history:\n{history_text}\n\n"
            f"Follow-up query: {query}\n\n"
            "Standalone query:"
        )

        rewritten = self.client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
        ).choices[0].message.content.strip()

        log.info("rag query_rewrite original=%r rewritten=%r", query[:60], rewritten[:60])
        return rewritten

    def run(self, query: str, history: list[Message]) -> RAGResult:
        rewritten = self._rewrite_query(query, history)
        chunks = self.retriever.retrieve(rewritten)

        if not chunks:
            log.info("rag kb_miss query=%r", rewritten[:60])
            return RAGResult(
                query=query,
                rewritten_query=rewritten,
                chunks=[],
                sources=[],
                needs_escalation=True,
            )

        sources = list({f"{c.article_id} — {c.title}" for c in chunks})

        return RAGResult(
            query=query,
            rewritten_query=rewritten,
            chunks=chunks,
            sources=sources,
            needs_escalation=False,
        )
