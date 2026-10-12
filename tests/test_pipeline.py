import unittest

from hermes_cfe.pipeline import run_harvest_job

VALID_XML=b'''<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" Version="4.0"><cfdi:Addenda><cfe:Service xmlns:cfe="urn:demo" RPU="000000000001" Periodo="2026-09"/></cfdi:Addenda><cfdi:Complemento><tfd:TimbreFiscalDigital UUID="AB12CD34-EF56-7890-ABCD-EF1234567890"/></cfdi:Complemento></cfdi:Comprobante>'''

class FakeAdapters:
    def __init__(self):
        self.calls=[]; self.credential_state="available"; self.xml=VALID_XML
        self.identity={"ingestion_status":"inserted","cfdi_uuid":"AB12CD34-EF56-7890-ABCD-EF1234567890","rpu":"000000000001","period":"202609"}
        self.ingest_result=dict(self.identity); self.readback_record={k:v for k,v in self.identity.items() if k!="ingestion_status"}
        self.object_etag='"version-1"'; self.pdf=b"%PDF-1.7 synthetic"; self.account_email="rpu-000000000001@newman.re"
    def fetch_object(self,bucket,key): self.calls.append(("fetch",bucket,key)); return {"bytes":self.pdf,"etag":self.object_etag}
    def decode_and_validate_pdf(self,data): self.calls.append(("decode",data)); return {"rpu":"000000000001","fields":{"total":12345}}
    def lookup_credential(self,rpu): self.calls.append(("credential",rpu)); return {"classification":self.credential_state,"credential":{"email":self.account_email}}
    def harvest_xml(self,rpu,credential): self.calls.append(("harvest",rpu)); return self.xml
    def parse_xml(self,xml_bytes,requested_rpu): self.calls.append(("parse",requested_rpu)); from hermes_cfe.cfdi import parse_cfdi_identity; return parse_cfdi_identity(xml_bytes,requested_rpu)
    def ingest_xml(self,parsed,xml_bytes,source_key): self.calls.append(("ingest",source_key)); return self.ingest_result
    def readback(self,cfdi_uuid): self.calls.append(("readback",cfdi_uuid)); return self.readback_record

class HarvestPipelineTests(unittest.TestCase):
    def setUp(self): self.adapter=FakeAdapters(); self.job={"bucket":"cfe-bills","object_key":"cfe/2026/09/000000000001/bill.pdf","object_version":"version-1"}
    def test_happy_path_marks_harvested_only_after_matching_readback(self):
        result=run_harvest_job(self.job,self.adapter); self.assertEqual(result["state"],"harvested"); self.assertEqual(result["cfdi_uuid"],self.adapter.identity["cfdi_uuid"]); self.assertEqual([x[0] for x in self.adapter.calls],["fetch","decode","credential","harvest","parse","ingest","readback"])
    def test_object_version_mismatch_stops_before_decoding_or_provider_calls(self):
        self.adapter.object_etag='"new-version"'; result=run_harvest_job(self.job,self.adapter); self.assertEqual(result["state"],"retryable_failure"); self.assertEqual([x[0] for x in self.adapter.calls],["fetch"])
    def test_content_hash_mismatch_stops_before_decode_or_external_access(self):
        job={**self.job,"sha256":"0"*64}
        result=run_harvest_job(job,self.adapter)
        self.assertEqual(result["error_class"],"object_content_hash_mismatch")
        self.assertEqual([x[0] for x in self.adapter.calls],["fetch"])
    def test_storage_path_rpu_must_match_decoded_pdf_rpu(self):
        job={**self.job,"object_key":"cfe/2026/09/000000000002/bill.pdf"}
        result=run_harvest_job(job,self.adapter)
        self.assertEqual(result["error_class"],"rpu_ambiguous_or_invalid")
        self.assertNotIn("credential",[x[0] for x in self.adapter.calls])
    def test_missing_credential_is_business_exception_and_never_harvests(self):
        self.adapter.credential_state="missing"; result=run_harvest_job(self.job,self.adapter); self.assertEqual(result["state"],"business_exception"); self.assertNotIn("harvest",[x[0] for x in self.adapter.calls])
    def test_unavailable_credential_is_retryable_and_never_harvests(self):
        self.adapter.credential_state="unavailable"; result=run_harvest_job(self.job,self.adapter); self.assertEqual(result["state"],"retryable_failure"); self.assertNotIn("harvest",[x[0] for x in self.adapter.calls])
    def test_rpu_mismatch_stops_before_credential_lookup(self):
        self.adapter.decode_and_validate_pdf=lambda data:{"rpu":"000000000002","fields":{}}; result=run_harvest_job(self.job,self.adapter); self.assertEqual(result["state"],"business_exception"); self.assertNotIn("credential",[x[0] for x in self.adapter.calls])
    def test_readback_mismatch_never_marks_harvested(self):
        self.adapter.readback_record={**self.adapter.readback_record,"cfdi_uuid":"OTHER"}; result=run_harvest_job(self.job,self.adapter); self.assertEqual(result["state"],"retryable_failure"); self.assertIn("readback",[x[0] for x in self.adapter.calls])
    def test_wrong_bucket_or_non_pdf_is_rejected_without_io(self):
        for bad in ({**self.job,"bucket":"public"},{**self.job,"object_key":"x.xml"}):
            with self.subTest(bad=bad):
                adapter=FakeAdapters(); result=run_harvest_job(bad,adapter); self.assertEqual(result["state"],"business_exception"); self.assertEqual(adapter.calls,[])

if __name__=="__main__": unittest.main()
