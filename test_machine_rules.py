import os
import unittest

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "test-key")
os.environ.setdefault("TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-secret")

from fastapi import HTTPException
from handlers import valid_cycle_duration
from main import telegram_webhook


class RequestWithoutWebhookSecret:
    headers = {}

    async def json(self):
        raise AssertionError("An invalid request must not be parsed.")


class CycleDurationTests(unittest.TestCase):
    def test_only_configured_durations_are_allowed(self):
        self.assertTrue(valid_cycle_duration("Washer", 33))
        self.assertTrue(valid_cycle_duration("Dryer", 70))
        self.assertFalse(valid_cycle_duration("Washer", 70))
        self.assertFalse(valid_cycle_duration("Unknown", 33))


class WebhookSecurityTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_a_missing_webhook_secret(self):
        with self.assertRaises(HTTPException) as error:
            await telegram_webhook(RequestWithoutWebhookSecret())
        self.assertEqual(error.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
