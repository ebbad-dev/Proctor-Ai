# Data retention and quarantine

ProctorAI captures biometric-adjacent images, browser activity, audit logs, reports, exports, local browser profile data, and database backups. Treat all generated data as confidential student records.

The default retention periods are defined in `config/retention_policy.json`:

- screenshots: 30 days
- generated reports: 90 days
- application logs: 14 days
- exports: 30 days
- end-to-end test artifacts: 7 days
- local browser runtime/profile data: 1 day
- database backups: 30 days
- quarantined files: 30 additional days before permanent deletion

Run a non-mutating preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/invoke_data_retention.ps1
```

Move expired files to quarantine:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/invoke_data_retention.ps1 -Apply -QuarantineRoot C:\ProctorAI-Quarantine\retention
```

Permanent deletion only occurs when both `-Apply` and `-PurgeQuarantine` are supplied. Verify institutional policy, legal holds, backup health, and the dry-run list first. Restrict the quarantine directory to authorized operators and do not sync it to consumer cloud storage.

Test fixtures must use synthetic identities and unique disposable credentials. Never commit `.env`, `seed.json`, screenshots, reports, runtime profiles, logs, database backups, or exported student data.

