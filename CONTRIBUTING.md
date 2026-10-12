# Contributing

## Safety boundary

This public repository must contain only code, synthetic fixtures and
redacted documentation. Never commit actual customer data (PDF/XML, RPU, RFC,
email, phone, usage/amount data), secrets, MFA codes, signed URLs, local env or
worker logs. Use synthetic values in tests and report customer-specific work in
a private system, not a public GitHub issue.

## Development loop

1. Choose one issue and one vertical acceptance criterion.
2. Add a deterministic failing test first.
3. Implement the smallest change and run the focused test.
4. Run the full deterministic suite and Mermaid/docs checks.
5. Report skipped network/device/live checks separately; never claim they pass.
6. Review `git diff --check`, tracked files and secret/PII scan before PR.

## Runtime boundaries

- Pull requests must not use production Supabase, Google Workspace, WhatsApp,
  CFE, Browser Use or 2captcha credentials.
- Real device/CFE E2E belongs in an explicitly authorized staging/pilot job,
  isolated from ordinary CI.
- Do not deploy, apply production migrations or change CFE account state from
  this repository without operator approval.

## Mermaid and data contract

When a change affects architecture or data lineage, update the Mermaid files
in `docs/` and the SQL contract with verified names. Clearly mark proposed vs
observed components. Any schema query in docs must be either tested in an
ephemeral DB or labeled as an unverified template.
