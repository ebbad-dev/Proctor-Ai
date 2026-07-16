# ProctorAI

ProctorAI is a local FastAPI + React/TanStack Start proctoring platform with SQL Server persistence, role-based authentication, live camera/audio/browser monitoring, risk scoring, evidence capture, and PDF reporting.

## Tech Stack

- Frontend: React, TanStack Router/Start, TanStack Query, Tailwind CSS, Radix UI, Recharts
- Backend: FastAPI, Pydantic, Uvicorn
- Database: SQL Server via `pyodbc`
- Proctoring sidecar: OpenCV camera capture, Flask MJPEG stream, sounddevice microphone capture
- Reports: ReportLab PDF generation

## Setup

1. Clone the repository to a local, non-synchronized path. Do not run the active repository, `.venv`, browser profile, or evidence folders from OneDrive/Dropbox/Google Drive.
2. Install Python 3.12.13 and Node.js 24, then create the reproducible environment:
   - `powershell -ExecutionPolicy Bypass -File scripts/setup_dev.ps1`
   - The script creates `.venv`, installs the hash-locked Python graph, and runs `npm ci` for the frontend.
3. Copy `.env.example` to `.env` or set the variables in your shell. Never commit `.env`.
4. Configure SQL Server:
   - `PROCTORAI_DB_SERVER=localhost`
   - `PROCTORAI_DB_NAME=ProctorAI_Lite`
   - `PROCTORAI_DB_TRUSTED=true`
   - `PROCTORAI_DB_DRIVER=ODBC Driver 17 for SQL Server`
   - `PROCTORAI_DB_ENCRYPT=false` for local trusted SQL Server; use encrypted connections in production when your SQL Server certificate chain is configured.
5. Configure auth:
   - Set `AUTH_SECRET` to a stable long random value. Production refuses to start without at least 32 characters.
   - Optionally set a separate `PROCTOR_DEVICE_SECRET`; otherwise a scoped device secret is derived from `AUTH_SECRET`.
   - Optionally set `PROCTORAI_BOOTSTRAP_ADMIN_EMAIL` and `PROCTORAI_BOOTSTRAP_ADMIN_PASSWORD` to create the first admin.
   - If `python` is not available on PATH, set `PYTHON_EXE=C:\path\to\python.exe` or create `.venv\Scripts\python.exe`.
6. Configure SMTP for password reset:
   - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `SMTP_TLS`
   - `FRONTEND_URL=http://127.0.0.1:8080`
7. Configure Google OAuth if you want Google sign-in/sign-up:
   - Create an OAuth client in Google Cloud Console.
   - Add redirect URI `http://127.0.0.1:5051/auth/google/callback` for local use.
   - Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and optionally `GOOGLE_REDIRECT_URI`.
   - New Google users are created as students; instructor/admin Google login works only for existing accounts with those roles.
8. Install the phone/object model:
   - `python scripts/download_phone_model.py`
   - This saves `models/phone_detector.onnx`, which enables COCO `cell phone` detection.
9. Load Browser Guard:
   - Open `chrome://extensions` or `edge://extensions`.
   - Enable Developer mode.
   - Choose **Load unpacked** and select `browser_guard_extension`.
   - Or run `npm run browser-guard` to open a dedicated Chrome/Edge Browser Guard profile that reports exact tab URLs through the DevTools protocol.

## Run

```powershell
npm install
powershell -ExecutionPolicy Bypass -File scripts/setup_dev.ps1
npm run dev
```

Services:

- Frontend: `http://127.0.0.1:8080`
- FastAPI: `http://127.0.0.1:5051`
- Proctor video sidecar: `http://127.0.0.1:5050`

`node launch_proctorai.js` also starts Browser Guard by default. Set `BROWSER_GUARD_AUTO_START=false` if you do not want it to open a dedicated Chrome/Edge profile.

Runtime logs are written under `logs/`:

- `api_access.log` for structured FastAPI request logs
- `fastapi.log`, `proctor.log`, `frontend.log`, and `browser-guard.log` for launcher child processes

Authenticated operators can inspect:

- `GET /ops/status` for runtime, DB, model, storage, and Browser Guard status
- `GET /ops/metrics` for admin-only platform counters

Production-style local start:

```powershell
Copy-Item .env.production.example .env.production
npm run prod
```

Operational helpers:

```powershell
npm run health
npm run quality
npm run preflight
npm run sql:smoke
npm run sql:backup
```

See [deployment/OPERATOR_RUNBOOK.md](deployment/OPERATOR_RUNBOOK.md) for Windows service installation, scheduled task setup, health checks, SQL backup/restore, and operator verification.

Generated evidence and runtime data are intentionally excluded from Git. Review [docs/DATA_RETENTION.md](docs/DATA_RETENTION.md) and schedule `scripts/invoke_data_retention.ps1` according to institutional policy.

## Roles

- Students can register from the UI, view assigned exams, complete setup, start monitored sessions, and view permitted reports.
- Instructors can create/edit exams, manage lifecycle status, schedule windows, assign/revoke students, review sessions, and generate reports.
- Admins can manage settings and have instructor privileges.
- Admins can use `/admin` to manage institutions and review audit activity.
- Admins can create users, assign roles, move users between institutions, disable accounts, and set temporary passwords from `/admin`.

Instructor/admin accounts are not publicly self-registered. Use bootstrap env variables or create them directly in the database.

## Enterprise Foundation

Schema initialization is non-destructive and creates a default tenant for existing data. New users, exams, sessions, events, evidence, reports, settings, and audit logs are tenant-aware. Admin actions such as login/logout, password reset, exam changes, settings updates, session start/end, evidence capture, reviews, reports, and tenant creation are recorded in `AuditLogs`.

## Proctoring Notes

The platform logs real browser fallback events, Browser Guard exact URL/tab events, audio threshold events, camera status, face-missing/low-light/frozen-camera events, phone detections, and evidence screenshots. If the ONNX model is missing or fails to load, the API reports `phone_detection: unavailable` and does not emit phone events.

Browser signals are accepted only from the authenticated student exam client, a short-lived extension token bound to the active session, or the trusted local companion. The Python sidecar signs AI event posts with the proctor device credential. Heartbeats update connectivity only and never add risk points.

Scored monitoring events are acknowledged only after SQL persistence. Producers retry transient failures with a stable, session-bound ingestion ID, and filtered unique indexes prevent a retry from duplicating browser activity or risk points.

## Test And Verification

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_quality_checks.ps1
```

SQL Server smoke:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_sqlserver_live_smoke_desktop.ps1
```

When using `Trusted_Connection`, run the SQL smoke and app under the Windows account that has SQL Server access. The Codex sandbox account may not have trusted SQL permissions.

Manual checks:

- Guest cannot access protected routes.
- Student registration/login works.
- Forgot/reset password requires SMTP and rejects invalid/used/expired tokens.
- Instructor/admin can create exams and review sessions.
- Student can start/end an assigned exam session.
- `/health` works publicly; authenticated `/proctor/status`, `/sessions`, `/reports/generate`, and report download work.

## Production Notes

- Always set `AUTH_SECRET`, SMTP credentials, and strict `CORS_ORIGINS`.
- Use HTTPS in production and store secrets outside source control.
- Rotate every legacy/E2E credential before deployment; test artifacts must use synthetic identities and disposable credentials.
- Keep SQL Server backups for exam/session evidence.
- Enforce the documented retention and legal-hold policy for captures, reports, logs, exports, runtime profiles, and backups.
- Review automated risk scores manually before academic decisions.
- Run production service/task hosts under a Windows account that has SQL Server access when using trusted authentication.
