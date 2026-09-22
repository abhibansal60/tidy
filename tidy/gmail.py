"""Google's OAuth implementation plus Gmail read access and label-only mutation (archive, spam). No sends or deletes."""

import base64
from html import unescape
import json
from pathlib import Path
import re
import time

from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import requests

from .store import private_json, required_text


READ_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
SCOPES = [READ_SCOPE, "openid", "https://www.googleapis.com/auth/userinfo.email"]
# Write access (label changes only: archive, spam) lives in a separate token, same split as tidy/youtube.py.
WRITE_SCOPE = "https://www.googleapis.com/auth/gmail.modify"
WRITE_SCOPES = [WRITE_SCOPE, "openid", "https://www.googleapis.com/auth/userinfo.email"]
API = "https://gmail.googleapis.com/gmail/v1/users/me/"
USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"


class APIError(RuntimeError):
    pass


RETRY_ATTEMPTS = 6  # Gmail's quota is per-minute, not per-second; a short retry budget gives up too early.
_RATE_LIMIT_REASONS = {"rateLimitExceeded", "quotaExceeded", "userRateLimitExceeded"}


def _retryable(response):
    if response.status_code == 429 or response.status_code >= 500:
        return True
    if response.status_code != 403:
        return False
    try:
        errors = response.json().get("error", {}).get("errors", [])
    except ValueError:
        return False
    return any(e.get("reason") in _RATE_LIMIT_REASONS for e in errors)


def _retry_delay(response):
    delay = response.headers.get("Retry-After", "")
    if delay.isdigit():
        return float(delay)
    return 65 if response.status_code == 403 else 2  # per-minute quota resets; short backoff won't help a 403


def check_scopes(scopes, write=False):
    scopes = set(scopes or [])
    need, allowed = (WRITE_SCOPE, WRITE_SCOPES) if write else (READ_SCOPE, SCOPES)
    if need not in scopes or scopes - set(allowed) - {"email"}:
        kind = "Gmail modify (labels only)" if write else "read-only Gmail"
        raise APIError(f"Credential scopes must be {kind} plus email/OpenID. Reauthorize.")


def authorize(client_file, expected_email, open_browser=True, write=False):
    config = json.loads(Path(client_file).read_text())
    if not isinstance(config, dict) or not isinstance(config.get("installed"), dict):
        raise ValueError("Expected a Google Desktop OAuth client JSON object.")
    installed = config.get("installed", {})
    if (installed.get("auth_uri") not in (
        "https://accounts.google.com/o/oauth2/auth", "https://accounts.google.com/o/oauth2/v2/auth"
    ) or installed.get("token_uri") != "https://oauth2.googleapis.com/token"):
        raise ValueError("Expected a Google Desktop OAuth client JSON with official Google endpoints.")
    scopes = WRITE_SCOPES if write else SCOPES
    flow = InstalledAppFlow.from_client_config(config, scopes, autogenerate_code_verifier=True)
    credentials = flow.run_local_server(
        host="127.0.0.1", port=0, open_browser=open_browser, timeout_seconds=180,
        prompt="consent", login_hint=expected_email, include_granted_scopes="false",
        success_message="Authorization received. Return to the terminal for account verification.",
    )
    check_scopes(credentials.granted_scopes or credentials.scopes, write)
    if not credentials.refresh_token:
        raise APIError("No refresh token received. Revoke the old grant and authorize again.")
    return credentials


def load_credentials(path, write=False):
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError("Invalid OAuth credential file; reauthorize.")
    check_scopes(data.get("scopes"), write)
    credentials = Credentials.from_authorized_user_info(data)
    if not credentials.valid:
        credentials.refresh(Request())
        save_credentials(path, credentials, write)
    return credentials


def save_credentials(path, credentials, write=False):
    check_scopes(credentials.granted_scopes or credentials.scopes, write)
    data = json.loads(credentials.to_json())
    data["scopes"] = list(credentials.granted_scopes or credentials.scopes)
    private_json(path, data)


class Gmail:
    def __init__(self, session, max_calls=1200):
        if max_calls < 1:
            raise ValueError("Call budget must be positive.")
        self.session = session
        self.max_calls = max_calls
        self.calls = 0

    def get(self, resource, **params):
        # No user-controlled URL, HTTP method, or mutation endpoint.
        if resource not in ("profile", "messages", "userinfo") and not resource.startswith("messages/"):
            raise ValueError("Only read-only endpoints are supported.")
        is_gmail = resource != "userinfo"
        for attempt in range(RETRY_ATTEMPTS):
            if is_gmail:
                if self.calls >= self.max_calls:
                    raise APIError("Local call budget reached.")
                self.calls += 1
            try:
                response = self.session.get(API + resource if is_gmail else USERINFO,
                                            params=params, timeout=30, allow_redirects=False)
            except requests.RequestException:
                if attempt == RETRY_ATTEMPTS - 1:
                    raise APIError("Network request failed.") from None
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
            if attempt < RETRY_ATTEMPTS - 1 and _retryable(response):
                time.sleep(_retry_delay(response))
                continue
            raise APIError(f"API returned HTTP {response.status_code}; check auth in Google Console.")

    def identity(self, expected_email):
        user = self.get("userinfo")
        email = required_text(user.get("email"), "Google email").casefold()
        if user.get("email_verified") is not True or email != expected_email.casefold():
            raise APIError("Signed-in Google account does not match configured verified email.")
        return {"google_sub": required_text(user.get("sub"), "Google subject"), "email": email}

    def message_ids(self, query, limit):
        """IDs matching a Gmail search query, oldest paging stops once `limit` collected."""
        ids, tokens, token = [], set(), None
        while len(ids) < limit:
            params = {"q": query, "maxResults": min(100, limit - len(ids))}
            if token:
                params["pageToken"] = token
            page = self.get("messages", **params)
            items = page.get("messages", [])
            if not isinstance(items, list):
                raise APIError("Message list page is missing items.")
            ids += [required_text(item.get("id"), "message ID") for item in items]
            token = page.get("nextPageToken")
            if not token:
                break
            if not isinstance(token, str) or token in tokens:
                raise APIError("Repeated/invalid pagination token.")
            tokens.add(token)
        return ids[:limit]

    def message(self, message_id):
        return self.get(f"messages/{message_id}", format="full")

    def batch_modify(self, ids, add=(), remove=()):
        """Label-only mutation (archive: remove INBOX; spam: add SPAM, remove INBOX). Idempotent, safe to retry."""
        if not ids:
            return
        if len(ids) > 1000:
            raise ValueError("Gmail batchModify allows at most 1000 ids per call.")
        allowed = {"INBOX", "SPAM"}
        if not set(add) <= allowed or not set(remove) <= allowed:
            raise ValueError("Only INBOX/SPAM label changes are supported (archive, spam).")
        body = {"ids": list(ids), "addLabelIds": list(add), "removeLabelIds": list(remove)}
        for attempt in range(RETRY_ATTEMPTS):
            if self.calls >= self.max_calls:
                raise APIError("Local call budget reached.")
            self.calls += 1
            try:
                response = self.session.post(API + "messages/batchModify", json=body, timeout=30, allow_redirects=False)
            except requests.RequestException:
                if attempt == RETRY_ATTEMPTS - 1:
                    raise APIError("Network request failed; rerun is safe (label changes are idempotent).") from None
                time.sleep(2 ** attempt)
                continue
            if response.status_code == 204:
                return
            if attempt < RETRY_ATTEMPTS - 1 and _retryable(response):
                time.sleep(_retry_delay(response))
                continue
            raise APIError(f"API returned HTTP {response.status_code}; label change may be partial. Rerun is safe.")

    def trash(self, message_id):
        """Move one message to Trash: reversible, Gmail purges Trash after ~30 days. Never permanently deletes.
        Gmail has no batch endpoint for this (unlike archive/spam), so this is one call per message."""
        for attempt in range(RETRY_ATTEMPTS):
            if self.calls >= self.max_calls:
                raise APIError("Local call budget reached.")
            self.calls += 1
            try:
                response = self.session.post(API + f"messages/{message_id}/trash", timeout=30, allow_redirects=False)
            except requests.RequestException:
                if attempt == RETRY_ATTEMPTS - 1:
                    raise APIError("Network request failed; rerun is safe (trash is idempotent).") from None
                time.sleep(2 ** attempt)
                continue
            if response.status_code == 200:
                return
            if attempt < RETRY_ATTEMPTS - 1 and _retryable(response):
                time.sleep(_retry_delay(response))
                continue
            raise APIError(f"API returned HTTP {response.status_code}; trash may be partial. Rerun is safe.")


def session_for(credentials):
    # Make retries visible to our call counter rather than hide 401 retries.
    return AuthorizedSession(credentials, max_refresh_attempts=0, refresh_timeout=30)


def _header(headers, name):
    return next((h["value"] for h in headers if h.get("name", "").casefold() == name.casefold()), None)


_UNSUB_URL_RE = re.compile(r"<([^>]+)>")


def parse_list_unsubscribe(value):
    """The mailto: and http(s): links in a List-Unsubscribe header, e.g. '<mailto:a@b.com>, <https://...>'.
    Display only: Tidy never fetches or emails these itself (clicking an unknown unsubscribe link is its own
    minor risk — can confirm a live inbox to a sender — so it stays the owner's call, one link at a time)."""
    links = {"mailto": None, "http": None}
    for url in _UNSUB_URL_RE.findall(value or ""):
        if url.lower().startswith("mailto:") and links["mailto"] is None:
            links["mailto"] = url
        elif url.lower().startswith("http") and links["http"] is None:
            links["http"] = url
    return links


def _part_text(payload, mime_type):
    """First part of `mime_type` found, walking multipart bodies depth-first."""
    if payload.get("mimeType") == mime_type and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"] + "==").decode("utf-8", "replace")
    for part in payload.get("parts", []) or []:
        text = _part_text(part, mime_type)
        if text is not None:
            return text
    return None


_STYLE_SCRIPT_RE = re.compile(r"<(style|script)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


def _html_to_text(html):
    """Strip style/script blocks (their content, not just the tags) before generic tag-stripping,
    so CSS/JS never crowds out the actual message ahead of the 1,000-char truncation."""
    return unescape(_TAG_RE.sub(" ", _STYLE_SCRIPT_RE.sub(" ", html)))


def _body_text(payload, snippet):
    """text/plain, else text/html with style/script/tags stripped, else Gmail's own short snippet."""
    plain = _part_text(payload, "text/plain")
    if plain is not None:
        return plain
    html = _part_text(payload, "text/html")
    if html is not None:
        return _html_to_text(html)
    return snippet or ""


def parse_message(raw):
    """Raw Gmail API message (format=full) into the flat fields the rest of Tidy needs."""
    payload = raw.get("payload", {})
    headers = payload.get("headers", [])
    body = _body_text(payload, raw.get("snippet"))
    body = " ".join(body.split())
    return {
        "id": required_text(raw.get("id"), "message ID"),
        "thread_id": required_text(raw.get("threadId"), "thread ID"),
        "subject": _header(headers, "Subject") or "",
        "sender": _header(headers, "From") or "",
        "to": _header(headers, "To") or "",
        "cc": _header(headers, "Cc") or "",
        "list_unsubscribe": _header(headers, "List-Unsubscribe") is not None,
        "list_unsubscribe_value": _header(headers, "List-Unsubscribe") or "",
        "list_unsubscribe_one_click": _header(headers, "List-Unsubscribe-Post") is not None,  # RFC 8058
        "internal_date_ms": int(required_text(raw.get("internalDate"), "internal date")),
        "label_ids": raw.get("labelIds", []) or [],
        "snippet": body[:1000],
    }
