"""SGIS 도시화지역 경계 원자료에서 시군구별 도시화 면적을 읽는다.

도시화율 계산에는 폴리곤 자체가 아니라 DBF의 ``SIGUNGU_CD``와
``UA_AREA``만 필요하다. 무거운 GIS 의존성을 추가하지 않기 위해 DBF를
직접 읽으며, 원본 SHP/PRJ는 출처와 공간 검증을 위해 함께 보관한다.
"""

from __future__ import annotations

import struct
import zipfile
from pathlib import Path

import pandas as pd

from ..config import RAW_DIR


DEFAULT_URBAN_BOUNDARY = RAW_DIR / "urbanization" / "BND_UA_PG.zip"


class UrbanBoundaryError(ValueError):
    """도시화지역 경계 원자료의 형식이 예상과 다르다."""


def load_urban_area_by_sgis_code(
    path: str | Path = DEFAULT_URBAN_BOUNDARY,
) -> pd.DataFrame | None:
    """SGIS 시군구 코드별 도시화지역 면적(km²)을 반환한다.

    파일이 없으면 ``None``을 반환해 기존 결측 정책을 유지한다. 파일이
    존재하지만 형식이 잘못됐으면 조용히 무시하지 않고 예외를 던진다.
    """
    source = Path(path)
    if not source.exists():
        return None

    if source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as archive:
            members = [
                name for name in archive.namelist() if name.lower().endswith(".dbf")
            ]
            if len(members) != 1:
                raise UrbanBoundaryError(f"도시화지역 ZIP에는 DBF가 하나여야 합니다: {members}")
            raw = archive.read(members[0])
    elif source.suffix.lower() == ".dbf":
        raw = source.read_bytes()
    else:
        raise UrbanBoundaryError(f"지원하지 않는 도시화지역 파일 형식: {source}")

    records = _read_dbf(raw)
    required = {"BASE_DATE", "SIGUNGU_CD", "UA_AREA"}
    missing = required - set(records.columns)
    if missing:
        raise UrbanBoundaryError(f"도시화지역 DBF 필수 컬럼이 없습니다: {sorted(missing)}")

    records["sgis_adm_cd"] = records["SIGUNGU_CD"].astype(str).str.strip()
    records["urban_area_km2"] = (
        pd.to_numeric(records["UA_AREA"], errors="coerce") / 1_000_000
    )
    if records["sgis_adm_cd"].eq("").any() or records["urban_area_km2"].isna().any():
        raise UrbanBoundaryError("SIGUNGU_CD 또는 UA_AREA에 비어 있거나 숫자가 아닌 값이 있습니다.")
    if (records["urban_area_km2"] < 0).any():
        raise UrbanBoundaryError("UA_AREA에 음수 면적이 있습니다.")

    grouped = records.groupby("sgis_adm_cd", as_index=False).agg(
        urban_area_km2=("urban_area_km2", "sum"),
        urban_polygon_count=("urban_area_km2", "size"),
        urban_reference_date=("BASE_DATE", "max"),
    )
    return grouped


def _read_dbf(raw: bytes) -> pd.DataFrame:
    if len(raw) < 33:
        raise UrbanBoundaryError("DBF 헤더가 너무 짧습니다.")
    record_count = struct.unpack("<I", raw[4:8])[0]
    header_length = struct.unpack("<H", raw[8:10])[0]
    record_length = struct.unpack("<H", raw[10:12])[0]
    if header_length > len(raw) or record_length < 2:
        raise UrbanBoundaryError("DBF 헤더 길이 또는 레코드 길이가 잘못됐습니다.")

    fields: list[tuple[str, int]] = []
    offset = 32
    while offset < header_length and raw[offset] != 0x0D:
        if offset + 32 > len(raw):
            raise UrbanBoundaryError("DBF 필드 정의가 잘렸습니다.")
        name = raw[offset : offset + 11].split(b"\0", 1)[0].decode("ascii")
        fields.append((name, raw[offset + 16]))
        offset += 32

    rows: list[dict[str, str]] = []
    for index in range(record_count):
        start = header_length + index * record_length
        record = raw[start : start + record_length]
        if len(record) != record_length:
            raise UrbanBoundaryError(f"DBF {index + 1}번째 레코드가 잘렸습니다.")
        if record[:1] == b"*":
            continue
        cursor = 1
        row: dict[str, str] = {}
        for name, length in fields:
            value = record[cursor : cursor + length]
            cursor += length
            row[name] = value.decode("cp949").strip()
        rows.append(row)
    return pd.DataFrame(rows, columns=[name for name, _ in fields])
