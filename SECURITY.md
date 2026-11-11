# Security Policy

## Reporting a vulnerability

Use GitHub's private vulnerability reporting: open the **Security** tab of this
repository and choose **Report a vulnerability**. Please do not open a public
issue for security problems.

## Scope

Only the current `main` branch is maintained.

The web app authenticates users through an OpenID Connect identity provider and
refuses access when none is configured. Roles are enforced in code: Read Only
users cannot upload documents or add answers, and only Administrators can
delete documents or change roles. The editable permission table in Settings is
a reference and is not itself enforced.

Demo mode (`AUDITFLOW_DEMO_MODE=true`) replaces sign-in with a simulated screen
that checks no credentials. Never enable it with real documents or on a
reachable network.

Not yet covered: the SQLite database, audit log, and uploaded documents are
stored unencrypted on local disk, and the audit log is an append-only CSV
without tamper protection. Run the app behind TLS on a trusted network.

## Handling of data

- Do not commit `.env`, `data/` contents from real assessments, `chroma_db/`,
  `auditflow.db`, or `audit_log.csv`.
- When an OpenAI or Anthropic key is configured, retrieved text chunks are sent
  to that provider to generate answers. With an OpenAI key set, document chunks
  are also sent to OpenAI to be embedded. Confirm this is permitted by your
  AI usage policy before indexing confidential documents.
