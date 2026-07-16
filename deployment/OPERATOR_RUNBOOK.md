# ProctorAI Operator Runbook

This runbook covers the local production-style deployment for the FastAPI, React, SQL Server, and proctoring sidecar stack.

## Prerequisites

- Windows account with SQL Server access to `localhost / ProctorAI_Lite`.
- Node.js 24 and npm on PATH.
- CPython 3.12.13. Dependencies are installed from `requirements.lock.txt` into `.venv`.
- ODBC Driver 17 or 18 for SQL Server.
- SMTP account configured for password reset emails.
- Optional: `models/phone_detector.onnx` for phone detection.

## First Setup

```powershell
Copy-Item .env.production.example .env.production
powershell -ExecutionPolicy Bypass -File scripts/setup_dev.ps1
powershell -ExecutionPolicy Bypass -File scripts/run_sqlserver_live_smoke_desktop.ps1
```

Keep the active clone on a local non-synchronized disk. Generated evidence, logs, runtime browser profiles, backups, and the virtual environment must not be committed or stored in consumer cloud-synchronized source folders.

Edit `.env.production` before starting the app:

- Set `AUTH_SECRET` to a long random value.
- Set `PROCTOR_DEVICE_SECRET` to a separate long random value when the sidecar or Browser Guard companion runs on another trusted host. Local single-host deployments derive it from `AUTH_SECRET` when omitted.
- Set `CORS_ORIGINS` to the real frontend origins.
- Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, and `SMTP_TLS`.
- Set `PROCTORAI_BOOTSTRAP_ADMIN_EMAIL` and `PROCTORAI_BOOTSTRAP_ADMIN_PASSWORD` only for the first admin bootstrap.
- Confirm `PROCTORAI_DB_SERVER`, `PROCTORAI_DB_NAME`, and `PROCTORAI_DB_DRIVER`.

## Start And Stop

Start the full stack:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_production.ps1 -BuildFrontend
```

Health check:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/health_check.ps1
```

Local hardware/model preflight:

```powershell
.venv\Scripts\python.exe scripts\hardware_preflight.py --require-camera --require-microphone
```

Use `Ctrl+C` in the launcher terminal to stop child processes. Logs are written to `logs/`.

## Windows Service

The service installer uses NSSM because Node and PowerShell are not native Windows services.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_windows_service.ps1
nssm start ProctorAI
```

To remove it:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_windows_service.ps1 -Uninstall
```

Run service installation from an elevated PowerShell prompt. The service account must have SQL Server access if `Trusted_Connection` is used.

## Scheduled Task Alternative

For a workstation deployment, a scheduled task at logon is often simpler than a Windows service:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_windows_scheduled_task.ps1
Start-ScheduledTask -TaskName ProctorAI
```

Remove it:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_windows_scheduled_task.ps1 -Uninstall
```

## SQL Server Backup And Restore

Backup:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/backup_sqlserver.ps1
```

By default the backup script writes to SQL Server's configured backup directory because the SQL Server service account usually cannot write into OneDrive or project folders.

Restore:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/restore_sqlserver.ps1 -BackupFile .\backups\ProctorAI_Lite_YYYYMMDD_HHMMSS.bak -ConfirmRestore
```

Restore replaces the target database and should only be run after confirming the backup file and maintenance window.

## Evidence retention

Preview expired generated data without changing anything:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/invoke_data_retention.ps1
```

Move expired data into an access-restricted quarantine directory:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/invoke_data_retention.ps1 -Apply -QuarantineRoot C:\ProctorAI-Quarantine\retention
```

See `docs/DATA_RETENTION.md`. Confirm institutional retention rules and legal holds before changing defaults or permanently purging quarantine.

## Disposable E2E credentials

The E2E seeder never uses repository-defined passwords. It reads the optional
`PROCTORAI_E2E_*` variables from the environment and otherwise generates separate
high-entropy passwords for the admin and student identities on every run:

```powershell
.venv\Scripts\python.exe scripts\prepare_e2e_seed.py
node scripts\capture_e2e.js
```

The seeder rotates the passwords of existing E2E identities and writes the temporary
credentials to ignored `e2e_artifacts/seed.json` for the capture process. The values
are not printed. Restrict access to that directory, delete it after verification, and
disable or remove E2E identities from any non-test database when the run is complete.

## Verification Checklist

- `GET http://127.0.0.1:5051/health` returns healthy.
- `GET http://127.0.0.1:5051/proctor/status` reports camera, microphone, database, and model status honestly.
- `GET http://127.0.0.1:5050/ping` returns from the video sidecar.
- `http://127.0.0.1:8080/login` loads.
- Guest routes redirect correctly.
- Admin can create instructor/student accounts.
- Instructor can create and assign an exam.
- Student can start an assigned session and submit it.
- Browser/tab/audio/camera events appear in the session timeline and risk score.
- Instructor can review a session and generate a report.

## Known Operational Limits

- Phone detection requires `models/phone_detector.onnx`; without it, the platform reports phone detection unavailable and does not fake events.
- SMTP must be configured before password reset emails can be sent.
- Browser Guard exact URL tracking requires the extension or dedicated browser guard profile. Fallback tab/window events still work.
- Trusted SQL Server authentication depends on the Windows account running the app.
