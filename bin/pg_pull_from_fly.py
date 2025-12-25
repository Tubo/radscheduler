"""Backup Fly.io Postgres via a short-lived fly proxy.

High-level flow:
  1) Read DATABASE_URL from a running Fly machine with:
       fly ssh console -a <FLY_APP> -C 'env'
  2) Start a temporary proxy:
       fly proxy localhost:<LOCAL_PORT> -> <FLY_PG_APP>:5432  (with --watch-stdin)
  3) pg_dump against 127.0.0.1:<LOCAL_PORT>, gzip to BACKUP_DIR
  4) Always stop the proxy (even on failure / Ctrl-C)

Required env vars:
  - FLY_APP:      Fly app to ssh into to read DATABASE_URL
  - FLY_PG_APP:   Fly Postgres app name to proxy to

Optional env vars:
  - LOCAL_PORT:   default 54321
  - BACKUP_DIR:   default ./backups

Doctests:
  Run them with:
    python -m doctest -v scripts/backup_fly_pg.py

Devenv task example (devenv.nix):
  packages = [ pkgs.flyctl pkgs.postgresql pkgs.gzip pkgs.python3 ];
  tasks."db:backup-fly".exec = ''
    python scripts/backup_fly_pg.py
  '';
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterator, Tuple
from urllib.parse import unquote, urlparse

# ------------------------------
# Pure parsing utilities
# ------------------------------

def parse_env_output(env_stdout: str) -> Dict[str, str]:
    """Parse `env` output (KEY=VALUE lines) into a dict.

    - Splits on the *first* '=' only (values can contain '=')
    - Trims whitespace
    - Strips a single pair of matching quotes around the value

    >>> parse_env_output("A=1\\nB=two words\\n") == {"A": "1", "B": "two words"}
    True

    Values may contain '=':

    >>> parse_env_output("JWT=a=b=c")["JWT"]
    'a=b=c'

    Quoted values are unwrapped once:

    >>> parse_env_output("DATABASE_URL='postgres://u:p@h:5432/db'")["DATABASE_URL"]
    'postgres://u:p@h:5432/db'
    """
    env_map: Dict[str, str] = {}
    for raw in env_stdout.splitlines():
        line = raw.strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if (len(v) >= 2) and (v[0] == v[-1]) and v[0] in ("'", '"'):
            v = v[1:-1]
        env_map[k] = v
    return env_map


def extract_database_url(env_stdout: str) -> str:
    """Extract DATABASE_URL from `env` output.

    Tries common keys first; falls back to a regex scan.

    >>> extract_database_url("DATABASE_URL=postgres://u:p@h/db")
    'postgres://u:p@h/db'

    Works even if `env` output has other variables:

    >>> extract_database_url("X=1\\nDATABASE_URL='postgres://u:p@h/db'\\nY=2")
    'postgres://u:p@h/db'

    Raises if missing:

    >>> extract_database_url("X=1\\nY=2")
    Traceback (most recent call last):
    ...
    RuntimeError: Could not find DATABASE_URL in `fly ssh console -C env` output.
    """
    env_map = parse_env_output(env_stdout)
    for key in ("DATABASE_URL", "DATABASEURL", "DATABASEURI"):
        if env_map.get(key):
            return env_map[key]

    # Fallback: regex scan (covers odd formats)
    m = re.search(r"^DATABASE_URL=(.+)$", env_stdout, flags=re.MULTILINE)
    if m:
        return m.group(1).strip().strip('"').strip("'")

    raise RuntimeError("Could not find DATABASE_URL in `fly ssh console -C env` output.")


def parse_database_url(database_url: str) -> Tuple[str, str, str]:
    """Parse DATABASE_URL and return (user, password, dbname).

    Note: URL decoding is applied to username/password.

    >>> parse_database_url('postgres://u:p@host:5432/mydb')
    ('u', 'p', 'mydb')

    URL-encoded secrets decode correctly:

    >>> parse_database_url('postgres://u:p%40ss%3Aword@host/mydb')
    ('u', 'p@ss:word', 'mydb')
    """
    p = urlparse(database_url)
    user = unquote(p.username or "")
    password = unquote(p.password or "")
    dbname = (p.path or "").lstrip("/")
    if not user or not password or not dbname:
        raise ValueError("DATABASE_URL missing user/password/dbname")
    return user, password, dbname


# ------------------------------
# Side-effecting helpers
# ------------------------------

def run_checked(cmd: list[str], *, timeout: int | None = None) -> str:
    """Run a command and return stdout. Raises with stderr on failure."""
    try:
        p = subprocess.run(
            cmd,
            timeout=timeout,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return p.stdout
    except subprocess.CalledProcessError as ex:
        msg = (ex.stderr or "").strip()
        raise RuntimeError(f"Command failed: {' '.join(cmd)} {msg}") from ex


def fetch_fly_env(*, fly_app: str) -> str:
    """Run `env` on a live Fly machine and return stdout."""
    print(f"[1/4] Fetching DATABASE_URL from Fly app '{fly_app}'...")
    result = run_checked(["fly", "ssh", "console", "-a", fly_app, "-C", "env"], timeout=60)
    print("      ✓ DATABASE_URL retrieved")
    return result


def wait_for_pg_ready(host: str, port: int, timeout_s: float = 20.0) -> None:
    """Wait until pg_isready succeeds."""
    print(f"[3/4] Waiting for Postgres to be ready at {host}:{port}...")
    deadline = time.time() + timeout_s
    attempts = 0
    while time.time() < deadline:
        try:
            subprocess.run(
                ["pg_isready", "-h", host, "-p", str(port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            print(f"      ✓ Postgres ready (after {attempts} retries)")
            return
        except subprocess.CalledProcessError:
            attempts += 1
            time.sleep(0.1)
    raise TimeoutError(f"Timed out waiting for Postgres at {host}:{port}")


@contextmanager
def fly_proxy(*, fly_pg_app: str, local_port: int) -> Iterator[None]:
    """Context manager that starts `fly proxy` and always shuts it down.

    Uses `--watch-stdin`, so closing stdin triggers a graceful exit.
    """
    print(f"[2/4] Starting fly proxy: localhost:{local_port} -> {fly_pg_app}:5432...")
    proxy = subprocess.Popen(
        ["fly", "proxy", f"{local_port}:5432", "-a", fly_pg_app, "--watch-stdin"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    print(f"      ✓ Proxy started (pid={proxy.pid})")

    def cleanup() -> None:
        print("      Shutting down proxy...")
        if proxy.poll() is not None:
            print("      ✓ Proxy already stopped")
            return
        try:
            if proxy.stdin:
                proxy.stdin.close()  # triggers --watch-stdin shutdown
        except Exception:
            pass
        # Backstop
        try:
            proxy.terminate()
        except Exception:
            pass
        try:
            proxy.wait(timeout=5)
        except Exception:
            try:
                proxy.kill()
            except Exception:
                pass
        print("      ✓ Proxy stopped")

    # Ensure Ctrl-C / SIGTERM also tears the proxy down
    def handle_sig(_sig, _frame):
        cleanup()
        raise KeyboardInterrupt

    old_int = signal.signal(signal.SIGINT, handle_sig)
    old_term = signal.signal(signal.SIGTERM, handle_sig)

    try:
        yield
    finally:
        cleanup()
        signal.signal(signal.SIGINT, old_int)
        signal.signal(signal.SIGTERM, old_term)


def pg_dump_gzip(*, db_user: str, db_pass: str, db_name: str, host: str, port: int, out_path: Path) -> None:
    """Run pg_dump against (host, port) and gzip to out_path."""
    print(f"[4/4] Running pg_dump for database '{db_name}'...")
    print(f"      Output: {out_path}")
    env = os.environ.copy()
    env["PGPASSWORD"] = db_pass

    out_path.parent.mkdir(parents=True, exist_ok=True)

    pg_dump = subprocess.Popen(
        ["pg_dump", "--no-owner", "--no-acl", "-h", host, "-p", str(port), "-U", db_user, db_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    with out_path.open("wb") as f:
        gzip = subprocess.Popen(
            ["gzip", "-c"],
            stdin=pg_dump.stdout,
            stdout=f,
            stderr=subprocess.PIPE,
        )
        assert pg_dump.stdout is not None
        pg_dump.stdout.close()  # allow SIGPIPE if gzip dies

        gz_stderr = gzip.communicate()[1]
        pg_stderr = pg_dump.communicate()[1]

    if gzip.returncode != 0:
        raise RuntimeError("gzip failed: " + (gz_stderr or b"").decode(errors="replace"))
    if pg_dump.returncode != 0:
        raise RuntimeError("pg_dump failed: " + (pg_stderr or b"").decode(errors="replace"))
    
    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"      ✓ pg_dump complete ({size_mb:.2f} MB)")


# ------------------------------
# Configuration + main
# ------------------------------

@dataclass(frozen=True)
class Config:
    fly_app: str
    fly_pg_app: str
    local_port: int = 54321
    backup_dir: Path = Path.cwd() / "backups"

    @staticmethod
    def from_env() -> "Config":
        fly_app = os.environ.get("FLY_APP")
        fly_pg_app = os.environ.get("FLY_PG_APP")
        if not fly_app:
            raise SystemExit("Set FLY_APP (Fly app to ssh into and read DATABASE_URL)")
        if not fly_pg_app:
            raise SystemExit("Set FLY_PG_APP (Fly Postgres app to proxy to)")

        local_port = int(os.environ.get("LOCAL_PORT", "54321"))
        backup_dir = Path(os.environ.get("BACKUP_DIR", Path.cwd() / "backups"))
        return Config(fly_app=fly_app, fly_pg_app=fly_pg_app, local_port=local_port, backup_dir=backup_dir)


def build_backup_path(backup_dir: Path, db_name: str, now: datetime | None = None) -> Path:
    """Create a timestamped backup path.

    >>> p = build_backup_path(Path('/tmp/backups'), 'mydb', datetime(2020, 1, 2, 3, 4, 5))
    >>> str(p).endswith('mydb.20200102_030405.sql.gz')
    True
    """
    now = now or datetime.now()
    ts = now.strftime("%Y%m%d_%H%M%S")
    return backup_dir / f"{db_name}.{ts}.sql.gz"


def backup_once(cfg: Config) -> Path:
    """Perform a single backup and return the written file path."""
    env_out = fetch_fly_env(fly_app=cfg.fly_app)
    database_url = extract_database_url(env_out)
    db_user, db_pass, db_name = parse_database_url(database_url)

    out_path = build_backup_path(cfg.backup_dir, db_name)

    with fly_proxy(fly_pg_app=cfg.fly_pg_app, local_port=cfg.local_port):
        wait_for_pg_ready("127.0.0.1", cfg.local_port, timeout_s=20.0)
        pg_dump_gzip(
            db_user=db_user,
            db_pass=db_pass,
            db_name=db_name,
            host="127.0.0.1",
            port=cfg.local_port,
            out_path=out_path,
        )

    return out_path


def main() -> None:
    cfg = Config.from_env()
    print(f"\n{'='*50}")
    print("Fly.io Postgres Backup")
    print("="*50)
    print(f"  FLY_APP:    {cfg.fly_app}")
    print(f"  FLY_PG_APP: {cfg.fly_pg_app}")
    print(f"  LOCAL_PORT: {cfg.local_port}")
    print(f"  BACKUP_DIR: {cfg.backup_dir}")
    print(f"{'='*50}\n")
    out = backup_once(cfg)
    print(f"\n{'='*50}")
    print(f"✓ Backup complete: {out}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()