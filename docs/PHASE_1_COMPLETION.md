# Phase 1 completion record

Phase 1 is complete as of 2026-07-16. The secured Phase 0 baseline now supports a
restart-safe and operationally honest exam workflow.

## Delivered guarantees

- Browser activity and risk events are stored in SQL Server and restored after restart.
- Monitoring clients retry with stable session-bound ingestion IDs; duplicate delivery is
  acknowledged without creating duplicate rows.
- Monitoring writes are accepted only while the persisted session is active. A late retry
  of an already-saved ingestion ID is still acknowledged after session close.
- Session start/end, proctor start, and attempt submission are idempotent. Terminal states,
  original end times, submitted scores, and reviewed states cannot be reopened by retries.
- A student can have only one active attempt. The API checks the rule and SQL Server closes
  concurrent-request races with a filtered unique index.
- Failed session creation compensates the newly created attempt so no orphaned active lock
  remains.
- Tenant exam/session isolation, student ownership, and instructor/admin role boundaries
  are verified through authenticated API calls backed by controlled live SQL rows.
- SQL schema initialization is migration-tracked. Applied migration checksums are immutable,
  repeat startup is a no-op, and pending/drifted/unexpected migration state is visible in
  operations status and release checks.
- Health and operations endpoints now use a dedicated router and application service. The
  Browser Guard recency calculation also uses the correct monotonic clock.
- OpenAPI, health, and operations responses use one central application version.

## Verification record

- `npm run quality`: backend compile, 46 regression tests, release structure, frontend
  typecheck, and production frontend build.
- `npm run sql:browser-smoke`: browser/event round trip and ingestion uniqueness.
- `npm run sql:lifecycle-smoke`: active-attempt uniqueness, first/repeated end semantics,
  stable end time, late-event rejection, and cleanup.
- `npm run sql:api-integration`: authenticated tenant/role/ownership boundaries, migration
  status exposure, and cleanup.
- `npm run check:release`: static release prerequisites, live migration status, and active
  attempt integrity.

All live smoke scripts use randomized controlled identifiers and verify or attempt cleanup in
`finally` blocks. They do not retain plaintext test credentials.

## Next-phase candidates

- Continue extracting the remaining exam, identity, monitoring, and reporting domains from
  the legacy FastAPI module into routers and application services.
- Add multi-process load tests for attempt-start and submit races.
- Run hardware/browser end-to-end certification on each supported deployment profile.
- Add forward migrations as new schema changes are introduced; never edit an applied
  migration revision in place.
