"""국가토지피복통계에서 시군구별 산림·농지 비율을 계산한다."""

from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path

import pandas as pd

from .config import PROCESSED_DIR, RAW_DIR, REFERENCE_DIR
from .regions import build_region_master, load_resources
from .sources.structural import PROVINCE_ALIASES

DEFAULT_OUTPUT = PROCESSED_DIR / "land_cover_by_region.csv"
DEFAULT_SHEET_NAME = "25년_시군구_토지피복지도"
SGIS_MAP_PATH = REFERENCE_DIR / "sgis_region_map.csv"

TOTAL_COLUMN = "총합계"
FOREST_COLUMNS = ("활엽수림", "침엽수림", "혼효림")
FARMLAND_COLUMNS = (
    "경지정리가 된 논",
    "경지정리가 안 된 논",
    "경지정리가 된 밭",
    "경지정리가 안 된 밭",
    "시설재배지",
    "과수원",
    "목장양식장",
    "기타재배지",
)
AREA_COLUMNS = (TOTAL_COLUMN, *FOREST_COLUMNS, *FARMLAND_COLUMNS)
SOURCE_NAME = "2025년(2024년 기준) 국가토지피복통계 토지피복지도현황"


def find_land_cover_workbook(raw_dir: str | Path = RAW_DIR) -> Path:
    """raw 폴더에서 토지피복 통계 엑셀을 찾는다.

    macOS에서 한글 파일명이 NFD로 저장될 수 있으므로 NFC 정규화 후 찾는다.
    """
    candidates = []
    for path in Path(raw_dir).glob("*.xlsx"):
        normalized = unicodedata.normalize("NFC", path.name)
        if "토지피복" in normalized and "토지피복지도현황" in normalized:
            candidates.append(path)
    if not candidates:
        raise FileNotFoundError("data/raw 아래에서 국가토지피복통계 토지피복지도현황 xlsx를 찾지 못했습니다.")
    return sorted(candidates, key=lambda path: path.name)[-1]


def load_land_cover_source(path: str | Path | None = None) -> pd.DataFrame:
    """원본 엑셀의 시군구 면적 행을 계산에 필요한 표준 컬럼으로 변환한다."""
    source_path = Path(path) if path else find_land_cover_workbook()
    raw = pd.read_excel(source_path, sheet_name=DEFAULT_SHEET_NAME, header=2)
    required = {"시도", "시군구", "구분", *AREA_COLUMNS}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"토지피복 원본에 필요한 컬럼이 없습니다: {sorted(missing)}")

    frame = raw.copy()
    for column in ["시도", "시군구", "구분"]:
        frame[column] = frame[column].map(_normalize_text)
    frame = frame[(frame["구분"] == "면적(㎡)") & (frame["시도"] != "전국")].copy()

    for column in AREA_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    result = pd.DataFrame(
        {
            "province_name": frame["시도"],
            "source_region_name": frame["시군구"],
            "total_area_m2": frame[TOTAL_COLUMN],
            "forest_area_m2": frame[list(FOREST_COLUMNS)].sum(axis=1, min_count=1),
            "farmland_area_m2": frame[list(FARMLAND_COLUMNS)].sum(axis=1, min_count=1),
        }
    )
    return _prepare_source_area(result)


def build_land_cover_features(
    regions: pd.DataFrame,
    source_area: pd.DataFrame,
    overrides: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """TourAPI 230개 지역 단위에 맞춰 산림·농지 비율을 만든다."""
    source = _prepare_source_area(source_area)
    mapping = _load_overrides() if overrides is None else overrides.copy()
    if not mapping.empty:
        mapping["region_id"] = mapping["region_id"].astype(str)

    rows: list[dict[str, object]] = []
    for region in regions.itertuples(index=False):
        direct = _find_one_source(source, region.province_name, region.region_name)
        if direct is not None:
            rows.append(
                _feature_record(
                    region.region_id,
                    [(1.0, direct)],
                    match_method="direct",
                    source_type="static_reference",
                )
            )
            continue

        if not mapping.empty and region.region_id in set(mapping["region_id"]):
            records = []
            subset = mapping[mapping["region_id"] == region.region_id]
            for item in subset.itertuples(index=False):
                match = _find_one_source(
                    source, item.sgis_province, item.sgis_municipality
                )
                if match is not None:
                    records.append((float(item.weight), match))
            if records:
                first_mapping = subset.iloc[0]
                method = (
                    "name_alias"
                    if len(records) == 1
                    and float(first_mapping["weight"]) == 1.0
                    and _normalize_text(first_mapping["region_name"])
                    == region.region_name
                    else "weighted_proxy"
                )
                source_type = "static_reference" if method == "name_alias" else "proxy"
                rows.append(
                    _feature_record(
                        region.region_id,
                        records,
                        match_method=method,
                        source_type=source_type,
                    )
                )
                continue

        rolled = _rollup_general_districts(
            source, region.province_name, region.region_name
        )
        if not rolled.empty:
            rows.append(
                _feature_record(
                    region.region_id,
                    [(1.0, row) for row in rolled.to_dict("records")],
                    match_method="general_district_rollup",
                    source_type="static_reference",
                )
            )
            continue

        rows.append(_missing_record(region.region_id))

    return pd.DataFrame(rows)


def build_and_save(
    *,
    input_path: str | Path | None = None,
    output_path: str | Path = DEFAULT_OUTPUT,
) -> Path:
    source = load_land_cover_source(input_path)
    regions = build_region_master(load_resources())
    features = build_land_cover_features(regions, source)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(output, index=False)
    return output


def _prepare_source_area(source_area: pd.DataFrame) -> pd.DataFrame:
    required = {
        "province_name",
        "source_region_name",
        "total_area_m2",
        "forest_area_m2",
        "farmland_area_m2",
    }
    missing = required - set(source_area.columns)
    if missing:
        raise ValueError(f"source_area에 필요한 컬럼이 없습니다: {sorted(missing)}")

    source = source_area.copy()
    source["province_name"] = source["province_name"].map(_normalize_text)
    source["source_region_name"] = source["source_region_name"].map(_normalize_text)
    for column in ["total_area_m2", "forest_area_m2", "farmland_area_m2"]:
        source[column] = pd.to_numeric(source[column], errors="coerce")
    return source.dropna(
        subset=["province_name", "source_region_name", "total_area_m2"]
    )


def _load_overrides() -> pd.DataFrame:
    if not SGIS_MAP_PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(SGIS_MAP_PATH, dtype={"region_id": str})


def _find_one_source(
    source: pd.DataFrame, province_name: str, region_name: str
) -> dict[str, object] | None:
    for province in _province_candidates(province_name):
        matches = source[
            (source["province_name"] == province)
            & (source["source_region_name"] == _normalize_text(region_name))
        ]
        if not matches.empty:
            return matches.iloc[0].to_dict()
    return None


def _rollup_general_districts(
    source: pd.DataFrame, province_name: str, region_name: str
) -> pd.DataFrame:
    frames = []
    prefix = f"{_normalize_text(region_name)} "
    for province in _province_candidates(province_name):
        matches = source[
            (source["province_name"] == province)
            & (source["source_region_name"].str.startswith(prefix, na=False))
        ]
        if not matches.empty:
            frames.append(matches)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _feature_record(
    region_id: str,
    records: list[tuple[float, dict[str, object]]],
    *,
    match_method: str,
    source_type: str,
) -> dict[str, object]:
    total_weight = sum(weight for weight, _ in records)
    if total_weight <= 0:
        return _missing_record(region_id)

    total_area = _weighted_sum(records, "total_area_m2")
    forest_area = _weighted_sum(records, "forest_area_m2")
    farmland_area = _weighted_sum(records, "farmland_area_m2")
    if not total_area:
        return _missing_record(region_id)

    return {
        "region_id": str(region_id),
        "land_cover_total_area_m2": total_area,
        "forest_area_m2": forest_area,
        "farmland_area_m2": farmland_area,
        "forest_ratio": forest_area / total_area,
        "farmland_ratio": farmland_area / total_area,
        "forest_ratio_source_type": source_type,
        "farmland_ratio_source_type": source_type,
        "forest_ratio_missing_reason": "",
        "farmland_ratio_missing_reason": "",
        "land_cover_match_method": match_method,
        "land_cover_source_regions": json.dumps(
            [
                {
                    "province_name": record["province_name"],
                    "region_name": record["source_region_name"],
                    "weight": weight,
                }
                for weight, record in records
            ],
            ensure_ascii=False,
        ),
        "land_cover_source_period": "2024",
        "land_cover_source_name": SOURCE_NAME,
    }


def _missing_record(region_id: str) -> dict[str, object]:
    reason = "land cover source region match missing"
    return {
        "region_id": str(region_id),
        "land_cover_total_area_m2": float("nan"),
        "forest_area_m2": float("nan"),
        "farmland_area_m2": float("nan"),
        "forest_ratio": float("nan"),
        "farmland_ratio": float("nan"),
        "forest_ratio_source_type": "static_reference",
        "farmland_ratio_source_type": "static_reference",
        "forest_ratio_missing_reason": reason,
        "farmland_ratio_missing_reason": reason,
        "land_cover_match_method": "missing",
        "land_cover_source_regions": "[]",
        "land_cover_source_period": "2024",
        "land_cover_source_name": SOURCE_NAME,
    }


def _weighted_sum(records: list[tuple[float, dict[str, object]]], column: str) -> float:
    return sum(float(weight) * float(record[column]) for weight, record in records)


def _province_candidates(province_name: str) -> list[str]:
    normalized = _normalize_text(province_name)
    candidates = [normalized, *PROVINCE_ALIASES.get(normalized, [])]
    return list(dict.fromkeys(candidates))


def _normalize_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFC", str(value))
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    return " ".join(text.split())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="국가토지피복통계 산림·농지 비율 생성")
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    output = build_and_save(input_path=args.input, output_path=args.output)
    result = pd.read_csv(output, dtype={"region_id": str})
    complete = int(result["forest_ratio"].notna().sum())
    print(f"{output}: {complete}/{len(result)}개 지역")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
