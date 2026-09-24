"""
Apply .sql files to whatever DATABASE_URL points at.

    uv run python scripts/db.py app/schema.sql app/seed.sql

Used locally to rebuild your Neon branch, and by CI to set up the throwaway Postgres
the tests run against.
"""

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv


def main(paths: list[str]) -> int:
    load_dotenv()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 1

    with psycopg.connect(database_url) as connection:
        for path in paths:
            sql = Path(path).read_text()
            # psycopg sends a query with no parameters using the simple protocol,
            # which is what lets one execute run a whole file of statements
            connection.execute(sql)
            print(f"applied {path}")
        connection.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
