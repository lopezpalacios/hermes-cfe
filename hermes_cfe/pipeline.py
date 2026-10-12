"""Adapter-driven harvest state machine; no live service integrations here."""
from __future__ import annotations

from typing import Any, Protocol

from hermes_cfe.cfdi import parse_cfdi_identity
from hermes_cfe.ingestion import IngestionVerificationError, verify_canonical_ingest


class HarvestAdapters(Protocol):
    def fetch_object(self, bucket: str, key: str) -> dict[str, Any]: ...
    def decode_and_validate_pdf(self, data: bytes) -> dict[str, Any]: ...
    def lookup_credential(self, rpu: str) -> dict[str, Any]: ...
    def harvest_xml(self, rpu: str, credential: dict[str, Any]) -> bytes: ...
    def parse_xml(self, xml_bytes: bytes, requested_rpu: str) -> dict[str, Any]: ...
    def ingest_xml(self, parsed: dict[str, Any], xml_bytes: bytes, source_key: str) -> dict[str, Any]: ...
    def readback(self, cfdi_uuid: str) -> dict[str, Any] | None: ...


def run_harvest_job(job: dict[str, Any], adapters: HarvestAdapters) -> dict[str, Any]:
    """Run one bounded logical pipeline job and return redacted state/summary."""
    bucket = job.get("bucket")
    key = job.get("object_key")
    if bucket != "cfe-bills" or not isinstance(key, str) or not key.lower().endswith(".pdf"):
        return {"state":"business_exception","error_class":"invalid_source_object"}

    try:
        obj = adapters.fetch_object(bucket, key)
    except Exception as exc:
        return {"state":"retryable_failure","error_class":"object_fetch_failed","detail":type(exc).__name__}
    expected_version = str(job.get("object_version", ""))
    actual_version = str(obj.get("etag", ""))
    if expected_version and actual_version and expected_version.strip('"') != actual_version.strip('"'):
        return {"state":"retryable_failure","error_class":"object_version_changed"}
    data = obj.get("bytes")
    if not isinstance(data, bytes) or not data.startswith(b"%PDF-"):
        return {"state":"business_exception","error_class":"invalid_pdf"}
    expected_sha = job.get("sha256")
    if expected_sha is not None:
        import hashlib
        if not isinstance(expected_sha, str) or hashlib.sha256(data).hexdigest() != expected_sha.lower():
            return {"state":"retryable_failure","error_class":"object_content_hash_mismatch"}

    try:
        decoded = adapters.decode_and_validate_pdf(data)
    except Exception as exc:
        return {"state":"business_exception","error_class":"pdf_or_rpu_invalid","detail":type(exc).__name__}
    rpu = decoded.get("rpu") if isinstance(decoded, dict) else None
    path_rpu = key.split("/")[-2] if len(key.split("/")) >= 2 else None
    if (not isinstance(rpu,str) or len(rpu)!=12 or not rpu.isascii() or not rpu.isdigit()
            or (path_rpu and path_rpu.isascii() and path_rpu.isdigit() and path_rpu != rpu)):
        return {"state":"business_exception","error_class":"rpu_ambiguous_or_invalid"}

    try:
        lookup = adapters.lookup_credential(rpu)
    except Exception as exc:
        return {"state":"retryable_failure","rpu":rpu,"error_class":"credential_lookup_unavailable","detail":type(exc).__name__}
    classification = lookup.get("classification") if isinstance(lookup,dict) else None
    if classification == "missing":
        return {"state":"business_exception","rpu":rpu,"exception_code":"CONTIGO_ACCOUNT_VERIFIED_CREDENTIAL_MISSING"}
    if classification != "available" or not isinstance(lookup.get("credential"),dict):
        return {"state":"retryable_failure","rpu":rpu,"error_class":"credential_lookup_unavailable"}

    try:
        xml_bytes = adapters.harvest_xml(rpu,lookup["credential"])
    except Exception as exc:
        return {"state":"retryable_failure","rpu":rpu,"error_class":"cfe_harvest_failed","detail":type(exc).__name__}
    if not isinstance(xml_bytes,bytes):
        return {"state":"business_exception","rpu":rpu,"error_class":"xml_not_bytes"}

    try:
        # Parse and validate XML identity before any write, so a bad/mismatched
        # CFDI cannot be inserted into the canonical intake path.
        parsed = adapters.parse_xml(xml_bytes,rpu)
        identity = parse_cfdi_identity(xml_bytes,rpu)
        for key_name in ("cfdi_uuid","rpu","period"):
            if parsed.get(key_name) != identity[key_name]:
                raise ValueError(f"parser identity mismatch: {key_name}")
    except Exception as exc:
        return {"state":"business_exception","rpu":rpu,"error_class":"cfdi_identity_invalid","detail":type(exc).__name__}

    try:
        ingest_result = adapters.ingest_xml(parsed,xml_bytes,key)
    except Exception as exc:
        return {"state":"retryable_failure","rpu":rpu,"error_class":"canonical_ingest_failed","detail":type(exc).__name__}
    try:
        readback = adapters.readback(identity["cfdi_uuid"])
        verified = verify_canonical_ingest(returncode=0,requested_rpu=rpu,xml_bytes=xml_bytes,
                                           rpc_result=ingest_result,readback=readback)
    except Exception as exc:
        return {"state":"retryable_failure","rpu":rpu,"error_class":"ingest_readback_unverified","detail":type(exc).__name__}
    return {"state":"harvested",**verified,"source_object_key":key}
