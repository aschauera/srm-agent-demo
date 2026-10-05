"""Offline regression checks for the additive analysis review surface."""

import copy
import importlib.util
import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "surface", Path(__file__).with_name("14-configure-analysis-surface.py"))
surface = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(surface)


class AnalysisSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(surface.SOURCE.read_text(encoding="utf-8"))

    def test_existing_controls_and_events_are_preserved(self):
        original = (
            '<form><tabs><tab name="tab_request" id="existing"><columns>'
            '<column><sections><section name="existing"><rows><row><cell>'
            '<control id="rating" datafieldname="mag_finalrating" disabled="false" />'
            '</cell></row></rows></section></sections></column></columns></tab></tabs>'
            '<events><event name="onload"><Handlers /></event></events></form>'
        )
        updated = ET.fromstring(surface.mutate_form(original, self.config))
        before = ET.fromstring(original)
        self.assertEqual(ET.tostring(before.find("tabs/tab")),
                         ET.tostring(updated.find("tabs/tab")))
        self.assertEqual(ET.tostring(before.find("events")),
                         ET.tostring(updated.find("events")))
        self.assertEqual(len(updated.findall("tabs/tab")), 2)

    def test_reapplication_is_idempotent(self):
        first = surface.mutate_form("<form><tabs /></form>", self.config)
        self.assertEqual(first, surface.mutate_form(first, self.config))

    def test_narrative_is_locked_and_grids_are_request_scoped(self):
        tab = surface.analysis_tab(self.config)
        fields = [c for c in tab.iter("control") if c.get("datafieldname")]
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0].get("datafieldname"), "mag_narrativedraft")
        self.assertEqual(fields[0].get("disabled"), "true")
        grids = [c for c in tab.iter("control") if c.get("classid") == surface.GRID_CLASS]
        self.assertEqual(len(grids), 3)
        for grid in grids:
            table = grid.findtext("parameters/TargetEntityType")
            self.assertEqual(grid.findtext("parameters/RelationshipName"),
                             f"{surface.TABLE}_{table}_mag_ReviewRequestId")
            self.assertEqual(grid.findtext("parameters/ViewId"), surface.identifier(f"view_{table}"))
        for cell in tab.iter("cell"):
            self.assertNotIn("name", cell.attrib)

    def test_unknown_columns_are_rejected(self):
        config = copy.deepcopy(self.config)
        config["views"][0]["columns"].append("mag_nonexistent")
        with self.assertRaisesRegex(RuntimeError, "Unknown surface columns"):
            surface.validate(config)

    def test_fetch_normalization_retains_semantics(self):
        first = '<fetch savedqueryid="server-id"><entity name="example" /></fetch>'
        second = '<fetch><entity name="example" /></fetch>'
        self.assertEqual(surface.normalized_xml(first), surface.normalized_xml(second))
        self.assertNotEqual(surface.normalized_xml(first),
                            surface.normalized_xml('<fetch><entity name="different" /></fetch>'))


if __name__ == "__main__":
    unittest.main()
