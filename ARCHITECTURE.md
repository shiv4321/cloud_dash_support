# Architecture — CloudDash Multi-Agent Support System

## System Overview

The system is a stateful multi-agent orchestration pipeline sitting between a FastAPI REST interface and a Pinecone-backed RAG knowledge base. Every conversation gets a unique `trace_id` UUID that flows through all agent calls, KB retrievals, handover events, and structured logs.

---

## End-to-End System Flow
 
```
┌─────────────────────────────────────────────────────────┐
│                        USER                             │
│         POST /api/v1/conversation/{id}/message          │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   INPUT GUARD                           │
│  • Prompt injection regex (9 patterns)                  │
│  • Off-topic token check (40 CloudDash keywords)        │
│  • Max 4,000 character limit                            │
└──────┬──────────────────┬──────────────────────────────┘
       │ blocked          │ passed
       ▼                  ▼
  [REJECTED]   ┌─────────────────────────────────────────┐
               │           ORCHESTRATOR                  │
               │  • YAML plugin registry                 │
               │  • Loads agents via importlib           │
               │  • Max 5 handovers per conversation     │
               │  • trace_id flows through every step    │
               └─────────────────┬───────────────────────┘
                                 │ first message always
                                 ▼
               ┌─────────────────────────────────────────┐
               │            TRIAGE AGENT                 │
               │  • GPT-4o with function calling         │
               │  • classify_intent tool (structured)    │
               │  • Extracts: intent, plan, urgency,     │
               │    entities, routing_target             │
               │  • Routes to: technical | billing       │
               └──────────┬─────────────┬────────────────┘
                          │             │
              ┌───────────▼──┐     ┌────▼──────────────┐
              │  TECHNICAL   │     │     BILLING        │
              │    AGENT     │     │      AGENT         │
              │              │     │                    │
              │ Troubleshoot │     │ Invoices, plans,   │
              │ + full RAG   │     │ refund triggers    │
              │ pipeline     │     │ + RAG pipeline     │
              └──────┬───────┘     └────────┬───────────┘
                     │                      │
                     │   ┌──────────────────┘
                     │   │ refund trigger / KB miss
                     │   ▼
                     │  ┌────────────────────────────────┐
                     │  │       ESCALATION AGENT         │
                     │  │  • Terminal node (no handover) │
                     │  │  • Packages full context       │
                     │  │  • SLA by plan tier:           │
                     │  │    Enterprise 1h / Pro 8h /    │
                     │  │    Starter 3 days              │
                     │  │  • Writes to audit.jsonl       │
                     │  └──────────────┬─────────────────┘
                     │                 │
                     ▼                 │
        ┌────────────────────────┐     │
        │      RAG PIPELINE      │     │
        │                        │     │
        │  1. Query rewrite      │     │
        │     gpt-4o-mini        │     │
        │     temp=0.0           │     │
        │     last 4 turns       │     │
        │                        │     │
        │  2. Embed query        │     │
        │     llama-text-embed-v2│     │
        │     input_type=query   │     │
        │     1,024 dims         │     │
        │                        │     │
        │  3. Hybrid retrieval   │     │
        │     Pinecone dense     │     │
        │     + rank_bm25 sparse │     │
        │     fusion:            │     │
        │     0.7×dense          │     │
        │     + 0.3×BM25         │     │
        │                        │     │
        │  4. Threshold filter   │     │
        │     score ≥ 0.35 only  │     │
        │     else → escalation  │     │
        └──────────┬─────────────┘     │
                   │                   │
                   ▼                   │
        ┌────────────────────────┐     │
        │   GPT-4o RESPONSE      │     │
        │                        │     │
        │  KB chunks injected    │     │
        │  into system prompt    │     │
        │  Citations mandatory   │     │
        │  (Source: KB-XXX)      │     │
        └──────────┬─────────────┘     │
                   │                   │
                   └─────────┬─────────┘
                             │
                             ▼
               ┌─────────────────────────────────────────┐
               │            OUTPUT GUARD                 │
               │  • PII redaction (cards, SSNs)          │
               │  • Fabrication strip                    │
               │  • Grounding check + disclaimer         │
               └─────────────────┬───────────────────────┘
                                 │
                                 ▼
               ┌─────────────────────────────────────────┐
               │           RESPONSE TO USER              │
               │  { agent, text, sources, metadata }     │
               └─────────────────────────────────────────┘
```
 
---
 
## Agent Summary
 
| Agent | Model | Temp | Purpose | Can hand off to |
|---|---|---|---|---|
| Triage | GPT-4o | 0.1 | Classify intent, extract entities, route | technical, billing |
| Technical | GPT-4o | 0.2 | Troubleshooting via RAG | billing, escalation |
| Billing | GPT-4o | 0.1 | Plans, invoices, refund policy | escalation |
| Escalation | GPT-4o | 0.2 | Human handover, SLA, audit log | — (terminal) |
 
---
 
## RAG Pipeline Detail
 
```
User message (raw)
        │
        ▼
  Query rewrite          ← gpt-4o-mini, temp=0.0, last 4 turns
        │                   "still broken" → "AWS credential rotation
        │                    CloudWatch alert not firing Pro plan"
        ▼
  Embed (query type)     ← llama-text-embed-v2, input_type="query"
        │
        ├──► Pinecone dense search   (cosine similarity, top_k×2 candidates)
        │
        └──► BM25 sparse scoring     (rank_bm25, built from corpus at startup)
                │
                ▼
        Hybrid fusion score
        0.7 × dense + 0.3 × BM25_normalized
                │
                ▼
        Threshold filter (≥ 0.35)
                │
        ┌───────┴────────┐
      pass             miss
        │                │
        ▼                ▼
   Top-K chunks     needs_escalation=True
   into prompt      → route to escalation
```
 
---
 
## Handover Protocol
 
When a specialist cannot resolve the issue, `HandoverProtocol.execute()` runs:
 
```
HandoverContext snapshot
  ├── source_agent
  ├── target_agent
  ├── reason
  ├── summary        ← last 6 conversation turns + KB sources
  ├── entities       ← plan, urgency, issue_type, extracted_entities
  └── timestamp
 
→ Injected as system message prefix to receiving agent
→ Appended to logs/audit.jsonl
→ handover_count incremented (circuit breaker: max 5)
```
 
The receiving agent has full context before processing the first message. The customer never repeats themselves.
 
---

---

## Agent Architecture — Plugin Pattern

### Why YAML-driven plugins instead of hardcoded routing?

**The problem with hardcoded routing**: every time you add an agent, you touch the orchestrator. This violates open/closed principle and makes tests brittle.

**The plugin approach**: `config/agents.yaml` defines each agent's:
- Python class path (dynamically imported via `importlib`)
- System prompt
- Model + temperature
- Routing rules and allowed handover targets

The `Orchestrator` loads all agents at startup from YAML. Adding an Onboarding Agent = add one YAML entry + one Python file. Zero orchestrator changes.

```python
# Orchestrator loads agents like this:
module = importlib.import_module("agents.onboarding_agent")
cls = getattr(module, "OnboardingAgent")
agents["onboarding"] = cls(config=cfg, openai_client=client, rag=rag)
```

### Why not LangChain/LangGraph?

LangChain adds abstraction without solving the core problems here (YAML config, handover protocol, audit logging). Direct OpenAI SDK calls keep the code readable, debuggable, and dependency-light. The orchestration logic is ~80 lines — simpler than any framework would produce.

---

## RAG Pipeline

### Chunking Strategy
- Chunk size: ~300 tokens (1200 chars), 50-token (200-char) overlap
- Each article → multiple chunks → each chunk = one Pinecone vector
- Chunk metadata includes: article_id, title, category, tags, applies_to, chunk_text
- `chunk_text` stored in metadata so retrieval doesn't need a second lookup

### Embedding
- Model: `llama-text-embed-v2` (Pinecone Inference API)
- Dimensions: 4096
- Served by Pinecone directly — no separate OpenAI embedding API call or billing. `input_type="query"` for retrieval; `input_type="passage"` for ingestion.

### Hybrid Retrieval (Vector + BM25)
- **Dense retrieval**: cosine similarity via Pinecone (semantic understanding)
- **Sparse retrieval**: BM25 via `rank_bm25` (exact keyword matching — critical for product names, error codes, article IDs)
- **Fusion**: `hybrid_score = 0.7 × dense + 0.3 × BM25_normalized`
- Weights chosen empirically: semantic understanding matters more for support, but BM25 catches "KB-007", "Pro plan", "InvalidClientTokenId" exactly

### Query Rewriting
Before retrieval, a `gpt-4o-mini` call rewrites the user's query into a standalone search query using the last 4 conversation turns. This handles pronouns and references ("still not working" → "AWS CloudWatch integration credentials not working after rotation").

`gpt-4o-mini` used here (not `gpt-4o`) because this is a low-stakes reformulation task — fast and cheap.

### Similarity Threshold
Default: 0.35 (configurable via env). Below this → KB miss → escalation. This value was chosen to balance false negatives (escalating too eagerly) vs. false positives (returning irrelevant chunks).

---

## Handover Protocol

### State Transfer
The `ConversationState` Pydantic model carries:
- Full message `history` (all turns, all agents)
- Extracted `entities` dict (customer_plan, urgency, issue_type, etc.)
- `handover_context` (source, target, reason, summary, entities snapshot)
- `handover_count` (circuit-breaker: max 5 handovers)

The receiving agent gets `handover_context` injected as a system message prefix — it has full context before processing the first user message.

### Failure Handling
If a target agent raises an exception, the orchestrator catches it, logs with context, and falls back to the escalation agent. If escalation itself fails, a safe static response is returned.

### Audit Log
Every handover event is appended to `logs/audit.jsonl` as a structured JSON record:
```json
{
  "event": "handover",
  "timestamp": "2026-05-07T10:30:00",
  "trace_id": "uuid",
  "source_agent": "technical",
  "target_agent": "billing",
  "reason": "Customer wants plan upgrade",
  "context_snapshot": { ... }
}
```

---

## Guardrails

### Input Guard
1. **Prompt injection**: regex match against ~9 known injection patterns (case-insensitive). Action: block with safe message.
2. **Off-topic detection**: checks if any token in the message overlaps a CloudDash keyword set. Messages with 4+ tokens and zero overlap are redirected. This is intentionally lenient to avoid false positives.
3. **Length limit**: 4000 chars max.

### Output Guard
1. **PII redaction**: regex patterns for credit card numbers and SSNs. Applied before sending to user.
2. **Grounding check**: if response has no cited KB sources and wasn't a deliberate escalation, a disclaimer is appended noting the answer wasn't KB-grounded.
3. **Fabrication strip**: removes specific overconfident phrases ("CloudDash guarantees", "we promise 100%").

---

## Observability

- **Structured JSON logging**: every agent invocation, KB retrieval, handover, and escalation emits a JSON log line with `trace_id`, `agent`, and relevant fields.
- **Audit log**: append-only JSONL at `logs/audit.jsonl` for handover and escalation events.
- **Langfuse** (optional): set `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` to enable LLM call tracing with token counts and latency.

---

## Tech Stack Rationale

| Layer | Choice | Why this, not X |
|-------|--------|-----------------|
| LLM | GPT-4o | Best instruction following + function calling. Claude 3.5 Sonnet would be comparable; GPT-4o chosen for broader familiarity in evaluation. |
| Embeddings | llama-text-embed-v2 (Pinecone Inference) | 4096-dim, served by Pinecone — zero extra API calls. No OpenAI embedding cost; compatible with the user's existing Pinecone serverless index. |
| Vector DB | Pinecone Serverless | Zero infra, free tier, native hybrid search, generous metadata. ChromaDB was considered but adds a local-only constraint. |
| BM25 | rank_bm25 | Lightweight, no server needed. Elasticsearch/OpenSearch would be overkill for <1000 chunks. |
| API | FastAPI | Async, Pydantic-native, auto-docs. Flask lacks native async; Django is too heavy. |
| Config | YAML | Human-readable, easy to diff in PRs. JSON lacks comments; Python files mix config with logic. |
| Logging | structlog-style JSON | Machine-parseable, Langfuse/Datadog-compatible. |

---

## Production Evolution Path

1. **Session persistence**: replace in-memory `dict` with Redis (TTL-based) or PostgreSQL.
2. **Auth**: add API key middleware or JWT on FastAPI routes.
3. **Multi-tenancy**: add `org_id` to `ConversationState`; scope Pinecone queries by metadata filter.
4. **BM25 at scale**: move to Elasticsearch or Pinecone's sparse vector support when corpus exceeds ~10k chunks.
5. **Rate limiting**: `slowapi` middleware on FastAPI.
6. **Cost optimization**: cache embeddings for repeated queries; use `llama-text-embed-v2` batch inference for high-volume ingestion.
7. **Monitoring**: wire `AuditLogger.log_agent_invocation` into actual token counts from OpenAI response headers.
