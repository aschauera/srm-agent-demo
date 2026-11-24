"""Offline tests for preserving connector behavior while replacing deployment identifiers."""

import importlib.util
import copy
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "connector", Path(__file__).with_name("18-parameterize-srm-connector.py"))
connector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(connector)


def fixture():
    scope = "api://fictional-api/SRM.Read"
    authorize, token = "https://example.invalid/authorize", "https://example.invalid/token"
    return {
        "host": "mcp.example.invalid", "paths": {"/mcp": {"post": {"operationId": "InvokeServer"}}},
        "securityDefinitions": {
            "oauth2-auth": {"type": "oauth2", "authorizationUrl": authorize, "tokenUrl": token,
                           "scopes": {scope: scope}},
            "oAuthClientCredentials": {"type": "oauth2", "tokenUrl": token, "scopes": {scope: scope}},
        },
        "security": [{"oauth2-auth": [scope]}, {"oAuthClientCredentials": [scope]}],
    }, {
        "token": {"type": "oAuthSetting", "oAuthSettings": {
            "clientId": "fictional-client", "identityProvider": "oauth2pkce", "scopes": [scope],
            "customParameters": {"AuthorizationUrl": {"value": authorize},
                                 "TokenUrl": {"value": token}, "RefreshUrl": {"value": token}},
        }},
    }


class ConnectorTests(unittest.TestCase):
    def test_all_settings_resolve_identically_and_originals_are_not_mutated(self):
        api, parameters = fixture()
        updated_api, updated_parameters, values = connector.parameterize(api, parameters, {})
        self.assertEqual(len(values), 6)
        self.assertEqual(connector.resolve(updated_api, values), api)
        self.assertEqual(connector.resolve(updated_parameters, values), parameters)
        self.assertEqual(updated_api["paths"], api["paths"])
        self.assertEqual(api["host"], "mcp.example.invalid")
        self.assertNotIn("fictional-api", str(updated_api))
        self.assertNotIn("fictional-client", str(updated_parameters))

    def test_repeated_parameterization_reuses_current_values(self):
        api, parameters, values = connector.parameterize(*fixture(), {})
        self.assertEqual(connector.parameterize(api, parameters, values), (api, parameters, values))
        with self.assertRaisesRegex(ValueError, "Unresolved"):
            connector.parameterize(api, parameters, {})

    def test_existing_oauth_mode_is_preserved(self):
        for provider in ["oauth2", "oauth2pkce"]:
            api, parameters = fixture()
            parameters["token"]["oAuthSettings"]["identityProvider"] = provider
            with self.subTest(provider=provider):
                _, updated, _ = connector.parameterize(api, parameters, {})
                self.assertEqual(updated["token"]["oAuthSettings"]["identityProvider"], provider)
        api, parameters = fixture()
        del api["securityDefinitions"]["oAuthClientCredentials"]
        api["security"] = [{"oauth2-auth": parameters["token"]["oAuthSettings"]["scopes"][:]}]
        updated, _, values = connector.parameterize(api, parameters, {})
        self.assertEqual(set(updated["securityDefinitions"]), {"oauth2-auth"})
        self.assertEqual(connector.resolve(updated, values), api)

    def test_inconsistent_scope_or_urls_are_rejected(self):
        api, parameters = fixture()
        api["securityDefinitions"]["oauth2-auth"]["tokenUrl"] = "https://other.example.invalid"
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            connector.parameterize(api, parameters, {})

    def test_changed_structure_or_connection_secret_is_rejected(self):
        for change in ["scope", "secret"]:
            api, parameters = fixture()
            settings = parameters["token"]["oAuthSettings"]
            if change == "scope":
                settings["scopes"].append("Other.Read")
            else:
                settings["clientSecret"] = "fictional-test-only"
            with self.subTest(change=change), self.assertRaises(ValueError):
                connector.parameterize(api, parameters, {})

    def test_only_known_platform_oauth_normalization_is_accepted(self):
        _, parameters = fixture()
        actual = copy.deepcopy(parameters)
        actual["token"]["type"] = "oauthSetting"
        oauth = actual["token"]["oAuthSettings"]
        oauth["properties"] = {"IsFirstParty": "False", "IsOnbehalfofLoginSupported": False}
        oauth["redirectUrl"] = "https://global.consent.azure-apim.net/redirect/fictional-connector"
        self.assertTrue(connector.parameters_match(actual, parameters))
        oauth["clientId"] = "different-client"
        self.assertFalse(connector.parameters_match(actual, parameters))
        oauth["clientId"] = parameters["token"]["oAuthSettings"]["clientId"]
        oauth["redirectUrl"] = "https://other.example.invalid/redirect/connector"
        self.assertFalse(connector.parameters_match(actual, parameters))
        oauth["redirectUrl"] = "https://global.consent.azure-apim.net/redirect/fictional-connector"
        oauth["properties"]["IsOnbehalfofLoginSupported"] = True
        self.assertFalse(connector.parameters_match(actual, parameters))


if __name__ == "__main__":
    unittest.main()
