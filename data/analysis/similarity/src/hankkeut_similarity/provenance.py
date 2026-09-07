"""어떤 값이 실데이터이고 어떤 값이 proxy/mock인지 추적한다.

공모전 산출물이므로 "이 숫자가 어디서 왔는가"를 결과 화면에서 바로
확인할 수 있어야 한다. 각 데이터 소스는 자기 상태를 여기에 등록하고
리포트는 그 목록을 그대로 출력한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SourceType(str, Enum):
    #: 목적에 맞는 공식 API/통계를 그대로 사용
    REAL = "real"
    #: 실데이터지만 원래 재고 싶던 것의 대리 지표 (예: 직선거리 → 접근성)
    PROXY = "proxy"
    #: 실제 공공데이터지만 API가 아니라 정적 테이블로 관리 (예: 해안 여부)
    STATIC_REFERENCE = "static_reference"
    #: 값 자체가 가짜. 파이프라인을 돌리기 위한 자리 채우기
    MOCK = "mock"

    @property
    def badge(self) -> str:
        return {
            SourceType.REAL: "실데이터",
            SourceType.PROXY: "proxy",
            SourceType.STATIC_REFERENCE: "정적참조",
            SourceType.MOCK: "MOCK",
        }[self]


@dataclass
class SourceRecord:
    """한 데이터 소스에 대한 설명."""

    name: str
    source_type: SourceType
    endpoint: str
    reference_period: str
    note: str = ""
    row_count: int | None = None


@dataclass
class Provenance:
    """실행 한 번 동안 사용된 소스 목록."""

    records: list[SourceRecord] = field(default_factory=list)

    def add(self, record: SourceRecord) -> None:
        # 같은 이름이 다시 등록되면 최신 정보로 교체한다.
        self.records = [r for r in self.records if r.name != record.name]
        self.records.append(record)

    def has_mock(self) -> bool:
        return any(r.source_type is SourceType.MOCK for r in self.records)

    def mock_names(self) -> list[str]:
        return [r.name for r in self.records if r.source_type is SourceType.MOCK]

    def to_rows(self) -> list[dict[str, object]]:
        return [
            {
                "소스": r.name,
                "신뢰도": r.source_type.badge,
                "엔드포인트/출처": r.endpoint,
                "기준시점": r.reference_period,
                "행수": r.row_count if r.row_count is not None else "",
                "비고": r.note,
            }
            for r in self.records
        ]
