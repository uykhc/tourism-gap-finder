"""유사 지역 그룹 산정 CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .similarity_groups import (
    build_similarity_result,
    load_similarity_config,
    load_similarity_regions,
    write_similarity_result,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="구조 특성 기반 시군구 유사 지역 그룹을 생성합니다.")
    parser.add_argument("--config", type=Path, required=True, help="유사 지역 설정 JSON")
    args = parser.parse_args(argv)
    try:
        config = load_similarity_config(args.config)
        regions = load_similarity_regions(config.input_csv)
        groups, neighbors, report = build_similarity_result(
            regions,
            weights=config.weights,
            groups_per_partition=config.groups_per_partition,
            partition_by_administrative_type=config.partition_by_administrative_type,
            neighbor_count=config.neighbor_count,
        )
        write_similarity_result(groups, neighbors, report, config=config)
    except (OSError, ValueError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2
    print(f"완료: {len(groups)}개 지역, {len(neighbors)}개 근접 레퍼런스 관계")
    print(f"저장: {config.groups_output_csv}")
    print(f"저장: {config.neighbors_output_csv}")
    print(f"저장: {config.report_output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
