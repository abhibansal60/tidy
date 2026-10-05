"""Google's OAuth implementation plus Gmail read access and label-only mutation (archive, spam). No sends or deletes."""

import base64
from contextlib import contextmanager
from html import unescape
from pathlib import Path
import re
import time

import requests

from .google_oauth import IDENTITY, GoogleOAuth, session_for
from .store import required_text


READ_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
SCOPES = [READ_SCOPE, *IDENTITY]
# Write access (label changes only: archive, spam) lives in a separate token, same split as tidy/youtube.py.
WRITE_SCOPE = "https://www.googleapis.com/auth/gmail.modify"
WRITE_SCOPES = [WRITE_SCOPE, *IDENTITY]
API = "https://gmail.googleapis.com/gmail/v1/users/me/"
USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"


class APIError(RuntimeError):
    pass


_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")


def check_id(message_id):
    """Gmail message IDs are short hex strings (allowed: URL-safe word chars). IDs can come from a hand-editable run.json (`mail-act`),
    so validate before they go into a URL path: nothing like `../` or `?` ever reaches the API."""
    if not isinstance(message_id, str) or not _ID_RE.fullmatch(message_id):
        raise ValueError(f"Invalid Gmail message ID: {message_id!r}")
    return message_id


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
        return min(float(delay), 120)  # a hostile or broken Retry-After must not park the run for hours
    return 65 if response.status_code == 403 else 2  # per-minute quota resets; short backoff won't help a 403


_oauth = GoogleOAuth(READ_SCOPE, WRITE_SCOPE, "read-only Gmail", "Gmail modify (labels only)", APIError)
check_scopes, authorize = _oauth.check_scopes, _oauth.authorize
load_credentials, save_credentials = _oauth.load_credentials, _oauth.save_credentials

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
        return self.get(f"messages/{check_id(message_id)}", format="full")

    def labels(self, message_id):
        """Current label IDs for one message (cheap `format=minimal` read), for rechecking live state before a mutation."""
        return self.get(f"messages/{check_id(message_id)}", format="minimal").get("labelIds", []) or []

    def batch_modify(self, ids, add=(), remove=()):
        """Label-only mutation (archive: remove INBOX; spam: add SPAM, remove INBOX). Idempotent, safe to retry."""
        if not ids:
            return
        ids = [check_id(i) for i in ids]
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
                response = self.session.post(API + f"messages/{check_id(message_id)}/trash", timeout=30, allow_redirects=False)
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




@contextmanager
def connect(token_path, expected_email=None, write=False, max_calls=1200):
    """A `Gmail` on the saved token: verifies the account when `expected_email` is given, and saves the token
    again on a clean exit so a refreshed access token is kept. Missing token -> ValueError naming the fix."""
    if not Path(token_path).is_file():
        raise ValueError("No Gmail write token. Run mail-auth --write first; see README." if write else
                         "No Gmail OAuth token. Run mail-auth first; see README.")
    credentials = load_credentials(token_path, write)
    with session_for(credentials) as session:
        api = Gmail(session, max_calls)
        if expected_email:
            api.identity(expected_email)
        yield api
    save_credentials(token_path, credentials, write)


def _header(headers, name):
    return next((h["value"] for h in headers if h.get("name", "").casefold() == name.casefold()), None)


_UNSUB_URL_RE = re.compile(r"<([^>]+)>")


def parse_list_unsubscribe(value):
    """The mailto: and http(s): links in a List-Unsubscribe header, e.g. '<mailto:a@b.com>, <https://...>'.
    Display only: Tidy never fetches or emails these itself (clicking an unknown unsubscribe link is its own
    minor risk, since it can confirm a live inbox to a sender, so it stays the owner's call, one link at a time)."""
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


_STYLE_SCRIPT_OPEN_RE = re.compile(r"<(style|script)\b", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def _drop_style_script(html):
    """Remove style/script blocks in one linear pass. A lazy `.*?</\\1>` regex is quadratic on unclosed
    tags, so any sender could stall the run with one crafted email; an unclosed block drops the rest."""
    lower, out, i = html.lower(), [], 0
    while m := _STYLE_SCRIPT_OPEN_RE.search(html, i):
        out.append(html[i:m.start()])
        close = f"</{m.group(1).lower()}>"
        end = lower.find(close, m.end())
        if end == -1:
            return " ".join(out)
        out.append(" ")
        i = end + len(close)
    out.append(html[i:])
    return "".join(out)


def _html_to_text(html):
    """Strip style/script blocks (their content, not just the tags) before generic tag-stripping,
    so CSS/JS never crowds out the actual message ahead of the 1,000-char truncation."""
    return unescape(_TAG_RE.sub(" ", _drop_style_script(html)))


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
