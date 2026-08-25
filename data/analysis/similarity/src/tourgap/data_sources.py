"""과제 1 원자료 로딩 어댑터.

외부 데이터 취득과 원본 로딩만 담당한다. feature 계산은
feature_builder.py와 sources/structural.py에서 처리한다.
"""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd

from .config import RAW_DIR
from .sources.sgis import SgisClient

KMA_NORMALS_FILESET_URL = (
    "https://data.kma.go.kr/climate/average30Years/"
    "selectAverage30YearsKoreaFileset.do?pgmNo=716"
)
KMA_NORMALS_DOWNLOAD_URL = "https://data.kma.go.kr/download/downloadNormDataFile.do"
KMA_STATION_LIST_URL = "https://data.kma.go.kr/tmeta/stn/selectStnList.do"
KMA_NORMALS_PERIODS = {
    "daily": ("day", "일별"),
    "monthly": ("month", "월별"),
    "seasonal": ("season", "계절별"),
    "annual": ("year", "연별"),
    "dekad": ("sun", "순별"),
    "weekly": ("week", "주별"),
}


@dataclass(frozen=True)
class RawDataPaths:
    sgis_boundary: Path | None = None
    urban_boundary: Path | None = None
    coastline: Path | None = None
    land_cover: Path | None = None
    dem: Path | None = None
    climate_normals: Path | None = None


class MissingRawDataError(FileNotFoundError):
    """필수 원자료 파일이 준비되지 않았다."""


def require_existing_paths(paths: RawDataPaths) -> None:
    missing = [
        f"{name}={path}"
        for name, path in paths.__dict__.items()
        if path is not None and not Path(path).exists()
    ]
    if missing:
        raise MissingRawDataError("공간/기후 원자료 파일을 찾을 수 없습니다: " + ", ".join(missing))


def load_table(
    path: str | Path, *, dtype: dict[str, Any] | None = None
) -> pd.DataFrame:
    """CSV/Parquet 원자료를 로딩한다."""
    source = Path(path)
    if not source.exists():
        raise MissingRawDataError(f"원자료 파일이 없습니다: {source}")
    if source.suffix.lower() == ".parquet":
        return pd.read_parquet(source)
    if source.suffix.lower() in {".xls", ".xlsx"}:
        return pd.read_excel(source, dtype=dtype)
    return pd.read_csv(source, dtype=dtype)


class SgisDataSource:
    """SGIS raw API 접근 계층."""

    def __init__(self, client: SgisClient) -> None:
        self._client = client

    def population(
        self, *, year: str, adm_cd: str | None = None
    ) -> list[dict[str, Any]]:
        return self._client.fetch_population(year=year, adm_cd=adm_cd, low_search="1")

    def boundary(self, *, year: str, adm_cd: str | None = None) -> dict[str, Any]:
        return self._client.fetch_boundary(year=year, adm_cd=adm_cd, low_search="1")

    def company(
        self,
        *,
        year: str,
        adm_cd: str | None = None,
        class_code: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._client.fetch_company(
            year=year,
            adm_cd=adm_cd,
            class_code=class_code,
            low_search="1",
        )

    def industry_codes(
        self, *, class_deg: str, class_code: str | None = None
    ) -> list[dict[str, Any]]:
        return self._client.fetch_industry_codes(
            class_deg=class_deg, class_code=class_code
        )


class KmaNormalsDownloadError(RuntimeError):
    """기상청 기후평년값 파일셋 자동 다운로드 실패."""


class KmaClimateNormalsSource:
    """기상청 1991~2020 기후평년값 파일셋 로딩.

    API 일자료를 재계산하지 않는다. 공식 기상자료개방포털 파일셋 페이지에서
    다운로드 링크를 찾아 원본 파일을 저장하거나, 이미 받은 CSV/Excel/Parquet
    파일을 읽는다.
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        *,
        fileset_url: str = KMA_NORMALS_FILESET_URL,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.cache_dir = cache_dir or RAW_DIR / "kma"
        self.fileset_url = fileset_url
        self.timeout_seconds = timeout_seconds

    def climate_normals(self, path: str | Path) -> pd.DataFrame:
        return load_table(path, dtype={"station_id": str})

    def station_metadata(self) -> pd.DataFrame:
        """기상청 공식 지점정보 HTML에서 지점 좌표를 읽는다."""
        html = _fetch_station_list_html(timeout_seconds=self.timeout_seconds)
        tables = pd.read_html(StringIO(html))
        if not tables:
            raise KmaNormalsDownloadError("기상청 지점정보 테이블을 찾지 못했습니다.")
        frame = tables[0].rename(
            columns={
                "지점번호": "station_id",
                "지점명": "station_name",
                "위도": "latitude",
                "경도": "longitude",
                "관측장소 해발고도(m)": "station_elevation_m",
            }
        )
        required = [
            "station_id",
            "station_name",
            "latitude",
            "longitude",
            "station_elevation_m",
        ]
        missing = [column for column in required if column not in frame.columns]
        if missing:
            raise KmaNormalsDownloadError(f"기상청 지점정보 필수 컬럼 누락: {missing}")
        frame = frame[required].copy()
        frame["station_id"] = (
            pd.to_numeric(frame["station_id"], errors="coerce")
            .astype("Int64")
            .astype(str)
        )
        for column in ["latitude", "longitude", "station_elevation_m"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame = frame.dropna(subset=["latitude", "longitude"])
        return frame.drop_duplicates("station_id", keep="first").reset_index(drop=True)

    def discover_downloads(self) -> dict[str, str]:
        """공식 파일셋 페이지에서 1991~2020 다운로드 요청을 구성한다.

        반환 키는 `daily`, `monthly`, `seasonal`, `annual`, `dekad`, `weekly`
        이다. 정적 링크가 있으면 링크를 사용하고, 기상청 공식 JS의
        `average30yearsKorea_1991_<type>.xlsx` 규칙이 확인되면 다운로드
        endpoint와 form 값을 query string으로 담은 URL을 반환한다.
        """
        html = _fetch_text(self.fileset_url, timeout_seconds=self.timeout_seconds)
        row = _extract_1991_2020_row(html)
        links = _extract_download_links(row, self.fileset_url)
        if not links:
            links = _construct_kma_normals_downloads(html)
        if not links:
            raise KmaNormalsDownloadError(
                "1991~2020 기후평년값 파일셋 다운로드 요청 정보를 HTML에서 찾지 못했습니다. "
                "공식 페이지 구조가 바뀌었거나 JavaScript 렌더링이 필요합니다."
            )
        return links

    def download(self, period: str = "annual") -> Path:
        """선택한 파일셋을 cache_dir에 저장하고 경로를 반환한다."""
        links = self.discover_downloads()
        if period not in links:
            raise KmaNormalsDownloadError(
                f"{period!r} 파일셋 링크가 없습니다. 탐색된 항목: {sorted(links)}"
            )

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        url = links[period]
        suffix = _download_suffix(url)
        target = self.cache_dir / f"kma_climate_normals_1991_2020_{period}{suffix}"
        _download_binary(url, target, timeout_seconds=self.timeout_seconds)
        return target


def _fetch_text(url: str, *, timeout_seconds: float) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "TourGap/0.1"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        content_type = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(content_type, errors="replace")


def _fetch_station_list_html(*, timeout_seconds: float) -> str:
    data = urllib.parse.urlencode(
        {
            "pgmNo": "123",
            "pageIndex": "1",
            "schListCnt": "1000",
            "serviceSe": "F00101",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        KMA_STATION_LIST_URL,
        data=data,
        headers={
            "User-Agent": "TourGap/0.1",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        content_type = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(content_type, errors="replace")


def _download_binary(url: str, target: Path, *, timeout_seconds: float) -> None:
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    post_fields = {
        key: values[0]
        for key, values in query.items()
        if key in {"distFileName", "realFileName"}
    }
    if post_fields:
        clean_url = urllib.parse.urlunparse(parsed._replace(query=""))
        data = urllib.parse.urlencode(post_fields).encode("utf-8")
        request = urllib.request.Request(
            clean_url,
            data=data,
            headers={
                "User-Agent": "TourGap/0.1",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
    else:
        request = urllib.request.Request(url, headers={"User-Agent": "TourGap/0.1"})

    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = response.read()
        content_type = response.headers.get("Content-Type", "")
    if "로그인이 필요".encode("utf-8") in payload or "text/html" in content_type.lower():
        raise KmaNormalsDownloadError(
            "다운로드 응답이 파일이 아니라 HTML입니다. 로그인 또는 세션이 필요할 수 있습니다."
        )
    target.write_bytes(payload)


def _download_suffix(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    for key in ("distFileName", "realFileName"):
        if query.get(key):
            suffix = Path(query[key][0]).suffix
            if suffix:
                return suffix
    return Path(parsed.path).suffix or ".download"


def _extract_1991_2020_row(html: str) -> str:
    normalized = re.sub(r"\s+", " ", html)
    match = re.search(
        r"1991\s*[~\-]\s*2020.*?(?=</tr>|1961\s*[~\-]\s*1990|1971\s*[~\-]\s*2000|1981\s*[~\-]\s*2010|$)",
        normalized,
        flags=re.IGNORECASE,
    )
    return match.group(0) if match else ""


def _construct_kma_normals_downloads(html: str) -> dict[str, str]:
    """기상청 공식 JS의 파일명 규칙이 확인될 때 다운로드 URL을 만든다."""
    if "average30yearsKorea_" not in html or "downloadNormDataFile.do" not in html:
        return {}

    result = {}
    for period, (code, label) in KMA_NORMALS_PERIODS.items():
        query = urllib.parse.urlencode(
            {
                "distFileName": f"average30yearsKorea_1991_{code}.xlsx",
                "realFileName": f"우리나라기후평년({label})_1991.xlsx",
            }
        )
        result[period] = f"{KMA_NORMALS_DOWNLOAD_URL}?{query}"
    return result


def _extract_download_links(fragment: str, base_url: str) -> dict[str, str]:
    labels = ("daily", "monthly", "seasonal", "annual", "dekad", "weekly")
    urls: list[str] = []

    for href in re.findall(r"""href=["']([^"']+)["']""", fragment):
        if "javascript" not in href.lower() and href.strip() not in {"#", ""}:
            urls.append(urllib.parse.urljoin(base_url, href))

    for onclick in re.findall(r"""onclick=["']([^"']+)["']""", fragment):
        urls.extend(
            urllib.parse.urljoin(base_url, value)
            for value in re.findall(
                r"""['"]([^'"]+\.(?:zip|csv|xls|xlsx)[^'"]*)['"]""", onclick
            )
        )
        urls.extend(
            urllib.parse.urljoin(base_url, value)
            for value in re.findall(
                r"""['"]([^'"]*download[^'"]*)['"]""", onclick, flags=re.IGNORECASE
            )
        )

    deduped = list(dict.fromkeys(urls))
    return {label: url for label, url in zip(labels, deduped, strict=False)}
