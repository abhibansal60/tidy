import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

from tidy import setup_check
from tidy.__main__ import main

CLIENT = {"installed": {"client_id": "x.apps.googleusercontent.com", "client_secret": "s",
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token"}}


def mode(path):
    return stat.S_IMODE(Path(path).stat().st_mode)


class DataDirTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.temp.name)

    def tearDown(self):
        os.chdir(self.cwd)
        self.temp.cleanup()

    def test_precedence_flag_env_local_home(self):
        with mock.patch.dict(os.environ, {"TIDY_DATA_DIR": "/tmp/from-env"}):
            self.assertEqual(setup_check.data_dir("/tmp/flag"), Path("/tmp/flag"))
            self.assertEqual(setup_check.data_dir(), Path("/tmp/from-env"))
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TIDY_DATA_DIR", None)
            self.assertEqual(setup_check.data_dir(), Path.home() / ".tidy")
            Path(".tidy").mkdir()
            self.assertEqual(setup_check.data_dir(), Path(".tidy"))


class InitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data = Path(self.temp.name) / "home"
        self.client = Path(self.temp.name) / "client.json"
        self.client.write_text(json.dumps(CLIENT))
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop("TYPESAFE_API_KEY", None)

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_creates_private_files_and_never_echoes_the_key(self):
        with mock.patch("sys.stdin", io.StringIO("sk-secret-123\n")):
            result = setup_check.init(self.data, "me@example.com", self.client, key_stdin=True)

        self.assertEqual(mode(self.data), 0o700)
        for name in ("config.json", "client_secret.json", ".env"):
            self.assertEqual(mode(self.data / name), 0o600, name)
        self.assertEqual(json.loads((self.data / "config.json").read_text()),
                         {"expected_email": "me@example.com", "mail_email": "me@example.com"})
        self.assertNotIn("sk-secret-123", json.dumps(result))
        self.assertEqual(setup_check.typesafe_key(self.data)[0], "sk-secret-123")

    def test_refuses_to_rebind_a_folder_to_another_account(self):
        setup_check.init(self.data, "me@example.com")
        with self.assertRaises(ValueError):
            setup_check.init(self.data, "other@example.com")

    def test_rejects_a_file_that_is_not_an_oauth_client(self):
        bad = Path(self.temp.name) / "bad.json"
        bad.write_text("[]")
        with self.assertRaises(ValueError):
            setup_check.init(self.data, "me@example.com", bad)
        self.assertFalse((self.data / "client_secret.json").exists())


class DoctorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_empty_folder_is_not_ready_and_says_what_to_run(self):
        with mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": ""}):
            report = setup_check.doctor(self.data / "nothing")
        self.assertFalse(report["ready"])
        self.assertIn("tidy init", report["next"][0])

    def test_flags_world_readable_secrets(self):
        setup_check.init(self.data, "me@example.com")
        (self.data / "token.json").write_text("{}")
        (self.data / "token.json").chmod(0o644)

        report = setup_check.doctor(self.data)

        self.assertIn(str(self.data / "token.json"), report["checks"]["loose_permissions"])

    def test_cli_doctor_prints_json_without_touching_the_database(self):
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            self.assertEqual(main(["--data-dir", str(self.data), "doctor"]), 0)
        self.assertIn("checks", json.loads(out.getvalue()))
        self.assertFalse((self.data / "inventory.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
