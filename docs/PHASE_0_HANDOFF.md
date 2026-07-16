# Phase 0 implementation handoff

Phase 0 establishes a reproducible, private, and testable baseline. It does not
certify a public production deployment; production secrets, TLS, database identity,
legal retention settings, and external account lifecycle remain operator-controlled.

## Implemented baseline

- Authentication and sidecar secrets are stable, explicit, and separated.
- Student answer payloads do not expose grading fields before submission.
- Event ingestion, Browser Guard control, status, camera streams, captures, and
  reports enforce authenticated session access.
- Browser Guard and media tokens are short-lived, session-bound, and tamper-evident.
- Capture paths reject traversal and cross-session access.
- Reports return consistent capped risk metadata and include evidence timestamps.
- Generated evidence, reports, logs, exports, runtime profiles, environments,
  dependency trees, and E2E artifacts are excluded from version control.
- A documented dry-run-first retention and quarantine workflow is available.
- Python 3.12.13 and direct dependencies are pinned; the transitive lock includes
  hashes. Frontend dependencies use `npm ci` and are covered by the committed lock.
- Windows CI, setup, quality-check, health-check, and hardware-preflight workflows
  are included.
- E2E and SQL smoke identities use disposable random passwords rather than fixed
  repository credentials.

## Validation evidence

The clean non-OneDrive environment passed:

- Python compilation and 12 security/regression tests;
- `pip check` with no broken requirements;
- frontend TypeScript type checking and a production Vite build;
- `npm audit` with zero reported vulnerabilities;
- camera, microphone, video-frame, and phone-model hardware preflight;
- integrated FastAPI/sidecar health smoke, including anonymous stream rejection.

## Operator-controlled release gates

Before using a real deployment:

1. Rotate production `AUTH_SECRET`, device, database, SMTP, OAuth, and bootstrap
   credentials outside the repository.
2. Run `scripts/prepare_e2e_seed.py --rotate-only` against the intended test database
   to invalidate any surviving E2E credentials without retaining replacement values.
3. Review the quarantine manifest and purge only after the retention/legal-hold
   window permits it.
4. Commit the sanitized tree and push it to the protected remote repository.
5. Configure branch protection, required CI checks, dependency alerts, and private
   vulnerability reporting in the repository host.
