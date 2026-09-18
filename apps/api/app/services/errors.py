"""API clients can branch on stable machine-readable error codes."""

from __future__ import annotations

from typing import NoReturn

from fastapi import HTTPException


def report_not_ready(region_id: str, missing: list[str]) -> NoReturn:
    raise HTTPException(
        status_code=409,
        detail={
            "code": "REPORT_NOT_READY",
            "region_id": region_id,
            "missing_artifacts": missing,
            "message": "분석 산출물이 아직 배포 준비 상태가 아닙니다.",
        },
    )
