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
