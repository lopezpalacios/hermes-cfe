## Summary

<!-- One vertical slice; link the public issue. Never include customer PII. -->

## Contract / diagrams updated

- [ ] Mermaid architecture/data lifecycle/operations docs updated if affected
- [ ] SQL identifiers/signatures verified or explicitly marked unverified

## Evidence

- [ ] New deterministic test written first and observed failing
- [ ] Focused tests pass
- [ ] Full deterministic suite and Mermaid check pass
- [ ] Live checks are separated as PASS / SKIP / BLOCKED

## Safety and privacy

- [ ] No credentials, real invoices/CFDIs, RPUs/RFCs, logs, MFA, signed URLs
- [ ] No production migration/deploy or live CFE/WhatsApp side effects
- [ ] Harvested state requires canonical RPC result + read-back verification

## Risk / rollback

<!-- Explain states affected, retry/idempotency effects and rollback. -->
