"""region_id ↔ TourAPI area/sigungu 코드 표를 만든다.

관광 수요·방문자 API는 TourAPI의 `area_code`/`sigungu_code`로 조회하지만
계약에 오가는 키는 법정동 시군구 코드 5자리(`region_id`)다. 그 사이를 잇는
표가 없어서 이 스크립트로 한 번 만들어 커밋한다.

원재료:
  - apps/api/app/data/regions.csv                              (전국 230개)
  - data/analysis/similarity/data/raw/tourapi_regions.json     (234개, gitignore 대상)

원재료 JSON은 커밋되지 않으므로 결과 CSV만 커밋한다. API는 결과 CSV만 읽는다.

`(시도명, 시군구명)`으로 조인하며, TourAPI가 광역시 이름을 줄여 쓰기 때문에
시도명을 먼저 정규화한다. 2026년 인천 개편으로 생긴 구는 TourAPI 목록에 아직
없다. 이 경우 옛 자치구 코드를 대신 넣지 않고 코드를 비워 두고 이유를 적는다.
수요 지수는 백분위 값이라 면적 비율로 나눠 배분할 수 없고, 옛 코드를 그대로
쓰면 서로 다른 지역에 같은 수요값이 붙어 조용히 틀린 비교가 된다.

실행:
    python3 scripts/build_region_code_map.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

REGIONS_CSV = Path("apps/api/app/data/regions.csv")
TOURAPI_JSON = Path("data/analysis/similarity/data/raw/tourapi_regions.json")
OUTPUT_CSV = Path("apps/api/app/data/region_code_map.csv")

#: TourAPI는 광역시 시도명을 줄여 쓴다.
PROVINCE_ALIASES = {
    "서울": "서울특별시",
    "부산": "부산광역시",
    "대구": "대구광역시",
    "인천": "인천광역시",
    "광주": "광주광역시",
    "대전": "대전광역시",
    "울산": "울산광역시",
}

#: 조인에 실패하는 지역과 그 이유. 코드를 비워 두는 근거를 데이터에 남긴다.
UNMAPPED_NOTES = {
    "28125": "2026년 개편(구 중구+동구)으로 신설. TourAPI 지역 목록에 아직 없음",
    "28155": "2026년 개편(구 중구 영종도부)으로 신설. TourAPI 지역 목록에 아직 없음",
    "28275": "2026년 개편(구 서구 분할)으로 신설. TourAPI 지역 목록에 아직 없음",
    "28290": "2026년 개편(구 서구 분할)으로 신설. TourAPI 지역 목록에 아직 없음",
}

FIELDNAMES = ("region_id", "province_name", "region_name", "area_code", "sigungu_code", "note")


def normalize_province(name: str) -> str:
    return PROVINCE_ALIASES.get(name.strip(), name.strip())


def main() -> int:
    regions = list(csv.DictReader(REGIONS_CSV.read_text(encoding="utf-8-sig").splitlines()))
    tourapi = json.loads(TOURAPI_JSON.read_text(encoding="utf-8"))

    by_key: dict[tuple[str, str], dict[str, str]] = {}
    for item in tourapi:
        key = (normalize_province(item["province_name"]), item["sigungu_name"].strip())
        if key in by_key:
            raise SystemExit(f"TourAPI 지역명이 시도 안에서 중복됩니다: {key}")
        by_key[key] = item

    rows: list[dict[str, str]] = []
    unmapped: list[str] = []
    for region in regions:
        region_id = region["region_id"].strip()
        province = region["province_name"].strip()
        name = region["region_name"].strip()
        match = by_key.get((province, name))
        if match is None:
            note = UNMAPPED_NOTES.get(region_id)
            if note is None:
                raise SystemExit(
                    f"TourAPI 코드를 찾지 못했고 사유도 등록되지 않았습니다: "
                    f"{region_id} {province} {name}. 추측으로 채우지 말고 "
                    f"UNMAPPED_NOTES에 근거를 등록하세요."
                )
            unmapped.append(region_id)
            rows.append({
                "region_id": region_id, "province_name": province, "region_name": name,
                "area_code": "", "sigungu_code": "", "note": note,
            })
            continue
        rows.append({
            "region_id": region_id, "province_name": province, "region_name": name,
            "area_code": str(match["area_code"]).strip(),
            "sigungu_code": str(match["sigungu_code"]).strip(),
            "note": "",
        })

    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        # csv defaults to CRLF; keep the file LF like regions.csv.
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(f"saved {OUTPUT_CSV} ({len(rows)} rows)")
    print(f"코드 있음 {len(rows) - len(unmapped)} / 코드 없음 {len(unmapped)}: {', '.join(unmapped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
