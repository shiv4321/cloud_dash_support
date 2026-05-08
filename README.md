# CloudDash Support ; Multi-Agent Customer Support System

A production-prototype multi-agent system for CloudDash, a cloud infrastructure monitoring SaaS.

<img width="1900" height="946" alt="image" src="https://github.com/user-attachments/assets/9625825d-9588-4375-9196-2cffd6158220" />


## Quick Start

```bash
# 1. Clone and install
pip install -r requirements.txt

# 2. Set environment variables
cp .env.example .env
# Edit .env — fill in OPENAI_API_KEY and PINECONE_API_KEY

# 3. Ingest the knowledge base (run once)
python knowledge_base/ingest.py

# 4. Start the API server
uvicorn api.main:app --reload --port 8000

# 5. Open docs
# http://localhost:8000/docs
```

## Pinecone Index Setup

Create a Serverless index with these exact settings:
- **Dimensions**: 1536 (text-embedding-3-small)
- **Metric**: cosine
- **Cloud**: aws / Region: us-east-1

The index name defaults to `clouddash-kb` (override via `PINECONE_INDEX_NAME`).

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/conversation` | Start a new support conversation |
| POST | `/api/v1/conversation/{id}/message` | Send a message |
| GET | `/api/v1/conversation/{id}/history` | Get conversation history |
| GET | `/health` | Health check |

### Example: Start + Chat

```bash
# Start conversation
curl -X POST http://localhost:8000/api/v1/conversation \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "cust_123"}'

# Send a message (use the conversation_id returned above)
curl -X POST http://localhost:8000/api/v1/conversation/{id}/message \
  -H "Content-Type: application/json" \
  -d '{"message": "My alerts stopped firing after I updated my AWS credentials. Im on Pro plan."}'
```

## Architecture Overview

```
User Request
     │
     ▼
FastAPI Gateway ──► Input Guardrail (injection + off-topic check)
     │
     ▼
Orchestrator (routes via YAML-configured agent registry)
     │
     ├──► Triage Agent     (intent classification via function calling)
     │
     ├──► Technical Agent  (KB retrieval → RAG → step-by-step response)
     │
     ├──► Billing Agent    (policy retrieval → plan/invoice/refund handling)
     │
     └──► Escalation Agent (context packaging → human handover ticket)
              │
              ▼
         Handover Protocol ──► Audit Log (logs/audit.jsonl)
              │
              ▼
       RAG Pipeline
         ├── Query Rewrite (GPT-4o-mini)
         ├── Vector Search (Pinecone text-embedding-3-small)
         ├── BM25 Keyword  (rank_bm25 hybrid)
         └── Hybrid Rerank (0.7 dense + 0.3 BM25)
              │
              ▼
         Pinecone KB (20+ articles, ~80 chunks)
              │
              ▼
Output Guardrail (PII redaction + grounding check + fabrication strip)
     │
     ▼
Response to User
```

## Agent Design

Agents are **YAML-configured plugins**. Adding a new agent (e.g. Onboarding Agent) requires:
1. Add an entry to `config/agents.yaml`
2. Create `agents/onboarding_agent.py` extending `BaseAgent`
3. Zero changes to `orchestrator.py`

The orchestrator dynamically imports the class specified in `agents.yaml`.

## Key Design Decisions

**Plugin agent pattern** — agents registered in YAML, dynamically loaded at startup. Extensible without touching orchestration logic.

**Stateful sessions via trace_id** — each conversation gets a UUID that flows through every log, agent call, and handover event.

**Hybrid retrieval** — 0.7 × cosine similarity + 0.3 × BM25 score. Vector search handles semantic similarity; BM25 handles exact keyword matches (e.g. "KB-007", "Pro plan").

**Handover context snapshot** — the full `HandoverContext` Pydantic model is passed to the receiving agent as a system message prefix. The customer never repeats themselves.

**Graceful KB miss** — when retrieval returns nothing above the similarity threshold (default 0.35), the agent explicitly says "I don't have this information" and routes to escalation.

## Running Tests

```bash
pytest tests/ -v
```

Tests mock all external services (OpenAI, Pinecone) — no API keys needed.

## Project Structure

```
clouddash-support/
├── agents/           # Agent implementations + orchestrator
├── api/              # FastAPI app, routes, Pydantic models
├── config/           # agents.yaml, guardrails.yaml
├── guardrails/       # Input + output guardrails
├── handover/         # Handover protocol + audit logging
├── knowledge_base/   # 20+ KB articles (JSON) + ingestion script
├── retrieval/        # Embedder, hybrid retriever, RAG chain
├── tests/            # Unit + scenario tests
└── logs/             # audit.jsonl written at runtime
```

## Known Limitations

- Sessions are in-memory (dict). A Redis or DB store would be needed for production.
- BM25 index is built by fetching all vectors from Pinecone at startup (works for ~1000 chunks; would need a dedicated search service at scale).
- No authentication on the API endpoints.
- Langfuse integration is optional — set the env vars to enable tracing.
