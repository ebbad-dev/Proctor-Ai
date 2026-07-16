# Phase 1: product integrity and durable workflows

Phase 1 turns the secured Phase 0 baseline into a restart-safe, operationally honest
exam workflow. Work is delivered in tested batches and pushed to `main` after each
batch.

## Batch 1: durable browser activity

- Persist exact browser URL, title, category, source, risk, and event timestamp.
- Restore browser timelines and report inputs after API restarts.
- Merge persisted and current-process rows without duplicating a just-written event.
- Preserve repeated identical events when they occurred at materially different times.
- Return an explicit retryable error when an active database connection rejects a
  browser-activity write.
- Verify the additive SQL migration with `npm run sql:browser-smoke`; the smoke row
  is deleted in a `finally` block.

## Batch 2: persistence honesty and retry safety

- Remove silent exception swallowing from session and event writes.
- Acknowledge only SQL-persisted monitoring events; return retryable 503 responses on
  write failures without creating phantom in-memory rows.
- Use session-bound ingestion IDs plus filtered unique SQL indexes to make retries
  duplicate-safe.
- Retry with the same ID in the proctor engine, Browser Guard companion/extension,
  and React exam fallback.

## Batch 3: session lifecycle integrity

- Enforce explicit setup, active, submitted, ended, and reviewed transitions.
- Preserve terminal session states so late monitoring traffic cannot reopen them.
- Make session start/end, proctor start, and attempt submission idempotent.
- Preserve the original end/submission timestamp and score on request replay.
- Reject review while a session is active and transition terminal sessions to reviewed.
- Prevent parallel active attempts and conflicting active proctor sessions in the API.
- Enforce one active attempt per student with a filtered SQL unique index.
- Compensate a partially failed attempt start so it cannot leave an orphaned active lock.
- Verify lifecycle transitions, late-event rejection, the unique active-attempt rule, and
  cleanup against live SQL Server with `npm run sql:lifecycle-smoke`.

## Batch 4: integration and maintainability

- Exercise authenticated API tenant isolation, student ownership, role boundaries, and
  operations access against controlled live SQL rows with `npm run sql:api-integration`.
- Begin splitting the monolithic FastAPI module by moving health/operations routes into
  a router and their logic into an independently tested application service.
- Track applied SQL migrations with immutable checksums and surface their state through
  the instructor operations endpoint.
- Centralize the application version used by OpenAPI, health, and operations responses.
- Run static release-structure checks in local quality and CI, and provide production
  configuration/database readiness checks through `npm run release:check`.
