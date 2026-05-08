from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from api.models import Message
from retrieval.rag_chain import RAGChain, RAGResult
from retrieval.retriever import RetrievedChunk


def _make_chunk(article_id: str, title: str, text: str, score: float = 0.8) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"{article_id}-chunk-0",
        article_id=article_id,
        title=title,
        category="troubleshooting",
        chunk_text=text,
        score=score,
    )


@pytest.fixture
def mock_rag():
    with patch("retrieval.rag_chain.HybridRetriever") as mock_retriever_cls, \
         patch("retrieval.rag_chain.OpenAI") as mock_openai_cls:

        mock_retriever = MagicMock()
        mock_retriever_cls.return_value = mock_retriever

        mock_openai = MagicMock()
        mock_openai_cls.return_value = mock_openai
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="rewritten query"))]
        )

        chain = RAGChain()
        chain.retriever = mock_retriever
        chain.client = mock_openai
        yield chain, mock_retriever


def test_rag_returns_chunks_on_hit(mock_rag):
    chain, mock_retriever = mock_rag
    chunk = _make_chunk("KB-007", "Alerts Not Firing", "Update credentials in CloudDash settings.")
    mock_retriever.retrieve.return_value = [chunk]

    result = chain.run("alerts not firing after credential update", [])

    assert not result.needs_escalation
    assert len(result.chunks) == 1
    assert result.chunks[0].article_id == "KB-007"
    assert "KB-007" in result.sources[0]


def test_rag_escalates_on_miss(mock_rag):
    chain, mock_retriever = mock_rag
    mock_retriever.retrieve.return_value = []

    result = chain.run("does clouddash support datadog integration", [])

    assert result.needs_escalation
    assert result.chunks == []
    assert result.sources == []


def test_rag_format_context(mock_rag):
    chain, mock_retriever = mock_rag
    chunk = _make_chunk("KB-009", "AWS CloudWatch Integration Failing", "Step 1: Verify credentials.")
    mock_retriever.retrieve.return_value = [chunk]

    result = chain.run("aws cloudwatch failing", [])
    ctx = result.format_context()

    assert "KB-009" in ctx
    assert "AWS CloudWatch Integration Failing" in ctx
    assert "Step 1" in ctx


def test_rag_rewrites_query_with_history(mock_rag):
    chain, mock_retriever = mock_rag
    mock_retriever.retrieve.return_value = []

    history = [
        Message(role="user", content="I'm on the Pro plan and my alerts stopped firing"),
        Message(role="assistant", content="Let me look into that."),
    ]
    chain.run("still not working", history)

    rewrite_call = chain.client.chat.completions.create.call_args
    prompt_content = rewrite_call[1]["messages"][0]["content"]
    assert "still not working" in prompt_content
    assert "alerts stopped firing" in prompt_content
