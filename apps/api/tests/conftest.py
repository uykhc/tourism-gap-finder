from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.api.app.deps import current_user
from apps.api.app.main import app


@pytest.fixture(scope="session", autouse=True)
def authenticated_api_client() -> None:
    """Most endpoint tests exercise domain behavior, not JWT decoding."""
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(id=1)
    yield
    app.dependency_overrides.pop(current_user, None)
