from __future__ import annotations

import os
import time
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def database_url() -> str:
    return os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/wellness_radar")


def wait_for_database(url: str, attempts: int = 30) -> None:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            with psycopg.connect(url) as conn, conn.cursor() as cur:
                cur.execute("SELECT 1")
            return
        except Exception as exc:  # pragma: no cover - exercised by compose timing
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"database did not become ready: {last_error}")


def migrate() -> None:
    url = database_url()
    wait_for_database(url)
    with psycopg.connect(url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_lock(hashtext('wellness_radar_migrations'))")
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                  version TEXT PRIMARY KEY,
                  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                version = path.name
                cur.execute("SELECT 1 FROM schema_migrations WHERE version = %s", (version,))
                if cur.fetchone():
                    continue
                cur.execute(path.read_text())
                cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
                print(f"applied migration {version}")
        finally:
            cur.execute("SELECT pg_advisory_unlock(hashtext('wellness_radar_migrations'))")


if __name__ == "__main__":
    migrate()
