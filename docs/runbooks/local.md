# Local Runbook

Use Docker Compose for the full local stack.

```bash
docker compose up --build
```

Open:

- API health: `http://localhost:8000/health`
- Web dashboard: `http://localhost:5173`
- Kiosk mode: `http://localhost:5173?mode=kiosk`
- Metrics: `http://localhost:8000/metrics`

Local Compose uses non-secret placeholder API tokens. For protected admin endpoints, use the local analyst or admin token from `docker-compose.yml`. Do not reuse local tokens outside local development.

## Verification

```bash
python3 -m pytest
python3 -m ruff check .
python3 -m mypy apps packages db
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

For a clean database check:

```bash
docker compose down -v --remove-orphans
docker compose up -d db
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wellness_radar python3 -m db.migrate
```
