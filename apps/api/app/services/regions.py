"""전국 시군구 목록.

조인 키는 법정동 시군구 코드 5자리(`region_id`)다. 지역명으로 조인하면
중구가 5곳, 서구·남구·북구가 4곳이라 값이 섞인다. 그래서 이름으로 지역을
찾는 `resolve_by_name`은 후보가 둘 이상이면 값을 만들지 않고 `None`을
돌려준다.

표는 `data/regions.csv`에 있고 `contracts/hankkeut_contracts/data/regions.csv`
사본이다. 컬럼명(`admin_type`)까지 원본과 같게 두어 diff로 비교할 수 있게 했고,
응답 스키마가 쓰는 `administrative_type`으로는 읽을 때 바꾼다.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REGIONS_CSV_PATH = _DATA_DIR / "regions.csv"

#: `scripts/build_region_code_map.py`가 만든 표. TourAPI(관광자원·중심관광지)는
#: 자체 area/sigungu 코드로 조회하지만 계약에는 region_id만 오간다.
REGION_CODE_MAP_CSV_PATH = _DATA_DIR / "region_code_map.csv"

#: `scripts/build_region_demand_codes.py`가 만든 표. 관광 수요지수 API는
#: **법정동 코드**로 조회한다. TourAPI 코드와 다른 체계이므로 표를 따로 둔다.
#: 일반구가 있는 시는 구 코드 여러 개에 대응한다.
REGION_DEMAND_CODES_CSV_PATH = _DATA_DIR / "region_demand_codes.csv"

#: CSV가 쓰는 컬럼명 → 응답 스키마가 쓰는 필드명.
_COLUMN_RENAMES = {"admin_type": "administrative_type"}

_REQUIRED_COLUMNS = ("region_id", "province_name", "region_name", "admin_type")

#: `schemas.common.AdministrativeType`와 같은 값이어야 한다. 여기서 한 번 더
#: 확인해, 표가 잘못되면 404가 아니라 로드 시점에 크게 실패하게 한다.
_ALLOWED_ADMINISTRATIVE_TYPES = frozenset({"시", "군", "자치구", "특별자치시"})


class RegionTableError(RuntimeError):
    """지역 표를 신뢰할 수 없을 때. 조용히 빈 결과를 돌려주지 않는다."""


@lru_cache(maxsize=1)
def _rows() -> tuple[dict[str, Any], ...]:
    try:
        text = REGIONS_CSV_PATH.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise RegionTableError(f"지역 표를 읽을 수 없습니다: {REGIONS_CSV_PATH}") from exc
    reader = csv.DictReader(text.splitlines())
    missing_columns = [name for name in _REQUIRED_COLUMNS if name not in (reader.fieldnames or ())]
    if missing_columns:
        raise RegionTableError("지역 표에 필요한 컬럼이 없습니다: " + ", ".join(missing_columns))
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for line_number, raw in enumerate(reader, start=2):
        row = {_COLUMN_RENAMES.get(key, key): str(value or "").strip() for key, value in raw.items()}
        region_id = row["region_id"]
        if len(region_id) != 5 or not region_id.isdigit():
            raise RegionTableError(f"{line_number}행 region_id는 5자리 숫자여야 합니다: {region_id!r}")
        if region_id in seen_ids:
            raise RegionTableError(f"region_id가 중복됩니다: {region_id}")
        seen_ids.add(region_id)
        if not row["province_name"] or not row["region_name"]:
            raise RegionTableError(f"{line_number}행 시도명·시군구명이 비어 있습니다: {region_id}")
        if row["administrative_type"] not in _ALLOWED_ADMINISTRATIVE_TYPES:
            raise RegionTableError(
                f"{line_number}행 행정유형을 알 수 없습니다: {row['administrative_type']!r}"
            )
        rows.append(row)
    if not rows:
        raise RegionTableError("지역 표가 비어 있습니다.")
    return tuple(rows)


@lru_cache(maxsize=1)
def _by_id() -> dict[str, dict[str, Any]]:
    return {row["region_id"]: row for row in _rows()}


@lru_cache(maxsize=1)
def _ids_by_name() -> dict[tuple[str, str], tuple[str, ...]]:
    """(시도명, 시군구명) 및 (빈 문자열, 시군구명) → region_id 후보."""
    index: dict[tuple[str, str], list[str]] = {}
    for row in _rows():
        index.setdefault((row["province_name"], row["region_name"]), []).append(row["region_id"])
        index.setdefault(("", row["region_name"]), []).append(row["region_id"])
    return {key: tuple(value) for key, value in index.items()}


def all_regions() -> list[dict[str, Any]]:
    return [dict(row) for row in _rows()]


def region_total() -> int:
    return len(_rows())


def all_region_ids() -> tuple[str, ...]:
    """전국 region_id. 전국 응답을 지역 단위로 걸러낼 때 쓴다."""
    return tuple(_by_id())


def find_region(region_id: str) -> dict[str, Any] | None:
    row = _by_id().get(region_id)
    return None if row is None else dict(row)


def search_regions(*, q: str | None = None, province: str | None = None) -> list[dict[str, Any]]:
    """시군구명 부분 일치와 시도명 완전 일치로 거른다."""
    items = _rows()
    if province:
        items = tuple(item for item in items if item["province_name"] == province)
    if q:
        items = tuple(item for item in items if q in item["region_name"])
    return [dict(row) for row in items]


def provinces() -> list[dict[str, Any]]:
    """시도별 시군구 수. 표의 등장 순서를 유지한다."""
    counts: dict[str, int] = {}
    for row in _rows():
        counts[row["province_name"]] = counts.get(row["province_name"], 0) + 1
    return [
        {"province_name": name, "region_count": count}
        for name, count in counts.items()
    ]


@lru_cache(maxsize=1)
def _tour_api_codes() -> dict[str, tuple[str, str]]:
    """region_id → (area_code, sigungu_code). 코드가 없는 지역은 빠진다.

    2026년 인천 개편으로 생긴 구는 TourAPI 지역 목록에 아직 없어 코드가 비어
    있다. 옛 자치구 코드를 대신 넣으면 서로 다른 지역에 같은 수요값이 붙으므로
    빼는 편이 맞다. 사유는 표의 `note`에 적혀 있다.
    """
    try:
        text = REGION_CODE_MAP_CSV_PATH.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise RegionTableError(f"지역 코드 표를 읽을 수 없습니다: {REGION_CODE_MAP_CSV_PATH}") from exc
    codes: dict[str, tuple[str, str]] = {}
    for row in csv.DictReader(text.splitlines()):
        area_code = str(row.get("area_code") or "").strip()
        sigungu_code = str(row.get("sigungu_code") or "").strip()
        if area_code and sigungu_code:
            codes[str(row["region_id"]).strip()] = (area_code, sigungu_code)
    if not codes:
        raise RegionTableError("지역 코드 표에 사용할 수 있는 행이 없습니다.")
    return codes


def tour_api_code(region_id: str) -> tuple[str, str] | None:
    """TourAPI 조회용 (area_code, sigungu_code). 매핑이 없으면 `None`.

    관광자원(`/portfolio`)과 중심관광지(`/hubs`) 전용이다. 관광 수요지수 API는
    코드 체계가 달라 `demand_codes()`를 써야 한다.
    """
    return _tour_api_codes().get(region_id)


@lru_cache(maxsize=1)
def _demand_codes() -> dict[str, tuple[str, ...]]:
    """region_id → 관광 수요지수 API의 법정동 코드들.

    일반구가 있는 시는 구 코드 여러 개가 대응하고, 호출측이 그 값들을
    평균한다. 공표되지 않는 지역은 표에 빈 값으로 남아 여기서 빠진다.
    """
    try:
        text = REGION_DEMAND_CODES_CSV_PATH.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise RegionTableError(
            f"관광 수요지수 코드 표를 읽을 수 없습니다: {REGION_DEMAND_CODES_CSV_PATH}"
        ) from exc
    codes: dict[str, tuple[str, ...]] = {}
    for row in csv.DictReader(text.splitlines()):
        values = tuple(
            item.strip() for item in str(row.get("demand_codes") or "").split(";") if item.strip()
        )
        if values:
            codes[str(row["region_id"]).strip()] = values
    if not codes:
        raise RegionTableError("관광 수요지수 코드 표에 사용할 수 있는 행이 없습니다.")
    return codes


def demand_codes(region_id: str) -> tuple[str, ...] | None:
    """관광 수요지수 API 조회용 법정동 코드들. 공표되지 않으면 `None`."""
    return _demand_codes().get(region_id)


@lru_cache(maxsize=1)
def legacy_region_codes() -> frozenset[str]:
    """행정구역 개편 전 코드 집합.

    2026년 개편으로 광주와 전남이 우리 표에서 `12`로 합쳐졌지만, 원천 API는
    개편이 반영되기 전 달에 대해 여전히 옛 코드(순천시 `46150`)로 공표한다.
    과거 월을 조회할 때 그 행을 버리지 않으려면 이 집합이 필요하다.

    일반구 코드는 개편과 무관하므로 제외한다.
    """
    return frozenset(
        code
        for region_id, codes in _demand_codes().items()
        if len(codes) == 1 and codes[0] != region_id
        for code in codes
    )


def resolve_by_name(
    region_name: str,
    *,
    province_name: str | None = None,
    candidate_region_ids: set[str] | None = None,
) -> str | None:
    """지역명을 `region_id`로 바꾼다. 확정할 수 없으면 `None`.

    `candidate_region_ids`를 주면 그 안에서만 찾는다. 산출물이 이름만 들고
    있을 때 전국이 아니라 해당 지역의 peer 집합 안에서 해석하기 위한 것으로,
    동명 시군구가 같은 집합에 동시에 들어오는 경우만 모호해진다.

    추측하지 않는 것이 이 함수의 요점이다. 후보가 여러 개면 그중 하나를
    고르지 않고 `None`을 돌려주고, 호출측이 그 사실을 응답에 남긴다.
    """
    name = (region_name or "").strip()
    if not name:
        return None
    candidates = _ids_by_name().get(((province_name or "").strip(), name), ())
    if candidate_region_ids is not None:
        candidates = tuple(item for item in candidates if item in candidate_region_ids)
    return candidates[0] if len(candidates) == 1 else None
