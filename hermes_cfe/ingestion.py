"""Canonical-ingest verification policy. Database and RPC access is injected by adapters."""
from __future__ import annotations

from typing import Any

from hermes_cfe.cfdi import parse_cfdi_identity
from hermes_cfe.policy import can_mark_harvested


class IngestionVerificationError(RuntimeError):
    """Raised when canonical ingest cannot be proven from its response and read-back."""


def verify_canonical_ingest(
    *,
    returncode: int,
    requested_rpu: str,
    xml_bytes: bytes,
    rpc_result: Any,
    readback: Any,
) -> dict[str, str]:
    """Parse identity, check exact RPC/read-back contract, then return safe harvest summary."""
    identity = parse_cfdi_identity(xml_bytes, requested_rpu)
    if not can_mark_harvested(returncode, requested_rpu, identity, rpc_result, readback):
        raise IngestionVerificationError("canonical CFDI ingest/read-back did not verify")
    return {**identity, "ingestion_status": rpc_result["ingestion_status"]}
