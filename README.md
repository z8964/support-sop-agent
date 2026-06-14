# Support SOP Agent

An open-source customer support workflow agent that follows SOPs, calls business tools, routes risky cases to human review, and generates compliant replies.

中文定位：一个基于 LangGraph + RAG + Tool Calling 的客服工单 SOP 执行 Agent。

## Why

Customer support agents should not stop at chat. Real support work needs order lookup, logistics checks, SOP retrieval, risk control, human review, and auditable execution traces.

This project aims to provide a practical business Agent template for customer support workflows.

## Planned Features

- Ticket intent classification
- SOP retrieval with RAG
- Mock order, logistics, and user tools
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
  .gitignore
  .env.example
  LICENSE
```

## Roadmap

- [ ] Initialize backend and frontend skeleton
- [ ] Add mock business APIs
- [ ] Implement ticket CRUD
- [ ] Build SOP ingestion and retrieval
- [ ] Implement LangGraph workflow
- [ ] Add trace persistence
- [ ] Add human review flow
- [ ] Add evaluation runner

## Current Status

Phase 0 is in progress:

- [x] Repository skeleton
- [x] FastAPI backend entry point
- [x] Health check API
- [x] React/Vite frontend skeleton
- [x] Docker and Docker Compose skeleton
- [x] Mock business APIs
- [ ] Ticket CRUD APIs
