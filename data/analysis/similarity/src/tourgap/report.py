"""분석 결과를 콘솔과 파일로 낸다. UI는 만들지 않는다."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from .config import RESULTS_DIR, get_config
from .pipeline import AnalysisResult

LINE = "=" * 68
THIN = "-" * 68

FEATURE_LABELS = {
    "log_population": "인구(log)",
    "log_area_km2": "면적(log)",
    "log_density": "인구밀도(log)",
    "coastal_flag": "해안 여부",
    "island_flag": "도서 여부",
    "forestry_household_ratio": "임가 비율",
    "farm_household_ratio": "농가 비율",
    "fishery_household_ratio": "어가 비율",
    "log_metro_distance_km": "대도시 거리(log)",
    "average_age": "평균연령",
    "avg_household_size": "평균가구원수",
}

METRIC_LABELS = {
    "share": "구성비",
    "per_10k_pop": "인구 1만명당",
    "per_100km2": "100km2당",
    "raw_count": "개수",
}


def render(result: AnalysisResult) -> str:
    target = result.target
    metric = get_config().gap.primary_metric
    metric_label = METRIC_LABELS.get(metric, metric)
    out: list[str] = []

    out.append(LINE)
    out.append(
        f"Target: {target['province_name']} {target['region_name']} "
        f"({target['region_id']})"
    )
    out.append(LINE)

    out.extend(_provenance_block(result))
    out.extend(_quality_block(result))
    out.extend(_peer_block(result))
    out.extend(_performance_block(result))
    out.extend(_gap_block(result, metric, metric_label))
    out.extend(_drilldown_block(result, metric_label))
    out.extend(_context_block(result, metric_label))
    out.extend(_caveat_block(result))
    return "\n".join(out)


def _provenance_block(result: AnalysisResult) -> list[str]:
    out = ["", "[데이터 출처와 신뢰도]"]
    frame = pd.DataFrame(result.provenance.to_rows())
    out.append(frame.to_string(index=False))
    if result.provenance.has_mock():
        names = ", ".join(result.provenance.mock_names())
        out.append("")
        out.append("  ⚠ MOCK 포함: " + names)
        out.append("    이 항목에 의존하는 결과(유사지역·benchmark 선정)는 " "아직 정책 판단에 쓸 수 없습니다.")
    return out


def _quality_block(result: AnalysisResult) -> list[str]:
    quality = result.quality
    out = ["", "[입력지역 등록 데이터 품질]"]
    out.append(
        f"  TourAPI 등록 자원 {int(quality['total_resources']):,}건 / "
        f"최근 {get_config().quality.stale_years}년 내 갱신 비율 "
        f"{float(quality['fresh_ratio']):.0%}"
    )
    if bool(quality["low_sample"]):
        out.append("  ⚠ 등록 자원이 적어 구성비가 불안정할 수 있습니다.")
    if bool(quality["stale"]):
        out.append("  ⚠ 갱신이 오래된 자원이 많습니다. 공급 부족이 아니라 " "등록 미비일 가능성을 함께 검토하세요.")
    return out


def _peer_block(result: AnalysisResult) -> list[str]:
    out = ["", THIN, "[결과 A] 유사 지역 (구조적 여건 기준)", THIN]
    frame = result.peers.copy()
    frame["지역"] = frame["province_name"] + " " + frame["region_name"]
    display = frame[["rank", "지역", "similarity", "distance"]].rename(
        columns={"rank": "순위", "similarity": "유사도", "distance": "거리"}
    )
    out.append(display.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    groups = get_config().similarity.group_weights
    group_names = {
        "regional_scale": "지역규모",
        "urban_concentration": "도시집적",
        "population_structure": "인구구조",
        "natural_geography": "자연지리",
        "climate": "기후",
        "industry_structure": "산업구조",
    }
    out.append("")
    out.append(
        "  가중치: "
        + ", ".join(
            f"{group_names.get(name, name)} {weight:.0%}"
            for name, weight in groups.items()
        )
    )
    return out


def _performance_block(result: AnalysisResult) -> list[str]:
    out = ["", THIN, "[결과 B] peer group 내 관광 성과", THIN]
    frame = result.performance.copy()
    frame["지역"] = frame["province_name"] + " " + frame["region_name"]
    frame["구분"] = [
        "◀ 입력지역"
        if region_id == result.target["region_id"]
        else ("★ benchmark" if region_id in result.benchmark_ids else "")
        for region_id in frame["region_id"]
    ]
    display = frame[
        [
            "지역",
            "performance_score",
            "visitor_level",
            "visitor_yoy_growth",
            "outsider_ratio",
            "foreign_ratio",
            "구분",
        ]
    ].rename(
        columns={
            "performance_score": "성과점수",
            "visitor_level": "관광방문자(12개월)",
            "visitor_yoy_growth": "전년대비",
            "outsider_ratio": "외지인비중",
            "foreign_ratio": "외국인비중",
        }
    )
    out.append(display.to_string(index=False, float_format=lambda v: f"{v:.2f}"))

    rank, total = result.target_performance_rank
    out.append("")
    out.append(f"  입력지역 성과 순위: peer {total}곳 중 {rank}위")

    if not result.benchmark_ids:
        out.append("")
        out.append("  ⚠ 입력 지역이 peer group에서 성과 1위입니다. " "벤치마킹할 상위 지역이 없습니다.")
        out.append("    자기보다 성과가 낮은 지역과 콘텐츠를 비교하는 것은 " "롤모델 분석이 아니므로 공백 계산을 건너뜁니다.")
        out.append("    --peer-k 를 늘려 비교군을 넓히거나, 이 지역을 " "다른 지역의 benchmark로 활용하세요.")
        return out

    names = ", ".join(
        f"{row.province_name} {row.region_name}"
        for row in result.benchmarks.itertuples()
    )
    out.append(f"  benchmark 지역: {names}")
    if len(result.benchmark_ids) < get_config().performance.benchmark_k:
        out.append(
            f"  ⚠ 입력 지역보다 성과가 높은 peer가 "
            f"{len(result.benchmark_ids)}곳뿐입니다. "
            "표본이 적어 공백 순위가 불안정할 수 있습니다."
        )
    return out


def _gap_block(result: AnalysisResult, metric: str, metric_label: str) -> list[str]:
    out = [
        "",
        THIN,
        f"[결과 C] 관광 콘텐츠 공백 (비교 지표: {metric_label})",
        THIN,
    ]
    if result.gaps.empty:
        out.append("  benchmark 지역이 없어 공백을 계산하지 않았습니다.")
        return out
    frame = result.gaps.copy()
    display = frame[
        [
            "rank",
            "category_name",
            "gap_score",
            "target_value",
            "benchmark_value",
            "consistency",
            "demand_label",
        ]
    ].rename(
        columns={
            "rank": "순위",
            "category_name": "카테고리",
            "gap_score": "공백점수",
            "target_value": "입력지역",
            "benchmark_value": f"benchmark {get_config().gap.aggregate}",
            "consistency": "일관성",
            "demand_label": "수요보정",
        }
    )
    formatter = (lambda v: f"{v:.1%}") if metric == "share" else (lambda v: f"{v:.2f}")

    def fmt(value: float) -> str:
        return formatter(value)

    out.append(display.to_string(index=False, float_format=fmt))
    out.append("")
    out.append("  공백점수 = 상대격차 × 일관성 × 수요보정  " "(일관성 = benchmark 중 입력지역보다 많은 곳의 비율)")
    return out


def _drilldown_block(result: AnalysisResult, metric_label: str) -> list[str]:
    if result.drilldown.empty:
        return []
    out = ["", THIN, "[결과 C-2] 상위 공백의 중분류 내역", THIN]
    for parent, group in result.drilldown.groupby("parent_name", sort=False):
        top = group.nlargest(4, "gap_score")
        out.append(f"  ▸ {parent}")
        display = top[
            ["category_name", "gap_score", "target_value", "benchmark_value"]
        ].rename(
            columns={
                "category_name": "중분류",
                "gap_score": "공백점수",
                "target_value": "입력지역",
                "benchmark_value": "benchmark",
            }
        )
        out.append(
            "    "
            + display.to_string(index=False, float_format=lambda v: f"{v:.3f}").replace(
                "\n", "\n    "
            )
        )
    return out


def _context_block(result: AnalysisResult, metric_label: str) -> list[str]:
    if result.context.empty:
        return []
    out = ["", THIN, "[참고] 원천 자원 비교 (공백 랭킹 제외)", THIN]
    display = result.context[
        ["category_name", "target_value", "benchmark_value"]
    ].rename(
        columns={
            "category_name": "카테고리",
            "target_value": "입력지역",
            "benchmark_value": "benchmark",
        }
    )
    out.append(display.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    out.append("")
    out.append("  자연·역사는 정책으로 새로 만들기 어려운 원천 여건이므로 " "공백 순위에 넣지 않습니다.")
    return out


def _caveat_block(result: AnalysisResult) -> list[str]:
    return [
        "",
        LINE,
        "[해석 주의]",
        "  이 분석은 인과관계를 증명하지 않습니다.",
        "  '체험시설을 늘리면 관광객이 늘어난다'고 말할 수 없습니다.",
        "  결과는 다음 정도로 읽어야 합니다:",
        "    구조적 여건이 비슷하면서 관광 성과가 높은 지역들과 비교할 때,",
        "    입력 지역에서 반복적으로 관찰되는 콘텐츠 구성상의 차이.",
        "",
        "  또한 공급량은 TourAPI '등록' 기준이므로 지자체의 등록 성실도가",
        "  섞여 있습니다. 공백 후보는 현장 확인을 거쳐 판단하세요.",
        LINE,
    ]


def save(result: AnalysisResult, *, output_dir: Path | None = None) -> Path:
    """결과를 JSON + CSV로 저장한다."""
    directory = output_dir or RESULTS_DIR
    target = result.target
    slug = f"{target['region_name']}_{target['region_id']}_{date.today():%Y%m%d}"
    base = directory / slug
    base.mkdir(parents=True, exist_ok=True)

    result.peers.to_csv(base / "peers.csv", index=False)
    result.performance.to_csv(base / "performance.csv", index=False)
    result.gaps.to_csv(base / "gaps.csv", index=False)
    result.contribution.to_csv(base / "peer_feature_contribution.csv", index=False)
    result.feature_comparison.to_csv(base / "feature_comparison.csv")
    if not result.drilldown.empty:
        result.drilldown.to_csv(base / "gap_drilldown.csv", index=False)
    result.context.to_csv(base / "endowment_context.csv", index=False)

    summary = {
        "target": {
            "region_id": target["region_id"],
            "province_name": target["province_name"],
            "region_name": target["region_name"],
        },
        "generated_at": date.today().isoformat(),
        "config": {
            "peer_k": get_config().similarity.peer_k,
            "benchmark_k": get_config().performance.benchmark_k,
            "gap_metric": get_config().gap.primary_metric,
            "group_weights": get_config().similarity.group_weights,
            "performance_weights": get_config().performance.weights,
        },
        "peers": result.peers[
            ["rank", "region_id", "province_name", "region_name", "similarity"]
        ].to_dict("records"),
        "benchmarks": result.benchmarks[
            ["region_id", "province_name", "region_name", "performance_score"]
        ].to_dict("records"),
        "gaps": result.gaps.to_dict("records"),
        "provenance": result.provenance.to_rows(),
    }
    (base / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return base
