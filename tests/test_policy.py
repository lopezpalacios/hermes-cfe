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

    def test_old_unverified_ingest_result_shape_cannot_mark_harvested(self):
        self.assertFalse(can_mark_harvested(0, "000000000001", {}, {"ingestion_status":"inserted"}, {}))
        self.assertFalse(can_mark_harvested(1, "000000000001", {}, {"ingestion_status":"inserted"}, {}))
        self.assertFalse(can_mark_harvested(0, "000000000001", {}, {"ingestion_status":"duplicate_sha"}, {}))

    def test_cfdi_identity_requires_valid_uuid_matching_rpu_and_month(self):
        from hermes_cfe.policy import validate_cfdi_identity
        parsed={"cfdi_uuid":"AB12CD34-EF56-7890-ABCD-EF1234567890","rpu":"000000000001","period":"202609"}
        self.assertEqual(validate_cfdi_identity("000000000001",parsed),parsed)

    def test_cfdi_identity_rejects_missing_fields_malformed_uuid_rpu_and_period(self):
        from hermes_cfe.policy import validate_cfdi_identity
        parsed={"cfdi_uuid":"AB12CD34-EF56-7890-ABCD-EF1234567890","rpu":"000000000001","period":"202609"}
        bad=[{"cfdi_uuid":None},{"cfdi_uuid":"not-a-uuid"},{"rpu":None},{"rpu":"123"},{"period":None},{"period":"202699"}]
        for updates in bad:
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                validate_cfdi_identity("000000000001",{**parsed,**updates})

    def test_cfdi_rpu_mismatch_is_never_replaced_by_requested_rpu(self):
        from hermes_cfe.policy import validate_cfdi_identity
        parsed={"cfdi_uuid":"AB12CD34-EF56-7890-ABCD-EF1234567890","rpu":"000000000001","period":"202609"}
        with self.assertRaisesRegex(ValueError,"RPU"):
            validate_cfdi_identity("000000000002",parsed)

    def test_harvest_requires_matching_rpc_and_readback(self):
        parsed={"cfdi_uuid":"AB12CD34-EF56-7890-ABCD-EF1234567890","rpu":"000000000001","period":"202609"}
        ingest={"ingestion_status":"inserted","cfdi_uuid":parsed["cfdi_uuid"],"rpu":parsed["rpu"],"period":parsed["period"]}
        self.assertTrue(can_mark_harvested(0,"000000000001",parsed,ingest,dict(ingest)))
        self.assertFalse(can_mark_harvested(0,"000000000001",parsed,ingest,None))
        self.assertFalse(can_mark_harvested(0,"000000000001",parsed,ingest,{**ingest,"rpu":"000000000002"}))
        self.assertFalse(can_mark_harvested(0,"000000000001",parsed,{**ingest,"cfdi_uuid":"OTHER"},dict(ingest)))

    def test_duplicate_ingest_requires_same_canonical_identity(self):
        parsed={"cfdi_uuid":"AB12CD34-EF56-7890-ABCD-EF1234567890","rpu":"000000000001","period":"202609"}
        duplicate={"ingestion_status":"duplicate_sha","cfdi_uuid":parsed["cfdi_uuid"],"rpu":parsed["rpu"],"period":parsed["period"]}
        self.assertTrue(can_mark_harvested(0,"000000000001",parsed,duplicate,dict(duplicate)))
        self.assertFalse(can_mark_harvested(0,"000000000001",parsed,duplicate,{**duplicate,"cfdi_uuid":"OTHER"}))


if __name__ == "__main__":
    unittest.main()
