"""Pure, fail-closed harvest policies; no network or credentials required."""
from __future__ import annotations

import re
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


_UUID = re.compile(r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[1-8][0-9A-Fa-f]{3}-[89ABab][0-9A-Fa-f]{3}-[0-9A-Fa-f]{12}$")


def validate_cfdi_identity(requested_rpu: str, parsed: Any) -> dict[str, str]:
    """Validate required CFDI identity fields without filling missing values."""
    if not isinstance(requested_rpu, str) or not re.fullmatch(r"\d{12}", requested_rpu):
        raise ValueError("requested RPU must be exactly 12 digits")
    if not isinstance(parsed, dict):
        raise ValueError("parsed CFDI must be a mapping")
    uuid = parsed.get("cfdi_uuid")
    rpu = parsed.get("rpu")
    period = parsed.get("period")
    if not isinstance(uuid, str) or not _UUID.fullmatch(uuid):
        raise ValueError("CFDI UUID missing or malformed")
    if not isinstance(rpu, str) or not re.fullmatch(r"\d{12}", rpu):
        raise ValueError("CFDI RPU missing or malformed")
    if rpu != requested_rpu:
        raise ValueError("CFDI RPU does not match requested RPU")
    if not isinstance(period, str) or not re.fullmatch(r"\d{6}", period):
        raise ValueError("CFDI period missing or malformed")
    year, month = int(period[:4]), int(period[4:])
    if year < 2000 or month < 1 or month > 12:
        raise ValueError("CFDI period outside accepted calendar range")
    return {"cfdi_uuid": uuid.upper(), "rpu": rpu, "period": period}


def can_mark_harvested(
    returncode: int,
    requested_rpu: str,
    parsed: Any,
    ingest_result: Any,
    readback: Any,
) -> bool:
    """Require parsed identity, a canonical ingest outcome, and matching read-back."""
    if returncode != 0 or not isinstance(ingest_result, dict) or not isinstance(readback, dict):
        return False
    try:
        identity = validate_cfdi_identity(requested_rpu, parsed)
    except (ValueError, TypeError):
        return False
    if ingest_result.get("ingestion_status") not in {"inserted", "duplicate_sha", "duplicate_period"}:
        return False
    for record in (ingest_result, readback):
        for key, value in identity.items():
            if record.get(key) != value:
                return False
    return True
