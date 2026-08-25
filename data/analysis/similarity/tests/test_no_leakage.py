"""원칙 1을 코드로 강제한다.

공백 분석의 output(관광 콘텐츠 유형별 공급)이 유사지역 선정의 input에
들어가면, 찾으려는 공백을 미리 지워 버린다. 사람이 주의하는 것만으로는
언젠가 깨지므로 테스트로 막는다.
"""

from __future__ import annotations

import unittest

from tourgap.config import SIMILARITY_FEATURES
from tourgap.similarity import feature_columns, feature_weights

CONTENT_CATEGORY_CODES = {"NA", "HS", "VE", "EX", "LS", "EV", "SH", "FD", "AC", "C01"}
CONTENT_CATEGORY_NAMES = {
    "자연관광",
    "역사관광",
    "문화관광",
    "체험관광",
    "레저스포츠",
    "축제",
    "공연",
    "행사",
    "쇼핑",
    "음식",
    "숙박",
    "추천코스",
}
SUPPLY_METRICS = {"raw_count", "share", "per_10k_pop", "per_100km2"}
PERFORMANCE_METRICS = {
    "stay_intensity",
    "consumption_intensity",
    "visitor_level",
    "visitor_yoy_growth",
    "outsider_ratio",
    "foreign_ratio",
}


class SimilarityIsolationTest(unittest.TestCase):
    def test_no_content_category_in_similarity_features(self) -> None:
        """관광 콘텐츠 카테고리 코드/이름이 유사성 feature에 없어야 한다.

        부분 문자열이 아니라 토큰 단위로 비교한다. 'fishery_household_ratio'
        안의 'sh'를 쇼핑(SH)으로 오인하면 안 되기 때문이다.
        """
        forbidden = {
            *(c.lower() for c in CONTENT_CATEGORY_CODES),
            *(name.lower() for name in CONTENT_CATEGORY_NAMES),
        }
        for feature in feature_columns():
            tokens = {feature.lower(), *feature.lower().split("_")}
            overlap = tokens & forbidden
            self.assertEqual(
                overlap,
                set(),
                f"유사성 feature '{feature}' 에 콘텐츠 분류 {overlap} 이 있습니다.",
            )

    def test_no_supply_metric_in_similarity_features(self) -> None:
        """공급 지표 이름이 유사성 feature에 없어야 한다."""
        features = set(feature_columns())
        self.assertEqual(features & set(SUPPLY_METRICS), set())

    def test_no_performance_metric_in_similarity_features(self) -> None:
        """성과 지표가 유사성 feature에 없어야 한다(원칙 1·3)."""
        features = set(feature_columns())
        self.assertEqual(features & PERFORMANCE_METRICS, set())

    def test_similarity_features_are_structural_only(self) -> None:
        """유사성 feature는 허용된 구조 변수 목록 안에서만 쓴다.

        새 feature를 넣을 때 이 목록을 함께 고치도록 강제해, 관광 결과
        변수가 슬그머니 들어오는 것을 막는다.
        """
        allowed = {
            "area_km2",
            "total_population",
            "population_density",
            "average_age",
            "urbanization_ratio",
            "coastal_dummy",
            "island_ratio",
            "forest_ratio",
            "farmland_ratio",
            "terrain_relief",
            "annual_mean_temperature",
            "annual_temperature_range",
            "annual_precipitation",
            "business_density",
            "manufacturing_worker_ratio",
            "construction_logistics_worker_ratio",
            "knowledge_public_service_worker_ratio",
        }
        self.assertTrue(
            set(feature_columns()) <= allowed,
            f"허용 목록 밖의 feature: {set(feature_columns()) - allowed}",
        )
        self.assertEqual(tuple(feature_columns()), SIMILARITY_FEATURES)


class WeightTest(unittest.TestCase):
    def test_feature_weights_sum_to_one(self) -> None:
        self.assertAlmostEqual(feature_weights().sum(), 1.0, places=9)

    def test_group_weight_is_split_evenly_within_group(self) -> None:
        """변수 개수가 늘어도 그룹 비중은 유지되어야 한다."""
        from tourgap.config import get_config

        config = get_config()
        weights = feature_weights()
        total = sum(config.similarity.group_weights.values())
        for group, columns in config.similarity.feature_groups.items():
            expected = config.similarity.group_weights[group] / total
            actual = sum(weights[column] for column in columns)
            self.assertAlmostEqual(actual, expected, places=9)

    def test_missing_feature_is_redistributed_inside_its_group(self) -> None:
        """일부 결측 때문에 다른 요인군의 실효 비중이 커지면 안 된다."""
        from tourgap.config import get_config

        config = get_config()
        available = [
            column
            for group in config.similarity.feature_groups.values()
            for column in group
            if column != "urbanization_ratio"
        ]
        weights = feature_weights(available)
        total = sum(config.similarity.group_weights.values())
        expected = config.similarity.group_weights["urban_concentration"] / total
        actual = sum(
            weights[column]
            for column in config.similarity.feature_groups["urban_concentration"]
            if column in available
        )
        self.assertAlmostEqual(actual, expected, places=9)


if __name__ == "__main__":
    unittest.main()
