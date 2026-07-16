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
- Make start/end/submit operations idempotent.
- Prevent parallel active attempts and conflicting active proctor sessions.

## Batch 4: integration and maintainability

- Expand SQL-backed API integration tests for tenant and role boundaries.
- Split the monolithic FastAPI module into routers and application services.
- Add migration/version tracking and release-readiness checks.
