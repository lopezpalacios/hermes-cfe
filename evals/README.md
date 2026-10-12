# Deterministic evals

The unit suite is intentionally offline and secret-free:

```bash
python -m unittest discover -s tests -v
python scripts/check_mermaid.py
```

These checks prove local policy/document contracts only. They do not assert live
Supabase, WhatsApp, phone, CFE, Browser Use, or deployment behavior. Live tests
must have a separate opt-in staging workflow and explicit operator authorization.

Keep a fixed eval inventory/denominator. Report PASS / FAIL / SKIP / BLOCKED
separately; never count a skipped live E2E as passed or shrink the denominator.
