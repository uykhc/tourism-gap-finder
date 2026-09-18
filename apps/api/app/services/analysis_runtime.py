"""분석 패키지와 API 키에 접근하는 유일한 지점.

`import hankkeut_*`를 여기 한 곳에 모아 감싼다. 그래서 분석 패키지가 설치되지
않은 환경에서도 앱이 뜨고, 지역 표·산출물만 쓰는 엔드포인트와 테스트는 그대로
동작한다. 패키지나 키가 없으면 그 사실을 담은 503이 필요한 엔드포인트에서만
드러난다.

키가 없을 때 모의 데이터를 돌려주지 않는다. 0이나 가짜 값이 섞이면 순위가
뒤집히고, 화면은 그것을 실제 분석 결과와 구별할 수 없다.
"""

from __future__ import annotations

import importlib
import os
from types import ModuleType

from fastapi import HTTPException

#: 설치 명령을 안내할 때 쓰는 패키지별 경로.
_INSTALL_PATHS = {
    "hankkeut_calculation": "data/analysis/calculation",
    "hankkeut_evaluation": "data/analysis/evaluation",
    "hankkeut_similarity": "data/analysis/similarity",
    "hankkeut_contracts": "contracts",
}


def require_module(module_name: str, *, feature: str) -> ModuleType:
    """분석 모듈을 가져온다. 없으면 무엇을 설치해야 하는지 담아 503."""
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        root = module_name.split(".")[0]
        path = _INSTALL_PATHS.get(root, root)
        raise HTTPException(
            503,
            detail=(
                f"{feature}에 필요한 분석 패키지가 설치되지 않았습니다: {root}. "
                f"`pip install -e {path}`를 실행하세요."
            ),
        ) from exc


def require_env(*names: str, feature: str) -> str:
    """환경변수 중 먼저 설정된 값을 돌려준다. 없으면 어떤 키가 필요한지 담아 503."""
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    raise HTTPException(
        503,
        detail=f"{feature}에 필요한 API 키가 설정되지 않았습니다: {' 또는 '.join(names)}",
    )


def has_env(*names: str) -> bool:
    return any(os.getenv(name, "").strip() for name in names)
