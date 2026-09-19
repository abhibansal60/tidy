from pathlib import Path
import tempfile
import unittest

from tidy.store import adopt_old_dir


class AdoptOldDirTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_old_directory_moves_once_and_keeps_contents(self):
        old, new = self.root / ".jev", self.root / ".tidy"
        old.mkdir()
        (old / "inventory.sqlite3").write_text("db")

        adopt_old_dir(new, old)
        adopt_old_dir(new, old)

        self.assertEqual((new / "inventory.sqlite3").read_text(), "db")
        self.assertFalse(old.exists())

    def test_existing_new_directory_is_never_overwritten(self):
        old, new = self.root / ".jev", self.root / ".tidy"
        old.mkdir()
        (old / "a").write_text("old")
        new.mkdir()
        (new / "a").write_text("new")

        adopt_old_dir(new, old)

        self.assertEqual((new / "a").read_text(), "new")
        self.assertEqual((old / "a").read_text(), "old")


if __name__ == "__main__":
    unittest.main()
