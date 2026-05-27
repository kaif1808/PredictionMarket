# Repository Guidelines

## Project Structure & Module Organization

This repository implements the Valdoria prediction market experiment. Backend code lives in `server/`: `server.py` exposes the FastAPI and Socket.io app, `orchestrator.py` manages session state, and `lmsr.py`, `bayesian.py`, `roles.py`, and `scenarios.py` hold domain logic. Database migrations are in `alembic/`. The React/Vite client is in `client/src/`, with screens under `client/src/views/`, shared API/socket helpers under `client/src/lib/`, and event types in `client/src/types/`. Tests are in `tests/`. Analysis, calibration, and operational scripts live in `analysis/`, `calibration/`, and `scripts/`; deployment notes are in `docs/`.

## Build, Test, and Development Commands

- `python3 -m venv .venv && source .venv/bin/activate`: create and enter a local Python environment.
- `pip install -r requirements.txt`: install backend, analysis, and test dependencies.
- `alembic upgrade head`: apply database migrations.
- `uvicorn server.server:combined_app --reload --port 8000`: run the backend locally.
- `cd client && npm install && npm run dev`: install and run the frontend dev server.
- `cd client && npm run build`: build the production frontend served by FastAPI at `/app`.
- `pytest`: run the Python test suite.
- `./scripts/run_local_smoke.sh`: run backend tests, frontend typecheck/build, migrations, readiness checks, and reconnect smoke coverage.

## Coding Style & Naming Conventions

Use Python 3 with four-space indentation, type hints where they clarify contracts, and small domain-focused functions. Keep backend runtime code out of `analysis/` and `calibration/`. Use React function components in PascalCase, helpers in camelCase, and TypeScript event contracts in `client/src/types/events.ts`. Keep environment-driven behavior in `server/config.py`; avoid scattering raw `os.environ` reads.

## Testing Guidelines

Add or update tests in `tests/` for backend behavior, orchestration, LMSR math, roles, API boundaries, and socket contracts. Name files `test_<feature>.py` and prefer focused end-to-end coverage when state transitions or persistence are involved. For frontend contract changes, run `npm run typecheck` inside `client/`. Use `pytest -k "<keyword>" -v` for targeted runs.

## Commit & Pull Request Guidelines

Recent history uses short imperative commits such as `deploy fix` and `update package.json`; keep messages concise and action-oriented. PRs should explain the user-visible change, list validation commands run, note migration or environment changes, and include screenshots for UI changes. Link issues or experiment-readiness gaps when relevant.

## Security & Configuration Tips

Do not commit secrets, local databases, or generated evidence outputs unless intentionally documenting a run. Review `ALLOWED_ORIGINS`, `COOKIE_SECURE`, `DATABASE_URL`, and `TOURNAMENT_TIE_BREAK_MODE` before deployment. Run `python3 scripts/deployment_readiness_check.py --strict-env` for production-style validation.
