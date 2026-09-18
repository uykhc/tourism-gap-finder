"""개발용 샘플 분석 산출물을 만든다 (경주시).

API의 `/gaps`·`/report`는 분석 산출물 JSON을 읽는다. 프론트가 화면을 붙일 수
있도록 경주시 개발용 산출물을 만들어 커밋한다. `/peers`는 이 스크립트가 아닌
`scripts/build_peer_artifacts.py`가 전국 실제 구조 변수 스냅숏으로 생성한다.

직접 JSON을 손으로 쓰지 않고 **실제 생산자 함수를 호출한다.** 그래야 샘플의
모양이 생산자 출력과 어긋날 수 없고, 리더가 실제 산출물에서 깨지는 일을
미리 잡을 수 있다. AI 리포트만은 LLM 출력이라 직접 쓰고, 생산자와 같은
검증기(`validate_report_payload`)로 확인한다.

숫자는 화면 개발용 표본이다. 각 산출물의 한계 목록에 그 사실을 적는다.
장소 수는 `apps/api/app/examples.py`가 쓰던 표본값에서 가져왔고, 비교 지역의
장소 수는 그 표본의 100㎢당 밀도와 실제 면적에서 되돌려 계산했다.

실행 (레포 루트에서):
    PYTHONPATH=data/analysis/calculation/src python3 scripts/build_sample_artifacts.py
"""

from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path
from typing import Any

from hankkeut_calculation.ai_reports.report_schema import validate_report_payload
from hankkeut_calculation.datalab_navigation.navigation_demand import (
    build_supply_pressure_report,
    import_navigation_demand_csv,
    load_navigation_demand_taxonomy,
)
from hankkeut_calculation.datalab_navigation.peer_comparison import (
    build_peer_supply_pressure_comparison,
)
from hankkeut_calculation.datalab_navigation.relative_supply import (
    build_relative_supply_report,
)

OUTPUT_ROOT = Path("apps/api/app/data/artifacts")
TAXONOMY_PATH = Path("config/datalab/navigation_destination_type_taxonomy.json")

SAMPLE_NOTICE = (
    "화면 개발용 샘플 산출물입니다. 실제 분석 결과가 아니며 정책 판단에 쓰지 않습니다."
)

TARGET = {"region_id": "47130", "province_name": "경상북도", "region_name": "경주시", "administrative_type": "시"}
BENCHMARKS = [
    {"region_id": "47110", "province_name": "경상북도", "region_name": "포항시", "administrative_type": "시"},
    {"region_id": "44210", "province_name": "충청남도", "region_name": "서산시", "administrative_type": "시"},
]

AREA_KM2 = {"경주시": 1324.39, "포항시": 1130.06, "서산시": 741.34}

#: 경주시 유형별 장소 수 (표본).
TARGET_PLACE_COUNTS = {
    "FOOD": 553,
    "ACCOMMODATION": 264,
    "CULTURE_TOURISM": 118,
    "EXPERIENCE_TOURISM": 87,
    "LEISURE_SPORTS": 96,
    "SHOPPING": 143,
}

#: 비교 지역의 100㎢당 공급밀도 (표본). 장소 수는 면적에서 되돌려 계산한다.
BENCHMARK_DENSITIES = {
    "포항시": {
        "FOOD": 46.17, "ACCOMMODATION": 13.93, "CULTURE_TOURISM": 6.48,
        "EXPERIENCE_TOURISM": 9.44, "LEISURE_SPORTS": 7.13, "SHOPPING": 12.21,
    },
    "서산시": {
        "FOOD": 41.33, "ACCOMMODATION": 15.60, "CULTURE_TOURISM": 5.97,
        "EXPERIENCE_TOURISM": 8.12, "LEISURE_SPORTS": 7.55, "SHOPPING": 9.56,
    },
}

#: 경주시 12개월 내비게이션 목적지 검색량 (표본). 데이터랩 원본 유형 기준이라
#: 문화관광·자연관광·역사관광이 따로 있고, 세 유형 모두 CULTURE_TOURISM으로 모인다.
TARGET_SEARCH_COUNTS = {
    "음식": 481226,
    "숙박": 402118,
    "문화관광": 74932,
    "자연관광": 21000,
    "역사관광": 13000,
    "체험관광": 184230,
    "레저스포츠": 96204,
    "쇼핑": 178440,
    "기타관광": 52310,
}

#: 비교 지역의 유형별 수요 구성 차이 (표본 가정).
#:
#: 비교 지역의 검색량을 대상 지역 값에 유형과 무관한 배수만 곱해서 만들면
#: `장소당 검색량` 비율이 `비교지역 장소 수 ÷ 대상 장소 수`로 약분되어, 공급압력
#: 신호가 공급밀도 신호와 수학적으로 같아진다. 두 신호를 따로 보는 의미가
#: 없어지므로, 지역마다 수요 구성이 다르다는 가정을 유형별 배수로 명시해 둔다.
#: 실제 산출물에서는 데이터랩 원본이 이 구성을 직접 제공한다.
BENCHMARK_DEMAND_MIX = {
    "포항시": {"음식": 1.30, "레저스포츠": 1.05, "쇼핑": 1.20},
    "서산시": {"음식": 1.30, "레저스포츠": 1.20},
}

ANALYSIS_MONTHS = [
    "202508", "202509", "202510", "202511", "202512", "202601",
    "202602", "202603", "202604", "202605", "202606", "202607",
]

#: 유사 지역 — `data/analysis/similarity/results/경주시_47130_20260817/peers.csv` 실제 값.
PEER_ROWS = [
    (1, "47110", "경상북도", "포항시", "시", 0.3174, 0.7280),
    (2, "44210", "충청남도", "서산시", "시", 0.3244, 0.7230),
    (3, "44270", "충청남도", "당진시", "시", 0.3404, 0.7115),
    (4, "52130", "전북특별자치도", "군산시", "시", 0.3866, 0.6794),
    (5, "12150", "전라남도", "순천시", "시", 0.3869, 0.6792),
]

PROVENANCE = [
    {
        "소스": "지역 마스터", "신뢰도": "실데이터",
        "엔드포인트/출처": "KorService2 /areaBasedList2 lDongRegnCd·lDongSignguCd",
        "기준시점": "2026-08-17 수집분", "행수": 230,
        "비고": "KTO 실제 관광자원 lDong 5자리 코드 기준. 일반구는 모 시로 합산",
    },
    {
        "소스": "인구·면적·사업체", "신뢰도": "실데이터",
        "엔드포인트/출처": "SGIS OpenAPI3 population.json · hadmarea.geojson · company.json",
        "기준시점": "인구 2020 총조사, 사업체 2024", "행수": 230,
        "비고": "면적은 경계 GeoJSON에 shoelace 공식 적용",
    },
    {
        "소스": "기후평년값", "신뢰도": "proxy",
        "엔드포인트/출처": "data/processed/kma_climate_normals_by_region.csv",
        "기준시점": "1991~2020 기상청 기후평년값", "행수": 230,
        "비고": "가까운 관측소 3개 역거리 제곱 보간",
    },
    {
        "소스": "해안·도서 여부", "신뢰도": "정적참조",
        "엔드포인트/출처": "data/reference/coastal_island.csv",
        "기준시점": "2026년 행정구역 기준", "행수": 76,
        "비고": "원천 여건. 직접 정리한 표",
    },
]


def _kakao_region(region_name: str, counts: dict[str, int]) -> dict[str, Any]:
    """카카오 수집 결과 모양. relative_supply가 이 모양을 입력으로 받는다."""
    return {
        "region_name": region_name,
        "taxonomy_version": "2026-09-13",
        "content_type_counts": counts,
        "truncated_tile_count": 0,
        "is_complete": True,
    }


def _benchmark_counts(region_name: str) -> dict[str, int]:
    area = AREA_KM2[region_name]
    return {
        content_type: max(1, round(density * area / 100))
        for content_type, density in BENCHMARK_DENSITIES[region_name].items()
    }


def _monthly_split(annual: int) -> list[int]:
    """연간 값을 12개월로 나눈다. 합계는 원래 값과 정확히 같아야 한다."""
    base, remainder = divmod(annual, len(ANALYSIS_MONTHS))
    values = [base] * len(ANALYSIS_MONTHS)
    values[-1] += remainder
    return values


def _write_navigation_csv(path: Path, annual_by_source_type: dict[str, int]) -> None:
    """데이터랩 월별 CSV. 월 합계가 '전체' 행과 정확히 맞아야 통과한다."""
    monthly = {source: _monthly_split(value) for source, value in annual_by_source_type.items()}
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["기준연월", "목적지 유형", "목적지 검색량"])
        for index, month in enumerate(ANALYSIS_MONTHS):
            total = sum(values[index] for values in monthly.values())
            writer.writerow([month, "전체", total])
            for source_type, values in monthly.items():
                writer.writerow([month, source_type, values[index]])


def _supply_pressure_report(
    directory: Path, region_name: str, counts: dict[str, int], searches: dict[str, int]
) -> dict[str, Any]:
    taxonomy = load_navigation_demand_taxonomy(TAXONOMY_PATH)
    csv_path = directory / f"{region_name}_navigation.csv"
    _write_navigation_csv(csv_path, searches)
    kakao_path = directory / f"{region_name}_kakao.json"
    kakao_path.write_text(
        json.dumps({"regions": [_kakao_region(region_name, counts)]}, ensure_ascii=False),
        encoding="utf-8",
    )
    demand = import_navigation_demand_csv(csv_path, region_name=region_name, taxonomy=taxonomy)
    return build_supply_pressure_report(
        demand, taxonomy=taxonomy, kakao_collection_path=kakao_path, month_count=12,
    )


def build_peer_candidates() -> dict[str, Any]:
    """유사도 패키지 `main._write_result`와 같은 모양."""
    return {
        "result_version": "2026-09-13",
        "target": TARGET,
        "selection_type": "structural_similarity_candidates",
        "warning": (
            "이 목록은 구조적으로 유사한 후보입니다. "
            "관광 성과 검증 전에는 '우수 Peer'로 해석하지 않습니다."
        ),
        "peers": [
            {
                "rank": rank, "region_id": region_id, "province_name": province,
                "region_name": name, "administrative_type": admin_type,
                "similarity": similarity, "distance": distance,
                "feature_weight_used": 1.0, "missing_feature_count": 0,
            }
            for rank, region_id, province, name, admin_type, distance, similarity in PEER_ROWS
        ],
        "provenance": PROVENANCE,
    }


def build_relative_supply() -> dict[str, Any]:
    report = build_relative_supply_report(
        target_region=_kakao_region("경주시", TARGET_PLACE_COUNTS),
        peer_regions=[
            _kakao_region(item["region_name"], _benchmark_counts(item["region_name"]))
            for item in BENCHMARKS
        ],
        area_km2_by_region=AREA_KM2,
    )
    report["limitations"] = [*report["limitations"], SAMPLE_NOTICE]
    return report


def build_supply_pressure(directory: Path) -> dict[str, Any]:
    target_report = _supply_pressure_report(
        directory, "경주시", TARGET_PLACE_COUNTS, TARGET_SEARCH_COUNTS
    )
    target_total = sum(TARGET_PLACE_COUNTS.values())
    peer_reports = []
    for item in BENCHMARKS:
        name = item["region_name"]
        counts = _benchmark_counts(name)
        # 비교 지역의 검색량은 장소 수 비율로 규모를 맞춘 뒤, 유형별 수요 구성
        # 차이를 곱한 표본값이다. 근거가 되는 원본이 없으므로 한계 목록에 적는다.
        scale = sum(counts.values()) / target_total
        mix = BENCHMARK_DEMAND_MIX.get(name, {})
        searches = {
            source: round(value * scale * mix.get(source, 1.0))
            for source, value in TARGET_SEARCH_COUNTS.items()
        }
        peer_reports.append(_supply_pressure_report(directory, name, counts, searches))
    comparison = build_peer_supply_pressure_comparison(
        target_report,
        peer_reports=peer_reports,
        peer_regions=[item["region_name"] for item in BENCHMARKS],
    )
    comparison["data_quality"]["warnings"] = [
        *comparison["data_quality"]["warnings"],
        "비교 지역의 검색량은 장소 수 비율로 규모를 맞추고 유형별 수요 구성 차이를 가정한 표본값입니다.",
        SAMPLE_NOTICE,
    ]
    return comparison


def build_ai_report() -> dict[str, Any]:
    """LLM 출력 자리. 생산자와 같은 검증기를 통과해야 한다."""
    report = {
        "region_name": "경주시",
        "analysis_period": f"{ANALYSIS_MONTHS[0]}~{ANALYSIS_MONTHS[-1]}",
        "status": "provisional",
        "gap_types": [
            {
                "content_type": "EXPERIENCE_TOURISM",
                "judgement": (
                    "비교한 두 지역 모두에서 체험관광 등록 공급의 구성비와 면적당 밀도가 낮게 "
                    "나타납니다. 동시에 등록 장소 1곳당 목적지 검색량도 두 지역보다 높아, "
                    "추가 공급·수요 검증 필요성이 가장 일관되게 관찰되는 유형입니다."
                ),
                "quantitative_evidence": [
                    {
                        "metric": "체험관광 등록 장소 1곳당 목적지 검색량",
                        "target_value": 2117.5862,
                        "comparison": "비교 지역 두 곳보다 높음",
                    }
                ],
                "peer_cases": [
                    {
                        "title": "포항 스페이스워크",
                        "peer_region": "포항시",
                        "summary": (
                            "포스코가 환호공원에 총 길이 333m의 체험형 조형물을 조성해 2021년 "
                            "포항시에 기부한 사례입니다. 기존 공원과 해안 전망이라는 장소 자원에 "
                            "직접 걷고 오르는 체험 요소를 더했습니다."
                        ),
                        "source_ids": ["source-1"],
                    },
                    {
                        "title": "서산 해미읍성 역사체험축제",
                        "peer_region": "서산시",
                        "summary": (
                            "해미읍성이라는 단일 역사공간에서 역사·병영 체험형 축제를 반복 "
                            "운영해 온 사례입니다. 상설 시설을 새로 만들지 않고 장소의 경험을 "
                            "콘텐츠로 구성했습니다."
                        ),
                        "source_ids": ["source-2"],
                    },
                ],
                "applicability_insight": (
                    "경주는 역사문화자원과 주요 관광거점이 이미 형성돼 있어 신규 시설을 만드는 "
                    "방식뿐 아니라 기존 관람 동선에 참여형·예약형 프로그램을 결합하는 방식을 "
                    "먼저 검토할 수 있습니다. 다만 현재 지표만으로는 어떤 세부 체험이 부족한지 "
                    "알 수 없어 세부 유형과 관광권역별 공급을 추가로 확인해야 합니다."
                ),
            },
            {
                "content_type": "FOOD",
                "judgement": (
                    "음식은 구성비가 두 비교 지역보다 낮지만, 등록 장소 1곳당 검색량이 높은 "
                    "쪽은 한 지역에 대해서만 관찰됩니다. 신호의 방향이 일치하지 않습니다."
                ),
                "quantitative_evidence": [
                    {
                        "metric": "음식 등록 장소 1곳당 목적지 검색량",
                        "target_value": 870.2098,
                        "comparison": "비교 지역 한 곳보다 높고 다른 한 곳보다 낮음",
                    }
                ],
                "peer_cases": [],
                "applicability_insight": (
                    "음식 장소 수는 이미 6개 유형 중 가장 많아, 공급을 늘리는 방향보다 관광 "
                    "동선과 연결되는지를 먼저 확인하는 편이 적절합니다."
                ),
            },
        ],
        "sources": [
            {
                "source_id": "source-1",
                "title": "스페이스워크 조성·기부 관련 공식 자료",
                "publisher": "포스코그룹 뉴스룸",
                "url": "https://newsroom.posco.com/",
                "published_at": "2021-11-18 외",
            },
            {
                "source_id": "source-2",
                "title": "서산 해미읍성축제 추진 현황 자료",
                "publisher": "서산시",
                "url": "https://www.seosan.go.kr/",
                "published_at": "2024",
            },
        ],
        "limitations": [
            "공급은 카카오맵에 해당 유형으로 등록된 장소 수를 이용한 대리변수이며, 실제 "
            "프로그램 수·운영시간·예약 가능량·수용인원을 직접 측정하지 않습니다.",
            "목적지 검색량은 실제 방문이나 미충족 수요와 같지 않으며, 반복 검색과 지역주민 "
            "이용이 포함될 수 있습니다.",
            "비교 지역은 구조적 유사 후보이며 관광 성과가 검증된 우수 지역이 아닙니다.",
            SAMPLE_NOTICE,
        ],
    }
    validate_report_payload(report)
    return {"generator": {"model": "sample", "response_id": None}, "report": report}


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        outputs = {
            "relative_supply/47130_relative_supply_gap_detailed.json": build_relative_supply(),
            "datalab_navigation/47130_individual_supply_pressure_detailed.json": build_supply_pressure(Path(directory)),
            "ai_reports/47130_detailed_gap_report_with_cases.json": build_ai_report(),
        }
    for relative_path, payload in outputs.items():
        path = OUTPUT_ROOT / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"saved {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
