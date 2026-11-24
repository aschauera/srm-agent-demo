"""Offline tests for portable defaults and preservation of the live demo recipient."""

import copy
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "deploy_flows", Path(__file__).with_name("08-deploy-flows.py"))
deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)

VARIABLE = {"schemaName": "mag_SRMDemoMailbox", "displayName": "Demo mailbox",
            "description": "Deployment-specific notification recipient"}


class FakeApi:
    def __init__(self, *, current="current@example.invalid", default="default@example.invalid"):
        self.definition = {
            "environmentvariabledefinitionid": "test-definition", "defaultvalue": default,
            "environmentvariabledefinition_environmentvariablevalue": (
                [{"value": current, "environmentvariablevalueid": "test-current"}] if current is not None else []),
        }
        self.calls = []
        self.fail_create = False

    def __call__(self, method, path, body=None, headers=None):
        self.calls.append((method, path, copy.deepcopy(body), headers))
        if method == "GET":
            return {"value": [copy.deepcopy(self.definition)]}
        if method == "POST" and path == "environmentvariablevalues":
            if self.fail_create:
                raise RuntimeError("Current value creation failed")
            self.definition["environmentvariabledefinition_environmentvariablevalue"] = [
                {"value": body["value"], "environmentvariablevalueid": "test-current"}]
        elif method == "PATCH" and path.startswith("environmentvariabledefinitions("):
            self.definition.update(body)
        elif method == "PATCH" and path.startswith("environmentvariablevalues("):
            self.definition["environmentvariabledefinition_environmentvariablevalue"][0].update(body)
        else:
            raise AssertionError(f"Unexpected operation: {method} {path}")


class EnvironmentVariableTests(unittest.TestCase):
    def clean(self, api, dry_run=False):
        with patch.object(deploy, "solution_component_ids", return_value={"test-definition"}):
            deploy.clear_mailbox_default(api, [VARIABLE], dry_run)

    def test_existing_current_recipient_is_preserved_and_default_is_cleared(self):
        api = FakeApi()
        self.clean(api)
        self.assertIsNone(api.definition["defaultvalue"])
        self.assertEqual(api.definition["environmentvariabledefinition_environmentvariablevalue"][0]["value"],
                         "current@example.invalid")
        self.assertFalse(any(path.startswith("environmentvariablevalues(") for _, path, _, _ in api.calls))
        self.clean(api)
        self.assertIsNone(api.definition["defaultvalue"])

    def test_default_only_recipient_is_saved_outside_solution_before_clearing(self):
        api = FakeApi(current=None)
        self.clean(api)
        writes = [c for c in api.calls if c[0] != "GET"]
        self.assertEqual(writes[0][0:2], ("POST", "environmentvariablevalues"))
        self.assertIsNone(writes[0][3])
        self.assertEqual(writes[0][2]["value"], "default@example.invalid")
        self.assertEqual(writes[1][2]["defaultvalue"], None)

    def test_failed_migration_leaves_default_intact(self):
        api = FakeApi(current=None)
        api.fail_create = True
        with self.assertRaisesRegex(RuntimeError, "creation failed"):
            self.clean(api)
        self.assertEqual(api.definition["defaultvalue"], "default@example.invalid")
        self.assertFalse(any(method == "PATCH" for method, _, _, _ in api.calls))

    def test_dry_run_and_ambiguous_values_never_write(self):
        api = FakeApi()
        self.clean(api, dry_run=True)
        self.assertTrue(all(c[0] == "GET" for c in api.calls))
        api.definition["environmentvariabledefinition_environmentvariablevalue"].append(
            {"value": "other@example.invalid", "environmentvariablevalueid": "other"})
        with self.assertRaisesRegex(RuntimeError, "Ambiguous"):
            self.clean(api)
        self.assertTrue(all(c[0] == "GET" for c in api.calls))

    def test_portable_constants_keep_the_existing_configured_value(self):
        api = FakeApi(current="21", default="18")
        variable = {**VARIABLE, "defaultValue": "18"}
        deploy.ensure_environment_variables(api, [variable], {variable["schemaName"]: "18"}, False)
        self.assertEqual(api.definition["defaultvalue"], "18")
        self.assertEqual(api.definition["environmentvariabledefinition_environmentvariablevalue"][0]["value"], "21")

    def test_profile_guard_checks_exact_target_not_display_name(self):
        for target in [deploy.ENVIRONMENT + "/", deploy.ENVIRONMENT + ".example.invalid/"]:
            profile = f"[1] * UNIVERSAL renamed-profile user Public User Demo PRE {target}\n"
            with self.subTest(target=target), \
                    patch.object(deploy.shutil, "which", return_value=r"C:\tools\cli.cmd"), \
                    patch.object(deploy.Path, "is_file", return_value=True), \
                    patch.object(deploy.subprocess, "run", return_value=deploy.subprocess.CompletedProcess(
                        [], 0, stdout=profile, stderr="")), \
                    patch.dict(deploy.os.environ, {"DATAVERSE_URL": deploy.ENVIRONMENT}):
                if target == deploy.ENVIRONMENT + "/":
                    self.assertTrue(callable(deploy._load_web_api()[0]))
                else:
                    with self.assertRaisesRegex(RuntimeError, "approved PAC DemoPRE profile"):
                        deploy._load_web_api()


if __name__ == "__main__":
    unittest.main()
