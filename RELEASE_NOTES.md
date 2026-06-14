# Release Notes

## v0.1.0

Initial usable release of Support SOP Agent.

### Highlights

- FastAPI backend with health check and API docs.
- React/Vite web demo for ticket workflow execution.
- Mock business APIs for orders, logistics, users, ticket history, and escalations.
- Ticket CRUD APIs.
- Markdown SOP knowledge base and retrieval APIs.
- LangGraph ticket workflow:
  - intent classification
  - context building
  - SOP retrieval
  - decision generation
  - reply generation
  - ticket status update
- Trace persistence and trace query APIs.
- Human review workflow with approve, edit, reject, and escalate actions.
- YAML evaluation runner with regression cases.
- Bilingual README: English and Simplified Chinese.

### Quick Start

```bash
cp .env.example .env
docker compose up --build
```

Open:

```text
Web UI:   http://localhost:3000
API docs: http://localhost:8000/docs
```

### Verification

Backend tests:

```bash
cd apps/api
py -3.12 -m pytest tests
```

Evaluation runner:

```bash
py -3.12 -m evals.run
```

Expected evaluation summary:

```text
{"total": 4, "passed": 4, "failed": 0}
```

### Known Limitations

- Uses in-memory services instead of persistent database storage.
- SOP retrieval currently uses lightweight keyword scoring, not embeddings.
- Agent decisions are deterministic for the MVP and do not yet call a real LLM.
- Mock APIs simulate business systems and are not connected to real CRM/order/logistics services.

