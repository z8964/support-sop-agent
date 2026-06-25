# API

FastAPI backend for Support SOP Agent.

## Local Development

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate
py -3.12 -m pip install -r requirements.txt
py -3.12 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```text
GET http://localhost:8000/health
```

## Ticket APIs

```text
POST  /api/tickets
GET   /api/tickets
GET   /api/tickets/{ticket_id}
PATCH /api/tickets/{ticket_id}
POST  /api/tickets/{ticket_id}/run
GET   /api/tickets/{ticket_id}/trace
GET   /api/tickets/{ticket_id}/traces
```

Create ticket example:

```json
{
  "user_id": "U1001",
  "order_id": "OD2026001",
  "message": "我不想要了，帮我退款",
  "channel": "web"
}
```

Run ticket workflow:

```text
POST /api/tickets/T00000001/run
```

Read latest trace:

```text
GET /api/tickets/T00000001/trace
```

Read trace history:

```text
GET /api/tickets/T00000001/traces
```

## Review APIs

```text
GET  /api/reviews/pending
POST /api/reviews/{ticket_id}
GET  /api/reviews/{ticket_id}
```

Submit review example:

```json
{
  "action": "edit",
  "final_reply": "您好，该高金额退款申请已通过人工审核，我们会继续为您处理。",
  "comment": "Adjusted wording.",
  "reviewer_id": "reviewer_1"
}
```

## Memory APIs

```text
GET  /api/memory/users/{user_id}
POST /api/memory
```

Create memory example:

```json
{
  "user_id": "U1001",
  "type": "user_preference",
  "content": "Customer prefers concise replies.",
  "metadata": {
    "source": "manual"
  }
}
```

## Evaluation

Run from repository root:

```bash
py -3.12 -m evals.run
```

The report is written to:

```text
evals/report.json
```

## SOP APIs

```text
GET  /api/sops
POST /api/sops/reindex
POST /api/sops/search
```

Search example:

```json
{
  "query": "shipped order direct refund",
  "policy_type": "refund",
  "top_k": 2
}
```

The SOP service uses vector hybrid retrieval:

- chunk Markdown SOP files by section
- generate embeddings in batches
- use deterministic hash embeddings by default for zero-config local execution
- optionally use an OpenAI-compatible embedding API
- persist vectors and index metadata in SQLite
- restore a valid index after restart
- rebuild automatically when SOP content or embedding configuration changes
- filter by `policy_type`
- combine vector score and keyword score
- return source/section citations

Default local RAG configuration:

```env
RAG_EMBEDDING_PROVIDER=hash
RAG_VECTOR_STORE_BACKEND=sqlite
RAG_VECTOR_STORE_PATH=./data/sop_vectors.sqlite3
RAG_VECTOR_WEIGHT=0.7
RAG_KEYWORD_WEIGHT=0.3
```

Use a real OpenAI-compatible embedding endpoint:

```env
RAG_EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIMENSIONS=1536
```

After changing the provider, model, dimensions, or SOP files, call:

```text
POST /api/sops/reindex
```

## Mock Business APIs

```text
GET  /mock/orders/{order_id}
GET  /mock/logistics/{order_id}
GET  /mock/users/{user_id}
GET  /mock/users/{user_id}/tickets
POST /mock/escalations
```

Useful seed IDs:

```text
OD2026001: shipped order
OD2026003: high-value order
OD2026004: logistics no-update order
OD2026005: delivered order for invoice flow
```
