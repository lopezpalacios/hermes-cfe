import unittest

from hermes_cfe.policy import (
    classify_credential_result,
    credential_result_contract,
    can_mark_harvested,
)


class CredentialPolicyTests(unittest.TestCase):
    def test_matching_credential_is_available(self):
        self.assertEqual(classify_credential_result(
            200, {"email": "rpu-000000000001@newman.re", "password": "synthetic-secret", "state": "ready"},
            "rpu-000000000001@newman.re"), "available")

    def test_explicit_missing_routes_only_to_business_exception(self):
        contract = credential_result_contract(
            500, {"code": "P0001", "message": "account not found"},
            "rpu-000000000001@newman.re")
        self.assertEqual(contract["classification"], "missing")
        self.assertEqual(contract["action"], "business_exception")
        self.assertNotIn("register", contract["action"])
        self.assertNotIn("signup", contract["action"])

    def test_cross_account_success_is_unavailable(self):
        self.assertEqual(classify_credential_result(
            200, {"email": "rpu-000000000002@newman.re", "password": "synthetic-secret", "state": "ready"},
            "rpu-000000000001@newman.re"), "unavailable")

    def test_noncanonical_rpc_error_does_not_classify_as_missing(self):
        for status, payload in (
            (500, {"code": "P0001", "message": "account not found", "email": "rpu-000000000002@newman.re"}),
            (500, {"code": "P0001", "message": "Account not found."}),
            (404, {"code": "P0001", "message": "account not found"}),
            (500, {"code": "23505", "message": "account not found"}),
        ):
            with self.subTest(status=status, payload=payload):
                self.assertEqual(classify_credential_result(
                    status, payload, "rpu-000000000001@newman.re"), "unavailable")

    def test_safe_result_contract_redacts_password(self):
        secret = "synthetic-only-password"
        result = credential_result_contract(
            200, {"email": "rpu-000000000001@newman.re", "password": secret, "state": "ready"},
            "rpu-000000000001@newman.re")
        self.assertEqual(result, {
            "classification": "available",
            "action": "use_credential",
            "credential": {
                "email": "rpu-000000000001@newman.re",
                "password": "[REDACTED]",
                "state": "ready",
            },
        })
        self.assertNotIn(secret, repr(result))

    def test_unavailable_result_contract_contains_no_rpc_payload(self):
        secret = "synthetic-only-password"
        result = credential_result_contract(
            503, {"password": secret, "message": "temporary failure"},
            "rpu-000000000001@newman.re")
        self.assertEqual(result, {"classification": "unavailable", "action": "stop"})
        self.assertNotIn(secret, repr(result))

    def test_explicit_missing_is_business_exception_not_signup(self):
        self.assertEqual(classify_credential_result(
            500, {"code": "P0001", "message": "account not found"},
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
