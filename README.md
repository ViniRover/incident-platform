# Pulse

Multi-tenant platform for availability monitoring and incident management.
The canonical project context and roadmap are in [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md).

## Project status

M0 provides a runnable foundation with React/TypeScript, FastAPI, PostgreSQL/TimescaleDB,
and Redis. The diagnostics screen queries the real API and displays dependency failures.
Authentication, tenants, monitors, the scheduler, workers, and incidents will be implemented
in later milestones. The original roadmap decisions remain in effect.
Local validation results and pending integration checks are recorded in
[docs/M0_VALIDATION.md](docs/M0_VALIDATION.md).

## Run with Docker

Prerequisites: Git, Docker Desktop with the Linux engine running, and Docker Compose v2 or later.
Run from the repository root:

```powershell
Copy-Item .env.example .env
docker compose up -d --build --wait
```

On Linux/macOS, use `cp .env.example .env`. The example credentials are for local
development only. If you change the username, password, or database, also update
`PULSE_DATABASE_URL` for development outside containers. Passwords included in the URL
must be URI-encoded. Changing environment variables does not update users in an
already initialized PostgreSQL volume.

The API and migrations require both `PULSE_DATABASE_URL` and `PULSE_REDIS_URL`.
Missing settings fail validation before startup. Compose supplies both values;
host-side commands load them explicitly from `.env`.

- Frontend: http://localhost:8080
- OpenAPI/Swagger: http://localhost:8000/docs
- Liveness: http://localhost:8000/api/v1/health/live
- Readiness: http://localhost:8000/api/v1/health/ready
- Prometheus metrics: http://localhost:8000/metrics

Compose waits for the database, runs migrations in a separate process, and starts the API.
PostgreSQL and Redis do not publish ports by default. Application ports are bound
to `127.0.0.1` only.

```powershell
docker compose ps
docker compose logs -f api
docker compose down
```

`down` preserves volumes. Do not use `down -v` if you need to retain the data.

## Development with live reload

Additional prerequisites: Node.js 24 LTS, Python 3.12 or 3.13, and uv 0.12.20.
Lockfiles are version-controlled; install dependencies using the frozen commands below.

From the repository root, start only the dependencies with local ports exposed:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml up -d --wait postgres redis
```

In a backend terminal:

```powershell
cd backend
uv sync --frozen --python 3.12
uv run --env-file ../.env alembic upgrade head
uv run --env-file ../.env uvicorn pulse.main:create_app --factory --reload
```

Python 3.13 is also supported (`--python 3.13`). Do not run both API instances on the
same port. If the full stack is already running, stop `frontend` and `api` before
starting live reload mode.

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to the local API; Nginx does the same
in the Docker stack. There is no need to enable CORS globally.

## Quality checks and tests

Backend, from `backend/`:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest -m "not integration" --cov=pulse --cov-fail-under=80
```

Frontend, from `frontend/`:

```powershell
npm run lint
npm test
npm run build
```

Integration tests require the services from `compose.dev.yaml` and applied migrations.
From `backend/`, in PowerShell:

```powershell
uv run --env-file ../.env alembic upgrade head
$env:PULSE_INTEGRATION = "1"
uv run --env-file ../.env pytest -m integration -v
Remove-Item Env:PULSE_INTEGRATION
```

In Bash: `PULSE_INTEGRATION=1 uv run --env-file ../.env pytest -m integration -v`.
The CI workflow creates a fresh database, reapplies `upgrade head`, verifies the schemas
and extension, builds both images, and tests proxy communication, API recreation,
Redis failure/recovery, and packet loss on an established PostgreSQL connection.
The packet-loss check runs on Linux and installs a temporary firewall rule only in
the test API container's network namespace, removing it when the step exits.

## Failure demonstration

With the full stack running:

```powershell
docker compose stop redis
curl.exe -i http://localhost:8000/api/v1/health/ready
curl.exe -i http://localhost:8000/api/v1/health/live
docker compose start redis
docker compose up -d --wait
```

Expected result: readiness returns `503` with `redis: false`, while liveness remains
`200`. After recovery, readiness returns `200` again. The screen lets you check
again. In Bash, use `curl` instead of `curl.exe`.

## Project structure

```text
backend/
  src/pulse/
    main.py                  # application composition and lifecycle
    platform/                # configuration and shared infrastructure resources
    features/health/         # use case, contract, adapters, DI, and routes
  migrations/                # Alembic history; core + telemetry in one cluster
  tests/                     # unit, HTTP, and real integration tests
frontend/
  src/app/                   # application composition and global styles
  src/features/system-health/# contract, HTTP adapter, hook, and components
  src/shared/ui/             # reusable UI components
compose.yaml                 # default local stack
compose.dev.yaml             # optional host access to dependencies
.github/workflows/ci.yaml     # quality checks, integration, and builds
docs/adr/                    # decisions and review criteria
```

Read the [conventions](docs/CONVENTIONS.md), [modular monolith ADR](docs/adr/0001-monolito-modular.md),
and [infrastructure ADR](docs/adr/0018-base-local-e-ci.md) before adding features.
These supporting documents are currently written in Portuguese.

## M0 limitations

- Compose is the foundation for local development and CI; production deployment is covered in M9.
- The local PostgreSQL user can install the extension. Production must separate
  migration credentials from application credentials.
- Images use version tags; digest pinning and automated updates should be included
  when preparing for production.
- Redis uses AOF and `noeviction`, but remains outside the source of truth. Outbox
  handling and cache reconstruction belong to later milestones.
- Basic HTTP metrics are available, without the full tracing planned for M5.
  Prometheus, Grafana, and OpenTelemetry collection will be added in that milestone.
- Scheduler and worker processes will be added as entrypoints in the same package
  when their respective milestones are implemented.
- PostgreSQL connections use libpq TCP timeouts and keepalives in addition to
  connection and statement timeouts. Socket option support depends on the OS.
  These protect against lost TCP traffic; they are not an overall readiness deadline
  or a timeout for a server that keeps acknowledging TCP while its process is stalled.
  See [libpq connection parameters](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-PARAMKEYWORDS).
