# Radscheduler

A rostering program for Radiology Registrars.

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Black code style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

License: MIT

## Development Setup with devenv

This project uses [devenv](https://devenv.sh/) for local development. It provides:

- Python 3.11 with virtual environment
- PostgreSQL database
- Node.js with pnpm
- Mailpit for email testing
- flyctl for Fly.io deployments

### Getting Started

1. Install [devenv](https://devenv.sh/getting-started/)
2. Clone the repository and enter the directory
3. Run `devenv shell` to enter the development environment
4. Run `devenv up` to start all services (PostgreSQL, Mailpit, Django, Webpack)

### Available Scripts

| Command             | Description                                             |
| ------------------- | ------------------------------------------------------- |
| `manage <args>`     | Run Django management commands (e.g., `manage migrate`) |
| `db:pull`           | Pull a backup from Fly.io production database           |
| `db:restore <file>` | Restore a backup to local database                      |

## Database Backup & Restore

### Pull a Backup from Fly.io

The `db:pull` script automates the entire backup process:

1. Fetches `DATABASE_URL` from the Fly.io app via SSH
2. Starts a temporary proxy to the Fly Postgres database
3. Runs `pg_dump` and compresses the output
4. Saves the backup to `backups/` directory

```bash
# Simply run:
db:pull

# Or directly:
python bin/pg_pull_from_fly.py
```

Environment variables (pre-configured in devenv.nix):

- `FLY_APP`: The Fly app to SSH into (default: `radscheduler`)
- `FLY_PG_APP`: The Fly Postgres app (default: `radscheduler-db`)
- `LOCAL_PORT`: Local port for proxy (default: `54321`)
- `BACKUP_DIR`: Where to save backups (default: `./backups`)

### Restore a Backup Locally

The `db:restore` script restores a gzipped SQL backup to your local database:

```bash
# Restore the latest backup (cleans the database first):
db:restore --latest

# Restore a specific backup:
db:restore backups/radscheduler.20251225_120000.sql.gz

# Restore without cleaning (may cause conflicts):
db:restore --latest --no-clean
```

Or run directly:

```bash
python bin/pg_restore.py --latest --clean
python bin/pg_restore.py backups/mybackup.sql.gz
```

Options:

- `--latest`: Automatically pick the newest `*.sql.gz` from `--backup-dir`
- `--backup-dir`: Directory to search for backups (default: `backups`)
- `--clean`: Drop all tables/sequences/views before restoring (recommended)

The script uses `DATABASE_URL` from your environment (automatically set by devenv)
