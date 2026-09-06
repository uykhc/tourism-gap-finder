import csv
import json
import tempfile
import unittest
from pathlib import Path

from hankkeut_analysis.datalab_navigation.navigation_demand import (
    build_supply_pressure_report,
    import_navigation_demand_csv,
    load_navigation_demand_taxonomy,
)
from hankkeut_analysis.datalab_navigation.peer_manifest import build_peer_demand_manifest
from hankkeut_analysis.datalab_navigation.peer_comparison import build_peer_supply_pressure_comparison
from hankkeut_analysis.datalab_navigation.relative_supply import build_relative_supply_report


class DataLabNavigationDemandTest(unittest.TestCase):
    def test_imports_monthly_csv_maps_types_and_builds_pressure_report(self):
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            csv_path = directory_path / "navigation.csv"
            _write_csv(csv_path, [
                ("202501", "전체", "100"), ("202501", "음식", "10"), ("202501", "숙박", "10"),
                ("202501", "문화관광", "20"), ("202501", "자연관광", "5"), ("202501", "역사관광", "5"),
                ("202501", "체험관광", "10"), ("202501", "레저스포츠", "10"), ("202501", "쇼핑", "20"), ("202501", "기타관광", "10"),
                ("202502", "전체", "200"), ("202502", "음식", "20"), ("202502", "숙박", "20"),
                ("202502", "문화관광", "40"), ("202502", "자연관광", "10"), ("202502", "역사관광", "10"),
                ("202502", "체험관광", "20"), ("202502", "레저스포츠", "20"), ("202502", "쇼핑", "40"), ("202502", "기타관광", "20"),
            ])
            taxonomy = load_navigation_demand_taxonomy(Path("config/datalab/navigation_destination_type_taxonomy.json"))
            demand_import = import_navigation_demand_csv(csv_path, region_name="수원시", taxonomy=taxonomy)
            self.assertEqual(demand_import.available_months, ("202501", "202502"))
            culture = next(record for record in demand_import.records if record.base_ym == "202501" and record.source_type == "역사관광")
            self.assertEqual(culture.content_type, "문화관광")
            excluded = next(record for record in demand_import.records if record.base_ym == "202501" and record.source_type == "기타관광")
            self.assertFalse(excluded.included)

            kakao_path = directory_path / "kakao.json"
            kakao_path.write_text(json.dumps({"regions": [{
                "region_name": "수원시", "taxonomy_version": "test", "is_complete": True, "truncated_tile_count": 0,
                "content_type_counts": {"음식": 2, "숙박": 2, "문화관광": 3, "체험관광": 2, "레저스포츠": 2, "쇼핑": 4},
            }]}, ensure_ascii=False), encoding="utf-8")
            report = build_supply_pressure_report(demand_import, taxonomy=taxonomy, kakao_collection_path=kakao_path, month_count=2)

        metrics = {metric["content_type"]: metric for metric in report["content_type_metrics"]}
        self.assertEqual(metrics["문화관광"]["navigation_search_count"], 90)
        self.assertEqual(metrics["문화관광"]["searches_per_place"], 30.0)
        self.assertEqual(report["demand_summary"]["excluded_source_type_counts"], {"기타관광": 30})
        self.assertEqual(report["ai_report_context"]["priority_order_by_supply_pressure"][0], "문화관광")

    def test_rejects_month_when_total_does_not_equal_type_sum(self):
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "invalid.csv"
            _write_csv(csv_path, [
                ("202501", "전체", "100"), ("202501", "음식", "10"), ("202501", "숙박", "10"),
                ("202501", "문화관광", "10"), ("202501", "자연관광", "10"), ("202501", "역사관광", "10"),
                ("202501", "체험관광", "10"), ("202501", "레저스포츠", "10"), ("202501", "쇼핑", "10"), ("202501", "기타관광", "10"),
            ])
            taxonomy = load_navigation_demand_taxonomy(Path("config/datalab/navigation_destination_type_taxonomy.json"))
            with self.assertRaisesRegex(ValueError, "전체 검색량"):
                import_navigation_demand_csv(csv_path, region_name="수원시", taxonomy=taxonomy)

    def test_restores_an_omitted_zero_destination_type_when_total_proves_it(self):
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "missing_type.csv"
            _write_csv(csv_path, [
                ("202501", "전체", "100"), ("202501", "음식", "10"), ("202501", "숙박", "10"),
                ("202501", "문화관광", "10"), ("202501", "자연관광", "10"), ("202501", "역사관광", "10"),
                ("202501", "체험관광", "10"), ("202501", "쇼핑", "20"), ("202501", "기타관광", "20"),
            ])
            taxonomy = load_navigation_demand_taxonomy(Path("config/datalab/navigation_destination_type_taxonomy.json"))
            result = import_navigation_demand_csv(csv_path, region_name="구리시", taxonomy=taxonomy)
        restored = next(record for record in result.records if record.source_type == "레저스포츠")
        self.assertEqual(restored.search_count, 0)
        self.assertTrue(restored.source_value_inferred)


class PeerDemandManifestTest(unittest.TestCase):
    def test_creates_monthly_input_tasks_without_calling_candidates_benchmarks(self):
        manifest = build_peer_demand_manifest({
            "target": {"region_id": "41110", "region_name": "수원시"},
            "peers": [{"rank": 1, "region_id": "41130", "region_name": "성남시", "similarity": 0.577}],
        })
        self.assertEqual(manifest["selection_type"], "structural_similarity_candidates")
        self.assertEqual(manifest["peer_inputs"][0]["recommended_raw_directory"], "data/raw/datalab_navigation/peers/41130_성남시")


class PeerSupplyPressureComparisonTest(unittest.TestCase):
    def test_prioritizes_maximum_individual_peer_pressure_ratio(self):
        target = _pressure_report("수원시", {"문화관광": 100.0, "쇼핑": 10.0})
        peer_a = _pressure_report("성남시", {"문화관광": 20.0, "쇼핑": 20.0})
        peer_b = _pressure_report("용인시", {"문화관광": 30.0, "쇼핑": 10.0})
        result = build_peer_supply_pressure_comparison(target, peer_reports=[peer_a, peer_b], peer_regions=["성남시", "용인시"])
        self.assertEqual(result["ai_report_context"]["priority_order_by_individual_peer_pressure"][0], "문화관광")
        self.assertEqual(result["peer_supply_pressure_comparison"][0]["max_target_to_peer_ratio"], 5.0)

    def test_limits_comparison_to_the_first_three_ranked_peers_by_default(self):
        target = _pressure_report("수원시", {"문화관광": 100.0})
        peers = [_pressure_report(name, {"문화관광": value}) for name, value in [
            ("성남시", 20.0), ("용인시", 30.0), ("고양시", 40.0), ("안양시", 50.0),
        ]]
        result = build_peer_supply_pressure_comparison(
            target, peer_reports=peers, peer_regions=["성남시", "용인시", "고양시", "안양시"],
        )
        self.assertEqual(result["peer_regions"], ["성남시", "용인시", "고양시"])
        self.assertEqual(result["ai_report_context"]["peer_count"], 3)


class RelativeSupplyComparisonTest(unittest.TestCase):
    def test_marks_a_type_when_composition_or_density_is_lower_than_an_individual_peer(self):
        target = _kakao_region("수원시", {"문화관광": 10, "음식": 90})
        peer_a = _kakao_region("성남시", {"문화관광": 30, "음식": 70})
        peer_b = _kakao_region("용인시", {"문화관광": 5, "음식": 95})
        result = build_relative_supply_report(
            target_region=target, peer_regions=[peer_a, peer_b],
            area_km2_by_region={"수원시": 100.0, "성남시": 100.0, "용인시": 200.0},
        )
        culture = next(item for item in result["content_type_comparisons"] if item["content_type"] == "문화관광")
        self.assertEqual(culture["candidate_peer_regions"], ["성남시"])
        self.assertEqual(result["priority_order_by_relative_supply_gap"][0], "문화관광")


def _write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["기준연월", "목적지 유형", "목적지 검색량"])
        writer.writerows(rows)


def _pressure_report(region_name, overrides):
    content_types = ["음식", "숙박", "문화관광", "체험관광", "레저스포츠", "쇼핑"]
    metrics = [{"content_type": name, "searches_per_place": overrides.get(name, 1.0)} for name in content_types]
    return {
        "region_name": region_name,
        "content_type_metrics": metrics,
        "ai_report_context": {
            "region_name": region_name,
            "analysis_period": "202508~202607",
            "metric_definition": "검색량 ÷ 장소 수",
            "limitation": "파일럿",
            "priority_order_by_supply_pressure": content_types,
            "content_type_metrics": metrics,
        },
    }


def _kakao_region(region_name, overrides):
    counts = {"음식": 0, "숙박": 0, "문화관광": 0, "체험관광": 0, "레저스포츠": 0, "쇼핑": 0}
    counts.update(overrides)
    return {"region_name": region_name, "content_type_counts": counts, "is_complete": True}


if __name__ == "__main__":
    unittest.main()
