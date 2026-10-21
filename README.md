# Pulse

Multi-tenant platform for availability monitoring and incident management.
The canonical project context and roadmap are in [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md).

## Project status

M1 adds organization registration, session authentication, role-based access control,
member management, and tenant-scoped monitor configuration to the M0 foundation.
The React dashboard uses a TypeScript client generated from FastAPI's OpenAPI schema.
Schedulers, HTTP checks, and incidents belong to later milestones; configured monitors
do not yet report availability.

Read the [M1 implementation walkthrough](docs/M1_IMPLEMENTATION.md) for a detailed
explanation in Portuguese, the [M1 validation record](docs/M1_VALIDATION.md) for executed
checks, and [M0 validation](docs/M0_VALIDATION.md) for the historical foundation.

## First use

Start the Docker stack, open http://localhost:8080, and choose **Criar uma organização**.
Provide a display name, a lowercase organization slug, your name, email, and a password
of 15–128 characters. Sign in using the same organization slug and email.
Create a public HTTP(S) monitor from **Novo monitor**. Owners and admins can manage
members from **Pessoas e acessos**. The interface is currently in Portuguese.

| Role | Monitor access | Member management |
| --- | --- | --- |
| owner | Read/write | Admin, operator, viewer |
| admin | Read/write | Operator and viewer |
| operator | Read/write | None |
| viewer | Read-only | None |

Monitor updates and deletion require the current `config_version`; stale versions
return 409. Cross-tenant resources return 404. API documentation is available at `/docs`.

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
The environment example also documents cookie security, session duration, and allowed
origins. Set `PULSE_COOKIE_SECURE=true` and explicit HTTPS origins when deploying behind TLS.

- Frontend: http://localhost:8080
- OpenAPI/Swagger: http://localhost:8000/docs
- Liveness: http://localhost:8000/api/v1/health/live
- Readiness: http://localhost:8000/api/v1/health/ready
- Prometheus metrics: http://localhost:8000/metrics

Compose waits for the database, runs migrations in a separate process, and starts the API.
PostgreSQL and Redis do not publish ports by default. Application ports are bound
to `127.0.0.1` only.

Nginx overwrites forwarded client-IP/protocol headers. Uvicorn trusts only nginx's
fixed `PULSE_PROXY_IP` on the dedicated proxy network, never every container or
arbitrary client headers. The standalone backend image disables proxy headers.
If `PULSE_PROXY_SUBNET` conflicts with a VPN or another project, change it together
with `PULSE_PROXY_DYNAMIC_RANGE` and `PULSE_PROXY_IP` in `.env`. Keep the fixed IP
inside the subnet but outside the dynamic range, so the API cannot take it before
nginx starts. Each simultaneous
stack needs a distinct proxy subnet. Clients behind the same NAT still share an IP
bucket; adding a CDN/load balancer requires a separately reviewed trust chain.

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

Generate the API contract and TypeScript types after changing API DTOs or routes:

```powershell
npm run api:generate
```

This requires the backend virtual environment created by `uv sync --frozen`.
The artifacts are `contracts/openapi.json` and `frontend/src/shared/api/schema.d.ts`.
Do not edit generated types manually. CI runs `npm run api:check` to detect drift.
The application uses `/api/v1`; incompatible changes require an explicit versioning plan.

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
M1 adds `alembic check`, migration rollback/reapplication on the fresh CI database,
tenant-isolation and RBAC scenarios against PostgreSQL, and a real-transaction test
with concurrent writes to the same monitor version.

With the full stack and development database ports running, the opt-in deployment
regression uses two temporary containers with different real source IPs:

```powershell
# From backend/. Set COMPOSE_PROJECT_NAME if using a non-default Compose project.
$env:PULSE_PROXY_INTEGRATION = "1"
uv run --env-file ../.env pytest tests/integration/test_proxy_identity.py -v
Remove-Item Env:PULSE_PROXY_INTEGRATION
```

It verifies separate login/registration buckets, nginx header overwriting, and
rejection of spoofed headers on direct API connections. It removes its temporary
containers and test records; it never flushes Redis or deletes application data.
CI runs this test after building and starting nginx and Uvicorn.

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
    features/identity/       # tenants, users, sessions, RBAC, CSRF, and auth throttling
    features/monitors/       # versioned monitor configuration and tenant-scoped repositories
  migrations/                # Alembic history; core + telemetry in one cluster
  tests/                     # unit, HTTP, and real integration tests
frontend/
  src/app/                   # application composition and global styles
  src/features/system-health/# contract, HTTP adapter, hook, and components
  src/features/identity/     # account forms, members, and typed HTTP gateway
  src/features/monitors/     # monitor editor, paginated dashboard, and typed gateway
  src/shared/api/            # generated OpenAPI types and shared client
  src/shared/ui/             # reusable UI components
compose.yaml                 # default local stack
compose.dev.yaml             # optional host access to dependencies
.github/workflows/ci.yaml     # quality checks, integration, and builds
docs/adr/                    # decisions and review criteria
contracts/openapi.json       # generated API contract
scripts/export-contract.mjs  # deterministic backend contract export
```

Read the [conventions](docs/CONVENTIONS.md), [modular monolith ADR](docs/adr/0001-monolito-modular.md),
and [infrastructure ADR](docs/adr/0018-base-local-e-ci.md) before adding features.
These supporting documents are currently written in Portuguese.

## Current limitations

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
- Authentication uses revocable HttpOnly cookie sessions with CSRF protection and
  Redis throttling. Password recovery/change, email verification, MFA, invitation
  links, and compromised-password screening are not implemented. Administrators
  currently set initial member passwords; complete these identity flows before
  exposing the application to real users. See [ADR 0019](docs/adr/0019-sessoes-e-autenticacao.md).
- Tenant isolation is enforced by application policies and scoped queries, without RLS.
  Monitor URL validation is preliminary; workers must still enforce SSRF protection
  at execution time, including DNS resolution, redirects, and rebinding.
- Member-role changes revoke the target user's sessions. Ownership transfer and
  automatic removal of expired sessions are deferred. Offset pagination does not
  provide a stable snapshot during concurrent edits.
- Session reads take no row locks. Requests already authorized may finish with
  their previous role; subsequent requests after revocation commits are denied.
- The per-account login limit can be deliberately exhausted to deny new logins to
  a known tenant/email. This accepted M1 limitation and future mitigations are
  documented in ADR 0019; trusted-device/backoff mitigations are not implemented.
- Stored monitor configurations remain readable when input policies evolve.
  Future rule changes need an explicit migration/invalid-state plan and worker-side
  safety checks; loading a historical configuration does not authorize its execution.
- PostgreSQL connections use libpq TCP timeouts and keepalives in addition to
  connection and statement timeouts. Socket option support depends on the OS.
  These protect against lost TCP traffic; they are not an overall readiness deadline
  or a timeout for a server that keeps acknowledging TCP while its process is stalled.
  See [libpq connection parameters](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-PARAMKEYWORDS).
