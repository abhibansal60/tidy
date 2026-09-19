import json
from pathlib import Path
import tempfile
import unittest

from tidy import profile


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "profile.json"

    def test_missing_file_gives_defaults(self):
        p = profile.load(self.path)
        self.assertEqual(p["caps"], {"unsubscribe": 5, "subscribe": 3})
        self.assertEqual(p["trial_days"], 30)
        self.assertEqual(p["gate"], {"min_labels": 30, "min_agreement": 0.85})

    def test_partial_override_keeps_other_defaults(self):
        self.path.write_text(json.dumps({"interests": "woodworking", "caps": {"unsubscribe": 1}}))
        p = profile.load(self.path)
        self.assertEqual(p["interests"], "woodworking")
        self.assertEqual(p["caps"], {"unsubscribe": 1, "subscribe": 3})

    def test_bad_types_and_unknown_keys_rejected(self):
        for bad in ({"trial_days": "30"}, {"caps": {"unsubscribe": -1}}, {"interests": ""},
                    {"gate": {"min_agreement": 2}}, {"thresholds": {"typo": 1}}, {"nope": 1}, [1]):
            self.path.write_text(json.dumps(bad))
            with self.assertRaises(ValueError, msg=bad):
                profile.load(self.path)
