"""Provider-neutral preparation and screening for Peer tourism case searches."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Protocol
from urllib.parse import urlparse

from .report_schema import CONTENT_TYPE_LABELS


class SourceKind(StrEnum):
    PUBLIC_INSTITUTION = "public_institution"
    LOCAL_GOVERNMENT = "local_government"
    OPERATOR = "operator"
    RESEARCH = "research"
    NEWS = "news"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class CaseSearchQuery:
    peer_region: str
    content_type: str
    query: str


@dataclass(frozen=True, slots=True)
class CaseSearchDocument:
    title: str
    url: str
    publisher: str
    source_kind: SourceKind
    snippet: str
    published_at: str | None = None
    peer_region: str = ""


@dataclass(frozen=True, slots=True)
class SupportedCaseSource:
    source_id: str
    title: str
    publisher: str
    url: str
    published_at: str | None
    source_kind: SourceKind
    evidence_snippet: str
    peer_region: str = ""

    def to_dict(self) -> dict[str, str | None]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "publisher": self.publisher,
            "url": self.url,
            "published_at": self.published_at,
        }


class CaseSearchProvider(Protocol):
    """A search integration returns documents; it never writes report prose itself."""

    def search(self, query: CaseSearchQuery) -> list[CaseSearchDocument]: ...


PREFERRED_SOURCE_KINDS = frozenset({
    SourceKind.PUBLIC_INSTITUTION,
    SourceKind.LOCAL_GOVERNMENT,
    SourceKind.OPERATOR,
    SourceKind.RESEARCH,
})


def build_case_search_queries(*, content_type: str, peer_regions: list[str]) -> list[CaseSearchQuery]:
    if not content_type.strip():
        raise ValueError("content_type은 비어 있을 수 없습니다.")
    unique_regions = list(dict.fromkeys(region.strip() for region in peer_regions if region.strip()))
    if not unique_regions:
        raise ValueError("최소 한 개의 Peer 지역이 필요합니다.")
    code = content_type.strip()
    # The content type is carried as a code, but the search text has to read the
    # way a Korean source would write it.
    label = CONTENT_TYPE_LABELS.get(code, code)
    return [
        CaseSearchQuery(
            peer_region=region,
            content_type=code,
            query=f"{region} {label} 관광사업 콘텐츠 운영 성과",
        )
        for region in unique_regions
    ]


def screen_case_documents(documents: list[CaseSearchDocument], *, source_id_prefix: str = "source") -> list[SupportedCaseSource]:
    """Keep only attributable, HTTPS, evidence-bearing sources for the LLM context."""
    approved: list[SupportedCaseSource] = []
    seen_urls: set[str] = set()
    for document in documents:
        if document.source_kind not in PREFERRED_SOURCE_KINDS:
            continue
        if (
            not _is_https_url(document.url)
            or not document.title.strip()
            or not document.publisher.strip()
            or not document.snippet.strip()
            or not document.published_at
            or not document.published_at.strip()
        ):
            continue
        normalized_url = document.url.strip()
        if normalized_url in seen_urls:
            continue
        seen_urls.add(normalized_url)
        approved.append(SupportedCaseSource(
            source_id=f"{source_id_prefix}-{len(approved) + 1}",
            title=document.title.strip(),
            publisher=document.publisher.strip(),
            url=normalized_url,
            published_at=document.published_at.strip(),
            source_kind=document.source_kind,
            evidence_snippet=document.snippet.strip(),
            peer_region=document.peer_region.strip(),
        ))
    return approved


def _is_https_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme == "https" and bool(parsed.netloc)
