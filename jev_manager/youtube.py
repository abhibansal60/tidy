"""Google's OAuth implementation plus GET-only YouTube inventory collection."""

import json
from pathlib import Path
import time

from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import requests

from .store import private_json, required_text


READ_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
SCOPES = [READ_SCOPE, "openid", "https://www.googleapis.com/auth/userinfo.email"]
API = "https://www.googleapis.com/youtube/v3/"
USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"


class APIError(RuntimeError):
    pass


def check_scopes(scopes):
    scopes = set(scopes or [])
    if READ_SCOPE not in scopes or scopes - set(SCOPES) - {"email"}:
        raise APIError("Credential scopes must be read-only YouTube plus email/OpenID. Reauthorize.")


def authorize(client_file, expected_email, open_browser=True):
    config = json.loads(Path(client_file).read_text())
    if not isinstance(config, dict) or not isinstance(config.get("installed"), dict):
        raise ValueError("Expected a Google Desktop OAuth client JSON object.")
    installed = config.get("installed", {})
    if (installed.get("auth_uri") not in (
        "https://accounts.google.com/o/oauth2/auth", "https://accounts.google.com/o/oauth2/v2/auth"
    ) or installed.get("token_uri") != "https://oauth2.googleapis.com/token"):
        raise ValueError("Expected a Google Desktop OAuth client JSON with official Google endpoints.")
    flow = InstalledAppFlow.from_client_config(config, SCOPES, autogenerate_code_verifier=True)
    credentials = flow.run_local_server(
        host="127.0.0.1", port=0, open_browser=open_browser, timeout_seconds=180,
        prompt="consent", login_hint=expected_email, include_granted_scopes="false",
        success_message="Authorization received. Return to the terminal for account verification.",
    )
    check_scopes(credentials.granted_scopes or credentials.scopes)
    if not credentials.refresh_token:
        raise APIError("No refresh token received. Revoke the old grant and authorize again.")
    return credentials


def load_credentials(path):
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError("Invalid OAuth credential file; reauthorize.")
    check_scopes(data.get("scopes"))
    credentials = Credentials.from_authorized_user_info(data)
    if not credentials.valid:
        credentials.refresh(Request())
        save_credentials(path, credentials)
    return credentials


def save_credentials(path, credentials):
    check_scopes(credentials.granted_scopes or credentials.scopes)
    data = json.loads(credentials.to_json())
    data["scopes"] = list(credentials.granted_scopes or credentials.scopes)
    private_json(path, data)


class YouTube:
    def __init__(self, session, max_units=100):
        if max_units < 1:
            raise ValueError("Quota budget must be positive.")
        self.session = session
        self.max_units = max_units
        self.units = 0

    def get(self, resource, **params):
        # No user-controlled URL, HTTP method, or mutation endpoint.
        if resource not in ("channels", "subscriptions", "userinfo"):
            raise ValueError("Only read-only inventory endpoints are supported.")
        is_youtube = resource != "userinfo"
        for attempt in range(3):
            if is_youtube:
                if self.units >= self.max_units:
                    raise APIError("Local quota budget reached; inventory not replaced.")
                self.units += 1
            try:
                response = self.session.get(API + resource if is_youtube else USERINFO,
                                            params=params, timeout=30, allow_redirects=False)
            except requests.RequestException:
                if attempt == 2:
                    raise APIError("Network request failed; inventory not replaced.") from None
                time.sleep(2 ** attempt)
                continue
            if response.status_code == 200:
                try:
                    value = response.json()
                except ValueError:
                    raise APIError("API returned invalid JSON.") from None
                if not isinstance(value, dict):
                    raise APIError("API returned an invalid response shape.")
                return value
            if (response.status_code == 429 or response.status_code >= 500) and attempt < 2:
                delay = response.headers.get("Retry-After", "")
                delay = float(delay) if delay.isdigit() else 2 ** attempt
                if delay > 30:
                    raise APIError("API requested a longer backoff; rerun later.")
                time.sleep(delay)
                continue
            raise APIError(f"API returned HTTP {response.status_code}; check auth/quota in Google Console.")

    def identity(self, expected_email):
        user = self.get("userinfo")
        email = required_text(user.get("email"), "Google email").casefold()
        if user.get("email_verified") is not True or email != expected_email.casefold():
            raise APIError("Signed-in Google account does not match configured verified email.")
        channels = self.get("channels", part="id,snippet", mine="true", maxResults=50)
        items = channels.get("items")
        if not isinstance(items, list) or len(items) != 1 or channels.get("nextPageToken"):
            raise APIError("Expected exactly one authorized YouTube channel; check selected account.")
        channel = items[0]
        if not isinstance(channel, dict):
            raise APIError("Malformed YouTube identity response.")
        return {"google_sub": required_text(user.get("sub"), "Google subject"), "email": email,
                "youtube_channel_id": required_text(channel.get("id"), "YouTube identity")}

    def subscriptions(self):
        rows, seen_ids, seen_channels, tokens = [], set(), set(), set()
        token = None
        while True:
            params = {"part": "id,snippet", "mine": "true", "maxResults": 50}
            if token:
                params["pageToken"] = token
            page = self.get("subscriptions", **params)
            items = page.get("items")
            if not isinstance(items, list):
                raise APIError("Subscription page is missing items; inventory not replaced.")
            for item in items:
                try:
                    snippet = item["snippet"]
                    row = {"id": required_text(item["id"], "subscription ID"),
                           "channel_id": required_text(snippet["resourceId"]["channelId"], "channel ID"),
                           "title": required_text(snippet["title"], "channel title"),
                           "subscribed_at": snippet.get("publishedAt")}
                    if row["subscribed_at"] is not None and not isinstance(row["subscribed_at"], str):
                        raise ValueError("Invalid publication date.")
                except (KeyError, TypeError, ValueError):
                    raise APIError("Malformed subscription item; inventory not replaced.") from None
                if row["id"] in seen_ids or row["channel_id"] in seen_channels:
                    raise APIError("Duplicate subscription across pages; rerun stable inventory.")
                seen_ids.add(row["id"])
                seen_channels.add(row["channel_id"])
                rows.append(row)
            token = page.get("nextPageToken")
            if token is None or token == "":
                return rows
            if not isinstance(token, str) or token in tokens:
                raise APIError("Repeated/invalid pagination token; inventory not replaced.")
            tokens.add(token)


def session_for(credentials):
    # Make retries visible to our quota counter rather than hide 401 retries.
    return AuthorizedSession(credentials, max_refresh_attempts=0, refresh_timeout=30)
