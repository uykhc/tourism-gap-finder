"""OpenAI Responses integration for source-grounded tourism-gap reports."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

from .case_search import (
    CaseSearchDocument,
    CaseSearchProvider,
    CaseSearchQuery,
    PREFERRED_SOURCE_KINDS,
    SourceKind,
    SupportedCaseSource,
    screen_case_documents,
)
from .report_schema import validate_report_payload

DEFAULT_MODEL = "gpt-5.6-luna"
DEFAULT_MAX_OUTPUT_TOKENS = 1_800
DEFAULT_MAX_GAP_TYPES = 2
MAX_CASE_EVIDENCE_CHARS = 240
# Three structural peers provide enough comparison context for the pilot while
# keeping case-search calls and the LLM context bounded.
DEFAULT_MAX_PEER_REGIONS = 3
REPORT_SCHEMA_PATH = Path("config/ai/tourism_gap_report.schema.json")
INTERPRETATION_RULES_PATH = Path("config/ai/tourism_gap_interpretation_rules.md")
OPENAI_API_KEY_ENV_NAME = "OPENAI_API_KEY"


class ResponsesClient(Protocol):
    @property
    def responses(self) -> Any: ...


@dataclass(frozen=True, slots=True)
class ReportGenerationResult:
    report: dict[str, Any]
    model: str
    response_id: str | None
    approved_sources: tuple[SupportedCaseSource, ...]


def resolve_openai_api_key(
    *, dotenv_path: Path = Path(".env"), environ: Mapping[str, str] | None = None,
) -> str | None:
    """Read only OPENAI_API_KEY without injecting all dotenv values into env."""
    source_environment = os.environ if environ is None else environ
    value = source_environment.get(OPENAI_API_KEY_ENV_NAME, "").strip()
    if value:
        return value
    try:
        lines = dotenv_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    for line in reversed(lines):
        stripped = line.strip()
        if stripped.startswith("export "):
            stripped = stripped.removeprefix("export ").lstrip()
        key, separator, raw_value = stripped.partition("=")
        if separator and key.strip() == OPENAI_API_KEY_ENV_NAME:
            candidate = raw_value.strip().strip("\"'")
            return candidate or None
    return None


def create_openai_client(*, api_key: str | None = None) -> ResponsesClient:
    key = api_key or resolve_openai_api_key()
    if not key:
        raise ValueError("OPENAI_API_KEY가 없습니다. .env 또는 서버 환경변수에 설정하세요.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("OpenAI SDK가 없습니다. python -m pip install -e '.[ai]'를 실행하세요.") from exc
    return OpenAI(api_key=key)


class OpenAIWebCaseSearchProvider(CaseSearchProvider):
    """Use web search only for discovery; report writing gets screened sources."""

    def __init__(self, client: ResponsesClient, *, model: str = DEFAULT_MODEL) -> None:
        self._client = client
        self._model = model

    def search(self, query: CaseSearchQuery) -> list[CaseSearchDocument]:
        response = self._client.responses.create(
            model=self._model,
            reasoning={"effort": "low"},
            tools=[{"type": "web_search"}],
            input=[
                {"role": "system", "content": (
                    "Find verifiable Korean tourism cases. Prefer official public institutions, "
                    "local governments, operators, and research institutions. Do not use blogs "
                    "or community posts. State only facts supported by cited pages."
                )},
                {"role": "user", "content": query.query},
            ],
            max_output_tokens=900,
            store=False,
        )
        evidence = _brief_case_evidence(_response_output_text(response))
        # One attributable recommendation per Peer/type query is enough for a
        # pilot report and prevents search prose from dominating model input.
        for citation in _response_url_citations(response):
            source_kind = _source_kind_from_url(citation["url"])
            if citation["title"] and citation["url"] and source_kind in PREFERRED_SOURCE_KINDS:
                return [CaseSearchDocument(
                    title=citation["title"], url=citation["url"], publisher=_publisher_from_url(citation["url"]),
                    source_kind=source_kind, snippet=evidence,
                )]
        return []


class OpenAITourismReportGenerator:
    """Create a JSON-schema report from supplied data and fixed source IDs."""

    def __init__(self, client: ResponsesClient, *, model: str = DEFAULT_MODEL,
                 schema_path: Path = REPORT_SCHEMA_PATH,
                 interpretation_rules_path: Path = INTERPRETATION_RULES_PATH,
                 max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS) -> None:
        if max_output_tokens < 256:
            raise ValueError("max_output_tokens는 256 이상이어야 합니다.")
        self._client = client
        self._model = model
        self._schema = _load_schema(schema_path)
        self._interpretation_rules = _load_interpretation_rules(interpretation_rules_path)
        self._max_output_tokens = max_output_tokens

    def generate(self, *, ai_report_context: Mapping[str, Any],
                 peer_regions: Sequence[str] = (),
                 approved_sources: Sequence[SupportedCaseSource] = (),
                 max_gap_types: int = DEFAULT_MAX_GAP_TYPES) -> ReportGenerationResult:
        context = _prepare_context(ai_report_context, max_gap_types=max_gap_types)
        sources = tuple(approved_sources)
        response = self._client.responses.create(
            model=self._model,
            reasoning={"effort": "low"},
            input=[
                {"role": "system", "content": _system_instruction(self._interpretation_rules)},
                {"role": "user", "content": json.dumps({
                    "analysis_context": context,
                    "peer_regions": _unique_nonempty(peer_regions, DEFAULT_MAX_PEER_REGIONS),
                    "approved_sources": [source.to_dict() | {"evidence_snippet": source.evidence_snippet} for source in sources],
                }, ensure_ascii=False)},
            ],
            text={"format": {"type": "json_schema", "name": "tourism_gap_insight_report",
                             "strict": True, "schema": self._schema}},
            max_output_tokens=self._max_output_tokens,
            store=False,
        )
        try:
            payload = json.loads(_response_output_text(response))
        except json.JSONDecodeError as exc:
            raise ValueError("OpenAI 응답이 JSON 리포트가 아닙니다.") from exc
        if not isinstance(payload, dict):
            raise ValueError("OpenAI 응답 리포트가 객체가 아닙니다.")
        validate_report_payload(payload)
        _validate_report_against_input(payload, context, sources)
        return ReportGenerationResult(payload, self._model, getattr(response, "id", None), sources)


def collect_approved_case_sources(provider: CaseSearchProvider, *, content_types: Sequence[str],
                                  peer_regions: Sequence[str],
                                  max_peer_regions: int = DEFAULT_MAX_PEER_REGIONS,
                                  max_concurrent_searches: int = 5) -> list[SupportedCaseSource]:
    """Search bounded Peer/type pairs concurrently, then screen source documents.

    ``executor.map`` preserves the query order, so generated source IDs remain
    deterministic even though network calls complete in a different order.
    """
    if max_concurrent_searches < 1:
        raise ValueError("max_concurrent_searches는 1 이상이어야 합니다.")
    peers = _unique_nonempty(peer_regions, max_peer_regions)
    queries: list[CaseSearchQuery] = []
    for content_type in content_types:
        content_type = str(content_type).strip()
        if not content_type:
            continue
        for peer in peers:
            queries.append(CaseSearchQuery(
                peer, content_type, f"{peer} {content_type} 관광사업 콘텐츠 운영 성과",
            ))
    if not queries:
        return []
    with ThreadPoolExecutor(max_workers=min(max_concurrent_searches, len(queries))) as executor:
        result_sets = list(executor.map(provider.search, queries))
    documents = [document for result in result_sets for document in result]
    return screen_case_documents(documents)


def _prepare_context(context: Mapping[str, Any], *, max_gap_types: int) -> dict[str, Any]:
    if not isinstance(max_gap_types, int) or not 1 <= max_gap_types <= 6:
        raise ValueError("max_gap_types는 1~6 범위여야 합니다.")
    region_name = str(context.get("region_name", "")).strip()
    analysis_period = str(context.get("analysis_period", "")).strip()
    metrics = context.get("content_type_metrics")
    if not region_name or not analysis_period or not isinstance(metrics, list):
        raise ValueError("ai_report_context에 region_name, analysis_period, content_type_metrics가 필요합니다.")
    priority = (
        context["priority_order_by_individual_peer_pressure"]
        if "priority_order_by_individual_peer_pressure" in context
        else context.get("priority_order_by_supply_pressure", [])
    )
    peer_comparison = context.get("peer_supply_pressure_comparison")
    if peer_comparison is not None:
        if not isinstance(peer_comparison, list):
            raise ValueError("peer_supply_pressure_comparison은 배열이어야 합니다.")
        # A type is a candidate if the target has at least as much pressure as
        # one individually compared Peer. The median is intentionally unused.
        candidate_types = {
            str(item.get("content_type", "")).strip()
            for item in peer_comparison
            if isinstance(item, dict)
            and isinstance(item.get("candidate_peer_count"), int)
            and item["candidate_peer_count"] > 0
        }
        priority = [item for item in priority if str(item).strip() in candidate_types]
    selected_types = [str(item).strip() for item in priority if str(item).strip()][:max_gap_types]
    selected_metrics = [metric for metric in metrics if isinstance(metric, dict) and metric.get("content_type") in selected_types]
    if len(selected_metrics) != len(selected_types):
        raise ValueError("priority_order_by_supply_pressure의 유형별 지표가 없습니다.")
    prepared = {
        "region_name": region_name, "analysis_period": analysis_period, "status": "provisional",
        "metric_definition": str(context.get("metric_definition", "")).strip(),
        "limitation": str(context.get("limitation", "")).strip(),
        "selected_content_types": selected_types, "content_type_metrics": selected_metrics,
    }
    if peer_comparison is not None:
        prepared["peer_supply_pressure_comparison"] = peer_comparison
        prepared["gap_candidate_rule"] = "개별 Peer 한 곳 이상에 대해 타겟/Peer 공급압력 비율이 1 이상인 유형만 빈칸 후보입니다."
    relative_supply = context.get("relative_supply_comparison")
    if relative_supply is not None:
        if not isinstance(relative_supply, list):
            raise ValueError("relative_supply_comparison은 배열이어야 합니다.")
        # Only retain rows for selected demand-pressure candidates; the
        # detailed raw collection remains in the analysis artifact, not prompt.
        prepared["relative_supply_comparison"] = [
            item for item in relative_supply
            if isinstance(item, dict) and item.get("content_type") in selected_types
        ]
    return prepared


def _validate_report_against_input(report: Mapping[str, Any], context: Mapping[str, Any],
                                   sources: Sequence[SupportedCaseSource]) -> None:
    if report["region_name"] != context["region_name"] or report["analysis_period"] != context["analysis_period"]:
        raise ValueError("리포트의 지역 또는 분석기간이 입력값과 다릅니다.")
    if report["status"] != "provisional":
        raise ValueError("현재 단일 지역 파일럿 리포트는 provisional이어야 합니다.")
    expected_sources = [source.to_dict() for source in sources]
    if report["sources"] != expected_sources:
        raise ValueError("리포트 출처 목록이 승인된 출처 목록과 다릅니다.")
    allowed_types = set(context["selected_content_types"])
    if not {item["content_type"] for item in report["gap_types"]}.issubset(allowed_types):
        raise ValueError("리포트가 선택되지 않은 관광 유형을 포함합니다.")
    metrics = {item["content_type"]: item for item in context["content_type_metrics"]}
    for item in report["gap_types"]:
        expected = metrics[item["content_type"]]["searches_per_place"]
        if not any(evidence["target_value"] == expected for evidence in item["quantitative_evidence"]):
            raise ValueError("리포트 정량근거에 입력 공급압력 값이 포함되지 않았습니다.")




def _system_instruction(interpretation_rules: str) -> str:
    return """You write Korean tourism-gap insight reports as strict JSON. Use only the supplied analysis_context for numbers. Never invent a number, source, URL, publisher, date, case, or peer region. Copy approved_sources to sources exactly. A peer case may cite only supplied source_ids; if no approved source supports a case, use an empty peer_cases array. Each peer_cases.summary must be at most two concise Korean sentences and must not restate a source body. The pilot has no national or peer percentile, so it must remain provisional and state this in limitations. If peer_supply_pressure_comparison is supplied, use it only as a cautious structural-peer comparison and clearly retain its data-quality limitations. If relative_supply_comparison is supplied, use it only as a separate relative-supply signal based on composition share or 100-km² density; do not confuse it with demand pressure. Select only selected_content_types. If selected_content_types is empty, return gap_types as an empty array and state that no priority gap candidate was found under the supplied comparison rule. For each included type, put its exact searches_per_place value from content_type_metrics in quantitative_evidence. Supply pressure is a screening signal, not proof that a new facility will succeed.

The following interpretation rules are normative and override any intuitive but conflicting interpretation:\n\n""" + interpretation_rules


def _load_schema(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"리포트 JSON 스키마 파일이 없습니다: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("리포트 JSON 스키마가 객체가 아닙니다.")
    return payload


def _load_interpretation_rules(path: Path) -> str:
    try:
        rules = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise ValueError(f"관광 빈칸 해석 규범 파일이 없습니다: {path}") from exc
    if not rules:
        raise ValueError("관광 빈칸 해석 규범 파일이 비어 있습니다.")
    return rules


def _response_output_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text
    if isinstance(response, Mapping) and isinstance(response.get("output_text"), str):
        return response["output_text"]
    raise ValueError("OpenAI 응답에 출력 텍스트가 없습니다.")


def _brief_case_evidence(value: str, *, limit: int = MAX_CASE_EVIDENCE_CHARS) -> str:
    """Collapse a web-search response into bounded evidence for the report call."""
    normalized = re.sub(r"\s+", " ", value).strip()
    if not normalized:
        return "공식 출처에서 확인된 관광 콘텐츠 운영 사례입니다."
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit - 1].rstrip() + "…"


def _response_url_citations(response: Any) -> list[dict[str, str]]:
    raw = response.model_dump() if hasattr(response, "model_dump") else response
    found: list[dict[str, str]] = []
    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("type") == "url_citation" and isinstance(value.get("url"), str):
                found.append({"url": value["url"], "title": str(value.get("title", ""))})
            for child in value.values(): visit(child)
        elif isinstance(value, list):
            for child in value: visit(child)
    visit(raw)
    unique, seen = [], set()
    for citation in found:
        if citation["url"] not in seen:
            seen.add(citation["url"]); unique.append(citation)
    return unique


def _source_kind_from_url(url: str) -> SourceKind:
    host = urlparse(url).netloc.lower().split(":")[0]
    if host.endswith(".go.kr"): return SourceKind.LOCAL_GOVERNMENT
    if host.endswith((".or.kr", ".ac.kr", ".re.kr")): return SourceKind.RESEARCH
    return SourceKind.OTHER


def _publisher_from_url(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _unique_nonempty(values: Sequence[str], limit: int) -> list[str]:
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))[:limit]
