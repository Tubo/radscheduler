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
pytest -k rules
pytest --create-db                                        # after migration changes (addopts has --reuse-db)
```

- Settings: `config.settings.test` (set in `pyproject.toml`). Fixtures live in `radscheduler/conftest.py`. The `app` fixture is django-webtest with CSRF checks off.
- Test settings use `FakeWebpackLoader`, so pages render **without JS bundles**. The Playwright tests in `radscheduler/functional_tests/` don't exercise Unpoly or Alpine either. To check real Unpoly behaviour, run `pnpm build` and override `WEBPACK_LOADER` to the real loader in a test.
- Use `freezegun` for anything date-dependent.
- One test is `xfail(strict=True)` because of a known business-logic issue (no `(date, registrar)` uniqueness on `Shift`). Remove the marker once the logic is fixed.
- `.github/copilot-instructions.md` asks for tests first: a Playwright E2E test for new user flows, django-webtest for views and forms, then unit tests for service/domain logic.

## Lint, format, build

- Python: **ruff only**, for lint and format (`ruff check .`, `ruff format .`). Config is in `pyproject.toml`; line length is 119 and migrations are excluded. Don't reintroduce black, isort, flake8, pylint or mypy.
- Templates: djlint (`djlint --profile=django --reformat`). JS/CSS: prettier.
- The git hooks (configured in `devenv.nix`) run ruff, djlint, prettier and `django-upgrade --target-version 5.2`.
- Frontend: `pnpm build` (production), or the `dev:webpack` and `dev:elm` processes in `devenv up`. Webpack bundles the JS and CSS into `radscheduler/static/webpack_bundles/` (`webpack-stats.json` is read by django-webpack-loader). Elm is compiled by elm-watch, not webpack (`elm-watch.json`), into `radscheduler/static/elm-build/`, which a separate `<script>` tag loads; `pnpm build` runs `elm-watch make --optimize`, minified by `elm-watch-postprocess.mjs`.
- Python deps: edit `pyproject.toml`, then run `pip:compile` (or `pip:upgrade`) to regenerate `requirements/local.txt` and `requirements/production.txt` with pip-tools. Don't hand-edit the `.txt` files.

## Architecture

### Layers

- **Views** (`radscheduler/core/views/`): thin, function-based views only. They parse input, call services and render templates.
- **Services** (`radscheduler/core/service.py`): ORM queries and straightforward business rules, such as building the editor's event grid and workload breakdowns.
- **Domain** (`radscheduler/roster/`): roster rules, kept free of the ORM. It uses dataclasses (`roster/models.py`), which share names with the ORM models: `Registrar`, `Shift`, `Leave` and `Status`. Only use this layer for complex algorithms; simple rules belong in services.
  - `rules.check_roster`: checks each registrar's shifts, leave and statuses and returns `Violation`s, each with the clause it breaks. Rules are plain functions over shift times (`models.SHIFT_HOURS`); each contract (`rules.STONZ`, `rules.RDA`) is a tuple of the same rules with its own parameters and clause numbers bound, chosen by `Registrar.contract`, and `rules.DEPARTMENT` holds the department's own rules. `rules.DEPARTMENT_VARIANCES` records limits the department has agreed with the registrars and union to go past: a covered violation is still returned, with `variance` set to the reason, and the editor API returns those under `variances` instead of `violations`. Ordinary 8–5 weekdays aren't stored: `check_roster` infers them (`OrdinaryDay`) for its `period` on weekdays with no shift, leave or public holiday, so pass the period and shifts from either side of it. The Elm editor shows its results through `service.roster_violations` (`/api/editor/roster` and `/api/editor/roster/checks`); the old template editor doesn't use it. The agreement text is not in the repo.
  - `canterbury.canterbury_holidays`: the stat-day calendar.
  - There is no automatic roster generation; the chief registrar builds rosters by hand in the editor.
- **`core/domain_mapper.py`**: converts between ORM and domain objects using Django Ninja `ModelSchema` and `dacite`. Watch for the duplicate names when importing; the code uses `import ... as orm` and `as domain`.
- **API**: Django Ninja (`core/api/`). `roster_calendar.py` feeds FullCalendar on the registrar calendar; `editor.py` is the staff-only API behind the Elm roster editor (session auth, so writes need the `X-CSRFToken` header). Operation ids are the view function names in camelCase, which become the Elm client's function names.
- **iCal feeds**: `core/ical.py`, cached for 15 minutes in `config/urls.py`.
- **Publishing**: a singleton `core.models.Settings` row holds `publish_start_date`/`publish_end_date`. This range limits what registrars see in the calendar API and the feeds.

### Other apps

- `paper_forms/`: fills in the hospital's PDF leave forms (`paper_forms/forms/*.pdf`) with reportlab overlays and pypdf. Triggered from a Leave admin action.
- `users/`: custom user model and django-allauth adapters.
- `core/admin.py`: much of the chief registrar's workflow runs here (leave approvals, printing, status).

### Roles

Signed-in registrars use the calendar, leave and extra-duty pages. Staff (`is_staff`) use the roster editor (`/roster/editor/`) and the extra-duty editor. Who may decide leave comes from groups, in `core/roles.py` (`leave_approvers`): the "Director of Training" group makes only the `dot` decision, "Office Staff" none, and other staff both. The leave PATCH endpoints refuse a decision the user can't make, the Elm pages disable it, and the admin hides its action. Migration `0013` creates the groups; live-server tests empty the database, so tests use `get_or_create` for them.

## Frontend conventions

- Server-rendered Django templates with Bootstrap 5, progressively enhanced with **Unpoly**, plus Alpine.js for small local state. Pages must work without JS, except the Elm roster editor. htmx has been removed; don't reintroduce it.
- **Elm is the future frontend.** The roster editor is being rebuilt in Elm at `/roster/editor/next/` (hand-written code in `radscheduler/static/elm/src/`, start-up in `static/js/editor_elm.js`, styles `static/css/editor_elm.scss`), loading everything from `/api/editor/` and drawing menus only when opened; the old template editor at `/roster/editor/` stays until it's replaced. `pnpm install` runs `elm-tooling install` to link `elm` and `elm-format`. Format with `elm-format`. In development the `dev:elm` process (`elm-watch hot`) shows compile errors on the page and hot-reloads the editor without losing its state; the first visit after it starts compiles and reloads once. Its WebSocket uses the page's hostname, so it works from other machines too (e.g. over Tailscale). The Playwright tests in `functional_tests/test_editor_elm.py` use the real bundles, so run `pnpm build` first.
- **Don't hand-write API types or decoders in Elm.** The client in `static/elm/generated/` (`Radscheduler.Api`, `.Types`, `.Json`) is generated from the Ninja schema by `elm-open-api`: after changing the API, run `devenv shell -- elm:api` and commit `static/elm/openapi.json` and `generated/`. `test_openapi.py` fails until you do. `openapi-overrides.json` makes the client send `X-CSRFToken` instead of setting the session cookie, which browsers forbid. The generator decodes every response body, so endpoints return JSON rather than an empty 204 (deleting a shift returns the deleted shift).
- Unpoly is configured in `radscheduler/static/js/vendors.js`. Non-GET requests send the CSRF token in the `X-CSRFToken` header (read from the `csrf-token` meta tag in `base.html`), and `wrapMethod = false`, so `up-method="delete"` sends a real DELETE.
- Prefer real `<form method="post">` with `{% csrf_token %}`, `up-submit` and `up-target`. Unpoly endpoints return HTML, not JSON. A non-form element can use `up-follow up-href up-method`.
- Unpoly parses responses as full documents, which **drops a bare `<tr>`**. Views that return a single table row must wrap it in a `<table>` (see `leaves/form_inline.html` and `extra_duties/row_response.html`). The `up-target` must also match an element in the response, usually a row id like `#leave-{{ pk }}`.
- When a template is included with `{% include ... only %}`, pass `csrf_token` through explicitly. There is a regression test for this in `functional_tests/test_editor.py`.

## Deployment

Fly.io (`fly.toml`, region `syd`). A push to `main` runs `.github/workflows/fly.yml`: ruff, then pytest against Postgres, then `flyctl deploy` and a Sentry release. The image is built from `compose/production/django/Dockerfile`. Its `start` script runs `migrate` and `collectstatic` before gunicorn, so migrations deploy automatically.
