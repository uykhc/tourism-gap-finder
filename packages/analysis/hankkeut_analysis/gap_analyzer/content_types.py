"""TourAPI 국문 관광정보 서비스의 콘텐츠 유형 정의."""

from collections import OrderedDict

# 표시 순서를 고정해 실행 시점과 관계없이 CSV/JSON diff가 안정적으로 유지된다.
CONTENT_TYPES: OrderedDict[int, str] = OrderedDict(
    [
        (12, "관광지"),
        (14, "문화시설"),
        (15, "행사/공연/축제"),
        (25, "여행코스"),
        (28, "레포츠"),
        (32, "숙박"),
        (38, "쇼핑"),
        (39, "음식점"),
    ]
)


def content_type_name(content_type_id: int | None) -> str:
    """콘텐츠 유형 ID를 사람이 읽을 수 있는 이름으로 변환한다."""
    if content_type_id is None:
        return "유형 미상"
    return CONTENT_TYPES.get(content_type_id, f"기타({content_type_id})")
