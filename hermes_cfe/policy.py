"""Pure, fail-closed harvest policies; no network or credentials required."""
from __future__ import annotations

from typing import Any


def classify_credential_result(status_code: int, payload: Any, expected_email: str) -> str:
    """Return available/missing/unavailable without turning RPC faults into absence."""
    if 200 <= status_code < 300:
        if (isinstance(payload, dict)
                and isinstance(payload.get("email"), str)
                and payload["email"].casefold() == expected_email.casefold()
                and isinstance(payload.get("password"), str)
                and bool(payload["password"])
                and isinstance(payload.get("state"), str)):
            return "available"
        return "unavailable"
    if (isinstance(payload, dict)
            and payload.get("code") == "P0001"
            and str(payload.get("message", "")).strip().casefold() == "account not found"
            and (payload.get("email") is None
                 or (isinstance(payload.get("email"), str)
                     and payload["email"].casefold() == expected_email.casefold()))):
        return "missing"
    return "unavailable"


def can_mark_harvested(returncode: int, ingest_result: Any) -> bool:
    """Require a valid CFDI identity plus an explicit canonical ingest outcome."""
    if returncode != 0 or not isinstance(ingest_result, dict):
        return False
    status = ingest_result.get("ingestion_status")
    uuid = ingest_result.get("cfdi_uuid")
    if not isinstance(uuid, str) or not uuid.strip():
        return False
    return status in {"inserted", "duplicate_sha", "duplicate_period"}
