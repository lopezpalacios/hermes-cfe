# Durable queue contract

## Implemented offline

`hermes_cfe.queue.DurableJobQueue` is a local SQLite reference implementation using WAL, full synchronous commits, unique `(bucket, object_key, object_version)` identity, `BEGIN IMMEDIATE` atomic claims, expiring random leases, token-checked state transitions, attempt limits, exponential retry delay, and persistent job state. It is exercised with temporary databases and concurrent claimant threads.

## Not production-bound

This queue is not connected to Supabase or Storage and is not an approved replacement for the live `hermes.jobs` table. The current repo migrations in `/opt/data/cfe-scrapper` are not in this public repo and include old non-lease RPCs (`rpc_claim_scrape_job`, `rpc_finish_scrape_job`). Never assume those names/columns support this contract. Before an adapter or migration is built, verify the live Supabase schema and project authorization, document claim/lease and finish semantics, then add migration contract tests. Do not apply a production migration in this step.

SQLite here is a one-host durable queue, not a distributed high-availability broker. This class serializes threads sharing an instance but does not implement worker heartbeats/lease renewal, signal handling, queue metrics/alerting, encrypted backup/restore, poison-message quarantine UI, multi-host failover, or atomic transaction spanning CFE harvesting and database ingest. Retry after a crash can repeat external work; canonical ingest must remain idempotent and proven before deployment.

## Safety contract

- Storage object version is required and part of the unique key; never enqueue a mutable key alone.
- Only the lease-token owner can finish/fail; expired/stale claims are rejected.
- Explicit business exceptions are terminal; retryable errors retry only up to a bounded attempt count.
- Job results must be compact and non-secret; credentials and signed URLs must never enter queue JSON.
- No live CFE fetch or Supabase write is performed by this reference queue.
