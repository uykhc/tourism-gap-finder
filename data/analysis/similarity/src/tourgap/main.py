"""분석 CLI.

    python -m tourgap.main --region 경주시
    python -m tourgap.main --region "경상남도 고성군" --explain
    python -m tourgap.main --region 경주시 --metric per_10k_pop --peer-k 20
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace

from dotenv import load_dotenv

from .config import PROJECT_ROOT, get_config, set_config
from .pipeline import analyze, load_dataset
from .regions import RegionMaster
from .report import render, save


def _apply_overrides(args: argparse.Namespace) -> None:
    """CLI 인자로 config를 덮어쓴다. 실험을 빠르게 돌리기 위한 통로."""
    current = get_config()
    similarity = current.similarity
    performance = current.performance
    gap = current.gap

    if args.peer_k is not None:
        similarity = replace(similarity, peer_k=args.peer_k)
    if args.no_admin_filter:
        similarity = replace(similarity, same_administrative_type=False)
    if args.allow_mock_structural:
        similarity = replace(similarity, allow_mock_structural=True)
    if args.benchmark_k is not None:
        performance = replace(performance, benchmark_k=args.benchmark_k)
    if args.normalize_scope is not None:
        performance = replace(performance, normalize_scope=args.normalize_scope)
    if args.metric is not None:
        gap = replace(gap, primary_metric=args.metric)

    set_config(
        replace(current, similarity=similarity, performance=performance, gap=gap)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="관광 콘텐츠 공백 분석")
    parser.add_argument(
        "--region",
        required=True,
        help="시군구명, '시도 시군구', 또는 KTO lDong 5자리 코드 (예: 경주시 / 47130)",
    )
    parser.add_argument("--peer-k", type=int, help="유사 지역 수")
    parser.add_argument("--benchmark-k", type=int, help="benchmark 지역 수")
    parser.add_argument(
        "--metric",
        choices=["share", "per_10k_pop", "per_100km2", "raw_count"],
        help="공백 비교의 중심 지표",
    )
    parser.add_argument(
        "--normalize-scope",
        choices=["national", "peer"],
        help="성과 z-표준화 범위",
    )
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
    parser.add_argument("--no-save", action="store_true", help="결과 파일을 저장하지 않는다")
    args = parser.parse_args(argv)

    load_dotenv(PROJECT_ROOT / ".env")
    _apply_overrides(args)

    dataset = load_dataset()
    master = RegionMaster(dataset.regions)
    try:
        target = master.resolve(args.region)
    except LookupError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1

    result = analyze(dataset, target)
    print(render(result))

    if args.explain:
        print()
        print("-" * 68)
        print("[설명] 입력지역 vs benchmark 구조 변수 원본값")
        print("-" * 68)
        print(result.feature_comparison.to_string(float_format=lambda v: f"{v:,.2f}"))

    if not args.no_save:
        path = save(result)
        print()
        print(f"결과 저장: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
