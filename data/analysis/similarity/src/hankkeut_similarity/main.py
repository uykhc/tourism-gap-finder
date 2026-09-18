"""PeerFinder CLI.

    python -m hankkeut_similarity.main --region 경주시
    python -m hankkeut_similarity.main --region "경상남도 고성군" --explain
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd
from .config import get_config, load_project_environment, set_config
from .pipeline import analyze, load_dataset
from .similarity import available_features
from .regions import RegionMaster


def _apply_overrides(args: argparse.Namespace) -> None:
    current = get_config()
    similarity = current.similarity

    if args.peer_k is not None:
        similarity = replace(similarity, peer_k=args.peer_k)
    if args.no_admin_filter:
        similarity = replace(similarity, same_administrative_type=False)
    if args.allow_mock_structural:
        similarity = replace(similarity, allow_mock_structural=True)

    set_config(replace(current, similarity=similarity))


def _write_features(features: pd.DataFrame, path: Path) -> None:
    """`find_peers`가 쓰는 컬럼만 남겨 CSV로 저장한다.

    중간 병합 컬럼(`coastal_dummy_x` 등)까지 내보내면 어느 컬럼이 계약인지
    알 수 없게 된다. 지역 식별 4개와 유사도에 실제로 쓰이는 변수만 남긴다.
    """
    columns = ["region_id", "province_name", "region_name", "admin_type"]
    columns += [name for name in available_features(features) if name not in columns]
    trimmed = features[columns]
    path.parent.mkdir(parents=True, exist_ok=True)
    trimmed.to_csv(path, index=False, encoding="utf-8")
    rows, column_count = trimmed.shape
    print(f"저장: {path} ({rows}개 지역 × {column_count}개 컬럼)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="구조적 여건 기반 유사 지역 탐색")
    parser.add_argument(
        "--region",
        help="시군구명, '시도 시군구', 또는 KTO lDong 5자리 코드 (예: 경주시 / 47130)",
    )
    parser.add_argument(
        "--dump-features",
        type=Path,
        help=(
            "전국 구조 feature 표를 CSV로 저장하고 끝낸다. find_peers는 이 표만 "
            "있으면 되므로, API가 SGIS 호출 없이 유사 지역을 계산할 수 있다"
        ),
    )
    parser.add_argument("--peer-k", type=int, help="유사 지역 수")
    parser.add_argument(
        "--no-admin-filter",
        action="store_true",
        help="시/군/자치구 동일 유형 제한을 끈다",
    )
    parser.add_argument(
        "--allow-mock-structural",
        action="store_true",
        help="SGIS 키 없이 개발용 합성 구조 변수로 실행한다(정책 판단 금지)",
    )
    parser.add_argument("--explain", action="store_true", help="feature 비교표를 함께 출력")
    parser.add_argument("--output", type=Path, help="Peer 결과 JSON 저장 경로")
    args = parser.parse_args(argv)
    if not args.region and not args.dump_features:
        parser.error("--region 또는 --dump-features 중 하나는 있어야 합니다")

    load_project_environment()
    _apply_overrides(args)

    dataset = load_dataset()

    if args.dump_features:
        _write_features(dataset.features, args.dump_features)
        if not args.region:
            return 0

    master = RegionMaster(dataset.regions)
    try:
        target = master.resolve(args.region)
    except LookupError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1

    result = analyze(dataset, target)
    print(_render(result))

    if args.output:
        _write_result(result, args.output)
        print(f"\n저장: {args.output}")

    if args.explain:
        print()
        print("-" * 68)
        print("[설명] 입력지역 vs peer 구조 변수 원본값")
        print("-" * 68)
        print(result.feature_comparison.to_string(float_format=lambda v: f"{v:,.2f}"))
    return 0


def _write_result(result, path: Path) -> None:
    """Write a stable handoff for demand collection and later benchmark filtering."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "result_version": "2026-09-05",
        "target": {
            "region_id": str(result.target["region_id"]),
            "province_name": str(result.target["province_name"]),
            "region_name": str(result.target["region_name"]),
            "administrative_type": str(result.target["admin_type"]),
        },
        "selection_type": "structural_similarity_candidates",
        "warning": (
            "이 목록은 구조적으로 유사한 후보입니다. 관광 성과 검증 전에는 "
            "'우수 Peer'로 해석하지 않습니다."
        ),
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
            for row in result.peers.itertuples(index=False)
        ],
        "provenance": result.provenance.to_rows(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _render(result) -> str:
    target = result.target
    out = [
        "=" * 68,
        f"Target: {target.province_name} {target.region_name} ({target.region_id})",
        "=" * 68,
        "",
        "[데이터 출처]",
        pd.DataFrame(result.provenance.to_rows()).to_string(index=False),
        "",
        "[유사 지역]",
    ]
    if result.peers.empty:
        out.append("  기본 유사도 하한을 넘는 peer가 없습니다.")
        return "\n".join(out)

    frame = result.peers.merge(
        result.features[["region_id", "province_name", "region_name", "admin_type"]],
        on="region_id",
        how="left",
        suffixes=("", "_peer"),
    )
    display = frame[
        [
            "rank",
            "province_name",
            "region_name",
            "admin_type",
            "similarity",
            "distance",
            "feature_weight_used",
            "missing_feature_count",
        ]
    ].rename(
        columns={
            "rank": "순위",
            "province_name": "시도",
            "region_name": "시군구",
            "admin_type": "행정유형",
            "similarity": "유사도",
            "distance": "거리",
            "feature_weight_used": "사용가중치",
            "missing_feature_count": "결측변수수",
        }
    )
    out.append(
        display.to_string(index=False, float_format=lambda value: f"{value:.3f}")
    )
    return "\n".join(out)


if __name__ == "__main__":
    sys.exit(main())
