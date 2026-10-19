"""
Apply supabase/migrations/*.sql to the Supabase database, in file-name order,
each once. Applied names are recorded in public.schema_migrations (RLS on, no
policies: server only).

    cd backend
    python scripts/migrate.py            apply what's new
    python scripts/migrate.py --status   list applied / pending, change nothing

Needs SUPABASE_DB_URL in .env (Supabase → Project Settings → Database →
Connection string). The URL is never printed.
"""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402  (loads .env)

MIGRATIONS = config.REPO_ROOT / "supabase" / "migrations"

BOOKKEEPING = """
create table if not exists public.schema_migrations (
  name        text primary key,
  applied_at  timestamptz not null default now()
);
alter table public.schema_migrations enable row level security;
"""


def _safe(text) -> str:
    return re.sub(r"postgres(ql)?://\S+", "[db url]", config.redact(text))


def main() -> int:
    url = os.getenv("SUPABASE_DB_URL", "").strip()
    if not url:
        print("SUPABASE_DB_URL is not set in .env; nothing applied.")
        return 1
    import psycopg

    files = sorted(MIGRATIONS.glob("*.sql"))
    try:
        with psycopg.connect(url, connect_timeout=15) as conn:
            conn.execute(BOOKKEEPING)
            conn.commit()
            done = {r[0] for r in conn.execute("select name from public.schema_migrations")}
            for path in files:
                if path.name in done:
                    print(f"applied   {path.name}")
                    continue
                if "--status" in sys.argv:
                    print(f"pending   {path.name}")
                    continue
                with conn.transaction():
                    conn.execute(path.read_text(encoding="utf-8"))
                    conn.execute("insert into public.schema_migrations (name) values (%s)", (path.name,))
                print(f"APPLIED   {path.name}")
    except Exception as exc:  # noqa: BLE001
        print(f"Migration failed: {type(exc).__name__}: {_safe(exc)[:400]}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
