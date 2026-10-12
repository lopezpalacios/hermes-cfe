import unittest

from hermes_cfe.cfdi import parse_cfdi_identity


VALID_XML = b'''<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
  xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" Version="4.0"
  Fecha="2026-10-02T10:15:00">
  <cfdi:Addenda><cfe:RPU xmlns:cfe="urn:demo:cfe" RPU="000000000001" Periodo="2026-09"/></cfdi:Addenda>
  <cfdi:Complemento><tfd:TimbreFiscalDigital UUID="AB12CD34-EF56-7890-ABCD-EF1234567890"/></cfdi:Complemento>
</cfdi:Comprobante>'''


class CfdiIdentityTests(unittest.TestCase):
    def test_extracts_canonical_cfdi_identity_from_namespaced_document(self):
        self.assertEqual(parse_cfdi_identity(VALID_XML, "000000000001"), {
            "cfdi_uuid": "AB12CD34-EF56-7890-ABCD-EF1234567890",
            "rpu": "000000000001",
            "period": "202609",
            "version": "4.0",
        })

    def test_rejects_non_cfdi_xml(self):
        with self.assertRaisesRegex(ValueError, "CFDI"):
            parse_cfdi_identity(b"<html/>", "000000000001")

    def test_rejects_missing_timbre_uuid(self):
        xml = VALID_XML.replace(b' UUID="AB12CD34-EF56-7890-ABCD-EF1234567890"', b"")
        with self.assertRaisesRegex(ValueError, "UUID"):
            parse_cfdi_identity(xml, "000000000001")

    def test_rejects_rpu_mismatch(self):
        with self.assertRaisesRegex(ValueError, "RPU"):
            parse_cfdi_identity(VALID_XML, "000000000002")

    def test_rejects_ambiguous_addenda_identity(self):
        xml = VALID_XML.replace(b"</cfdi:Addenda>", b'<cfe:RPU xmlns:cfe="urn:demo:cfe" RPU="000000000002" Periodo="2026-09"/></cfdi:Addenda>')
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            parse_cfdi_identity(xml, "000000000001")

    def test_rejects_missing_period_instead_of_substituting_current_month(self):
        xml = VALID_XML.replace(b' Periodo="2026-09"', b"")
        with self.assertRaisesRegex(ValueError, "period"):
            parse_cfdi_identity(xml, "000000000001")


if __name__ == "__main__":
    unittest.main()
