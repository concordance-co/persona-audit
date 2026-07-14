# Security

## Reporting

Please report suspected vulnerabilities privately via GitHub security
advisories on this repository (Security tab → "Report a vulnerability")
rather than public issues.

## Scope and posture

Persona Audit is a **local-first analysis tool**, not a hosted service:

- The API has **no authentication by design**. It is meant to run on
  localhost against your own data. If you deploy it anywhere shared, put it
  behind your own auth/reverse proxy and set `PERSONA_AUDIT_CORS_ORIGINS`
  to explicit origins (credentials are only allowed with explicit origins).
- Database access is configured via `PERSONA_AUDIT_DATABASE_URL`; secrets
  live in the untracked `.env`. Never commit `.env` or print its values.
- Table names from configuration are validated as SQL identifiers and all
  query values are parameterized.
- Modal credentials and `HF_TOKEN` are only used by the opt-in scoring
  workflows; the dashboard itself never needs them.

Conversation traces are sensitive by nature: treat any imported dataset as
private unless you have explicit rights to publish it (see the privacy notes
in [README.md](README.md) and docs/release-checklist.md).
