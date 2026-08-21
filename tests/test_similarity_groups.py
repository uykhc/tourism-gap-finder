import unittest

from hankkeut_analysis.peer_finder.similarity_groups import (
    DOMAIN_WEIGHTS,
    SimilarityRegion,
    build_similarity_result,
)


def _region(code: str, name: str, population: float, product: str) -> SimilarityRegion:
    return SimilarityRegion(
        region_code=code,
        region_name=name,
        province_name="테스트도",
        administrative_type="city",
        values={
            "population": population,
            "population_density": population / 10,
            "area_square_km": 100,
            "forest_ratio": 0.3,
            "water_ratio": 0.1,
            "mean_elevation_m": 50,
            "gateway_access_minutes": 60,
            "rail_access_score": 0.8,
            "expressway_access_score": 0.7,
            "commercial_facility_ratio": 0.4,
            "industrial_facility_ratio": 0.2,
            "residential_facility_ratio": 0.4,
            "annual_mean_temperature_c": 12,
            "annual_precipitation_mm": 1200,
            "temperature_range_c": 25,
        },
        core_products=frozenset(product.split("|")),
    )


class SimilarityGroupsTest(unittest.TestCase):
    def test_builds_partitioned_groups_and_neighbors(self) -> None:
        regions = tuple(
            _region(*values)
            for values in (
                ("1", "가시", 10, "자연|레저"),
                ("2", "나시", 11, "자연|레저"),
                ("3", "다시", 90, "역사문화|도시상업"),
                ("4", "라시", 91, "역사문화|도시상업"),
            )
        )
        groups, neighbors, report = build_similarity_result(
            regions,
            weights=DOMAIN_WEIGHTS,
            groups_per_partition=2,
            neighbor_count=1,
        )

        self.assertEqual(len(groups), 4)
        self.assertEqual(len(neighbors), 4)
        self.assertEqual(report["partitions"]["city"]["group_count"], 2)
        nearest = {row["region_name"]: row["neighbor_region_name"] for row in neighbors}
        self.assertEqual(nearest["가시"], "나시")
        self.assertEqual(nearest["다시"], "라시")


if __name__ == "__main__":
    unittest.main()
