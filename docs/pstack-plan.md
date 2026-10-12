# Pstack hill-climb plan

Current environment did not include the `pstack` executable or external coding
agent CLIs. This document is the orchestration contract; it does not claim any
pstack run. Until installed/configured, use GitHub Issues and independent
worktrees/tasks with one integrator.

## Parallel lanes (separate worktrees, one owner per file set)

1. **Eval/contract lane** — deterministic tests, fixed eval denominator, API and
   queue state contract, no production credentials.
2. **Queue/worker lane** — verified schema, idempotent Storage event, atomic
   claim/lease/recovery, Contigo adapter boundary, no live migration/deploy.
3. **Portal lane** — static prototype and UX contract only; fictional demo data.
4. **Integrator/reviewer** — inspect diffs, reconcile contracts, run full suite,
   security/PII scan, authorize no external side-effects by default.

Agents should report touched files, tests run, test outcomes, dependencies and
unverified assumptions. Do not let separate lanes edit the same files.

## Phases and gates

### 0. Make evals trustworthy

- Align suite inventory/weights across `evals/run.py`, README and install docs.
- Explicitly report SKIP/BLOCKED, never count skips as passes or remove them from
  a fixed denominator.
- Replace developer-home absolute paths with repo-relative fixture lookup.
- Split pure local tests from live RPC, endpoint and phone tests.
- Gate live tests behind explicit opt-in, staging URL and named test data.

**Gate:** clean checkout runs deterministic tier without network/secret; 10 runs
have identical outcomes; missing suite/import error fails the gate.

### 1. Safe intake validation

- Strict PDF, RPU and invoice-fields contract; barcode and labeled field must
  agree where both exist.
- Ambiguous/multi-service/malformed documents park for review.

**Gate:** test valid, corrupt, multi-RPU, mismatched total and wrong RPU; no
registration, worker call or ingest on invalid input.

### 2. Credential decision safety

- Distinguish credential found, explicit confirmed absent, unauthorized, timeout,
  5xx, malformed response and wrong-account response.
- Only found credential proceeds to harvest. Missing/verified account is a
  terminal business exception pending operator recovery. No automatic signup.

**Gate:** fault-matrix tests prove that only a valid matching credential can
reach the harvest adapter.

### 3. Durable storage queue

- Verify live Storage schema/event behavior first.
- Queue bucket/key/version, enforce unique idempotency, bounded attempts,
  next-attempt and lease timestamps.
- Trigger performs metadata enqueue only. No outbound CFE request inside trigger.

**Gate:** same version deduplicates; new version follows documented semantics;
parallel claim yields one owner; insertion/update uploader behavior tested.

### 4. Worker lifecycle

- Persistent supervised worker on Mac mini; outbound polling through least-
  privilege RPC. Claim with lease, heartbeat, retry schedule, bounded jitter.
- Serialize operations requiring the single Android/ADB resource.
- Restart/crash recovery and explicit operator requeue.

**Gate:** kill worker after claim and during each external adapter; retry does not
produce duplicate logical ingestion; queue alerts on stuck work.

### 5. CFDI ingest correctness

- Verify parser requires root/namespace/version, UUID, RPU, period, and expected
  issuer as applicable. Never substitute request RPU/current month for missing XML.
- Call only the canonical ingest RPC. Validate its response and read back by
  canonical key/hash/UUID.

**Gate:** invalid/mismatched XML cannot ingest; inserted and expected duplicate
are separately tested; anything else cannot be marked harvested.

### 6. Ops portal

- API is read-only by default; explicit permissions for retry/requeue.
- Portfolio, receipts, job monitor, detail/evidence, exception inbox.
- Demo fixture values visibly marked fiction. Do not leak signed URLs or PDF
  contents in public output.

**Gate:** all job states have empty/loading/success/error variants and accessible
keyboard interactions; control actions are server-authorized and auditable.

### 7. Staging and supervised pilot

- Provision staging queue and isolated test RPU/credentials; explicit operator
  authorization for real WhatsApp/phone/CFE interactions.
- Confirm object, job, XML, canonical DB row, job terminal state, notifications,
  retry and requeue read-back.

**Gate:** one end-to-end is evidence only for pilot; repeat across new object,
duplicate, transient outage, worker restart and business exception before
production label.

## Fixed eval rules

- Establish one fixed point denominator after the eval inventory is reconciled.
- Every run reports `passed`, `failed`, `skipped`, `blocked`, and the denominator.
- Skips/blocked never count as success; do not lower the denominator to improve
  score.
- Ledger fields: UTC timestamp, phase, hypothesis, change, test IDs, exact
  results, evidence link/path, live-vs-local, decision.
- Only one live provider test at a time on the shared phone; budget and network
  costs are recorded before any authorized live run.
