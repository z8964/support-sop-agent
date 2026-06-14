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

