"""
knowledge_base/ingest.py

Loads all KB JSON files, chunks them, embeds with Pinecone inference
(llama-text-embed-v2), and upserts to Pinecone. Run once before starting
the API server.

Usage:
    python knowledge_base/ingest.py

Environment variables required:
    PINECONE_API_KEY
    PINECONE_INDEX_NAME   (default: vikara)
    PINECONE_INDEX_HOST   (optional, speeds up connections)
    PINECONE_EMBED_MODEL  (default: llama-text-embed-v2)
"""

import os
import json
import logging
from pathlib import Path

from dotenv import load_dotenv
from pinecone import Pinecone

load_dotenv()

CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
EMBED_MODEL = os.getenv("PINECONE_EMBED_MODEL", "llama-text-embed-v2")
BATCH_SIZE = 96
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "vikara")
INDEX_HOST = os.getenv("PINECONE_INDEX_HOST", "")
ARTICLES_DIR = Path(__file__).parent / "articles"

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])


def _char_chunks(text: str, size: int = CHUNK_SIZE * 4, overlap: int = CHUNK_OVERLAP * 4) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end].strip())
        if end == len(text):
            break
        start += size - overlap
    return [c for c in chunks if c]


def chunk_article(article: dict) -> list[dict]:
    full_text = f"{article['title']}\n\n{article['content']}"
    raw_chunks = _char_chunks(full_text)
    return [
        {
            "chunk_id": f"{article['id']}-chunk-{i}",
            "article_id": article["id"],
            "title": article["title"],
            "category": article["category"],
            "tags": article.get("tags", []),
            "applies_to": article.get("applies_to", []),
            "last_updated": article.get("last_updated", ""),
            "chunk_text": chunk_text,
            "chunk_index": i,
            "total_chunks": len(raw_chunks),
        }
        for i, chunk_text in enumerate(raw_chunks)
    ]


def embed_batch(texts: list[str]) -> list[list[float]]:
    result = pc.inference.embed(
        model=EMBED_MODEL,
        inputs=texts,
        parameters={"input_type": "passage", "truncate": "END"},
    )
    return [r.values for r in result]


def load_all_articles() -> list[dict]:
    articles = []
    for json_file in sorted(ARTICLES_DIR.glob("*.json")):
        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)
        batch = data if isinstance(data, list) else [data]
        articles.extend(batch)
        log.info("Loaded %s (%d articles)", json_file.name, len(batch))
    return articles


def run_ingestion() -> None:
    log.info("═══ CloudDash KB Ingestion ═══")

    articles = load_all_articles()
    log.info("Total articles: %d", len(articles))

    all_chunks: list[dict] = []
    for article in articles:
        all_chunks.extend(chunk_article(article))
    log.info("Total chunks: %d", len(all_chunks))

    index = pc.Index(INDEX_NAME, host=INDEX_HOST) if INDEX_HOST else pc.Index(INDEX_NAME)

    total_upserted = 0
    for batch_start in range(0, len(all_chunks), BATCH_SIZE):
        batch = all_chunks[batch_start: batch_start + BATCH_SIZE]
        texts = [c["chunk_text"] for c in batch]

        log.info("Embedding chunks %d–%d …", batch_start, batch_start + len(batch) - 1)
        embeddings = embed_batch(texts)

        vectors = [
            {
                "id": chunk["chunk_id"],
                "values": embedding,
                "metadata": {
                    "article_id": chunk["article_id"],
                    "title": chunk["title"],
                    "category": chunk["category"],
                    "tags": chunk["tags"],
                    "applies_to": chunk["applies_to"],
                    "last_updated": chunk["last_updated"],
                    "chunk_text": chunk["chunk_text"],
                    "chunk_index": chunk["chunk_index"],
                    "total_chunks": chunk["total_chunks"],
                },
            }
            for chunk, embedding in zip(batch, embeddings)
        ]

        index.upsert(vectors=vectors)
        total_upserted += len(vectors)
        log.info("Upserted %d vectors (running total: %d)", len(vectors), total_upserted)

    log.info("═══ Ingestion complete. %d vectors in '%s'. ═══", total_upserted, INDEX_NAME)


if __name__ == "__main__":
    run_ingestion()
