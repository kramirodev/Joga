"""Testes da prova de OTP com adapter simulado."""

from __future__ import annotations

import secrets
import unittest

from otp import (
    MAX_ATTEMPTS,
    OTP_LENGTH,
    OTP_TTL_SECONDS,
    RESEND_COOLDOWN_SECONDS,
    AlreadyUsed,
    ChallengeExpired,
    ChallengeNotFound,
    InvalidCode,
    InvalidPhone,
    OtpService,
    ResendTooSoon,
    SimulatedSmsAdapter,
    TooManyAttempts,
    normalize_phone,
)


class FakeClock:
    def __init__(self, start: float = 1_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class OtpTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        self.adapter = SimulatedSmsAdapter()
        self.service = OtpService(
            secret=secrets.token_bytes(32),
            adapter=self.adapter,
            clock=self.clock,
        )

    def request(self, phone: str = "+5511999999999") -> tuple[str, str]:
        challenge_id = self.service.request_code(phone)
        return challenge_id, self.adapter.sent[-1]["code"]


class NormalizePhoneTests(unittest.TestCase):
    def test_accepts_e164_and_common_separators(self) -> None:
        self.assertEqual(normalize_phone("+55 11 99999-9999"), "+5511999999999")
        self.assertEqual(normalize_phone("+55 (11) 99999.9999"), "+5511999999999")

    def test_converts_00_prefix(self) -> None:
        self.assertEqual(normalize_phone("005511999999999"), "+5511999999999")

    def test_rejects_invalid_input(self) -> None:
        for raw in ("", "11999999999", "+0123456789", "+55abc", "+551"):
            with self.subTest(raw=raw), self.assertRaises(InvalidPhone):
                normalize_phone(raw)


class RequestCodeTests(OtpTestCase):
    def test_sends_six_digit_code_and_stores_only_hash(self) -> None:
        challenge_id, code = self.request()

        self.assertEqual(len(code), OTP_LENGTH)
        self.assertTrue(code.isdigit())
        self.assertEqual(self.adapter.sent[-1]["phone"], "+5511999999999")
        challenge = self.service._challenges[challenge_id]
        self.assertNotIn(code, repr(challenge))
        self.assertNotEqual(challenge.code_hash, code)
        self.assertEqual(len(challenge.code_hash), 64)

    def test_rejects_secret_shorter_than_32_bytes(self) -> None:
        with self.assertRaises(ValueError):
            OtpService(secret=b"curto", adapter=self.adapter)

    def test_enforces_resend_cooldown_and_invalidates_previous(self) -> None:
        first_id, first_code = self.request()

        self.clock.advance(RESEND_COOLDOWN_SECONDS - 1)
        with self.assertRaises(ResendTooSoon):
            self.service.request_code("+5511999999999")

        self.clock.advance(1)
        second_id, second_code = self.request()
        self.assertNotEqual(first_id, second_id)
        self.assertNotEqual(first_code, second_code)

        with self.assertRaises(AlreadyUsed):
            self.service.verify_code(first_id, first_code)

        self.assertEqual(self.service.verify_code(second_id, second_code), "+5511999999999")


class VerifyCodeTests(OtpTestCase):
    def test_valid_code_is_single_use(self) -> None:
        challenge_id, code = self.request()

        self.assertEqual(self.service.verify_code(challenge_id, code), "+5511999999999")
        with self.assertRaises(AlreadyUsed):
            self.service.verify_code(challenge_id, code)

    def test_unknown_challenge(self) -> None:
        with self.assertRaises(ChallengeNotFound):
            self.service.verify_code("nao-existe", "000000")

    def test_expires_after_ttl(self) -> None:
        challenge_id, code = self.request()

        self.clock.advance(OTP_TTL_SECONDS + 1)
        with self.assertRaises(ChallengeExpired):
            self.service.verify_code(challenge_id, code)

    def test_blocks_after_max_attempts(self) -> None:
        challenge_id, code = self.request()
        wrong = "000000" if code != "000000" else "111111"

        for attempt in range(1, MAX_ATTEMPTS):
            with self.subTest(attempt=attempt), self.assertRaises(InvalidCode):
                self.service.verify_code(challenge_id, wrong)

        with self.assertRaises(TooManyAttempts):
            self.service.verify_code(challenge_id, wrong)

        # O código correto não pode reabilitar um desafio já bloqueado.
        with self.assertRaises(AlreadyUsed):
            self.service.verify_code(challenge_id, code)

    def test_wrong_code_does_not_consume_attempts_on_correct_submission(self) -> None:
        challenge_id, code = self.request()
        wrong = "000000" if code != "000000" else "111111"

        with self.assertRaises(InvalidCode):
            self.service.verify_code(challenge_id, wrong)

        self.assertEqual(self.service.verify_code(challenge_id, code), "+5511999999999")

    def test_challenge_repr_does_not_leak_phone(self) -> None:
        challenge_id, _ = self.request()
        self.assertNotIn("5511999999999", repr(self.service._challenges[challenge_id]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
