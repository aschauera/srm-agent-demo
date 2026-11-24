import copy
import importlib.util
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from dashboard import COLUMNS, RATINGS, SEVERITIES, DashboardError, load_dashboard, within_months
from server import EntraVerifier, ReadOnlyDataverse

ROOT = Path(__file__).resolve().parents[3]
SID = "11111111-1111-1111-1111-111111111111"
RID = "22222222-2222-2222-2222-222222222222"
NOW = datetime(2026, 11, 23, tzinfo=timezone.utc)

smoke_spec = importlib.util.spec_from_file_location("smoke_test", ROOT / "scripts/17-smoke-test-srm-mcp.py")
smoke_test = importlib.util.module_from_spec(smoke_spec)
smoke_spec.loader.exec_module(smoke_test)


class SmokeEndpointTests(unittest.TestCase):
    def test_requires_matching_safe_endpoint(self):
        endpoint = "https://dashboard.example.test/mcp"
        smoke_test.validate_endpoint(endpoint, endpoint)
        for state_url, approved in [
            ("https://other.example.test/mcp", endpoint),
            ("http://dashboard.example.test/mcp", "http://dashboard.example.test/mcp"),
            ("https://user@dashboard.example.test/mcp", "https://user@dashboard.example.test/mcp"),
            (endpoint + "?x=1", endpoint + "?x=1"),
            (endpoint + "#fragment", endpoint + "#fragment"),
            ("https://dashboard.example.test/other", "https://dashboard.example.test/other"),
        ]:
            with self.subTest(state_url=state_url), self.assertRaises(ValueError):
                smoke_test.validate_endpoint(state_url, approved)


class FakeRecords:
    def __init__(self):
        self.calls = []
        self.rows = {
            "mag_supplier": [{"mag_supplierid": SID, "mag_suppliercode": "SUP-012",
                              "mag_legalname": "Fictional Supplier", "mag_hasactivespend": True,
                              "mag_annualspend": 12700000, "mag_currentmagnarating": 100000002}],
            "mag_financialreviewrequest": [{
                "mag_financialreviewrequestid": RID, "mag_requestref": "REQ-2026-012",
                "mag_finalratingconfirmed": False, "mag_finalrating": 100000002,
                "mag_preliminaryrating": 100000000, "mag_currentstage": 3,
                "mag_reviewstatus": 100000001, "mag_reviewpath": 100000002,
                "mag_narrativedraft": "Sensitive legal narrative",
            }],
            "mag_cofacecreditrecord": [{
                "mag_score": 2, "mag_risktier": 100000002, "mag_assessmentdate": "2024-08-19T00:00:00Z"}],
        }

    def list(self, table, **kwargs):
        self.calls.append((table, kwargs))
        return [{k: v for k, v in row.items() if k in kwargs["select"]}
                for row in copy.deepcopy(self.rows.get(table, []))]


class DashboardTests(unittest.TestCase):
    def test_live_state_not_seed_assumptions_or_ai_approval(self):
        result = load_dashboard(FakeRecords(), "SUP-012", "REQ-2026-012", now=NOW)
        self.assertEqual(result["supplier"]["masterRating"], "Red")
        self.assertEqual(result["review"]["preliminaryRating"], "Green")
        self.assertEqual(result["review"]["finalRating"], "Not rated")
        self.assertFalse(result["review"]["confirmed"])
        self.assertFalse(result["coface"]["current"])
        self.assertIn("differ", " ".join(result["warnings"]))

    def test_restricted_access_never_selects_or_returns_sensitive_details(self):
        records = FakeRecords()
        result = load_dashboard(records, "SUP-012", now=NOW)
        self.assertIsNone(result["review"]["narrativeDraft"])
        self.assertEqual(result["adverseEvents"], [])
        for table, query in records.calls:
            self.assertNotIn(table, ["mag_adversenewsevent", "mag_nonfinancialriskitem", "mag_supplieronepagesummary"])
            self.assertNotIn("mag_narrativedraft", query["select"])
            self.assertNotIn("mag_remarks", query["select"])
        result = load_dashboard(records, "SUP-012", sensitive=True, now=NOW)
        self.assertEqual(result["review"]["narrativeDraft"], "Sensitive legal narrative")

    def test_mismatch_missing_zero_spend_and_injection_fail_explicitly(self):
        for code, ref in [("SUP-012' or true", None), ("SUP-012", "REQ-2026-012'"),
                          ("SUP-012", "REQ-2026-999")]:
            with self.subTest(code=code, ref=ref), self.assertRaises(DashboardError):
                load_dashboard(FakeRecords(), code, ref, now=NOW)
        records = FakeRecords()
        records.rows["mag_supplier"][0]["mag_annualspend"] = 0
        with self.assertRaisesRegex(DashboardError, "zero-spend"):
            load_dashboard(records, "SUP-012", now=NOW)

    def test_confirmation_and_expiry_are_separate_from_current_master(self):
        records = FakeRecords()
        records.rows["mag_financialreviewrequest"][0].update(
            mag_finalratingconfirmed=True, mag_ratingexpiry="2026-11-22")
        result = load_dashboard(records, "SUP-012", now=NOW)
        self.assertEqual(result["review"]["finalRating"], "Red")
        self.assertTrue(result["review"]["expired"])
        self.assertIn("expired", " ".join(result["warnings"]))

    def test_coface_calendar_boundary_leap_day_and_future(self):
        self.assertTrue(within_months("2024-02-29", datetime(2025, 8, 29, tzinfo=timezone.utc), 18))
        self.assertFalse(within_months("2024-02-29", datetime(2025, 8, 30, tzinfo=timezone.utc), 18))
        self.assertFalse(within_months("2027-01-01", NOW, 18))
        self.assertFalse(within_months(None, NOW, 18))

    def test_queries_match_authoritative_schema(self):
        for table, selected in COLUMNS.items():
            schema = json.loads((ROOT / "schema" / "tables" / f"{table[4:]}.json").read_text())
            columns = {f"mag_{c['name']}".lower() for c in schema["columns"]}
            columns |= {f"_mag_{lookup['name']}id_value".lower() for lookup in schema.get("lookups", [])}
            columns |= {f"{table}id", "modifiedon", "createdon", "mag_name"}
            self.assertFalse(set(selected) - columns, (table, set(selected) - columns))
        choices = json.loads((ROOT / "schema" / "choices.json").read_text())
        self.assertEqual(RATINGS, dict(zip(choices["rating"]["values"], choices["rating"]["options"])))
        self.assertEqual(SEVERITIES, dict(zip(choices["severity"]["values"], choices["severity"]["options"])))


class AuthorizationTests(unittest.TestCase):
    def test_signature_audience_tenant_expiry_role_and_scope_validation(self):
        verifier = EntraVerifier(SID, RID, "https://example.invalid/mcp")
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        verifier.keys = Mock()
        verifier.keys.get_signing_key_from_jwt.return_value.key = key.public_key()
        timestamp = int(datetime.now(timezone.utc).timestamp())
        good = {"iss": verifier.issuer, "aud": RID, "tid": SID, "oid": SID,
                "iat": timestamp, "nbf": timestamp - 10, "exp": timestamp + 300,
                "roles": ["SRM.Reader"], "scp": "SRM.Read"}
        self.assertIsNotNone(verifier.decode(jwt.encode(good, key, algorithm="RS256")))
        for change in [{"aud": SID}, {"tid": RID}, {"exp": timestamp - 1},
                       {"roles": []}, {"scp": "Other.Read"}]:
            with self.subTest(change=change):
                self.assertIsNone(verifier.decode(jwt.encode({**good, **change}, key, algorithm="RS256")))
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.assertIsNone(verifier.decode(jwt.encode(good, other, algorithm="RS256")))


class ReadOnlyApiTests(unittest.TestCase):
    def test_get_only_allowlist_redirect_and_partial_page_failures(self):
        credential = Mock()
        credential.get_token.return_value.token = "test-only"
        with ReadOnlyDataverse(credential) as reader:
            reader.session = Mock()
            response = reader.session.get.return_value
            response.status_code = 200
            response.json.return_value = {"value": [{"mag_suppliercode": "SUP-012"}]}
            rows = reader.list("mag_supplier", select=["mag_suppliercode"], filter="statecode eq 0")
            self.assertEqual(rows[0]["mag_suppliercode"], "SUP-012")
            self.assertFalse(reader.session.get.call_args.kwargs["allow_redirects"])
            self.assertNotIn("EntityDefinitions", reader.session.get.call_args.args[0])
            with self.assertRaisesRegex(DashboardError, "allowlist"):
                reader.list("systemuser", select=["fullname"], filter="statecode eq 0")
            response.status_code = 302
            with self.assertRaisesRegex(DashboardError, "redirects"):
                reader.list("mag_supplier", select=["mag_suppliercode"], filter="statecode eq 0")
            response.status_code = 200
            response.json.return_value = {"value": [], "@odata.nextLink": "https://example.invalid"}
            with self.assertRaisesRegex(DashboardError, "partial page"):
                reader.list("mag_supplier", select=["mag_suppliercode"], filter="statecode eq 0")


if __name__ == "__main__":
    unittest.main()
