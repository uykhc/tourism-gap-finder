import tempfile
import unittest
from pathlib import Path

from hankkeut_calculation.tourism_data.config import (
    resolve_hub_service_key,
    resolve_portfolio_service_key,
    resolve_service_key,
)


class ResolveServiceKeyTest(unittest.TestCase):
    def test_resolves_separate_keys_for_each_analysis(self) -> None:
        environment = {
            "KOR_TOUR_API_SERVICE_KEY": "portfolio-key",
            "HUB_TOUR_API_SERVICE_KEY": "hub-key",
            "TOUR_API_SERVICE_KEY": "legacy-key",
        }

        portfolio_key = resolve_portfolio_service_key(environ=environment)
        hub_key = resolve_hub_service_key(environ=environment)

        self.assertEqual(portfolio_key, "portfolio-key")
        self.assertEqual(hub_key, "hub-key")

    def test_specific_dotenv_key_wins_regardless_of_file_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dotenv_path = Path(temp_dir) / ".env"
            dotenv_path.write_text(
                "TOUR_API_SERVICE_KEY=legacy-key\n"
                "HUB_TOUR_API_SERVICE_KEY=hub-key\n",
                encoding="utf-8",
            )

            result = resolve_hub_service_key(
                dotenv_path=dotenv_path,
                environ={},
            )

        self.assertEqual(result, "hub-key")

    def test_uses_legacy_key_when_specific_key_is_missing(self) -> None:
        environment = {"TOUR_API_SERVICE_KEY": "legacy-key"}

        self.assertEqual(
            resolve_portfolio_service_key(environ=environment),
            "legacy-key",
        )
        self.assertEqual(
            resolve_hub_service_key(environ=environment),
            "legacy-key",
        )

    def test_environment_takes_precedence_over_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dotenv_path = Path(temp_dir) / ".env"
            dotenv_path.write_text(
                "TOUR_API_SERVICE_KEY=dotenv-key\n",
                encoding="utf-8",
            )

            result = resolve_service_key(
                dotenv_path=dotenv_path,
                environ={"TOUR_API_SERVICE_KEY": "environment-key"},
            )

        self.assertEqual(result, "environment-key")

    def test_environment_legacy_key_takes_precedence_over_specific_dotenv_key(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dotenv_path = Path(temp_dir) / ".env"
            dotenv_path.write_text(
                "HUB_TOUR_API_SERVICE_KEY=dotenv-hub-key\n",
                encoding="utf-8",
            )

            result = resolve_hub_service_key(
                dotenv_path=dotenv_path,
                environ={"TOUR_API_SERVICE_KEY": "environment-key"},
            )

        self.assertEqual(result, "environment-key")

    def test_reads_exported_and_quoted_value_from_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dotenv_path = Path(temp_dir) / ".env"
            dotenv_path.write_text(
                "# local secret\n"
                "OTHER_VALUE=ignored\n"
                "export TOUR_API_SERVICE_KEY='encoded+key/value='\n",
                encoding="utf-8",
            )

            result = resolve_service_key(
                dotenv_path=dotenv_path,
                environ={},
            )

        self.assertEqual(result, "encoded+key/value=")

    def test_returns_none_when_dotenv_does_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = resolve_service_key(
                dotenv_path=Path(temp_dir) / ".env",
                environ={},
            )

        self.assertIsNone(result)

    def test_reports_malformed_quotes_without_exposing_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dotenv_path = Path(temp_dir) / ".env"
            dotenv_path.write_text(
                "TOUR_API_SERVICE_KEY='secret-value\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "따옴표") as context:
                resolve_service_key(dotenv_path=dotenv_path, environ={})

        self.assertNotIn("secret-value", str(context.exception))


if __name__ == "__main__":
    unittest.main()
