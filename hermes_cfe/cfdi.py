"""Strict CFDI identity extraction for offline contracts."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

UUID_RE = re.compile(r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[1-8][0-9A-Fa-f]{3}-[89ABab][0-9A-Fa-f]{3}-[0-9A-Fa-f]{12}$")
RPU_RE = re.compile(r"^\d{12}$")
CFDI_NS = "http://www.sat.gob.mx/cfd/"
TFD_NS = "http://www.sat.gob.mx/TimbreFiscalDigital"


def parse_cfdi_identity(xml_bytes: bytes, requested_rpu: str) -> dict[str, str]:
    """Return only validated CFDI version/UUID/RPU/period; never guess missing fields."""
    if not isinstance(requested_rpu, str) or not RPU_RE.fullmatch(requested_rpu):
        raise ValueError("requested RPU must be exactly 12 digits")
    try:
        root = ET.fromstring(xml_bytes)
    except (ET.ParseError, TypeError) as exc:
        raise ValueError("malformed CFDI XML") from exc
    if root.tag != f"{{{CFDI_NS}4}}Comprobante":
        raise ValueError("document is not a CFDI 4 Comprobante")
    version = root.attrib.get("Version")
    if version != "4.0":
        raise ValueError("CFDI version missing or unsupported")

    uuids = {
        node.attrib["UUID"].strip().upper()
        for node in root.iter(f"{{{TFD_NS}}}TimbreFiscalDigital")
        if isinstance(node.attrib.get("UUID"), str) and node.attrib["UUID"].strip()
    }
    if len(uuids) != 1:
        raise ValueError("CFDI must contain exactly one TimbreFiscalDigital UUID")
    uuid = next(iter(uuids))
    if not UUID_RE.fullmatch(uuid):
        raise ValueError("CFDI UUID malformed")

    candidates: list[tuple[str, str]] = []
    for node in root.iter():
        rpu_values = [value.strip() for key, value in node.attrib.items()
                      if key.casefold() in {"rpu", "numerorservicio", "no_rpu"}
                      and RPU_RE.fullmatch(value.strip())]
        period_values = []
        for pkey, pvalue in node.attrib.items():
            if pkey.casefold() in {"periodo", "anio_mes", "period"}:
                match = re.fullmatch(r"(\d{4})[-/]?(\d{2})", pvalue.strip())
                if match:
                    period_values.append(match.group(1) + match.group(2))
        # Keep element boundaries: duplicate identical entries are still ambiguous.
        if rpu_values or period_values:
            if len(rpu_values) != 1 or len(period_values) != 1:
                raise ValueError("CFDI addenda identity element must contain exactly one RPU and period")
            candidates.append((rpu_values[0], period_values[0]))
    if len(candidates) != 1:
        raise ValueError("CFDI addenda must contain exactly one unambiguous RPU/period pair")
    rpu, period = candidates[0]
    if rpu != requested_rpu:
        raise ValueError("CFDI RPU does not match requested RPU")
    year, month = int(period[:4]), int(period[4:])
    if year < 2000 or month < 1 or month > 12:
        raise ValueError("CFDI period outside accepted calendar range")
    return {"cfdi_uuid": uuid, "rpu": rpu, "period": period, "version": version}
