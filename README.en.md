# Support SOP Agent

[English](./README.en.md) | [中文](./README.zh-CN.md)

An open-source customer support workflow agent that follows SOPs, calls business tools, routes risky cases to human review, and generates compliant replies.

## Why

Customer support agents should not stop at chat. Real support work needs order lookup, logistics checks, SOP retrieval, risk control, human review, and auditable execution traces.

This project aims to provide a practical business Agent template for customer support workflows.

## Planned Features

- Ticket intent classification
- SOP retrieval with RAG
- Mock order, logistics, and user tools
- Ticket CRUD APIs
- LangGraph-based stateful workflow
- Human-in-the-loop review for risky cases
- Agent execution trace timeline
- YAML-based regression evaluation

## MVP Scenarios

- Shipped order refund
- Logistics issue
- Invoice reissue

## Planned Tech Stack

- Backend: FastAPI
- Frontend: React or Next.js
- Agent workflow: LangGraph
- Vector store: Chroma
- Database: SQLite first, PostgreSQL later
- Evaluation: YAML cases + Python runner

## Local Development

### Backend

```bash
cd apps/api
py -3.12 -m pip install -r requirements.txt
py -3.12 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```text
http://localhost:8000/health
```

API docs:

```text
http://localhost:8000/docs
```

Ticket APIs:

```text
POST  /api/tickets
GET   /api/tickets
GET   /api/tickets/{ticket_id}
PATCH /api/tickets/{ticket_id}
POST  /api/tickets/{ticket_id}/run
GET   /api/tickets/{ticket_id}/trace
GET   /api/tickets/{ticket_id}/traces
```

SOP APIs:

```text
GET  /api/sops
POST /api/sops/reindex
POST /api/sops/search
```

Mock business APIs:

```text
GET  /mock/orders/{order_id}
GET  /mock/logistics/{order_id}
GET  /mock/users/{user_id}
GET  /mock/users/{user_id}/tickets
POST /mock/escalations
```

Seed examples:

```text
OD2026001: shipped refund scenario
OD2026003: high-value refund scenario
OD2026004: logistics no-update scenario
OD2026005: invoice reissue scenario
```

### Frontend

```bash
cd apps/web
npm install
npm run dev
```

The frontend runs at:

```text
http://localhost:3000
```

### Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

## Project Structure

```text
support-sop-agent/
  apps/
    api/
    web/
  knowledge_base/
  evals/
    cases/
  examples/
    tickets/
  .github/
    ISSUE_TEMPLATE/
  README.md
  README.en.md
  README.zh-CN.md
  .gitignore
  .env.example
  LICENSE
```

## Roadmap

- [x] Initialize backend and frontend skeleton
- [x] Add mock business APIs
- [x] Implement ticket CRUD
- [x] Build SOP ingestion and retrieval
- [x] Implement LangGraph workflow
- [x] Add trace persistence
- [ ] Add human review flow
- [ ] Add evaluation runner

## Current Status

Foundation APIs are ready:

- [x] Repository skeleton
- [x] FastAPI backend entry point
- [x] Health check API
- [x] React/Vite frontend skeleton
- [x] Docker and Docker Compose skeleton
- [x] Mock business APIs
- [x] Ticket CRUD APIs
- [x] Markdown SOP loading and retrieval APIs
- [x] LangGraph ticket workflow for refund, logistics, and invoice scenarios
- [x] In-memory trace persistence and trace query APIs
