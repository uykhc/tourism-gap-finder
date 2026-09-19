"""Kakao DB·OpenAI 없이, 심화 대상 5개 지역 전부에서 생산자 코드와 report 조립이 실제로
도는지 지금 확인한다.

가짜인 건 카카오 공급 개수(MemorySupplyProvider)와 ai_report 산문뿐이다. peer_candidates·
performance·DataLab CSV는 전부 커밋된 실데이터를 그대로 쓴다. 지금까지 이 파이프라인은
경주시(47130) 하나에서만 실검증됐다 — 나머지 4개(해운대구·화성시·강릉시·여수시)에서 지역별
면적·peer 수·지역명 차이로 걸리는 버그가 있는지가 이 테스트의 목적이다.

이 드라이런 릴리스는 나머지 225개 지역에 대한 "축소 리포트" 경로도 함께 검증한다 — 5개
대상 외 모든 지역은 실제 `peer_candidates`/`performance`는 있지만 심화 3종은 없는, 운영과
동일한 상태이기 때문이다(기존 `test_report_assembler.py`의 준비중 테스트는 산출물이 하나도
없는 빈 디렉터리로만 검증했다 — 이 테스트는 그 간극을 메운다).

진짜 Kakao DB run과 진짜 ai_report가 도착하면 이 테스트가 검증하는 건 그대로 유효하고,
`scripts/build_api_release.py`로 실제 release를 빌드하면 된다.
"""

from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from fastapi.testclient import TestClient

from apps.api.app.main import app
from apps.api.app.schemas.reports import RegionReport
from apps.api.app.services import artifacts, regions, report as report_service
from hankkeut_calculation.ai_reports.report_schema import validate_report_payload
from hankkeut_calculation.datalab_navigation.kakao_supply import MemorySupplyProvider
from scripts.build_release_artifacts import (
    ADVANCED_REPORT_TARGETS,
    build_datalab_pressure,
    build_relative_supply,
    select_performance_peers,
)

REAL_RELEASE_ROOT = artifacts.REPOSITORY_ROOT / "data" / "artifacts" / "releases" / "baseline-202608"
RAW_ROOT = artifacts.REPOSITORY_ROOT / "data" / "raw" / "datalab_navigation"

#: 드라이런용 가짜 카카오 공급 개수. 실제 운영값이 아니다 — Kakao DB가 아직 없을 때 우리
#: 코드(생산자·리포트 조립)가 5개 심화 대상 전부에서 도는지만 확인하기 위한 값이다.
_FAKE_PLACE_COUNTS = {
    "FOOD": 120, "ACCOMMODATION": 40, "CULTURE_TOURISM": 15,
    "EXPERIENCE_TOURISM": 25, "LEISURE_SPORTS": 18, "SHOPPING": 30,
}


def _fake_ai_report(context: dict) -> dict:
    """cli.py + OpenAITourismReportGenerator가 만들 모양을 흉내 낸 최소 유효 payload.

    gap_types를 비워 둔다 — 빈 배열은 스키마상 적법하고(판정을 지어내지 않음), 오늘 밤 목적은
    "실제 OpenAI 산문"이 아니라 "이 payload가 report.py 조립을 안 깨뜨리는가"이기 때문이다.
    """
    return {
        "region_name": context["region_name"],
        "analysis_period": context["analysis_period"],
        "status": "provisional",
        "gap_types": [],
        "recommended_actions": [{
            "title": "실데이터 반영 후 재생성 필요",
            "rationale": "드라이런 검증용 리포트로, 실제 Kakao 공급 데이터가 반영되지 않았습니다.",
            "evidence_texts": ["드라이런 검증: 실제 데이터로 재생성 전까지 사용하지 않습니다."],
            "case_titles": [],
        }],
        "sources": [],
        "limitations": ["드라이런 검증용 임시 리포트이며 실제 분석 결과가 아닙니다."],
    }


class AdvancedPipelineDryRunTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not REAL_RELEASE_ROOT.is_dir():
            raise unittest.SkipTest(f"release fixture missing: {REAL_RELEASE_ROOT}")

        cls._tmp = TemporaryDirectory()
        cls.release_root = Path(cls._tmp.name)
        for name in ("peer_candidates", "performance", "portfolios", "hubs"):
            shutil.copytree(REAL_RELEASE_ROOT / name, cls.release_root / name)

        region_ids: set[str] = set()
        peers_by_target: dict[str, list[str]] = {}
        for target in ADVANCED_REPORT_TARGETS:
            peers = select_performance_peers(
                target,
                peer_artifact=cls.release_root / "peer_candidates" / f"{target}.json",
                performance_dir=cls.release_root / "performance",
                max_peers=3,
            )
            peers_by_target[target] = peers
            region_ids.add(target)
            region_ids.update(peers)
        cls.peers_by_target = peers_by_target

        supply = {
            region_id: {
                "content_type_counts": dict(_FAKE_PLACE_COUNTS),
                "is_complete": True,
                "truncated_tile_count": 0,
            }
            for region_id in region_ids
        }
        provider = MemorySupplyProvider(supply, taxonomy_version="dry-run", collection_id="tonight-dry-run")

        (cls.release_root / "datalab_navigation").mkdir()
        (cls.release_root / "relative_supply").mkdir()
        (cls.release_root / "ai_reports").mkdir()

        cls.errors: dict[str, str] = {}
        patcher = mock.patch(
            "hankkeut_calculation.datalab_navigation.kakao_supply.PostgresKakaoSupplyProvider",
            side_effect=lambda *args, **kwargs: provider,
        )
        with patcher:
            for target in ADVANCED_REPORT_TARGETS:
                try:
                    pressure = build_datalab_pressure(
                        target,
                        raw_root=RAW_ROOT,
                        database_url="dry-run",
                        kakao_run_id="dry-run",
                        peer_artifact=cls.release_root / "peer_candidates" / f"{target}.json",
                        performance_dir=cls.release_root / "performance",
                        period_start_ym="202509",
                        period_end_ym="202608",
                    )
                    (cls.release_root / "datalab_navigation" / f"{target}.json").write_text(
                        json.dumps(pressure, ensure_ascii=False), encoding="utf-8",
                    )

                    relative = build_relative_supply(
                        target,
                        peer_artifact=cls.release_root / "peer_candidates" / f"{target}.json",
                        performance_dir=cls.release_root / "performance",
                        database_url="dry-run",
                        kakao_run_id="dry-run",
                        max_peers=3,
                    )
                    (cls.release_root / "relative_supply" / f"{target}.json").write_text(
                        json.dumps(relative, ensure_ascii=False), encoding="utf-8",
                    )

                    ai_payload = _fake_ai_report(pressure["ai_report_context"])
                    validate_report_payload(ai_payload)
                    (cls.release_root / "ai_reports" / f"{target}.json").write_text(
                        json.dumps(
                            {"generator": {"model": "dry-run", "response_id": None}, "report": ai_payload},
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
                except Exception as exc:  # noqa: BLE001 — 지역별 실패를 한꺼번에 모아 보고한다.
                    cls.errors[target] = f"{type(exc).__name__}: {exc}"

        cls.artifact_root_patcher = mock.patch.object(artifacts, "ARTIFACT_ROOT", cls.release_root)
        cls.artifact_root_patcher.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.artifact_root_patcher.stop()
        cls._tmp.cleanup()
        artifacts._read_cached.cache_clear()

    def test_producers_run_for_every_advanced_target(self):
        self.assertEqual(self.errors, {}, "생산자 단계에서 실패한 지역이 있습니다")

    def test_all_five_advanced_targets_produce_a_schema_valid_full_report(self):
        for target in ADVANCED_REPORT_TARGETS:
            if target in self.errors:
                continue  # 위 테스트가 이미 실패를 보고한다.
            with self.subTest(region_id=target):
                payload = report_service.build_region_report(target)
                report = RegionReport.model_validate(payload)
                self.assertNotEqual(report.summary.diagnosis_status.value, "INSUFFICIENT_DATA")
                self.assertTrue(report.recommended_actions)

    def _non_advanced_sample(self) -> list[str]:
        """5개 대상 제외, 실제 peer_candidates/performance는 있고 심화 3종만 없는 지역 표본.

        대상의 peer로 등장하는 3개 지역(대상 본인은 아니지만 심화 산출물도 없음), 포트폴리오가
        없는 4개 인천 지역(PROVIDER_UNAVAILABLE_PORTFOLIOS — report.py는 portfolio를 안 써서
        영향이 없어야 함), 그리고 전국에 고르게 퍼진 5개를 더한다.
        """
        # 대상의 peer로 뽑힌 지역이 동시에 다른 대상의 peer이자 그 자신도 대상인 경우가
        # 있다(예: 47130 경주시·51150 강릉시는 12130 여수시의 peer이면서 자기 자신도 심화
        # 대상). 그런 지역은 실제로 full report를 받는 게 맞는 동작이므로 표본에서 뺀다.
        peers = {p for peers in self.peers_by_target.values() for p in peers} - set(ADVANCED_REPORT_TARGETS)
        provider_unavailable = set(artifacts.PROVIDER_UNAVAILABLE_PORTFOLIOS)
        all_ids = regions.all_region_ids()
        excluded = set(ADVANCED_REPORT_TARGETS) | peers | provider_unavailable
        spread = [all_ids[i] for i in range(0, len(all_ids), len(all_ids) // 5) if all_ids[i] not in excluded][:5]
        return sorted(peers | provider_unavailable | set(spread))

    def test_non_advanced_regions_get_a_schema_valid_reduced_report(self):
        for region_id in self._non_advanced_sample():
            with self.subTest(region_id=region_id):
                payload = report_service.build_region_report(region_id)
                report = RegionReport.model_validate(payload)
                self.assertEqual(report.summary.diagnosis_status.value, "INSUFFICIENT_DATA")
                self.assertIsNone(report.summary.primary_gap_type)
                self.assertEqual(report.summary.key_metrics, [])
                self.assertEqual(report.recommended_actions, [])
                self.assertEqual(report.report_status.value, "PROVISIONAL")

    def test_non_advanced_regions_serve_a_200_report_and_a_409_gaps_over_http(self):
        client = TestClient(app)
        for region_id in self._non_advanced_sample()[:4]:
            with self.subTest(region_id=region_id):
                report_response = client.get(f"/regions/{region_id}/report")
                self.assertEqual(report_response.status_code, 200)
                self.assertEqual(
                    report_response.json()["summary"]["diagnosis_status"], "INSUFFICIENT_DATA"
                )
                gaps_response = client.get(f"/regions/{region_id}/gaps")
                self.assertEqual(gaps_response.status_code, 409)
                self.assertEqual(gaps_response.json()["detail"]["code"], "REPORT_NOT_READY")
