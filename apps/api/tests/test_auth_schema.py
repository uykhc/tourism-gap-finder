"""Frontend and API registration-contract tests."""

import unittest

from pydantic import ValidationError

from apps.api.app.schemas.auth import ChangePasswordRequest, SignUpRequest


class AuthSchemaTest(unittest.TestCase):
    def test_signup_accepts_the_frontend_payload_without_consents(self) -> None:
        request = SignUpRequest.model_validate(
            {
                "email": "visitor@example.com",
                "password": "Password123",
                "password_confirm": "Password123",
                "default_region": None,
            }
        )
        self.assertEqual(request.email, "visitor@example.com")

    def test_password_still_requires_letters_and_digits(self) -> None:
        with self.assertRaises(ValidationError):
            SignUpRequest.model_validate(
                {
                    "email": "visitor@example.com",
                    "password": "passwordonly",
                    "password_confirm": "passwordonly",
                    "default_region": None,
                }
            )

    def test_password_change_uses_the_same_rule(self) -> None:
        request = ChangePasswordRequest.model_validate(
            {"new_password": "Password123", "new_password_confirm": "Password123"}
        )
        self.assertEqual(request.new_password, "Password123")


if __name__ == "__main__":
    unittest.main()
