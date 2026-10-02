"""Google's OAuth implementation plus GET-only YouTube inventory collection."""

import json
import time

import requests

from .google_oauth import IDENTITY, GoogleOAuth, session_for  # noqa: F401 (session_for re-exported)
from .store import required_text


READ_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
SCOPES = [READ_SCOPE, *IDENTITY]
# Write access lives in a separate token, only used by the approved-unsubscribe command.
WRITE_SCOPE = "https://www.googleapis.com/auth/youtube"
WRITE_SCOPES = [WRITE_SCOPE, *IDENTITY]
API = "https://www.googleapis.com/youtube/v3/"
USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"
DELETE_COST = 50  # documented quota cost of subscriptions.delete
SUBSCRIBE_COST = 50  # documented quota cost of subscriptions.insert


class APIError(RuntimeError):
    pass


class UnknownOutcome(APIError):
    """A mutation may or may not have happened; reconcile before retrying."""


_oauth = GoogleOAuth(READ_SCOPE, WRITE_SCOPE, "read-only YouTube", "YouTube write", APIError)
check_scopes, authorize = _oauth.check_scopes, _oauth.authorize
load_credentials, save_credentials = _oauth.load_credentials, _oauth.save_credentials

class YouTube:
    def __init__(self, session, max_units=100):
        if max_units < 1:
            raise ValueError("Quota budget must be positive.")
        self.session = session
        self.max_units = max_units
        self.units = 0

    def get(self, resource, **params):
        # No user-controlled URL, HTTP method, or mutation endpoint.
        if resource not in ("channels", "subscriptions", "userinfo", "playlistItems", "videos"):
            raise ValueError("Only read-only endpoints are supported.")
        is_youtube = resource != "userinfo"
        for attempt in range(3):
            if is_youtube:
                if self.units >= self.max_units:
                    raise APIError("Local quota budget reached.")
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

    def delete_subscription(self, subscription_id):
        """The only mutation. One attempt, never auto-retried: an ambiguous outcome must be reconciled."""
        if self.units + DELETE_COST > self.max_units:
            raise APIError("Local quota budget reached; no unsubscribe attempted.")
        self.units += DELETE_COST
        try:
            response = self.session.delete(API + "subscriptions", params={"id": subscription_id},
                                           timeout=30, allow_redirects=False)
        except requests.RequestException:
            raise UnknownOutcome("Network failure during unsubscribe; outcome unknown.") from None
        if response.status_code == 204:
            return "deleted"
        if response.status_code == 404:
            return "absent"
        if response.status_code >= 500 or response.status_code == 429:
            raise UnknownOutcome(f"API returned HTTP {response.status_code}; outcome unknown.")
        raise APIError(f"API returned HTTP {response.status_code}; unsubscribe not performed.")

    def subscribe(self, channel_id):
        """One attempt, never auto-retried. Returns (outcome, subscription_id or None)."""
        if self.units + SUBSCRIBE_COST > self.max_units:
            raise APIError("Local quota budget reached; no subscribe attempted.")
        self.units += SUBSCRIBE_COST
        body = {"snippet": {"resourceId": {"kind": "youtube#channel", "channelId": channel_id}}}
        try:
            response = self.session.post(API + "subscriptions", params={"part": "snippet"}, json=body,
                                         timeout=30, allow_redirects=False)
        except requests.RequestException:
            raise UnknownOutcome("Network failure during subscribe; outcome unknown.") from None
        if response.status_code == 200:
            try:
                return "subscribed", required_text(response.json().get("id"), "subscription ID")
            except (ValueError, AttributeError):
                raise UnknownOutcome("Subscribe reply unreadable; outcome unknown.") from None
        if response.status_code >= 500 or response.status_code == 429:
            raise UnknownOutcome(f"API returned HTTP {response.status_code}; outcome unknown.")
        if response.status_code == 400:
            try:
                if "subscriptionDuplicate" in json.dumps(response.json()):
                    return "exists", None
            except ValueError:
                pass
        raise APIError(f"API returned HTTP {response.status_code}; subscribe not performed.")

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


