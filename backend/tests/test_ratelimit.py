import unittest

from backend import config
from backend.ratelimit import RateLimiter, limiter
from backend.tests.base import ApiTestCase


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class RateLimiterUnitTests(unittest.TestCase):
    def test_blocks_after_limit_and_recovers(self):
        clock = FakeClock()
        rl = RateLimiter(clock)
        for _ in range(3):
            self.assertEqual(rl.retry_after("k", 3, 60), 0)
            rl.record("k", 60)
        wait = rl.retry_after("k", 3, 60)
        self.assertGreater(wait, 0)
        self.assertLessEqual(wait, 61)
        clock.now += 61
        self.assertEqual(rl.retry_after("k", 3, 60), 0)

    def test_keys_are_independent_and_clearable(self):
        rl = RateLimiter(FakeClock())
        rl.record("a", 60)
        rl.record("a", 60)
        self.assertGreater(rl.retry_after("a", 2, 60), 0)
        self.assertEqual(rl.retry_after("b", 2, 60), 0)
        rl.clear("a")
        self.assertEqual(rl.retry_after("a", 2, 60), 0)


class LoginThrottleApiTests(ApiTestCase):
    def bad_login(self, email="alex@brooklynrangers.club"):
        return self.request("POST", "/api/v1/auth/login", {"email": email, "password": "wrong-pass"})

    def test_account_locks_after_repeated_failures_with_retry_after(self):
        for _ in range(config.LOGIN_FAIL_LIMIT_PER_EMAIL):
            self.assertEqual(self.bad_login()["status"], 401)
        locked = self.bad_login()
        self.assertEqual(locked["status"], 429)
        self.assertEqual(locked["json"]["error"]["code"], "rate_limited")
        self.assertGreater(int(locked["headers"]["retry-after"]), 0)
        # even the correct password is refused while locked out
        good = self.request(
            "POST", "/api/v1/auth/login",
            {"email": "alex@brooklynrangers.club", "password": config.DEMO_PASSWORD},
        )
        self.assertEqual(good["status"], 429)

    def test_lockout_is_per_account_not_global(self):
        for _ in range(config.LOGIN_FAIL_LIMIT_PER_EMAIL + 1):
            self.bad_login()
        other = self.request(
            "POST", "/api/v1/auth/register",
            {"name": "Sam Lee", "email": "sam@example.com", "password": "Str0ng-pass-123"},
        )
        self.assertEqual(other["status"], 200, other["body"])
        ok = self.request(
            "POST", "/api/v1/auth/login",
            {"email": "sam@example.com", "password": "Str0ng-pass-123"},
        )
        self.assertEqual(ok["status"], 200)

    def test_success_clears_account_counter(self):
        for _ in range(config.LOGIN_FAIL_LIMIT_PER_EMAIL - 1):
            self.bad_login()
        good = self.request(
            "POST", "/api/v1/auth/login",
            {"email": "alex@brooklynrangers.club", "password": config.DEMO_PASSWORD},
        )
        self.assertEqual(good["status"], 200)
        for _ in range(config.LOGIN_FAIL_LIMIT_PER_EMAIL):
            self.assertEqual(self.bad_login()["status"], 401)

    def test_one_ip_spraying_many_emails_is_throttled(self):
        statuses = [
            self.bad_login(f"user{i}@example.com")["status"]
            for i in range(config.LOGIN_FAIL_LIMIT_PER_IP + 2)
        ]
        self.assertEqual(statuses[: config.LOGIN_FAIL_LIMIT_PER_IP], [401] * config.LOGIN_FAIL_LIMIT_PER_IP)
        self.assertEqual(statuses[-1], 429)

    def test_registration_flood_is_throttled(self):
        last = None
        for i in range(config.REGISTER_LIMIT_PER_IP + 1):
            last = self.request(
                "POST", "/api/v1/auth/register",
                {"name": "Bot Name", "email": f"bot{i}@example.com", "password": "Str0ng-pass-123"},
            )
        self.assertEqual(last["status"], 429)

    def test_x_forwarded_for_is_ignored_unless_proxy_trusted(self):
        for i in range(config.LOGIN_FAIL_LIMIT_PER_IP + 1):
            r = self.request(
                "POST", "/api/v1/auth/login",
                {"email": f"spoof{i}@example.com", "password": "x"},
                headers={"X-Forwarded-For": f"10.0.0.{i}"},
            )
        self.assertEqual(r["status"], 429)


if __name__ == "__main__":
    unittest.main()
