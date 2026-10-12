import unittest

from hermes_cfe.policy import classify_credential_result, can_mark_harvested


class CredentialPolicyTests(unittest.TestCase):
    def test_matching_credential_is_available(self):
        self.assertEqual(classify_credential_result(
            200, {"email":"rpu-000000000001@newman.re","password":"redacted","state":"ready"},
            "rpu-000000000001@newman.re"), "available")

    def test_explicit_missing_is_business_exception_not_signup(self):
        self.assertEqual(classify_credential_result(
            500,{"code":"P0001","message":"account not found"},
            "rpu-000000000001@newman.re"), "missing")

    def test_transient_or_auth_failure_is_unavailable(self):
        for status, body in ((401,{"message":"unauthorized"}),
                             (503,{"message":"try later"}),
                             (200,{"email":"wrong","password":"x","state":"ready"}),
                             (200,"invalid")):
            with self.subTest(status=status, body=body):
                self.assertEqual(classify_credential_result(status,body,"rpu-000000000001@newman.re"),"unavailable")

    def test_only_verified_ingest_terminal_states_can_mark_harvested(self):
        self.assertTrue(can_mark_harvested(0,{"ingestion_status":"inserted","cfdi_uuid":"demo"}))
        self.assertTrue(can_mark_harvested(0,{"ingestion_status":"duplicate_sha","cfdi_uuid":"demo"}))
        for code, payload in ((0,{"state":"harvested"}),
                              (1,{"ingestion_status":"inserted","cfdi_uuid":"demo"}),
                              (0,{"ingestion_status":"failed","cfdi_uuid":"demo"}),
                              (0,{"ingestion_status":"inserted"})):
            with self.subTest(code=code,payload=payload): self.assertFalse(can_mark_harvested(code,payload))


if __name__ == "__main__":
    unittest.main()
