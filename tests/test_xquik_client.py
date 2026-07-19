import io
import json
import unittest
from urllib.error import HTTPError

from bot.services.xquik_client import (
    XQUIK_PENDING_PREFIX,
    XquikClient,
    is_xquik_pending_id,
    tweet_url_for_id,
    xquik_action_id,
)


class FakeResponse:
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class XquikClientTest(unittest.TestCase):
    def test_create_tweet_posts_text_payload(self):
        requests = []

        def opener(request, timeout=None):
            requests.append((request, timeout))
            return FakeResponse(200, {"tweetId": "12345", "success": True})

        client = XquikClient("test-key", "demo-account", opener=opener)

        success, tweet_id, error = client.create_tweet("Hello X")

        self.assertEqual((success, tweet_id, error), (True, "12345", None))
        self.assertEqual(len(requests), 1)
        request, timeout = requests[0]
        self.assertEqual(timeout, 30)
        self.assertEqual(request.full_url, "https://xquik.com/api/v1/x/tweets")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.headers["X-api-key"], "test-key")
        self.assertNotIn("Authorization", request.headers)
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {"account": "demo-account", "text": "Hello X"},
        )

    def test_create_tweet_tracks_pending_write_action(self):
        def opener(_request, timeout=None):
            return FakeResponse(202, {"writeActionId": "write-42"})

        client = XquikClient("test-key", "demo-account", opener=opener)

        success, tweet_id, error = client.create_tweet("Hello X")

        self.assertEqual(success, True)
        self.assertEqual(tweet_id, f"{XQUIK_PENDING_PREFIX}write-42")
        self.assertIsNone(error)
        self.assertTrue(is_xquik_pending_id(tweet_id))
        self.assertEqual(xquik_action_id(tweet_id), "write-42")
        self.assertIsNone(tweet_url_for_id(tweet_id))

    def test_create_tweet_reports_http_error_message(self):
        def opener(_request, timeout=None):
            body = io.BytesIO(json.dumps({"message": "Account is required."}).encode("utf-8"))
            raise HTTPError(
                "https://xquik.com/api/v1/x/tweets",
                422,
                "Unprocessable Entity",
                {},
                body,
            )

        client = XquikClient("test-key", "demo-account", opener=opener)

        success, tweet_id, error = client.create_tweet("Hello X")

        self.assertEqual((success, tweet_id, error), (False, None, "Account is required."))


if __name__ == "__main__":
    unittest.main()
