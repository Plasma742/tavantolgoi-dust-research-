"""Static consistency tests, NOT validation of Earth Engine computations."""
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class StarterContractTests(unittest.TestCase):
    def test_required_docs(self):
        for name in ("README.md", "CLAUDE.md", "docs/RESEARCH_PROTOCOL.md",
                     "docs/DATA_CATALOG.md", "docs/SYSTEM_ARCHITECTURE.md",
                     "docs/CLAUDE_BUILD_BRIEF.md", "gee/maiac_smoke_test.js"):
            self.assertTrue((ROOT / name).is_file(), name)

    def test_provenance_must_be_demo_only(self):
        obj = json.loads((ROOT / 'docs/PROVENANCE_EXAMPLE.json').read_text())
        self.assertEqual(obj['status'], 'example_only_not_real_observations')
        self.assertIsNone(obj['valid_observation_count'])
        self.assertIsNone(obj['valid_day_count'])
        self.assertEqual(obj['scale_factor'], 0.001)
        self.assertIn('AOD', obj['caveat'])

    def test_gee_script_documents_primary_dataset_and_qa(self):
        source = (ROOT/'gee/maiac_smoke_test.js').read_text()
        for token in ("MODIS/061/MCD19A2_GRANULES", "Optical_Depth_055", "AOD_QA",
                      "multiply(0.001)", "filterDate(start, end)", "filtered.count()"):
            self.assertIn(token, source)

    def test_ignored_secrets(self):
        ignore = (ROOT/'.gitignore').read_text()
        for token in ('.env', '*service-account*.json', '*.pem'):
            self.assertIn(token, ignore)


if __name__ == '__main__':
    unittest.main()
