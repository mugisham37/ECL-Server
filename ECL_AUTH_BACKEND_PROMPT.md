# ECL Platform — Auth Backend Engineering Brief v2
### Production-Ready FastAPI Auth Module · Cursor AI Optimized · Full Build Prompt

> **Version:** 2.0 — polished for Cursor AI agent workflows
> **Scope:** Authentication, registration, authorization, and session management — Module 1 of 5
> **Frontend reference:** `../ECL-Web/` folder — READ ONLY, never modify
> **Backend target:** `./` folder — all code lives here
> **Analyzed frontend commit:** ECL-Web @ 970cfd9

---

## Table of Contents

0. [Cursor AI Agent Operating Instructions](#0-cursor-ai-agent-operating-instructions)
1. [Workspace Layout](#1-workspace-layout)
2. [Engineering Context](#2-engineering-context)
3. [Frontend Auth Contract](#3-frontend-auth-contract)
4. [Tech Stack & Rationale](#4-tech-stack--rationale)
5. [Production Dependencies](#5-production-dependencies)
6. [Repository Structure](#6-repository-structure)
7. [Database Schema](#7-database-schema)
8. [API Endpoint Inventory](#8-api-endpoint-inventory)
9. [Error Code Registry](#9-error-code-registry)
10. [Pagination Pattern](#10-pagination-pattern)
11. [Security Architecture](#11-security-architecture)
12. [Email & Notification Flows](#12-email--notification-flows)
13. [Background Task Architecture](#13-background-task-architecture)
14. [Caching Strategy](#14-caching-strategy)
15. [Rate Limiting & Account Lockout](#15-rate-limiting--account-lockout)
16. [Module Build Order & Git Workflow](#16-module-build-order--git-workflow)
17. [Makefile — Developer Commands](#17-makefile--developer-commands)
18. [Environment Configuration](#18-environment-configuration)
19. [Production Readiness Checklist](#19-production-readiness-checklist)
20. [Frontend Integration Guide](#20-frontend-integration-guide)
21. [Testing Strategy](#21-testing-strategy)
22. [Architecture Diagram](#22-architecture-diagram)

---

## 0. Cursor AI Agent Operating Instructions

> **Read this section first. It governs how every agent and composer session must behave throughout this entire project.**

### 0.1 You Are a Senior Engineering Team

You are not a code autocomplete tool. You are acting as a senior backend engineering team building a production-grade FastAPI authentication service for a real financial platform. Every decision must be made as if millions of users depend on this system — because they will. Hold yourself to that standard at every line.

### 0.2 Workspace Rule — ABSOLUTE

The parent directory contains two sibling folders:

```
ECL/
├── ECL-Web/        ← FRONTEND (Next.js). READ ONLY. Never create, modify, or delete any file here.
└── ECL-Server/     ← BACKEND (FastAPI). All your work happens here.
```

**`../ECL-Web/` is a reference library, not a working directory.** You read it to understand what the frontend expects. You never touch it. If you ever find yourself about to write to a file inside `../ECL-Web/`, stop immediately and re-read this rule.

### 0.3 How to Reference the Frontend

Before implementing any endpoint or Pydantic schema, open and read the corresponding frontend files. Use Cursor's `@file` reference syntax to pull them into context:

| Before building... | Read this frontend file |
|---|---|
| Any auth endpoint | `@../ECL-Web/src/app/actions/auth.ts` |
| Registration / login schemas | `@../ECL-Web/src/lib/auth-schema.ts` |
| User / tenant types | `@../ECL-Web/src/lib/dashboard-types.ts` |
| Member management types | `@../ECL-Web/src/lib/admin-types.ts` |
| Session / profile types | `@../ECL-Web/src/lib/settings-types.ts` |
| Platform admin types | `@../ECL-Web/src/lib/superadmin-types.ts` |
| Password rules | `@../ECL-Web/src/lib/use-password-strength.ts` |
| Invite form behavior | `@../ECL-Web/src/components/auth/InviteForm.tsx` |
| Forgot/reset behavior | `@../ECL-Web/src/components/auth/ForgotForm.tsx` |

**Every response shape you design must exactly match what these files expect.** Field names, casing, nesting — all must align precisely.

### 0.4 Cursor Agent Rules File

Create the following file in the server project at `ECL-Server/.cursor/rules/ecl-backend.mdc` before writing any code:

```markdown
---
description: ECL backend engineering rules — always active
globs: ["**/*.py", "**/*.toml", "**/*.ini", "**/*.env*"]
alwaysApply: true
---

# ECL Backend Rules

## Workspace
- NEVER read, write, or reference files in ../ECL-Web/ for modification purposes
- You MAY read ../ECL-Web/ files to understand frontend contracts
- ALL code changes happen inside ECL-Server/ only

## Code Quality
- All Python files must pass ruff check and mypy --strict before being considered done
- No `# type: ignore` without an inline comment explaining why
- All async functions must use `async def` — no sync DB calls in async context
- All DB queries go through SQLAlchemy ORM — no raw SQL strings

## Architecture
- Service layer (service.py) contains all business logic — routers only handle HTTP
- Dependencies (dependencies.py) handle auth, DB sessions, permissions — never inline these
- Pydantic schemas live in schemas.py — never use SQLAlchemy models as API responses
- Enums live in core/enums.py — never define an enum inline in a router or service

## Git Discipline (CRITICAL)
- After completing each checkbox in the build phases, run: git add -p (stage hunks individually)
- Then commit with the exact message format specified in Section 16
- Do NOT batch multiple features into one commit
- Do NOT commit broken/untested code — tests must pass before committing

## Testing
- Every endpoint must have at least one happy-path test and one test per error case
- Use real PostgreSQL — never mock the database
- Tests must pass before the commit for that feature

## Security (Never Compromise)
- Never log passwords, tokens, or secrets in plaintext
- Never return stack traces to the client in production
- Always hash tokens before storing in DB
- Always run password hash even when user is not found (timing attack prevention)
```

### 0.5 Cursor Background Agent Instructions

When launching a Background Agent for a build phase, give it this preamble:

```
You are building the ECL Platform backend auth module. Your full specification is in
ECL-Server/ECL_AUTH_BACKEND_PROMPT.md. The frontend reference (read-only) is in ../ECL-Web/.

Your job for this session: [INSERT PHASE NAME AND CHECKBOX LIST FROM SECTION 16]

Rules:
1. Read the relevant frontend files listed in Section 0.3 before writing schemas
2. Follow the exact module structure in Section 6
3. After each checkbox is done and tests pass, run git add and commit
4. Never modify ../ECL-Web/
5. When you finish, show me: which checkboxes are done, which tests passed, and what commits were made
```

### 0.6 Git Discipline — Non-Negotiable

- **After every feature or sub-feature is working and tested:** `git add` the relevant files (use `-p` to stage by hunk if needed), then commit immediately
- **Commit message format:** `<type>(<scope>): <description>` — see Section 16
- **Never push** — the engineer reviews and pushes manually
- **Never squash in-progress** — each atomic unit of work gets its own commit
- **Never commit:** `.env`, `*.pyc`, `__pycache__/`, generated keys

---

## 1. Workspace Layout

```
ECL/                                    ← Parent project directory
│
├── ECL-Web/                                ← FRONTEND — READ ONLY
│   ├── src/
│   │   ├── app/
│   │   │   ├── (auth)/                 ← Auth pages: sign-in, sign-up, etc.
│   │   │   ├── actions/
│   │   │   │   └── auth.ts             ← ⭐ ALL frontend→backend call stubs live here
│   │   │   └── api/auth/[...nextauth]/ ← NextAuth handler
│   │   ├── components/auth/            ← Auth form components (source of UX truth)
│   │   │   ├── LoginForm.tsx
│   │   │   ├── SignUpForm.tsx
│   │   │   ├── ForgotForm.tsx
│   │   │   ├── ResetForm.tsx
│   │   │   └── InviteForm.tsx
│   │   └── lib/
│   │       ├── auth-schema.ts          ← ⭐ Zod schemas — mirrors your Pydantic models
│   │       ├── auth.ts                 ← NextAuth config
│   │       ├── dashboard-types.ts      ← Tenant, AppShellUser types
│   │       ├── admin-types.ts          ← Member, MemberRole, MemberStatus types
│   │       ├── settings-types.ts       ← Session, UserProfile types
│   │       └── superadmin-types.ts     ← PlatformUser, TenantPlan types
│   └── middleware.ts                   ← Protected route prefixes
│
└── ECL-Server/                             ← BACKEND — all your work here
    ├── .cursor/
    │   └── rules/
    │       └── ecl-backend.mdc         ← Cursor rules (create first — see Section 0.4)
    ├── app/                            ← FastAPI application
    ├── migrations/                     ← Alembic
    ├── tests/                          ← pytest
    ├── docker/
    ├── scripts/
    ├── Makefile
    └── pyproject.toml
```

### Starting a Session

When you open Cursor for the first time in this project:
1. Open the `ECL/` parent folder as the workspace root (not `./` alone)
2. Pin this file (`ECL-Server/ECL_AUTH_BACKEND_PROMPT.md`) in a Cursor Notepad tab so it is always in context
3. Keep `../ECL-Web/src/app/actions/auth.ts` and `../ECL-Web/src/lib/auth-schema.ts` open as reference tabs

---

## 2. Engineering Context

### What ECL Is

ECL Platform is a multi-tenant SaaS for financial institutions computing Expected Credit Losses under IFRS 9. Each institution is a **tenant** (workspace). Within a tenant, users hold one of three roles. Above all tenants sits a **platform superadmin** layer.

### The Module-by-Module Philosophy

The backend is built flow by flow, mirroring the frontend's modular architecture. This document covers **Module 1: Auth** only.

| Module | Domain | Status |
|---|---|---|
| **1 (this doc)** | Auth, Registration, Invites, Sessions | Build now |
| 2 | Runs — ECL computation jobs | Future |
| 3 | Results — ECL output explorer | Future |
| 4 | Admin — member/config management | Future |
| 5 | Platform — superadmin console | Stub in Module 1 |

Each module is independently buildable, testable, and deployable.

### Multi-Tenancy Model

```
Platform (global)
└── Tenant / Workspace  (e.g. "Zenith Bank")
    ├── Administrator   — full workspace control, can invite
    ├── Analyst         — create/view runs and results
    └── Reviewer        — read-only on runs and results

One user email can belong to N tenants with different roles.
Active tenant is encoded in the JWT and switchable without re-login.
```

### Current Frontend State

All five auth server actions in `../ECL-Web/src/app/actions/auth.ts` are stubbed. The NextAuth credentials provider accepts any well-formed email and password. This backend replaces every stub with a real, hardened API.

---

## 3. Frontend Auth Contract

> This section is your specification. Every schema, response shape, and behavior listed here comes directly from reading the frontend source code. Keep this open while building.

### 3.1 Page → Action → Endpoint Map

```
Frontend Page                  Server Action        Backend Endpoint
────────────────────────────────────────────────────────────────────────────────
/sign-up                    → signUpAction()     → POST  /api/v1/auth/register
/sign-in                    → loginAction()      → POST  /api/v1/auth/login
/forgot-password            → forgotAction()     → POST  /api/v1/auth/forgot-password
/reset-password?token=      → resetAction()      → POST  /api/v1/auth/reset-password
/invite?token=&org=&inviter= → inviteAction()    → GET   /api/v1/invites/validate/{token}
                                                   POST  /api/v1/invites/accept
```

### 3.2 Form Field Contracts (from `../ECL-Web/src/lib/auth-schema.ts`)

**RegisterRequest**
```
companyName   string   min 2 chars        → creates Tenant record
email         string   valid email        → creates User, role = administrator
name          string   min 2 chars        → user display name
password      string   ≥8 chars, ≥1 letter, ≥1 number
confirm       string   must equal password  (validated client-side; omit from backend request)
terms         bool     must be true         (client-side only; omit from backend request)
```

**LoginRequest**
```
email         string   valid email
password      string   non-empty
remember      bool?    optional, default false → drives refresh token expiry (7d vs 24h)
```

**ForgotPasswordRequest**
```
email         string   valid email
```

**ResetPasswordRequest**
```
token         string   raw token from URL ?token=
password      string   ≥8 chars, ≥1 letter, ≥1 number
confirm       string   must equal password  (client-side; omit from backend)
```

**AcceptInviteRequest**
```
token         string   raw invite token from URL
name          string   min 2 chars
password      string   ≥8 chars, ≥1 letter, ≥1 number
confirm       string   must equal password  (client-side; omit from backend)
terms         bool     must be true          (client-side; omit from backend)
```

### 3.3 Password Strength Rules (from `../ECL-Web/src/lib/use-password-strength.ts`)

The backend MUST enforce the same rules the frontend shows the user. Validation failure returns `422` with a list of which rules failed.

| Rule key | Description | Required |
|---|---|---|
| `len8` | At least 8 characters | Yes |
| `mix` | Contains ≥1 letter AND ≥1 digit | Yes |
| `name` | Does NOT contain (case-insensitive): user's name parts, org name parts, "ecl", "platform" | Yes |
| `len12` | At least 12 characters | No — recommended only |

Also check against the HaveIBeenPwned API (k-anonymity prefix method) — fail with a clear message if the password appears in a known breach dataset.

### 3.4 Response Shapes the Frontend Consumes

**Auth success (login, register, invite accept):**
```json
{
  "data": {
    "access_token": "eyJ...",
    "token_type": "bearer",
    "expires_in": 900,
    "user": {
      "id": "01HXXX",
      "email": "jane@zenith.com",
      "name": "Jane Smith",
      "role": "administrator",
      "tenant_id": "01HYYY",
      "tenant_name": "Zenith Bank",
      "is_email_verified": true
    }
  },
  "message": "Login successful"
}
```

**Invite validate (GET):**
```json
{
  "data": {
    "email": "newuser@example.com",
    "tenant_name": "Zenith Bank",
    "inviter_name": "Jane Smith",
    "role": "analyst",
    "expires_at": "2026-06-10T12:00:00Z"
  }
}
```

**Member list (from `../ECL-Web/src/lib/admin-types.ts: Member`):**
```json
{
  "data": [
    {
      "id": "01HXXX",
      "name": "Jane Smith",
      "email": "jane@zenith.com",
      "initials": "JS",
      "role": "administrator",
      "status": "active",
      "last_active": "2026-06-03T10:30:00Z",
      "is_you": true
    }
  ],
  "meta": { "total": 5, "page": 1, "per_page": 50 }
}
```

**Session list (from `../ECL-Web/src/lib/settings-types.ts: Session`):**
```json
{
  "data": [
    {
      "id": "01HAAA",
      "device_type": "laptop",
      "device_name": "Chrome on macOS",
      "last_active_at": "2026-06-03T10:30:00Z",
      "current": true
    }
  ]
}
```

**Error responses (all errors follow this envelope):**
```json
{
  "code": "INVALID_CREDENTIALS",
  "detail": "Invalid email or password.",
  "field": null
}
```
Field-level errors include the `field` key. See Section 9 for the full error code registry.

### 3.5 Protected Routes (from `../ECL-Web/middleware.ts`)

The frontend guards these prefixes: `/dashboard`, `/runs`, `/results`, `/admin`, `/account`, `/setup`. The backend does not enforce routing — this is purely for context. JWT validation is the backend's concern.

---

## 4. Tech Stack & Rationale

### Core

| Layer | Choice | Rationale |
|---|---|---|
| Framework | **FastAPI** (latest stable) | Async-native, automatic OpenAPI, Python type hints, highest Python HTTP performance |
| ASGI server (dev) | **Uvicorn** | Auto-reload, async |
| Process manager (prod) | **Gunicorn** + uvicorn workers | Worker management, graceful restart, CPU utilization |
| ORM | **SQLAlchemy 2.0** (async) | Production-proven, native async in v2, first-class Alembic support, full control |
| DB driver | **asyncpg** | Fastest async PostgreSQL driver, binary protocol, ~3× faster than psycopg2 |
| Migrations | **Alembic** | SQLAlchemy-native, auto-generation, rollback support |
| Validation | **Pydantic v2** | Built into FastAPI, extreme performance, strict mode |
| Settings | **pydantic-settings** | Type-safe env var loading, `.env` file support |

### Database & Caching

| Layer | Choice | Rationale |
|---|---|---|
| Primary DB | **PostgreSQL 16** | ACID, JSONB, row-level security, partial indexes, battle-tested at scale |
| Cache / Token Store | **Redis 7** | Sub-millisecond reads, atomic ops, pub/sub, TTL native — perfect for token blacklist and rate limiting |
| Connection pooling | **SQLAlchemy pool** (dev) + **PgBouncer** (prod) | PgBouncer in transaction mode prevents connection exhaustion under load |

### Auth & Security

| Layer | Choice | Rationale |
|---|---|---|
| Password hashing | **argon2-cffi** (Argon2id) | Winner of Password Hashing Competition 2015; GPU/ASIC resistant; superior to bcrypt and scrypt |
| JWT | **python-jose[cryptography]** | RS256 asymmetric signing — private key signs, public key verifies; safe to publish public key |
| Token strategy | Access 15 min + Refresh 7 day (rotated) | Short-lived access limits exposure window; refresh rotation detects token theft |
| Rate limiting | **slowapi** | Starlette/FastAPI native, Redis-backed, per-route granularity, custom key functions |
| HIBP | **httpx** (async) to `api.pwnedpasswords.com` | k-anonymity prefix method — never sends full password hash |

### Background & Email

| Layer | Choice | Rationale |
|---|---|---|
| Task queue | **Celery** (Redis broker) | Industry standard, battle-tested at scale, retry/backoff, scheduled tasks |
| Email | **fastapi-mail** | Async SMTP, Jinja2 templates, SendGrid-compatible |
| Scheduler | **Celery Beat** | Cron-style cleanup tasks (expire tokens, purge stale sessions) |

### Observability

| Layer | Choice | Rationale |
|---|---|---|
| Logging | **structlog** | JSON-structured, bound context, compatible with Datadog/CloudWatch/Loki |
| Errors | **sentry-sdk[fastapi]** | Real-time error tracking, performance monitoring, release tagging |
| Metrics | **prometheus-fastapi-instrumentator** | `/metrics` endpoint for Prometheus/Grafana |

### Developer Tooling

| Tool | Purpose |
|---|---|
| **ruff** | Linting + formatting (replaces flake8, black, isort — 10–100× faster) |
| **mypy** (strict mode) | Static type checking |
| **pre-commit** | Runs ruff + mypy before every commit — blocks bad code from entering history |
| **pytest** + **pytest-asyncio** | Async test support |
| **httpx** | Async ASGI test client |
| **factory-boy** + **faker** | Realistic test fixtures without boilerplate |
| **bandit** | Python SAST security scanning |

---

## 5. Production Dependencies

### `pyproject.toml` — complete dependency list

```toml
[project]
name = "ecl-backend"
version = "1.0.0"
requires-python = ">=3.12"

[project.dependencies]
# ── Web Framework ──────────────────────────────────────────────────────────────
fastapi = {extras = ["standard"], version = ">=0.115"}  # includes uvicorn, httpx, pydantic
uvicorn = {extras = ["standard"], version = ">=0.30"}
gunicorn = ">=22.0"

# ── Database ───────────────────────────────────────────────────────────────────
sqlalchemy = {extras = ["asyncio"], version = ">=2.0"}
asyncpg = ">=0.29"
alembic = ">=1.13"
psycopg2-binary = ">=2.9"          # sync driver for alembic --autogenerate

# ── Validation & Settings ──────────────────────────────────────────────────────
pydantic-settings = ">=2.3"
email-validator = ">=2.1"          # pydantic EmailStr support

# ── Auth & Security ────────────────────────────────────────────────────────────
argon2-cffi = ">=23.1"             # Argon2id password hashing
python-jose = {extras = ["cryptography"], version = ">=3.3"}
cryptography = ">=42.0"            # RSA key generation

# ── Rate Limiting ──────────────────────────────────────────────────────────────
slowapi = ">=0.1.9"

# ── Caching ────────────────────────────────────────────────────────────────────
redis = {extras = ["hiredis"], version = ">=5.0"}   # hiredis = C extension, ~10× faster parsing

# ── Background Tasks ──────────────────────────────────────────────────────────
celery = {extras = ["redis"], version = ">=5.4"}
flower = ">=2.0"                   # Celery monitoring dashboard

# ── Email ──────────────────────────────────────────────────────────────────────
fastapi-mail = ">=1.4"
jinja2 = ">=3.1"

# ── HTTP Client (HIBP + internal) ─────────────────────────────────────────────
httpx = ">=0.27"

# ── Observability ──────────────────────────────────────────────────────────────
structlog = ">=24.0"
sentry-sdk = {extras = ["fastapi"], version = ">=2.0"}
prometheus-fastapi-instrumentator = ">=7.0"

# ── Utilities ──────────────────────────────────────────────────────────────────
python-ulid = ">=3.0"              # Sortable, URL-safe IDs
pytz = ">=2024.1"
user-agents = ">=2.2"              # Parse User-Agent strings for session device info

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-asyncio>=0.23",
  "pytest-cov>=5.0",
  "factory-boy>=3.3",
  "faker>=25.0",
  "ruff>=0.5",
  "mypy>=1.10",
  "pre-commit>=3.7",
  "bandit>=1.7",
  "locust>=2.29",                  # Load testing
]
```

---

## 6. Repository Structure

```
server/
│
├── .cursor/
│   └── rules/
│       └── ecl-backend.mdc            # Cursor rules — create this FIRST (see Section 0.4)
│
├── app/
│   ├── __init__.py
│   ├── main.py                        # FastAPI factory, lifespan, middleware + router registration
│   ├── config.py                      # pydantic-settings: typed env vars with validation
│   ├── database.py                    # Async engine, AsyncSessionLocal, Base, get_db dependency
│   ├── dependencies.py                # get_current_user, require_admin, require_platform_admin
│   │
│   ├── modules/
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── router.py              # HTTP layer only — no business logic here
│   │   │   ├── service.py             # All auth business logic (pure async functions)
│   │   │   ├── schemas.py             # Pydantic request/response models
│   │   │   └── models.py              # SQLAlchemy: User, PasswordResetToken, EmailVerificationToken
│   │   │
│   │   ├── tenants/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── schemas.py
│   │   │   └── models.py              # SQLAlchemy: Tenant, TenantMembership
│   │   │
│   │   ├── invites/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── schemas.py
│   │   │   └── models.py              # SQLAlchemy: Invitation
│   │   │
│   │   ├── sessions/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── schemas.py
│   │   │   └── models.py              # SQLAlchemy: RefreshToken, Session
│   │   │
│   │   └── platform/
│   │       ├── __init__.py
│   │       ├── router.py              # SuperAdmin endpoints — guarded by is_platform_admin
│   │       ├── service.py
│   │       ├── schemas.py
│   │       └── models.py              # No new models — reads from users + tenants
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py                # Argon2id hash/verify, JWT create/decode, token hashing
│   │   ├── email.py                   # fastapi-mail client + template rendering
│   │   ├── hibp.py                    # Have I Been Pwned k-anonymity check (async httpx)
│   │   ├── cache.py                   # Redis client, blacklist_token, is_blacklisted, rate_key helpers
│   │   ├── limiter.py                 # slowapi Limiter instance + custom key functions
│   │   ├── exceptions.py              # ECLException base + typed subclasses, global exception handlers
│   │   ├── enums.py                   # UserRole, MemberStatus, TenantPlan, TenantStatus, DeviceType
│   │   ├── pagination.py              # PageParams, Page[T] generic response model
│   │   └── middleware.py              # RequestID injection, timing header, structured access log
│   │
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── celery_app.py              # Celery factory with Redis broker
│   │   ├── email_tasks.py             # send_reset_email, send_invite_email, send_welcome_email
│   │   └── cleanup_tasks.py           # expire tokens, purge revoked refresh tokens (Celery Beat)
│   │
│   └── templates/                     # Jinja2 HTML email templates
│       ├── base_email.html            # ECL branded base layout (inline CSS, #6D4AFF)
│       ├── welcome.html
│       ├── verify_email.html
│       ├── reset_password.html
│       ├── password_changed.html
│       ├── invite_member.html
│       └── welcome_to_tenant.html
│
├── migrations/
│   ├── env.py                         # Alembic async env with SQLAlchemy 2.0 pattern
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_auth_schema.py
│
├── tests/
│   ├── conftest.py                    # Engine, session fixture (rollback pattern), test client, factories
│   ├── factories.py                   # factory-boy: UserFactory, TenantFactory, MembershipFactory, etc.
│   │
│   ├── test_core/
│   │   ├── test_security.py           # hash, verify, JWT encode/decode, token hashing
│   │   └── test_hibp.py               # HIBP k-anonymity (mock httpx)
│   │
│   ├── test_auth/
│   │   ├── test_register.py
│   │   ├── test_login.py
│   │   ├── test_forgot_password.py
│   │   ├── test_reset_password.py
│   │   ├── test_refresh_token.py
│   │   └── test_logout.py
│   │
│   ├── test_invites/
│   │   ├── test_validate_invite.py
│   │   ├── test_accept_invite.py
│   │   └── test_send_invite.py
│   │
│   ├── test_sessions/
│   │   └── test_session_management.py
│   │
│   └── test_tenants/
│       ├── test_tenant_crud.py
│       └── test_member_management.py
│
├── docker/
│   ├── Dockerfile                     # Multi-stage: python:3.12-slim builder → distroless production
│   ├── docker-compose.yml             # postgres + redis + app + celery-worker + celery-beat + flower
│   └── docker-compose.test.yml        # Isolated postgres + redis for CI
│
├── scripts/
│   ├── generate_keys.py               # Generate RSA-2048 key pair for JWT (run once at setup)
│   ├── seed_superadmin.py             # Create platform superadmin account
│   └── seed_dev_data.py               # Seed realistic development data (2 tenants, 5 users)
│
├── Makefile                           # Developer commands (see Section 17)
├── alembic.ini
├── pyproject.toml
├── .env.example
├── .pre-commit-config.yaml
└── README.md
```

---

## 7. Database Schema

### Design Principles

- **Primary keys:** ULIDs (`python-ulid`) — sortable, URL-safe, no coordination needed, better index locality than random UUIDs
- **Timestamps:** All `TIMESTAMPTZ` in UTC — never `TIMESTAMP WITHOUT TIME ZONE`
- **Soft deletes:** `deleted_at TIMESTAMPTZ NULL` on `users` and `tenants` — never hard-delete a user
- **Token storage:** All token strings stored as `SHA-256(raw_token)` hex — the raw token travels over the wire exactly once
- **`updated_at` trigger:** Use a PostgreSQL trigger (`set_updated_at`) applied to every table — Alembic migration includes trigger DDL
- **Partial indexes:** Used heavily to keep index size small (e.g., `WHERE deleted_at IS NULL`, `WHERE status = 'pending'`)

---

### `users`

```sql
Column               Type          Nullable   Default        Notes
──────────────────────────────────────────────────────────────────────────────────
id                   TEXT          NOT NULL   (ULID)         PK
email                TEXT          NOT NULL                  UNIQUE via partial index
name                 TEXT          NOT NULL
hashed_password      TEXT          NOT NULL                  Argon2id hash string
is_active            BOOLEAN       NOT NULL   true
is_email_verified    BOOLEAN       NOT NULL   false
is_platform_admin    BOOLEAN       NOT NULL   false
failed_login_count   INTEGER       NOT NULL   0              Increment on failed auth
locked_until         TIMESTAMPTZ   NULL                      NULL = not locked
last_login_at        TIMESTAMPTZ   NULL
created_at           TIMESTAMPTZ   NOT NULL   NOW()
updated_at           TIMESTAMPTZ   NOT NULL   NOW()          Managed by trigger
deleted_at           TIMESTAMPTZ   NULL                      Soft delete

INDEXES
  users_email_active_idx   UNIQUE (email)        WHERE deleted_at IS NULL
  users_locked_idx         (locked_until)        WHERE locked_until IS NOT NULL
```

---

### `tenants`

```sql
Column               Type          Nullable   Default        Notes
──────────────────────────────────────────────────────────────────────────────────
id                   TEXT          NOT NULL   (ULID)         PK
name                 TEXT          NOT NULL
slug                 TEXT          NOT NULL                  URL-safe, UNIQUE
plan                 TEXT          NOT NULL   'trial'        CHECK IN (trial,starter,growth,enterprise)
status               TEXT          NOT NULL   'trial'        CHECK IN (trial,active,suspended)
currency             TEXT          NOT NULL   'USD'
reporting_cadence    TEXT          NOT NULL   'monthly'      CHECK IN (monthly,quarterly)
timezone             TEXT          NOT NULL   'UTC'          Valid IANA tz string
created_at           TIMESTAMPTZ   NOT NULL   NOW()
updated_at           TIMESTAMPTZ   NOT NULL   NOW()
deleted_at           TIMESTAMPTZ   NULL

INDEXES
  tenants_slug_active_idx  UNIQUE (slug)     WHERE deleted_at IS NULL
  tenants_status_idx       (status)
```

---

### `tenant_memberships`

```sql
Column               Type          Nullable   Default        Notes
──────────────────────────────────────────────────────────────────────────────────
id                   TEXT          NOT NULL   (ULID)         PK
user_id              TEXT          NOT NULL                  FK → users(id) ON DELETE CASCADE
tenant_id            TEXT          NOT NULL                  FK → tenants(id) ON DELETE CASCADE
role                 TEXT          NOT NULL                  CHECK IN (administrator,analyst,reviewer)
status               TEXT          NOT NULL   'active'       CHECK IN (active,disabled)
joined_at            TIMESTAMPTZ   NOT NULL   NOW()
created_at           TIMESTAMPTZ   NOT NULL   NOW()
updated_at           TIMESTAMPTZ   NOT NULL   NOW()

CONSTRAINTS
  memberships_unique   UNIQUE (user_id, tenant_id)

INDEXES
  memberships_user_idx          (user_id)
  memberships_tenant_idx        (tenant_id)
  memberships_tenant_active_idx (tenant_id, status)   WHERE status = 'active'
```

---

### `invitations`

```sql
Column               Type          Nullable   Default        Notes
──────────────────────────────────────────────────────────────────────────────────
id                   TEXT          NOT NULL   (ULID)         PK
email                TEXT          NOT NULL
tenant_id            TEXT          NOT NULL                  FK → tenants(id) ON DELETE CASCADE
invited_by_user_id   TEXT          NOT NULL                  FK → users(id)
role                 TEXT          NOT NULL                  CHECK IN (administrator,analyst,reviewer)
token_hash           TEXT          NOT NULL                  UNIQUE — SHA-256 of raw token
status               TEXT          NOT NULL   'pending'      CHECK IN (pending,accepted,expired,cancelled)
expires_at           TIMESTAMPTZ   NOT NULL                  NOW() + 7 days at creation
accepted_at          TIMESTAMPTZ   NULL
created_at           TIMESTAMPTZ   NOT NULL   NOW()
updated_at           TIMESTAMPTZ   NOT NULL   NOW()

INDEXES
  invitations_token_hash_idx     UNIQUE (token_hash)
  invitations_email_tenant_idx   (email, tenant_id)
  invitations_tenant_status_idx  (tenant_id, status)
  invitations_pending_expiry_idx (expires_at)   WHERE status = 'pending'
```

---

### `password_reset_tokens`

```sql
Column               Type          Nullable   Default        Notes
──────────────────────────────────────────────────────────────────────────────────
id                   TEXT          NOT NULL   (ULID)         PK
user_id              TEXT          NOT NULL                  FK → users(id) ON DELETE CASCADE
token_hash           TEXT          NOT NULL                  UNIQUE — SHA-256 of raw token
expires_at           TIMESTAMPTZ   NOT NULL                  NOW() + 1 hour
used_at              TIMESTAMPTZ   NULL
created_at           TIMESTAMPTZ   NOT NULL   NOW()

INDEXES
  prt_token_hash_idx  UNIQUE (token_hash)
  prt_user_idx        (user_id)
  prt_active_idx      (expires_at)    WHERE used_at IS NULL
```

---

### `email_verification_tokens`

```sql
Column               Type          Nullable   Default        Notes
──────────────────────────────────────────────────────────────────────────────────
id                   TEXT          NOT NULL   (ULID)         PK
user_id              TEXT          NOT NULL                  FK → users(id) ON DELETE CASCADE
token_hash           TEXT          NOT NULL                  UNIQUE
expires_at           TIMESTAMPTZ   NOT NULL                  NOW() + 24 hours
verified_at          TIMESTAMPTZ   NULL
created_at           TIMESTAMPTZ   NOT NULL   NOW()

INDEXES
  evtoken_hash_idx  UNIQUE (token_hash)
  evtoken_user_idx  (user_id)
```

---

### `refresh_tokens`

```sql
Column               Type          Nullable   Default        Notes
──────────────────────────────────────────────────────────────────────────────────
id                   TEXT          NOT NULL   (ULID)         PK
user_id              TEXT          NOT NULL                  FK → users(id) ON DELETE CASCADE
token_family_id      TEXT          NOT NULL                  Groups tokens from same login event
token_hash           TEXT          NOT NULL                  UNIQUE — SHA-256 of raw token
is_revoked           BOOLEAN       NOT NULL   false
expires_at           TIMESTAMPTZ   NOT NULL
last_used_at         TIMESTAMPTZ   NULL
created_at           TIMESTAMPTZ   NOT NULL   NOW()

INDEXES
  rt_token_hash_idx   UNIQUE (token_hash)
  rt_user_idx         (user_id)
  rt_family_idx       (token_family_id)
  rt_user_active_idx  (user_id)   WHERE is_revoked = false
```

---

### `sessions`

Maps directly to `../ECL-Web/src/lib/settings-types.ts: Session` for the frontend Settings → Sessions UI.

```sql
Column               Type          Nullable   Default        Notes
──────────────────────────────────────────────────────────────────────────────────
id                   TEXT          NOT NULL   (ULID)         PK
user_id              TEXT          NOT NULL                  FK → users(id) ON DELETE CASCADE
refresh_token_id     TEXT          NOT NULL                  FK → refresh_tokens(id) ON DELETE CASCADE
device_type          TEXT          NOT NULL                  CHECK IN (laptop,phone,unknown)
device_name          TEXT          NULL                      Parsed from User-Agent (e.g. "Chrome on macOS")
browser              TEXT          NULL
ip_address_hash      TEXT          NOT NULL                  HMAC-SHA256 of IP (privacy preserving)
country              TEXT          NULL                      GeoIP lookup (optional)
last_active_at       TIMESTAMPTZ   NOT NULL   NOW()
created_at           TIMESTAMPTZ   NOT NULL   NOW()

INDEXES
  sessions_user_idx         (user_id)
  sessions_rt_idx           (refresh_token_id)
  sessions_user_active_idx  (user_id, last_active_at DESC)
```

---

### Entity Relationship Diagram

```
                    ┌─────────────────────┐
                    │       users         │
                    ├─────────────────────┤
                    │ id (PK, ULID)       │
                    │ email               │
                    │ name                │
                    │ hashed_password     │
                    │ is_active           │
                    │ is_email_verified   │
                    │ is_platform_admin   │
                    │ failed_login_count  │
                    │ locked_until        │
                    │ last_login_at       │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          │ 1:N                │ 1:N                │ 1:N
          ▼                    ▼                    ▼
  ┌───────────────┐  ┌──────────────────┐  ┌─────────────────────┐
  │tenant_member  │  │ refresh_tokens   │  │ password_reset_     │
  │ships          │  ├──────────────────┤  │ tokens              │
  ├───────────────┤  │ token_family_id  │  ├─────────────────────┤
  │ user_id (FK)  │  │ token_hash       │  │ token_hash          │
  │ tenant_id(FK) │  │ is_revoked       │  │ expires_at          │
  │ role          │  │ expires_at       │  │ used_at             │
  │ status        │  └────────┬─────────┘  └─────────────────────┘
  └───────┬───────┘           │ 1:1
          │                   ▼
          │ N:1      ┌─────────────────────┐
          │          │     sessions        │
  ┌───────┴───────┐  ├─────────────────────┤
  │   tenants     │  │ refresh_token_id(FK)│
  ├───────────────┤  │ device_type         │
  │ name, slug    │  │ device_name         │
  │ plan, status  │  │ ip_address_hash     │
  │ currency      │  │ last_active_at      │
  └───────────────┘  └─────────────────────┘

  ┌───────────────────────────────────────────────────┐
  │                 invitations                        │
  ├───────────────────────────────────────────────────┤
  │ email, tenant_id (FK), invited_by_user_id (FK)    │
  │ token_hash (UNIQUE), role, status, expires_at     │
  └───────────────────────────────────────────────────┘

  ┌───────────────────────────────────────────────────┐
  │           email_verification_tokens                │
  ├───────────────────────────────────────────────────┤
  │ user_id (FK), token_hash (UNIQUE), expires_at     │
  └───────────────────────────────────────────────────┘
```

---

## 8. API Endpoint Inventory

### Conventions

- **Base URL:** `/api/v1`
- **Auth header:** `Authorization: Bearer <access_token>`
- **Success envelope:** `{ "data": T, "message": "..." }`
- **Error envelope:** `{ "code": "MACHINE_CODE", "detail": "Human message.", "field": null | "fieldName" }`
- **HTTP status codes:** 200 (ok), 201 (created), 204 (deleted/no content), 400 (bad request), 401 (unauthenticated), 403 (forbidden), 404 (not found), 409 (conflict), 422 (validation), 429 (rate limited), 500 (server error)
- **Refresh token transport:** HTTP-only Secure SameSite=Lax cookie named `ecl_refresh`

---

### 8.1 Auth — `/api/v1/auth`

---

#### `POST /auth/register`
**Purpose:** Create new workspace + first admin user. Maps to `/sign-up`.

**No auth required.**

**Request:**
```json
{ "company_name": "Zenith Bank", "email": "jane@zenith.com", "name": "Jane Smith", "password": "Secure123!" }
```

**Business logic (in order, all in one DB transaction):**
1. Validate password strength against all rules (Section 3.3) — fail fast, return all broken rules
2. Check HIBP k-anonymity — fail if password found in breach database
3. Check no user with this email (soft-delete excluded)
4. Derive tenant slug: `slugify(company_name)`, ensure unique, auto-suffix if collision
5. Hash password with Argon2id
6. INSERT `users` (`is_email_verified = false`)
7. INSERT `tenants`
8. INSERT `tenant_memberships` (role = administrator, status = active)
9. Generate ULID refresh token family ID
10. Generate raw refresh token → hash → INSERT `refresh_tokens`
11. Parse User-Agent → INSERT `sessions`
12. Generate RS256 access token (payload: sub, email, role=administrator, tenant_id, jti)
13. Queue Celery: `send_welcome_email(user_id, tenant_id)`
14. Queue Celery: `send_verification_email(user_id, raw_verify_token)`
15. Set refresh token cookie, return access token + user object

**201 Created**

**Errors:** 409 email conflict · 409 company slug conflict · 422 password rules · 429 rate limited

---

#### `POST /auth/login`
**Purpose:** Authenticate. Maps to `/sign-in`.

**No auth required.**

**Request:**
```json
{ "email": "jane@zenith.com", "password": "Secure123!", "remember": true }
```

**Business logic:**
1. Look up user by email — if missing, run dummy Argon2id verify anyway (constant time)
2. Check `locked_until`: if in future → 423 Locked with `retry_after` seconds
3. Verify password against hash — if wrong: increment `failed_login_count`, check lockout threshold, return 401 (same message as wrong email)
4. On success: reset `failed_login_count = 0`, clear `locked_until = null`
5. Check `is_active` — 403 if false
6. Determine which tenant to embed in JWT: user's most recently active membership (check `sessions` for last tenant)
7. Determine refresh token TTL: `remember=true` → 7 days, `false` → 24 hours
8. Create refresh token, session, generate access token
9. Update `user.last_login_at`
10. Return + set cookie

**Account lockout thresholds:**
- 5 failures in 15 min → lock for 15 min
- 10 failures in 1 hour → lock for 1 hour
- 20 failures total → lock for 24 hours (admin must unlock)

**200 OK**

**Errors:** 401 invalid credentials · 403 account disabled · 423 account locked · 429 rate limited

---

#### `POST /auth/refresh`
**Purpose:** Rotate refresh token → new access token.

**Auth: Refresh token in `ecl_refresh` cookie.**

**Business logic (Refresh Token Rotation with Theft Detection):**
1. Read raw token from cookie
2. Hash it → look up in `refresh_tokens`
3. Not found → 401
4. `is_revoked = true` → **THEFT DETECTED** → revoke entire `token_family_id` → 401 `code: TOKEN_REUSE`
5. `expires_at < NOW()` → 401
6. Mark current token `is_revoked = true`
7. Create new refresh token in same `token_family_id`
8. Update session `last_active_at`
9. Generate new access token (same `sub`, `tenant_id`, updated `jti`)
10. Set new cookie, return new access token

**200 OK**

---

#### `POST /auth/logout`
**Purpose:** Invalidate current session.

**Auth: Bearer access token.**

**Business logic:**
1. Decode access token → extract `jti` + `exp`
2. Blacklist `jti` in Redis: `SET blacklist:jti:{jti} 1 EX {remaining_seconds}`
3. Read refresh cookie → hash → revoke refresh token → delete session record
4. Clear `ecl_refresh` cookie (set empty, expired)

**200 OK**

---

#### `POST /auth/logout-all`
**Purpose:** Revoke all sessions across all devices.

**Auth: Bearer access token.**

**Business logic:**
1. Blacklist current access token JTI in Redis
2. `UPDATE refresh_tokens SET is_revoked = true WHERE user_id = ? AND is_revoked = false`
3. `DELETE FROM sessions WHERE user_id = ?`
4. Clear cookie

**200 OK**

---

#### `POST /auth/forgot-password`
**Purpose:** Trigger password reset email. Maps to `/forgot-password`.

**No auth required.**

**CRITICAL: Always return the exact same response regardless of whether the email is registered. This prevents email enumeration.**

**Business logic:**
1. Rate limit check (Section 15) — `429` if exceeded
2. Look up user by email
3. Always return 200 immediately in the response (do not wait for email to send)
4. If user exists and is active (async, after response):
   a. Expire old unused reset tokens for this user
   b. Generate 64 random bytes → raw token
   c. Hash → INSERT `password_reset_tokens` (expires 1 hour)
   d. Queue Celery: `send_reset_password_email(user_id, raw_token, ip_address)`

**200 OK** — identical body whether email found or not:
```json
{ "message": "If that email is registered, a reset link has been sent." }
```

**Errors:** 429 rate limited

---

#### `POST /auth/reset-password`
**Purpose:** Set new password using reset token. Maps to `/reset-password?token=`.

**No auth required.**

**Request:**
```json
{ "token": "<raw_token>", "password": "NewSecure456!" }
```

**Business logic:**
1. Hash token → look up `password_reset_tokens`
2. Not found / already used / expired → 400 `code: INVALID_RESET_TOKEN`
3. Validate password strength — fail with all broken rules
4. Hash new password
5. UPDATE `users.hashed_password`
6. Mark token `used_at = NOW()`
7. Revoke ALL refresh tokens for this user (password change = all sessions out)
8. Delete all sessions for this user
9. Queue Celery: `send_password_changed_email(user_id, ip_address)`
10. Return success — do NOT auto-login (frontend redirects to `/sign-in`)

**200 OK**

---

#### `GET /auth/verify-email/{token}`
**Purpose:** Verify email from welcome email link.

**No auth required.**

**Business logic:**
1. Hash token → look up `email_verification_tokens`
2. Expired or used → 400
3. Set `user.is_email_verified = true`
4. Mark token `verified_at = NOW()`

**200 OK**

---

#### `POST /auth/resend-verification`
**Purpose:** Resend email verification.

**Auth: Bearer access token.**

**Business logic:**
1. Check user is not already verified — 409 if yes
2. Rate limit: 3 per hour per user
3. Expire old verification token, generate new one
4. Queue Celery: `send_verification_email`

**200 OK**

---

#### `POST /auth/switch-tenant`
**Purpose:** Switch active tenant (for users belonging to multiple tenants). Issues a new access token with a different `tenant_id` without requiring re-login.

**Auth: Bearer access token.**

**Request:**
```json
{ "tenant_id": "01HYYY" }
```

**Business logic:**
1. Look up `tenant_memberships` for (current_user_id, requested_tenant_id)
2. Verify membership exists and status = active — 403 if not
3. Generate new access token with the new `tenant_id` and the user's role in that tenant
4. Do NOT rotate the refresh token (no new cookie needed)
5. Return new access token

**200 OK**
```json
{
  "data": {
    "access_token": "eyJ...",
    "token_type": "bearer",
    "expires_in": 900,
    "tenant_id": "01HYYY",
    "tenant_name": "Second Corp",
    "role": "analyst"
  }
}
```

---

#### `GET /.well-known/jwks.json`
**Purpose:** Publish RSA public key for JWT verification. Allows any consumer to verify access tokens without calling the backend.

**No auth required.**

**Response:**
```json
{
  "keys": [
    {
      "kty": "RSA",
      "use": "sig",
      "alg": "RS256",
      "kid": "ecl-auth-2026-01",
      "n": "<base64url-encoded modulus>",
      "e": "AQAB"
    }
  ]
}
```

Cache-Control header: `max-age=3600` — clients should cache this for up to 1 hour.

---

#### `POST /auth/validate-token`
**Purpose:** Quick token validation — returns user context without full `/me` overhead. Used by Next.js middleware or other services to verify a token is valid.

**Auth: Bearer access token.**

**No DB query needed** — validate JWT signature + blacklist check in Redis only.

**200 OK**
```json
{
  "data": {
    "user_id": "01HXXX",
    "email": "jane@zenith.com",
    "role": "administrator",
    "tenant_id": "01HYYY",
    "exp": 1748990400
  }
}
```

---

### 8.2 Invites — `/api/v1/invites`

---

#### `GET /invites/validate/{token}`
**Purpose:** Validate invite before showing the form. Called on page load of `/invite?token=`.

**No auth required.**

**Business logic:**
1. Hash token → look up `invitations`
2. `status != pending` or `expires_at < NOW()` → 400 `code: INVALID_INVITE_TOKEN`
3. Return safe subset of invitation info (no sensitive data)

**200 OK** — see Section 3.4 for response shape.

---

#### `POST /invites/accept`
**Purpose:** Accept invite — create or link account, auto-login. Maps to InviteForm submit.

**No auth required.**

**Request:**
```json
{ "token": "<raw_token>", "name": "Bob Jones", "password": "Secure789!" }
```

**Business logic:**
1. Hash token → validate invitation (status + expiry)
2. Validate password strength
3. Check HIBP
4. Check if user with invitation email already exists:
   - **New user:** CREATE user, hash password, `is_email_verified = true` (email used for invite)
   - **Existing user:** Verify provided password — 401 if wrong
5. Check not already a member of this tenant — 409 if yes
6. INSERT `tenant_memberships` with invited role
7. Mark invitation `status = accepted`, `accepted_at = NOW()`
8. Create refresh token, session, access token (auto-login)
9. Queue Celery: `send_welcome_to_tenant_email`

**201 Created** — same auth response shape as login.

---

#### `POST /invites`
**Purpose:** Send invite to a team member.

**Auth: Bearer + must be Administrator of the target tenant.**

**Request:**
```json
{ "email": "newmember@example.com", "role": "analyst", "tenant_id": "01HYYY" }
```

**Business logic:**
1. Verify caller is Administrator of tenant_id
2. Check no pending invite for this email + tenant
3. Check email not already an active member
4. Generate 64-byte random token → hash → INSERT `invitations` (7-day expiry)
5. Queue Celery: `send_invite_email(invitation_id, raw_token)`

**201 Created**

---

#### `DELETE /invites/{invite_id}`
**Auth: Bearer + Administrator of tenant.**

Cancels a pending invite (sets `status = cancelled`).

**204 No Content**

---

#### `POST /invites/{invite_id}/resend`
**Auth: Bearer + Administrator of tenant.**

Resets expiry, generates new token, re-queues email task. Rate limited: 2 per 24 hours per invite.

**200 OK**

---

### 8.3 Profile — `/api/v1/me`

---

#### `GET /me`
**Auth: Bearer.** Returns current user + all tenant memberships.

**Response** — see Section 3.4.

---

#### `PATCH /me`
**Auth: Bearer.**

**Request:** `{ "name": "Jane M. Smith" }` (all fields optional)

**204 No Content** on success.

---

#### `PATCH /me/password`
**Auth: Bearer.**

**Request:**
```json
{ "current_password": "old", "new_password": "New456!", "confirm": "New456!" }
```

**Business logic:** Verify current → validate strength + HIBP → hash → update → revoke all OTHER sessions (keep current).

**204 No Content**

---

#### `GET /me/sessions`
**Auth: Bearer.** Returns all active sessions. Marks current session with `"current": true` by comparing current refresh token ID.

**Response** — see Section 3.4.

---

#### `DELETE /me/sessions/{session_id}`
**Auth: Bearer.** Revokes the refresh token for that session. Cannot revoke own current session (use logout).

**204 No Content**

---

#### `DELETE /me/sessions`
**Auth: Bearer.** Revokes all sessions EXCEPT the current one.

**200 OK** `{ "message": "2 other sessions revoked." }`

---

### 8.4 Tenants — `/api/v1/tenants`

---

#### `GET /tenants/{tenant_id}`
**Auth: Bearer + member of tenant.**

Returns tenant profile.

---

#### `PATCH /tenants/{tenant_id}`
**Auth: Bearer + Administrator of tenant.**

**Request fields (all optional):** `name`, `currency`, `reporting_cadence` (monthly|quarterly), `timezone` (IANA tz string)

**204 No Content**

---

#### `GET /tenants/{tenant_id}/members`
**Auth: Bearer + member of tenant.** Supports pagination (Section 10).

**Response** — see Section 3.4 for member shape.

---

#### `PATCH /tenants/{tenant_id}/members/{user_id}`
**Auth: Bearer + Administrator of tenant.**

**Request:** `{ "role": "analyst" }` or `{ "status": "disabled" }`

**Guards:** Cannot demote last administrator. Cannot disable own account.

**204 No Content**

---

#### `DELETE /tenants/{tenant_id}/members/{user_id}`
**Auth: Bearer + Administrator of tenant.**

**Guard:** Cannot remove last administrator.

**204 No Content**

---

### 8.5 Platform — `/api/v1/platform`

**All endpoints in this section require `user.is_platform_admin == true`. Return 403 for any other user.**

---

#### `GET /platform/tenants`
Query params: `status`, `plan`, `search`, `page`, `per_page`

#### `POST /platform/tenants`
Create tenant without self-registration.

#### `PATCH /platform/tenants/{tenant_id}`
Update `plan`, `status` (active|suspended), `name`.

#### `GET /platform/tenants/{tenant_id}/members`
All members of a specific tenant.

#### `GET /platform/users`
All users across all tenants, paginated.

#### `PATCH /platform/users/{user_id}`
`{ "is_active": false }` — enable/disable globally.

---

### 8.6 Infrastructure

```
GET /health     → { "status": "ok", "db": "ok", "redis": "ok", "version": "1.0.0" }
GET /ready      → 200 if migrations applied and connections healthy, 503 otherwise
GET /metrics    → Prometheus text format (protected by IP allowlist or basic auth)
```

---

## 9. Error Code Registry

Every error response includes a `code` field (machine-readable) alongside a `detail` field (human-readable). The frontend server action layer translates `code` into user-facing messages. Never change a `code` value once shipped — it is a public API contract.

| HTTP | Code | Meaning |
|---|---|---|
| 400 | `INVALID_RESET_TOKEN` | Password reset token is invalid, expired, or already used |
| 400 | `INVALID_INVITE_TOKEN` | Invite token is invalid, expired, or already used |
| 400 | `INVALID_VERIFY_TOKEN` | Email verification token is invalid or expired |
| 400 | `PASSWORD_MISMATCH` | confirm does not match password (server-side fallback) |
| 400 | `ALREADY_VERIFIED` | Email is already verified |
| 401 | `INVALID_CREDENTIALS` | Wrong email or password (never distinguish which) |
| 401 | `TOKEN_EXPIRED` | Access token has expired |
| 401 | `TOKEN_INVALID` | Access token signature invalid or malformed |
| 401 | `TOKEN_BLACKLISTED` | Access token has been revoked (after logout) |
| 401 | `TOKEN_REUSE` | Refresh token reuse detected — entire family revoked |
| 401 | `REFRESH_EXPIRED` | Refresh token has expired — re-login required |
| 403 | `ACCOUNT_DISABLED` | User account is disabled by an administrator |
| 403 | `INSUFFICIENT_ROLE` | User's role does not permit this action |
| 403 | `NOT_TENANT_MEMBER` | User is not a member of this tenant |
| 403 | `PLATFORM_ADMIN_REQUIRED` | Action requires platform superadmin privileges |
| 404 | `RESOURCE_NOT_FOUND` | Requested resource does not exist |
| 409 | `EMAIL_TAKEN` | Email address is already registered |
| 409 | `SLUG_TAKEN` | Company name generates a slug that is already taken |
| 409 | `ALREADY_MEMBER` | User is already a member of this tenant |
| 409 | `INVITE_ALREADY_PENDING` | A pending invite already exists for this email + tenant |
| 422 | `PASSWORD_TOO_SHORT` | Password must be at least 8 characters |
| 422 | `PASSWORD_MISSING_MIX` | Password must contain letters and numbers |
| 422 | `PASSWORD_CONTAINS_FORBIDDEN` | Password contains a forbidden substring |
| 422 | `PASSWORD_PWNED` | Password has appeared in a known data breach |
| 422 | `VALIDATION_ERROR` | Pydantic field-level validation failed |
| 423 | `ACCOUNT_LOCKED` | Account locked due to too many failed attempts |
| 429 | `RATE_LIMITED` | Too many requests — see `retry_after` field |
| 500 | `INTERNAL_ERROR` | Unexpected server error (details in Sentry, not response) |

**Error response format:**
```json
{
  "code": "PASSWORD_TOO_SHORT",
  "detail": "Password must be at least 8 characters.",
  "field": "password",
  "retry_after": null
}
```

For `RATE_LIMITED`, include `"retry_after": 47` (seconds).
For `ACCOUNT_LOCKED`, include `"retry_after": 900` (seconds until unlock).

---

## 10. Pagination Pattern

All list endpoints (`/tenants/{id}/members`, `/platform/tenants`, `/platform/users`, etc.) support pagination using this standard pattern.

### Query Parameters

```
page      int    default 1    (1-indexed)
per_page  int    default 50   max 200
sort      str    optional     column to sort by (allowlisted per endpoint)
order     str    optional     asc | desc
search    str    optional     fuzzy search on relevant fields
```

### Response Envelope

```json
{
  "data": [ ... ],
  "meta": {
    "total": 143,
    "page": 2,
    "per_page": 50,
    "pages": 3,
    "has_next": true,
    "has_prev": true
  }
}
```

### Implementation

Create `app/core/pagination.py` with:
- `PageParams` — Pydantic model with `page`, `per_page` validated fields
- `Page[T]` — Generic response model wrapping `List[T]` + meta
- `paginate(query, params, session)` — async helper that applies `.offset()` / `.limit()` and runs a count query

All list service functions accept `PageParams` and return `Page[T]`.

---

## 11. Security Architecture

### 11.1 Password Security

**Hashing algorithm:** Argon2id (preferred over Argon2i and Argon2d — hybrid, side-channel + GPU resistant)

**Parameters (tune for ~300ms hash time on your target hardware):**
```
memory_cost  = 65536  # 64 MB — resist GPU parallelism
time_cost    = 3      # iterations
parallelism  = 4      # threads
hash_length  = 32     # bytes
salt_length  = 16     # bytes (random per hash)
```

**Common password protection:** On registration and password change:
1. Check against a local wordlist of the 10,000 most common passwords (load into memory at startup)
2. Call HaveIBeenPwned k-anonymity API (async, via `app/core/hibp.py`):
   - Hash the password with SHA-1
   - Send first 5 hex chars to `api.pwnedpasswords.com/range/{prefix}`
   - Check if the suffix appears in the response
   - If match count > 0 → reject with `PASSWORD_PWNED`
   - Timeout: 2 seconds — if HIBP is down, log warning but allow the password (fail open)

**Strength validation function signature:**
```python
async def validate_password_strength(
    password: str,
    name: str | None = None,
    org_name: str | None = None,
) -> list[str]:  # returns list of violated rule codes, empty = valid
```

---

### 11.2 JWT Architecture

**Algorithm:** RS256 (asymmetric) — private key signs, public key verifies.

Rationale: Public key can be distributed via JWKS endpoint (`/.well-known/jwks.json`) so other services and even the frontend can verify tokens without calling the backend.

**Access token payload:**
```json
{
  "sub": "01HXXX",
  "email": "jane@zenith.com",
  "name": "Jane Smith",
  "role": "administrator",
  "tenant_id": "01HYYY",
  "jti": "unique-per-token-ulid",
  "iat": 1748990000,
  "exp": 1748990900
}
```

**Key management:**
- Generate RSA-2048 key pair with `scripts/generate_keys.py` (run once)
- Store private key as `JWT_PRIVATE_KEY` env var (base64-encoded PEM)
- Store public key as `JWT_PUBLIC_KEY` env var
- Key ID (`kid`) in JWKS allows rolling key rotation with zero downtime

**Key rotation procedure:**
1. Generate new key pair, assign new `kid`
2. Add new private key to config, keep old public key in JWKS
3. New tokens signed with new key; old tokens still verify against old public key for their remaining lifetime (max 15 min)
4. After 15 min, remove old public key from JWKS

---

### 11.3 Token Blacklisting

Access tokens are stateless JWTs. On logout, their `jti` is stored in Redis with TTL equal to the remaining token lifetime. Every request to a protected endpoint checks:

1. Verify JWT signature
2. Check `exp` not expired
3. `GET blacklist:jti:{jti}` — if exists → 401 `TOKEN_BLACKLISTED`

```
Redis key format:  blacklist:jti:{jti_value}
Value:             "1"
TTL:               (token.exp - time.now())  seconds
```

---

### 11.4 Refresh Token Rotation + Theft Detection

```
Normal flow:
  Login         → Family=F1, Token=T1 (active)
  Refresh       → T1 revoked → T2 issued (active), same family F1
  Refresh again → T2 revoked → T3 issued (active), same family F1

Theft detection:
  Attacker steals T1 (before rotation)
  Legitimate user refreshes → T2 issued
  Attacker uses T1 → T1 is revoked → THEFT DETECTED
  → Revoke ALL tokens in family F1
  → All sessions for this login event are terminated
  → User must re-login
```

This protects against stolen refresh tokens while ensuring legitimate users are only logged out if a theft actually occurred.

---

### 11.5 Account Lockout

Tracked via `users.failed_login_count` and `users.locked_until`. Uses DB, not Redis, so it survives server restarts.

| Failure threshold | Lock duration |
|---|---|
| 5 failures in 15 min | Lock for 15 minutes |
| 10 failures in 1 hour | Lock for 1 hour |
| 20 total failures | Lock for 24 hours (requires admin/platform unlock) |

On successful login: reset `failed_login_count = 0`, clear `locked_until = null`.

Response when locked:
```json
{
  "code": "ACCOUNT_LOCKED",
  "detail": "Account locked due to too many failed login attempts.",
  "retry_after": 900
}
```
HTTP status: `423 Locked`

---

### 11.6 CORS

```python
allow_origins      = settings.CORS_ORIGINS   # ["http://localhost:3000", "https://app.eclplatform.com"]
allow_methods      = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
allow_headers      = ["Authorization", "Content-Type", "X-Request-ID"]
allow_credentials  = True     # REQUIRED for cookie-based refresh tokens
expose_headers     = ["X-Request-ID", "X-RateLimit-Remaining", "X-RateLimit-Reset"]
max_age            = 600      # 10 min preflight cache
```

---

### 11.7 Security Headers

Applied in `app/core/middleware.py` to every response:

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains  (production only)
Content-Security-Policy: default-src 'self'
Cache-Control: no-store  (on all auth endpoints)
```

---

### 11.8 SQL Injection Prevention

- All DB queries use SQLAlchemy's ORM expression language or `text()` with bound parameters — zero raw string interpolation
- Dynamic `ORDER BY` columns are validated against an allowlist before use
- Pydantic strips leading/trailing whitespace on all strings at model level
- Emails normalized to lowercase in Pydantic validators

---

### 11.9 Security Audit Log

Use `structlog` to emit these structured events. Each log entry includes `request_id`, `user_id`, `ip`, `timestamp`.

```
auth.register_success          user_id, tenant_id
auth.login_success             user_id, tenant_id, device_type
auth.login_failure             email_sha256, ip, reason
auth.login_locked              email_sha256, locked_until
auth.logout                    user_id, session_id
auth.logout_all                user_id, sessions_revoked_count
auth.token_theft_detected      user_id, family_id, ip
auth.password_reset_requested  user_id_or_null (null if email not found)
auth.password_reset_used       user_id
auth.password_changed          user_id
invite.sent                    inviter_id, invitee_email, tenant_id, role
invite.accepted                user_id, tenant_id
invite.cancelled               inviter_id, invite_id
member.role_changed            admin_id, target_user_id, old_role, new_role, tenant_id
member.disabled                admin_id, target_user_id, tenant_id
```

---

## 12. Email & Notification Flows

### 12.1 Templates

| File | Trigger | Key Variables |
|---|---|---|
| `welcome.html` | After registration | name, tenant_name, verify_link |
| `verify_email.html` | After registration / resend | name, verify_link, expires_in_hours |
| `reset_password.html` | After forgot-password | name, reset_link, expires_in_minutes, ip_address, user_agent |
| `password_changed.html` | After password change | name, timestamp, ip_address, support_link |
| `invite_member.html` | When admin sends invite | inviter_name, tenant_name, role, invite_link, expires_in_days |
| `welcome_to_tenant.html` | After invite accepted | name, tenant_name, role, dashboard_link |

### 12.2 Email Design Requirements

- All CSS must be **inline** (email client compatibility — no `<style>` blocks)
- Brand color: `#6D4AFF` (ECL violet — from `../ECL-Web/src/app/globals.css` `--accent`)
- Font: system sans-serif fallback stack (web fonts don't render in email)
- All links must include the full URL with expiry
- All security emails (reset, password changed) include: timestamp, IP address, device info, "Not you? Contact support" CTA
- Mobile-responsive: max-width 600px, table-based layout

### 12.3 SMTP

- Primary: **SendGrid** (transactional, high deliverability, SPF/DKIM/DMARC configured)
- Fallback: direct SMTP
- From: `noreply@eclplatform.com` (display name: "ECL Platform")
- Reply-to: `support@eclplatform.com`
- Unsubscribe link required for non-transactional emails (legal compliance)

---

## 13. Background Task Architecture

### 13.1 Celery Configuration

```python
# tasks/celery_app.py
app = Celery(
    "ecl_tasks",
    broker=settings.REDIS_CELERY_URL,      # redis://localhost:6379/1
    backend=settings.REDIS_CELERY_URL,
    include=["app.tasks.email_tasks", "app.tasks.cleanup_tasks"],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_soft_time_limit=30,               # SoftTimeLimitExceeded raised at 30s
    task_time_limit=60,                    # Worker killed at 60s
    task_acks_late=True,                   # Acknowledge only after task completes
    task_reject_on_worker_lost=True,       # Re-queue if worker dies mid-task
    worker_prefetch_multiplier=1,          # One task at a time per worker slot
)

# Retry policy for all tasks (overridable per task)
DEFAULT_RETRY_POLICY = {
    "max_retries": 3,
    "interval_start": 5,
    "interval_step": 20,
    "interval_max": 125,
}
```

### 13.2 Task Definitions

```python
# tasks/email_tasks.py

send_reset_password_email(user_id: str, raw_token: str, ip_address: str)
  # Constructs: {FRONTEND_URL}/reset-password?token={raw_token}
  # Template: reset_password.html

send_invite_email(invitation_id: str, raw_token: str)
  # Fetches invitation, tenant, inviter from DB
  # Constructs: {FRONTEND_URL}/invite?token={raw_token}&org={tenant_slug}&inviter={inviter_name}
  # Template: invite_member.html

send_welcome_email(user_id: str, tenant_id: str)
  # Template: welcome.html

send_verification_email(user_id: str, raw_token: str)
  # Constructs: {FRONTEND_URL}/auth/verify-email/{raw_token}
  # Template: verify_email.html

send_password_changed_email(user_id: str, ip_address: str, user_agent: str)
  # Template: password_changed.html

send_welcome_to_tenant_email(user_id: str, tenant_id: str)
  # Template: welcome_to_tenant.html
```

```python
# tasks/cleanup_tasks.py — all scheduled via Celery Beat

expire_password_reset_tokens()           # Every 15 minutes
  # UPDATE password_reset_tokens SET ... WHERE expires_at < NOW() AND used_at IS NULL

expire_invitations()                     # Every hour
  # UPDATE invitations SET status='expired' WHERE expires_at < NOW() AND status='pending'

purge_revoked_refresh_tokens()           # Daily at 03:00 UTC
  # DELETE FROM refresh_tokens WHERE is_revoked = true AND expires_at < NOW() - INTERVAL '7 days'

purge_old_sessions()                     # Daily at 03:00 UTC
  # DELETE FROM sessions WHERE last_active_at < NOW() - INTERVAL '90 days'
```

---

## 14. Caching Strategy

```
Key                                TTL        Description
───────────────────────────────────────────────────────────────────────────────
blacklist:jti:{jti}                dynamic    Access token blacklist (= remaining token life)
ratelimit:login:{ip}               60s        Login attempt counter per IP
ratelimit:login:long:{ip}          900s       15-min window counter per IP
ratelimit:forgot:{email_sha256}    3600s      Forgot-password counter per email
ratelimit:register:{ip}            3600s      Registration counter per IP
ratelimit:resend:{user_id}         3600s      Resend verification counter
lock:login:{email_sha256}          dynamic    Account lockout (TTL = lock duration)
tenant:{tenant_id}:members         120s       Member list cache
user:{user_id}:memberships         300s       User's tenant memberships (for /me)
jwks                               3600s      JWKS JSON cache (avoid re-reading key from env)
```

**Cache invalidation:**
- `logout-all` → delete `user:{user_id}:memberships`, `tenant:{tenant_id}:members` for all of user's tenants
- Role/status change → delete `tenant:{tenant_id}:members`
- Password change → blacklist current JTI, all other sessions revoked via DB

---

## 15. Rate Limiting & Account Lockout

### 15.1 Per-Endpoint Rate Limits

| Endpoint | Limit | Window | Key Function |
|---|---|---|---|
| `POST /auth/login` | 5 req | 1 min | IP |
| `POST /auth/login` | 10 req | 15 min | IP |
| `POST /auth/register` | 3 req | 1 hour | IP |
| `POST /auth/forgot-password` | 3 req | 1 hour | SHA-256(email field) |
| `POST /auth/resend-verification` | 3 req | 1 hour | user_id (from JWT) |
| `POST /auth/refresh` | 30 req | 1 min | IP |
| `POST /invites/{id}/resend` | 2 req | 24 hours | invite_id |
| `POST /invites` | 20 req | 1 hour | tenant_id (from JWT) |
| Global (all endpoints) | 1000 req | 1 min | IP |

### 15.2 Rate Limit Response

```json
{
  "code": "RATE_LIMITED",
  "detail": "Too many requests. Please wait before trying again.",
  "field": null,
  "retry_after": 47
}
```
HTTP `429 Too Many Requests` with `Retry-After: 47` header.

### 15.3 Account Lockout (DB-backed, survives restarts)

See Section 11.5 for full lockout threshold table.

**Implementation in `authenticate_user()`:**
```
1. Load user by email
2. If user.locked_until > NOW() → raise 423 with retry_after
3. Verify password
4. If wrong:
   - user.failed_login_count += 1
   - Apply lockout threshold → set user.locked_until
   - Commit
   - Raise 401
5. If correct:
   - user.failed_login_count = 0
   - user.locked_until = null
   - Commit
   - Continue login flow
```

---

## 16. Module Build Order & Git Workflow

### Git Rules

Before writing any code, initialize the git repository:
```bash
cd ECL-Server/
git init
git add .gitignore
git commit -m "chore: initialize server repository"
```

**After every checkpoint below:** Run the tests for that feature. If they pass, stage only the relevant files with `git add -p` (stage by hunk), then commit immediately with the exact message format shown.

**Commit format:**
```
<type>(<scope>): <imperative description, ≤72 chars>

Types: feat, fix, refactor, test, chore, docs
Scope: core, db, auth, invite, tenant, session, platform, tasks, ci, docker
```

**Never push** — the engineer reviews git log and pushes manually.

---

### Phase 0: Project Scaffolding

```
□ Create .cursor/rules/ecl-backend.mdc  (Section 0.4 content)
□ Initialize pyproject.toml with all dependencies (Section 5)
□ Create .env.example with all variables (Section 18)
□ Create .pre-commit-config.yaml (ruff + mypy + bandit)
□ Run: pre-commit install
□ Create docker/docker-compose.yml (postgres 16 + redis 7)
□ Run: docker compose up -d → verify both services healthy
□ Create app/config.py with pydantic-settings (all env vars, fail on missing)
□ Create app/database.py (async engine, AsyncSessionLocal, Base, get_db)
□ Create app/core/enums.py (UserRole, MemberStatus, TenantPlan, TenantStatus, DeviceType)
□ Create app/core/exceptions.py (ECLException, typed subclasses, global handlers)
□ Create app/core/middleware.py (RequestID, timing, CORS, security headers)
□ Create app/main.py (lifespan, middleware, /health, /ready)
□ Run: uvicorn app.main:app --reload → GET /health returns 200

✓ git commit: chore(core): scaffold FastAPI project with config, middleware, and health endpoints
✓ git commit: chore(ci): add pre-commit hooks (ruff, mypy, bandit)
```

---

### Phase 1: Core Security Layer

```
□ Create app/core/security.py:
  - hash_password(plain: str) → str          (Argon2id)
  - verify_password(plain: str, hashed: str) → bool
  - hash_token(raw: str) → str               (SHA-256 hex)
  - generate_raw_token(nbytes: int = 64) → str
  - create_access_token(payload: dict) → str  (RS256 JWT)
  - decode_access_token(token: str) → dict | raises ECLException
  - Keys loaded from settings at startup, cached in module scope

□ Create app/core/hibp.py:
  - check_password_pwned(password: str) → bool  (async httpx, k-anonymity)
  - validate_password_strength(password, name, org_name) → list[str]

□ Create app/core/cache.py:
  - get_redis() → AsyncRedis dependency
  - blacklist_token(redis, jti: str, ttl: int) → None
  - is_token_blacklisted(redis, jti: str) → bool

□ Create app/core/pagination.py:
  - PageParams Pydantic model
  - Page[T] generic response model
  - paginate(query, params, session) → Page[T]

□ Write tests/test_core/test_security.py:
  - hash + verify correct password → True
  - hash + verify wrong password → False
  - hash is deterministic per-input but unique per-call (different salts)
  - JWT encode → decode round trip → same payload
  - Expired JWT → raises ECLException code TOKEN_EXPIRED
  - hash_token is deterministic (SHA-256 is pure function)

□ Write tests/test_core/test_hibp.py:
  - Mock httpx → simulate breached password → returns True
  - Mock httpx → simulate clean password → returns False
  - Mock httpx timeout → returns False (fail open)

✓ git commit: feat(core): implement Argon2id hashing and RS256 JWT utilities
✓ git commit: feat(core): implement HIBP k-anonymity check and password strength validation
✓ git commit: feat(core): implement Redis cache layer and token blacklisting
✓ git commit: feat(core): implement pagination helpers
✓ git commit: test(core): add security, HIBP, and cache unit tests
```

---

### Phase 2: Database Models + Migration

```
□ Create all SQLAlchemy models (Section 7):
  - app/modules/auth/models.py      → User, PasswordResetToken, EmailVerificationToken
  - app/modules/tenants/models.py   → Tenant, TenantMembership
  - app/modules/invites/models.py   → Invitation
  - app/modules/sessions/models.py  → RefreshToken, Session

□ Configure migrations/env.py for async SQLAlchemy pattern
□ Run: alembic revision --autogenerate -m "initial_auth_schema"
□ REVIEW generated migration manually — add:
  - All partial indexes listed in Section 7
  - The set_updated_at trigger DDL for each table
□ Run: alembic upgrade head
□ Verify in psql: \dt → all tables present, \di → all indexes present

✓ git commit: feat(db): add SQLAlchemy models for all auth module tables
✓ git commit: feat(db): add migration 0001 — full auth schema with indexes and triggers
```

---

### Phase 3: Registration Endpoint

```
□ READ FIRST: @../ECL-Web/src/app/actions/auth.ts (signUpAction)
□ READ FIRST: @../ECL-Web/src/lib/auth-schema.ts (SignUpSchema)

□ Create app/modules/auth/schemas.py:
  - RegisterRequest, LoginRequest, ForgotPasswordRequest, ResetPasswordRequest
  - TokenResponse, UserOut, AuthResponse (matches Section 3.4 exactly)

□ Create app/modules/auth/service.py:
  - register_user(db, redis, request, ip, user_agent) → AuthResponse
  - All DB operations in one transaction

□ Create app/modules/auth/router.py:
  - POST /auth/register
  - Wire rate limiting, Celery tasks

□ Wire router in app/main.py

□ Write tests/test_auth/test_register.py:
  - 201 happy path: response shape matches Section 3.4 exactly
  - 409 duplicate email
  - 409 duplicate company slug
  - 422 password too short
  - 422 password no mix
  - 422 password contains "ecl"
  - 422 password pwned (mock HIBP)
  - 429 rate limit exceeded (mock slowapi)

✓ git commit: feat(auth): add registration Pydantic schemas
✓ git commit: feat(auth): implement register_user service with workspace creation
✓ git commit: feat(auth): add POST /auth/register endpoint with rate limiting
✓ git commit: test(auth): add registration tests — all happy and error cases
```

---

### Phase 4: Login, Refresh, Dependencies

```
□ READ FIRST: @../ECL-Web/src/app/actions/auth.ts (loginAction)
□ READ FIRST: @../ECL-Web/src/lib/auth.ts (NextAuth credentials provider)

□ Implement in service.py:
  - authenticate_user(db, email, password) → User  (timing-safe — always hash even on miss)
  - check_lockout(user) → raises 423 if locked
  - handle_failed_login(db, user) → increments count, applies lockout
  - create_auth_session(db, user, request, remember) → AuthResponse

□ Create app/dependencies.py:
  - get_current_user(token: str, db, redis) → User
    (validate JWT sig + exp + blacklist check, load user from DB)
  - require_tenant_member(tenant_id, current_user, db) → TenantMembership
  - require_tenant_admin(tenant_id, current_user, db) → TenantMembership
  - require_platform_admin(current_user) → User

□ Add to router.py:
  - POST /auth/login
  - POST /auth/refresh  (rotation + theft detection)
  - POST /auth/switch-tenant

□ Write tests:
  - Login happy path → 200 + cookie set
  - Wrong password → 401, failed_login_count incremented
  - Non-existent email → 401 (same latency bracket)
  - Disabled account → 403
  - Locked account → 423 with retry_after
  - Lockout progression: 5 → 10 → 20 failures
  - Rate limit → 429
  - Refresh happy path → new access token + new cookie
  - Refresh with revoked token → 401 TOKEN_REUSE, whole family revoked
  - Refresh with expired token → 401
  - Switch tenant → 200 with new access token containing new tenant_id

✓ git commit: feat(auth): implement timing-safe login with account lockout
✓ git commit: feat(auth): implement refresh token rotation with theft detection
✓ git commit: feat(auth): implement switch-tenant endpoint
✓ git commit: feat(core): add get_current_user and role enforcement dependencies
✓ git commit: test(auth): add login, refresh, and switch-tenant tests
```

---

### Phase 5: Logout + Password Reset

```
□ READ FIRST: @../ECL-Web/src/components/auth/ForgotForm.tsx (ResendCountdown, 60s UI)
□ READ FIRST: @../ECL-Web/src/components/auth/ResetForm.tsx (success screen, no auto-login)

□ Add to router.py:
  - POST /auth/logout
  - POST /auth/logout-all
  - POST /auth/forgot-password
  - POST /auth/reset-password
  - GET  /auth/verify-email/{token}
  - POST /auth/resend-verification

□ Create app/tasks/email_tasks.py (Celery tasks from Section 13.2)
□ Create app/core/email.py (fastapi-mail client + Jinja2 render)
□ Create app/templates/ (all 6 HTML templates from Section 12.1)

□ Write tests:
  - Logout: access JTI blacklisted, refresh revoked, cookie cleared, session deleted
  - Logout-all: all user refresh tokens revoked, all sessions deleted
  - Forgot-password: always 200 (test with known email AND unknown email — same response time)
  - Forgot-password: Celery task queued when email exists
  - Reset: valid token → password updated, all sessions revoked, 200
  - Reset: expired token → 400 INVALID_RESET_TOKEN
  - Reset: already used token → 400 INVALID_RESET_TOKEN
  - Reset: weak password → 422

✓ git commit: feat(auth): implement logout and logout-all with token blacklisting
✓ git commit: feat(auth): implement forgot-password with email enumeration protection
✓ git commit: feat(auth): implement reset-password and email verification endpoints
✓ git commit: feat(tasks): add Celery email tasks for auth flows
✓ git commit: feat(core): add email client and Jinja2 HTML templates
✓ git commit: test(auth): add logout and password reset tests
```

---

### Phase 6: JWKS + Token Validation

```
□ Add to router.py:
  - GET  /.well-known/jwks.json
  - POST /auth/validate-token

□ Write tests:
  - JWKS: returns valid JSON with RSA modulus and exponent
  - Validate-token: valid JWT → 200 with payload
  - Validate-token: expired JWT → 401
  - Validate-token: blacklisted JTI → 401

✓ git commit: feat(auth): add JWKS endpoint and token validation endpoint
✓ git commit: test(auth): add JWKS and token validation tests
```

---

### Phase 7: Invite Module

```
□ READ FIRST: @../ECL-Web/src/components/auth/InviteForm.tsx (loads org info on mount, auto-redirect on success)
□ READ FIRST: @../ECL-Web/src/app/actions/auth.ts (inviteAction)

□ Create app/modules/invites/schemas.py
□ Create app/modules/invites/service.py
□ Create app/modules/invites/router.py:
  - GET  /invites/validate/{token}
  - POST /invites/accept
  - POST /invites
  - DELETE /invites/{id}
  - POST /invites/{id}/resend

□ Write tests:
  - Validate: pending token → org info
  - Validate: expired → 400
  - Validate: accepted → 400
  - Accept (new user): user created, membership created, auto-login tokens returned
  - Accept (existing user, correct password): membership created, auto-login
  - Accept (existing user, wrong password): 401
  - Accept: already member → 409
  - Send: non-admin → 403
  - Send: already pending → 409
  - Send: already member → 409
  - Resend: resets expiry, queues new email
  - Cancel: status = cancelled

✓ git commit: feat(invite): add invite validation and acceptance endpoints
✓ git commit: feat(invite): add send, resend, and cancel invite endpoints
✓ git commit: feat(tasks): add Celery task for invite email
✓ git commit: test(invite): add full invite flow tests
```

---

### Phase 8: User Profile + Session Management

```
□ READ FIRST: @../ECL-Web/src/lib/settings-types.ts (Session, UserProfile shapes)

□ Create app/modules/sessions/router.py:
  - GET    /me
  - PATCH  /me
  - PATCH  /me/password
  - GET    /me/sessions
  - DELETE /me/sessions/{session_id}
  - DELETE /me/sessions

□ Write tests

✓ git commit: feat(session): implement /me profile and password change endpoints
✓ git commit: feat(session): implement session listing and revocation endpoints
✓ git commit: test(session): add profile and session management tests
```

---

### Phase 9: Tenant Management

```
□ READ FIRST: @../ECL-Web/src/lib/admin-types.ts (Member, MemberRole, MemberStatus, TenantProfile)
□ READ FIRST: @../ECL-Web/src/lib/dashboard-types.ts (Tenant)

□ Create app/modules/tenants/router.py:
  - GET    /tenants/{tenant_id}
  - PATCH  /tenants/{tenant_id}
  - GET    /tenants/{tenant_id}/members  (paginated)
  - PATCH  /tenants/{tenant_id}/members/{user_id}
  - DELETE /tenants/{tenant_id}/members/{user_id}

□ Write tests including role guard edge cases

✓ git commit: feat(tenant): implement tenant profile and member management endpoints
✓ git commit: test(tenant): add tenant management tests with role authorization cases
```

---

### Phase 10: Platform SuperAdmin

```
□ READ FIRST: @../ECL-Web/src/lib/superadmin-types.ts (PlatformUser, TenantPlan, TenantStatus)

□ Create app/modules/platform/router.py (all endpoints from Section 8.5)
□ Create scripts/seed_superadmin.py
□ Create scripts/seed_dev_data.py (2 tenants, 5 users, sample invites)

✓ git commit: feat(platform): add platform admin endpoints with is_platform_admin guard
✓ git commit: chore(scripts): add superadmin seeder and dev data seed scripts
```

---

### Phase 11: Observability + Production Hardening

```
□ Configure structlog: JSON format, bound request_id per request via middleware
□ Add all audit log events (Section 11.9) to service functions
□ Configure Prometheus instrumentator
□ Configure Sentry with FastAPI integration + release tagging
□ Wire Celery Beat schedule for cleanup tasks
□ Finalize /health and /ready with real dependency checks
□ Build multi-stage Dockerfile (python:3.12-slim builder → slim production)
□ Complete docker-compose.yml (postgres + redis + app + celery-worker + celery-beat + flower)
□ Security scan: run bandit -r app/ → zero high-severity findings

✓ git commit: feat(observability): add structlog JSON logging with request ID and audit events
✓ git commit: feat(observability): add Prometheus metrics and Sentry integration
✓ git commit: feat(tasks): add Celery Beat schedule for cleanup tasks
✓ git commit: chore(docker): add production multi-stage Dockerfile and docker-compose
✓ git commit: chore(security): fix all bandit findings, add security scan to pre-commit
```

---

## 17. Makefile — Developer Commands

Create `./Makefile` with these targets. Run `make help` for a summary.

```makefile
.PHONY: help up down logs shell migrate migrate-down test test-cov lint type-check \
        format security-scan generate-keys seed-admin seed-dev clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

up: ## Start all services (postgres, redis, celery, app)
	docker compose -f docker/docker-compose.yml up -d

down: ## Stop all services
	docker compose -f docker/docker-compose.yml down

logs: ## Follow app logs
	docker compose -f docker/docker-compose.yml logs -f app

shell: ## Open psql shell
	docker compose -f docker/docker-compose.yml exec postgres psql -U ecl ecl_db

migrate: ## Apply all pending migrations
	alembic upgrade head

migrate-down: ## Rollback last migration
	alembic downgrade -1

migrate-new: ## Generate a new migration (usage: make migrate-new MSG="add something")
	alembic revision --autogenerate -m "$(MSG)"

test: ## Run full test suite
	pytest tests/ -v --tb=short

test-cov: ## Run tests with coverage report
	pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=90

test-auth: ## Run only auth tests
	pytest tests/test_auth/ -v

lint: ## Run ruff linter
	ruff check app/ tests/

format: ## Auto-format code with ruff
	ruff format app/ tests/

type-check: ## Run mypy strict type checking
	mypy app/ --strict

security-scan: ## Run bandit SAST scanner
	bandit -r app/ -ll

generate-keys: ## Generate RSA key pair for JWT (run once at setup)
	python scripts/generate_keys.py

seed-admin: ## Seed platform superadmin account
	python scripts/seed_superadmin.py

seed-dev: ## Seed realistic development data
	python scripts/seed_dev_data.py

clean: ## Remove .pyc files and __pycache__
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
```

---

## 18. Environment Configuration

### `.env.example` — complete and documented

```bash
# ─── Application ─────────────────────────────────────────────────────────────
APP_ENV=development                     # development | staging | production
APP_NAME="ECL Platform API"
APP_VERSION=1.0.0
DEBUG=true                              # MUST be false in production
SECRET_KEY=<64 random hex chars>        # Misc signing — generate with: python -c "import secrets; print(secrets.token_hex(32))"

# ─── Server ──────────────────────────────────────────────────────────────────
HOST=0.0.0.0
PORT=8000
WORKERS=4                               # Gunicorn: 2 × CPU_count + 1 is a good starting point
RELOAD=false                            # Uvicorn hot-reload — development only

# ─── Database ────────────────────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://ecl:ecl_password@localhost:5432/ecl_db
DATABASE_POOL_SIZE=10                   # Per-worker SQLAlchemy pool size
DATABASE_MAX_OVERFLOW=20                # Max connections above pool_size
DATABASE_POOL_TIMEOUT=30               # Seconds to wait for connection

# ─── Redis ───────────────────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0      # Main cache + blacklist
REDIS_CELERY_URL=redis://localhost:6379/1  # Celery broker + backend (separate DB index)
REDIS_CACHE_TTL_DEFAULT=300            # Seconds

# ─── JWT ─────────────────────────────────────────────────────────────────────
JWT_PRIVATE_KEY=<base64-encoded RSA-2048 private key PEM>   # From: make generate-keys
JWT_PUBLIC_KEY=<base64-encoded RSA-2048 public key PEM>     # From: make generate-keys
JWT_KEY_ID=ecl-auth-2026-01            # Key ID for JWKS — increment when rotating
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
JWT_ALGORITHM=RS256

# ─── Argon2 ──────────────────────────────────────────────────────────────────
ARGON2_MEMORY_COST=65536               # KB — 64 MB. Benchmark on your hardware for ~300ms
ARGON2_TIME_COST=3                     # Iterations
ARGON2_PARALLELISM=4                   # Threads

# ─── CORS ────────────────────────────────────────────────────────────────────
CORS_ORIGINS=http://localhost:3000,https://app.eclplatform.com
# Production: remove localhost, keep only production domain

# ─── Email ───────────────────────────────────────────────────────────────────
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=<sendgrid api key>
SMTP_FROM_EMAIL=noreply@eclplatform.com
SMTP_FROM_NAME="ECL Platform"
SMTP_TLS=true

# ─── Frontend ────────────────────────────────────────────────────────────────
FRONTEND_URL=http://localhost:3000      # Used to construct links in emails
# Production: https://app.eclplatform.com

# ─── HIBP (Have I Been Pwned) ────────────────────────────────────────────────
HIBP_TIMEOUT_SECONDS=2                 # Fail open if HIBP unreachable
HIBP_ENABLED=true                      # Set false to disable in tests

# ─── Observability ───────────────────────────────────────────────────────────
SENTRY_DSN=                            # Leave blank to disable
LOG_LEVEL=INFO                         # DEBUG | INFO | WARNING | ERROR
LOG_FORMAT=json                        # json | console (console is human-readable for dev)
RELEASE=dev                            # Sentry release tag — set to git SHA in CI

# ─── Rate Limiting ───────────────────────────────────────────────────────────
RATE_LIMIT_ENABLED=true                # Set false in test environment

# ─── Account Lockout ─────────────────────────────────────────────────────────
LOCKOUT_THRESHOLD_1=5                  # Failures → lock for 15 min
LOCKOUT_THRESHOLD_2=10                 # Failures → lock for 60 min
LOCKOUT_THRESHOLD_3=20                 # Failures → lock for 24 hours

# ─── Metrics ─────────────────────────────────────────────────────────────────
METRICS_TOKEN=<random token>           # Bearer token required to access /metrics (optional)
```

---

## 19. Production Readiness Checklist

### Security
- [ ] Argon2id parameters benchmarked on target hardware (~300ms per hash)
- [ ] RS256 JWT with RSA-2048 (not HS256)
- [ ] Refresh token rotation with family-level theft detection
- [ ] HTTP-only Secure SameSite=Lax cookie for refresh token
- [ ] JWT blacklist in Redis on logout
- [ ] Rate limiting on all auth endpoints (slowapi + Redis)
- [ ] Account lockout after progressive failure thresholds
- [ ] Email enumeration protection on `/forgot-password`
- [ ] Timing-safe login (always run Argon2 even when user not found)
- [ ] All tokens stored as SHA-256 hashes — never plaintext
- [ ] HIBP breach check on registration + password change
- [ ] Security headers on every response
- [ ] CORS locked to specific origins only
- [ ] `DEBUG=false` in production
- [ ] SQL injection: zero raw string queries
- [ ] bandit SAST scan: zero high-severity findings

### Database
- [ ] All migrations applied (`alembic upgrade head` in startup script)
- [ ] Partial indexes present (verify with `\di` in psql)
- [ ] `set_updated_at` trigger on every table
- [ ] PgBouncer in transaction mode (production connection pooling)
- [ ] Regular VACUUM/ANALYZE configured
- [ ] Automated daily backups with point-in-time recovery
- [ ] Soft-delete enforced — never hard-delete users

### Application
- [ ] `/health` checks real DB + Redis connectivity
- [ ] `/ready` returns 503 until migrations complete
- [ ] Graceful shutdown: SQLAlchemy pool dispose + Celery warm shutdown on SIGTERM
- [ ] All env vars validated at startup (pydantic-settings, fails loud)
- [ ] All background tasks in Celery (zero blocking calls in request path)
- [ ] Celery Beat running for cleanup tasks
- [ ] Flower dashboard secured with basic auth

### Observability
- [ ] Structured JSON logs to stdout (parsed by cloud aggregator)
- [ ] `X-Request-ID` on every request (injected in middleware, returned in response header)
- [ ] Sentry DSN configured + release tagging
- [ ] Prometheus metrics at `/metrics`
- [ ] Alert rules: error rate > 1%, P99 latency > 500ms, login failure rate spike

### Infrastructure
- [ ] Multi-stage Dockerfile: final image < 200 MB, non-root user
- [ ] docker-compose.yml with healthchecks for all services
- [ ] Kubernetes manifests: Deployment, Service, ConfigMap, Secret, HPA
- [ ] PgBouncer as sidecar in K8s pod
- [ ] Redis Sentinel or Redis Cluster for HA
- [ ] TLS termination at load balancer, `HSTS` header enabled

### Testing & CI
- [ ] Every endpoint: ≥1 happy path test + test per error code
- [ ] Real PostgreSQL in tests (no mocks)
- [ ] Coverage ≥ 90% across auth module
- [ ] Load test passed: 1000 concurrent logins, P99 < 200ms, error rate < 0.1%
- [ ] Pre-commit hooks: ruff + mypy + bandit block commits

---

## 20. Frontend Integration Guide

### How Server Actions Call the Backend

Once the backend runs at `http://localhost:8000`, update `../ECL-Web/.env.local`:
```
BACKEND_URL=http://localhost:8000
```

Then wire each server action in `../ECL-Web/src/app/actions/auth.ts`:

---

#### `loginAction` → `POST /api/v1/auth/login`

```
Frontend sends: { email, password, remember }
Backend returns: 200 + { data: { access_token, user } } + Set-Cookie: ecl_refresh=...
Frontend:
  1. Feed access_token + user to NextAuth signIn("credentials", ...)
  2. NextAuth stores user in JWT session
  3. Cookie is browser-managed (forwarded automatically on future requests)
```

Error handling in server action:
```typescript
if (response.status === 423) return { error: `Account locked. Try again in ${data.retry_after} seconds.` }
if (response.status === 401) return { error: "Invalid email or password." }
if (response.status === 403) return { error: "Your account has been disabled. Contact support." }
if (response.status === 429) return { error: `Too many attempts. Try again in ${data.retry_after} seconds.` }
```

---

#### `signUpAction` → `POST /api/v1/auth/register`

```
Frontend sends: { company_name: companyName, email, name, password }
(confirm and terms are validated client-side — backend does not need them)
Backend returns: 201 + { data: { access_token, user } }
Frontend: feed tokens to NextAuth, redirect to /setup/onboarding
```

---

#### `forgotAction` → `POST /api/v1/auth/forgot-password`

```
Frontend sends: { email }
Backend: always returns 200 (enumeration-safe)
Frontend: shows email confirmation screen using the email it sent (not backend's response)
```

---

#### `resetAction` → `POST /api/v1/auth/reset-password`

```
Frontend sends: { token, password }
(confirm is validated client-side)
Backend returns: 200 on success, 400 INVALID_RESET_TOKEN, 422 password rules
Frontend: 200 → success screen → user clicks to /sign-in
          400 → redirect to /auth/error?reason=expired
          422 → show validation errors in AuthFormError
```

---

#### `inviteAction` — two-phase

**Phase 1 (page load):** `GET /api/v1/invites/validate/{token}`
- Runs when `/invite` page loads
- Returns `{ tenant_name, inviter_name, role, email }` to pre-fill InviteForm UI
- On 400 → redirect to `/auth/error?reason=expired`

**Phase 2 (form submit):** `POST /api/v1/invites/accept`
- Sends `{ token, name, password }`
- Returns auth response → auto-login → redirect to `/dashboard`

---

### NextAuth Credentials Provider Wiring

When the backend is ready, update `../ECL-Web/src/lib/auth.ts`:

```typescript
// The credentials provider's authorize() function:
// 1. Receives { access_token, user_json } from the server action
// 2. Parses user_json
// 3. Returns the user object — NextAuth stores it in the JWT session
// 4. The session.user is then available in all server components

// The backend's access token is stored in session.accessToken
// and forwarded to the backend in Authorization headers for subsequent requests
```

---

### Local Development Flow

```bash
# Terminal 1: Start backend
cd ECL-Server/
make up           # starts postgres + redis
make migrate      # applies migrations
make seed-dev     # creates 2 tenants, 5 users, sample invites
uvicorn app.main:app --reload --port 8000

# Terminal 2: Start frontend
cd ECL-Web/
npm run dev       # starts on port 3000

# Test in browser:
# http://localhost:3000/sign-up → should hit backend, create workspace
# http://localhost:3000/sign-in → should authenticate
```

---

## 21. Testing Strategy

### Test Environment

- PostgreSQL runs in docker via `docker-compose.test.yml` — always a real database
- Redis runs in docker — real cache behavior
- Email sending is **always mocked** in tests (capture outbox, do not send)
- HIBP is **mocked** in tests (controllable via fixture)
- Celery runs in **eager mode** in tests (`CELERY_TASK_ALWAYS_EAGER=True`)

### Test Isolation (Transaction Rollback Pattern)

```python
# tests/conftest.py
@pytest.fixture(scope="function")
async def db_session():
    async with engine.begin() as conn:
        async with AsyncSession(conn) as session:
            yield session
            await session.rollback()   # All test data vanishes after each test
```

### Factory Pattern

```python
# tests/factories.py — using factory-boy
class UserFactory(AsyncSQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session = ...

    id = factory.LazyFunction(lambda: str(ULID()))
    email = factory.Faker("email")
    name = factory.Faker("name")
    hashed_password = factory.LazyFunction(lambda: hash_password("TestPass123!"))
    is_active = True
    is_email_verified = True

class TenantFactory: ...
class MembershipFactory: ...
class InvitationFactory: ...
```

### Test Coverage Requirements

| Module | Minimum |
|---|---|
| `core/security.py` | 100% |
| `modules/auth/` | 95% |
| `modules/invites/` | 90% |
| `modules/tenants/` | 85% |
| `modules/sessions/` | 85% |
| `modules/platform/` | 80% |
| `core/email.py` | 70% (email sending mocked) |

### Load Test (before production sign-off)

```
Tool: Locust (included in dev dependencies)
Target: http://localhost:8000
Scenario:
  - 70% of users: POST /auth/login → GET /me → POST /auth/refresh → POST /auth/logout
  - 20% of users: POST /auth/refresh only
  - 10% of users: POST /auth/register

Ramp-up: 0 → 1000 users over 60 seconds, hold for 5 minutes
Acceptance criteria:
  - P50 response time < 50ms
  - P99 response time < 200ms
  - Error rate < 0.1%
  - Zero 5xx errors during steady state
```

---

## 22. Architecture Diagram

```
                    ECL PLATFORM — AUTH MODULE — PRODUCTION ARCHITECTURE
                    ═══════════════════════════════════════════════════════

  WORKSPACE
  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │  ECL/                                                                           │
  │  ├── ECL-Web/     (READ ONLY — Next.js 16, React 19)                               │
  │  │   ├── src/app/(auth)/  sign-in, sign-up, forgot-password, reset, invite     │
  │  │   ├── src/app/actions/auth.ts  ← stubs replaced by real fetch calls          │
  │  │   └── src/lib/auth-schema.ts  ← mirrors your Pydantic schemas exactly        │
  │  │                                                                               │
  │  └── ECL-Server/  (ALL WRITES HERE — FastAPI)                                       │
  └─────────────────────────────────────────────────────────────────────────────────┘

  REQUEST FLOW
  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │  Browser / Next.js Server Action                                                 │
  │  POST /api/v1/auth/login  {email, password}                                     │
  └──────────────────────────────────┬──────────────────────────────────────────────┘
                                     │ HTTPS
                                     ▼
  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │  FASTAPI  (server/app/)                                                          │
  │                                                                                  │
  │  Middleware stack (in order):                                                    │
  │    1. RequestID injection  (X-Request-ID header)                                 │
  │    2. CORS enforcement                                                           │
  │    3. Security headers                                                           │
  │    4. Global rate limit (1000/min/IP via slowapi)                               │
  │    5. Structured access logging (structlog)                                      │
  │                                                                                  │
  │  Router → auth/router.py                                                        │
  │    ├── Rate limit check (slowapi + Redis)  → 429 if exceeded                   │
  │    ├── Request body parsed by Pydantic RegisterRequest / LoginRequest            │
  │    └── Calls auth/service.py                                                    │
  │                                                                                  │
  │  Service Layer (auth/service.py):                                               │
  │    ├── validate_password_strength() + hibp.check_password_pwned()               │
  │    ├── authenticate_user() — Argon2id verify (constant time)                    │
  │    ├── check_lockout() / handle_failed_login()                                   │
  │    ├── create_auth_session() — refresh token + access token + session record    │
  │    └── Queue Celery tasks (email sending off request path)                      │
  │                                                                                  │
  │  Dependencies:                                                                   │
  │    get_db()             → AsyncSession from pool                                │
  │    get_redis()          → Redis connection                                       │
  │    get_current_user()   → JWT verify + blacklist check + DB lookup              │
  │    require_tenant_admin() → membership role check                               │
  └──────────┬──────────────────────────────────────────────┬───────────────────────┘
             │ SQLAlchemy 2.0 async                          │ redis-py async
             ▼                                               ▼
  ┌───────────────────────┐                    ┌────────────────────────────────────┐
  │   PostgreSQL 16        │                    │            Redis 7                  │
  │                        │                    │                                    │
  │  users                 │                    │  DB 0: cache + blacklist           │
  │  tenants               │                    │    blacklist:jti:{jti}             │
  │  tenant_memberships    │                    │    ratelimit:login:{ip}            │
  │  invitations           │                    │    tenant:{id}:members             │
  │  refresh_tokens        │                    │    user:{id}:memberships           │
  │  sessions              │                    │                                    │
  │  password_reset_tokens │                    │  DB 1: Celery broker + results     │
  │  email_verify_tokens   │                    │    celery task queue               │
  └───────────────────────┘                    └────────────────────────────────────┘

  BACKGROUND
  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │  CELERY WORKERS  (server/app/tasks/)                                            │
  │                                                                                  │
  │  Triggered by service layer (fire-and-forget, never block request):             │
  │    send_reset_password_email(user_id, raw_token, ip)                           │
  │    send_invite_email(invitation_id, raw_token)                                  │
  │    send_welcome_email(user_id, tenant_id)                                       │
  │    send_verification_email(user_id, raw_token)                                  │
  │    send_password_changed_email(user_id, ip)                                     │
  │                                                                                  │
  │  CELERY BEAT (scheduled):                                                        │
  │    Every 15 min → expire_password_reset_tokens()                                │
  │    Every hour   → expire_invitations()                                           │
  │    Daily 03:00  → purge_revoked_refresh_tokens()                                │
  │    Daily 03:00  → purge_old_sessions()                                           │
  └──────────────────────────────────────────────┬──────────────────────────────────┘
                                                  │
                                     ┌────────────┴────────────┐
                                     │     SendGrid / SMTP      │
                                     │  Password Reset Email    │
                                     │  Team Invite Email       │
                                     │  Welcome Email           │
                                     │  Email Verification      │
                                     └─────────────────────────┘

  OBSERVABILITY
  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │  structlog → JSON → stdout → Cloud Log Aggregator (Datadog / CloudWatch / Loki)│
  │  Sentry SDK → error tracking + performance APM                                  │
  │  /metrics → Prometheus → Grafana dashboards + alerting rules                   │
  │  Flower → http://localhost:5555 → Celery task monitoring                       │
  └─────────────────────────────────────────────────────────────────────────────────┘
```

---

*Document version: 2.0*
*Frontend analyzed: ECL-Web @ 970cfd9*
*Frontend reference: `../ECL-Web/` (read-only)*
*Backend target: `./` (all writes)*
*Backend module: Module 1 of 5 — Auth*
*Last updated: 2026-06-03*
