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

