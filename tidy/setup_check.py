"""Where Tidy keeps its files, `tidy init` (first-run setup) and `tidy doctor` (what is missing, never any secret)."""

import getpass
import json
import os
from pathlib import Path
import shutil
import stat
import sys

from . import __version__
from .store import private_json, private_text

KEY_NAME = "TYPESAFE_API_KEY"


def data_dir(given=None):
    """--data-dir, else $TIDY_DATA_DIR, else ./.tidy when it exists (a cloned checkout), else ~/.tidy."""
    if given:
        return Path(given).expanduser()
    if os.environ.get("TIDY_DATA_DIR"):
        return Path(os.environ["TIDY_DATA_DIR"]).expanduser()
    local = Path(".tidy")
    return local if local.is_dir() else Path.home() / ".tidy"


def client_secrets(data, given=None):
    """--client-secrets, else <data dir>/client_secret.json, else ./secrets/client_secret.json."""
    if given:
        return Path(given).expanduser()
    inside = data / "client_secret.json"
    return inside if inside.is_file() else Path("secrets/client_secret.json")


def env_files(data):
    return [data / ".env", Path.cwd() / ".env", Path.cwd().parent / ".env"]


def typesafe_key(data):
    """The key from the environment, else the first .env that sets it. Returned, never printed."""
    if os.environ.get(KEY_NAME):
        return os.environ[KEY_NAME], "environment"
    for env in env_files(data):
        if env.is_file():
            for line in env.read_text().splitlines():
                name, _, value = line.partition("=")
                if name.strip() == KEY_NAME and value.strip().strip("\"'"):
                    return value.strip().strip("\"'"), str(env)
    return None, None


def init(data, email, client_file=None, key_stdin=False, mail=True):
    """Create the private data dir, config.json, and optionally copy the OAuth client and store the TypeSafe key.
    Never overwrites an existing config with a different email; never echoes the key."""
    if "@" not in (email or ""):
        raise ValueError("--email must be the Google account you will sign in with.")
    data.mkdir(parents=True, exist_ok=True, mode=0o700)
    data.chmod(0o700)
    config_file = data / "config.json"
    config = json.loads(config_file.read_text()) if config_file.is_file() else {}
    if config.get("expected_email") not in (None, email):
        raise ValueError(f"{config_file} already set up for another account; use a separate --data-dir.")
    config["expected_email"] = email
    if mail:
        config.setdefault("mail_email", email)
    private_json(config_file, config)
    done = {"data_dir": str(data), "config": str(config_file)}
    if client_file:
        client_file = Path(client_file).expanduser()
        parsed = json.loads(client_file.read_text())
        if not isinstance(parsed, dict) or "installed" not in parsed:
            raise ValueError("That is not a Google Desktop OAuth client JSON (expected an \"installed\" object).")
        target = data / "client_secret.json"
        private_text(target, client_file.read_text())
        done["client_secrets"] = str(target)
    if key_stdin:
        # A terminal gets a hidden prompt; a pipe (agents, scripts) is read as is. The key is never echoed back.
        key = (getpass.getpass("TypeSafe API key (hidden): ") if sys.stdin.isatty() else sys.stdin.readline()).strip()
        if not key:
            raise ValueError("No key on stdin.")
        env = data / ".env"
        lines = [l for l in (env.read_text().splitlines() if env.is_file() else []) if not l.startswith(KEY_NAME + "=")]
        private_text(env, "\n".join(lines + [f"{KEY_NAME}={key}"]) + "\n")
        done["typesafe_key"] = str(env)
    return {**done, **doctor(data)}


def _loose(path):
    """True when group or others can read a private file or enter a private dir."""
    return path.exists() and bool(path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO))


def doctor(data, client_file=None):
    """What is set up and what is missing, as plain facts plus the next command to run. Safe to paste anywhere:
    reports whether secrets exist and whether their permissions are private, never their contents."""
    config_file = data / "config.json"
    config = {}
    if config_file.is_file():
        try:
            config = json.loads(config_file.read_text())
        except ValueError:
            config = {"_invalid": True}
    secrets = client_secrets(data, client_file)
    key, key_source = typesafe_key(data)
    tokens = {name: (data / f"{name}.json").is_file()
              for name in ("token", "token_write", "token_mail", "token_mail_write")}
    private = [p for p in (data, config_file, secrets, data / ".env", data / "inventory.sqlite3",
                           *(data / f"{n}.json" for n in tokens)) if p.exists()]
    loose = [str(p) for p in private if _loose(p)]
    checks = {
        "python": sys.version.split()[0],
        "tidy": __version__,
        "data_dir": str(data),
        "config": "ok" if config.get("expected_email") else ("invalid" if config.get("_invalid") else "missing"),
        "google_client_secrets": str(secrets) if secrets.is_file() else "missing",
        "typesafe_key": key_source if key else "missing",
        "tokens": tokens,
        "claude_cli_for_second_opinion": bool(shutil.which("claude")),
        "loose_permissions": loose,
    }
    guide = "https://github.com/abhibansal60/tidy/blob/main/docs/agent-setup.md"
    steps = []
    if checks["config"] != "ok":
        steps.append(f"Create a Google Desktop OAuth client ({guide}) and a TypeSafe key (https://console.typesafe.ai), "
                     "then: tidy init --email you@gmail.com --client-secrets PATH --key-stdin")
    else:
        if checks["google_client_secrets"] == "missing":
            steps.append(f"Create a Google Desktop OAuth client ({guide}), then: tidy init --email "
                         f"{config['expected_email']} --client-secrets PATH")
        if not key:
            steps.append(f"Get a key at https://console.typesafe.ai, then: tidy init --email {config['expected_email']} --key-stdin")
    if loose:
        steps.append("chmod 700 " + str(data) + " && chmod 600 " + " ".join(p for p in loose if p != str(data)))
    ready = not steps
    if ready and not (tokens["token"] or tokens["token_mail"]):
        steps.append("tidy mail-auth   (Gmail)   or   tidy auth   (YouTube)")
    return {"ready": ready, "checks": checks, "next": steps}
