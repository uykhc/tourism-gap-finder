"""유사 지역 탐색 (과제 1 · PeerFinder)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from .. import examples
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
    # TODO(실연결): tourgap.peers.TourgapPeerFinder(features).find_peers(region_id, k=k)
    #   provenance는 Provenance.to_rows()의 한글 키를 영문 키로 변환해 싣는다.
    del region_id
    return PeerResult.model_validate(
        examples.peer_result(k=k, min_similarity=min_similarity)
    )
