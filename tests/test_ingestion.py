import unittest

from hermes_cfe.ingestion import IngestionVerificationError, verify_canonical_ingest

XML = b'''<?xml version="1.0"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" Version="4.0">
 <cfdi:Addenda><cfe:Service xmlns:cfe="urn:demo" RPU="000000000001" Periodo="2026-09"/></cfdi:Addenda>
 <cfdi:Complemento><tfd:TimbreFiscalDigital UUID="AB12CD34-EF56-7890-ABCD-EF1234567890"/></cfdi:Complemento>
</cfdi:Comprobante>'''


class IngestionVerificationTests(unittest.TestCase):
    def setUp(self):
        self.identity = {"cfdi_uuid":"AB12CD34-EF56-7890-ABCD-EF1234567890","rpu":"000000000001","period":"202609","version":"4.0"}
        self.result = {"ingestion_status":"inserted", **{k:v for k,v in self.identity.items() if k != "version"}}

    def test_inserted_result_and_matching_readback_are_verified(self):
        result=verify_canonical_ingest(returncode=0,requested_rpu="000000000001",xml_bytes=XML,rpc_result=self.result,readback={k:v for k,v in self.result.items() if k != "ingestion_status"})
        self.assertEqual(result["ingestion_status"],"inserted")
        self.assertEqual(result["cfdi_uuid"],self.identity["cfdi_uuid"])

    def test_expected_duplicate_is_verified_only_when_readback_matches(self):
        rpc={**self.result,"ingestion_status":"duplicate_sha"}
        self.assertEqual(verify_canonical_ingest(returncode=0,requested_rpu="000000000001",xml_bytes=XML,rpc_result=rpc,readback={k:v for k,v in rpc.items() if k != "ingestion_status"})["ingestion_status"],"duplicate_sha")
        bad={**rpc,"cfdi_uuid":"OTHER"}
        with self.assertRaises(IngestionVerificationError):
            verify_canonical_ingest(returncode=0,requested_rpu="000000000001",xml_bytes=XML,rpc_result=rpc,readback=bad)

    def test_failed_rpc_or_unreadable_result_never_reports_harvested(self):
        bad_rpc = {**self.result, "ingestion_status": "failed"}
        with self.assertRaises(IngestionVerificationError):
            verify_canonical_ingest(returncode=0,requested_rpu="000000000001",xml_bytes=XML,rpc_result=bad_rpc,readback=self.result)
        with self.assertRaises(IngestionVerificationError):
            verify_canonical_ingest(returncode=2,requested_rpu="000000000001",xml_bytes=XML,rpc_result=self.result,readback=self.result)
        bad_readback = {**self.result}
        bad_readback.pop("period")
        with self.assertRaises(IngestionVerificationError):
            verify_canonical_ingest(returncode=0,requested_rpu="000000000001",xml_bytes=XML,rpc_result=self.result,readback=bad_readback)

    def test_wrong_rpu_in_xml_is_rejected_before_ingest(self):
        with self.assertRaisesRegex(ValueError,"RPU"):
            verify_canonical_ingest(returncode=0,requested_rpu="000000000002",xml_bytes=XML,rpc_result=self.result,readback=self.result)


if __name__ == "__main__":
    unittest.main()
