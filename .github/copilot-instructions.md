You are GitHub Copilot working inside a scheduler web app repo.

## Project identity

- This project started from cookiecutter-django and originally used Docker for dev.
- Local development has been migrated to devenv (prefer devenv workflows; do not introduce new Docker-only steps unless explicitly asked).
- Frontend: server-rendered HTML using Django templates + django-template-partials, enhanced with Unpoly and Alpine.js.
- Backend: Django + Django Ninja for APIs.
- Views: function-based views only.
- Architecture rule: keep business logic out of views. Views should validate/parse input, call services/domain, and return responses.

## Testing is mandatory (TDD required)

Always propose/produce tests first unless explicitly asked otherwise.
Testing order and scope:

1. E2E: Playwright (preferred starting point for new user flows).
2. Integration: django-webtest for view/service integration and form behavior.
3. Unit: fast unit tests for services and pure functions.

When implementing features or fixing bugs:

- Start by writing a failing test that demonstrates the desired behavior.
- Then implement the minimal code to make it pass.
- Add edge cases and regression tests where relevant.
- Keep tests deterministic; avoid time-dependent flakiness (freeze time or inject clocks when needed).

## Layering rules

### Views (function-based)

- Thin and boring by design.
- No database-heavy loops or scheduling logic inside views.
- No direct complex computations in templates.
- Use Django Ninja only for API endpoints; still keep business logic in services/domain.

### Service layer (default for most business logic)

- Put simple business rules in services (e.g., create/update roster entry, apply a straightforward policy).
- Services may coordinate ORM queries and call helper functions.
- Services should be testable: accept explicit inputs, return useful outputs, keep side effects controlled.

### Domain-driven design (only for complex algorithms)

- Use DDD when implementing complex scheduling/optimization/analytics logic.
- The domain app is `roster`.
- In `roster`, model complex concepts with domain models/value objects, invariants, and explicit domain services.
- Keep domain logic as pure as practical (minimize Django ORM coupling inside the deepest domain logic).
- For simple logic, do NOT create domain models—keep it in the service layer.

## Code style and patterns

- Prefer explicitness over cleverness.
- Type hints are welcome where they improve clarity, especially in services/domain boundaries.
- Keep functions small; name things based on domain meaning, not implementation details.
- Handle validation near boundaries (views/api), not deep in the domain unless it’s an invariant.
- Avoid introducing new frameworks or architectural patterns not already in use.

## Unpoly + Alpine conventions

- Prefer progressive enhancement: baseline works without JS; Unpoly/Alpine improve UX.
- Use django-template-partials for reusable fragments.
- Unpoly endpoints should return partial HTML fragments, not JSON, unless it’s a Ninja API.
- Keep Alpine state small and localized; do not build an SPA.

## When generating code

For any new feature/endpoint/behavior:

1. Identify the user-visible behavior and write an E2E Playwright test.
2. Add a django-webtest integration test for the relevant view(s).
3. Add unit tests for service/domain logic.
4. Implement: view → service → (optional domain in `roster` if complex).
5. Keep the PR minimal; avoid drive-by refactors unless necessary for the change.

If a request is ambiguous, make the smallest reasonable assumption and encode it in a test expectation.
Document any non-obvious assumptions in comments in the test.
