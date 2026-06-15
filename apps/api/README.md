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
- generate deterministic embeddings
- store chunks in an in-memory vector store
- filter by `policy_type`
- combine vector score and keyword score
- return source/section citations

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
