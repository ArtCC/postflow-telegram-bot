"""
Xquik Client
Minimal REST helper for posting text to X through Xquik.
"""

import json
from typing import Any, Callable, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


XQUIK_PENDING_PREFIX = "xquik-write-action:"


class XquikClient:
    """Client for Xquik text posts."""

    def __init__(
        self,
        api_key: str,
        account: str,
        base_url: str = "https://xquik.com",
        timeout: int = 30,
        opener: Optional[Callable[..., Any]] = None,
    ):
        """Initialize the Xquik REST client."""
        self.api_key = api_key
        self.account = account
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.opener = opener or urlopen

    def create_tweet(
        self,
        text: str,
        reply_to_tweet_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Create a text tweet through Xquik."""
        if reply_to_tweet_id and is_xquik_pending_id(reply_to_tweet_id):
            return False, None, "Cannot reply to an unconfirmed Xquik write."

        payload = {
            "account": self.account,
            "text": text,
        }
        if reply_to_tweet_id:
            payload["reply_to_tweet_id"] = reply_to_tweet_id

        request = Request(
            f"{self.base_url}/api/v1/x/tweets",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with self.opener(request, timeout=self.timeout) as response:
                data = _read_json(response)
                status = getattr(response, "status", 200)
        except HTTPError as error:
            return False, None, _read_error_message(error)
        except URLError as error:
            return False, None, f"Xquik connection failed: {error.reason}"
        except OSError as error:
            return False, None, f"Xquik request failed: {error}"

        if status == 202:
            write_action_id = _string_value(data, "writeActionId") or "pending"
            return True, f"{XQUIK_PENDING_PREFIX}{write_action_id}", None

        if 200 <= status < 300:
            tweet_id = _string_value(data, "tweetId")
            if tweet_id:
                return True, tweet_id, None
            return False, None, "Xquik response did not include a tweet ID."

        message = _string_value(data, "message") or _string_value(data, "error")
        return False, None, message or f"Xquik request failed with status {status}."


def is_xquik_pending_id(tweet_id: Optional[str]) -> bool:
    """Return whether a stored ID is an unconfirmed Xquik write."""
    return bool(tweet_id and tweet_id.startswith(XQUIK_PENDING_PREFIX))


def xquik_action_id(tweet_id: Optional[str]) -> Optional[str]:
    """Extract the Xquik write action ID from a stored pending ID."""
    if not is_xquik_pending_id(tweet_id):
        return None
    return tweet_id[len(XQUIK_PENDING_PREFIX):]


def tweet_url_for_id(tweet_id: Optional[str]) -> Optional[str]:
    """Build an X status URL only for confirmed tweet IDs."""
    if not tweet_id or is_xquik_pending_id(tweet_id):
        return None
    return f"https://twitter.com/i/web/status/{tweet_id}"


def _read_json(response: Any) -> dict:
    """Read a JSON response body."""
    raw_body = response.read()
    if not raw_body:
        return {}
    try:
        data = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if isinstance(data, dict):
        return data
    return {}


def _read_error_message(error: HTTPError) -> str:
    """Read the most useful message from an HTTP error response."""
    data = _read_json(error)
    return (
        _string_value(data, "message")
        or _string_value(data, "error")
        or f"Xquik request failed with status {error.code}."
    )


def _string_value(data: dict, key: str) -> Optional[str]:
    """Return a non-empty string value from a dictionary."""
    value = data.get(key)
    if isinstance(value, str) and value:
        return value
    return None
