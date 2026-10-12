# Deterministic evals

Run the offline, secret-free checks locally:

```bash
python -m unittest discover -s tests -v
python scripts/check_mermaid.py
```

CI first requires at least one `test_*.py` file under `tests/`, then runs the
entire unittest discovery suite and Mermaid checker. It does not filter by
markers or skip tests based on secret availability; deterministic tests must
remain offline and secret-free.

These checks prove local policy/document contracts only. They do not assert live
Supabase, WhatsApp, phone, CFE, Browser Use, or deployment behavior. Live tests
must have a separate opt-in staging workflow and explicit operator authorization.

Keep a fixed eval inventory/denominator. Report PASS / FAIL / SKIP / BLOCKED
separately; never count a skipped live E2E as passed or shrink the denominator.
