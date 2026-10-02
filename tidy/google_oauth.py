"""Google's OAuth for one API (Gmail or YouTube): a read token and a separate write token, each scope-checked."""

import json
from pathlib import Path

from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .store import private_json

IDENTITY = ["openid", "https://www.googleapis.com/auth/userinfo.email"]
GOOGLE_AUTH_URIS = ("https://accounts.google.com/o/oauth2/auth", "https://accounts.google.com/o/oauth2/v2/auth")
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"


class GoogleOAuth:
    """`read_scope` / `write_scope` plus email/OpenID; `error` is the calling API module's APIError."""

    def __init__(self, read_scope, write_scope, read_kind, write_kind, error):
        self.read_scope, self.write_scope = read_scope, write_scope
        self.read_scopes, self.write_scopes = [read_scope, *IDENTITY], [write_scope, *IDENTITY]
        self.read_kind, self.write_kind, self.error = read_kind, write_kind, error

    def check_scopes(self, scopes, write=False):
        scopes = set(scopes or [])
        need, allowed = (self.write_scope, self.write_scopes) if write else (self.read_scope, self.read_scopes)
        if need not in scopes or scopes - set(allowed) - {"email"}:
            kind = self.write_kind if write else self.read_kind
            raise self.error(f"Credential scopes must be {kind} plus email/OpenID. Reauthorize.")

    def authorize(self, client_file, expected_email, open_browser=True, write=False):
        config = json.loads(Path(client_file).read_text())
        if not isinstance(config, dict) or not isinstance(config.get("installed"), dict):
            raise ValueError("Expected a Google Desktop OAuth client JSON object.")
        installed = config["installed"]
        if installed.get("auth_uri") not in GOOGLE_AUTH_URIS or installed.get("token_uri") != GOOGLE_TOKEN_URI:
            raise ValueError("Expected a Google Desktop OAuth client JSON with official Google endpoints.")
        scopes = self.write_scopes if write else self.read_scopes
        flow = InstalledAppFlow.from_client_config(config, scopes, autogenerate_code_verifier=True)
        credentials = flow.run_local_server(
            host="127.0.0.1", port=0, open_browser=open_browser, timeout_seconds=180,
            prompt="consent", login_hint=expected_email, include_granted_scopes="false",
            success_message="Authorization received. Return to the terminal for account verification.",
        )
        self.check_scopes(credentials.granted_scopes or credentials.scopes, write)
        if not credentials.refresh_token:
            raise self.error("No refresh token received. Revoke the old grant and authorize again.")
        return credentials

    def load_credentials(self, path, write=False):
        data = json.loads(Path(path).read_text())
        if not isinstance(data, dict):
            raise ValueError("Invalid OAuth credential file; reauthorize.")
        self.check_scopes(data.get("scopes"), write)
        credentials = Credentials.from_authorized_user_info(data)
        if not credentials.valid:
            credentials.refresh(Request())
            self.save_credentials(path, credentials, write)
        return credentials

    def save_credentials(self, path, credentials, write=False):
        self.check_scopes(credentials.granted_scopes or credentials.scopes, write)
        data = json.loads(credentials.to_json())
        data["scopes"] = list(credentials.granted_scopes or credentials.scopes)
        private_json(path, data)


def session_for(credentials):
    # Make retries visible to the API's call/quota counter rather than hide 401 retries.
    return AuthorizedSession(credentials, max_refresh_attempts=0, refresh_timeout=30)
