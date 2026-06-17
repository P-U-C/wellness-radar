# Vancouver Wellness Radar

Map-first market intelligence for public Metro Vancouver wellness signals.

This repository currently implements the Phase 0 / Milestone 1 vertical slice:

```text
City of Vancouver business licences
  -> raw_payload
  -> normalize
  -> bc_gate
  -> PostGIS operator/source_event/signal
  -> FastAPI read API
  -> React + MapLibre dashboard
```

## Run

```bash
docker compose up --build
```

Services:

- API: http://localhost:8000/health
- Web: http://localhost:5173
- PostGIS: localhost:5432

The jobs service applies migrations, ingests the City of Vancouver business licence source, and then idles as a simple scheduler placeholder for the next milestone.

## Local Checks

```bash
python3 -m pytest
python3 -m ruff check .
python3 -m mypy apps packages db
pnpm install
pnpm lint
pnpm typecheck
pnpm test
```
