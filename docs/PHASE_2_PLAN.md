# Phase 2: modular domains and deployment confidence

Phase 2 turns the reliable Phase 1 workflow into a maintainable service boundary that can
be load-tested and certified across supported deployment profiles. Each batch is delivered
with regression coverage and pushed only after the full local and hosted quality gates pass.

## Batch 1: identity boundary

- Extract registration, login, current-user, logout, password-reset, and Google OAuth routes
  from the legacy FastAPI module into a dedicated identity router.
- Move validation, credential handling, reset-token flow, OAuth state verification, and
  provider exchange into a framework-independent application service.
- Preserve the existing HTTP paths, response payloads, redirects, audit actions, and role
  behavior.
- Add focused tests for public-user privacy, password validation and login errors, hashed
  one-time reset tokens, signed OAuth state, provider identity creation, and route ownership.
- Verify registration, persisted password hashing, invalid login, login, current-user, and
  logout against controlled live SQL rows with `npm run sql:identity-smoke`; the randomized
  identity and audit rows are deleted in a `finally` block and no plaintext credential is
  retained.

## Batch 2: exam and attempt boundary

- Extract exam authoring, questions/options, publishing, assignment, student discovery, and
  attempt APIs into routers backed by application services.
- Centralize exam-window, editability, content, grading-field privacy, and ownership rules.
- Add deterministic concurrency tests for active-attempt start and submission replay races,
  followed by a controlled multi-process SQL Server load smoke.

## Batch 3: monitoring and reporting boundaries

- Extract browser/device ingestion, session/proctor control, review, evidence, and reporting
  APIs without weakening session-bound authorization or retry idempotency.
- Separate durable repository data from explicitly degraded in-memory fallback behavior.
- Add API-contract tests for monitoring clients and report/evidence consistency across an API
  restart.

## Batch 4: deployment certification and release hardening

- Define supported Windows, browser-extension, camera, microphone, and optional secondary
  camera profiles with machine-readable preflight results.
- Exercise the full browser/hardware workflow against each supported profile and document
  operator-visible failures and recovery steps.
- Add forward-only schema revisions for Phase 2 changes and verify upgrade from the Phase 1
  schema; applied migration files remain immutable.
- Establish measured latency, ingestion throughput, race-safety, and recovery acceptance
  thresholds for release approval.

## Phase completion gate

Phase 2 is complete only when the legacy API module no longer owns the identity, exam,
monitoring, or reporting route implementations; concurrency and deployment-profile checks
are reproducible; all migrations are forward-only; local quality, live SQL smokes, release
readiness, and GitHub Actions are green.
