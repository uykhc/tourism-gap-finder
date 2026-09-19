import unittest
from unittest.mock import patch

from hankkeut_calculation.datalab_navigation.kakao_supply import (
    CONTENT_TYPES,
    MemorySupplyProvider,
    PostgresKakaoSupplyProvider,
    normalize_supply_run,
)


class KakaoSupplyDatabaseTest(unittest.TestCase):
    def test_korean_and_english_rows_normalize_to_the_same_codes(self):
        korean = normalize_supply_run(_metadata(), _rows(korean=True), required_region_ids=("26350",))
        english = normalize_supply_run(_metadata(), _rows(korean=False), required_region_ids=("26350",))
        self.assertEqual(
            korean.regions["26350"]["content_type_counts"],
            english.regions["26350"]["content_type_counts"],
        )
        self.assertEqual(korean.normalized_sha256, english.normalized_sha256)

    def test_postgres_provider_selects_regions_without_a_run_id(self):
        with patch(
            "hankkeut_calculation.datalab_navigation.kakao_supply._read_latest_supply_region",
            return_value=(_metadata(), _rows(korean=True)),
        ):
            database = PostgresKakaoSupplyProvider(
                "postgresql://example", required_region_ids=("26350",)
            )
        memory = MemorySupplyProvider(
            {"26350": database.run.regions["26350"]},
            taxonomy_version="tourism-v1",
        )
        self.assertEqual(
            database.get_region("26350")["content_type_counts"],
            memory.get_region("26350")["content_type_counts"],
        )

    def test_rejects_invalid_run_variants(self):
        cases = {
            "unknown type": lambda m, r: r[0].__setitem__(1, "기타"),
            "missing type": lambda m, r: r.pop(),
            "negative count": lambda m, r: r[0].__setitem__(2, -1),
            "noninteger count": lambda m, r: r[0].__setitem__(2, 1.5),
            "incomplete": lambda m, r: r[0].__setitem__(3, False),
            "truncated": lambda m, r: r[0].__setitem__(4, 1),
            "not completed": lambda m, r: m.update({"status": "running"}),
            "normalized duplicate": lambda m, r: r.append(["26350", "FOOD", 1, True, 0]),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                metadata = _metadata()
                rows = _rows(korean=True)
                mutate(metadata, rows)
                with self.assertRaises(ValueError):
                    normalize_supply_run(metadata, rows, required_region_ids=("26350",))

    def test_rejects_missing_required_region(self):
        with self.assertRaisesRegex(ValueError, "필수 지역"):
            normalize_supply_run(_metadata(), _rows(korean=True), required_region_ids=("47130",))


class KakaoSupplySelectionTest(unittest.TestCase):
    def test_allows_incomplete_and_noncompleted_rows_when_requested(self):
        metadata = _metadata()
        metadata["status"] = "failed"
        rows = _rows(korean=False)
        rows[0][3] = False
        rows[0][4] = 3
        result = normalize_supply_run(
            metadata,
            rows,
            required_region_ids=("26350",),
            require_complete=False,
            require_completed=False,
        )
        self.assertEqual(result.regions["26350"]["content_type_counts"]["FOOD"], 1)


def _metadata() -> dict:
    return {
        "run_id": "run-1",
        "taxonomy_version": "tourism-v1",
        "collected_at": "2026-09-19T00:00:00+09:00",
        "status": "completed",
    }


def _rows(*, korean: bool) -> list[list[object]]:
    names = (
        ("음식", "숙박", "문화관광", "체험관광", "레저스포츠", "쇼핑")
        if korean else CONTENT_TYPES
    )
    return [
        ["26350", content_type, index + 1, True, 0]
        for index, content_type in enumerate(names)
    ]


if __name__ == "__main__":
    unittest.main()
