"""도메인별 라우터."""

from . import analysis, auth, compare, peers, provinces, regions, reports, users

ALL_ROUTERS = (
    auth.router,
    users.router,
    provinces.router,
    regions.router,
    peers.router,
    analysis.router,
    reports.router,
    compare.router,
)

__all__ = [
    "ALL_ROUTERS",
    "analysis",
    "auth",
    "compare",
    "peers",
    "provinces",
    "regions",
    "reports",
    "users",
]
