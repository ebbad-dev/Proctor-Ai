# Security policy

Do not report vulnerabilities through public issues when they include credentials, student data, captures, or reproducible access to a deployed instance. Contact the repository owner privately and include the affected version, impact, and minimal reproduction steps.

Before deployment:

- rotate `AUTH_SECRET`, `PROCTOR_DEVICE_SECRET`, SMTP credentials, database credentials, bootstrap credentials, and all E2E accounts;
- use HTTPS and a restricted SQL Server identity;
- keep `.env` and all generated evidence outside version control;
- run the regression suite and dependency audit;
- review `docs/DATA_RETENTION.md` and apply the institution's retention/legal-hold policy.
