"""전국 관광자원 배치 수집.

한 번 돌려 두면 data/raw/ 에 캐시가 쌓이고, 이후 분석은 API 호출 없이
오프라인으로 반복 실행할 수 있다.

    python -m tourgap.collect --all
    python -m tourgap.collect --all --refresh   # 캐시 무시하고 다시 수집

수집 단위는 '시군구'가 아니라 '콘텐츠 유형'이다. 이유는
KorServiceClient.fetch_all_resources_by_type 의 주석을 참고할 것.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from dotenv import load_dotenv

from .config import PROJECT_ROOT, RAW_DIR, data_go_kr_key
from .sources.kto_kor import CONTENT_TYPES, KorServiceClient, TourApiError

TOURAPI_REGIONS_PATH = RAW_DIR / "tourapi_regions.json"
RESOURCES_DIR = RAW_DIR / "resources_by_type"
LCLS_PATH = RAW_DIR / "lcls_codes.json"


def collect_tourapi_regions(client: KorServiceClient, *, refresh: bool) -> list[dict]:
    """TourAPI 지역코드 마스터.

    분석의 지역 단위는 법정동 코드지만, 이 표는 지역명을 붙이고
    두 코드체계를 대조하는 데 쓴다.
    """
    if TOURAPI_REGIONS_PATH.exists() and not refresh:
        return json.loads(TOURAPI_REGIONS_PATH.read_text(encoding="utf-8"))

    rows: list[dict] = []
    for province in client.fetch_provinces():
        for sigungu in client.fetch_sigungu(province["area_code"]):
            rows.append(
                {
                    "tourapi_region_id": (
                        f"{sigungu['area_code']}-{sigungu['sigungu_code']}"
                    ),
                    "province_name": province["province_name"],
                    **sigungu,
                }
            )
        print(f"  {province['province_name']}", flush=True)
        time.sleep(0.1)

    TOURAPI_REGIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOURAPI_REGIONS_PATH.write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return rows


def collect_lcls_codes(client: KorServiceClient, *, refresh: bool) -> dict:
    """신분류체계 대분류/중분류 이름표."""
    if LCLS_PATH.exists() and not refresh:
        return json.loads(LCLS_PATH.read_text(encoding="utf-8"))

    names: dict[str, str] = {}
    for major in client.fetch_lcls_codes():
        names[major["code"]] = major["name"]
        for minor in client.fetch_lcls_codes(major["code"]):
            names[minor["code"]] = minor["name"]
        time.sleep(0.1)

    LCLS_PATH.parent.mkdir(parents=True, exist_ok=True)
    LCLS_PATH.write_text(
        json.dumps(names, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return names


def collect_resources(client: KorServiceClient, *, refresh: bool) -> int:
    """콘텐츠 유형별 전국 자원."""
    RESOURCES_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    failures: list[tuple[str, str]] = []

    for content_type_id, label in CONTENT_TYPES.items():
        path = RESOURCES_DIR / f"{content_type_id}.json"
        if path.exists() and not refresh:
            count = len(json.loads(path.read_text(encoding="utf-8")))
            total += count
            print(f"  {label}({content_type_id}) … 캐시 {count:,}건", flush=True)
            continue

        print(f"  {label}({content_type_id}) … 수집 중", flush=True)
        try:
            items = client.fetch_all_resources_by_type(content_type_id)
        except TourApiError as exc:
            failures.append((label, str(exc)))
            print(f"  {label}({content_type_id}) … 실패: {exc}", flush=True)
            continue

        path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        total += len(items)
        print(f"  {label}({content_type_id}) … {len(items):,}건", flush=True)
        time.sleep(0.2)

    print(f"\n수집 완료: {total:,}건")
    if failures:
        print(f"실패 {len(failures)}건:")
        for label, message in failures:
            print(f"  - {label}: {message}")
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="전국 관광자원 수집")
    parser.add_argument("--all", action="store_true", help="자원까지 수집")
    parser.add_argument("--refresh", action="store_true", help="캐시를 무시하고 다시 받는다")
    args = parser.parse_args(argv)

    load_dotenv(PROJECT_ROOT / ".env")
    client = KorServiceClient(data_go_kr_key())

    print("[1/3] TourAPI 지역코드")
    regions = collect_tourapi_regions(client, refresh=args.refresh)
    print(f"  시군구 {len(regions)}개\n")

    print("[2/3] 신분류체계 코드")
    names = collect_lcls_codes(client, refresh=args.refresh)
    print(f"  분류 {len(names)}개\n")

    if not args.all:
        print("자원 수집을 하려면 --all 을 붙이세요.")
        return 0

    print("[3/3] 전국 관광자원 (콘텐츠 유형별)")
    collect_resources(client, refresh=args.refresh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
