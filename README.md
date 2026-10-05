# Freight Search

A local freight-search portfolio project. Only the application liveness
endpoint is implemented so far.

Use Python 3.12 and the project's existing `.venv`. From the project root,
activate the environment:

```bash
source .venv/bin/activate
```

Run tests:

```bash
python -m pytest -q
```

Run locally:

```bash
python -m uvicorn freight_search.main:app --app-dir src --host 127.0.0.1 --port 8000
```

`GET /health/live` returns HTTP 200 with `{"status": "ok"}`. This checks only
application liveness; it does not prove PostgreSQL, NATS, or OpenSearch health.
