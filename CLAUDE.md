# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Radscheduler is a Django app for rostering radiology registrars in one Canterbury (NZ) department. It handles shifts, leave requests with two-step approval, extra-duty allocation, iCal feeds, and checks rosters against the STONZ MECA employment contract. `PRODUCT.md` describes the users, domain vocabulary and product principles; read it before any user-facing work.

## Development environment

Local dev uses [devenv](https://devenv.sh/) (Nix). Prefer devenv workflows and don't add Docker-only steps. The project started from cookiecutter-django. Two pieces of that setup are kept on purpose:

- **Docker Compose** (`local.yml`, `production.yml`, `compose/`, `merge_production_dotenvs_in_dotenv.py`): an alternative dev and deploy path. Keep it in step with devenv and production when you change Python, Postgres or Node versions, dependencies or services.
- **Heroku files** (`Procfile`, `requirements.txt`, `runtime.txt`, `bin/post_compile`).

- `devenv shell`: enter the env (Python 3.13 venv, pnpm deps, git hooks).
- `devenv up`: start Postgres, Mailpit, Django (`runserver_plus`) and the webpack watcher. Migrations run automatically first. Ports are allocated dynamically; see `devenv processes list`.
- `manage <args>`: Django management commands.
- `db:pull` / `db:restore --latest --clean` / `db:refresh`: copy the Fly production database locally. The data is real staff personal data.

## Tests

Tests need Postgres. Run `pytest` inside `devenv shell` while `devenv up` is running, or use `devenv test` with `devenv up` stopped.

```bash
pytest                                                    # whole suite
pytest radscheduler/core/tests/test_views.py::TestLeaves::test_form
pytest -k fatigue
pytest --create-db                                        # after migration changes (addopts has --reuse-db)
```

- Settings: `config.settings.test` (set in `pyproject.toml`). Fixtures live in `radscheduler/conftest.py`. The `app` fixture is django-webtest with CSRF checks off.
- Test settings use `FakeWebpackLoader`, so pages render **without JS bundles**. The Playwright tests in `radscheduler/functional_tests/` don't exercise Unpoly or Alpine either. To check real Unpoly behaviour, run `pnpm build` and override `WEBPACK_LOADER` to the real loader in a test.
- Use `freezegun` for anything date-dependent.
- Three tests are `xfail(strict=True)` because of known business-logic issues. Remove the marker once the logic is fixed.
- `.github/copilot-instructions.md` asks for tests first: a Playwright E2E test for new user flows, django-webtest for views and forms, then unit tests for service/domain logic.

## Lint, format, build

- Python: **ruff only**, for lint and format (`ruff check .`, `ruff format .`). Config is in `pyproject.toml`; line length is 119 and migrations are excluded. Don't reintroduce black, isort, flake8, pylint or mypy.
- Templates: djlint (`djlint --profile=django --reformat`). JS/CSS: prettier.
- The git hooks (configured in `devenv.nix`) run ruff, djlint, prettier and `django-upgrade --target-version 5.2`.
- Frontend: `pnpm build` (production) or the `dev:webpack` process. The bundles land in `radscheduler/static/webpack_bundles/`, and `webpack-stats.json` is used by django-webpack-loader.
- Python deps: edit `pyproject.toml`, then run `pip:compile` (or `pip:upgrade`) to regenerate `requirements/local.txt` and `requirements/production.txt` with pip-tools. Don't hand-edit the `.txt` files.

## Architecture

### Layers

- **Views** (`radscheduler/core/views/`): thin, function-based views only. They parse input, call services and render templates.
- **Services** (`radscheduler/core/service.py`): ORM queries and straightforward business rules, such as building the editor's event grid, workload breakdowns and `fill_shifts`.
- **Domain** (`radscheduler/roster/`): the scheduling engine, kept free of the ORM. It uses dataclasses (`roster/models.py`), which share names with the ORM models: `Registrar`, `Shift`, `Leave` and `Status`. Only use this layer for complex algorithms; simple rules belong in services.
  - `generator.generate_shifts`: creates the unfilled shifts for a date range from a roster definition (`rosters.SingleOnCallRoster`, which also defines fatigue weights).
  - `assigner.AutoAssigner`: fills shifts, choosing registrars by fatigue with a recency bias.
  - `validators.StonzMecaValidator` / `validate_roster`: the contract rules.
  - `canterbury_holidays`: the stat-day calendar.
- **`core/domain_mapper.py`**: converts between ORM and domain objects using Django Ninja `ModelSchema` and `dacite`. Watch for the duplicate names when importing; the code uses `import ... as orm` and `as domain`.
- **API**: Django Ninja (`core/api/`). It feeds FullCalendar on the registrar calendar.
- **iCal feeds**: `core/ical.py`, cached for 15 minutes in `config/urls.py`.
- **Publishing**: a singleton `core.models.Settings` row holds `publish_start_date`/`publish_end_date`. This range limits what registrars see in the calendar API and the feeds.

### Other apps

- `paper_forms/`: fills in the hospital's PDF leave forms (`paper_forms/forms/*.pdf`) with reportlab overlays and pypdf. Triggered from a Leave admin action.
- `users/`: custom user model and django-allauth adapters.
- `core/admin.py`: much of the chief registrar's workflow runs here (leave approvals, printing, status).

### Roles

Signed-in registrars use the calendar, leave and extra-duty pages. Staff (`is_staff`) use the roster editor (`/roster/editor/`) and the extra-duty editor.

## Frontend conventions

- Server-rendered Django templates with Bootstrap 5, progressively enhanced with **Unpoly**, plus Alpine.js for small local state. Pages must work without JS. htmx has been removed; don't reintroduce it.
- Elm tooling (`elm.json`, `elm-webpack-loader`) is set up on purpose: **Elm is the planned future frontend**, even though no `.elm` sources exist yet.
- Unpoly is configured in `radscheduler/static/js/vendors.js`. Non-GET requests send the CSRF token in the `X-CSRFToken` header (read from the `csrf-token` meta tag in `base.html`), and `wrapMethod = false`, so `up-method="delete"` sends a real DELETE.
- Prefer real `<form method="post">` with `{% csrf_token %}`, `up-submit` and `up-target`. Unpoly endpoints return HTML, not JSON. A non-form element can use `up-follow up-href up-method`.
- Unpoly parses responses as full documents, which **drops a bare `<tr>`**. Views that return a single table row must wrap it in a `<table>` (see `leaves/form_inline.html` and `extra_duties/row_response.html`). The `up-target` must also match an element in the response, usually a row id like `#leave-{{ pk }}`.
- When a template is included with `{% include ... only %}`, pass `csrf_token` through explicitly. There is a regression test for this in `functional_tests/test_editor.py`.

## Deployment

Fly.io (`fly.toml`, region `syd`). A push to `main` runs `.github/workflows/fly.yml`: ruff, then pytest against Postgres, then `flyctl deploy` and a Sentry release. The image is built from `compose/production/django/Dockerfile`. Its `start` script runs `migrate` and `collectstatic` before gunicorn, so migrations deploy automatically.
