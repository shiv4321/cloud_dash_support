from __future__ import annotations

import os
from pinecone import Pinecone

EMBED_MODEL = os.getenv("PINECONE_EMBED_MODEL", "llama-text-embed-v2")
EMBED_DIM = 1024

_pc: Pinecone | None = None


def _client() -> Pinecone:
    global _pc
    if _pc is None:
        _pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    return _pc


def embed(text: str) -> list[float]:
    result = _client().inference.embed(
        model=EMBED_MODEL,
        inputs=[text],
        parameters={"input_type": "query", "truncate": "END"},
    )
    return result[0].values


def embed_batch(texts: list[str]) -> list[list[float]]:
    result = _client().inference.embed(
        model=EMBED_MODEL,
        inputs=texts,
        parameters={"input_type": "passage", "truncate": "END"},
    )
    return [r.values for r in result]
