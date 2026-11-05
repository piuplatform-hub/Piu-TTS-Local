# Repository Guidelines

## Project Structure & Module Organization

- `apps/server/` contains the FastAPI application, API v1 routes, services, models, and the durable job runner.
- `apps/web/` is the React/TypeScript Vite client; engine adapters live in `engines/`, and the shared Python SDK is in `packages/engine_sdk/`.
- `alembic/` stores database migrations. `tests/` is split into `unit/`, `contract/`, `integration/`, and `e2e/` suites.
- `scripts/` holds operational and benchmark utilities; `docs/` contains architecture, plans, reports, and runbooks; `infra/` contains Caddy configuration.
- Runtime data and secrets belong outside Git. Configure them through a local `.env` copied from `.env.example`.

## Build, Test, and Development Commands

From the repository root in PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r apps/server/requirements.txt
pip install -e packages/engine_sdk
alembic upgrade head
python -m apps.server.src.main
python -m apps.server.src.runner                 # standalone durable worker
npm ci --prefix apps/web
npm run dev --prefix apps/web
npm run build --prefix apps/web
```

Use `python -m apps.server.src.main` for the API and `npm run dev --prefix apps/web` for Vite development. The default configuration binds to `127.0.0.1`; keep that boundary for local work.

## Coding Style & Naming Conventions

Use four-space indentation, type hints, and `snake_case` for Python files, functions, and variables; use `PascalCase` for Python classes. Use two-space indentation in TypeScript/TSX, `camelCase` for values, and `PascalCase` for React components. Match surrounding code. No repository formatter or linter script is configured, so review diffs carefully and run `git diff --check`.

## Testing Guidelines

Run `pytest -q` for the full Python suite or target a layer, for example `pytest tests/unit -q` or `pytest tests/integration/test_projects_api.py -q`. Name files `test_*.py` and test functions `test_*`. Tests use isolated temporary databases; do not point them at real studio data. Build the web client with `npm run build --prefix apps/web` before UI-related review.

## Database, Security, and Configuration

Add schema changes through a new Alembic revision; do not edit applied migrations. Never commit `.env`, credentials, private keys, databases, or generated runtime data. Keep authentication, proxy, and engine changes covered by focused tests.

## Commit & Pull Request Guidelines

Use Conventional Commit messages such as `feat(ui): ...`, `fix(security): ...`, or `test(phase5b): ...`. Keep commits focused. PRs should explain behavior changes, link the issue or phase, list exact validation commands and results, call out migrations or configuration changes, and include screenshots for UI changes.
