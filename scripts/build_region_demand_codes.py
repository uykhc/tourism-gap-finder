"""region_id ↔ 관광 수요지수 API의 법정동 코드 표를 만든다.

관광 수요지수 API(`AreaTarResDemService`·`AreaTarDemDsService`)는 `areaCd`(법정동
시도 2자리)와 `signguCd`(법정동 5자리)로 조회한다. TourAPI의 `area_code`/
`sigungu_code`와는 **다른 코드 체계**다. 같은 표를 두 API에 쓰면 조회가 조용히
실패하므로 표를 따로 둔다. TourAPI용 표는 `build_region_code_map.py`가 만든다.

이 API는 일반구가 있는 시를 **구 단위로** 공표한다. 수원시(41110)는 없고
장안구·권선구·팔달구·영통구(41111·41113·41115·41117)가 있다. 그래서 한 지역이
여러 코드에 대응하며, `build_regional_tourism_scores`가 그 코드들의 값을
평균한다.

일반구를 묶는 규칙은 API 응답에서 그대로 도출된다 — 구 코드는 모 시 코드와 앞
4자리가 같다. 실측으로 확인했고(부모를 못 찾은 코드 0개),
`ACTIVE_CITY_SIGUNGU_CODES` 수작업 표와 28개 중 27개가 일치한다. 남은 1개는
이 규칙이 틀린 것이 아니라 수작업 표가 낡은 것이다(화성시 일반구 신설).

**시도 코드는 우리 표와 API가 다르다.** 우리 표는 2026년 개편을 반영해 광주와
전남을 `12`로 합쳤지만, API는 여전히 `29`(광주)·`46`(전남)로 나눠 공표한다.
이 경우 뒤 3자리가 보존된다고 가정하면 안 된다 — 장흥군(우리 `12770`)의 뒤
3자리를 전남에 붙이면 `46770`이 나오는데 그건 고흥군이다. 그래서 개편으로
코드가 바뀐 지역은 **(시군구명, 후보 시도) 조합으로 맞추고, 후보가 정확히
하나일 때만** 채택한다. 둘 이상이면 추측하지 않고 비워 둔다.

원재료가 API 응답이라 실행에 키가 필요하다. 결과 CSV만 커밋하고 API는 그것만
읽는다.

실행 (레포 루트에서):
    python3 scripts/build_region_demand_codes.py
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, "data/analysis/similarity/src")

from hankkeut_calculation.tourism_data.config import resolve_visitor_service_key
from hankkeut_calculation.tourism_data.tourism_demand_api import (
    TourismDemandApiClient,
    previous_months,
)
from hankkeut_similarity.config import load_project_environment

REGIONS_CSV = Path("apps/api/app/data/regions.csv")
OUTPUT_CSV = Path("apps/api/app/data/region_demand_codes.csv")

#: 네 지표가 모두 있는 월을 찾을 때 거슬러 볼 개월 수. 최근 1~2개월은 공표
#: 지연으로 비어 있는 것이 정상이다.
LOOKBACK_MONTHS = 24

FIELDNAMES = ("region_id", "province_name", "region_name", "demand_codes", "note")

METRICS = ("resource_service", "resource_culture", "intensity_stay", "intensity_spend")

#: API가 쓰는 법정동 시도 코드 후보. 우리 표의 시도 코드와 다른 경우만 적는다.
#: 2026년 개편으로 광주(29)와 전남(46)이 우리 표에서 12로 합쳐졌다.
API_AREA_CANDIDATES = {"12": ("29", "46")}

#: 개편으로 신설돼 API가 아직 공표하지 않는 지역. 옛 자치구 코드를 빌려 쓰면
#: 서로 다른 지역에 같은 수요값이 붙으므로 비워 두고 사유를 남긴다.
KNOWN_UNPUBLISHED = {
    "28125": "2026년 개편(구 중구+동구) 신설. 수요지수 API 미공표",
    "28155": "2026년 개편(구 중구 영종도부) 신설. 수요지수 API 미공표",
    "28275": "2026년 개편(구 서구 분할) 신설. 수요지수 API 미공표",
    "28290": "2026년 개편(구 서구 분할) 신설. 수요지수 API 미공표",
}


def published_codes(
    client: TourismDemandApiClient, area_code: str
) -> tuple[str, dict[str, str]]:
    """해당 시도에서 네 지표가 모두 있는 최근 월과 `코드 → 시군구명`.

    한 지표에만 있는 코드는 점수를 낼 수 없으므로 네 지표의 교집합만 쓴다.
    """
    for base_ym in previous_months(maximum_count=LOOKBACK_MONTHS):
        scores = client.fetch_all_scores(base_ym=base_ym, area_code=area_code)
        common = set.intersection(*(set(scores[metric]) for metric in METRICS))
        if common:
            names = {code: scores["resource_service"][code].sigungu_name for code in common}
            return base_ym, names
    return "", {}


def _children_of(code: str, names: dict[str, str]) -> list[str]:
    """일반구 코드. 모 시 코드와 앞 4자리가 같다."""
    return sorted(item for item in names if item[:4] == code[:4] and item != code)


def _resolve(
    region_id: str,
    region_name: str,
    candidates: tuple[str, ...],
    names_by_area: dict[str, dict[str, str]],
) -> tuple[list[str], str]:
    """지역 하나에 대응하는 수요지수 코드 목록과 근거 메모."""
    # 1. 우리 코드가 그대로 공표되는 경우.
    for area in candidates:
        names = names_by_area.get(area, {})
        if region_id in names:
            return [region_id], ""
    # 2. 일반구 단위로만 공표되는 시. 우리 코드 기준으로 자식을 찾는다.
    for area in candidates:
        names = names_by_area.get(area, {})
        children = _children_of(region_id, names)
        if children:
            return children, "일반구 단위 공표. 구 코드 평균을 사용"
    # 3. 개편으로 코드가 바뀐 지역. 뒤 3자리 보존을 가정하면 다른 지역에
    #    붙으므로(장흥군 12770 → 46770은 고흥군), 이름으로만 맞춘다.
    matches = [
        (area, code)
        for area in candidates
        for code, name in names_by_area.get(area, {}).items()
        if name == region_name
    ]
    if len(matches) == 1:
        area, code = matches[0]
        children = _children_of(code, names_by_area[area])
        if children:
            return children, f"개편 전 코드 {code}의 일반구 평균을 사용"
        return [code], f"개편으로 코드가 바뀜. 개편 전 코드 {code}"
    if len(matches) > 1:
        found = ", ".join(code for _, code in matches)
        return [], f"동명 후보가 여럿이라 확정 불가: {found}"
    return [], ""


def main() -> int:
    load_project_environment()
    service_key = resolve_visitor_service_key() or os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip()
    if not service_key:
        raise SystemExit(
            "관광 수요지수 API 키가 필요합니다. VISITOR_API_SERVICE_KEY 또는 "
            "TOUR_API_SERVICE_KEY를 설정하세요."
        )

    regions = list(csv.DictReader(REGIONS_CSV.read_text(encoding="utf-8-sig").splitlines()))
    client = TourismDemandApiClient(service_key, timeout_seconds=45, page_size=200)

    # 우리 표의 시도 코드와, 개편 전 코드를 쓰는 시도 후보를 모두 조회한다.
    wanted_areas = set()
    for row in regions:
        prefix = row["region_id"][:2]
        wanted_areas.update(API_AREA_CANDIDATES.get(prefix, (prefix,)))

    names_by_area: dict[str, dict[str, str]] = {}
    for area_code in sorted(wanted_areas):
        month, names = published_codes(client, area_code)
        if not names:
            print(f"  시도 {area_code}: 공표 없음")
            continue
        names_by_area[area_code] = names
        print(f"  시도 {area_code}: {month} 기준 {len(names)}개 코드")

    rows: list[dict[str, str]] = []
    unmapped: list[str] = []
    for region in regions:
        region_id = region["region_id"].strip()
        region_name = region["region_name"].strip()
        candidates = API_AREA_CANDIDATES.get(region_id[:2], (region_id[:2],))
        demand_codes, note = _resolve(region_id, region_name, candidates, names_by_area)
        if not demand_codes:
            note = note or KNOWN_UNPUBLISHED.get(region_id) or "관광 수요지수 API가 이 지역을 공표하지 않음"
            unmapped.append(f"{region_id} {region_name} — {note}")
        rows.append({
            "region_id": region_id,
            "province_name": region["province_name"].strip(),
            "region_name": region_name,
            "demand_codes": ";".join(demand_codes),
            "note": note,
        })

    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    mapped = len(rows) - len(unmapped)
    print(f"\nsaved {OUTPUT_CSV} ({len(rows)} rows)")
    print(f"코드 있음 {mapped} / 코드 없음 {len(unmapped)}")
    for item in unmapped:
        print(f"   - {item}")
    _compare_with_hand_table(rows)
    return 0


def _compare_with_hand_table(rows: list[dict[str, str]]) -> None:
    """경기 28개 시 수작업 표와 대조해 차이를 눈에 보이게 남긴다."""
    try:
        from hankkeut_evaluation.visitor_portfolio_benchmark import ACTIVE_CITY_SIGUNGU_CODES
    except ImportError:
        return
    derived = {row["region_name"]: row["demand_codes"].split(";") for row in rows}
    agree, diffs = 0, []
    for name, hand in ACTIVE_CITY_SIGUNGU_CODES.items():
        mine = derived.get(name)
        if mine is None:
            continue
        if set(mine) == set(hand):
            agree += 1
        else:
            diffs.append((name, tuple(mine), tuple(sorted(hand))))
    print(f"\nACTIVE_CITY_SIGUNGU_CODES 대조: 일치 {agree} / 차이 {len(diffs)}")
    for name, mine, hand in diffs:
        print(f"   {name}: API={mine} 수작업표={hand}")
    if diffs:
        print("   → 수작업 표가 낡았는지 확인하세요. API 응답이 기준입니다.")


if __name__ == "__main__":
    raise SystemExit(main())
