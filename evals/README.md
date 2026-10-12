# Deterministic evals

Run the offline, secret-free checks locally:

```bash
python -m unittest discover -s tests -v
python scripts/check_mermaid.py
python -m compileall -q hermes_cfe scripts tests
```

CI requires at least one `test_*.py` under `tests/`, runs the complete unittest
suite, and validates Mermaid source. It does not filter by markers or skip tests
based on secret availability; deterministic tests must remain offline and
secret-free.

## Fixed offline eval inventory

This is a named minimum gate, not a score that may be improved by dropping hard
tests. Each item is independently covered by tests in `tests/test_policy.py`,
`test_cfdi.py`, `test_ingestion.py`, and `test_pipeline.py`.

| Eval | Required evidence |
|---|---|
| E01 credential account binding | matching RPU account is accepted; another account, malformed response, or lookup outage never reaches CFE |
| E02 credential absence | only explicit missing credential becomes the named operator exception; no registration/signup action |
| E03 source object safety | private `cfe-bills` PDF path, immutable object version, optional content SHA-256; wrong/missing identity stops before account access |
| E04 PDF RPU agreement | decoded RPU is 12 digits and agrees with encoded path RPU when present |
| E05 CFDI identity | CFDI 4 root/version, exactly one valid TFD UUID, one unambiguous RPU/period pair, requested-RPU match |
| E06 no XML guessing | malformed XML, unsupported root/version, missing UUID/period, invalid month, ambiguous or mismatched identity fails closed |
| E07 ingest gate | only canonical inserted/expected-duplicate outcomes are eligible; returned UUID/RPU/period match parsed identity |
| E08 canonical read-back | successful read-back must match UUID/RPU/period; missing/mismatch/error never marks harvested |
| E09 state transitions | order is fetch → PDF/RPU → credential → CFE XML → validate → ingest → read-back; early failures do not invoke later stages |
| E10 offline repo safety | full unit suite, Mermaid check, compilation, secret-free CI, and diff hygiene |
| E11 durable queue behavior | atomic claim, unique lease, stale-owner rejection, idempotent object identity, retry budget, exception terminal state, and restart persistence |

Current report after commit `503846a`: **E01–E11 are covered offline with synthetic fixtures; full suite (47 tests), Mermaid check (3 diagrams), compilation, and CI all pass.** This does NOT make the live acceptance suite pass: real-schema verification, golden-CFDI confirmation, production storage adapter, lease renewal, crash/recovery around external side effects, integration, and authorized staging are all **BLOCKED**, not passing or skipped silently.

These checks prove local policy/data-contract behavior only. They do not assert live
Supabase, WhatsApp, phone, CFE, Browser Use, or deployment behavior. Live tests
must have a separate opt-in staging workflow and explicit operator authorization.

Keep the denominator fixed. Report PASS / FAIL / SKIP / BLOCKED separately;
never count a skipped live E2E as passed or shrink the denominator.