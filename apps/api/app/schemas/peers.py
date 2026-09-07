"""유사 지역(peer) 탐색 응답.

`tourgap.main._write_result`가 저장하는 handoff JSON과 같은 형태다.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .common import ProvenanceRecord, RegionRef

STRUCTURAL_CANDIDATE_WARNING = (
    "이 목록은 구조적으로 유사한 후보입니다. "
    "관광 성과 검증 전에는 '우수 Peer'로 해석하지 않습니다."
)


class PeerItem(RegionRef):
    """유사 지역 한 곳."""

    rank: int = Field(ge=1, examples=[1])
    similarity: float = Field(
        ge=0.0, le=1.0, examples=[0.728], description="exp(-거리). 클수록 유사"
    )
    distance: float = Field(examples=[0.3174], description="표준화된 가중 유클리드 거리")
    feature_weight_used: float = Field(
        examples=[1.0], description="거리 계산에 쓰인 가중치 합"
    )
    missing_feature_count: int = Field(examples=[0], description="결측 변수 수")


class PeerResult(BaseModel):
    """구조적 유사 후보 목록."""

    result_version: str = Field(examples=["2026-09-05"])
    target: RegionRef
    selection_type: str = Field(default="structural_similarity_candidates")
    warning: str = Field(default=STRUCTURAL_CANDIDATE_WARNING)
    requested_k: int = Field(examples=[15])
    min_similarity: float = Field(examples=[0.40])
    peers: list[PeerItem]
    provenance: list[ProvenanceRecord]


class FeatureContribution(BaseModel):
    """변수별 거리 기여도."""

    region_id: str = Field(pattern=r"^\d{5}$", examples=["47110"])
    region_name: str = Field(examples=["포항시"])
    feature: str = Field(examples=["manufacturing_worker_ratio"])
    difference_share: float = Field(
        ge=0.0, le=1.0, examples=[0.2314], description="가중 제곱차 비중"
    )
