
#!/usr/bin/env python3
"""
Restore a gzipped plain-SQL Postgres backup into a local Postgres, using local DATABASE_URL.

Typical usage:
  export DATABASE_URL="postgres://user:pass@localhost:5432/mydb"
  python scripts/restore_local_pg.py backups/mydb.20251225_120000.sql.gz

Restore the latest backup automatically:
  python scripts/restore_local_pg.py --latest --backup-dir backups

Optionally wipe the target DB schema first (dangerous):
  python scripts/restore_local_pg.py --latest --clean

Notes:
- This expects backups produced as: pg_dump ... | gzip > file.sql.gz
- Uses `psql` (must be in PATH). It streams decompressed SQL into psql stdin.
"""

from __future__ import annotations

import argparse
import gzip
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse


@dataclass(frozen=True)
class DbConn:
    user: str
    password: str
    host: str
    port: int
    dbname: str

    @classmethod
    def from_url(cls, url: str) -> DbConn:
        """Parse a Postgres DATABASE_URL and URL-decode credentials."""
        p = urlparse(url)
        user, password = unquote(p.username or ""), unquote(p.password or "")
        host, port = p.hostname or "", p.port or 5432
        dbname = (p.path or "").lstrip("/")
        if not all([user, password, dbname]):
            raise ValueError("DATABASE_URL must include username, password, and db name")
        return cls(user=user, password=password, host=host, port=port, dbname=dbname)

    def psql_args(self) -> list[str]:
        """Return common psql connection arguments."""
        return ["psql", "-h", self.host, "-p", str(self.port), "-U", self.user, "-d", self.dbname, "-v", "ON_ERROR_STOP=1"]

    def env(self) -> dict[str, str]:
        """Return environment with PGPASSWORD set."""
        return {**os.environ, "PGPASSWORD": self.password}


def pick_latest_backup(backup_dir: Path) -> Path:
    """Pick the newest *.sql.gz by timestamp in filename, or by mtime."""
    candidates = list(backup_dir.glob("*.sql.gz"))
    if not candidates:
        raise FileNotFoundError(f"No *.sql.gz backups found in {backup_dir}")

    ts_re = re.compile(r"\.(\d{8}_\d{6})\.sql\.gz$")
    timestamped = [(m.group(1), p) for p in candidates if (m := ts_re.search(p.name))]
    if timestamped:
        return max(timestamped)[1]
    return max(candidates, key=lambda x: x.stat().st_mtime)


def run_psql(conn: DbConn, sql: str) -> None:
    """Run a one-off SQL command via psql."""
    subprocess.run(conn.psql_args() + ["-c", sql], check=True, env=conn.env())


def clean_target_schema(conn: DbConn) -> None:
    """
    Attempt a “wipe” of the public schema (common dev restore workflow).
    Drops all tables, sequences, views, and types in public schema.
    
    This approach works even when the user doesn't own the public schema
    (common with devenv/nix-managed Postgres).
    """
    # Drop all tables, views, sequences, and types in public schema
    # This avoids needing ownership of the schema itself
    clean_sql = """
    DO $$ 
    DECLARE
        r RECORD;
    BEGIN
        -- Drop all tables
        FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
            EXECUTE 'DROP TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' CASCADE';
        END LOOP;
        -- Drop all sequences
        FOR r IN (SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public') LOOP
            EXECUTE 'DROP SEQUENCE IF EXISTS public.' || quote_ident(r.sequence_name) || ' CASCADE';
        END LOOP;
        -- Drop all views
        FOR r IN (SELECT viewname FROM pg_views WHERE schemaname = 'public') LOOP
            EXECUTE 'DROP VIEW IF EXISTS public.' || quote_ident(r.viewname) || ' CASCADE';
        END LOOP;
        -- Drop all types (enums, etc.)
        FOR r IN (SELECT typname FROM pg_type t JOIN pg_namespace n ON t.typnamespace = n.oid WHERE n.nspname = 'public' AND t.typtype = 'e') LOOP
            EXECUTE 'DROP TYPE IF EXISTS public.' || quote_ident(r.typname) || ' CASCADE';
        END LOOP;
    END $$;
    """
    run_psql(conn, clean_sql)


def restore_backup(conn: DbConn, backup_path: Path) -> None:
    """Stream-decompress a .sql.gz backup into psql."""
    if not backup_path.exists():
        raise FileNotFoundError(str(backup_path))
    if not backup_path.suffix == ".gz" or not backup_path.stem.endswith(".sql"):
        raise ValueError("Backup file must end with .sql.gz (plain SQL gzipped)")

    with subprocess.Popen(conn.psql_args(), stdin=subprocess.PIPE, env=conn.env()) as psql:
        assert psql.stdin is not None
        with gzip.open(backup_path, "rb") as f:
            shutil.copyfileobj(f, psql.stdin)
        psql.stdin.close()
    if psql.returncode != 0:
        raise RuntimeError(f"psql exited with code {psql.returncode}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Restore a .sql.gz backup into local Postgres via DATABASE_URL.")
    ap.add_argument("backup", nargs="?", help="Path to .sql.gz backup (omit if --latest).")
    ap.add_argument("--latest", action="store_true", help="Restore the newest *.sql.gz from --backup-dir.")
    ap.add_argument("--backup-dir", default="backups", help="Directory to search when using --latest (default: backups).")
    ap.add_argument("--clean", action="store_true", help="Drop/recreate public schema before restoring (destructive).")
    args = ap.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("Set local DATABASE_URL (e.g. postgres://user:pass@localhost:5432/mydb)")

    conn = DbConn.from_url(database_url)

    if args.latest:
        backup_path = pick_latest_backup(Path(args.backup_dir))
    else:
        if not args.backup:
            raise SystemExit("Provide a backup path, or use --latest.")
        backup_path = Path(args.backup)

    print(f"Target: postgres://{conn.user}@{conn.host}:{conn.port}/{conn.dbname}")
    print(f"Backup: {backup_path}")

    if args.clean:
        print("Cleaning target schema (DROP/CREATE public)...")
        clean_target_schema(conn)

    print("Restoring...")
    restore_backup(conn, backup_path)
    print("Restore complete.")


if __name__ == "__main__":
    main()