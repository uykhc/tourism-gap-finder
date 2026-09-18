"""전국 구조 변수 스냅숏으로 API용 Peer 산출물을 생성한다.

HTTP 요청 중에는 유사도 계산을 수행하지 않는다. 이 스크립트가 전국 지역별
상위 후보를 미리 계산해 ``peer_candidates/<region_id>.json``으로 저장하면 API는
그 산출물을 읽고 요청의 ``k``와 ``min_similarity``만 적용한다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from hankkeut_similarity.config import SIMILARITY_FEATURES
from hankkeut_similarity.peers import find_peers


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEATURES_PATH = REPOSITORY_ROOT / "apps" / "api" / "app" / "data" / "region_features.csv"
DEFAULT_OUTPUT_DIR = (
    REPOSITORY_ROOT
    / "apps"
    / "api"
    / "app"
    / "data"
    / "artifacts"
    / "peer_candidates"
)
RESULT_VERSION = "structural-peers-v1+2026-09-18"
DEFAULT_STORED_K = 50
EXPECTED_REGION_COUNT = 230
WARNING = (
    "이 목록은 구조적으로 유사한 후보입니다. 관광 성과 검증 전에는 "
    "'우수 Peer'로 해석하지 않습니다."
)

PROVENANCE: tuple[dict[str, Any], ...] = (
    {
        "소스": "지역 마스터",
        "신뢰도": "실데이터",
        "엔드포인트/출처": "KorService2 /areaBasedList2 lDongRegnCd·lDongSignguCd",
        "기준시점": "2026-08-17 수집분",
        "행수": 230,
        "비고": "KTO 실제 관광자원 lDong 5자리 코드 기준. 일반구는 모 시로 합산",
    },
    {
        "소스": "인구·면적·사업체",
        "신뢰도": "실데이터",
        "엔드포인트/출처": "SGIS OpenAPI3 population.json · hadmarea.geojson · company.json",
        "기준시점": "인구 2020 총조사, 사업체 2024",
        "행수": 230,
        "비고": "면적은 경계 GeoJSON에 shoelace 공식 적용",
    },
    {
        "소스": "기후평년값",
        "신뢰도": "proxy",
        "엔드포인트/출처": "data/processed/kma_climate_normals_by_region.csv",
        "기준시점": "1991~2020 기상청 기후평년값",
        "행수": 230,
        "비고": "가까운 관측소 3개 역거리 제곱 보간",
    },
    {
        "소스": "해안·도서 여부",
        "신뢰도": "정적참조",
        "엔드포인트/출처": "data/reference/coastal_island.csv",
        "기준시점": "2026년 행정구역 기준",
        "행수": 76,
        "비고": "원천 여건. 직접 정리한 표",
    },
    {
        "소스": "지형 기복",
        "신뢰도": "정적참조",
        "엔드포인트/출처": "data/processed/dem_terrain_relief_by_region.csv",
        "기준시점": "국토지리정보원 한반도 90m DEM",
        "행수": 230,
        "비고": "시군구 경계 내 P90 고도-P10 고도. 2026년 분할 지역은 proxy",
    },
    {
        "소스": "토지피복",
        "신뢰도": "정적참조",
        "엔드포인트/출처": "data/processed/land_cover_by_region.csv",
        "기준시점": "2024년 기준 국가토지피복통계",
        "행수": 230,
        "비고": "일반구는 모 시 합산, 인천 2026년 분할 지역은 보정표로 면적 배분",
    },
)


def load_features(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"region_id": str})
    identity_columns = {"region_id", "province_name", "region_name", "admin_type"}
    missing_columns = (identity_columns | set(SIMILARITY_FEATURES)) - set(frame.columns)
    if missing_columns:
        raise ValueError(f"구조 변수 표에 필요한 컬럼이 없습니다: {sorted(missing_columns)}")
    if frame["region_id"].duplicated().any():
        duplicates = sorted(frame.loc[frame["region_id"].duplicated(), "region_id"].unique())
        raise ValueError(f"구조 변수 표의 region_id가 중복됩니다: {duplicates}")
    if len(frame) != EXPECTED_REGION_COUNT:
        raise ValueError(
            f"전국 구조 변수 표는 {EXPECTED_REGION_COUNT}개 지역이어야 합니다: {len(frame)}개"
        )
    if frame[list(identity_columns)].isna().any().any():
        raise ValueError("구조 변수 표의 지역 식별 정보에 결측값이 있습니다.")
    if not frame["region_id"].str.fullmatch(r"\d{5}").all():
        raise ValueError("region_id는 5자리 숫자 문자열이어야 합니다.")
    if frame[list(SIMILARITY_FEATURES)].isna().any().any():
        raise ValueError("구조 변수 표에 결측값이 있습니다.")
    return frame


def build_payload(
    features: pd.DataFrame,
    target_region_id: str,
    *,
    stored_k: int = DEFAULT_STORED_K,
) -> dict[str, Any]:
    targets = features.loc[features["region_id"] == target_region_id]
    if targets.empty:
        raise LookupError(f"Unknown region_id: {target_region_id}")
    target = targets.iloc[0]
    peers, _ = find_peers(
        features,
        target_region_id,
        k=stored_k,
        min_similarity=0.0,
        same_admin_type=True,
    )
    return {
        "result_version": RESULT_VERSION,
        "target": {
            "region_id": str(target["region_id"]),
            "province_name": str(target["province_name"]),
            "region_name": str(target["region_name"]),
            "administrative_type": str(target["admin_type"]),
        },
        "selection_type": "structural_similarity_candidates",
        "warning": WARNING,
        "peers": [
            {
                "rank": int(row.rank),
                "region_id": str(row.region_id),
                "province_name": str(row.province_name),
                "region_name": str(row.region_name),
                "administrative_type": str(row.admin_type),
                "similarity": float(row.similarity),
                "distance": float(row.distance),
                "feature_weight_used": float(row.feature_weight_used),
                "missing_feature_count": int(row.missing_feature_count),
            }
            for row in peers.itertuples(index=False)
        ],
        "provenance": [dict(item) for item in PROVENANCE],
    }


def write_all(features: pd.DataFrame, output_dir: Path, *, stored_k: int) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    region_ids = [str(value) for value in features["region_id"]]
    expected_paths = {output_dir / f"{region_id}.json" for region_id in region_ids}
    stale_paths = set(output_dir.glob("*.json")) - expected_paths
    if stale_paths:
        names = ", ".join(sorted(path.name for path in stale_paths))
        raise ValueError(f"출력 디렉터리에 지역 코드 형식이 아닌 기존 JSON이 있습니다: {names}")
    for region_id in region_ids:
        payload = build_payload(features, region_id, stored_k=stored_k)
        destination = output_dir / f"{region_id}.json"
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
    return len(region_ids)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="전국 API Peer 산출물 생성")
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--stored-k", type=int, default=DEFAULT_STORED_K)
    args = parser.parse_args(argv)
    if not 1 <= args.stored_k <= 229:
        parser.error("--stored-k는 1~229여야 합니다")

    features = load_features(args.features)
    count = write_all(features, args.output_dir, stored_k=args.stored_k)
    print(f"Peer 산출물 생성 완료: {count}개 지역 -> {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
