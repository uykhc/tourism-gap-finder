"""유사 지역 탐색 (과제 1 · PeerFinder)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..services import artifacts
from ..deps import RegionIdPath
from ..schemas.peers import PeerResult

router = APIRouter(prefix="/regions", tags=["peers"])


@router.get(
    "/{region_id}/peers",
    response_model=PeerResult,
    summary="구조적으로 유사한 지역",
)
def get_peers(
    region_id: RegionIdPath,
    k: int = Query(default=15, ge=1, le=50, description="최대 개수"),
    min_similarity: float = Query(
        default=0.40, ge=0.0, le=1.0, description="유사도 하한"
    ),
) -> PeerResult:
    """구조적 여건이 비슷한 지역 목록.

    반환 개수는 0~k로 가변이다.
    """
    return PeerResult.model_validate(artifacts.peers(region_id, k=k, min_similarity=min_similarity))
