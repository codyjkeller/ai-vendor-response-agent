# Security Policy

## Reporting a vulnerability

Use GitHub's private vulnerability reporting: open the **Security** tab of this
repository and choose **Report a vulnerability**. Please do not open a public
issue for security problems.

## Scope

Only the current `main` branch is maintained.

This is a reference implementation, not a hardened product. In particular, the
sign-in and MFA screens in `src/app.py` are a demonstration flow with fixed
demo credentials, and the role table in Settings is not enforced. Do not expose
the Streamlit app to an untrusted network.

## Handling of data

- Do not commit `.env`, `data/` contents from real assessments, `chroma_db/`,
  `auditflow.db`, or `audit_log.csv`.
- When an OpenAI or Anthropic key is configured, retrieved text chunks are sent
  to that provider to generate answers. With an OpenAI key set, document chunks
  are also sent to OpenAI to be embedded. Confirm this is permitted by your
  AI usage policy before indexing confidential documents.
