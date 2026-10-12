"""Pure, fail-closed harvest policies; no network or credentials required."""
from __future__ import annotations

from typing import Any


def classify_credential_result(status_code: int, payload: Any, expected_email: str) -> str:
    """Classify only canonical, identity-matched credential RPC responses.

    All malformed, unexpected, or non-success RPC results fail closed as
    unavailable. A missing account is recognized only by the exact documented
    server error tuple; it is not a signal to create or register an account.
    """
    if not isinstance(status_code, int) or isinstance(status_code, bool):
        return "unavailable"
    if not isinstance(expected_email, str) or not expected_email:
        return "unavailable"
    if 200 <= status_code < 300:
        if (isinstance(payload, dict)
                and isinstance(payload.get("email"), str)
                and payload["email"].casefold() == expected_email.casefold()
                and isinstance(payload.get("password"), str)
                and bool(payload["password"])
                and isinstance(payload.get("state"), str)):
            return "available"
        return "unavailable"
    if (status_code == 500
            and isinstance(payload, dict)
            and payload.get("code") == "P0001"
            and payload.get("message") == "account not found"
            and ("email" not in payload or payload.get("email") is None
                 or (isinstance(payload.get("email"), str)
                     and payload["email"].casefold() == expected_email.casefold()))):
        return "missing"
    return "unavailable"


def credential_result_contract(status_code: int, payload: Any, expected_email: str) -> dict[str, Any]:
    """Return a safe decision object; never expose raw RPC payload/secrets."""
    classification = classify_credential_result(status_code, payload, expected_email)
    if classification == "missing":
        return {"classification": "missing", "action": "business_exception"}
    if classification != "available":
        return {"classification": "unavailable", "action": "stop"}
    return {
        "classification": "available",
        "action": "use_credential",
        "credential": {
            "email": payload["email"],
            "password": "[REDACTED]",
            "state": payload["state"],
        },
    }


def can_mark_harvested(returncode: int, ingest_result: Any) -> bool:
    """Require a valid CFDI identity plus an explicit canonical ingest outcome."""
    if returncode != 0 or not isinstance(ingest_result, dict):
        return False
    status = ingest_result.get("ingestion_status")
    uuid = ingest_result.get("cfdi_uuid")
    if not isinstance(uuid, str) or not uuid.strip():
        return False
    return status in {"inserted", "duplicate_sha", "duplicate_period"}
