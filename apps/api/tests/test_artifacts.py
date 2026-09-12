"""산출물 리더 회귀 테스트.

각 테스트는 실제로 있었던 결함 하나에 대응한다. 산출물은 사람이 만든 파일을
읽는 경로라, 생산자와 리더가 어긋나면 값이 조용히 바뀌어 나간다.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest import mock

from fastapi import HTTPException

from apps.api.app.schemas.common import ProvenanceRecord
from apps.api.app.services import artifacts


def _peer_candidates(region_id: str, region_name: str, province: str = "경상북도", **extra: Any) -> dict[str, Any]:
    return {
        "result_version": "2026-09-13",
        "target": {
            "region_id": region_id, "province_name": province,
            "region_name": region_name, "administrative_type": "시",
        },
        "selection_type": "structural_similarity_candidates",
        "warning": "구조적 유사 후보입니다.",
        "peers": [{
            "rank": 1, "region_id": "47110", "province_name": "경상북도",
            "region_name": "포항시", "administrative_type": "시",
            "similarity": 0.728, "distance": 0.3174,
            "feature_weight_used": 1.0, "missing_feature_count": 0,
        }],
        "provenance": [],
        **extra,
    }


class ArtifactRootTestCase(unittest.TestCase):
    """`ANALYSIS_ARTIFACT_ROOT`를 임시 디렉터리로 바꿔 쓰는 공통 준비."""

    def setUp(self) -> None:
        self._directory = TemporaryDirectory()
        self.root = Path(self._directory.name)
        patcher = mock.patch.object(artifacts, "ARTIFACT_ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._directory.cleanup)

    def write(self, directory: str, name: str, payload: dict[str, Any]) -> Path:
        path = self.root / directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path


class ProvenanceMappingTest(ArtifactRootTestCase):
    def test_a_mock_source_is_never_reported_as_a_static_reference(self):
        # 생산자는 '모의'가 아니라 'MOCK'을 쓴다. 매핑이 어긋나면 모의 데이터가
        # 정적 참조로 보고되어 P4 출처 표기 약속이 깨진다.
        self.write("peer_candidates", "47130.json", _peer_candidates(
            "47130", "경주시",
            provenance=[{"소스": "표본", "신뢰도": "MOCK", "엔드포인트/출처": "x",
                         "기준시점": "y", "행수": 3, "비고": ""}],
        ))
        result = artifacts.peers("47130", k=5, min_similarity=0.0)
        self.assertEqual(result["provenance"][0]["source_type"], "mock")

    def test_every_producer_badge_maps_to_its_own_source_type(self):
        badges = [("실데이터", "real"), ("proxy", "proxy"), ("정적참조", "static_reference"), ("MOCK", "mock")]
        self.write("peer_candidates", "47130.json", _peer_candidates(
            "47130", "경주시",
            provenance=[
                {"소스": badge, "신뢰도": badge, "엔드포인트/출처": "", "기준시점": "", "행수": 1, "비고": ""}
                for badge, _ in badges
            ],
        ))
        result = artifacts.peers("47130", k=5, min_similarity=0.0)
        self.assertEqual(
            [row["source_type"] for row in result["provenance"]],
            [expected for _, expected in badges],
        )

    def test_an_unknown_row_count_becomes_null_not_zero(self):
        # 생산자는 행수를 모르면 빈 문자열을 쓴다. 그대로 넘기면 검증 오류로
        # 500이 나고, 0으로 바꾸면 '자료 없음'이 '0건'이 된다.
        self.write("peer_candidates", "47130.json", _peer_candidates(
            "47130", "경주시",
            provenance=[{"소스": "표본", "신뢰도": "실데이터", "엔드포인트/출처": "",
                         "기준시점": "", "행수": "", "비고": ""}],
        ))
        row = artifacts.peers("47130", k=5, min_similarity=0.0)["provenance"][0]
        self.assertIsNone(row["row_count"])
        self.assertIsNone(ProvenanceRecord.model_validate(row).row_count)


class RegionJoinTest(ArtifactRootTestCase):
    def test_same_named_regions_each_resolve_to_their_own_artifact(self):
        # 중구는 5곳이다. 이름으로 조인하면 부산 중구 요청에 서울 중구 산출물이
        # 응답될 수 있다.
        self.write("peer_candidates", "a.json", _peer_candidates("26110", "중구", "부산광역시"))
        self.write("peer_candidates", "b.json", _peer_candidates("11140", "중구", "서울특별시"))
        for region_id in ("26110", "11140"):
            payload = artifacts.load_peer_candidates(region_id)
            self.assertIsNotNone(payload)
            self.assertEqual(payload["target"]["region_id"], region_id)

    def test_an_artifact_naming_another_region_is_rejected(self):
        self.write("peer_candidates", "47130.json", _peer_candidates("47110", "포항시"))
        self.assertIsNone(artifacts.load_peer_candidates("47130"))

    def test_an_unresolvable_peer_name_is_dropped_instead_of_becoming_the_target(self):
        # 예전 구현은 이름을 못 찾으면 대상 지역 자신을 넣었다. 그러면 자기
        # 자신과 비교한 값이 비교 기준 목록에 섞여 들어간다.
        resolved, unresolved = artifacts.resolve_peer_regions(
            ["포항시", "중구"], candidate_region_ids={"47110"}
        )
        self.assertEqual([row["region_id"] for row in resolved], ["47110"])
        self.assertEqual(unresolved, ["중구"])
        self.assertNotIn("47130", [row["region_id"] for row in resolved])


class MalformedArtifactTest(ArtifactRootTestCase):
    def test_a_missing_target_report_fails_loudly(self):
        self.write("datalab_navigation", "47130.json", {"region_name": "경주시"})
        with self.assertRaises(HTTPException) as caught:
            artifacts.require_target_report(artifacts.load_supply_pressure("47130"))
        self.assertEqual(caught.exception.status_code, 502)

    def test_unreadable_json_is_a_service_error_not_a_crash(self):
        path = self.root / "peer_candidates" / "broken.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{ not json", encoding="utf-8")
        with self.assertRaises(HTTPException) as caught:
            artifacts.load_peer_candidates("47130")
        self.assertEqual(caught.exception.status_code, 503)

    def test_a_missing_directory_is_simply_no_artifact(self):
        self.assertIsNone(artifacts.load_relative_supply("47130"))
        self.assertIsNone(artifacts.load_ai_report("47130"))


if __name__ == "__main__":
    unittest.main()
