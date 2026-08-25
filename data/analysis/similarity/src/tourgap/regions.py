"""지역 마스터.

분석의 canonical 단위는 KTO 실제 관광자원 응답의
**lDongRegnCd + lDongSignguCd 5자리 코드**다.
TourAPI의 areaCode/sigunguCode를 쓰지 않는 이유:

1. 전국 자원의 약 47%가 areacode/sigungucode가 비어 있다(2026-08-17 확인).
   이 코드로 지역을 나누면 그 자원들이 통째로 사라진다.
2. TourAPI 코드 목록에는 이미 없어진 행정구역이 남아 있다
   (마산시·진해시·청원군·남제주군·북제주군).
3. lDong 계열 코드는 실제 관광자원 행마다 붙어 있어 공급 분석과 같은
   지역 단위를 유지할 수 있다.

일반구(청주시 흥덕구, 창원시 마산합포구 등)는 기초자치단체가 아니므로
모(母) 시로 합친다. 합칠 대상은 **주소로** 판별한다. 주소에 '○○시 ○○구'가
함께 나오면 일반구이고, 그때 모 시 코드는 끝자리를 0으로 바꾼 값이다.
예) 43113 청주시 흥덕구 -> 43110 청주시
    48125 창원시 마산합포구 -> 48120 창원시

끝자리 숫자만 보고 판별하면 안 된다. 증평군(43745)처럼 나중에 신설되어
끝자리가 0이 아닌 군이 있고, 그런 지역은 엉뚱하게 옆 군으로 합쳐진다.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

import pandas as pd

from .config import RAW_DIR, REFERENCE_DIR

RESOURCES_DIR = RAW_DIR / "resources_by_type"
TOURAPI_REGIONS_PATH = RAW_DIR / "tourapi_regions.json"
OVERRIDES_PATH = REFERENCE_DIR / "region_code_overrides.csv"

# 시도 코드(법정동 앞 2자리) -> 시도명.
# 실제 수집 데이터에 나타난 prefix 기준이다(2026-08-17). KTO 실제 자원
# 데이터의 lDongRegnCd/lDongSignguCd는 광주광역시와 전라남도에 prefix 12를
# 쓰므로, 12는 지역명 또는 TourAPI areaCode2 마스터로 다시 분리한다.
# 옛 코드는 과거 캐시를 읽을 때를 대비해 남겨 둔다.
PROVINCE_BY_PREFIX: dict[str, str] = {
    "11": "서울특별시",
    "26": "부산광역시",
    "27": "대구광역시",
    "28": "인천광역시",
    "29": "광주광역시",  # legacy
    "30": "대전광역시",
    "31": "울산광역시",
    "36": "세종특별자치시",
    "41": "경기도",
    "42": "강원도",  # legacy
    "43": "충청북도",
    "44": "충청남도",
    "45": "전라북도",  # legacy
    "46": "전라남도",  # legacy
    "47": "경상북도",
    "48": "경상남도",
    "50": "제주특별자치도",
    "51": "강원특별자치도",
    "52": "전북특별자치도",
}

GWANGJU_DISTRICTS = {"동구", "서구", "남구", "북구", "광산구"}

KTO_PROVINCE_NAMES: dict[str, str] = {
    "서울": "서울특별시",
    "부산": "부산광역시",
    "대구": "대구광역시",
    "인천": "인천광역시",
    "광주": "광주광역시",
    "대전": "대전광역시",
    "울산": "울산광역시",
    "세종특별자치시": "세종특별자치시",
    "경기도": "경기도",
    "강원특별자치도": "강원특별자치도",
    "충청북도": "충청북도",
    "충청남도": "충청남도",
    "전라남도": "전라남도",
    "경상북도": "경상북도",
    "경상남도": "경상남도",
    "전북특별자치도": "전북특별자치도",
    "제주특별자치도": "제주특별자치도",
}

_SIGUNGU_PATTERN = re.compile(r"^(\S+?)(시|군|구)$")


@dataclass(frozen=True)
class RegionMaster:
    frame: pd.DataFrame  # region_id, province_name, region_name, admin_type

    def resolve(self, query: str) -> pd.Series:
        """'경주시', '경상북도 경주시', '47130' 을 한 행으로 해석한다."""
        text = query.strip()
        frame = self.frame

        exact_id = frame[frame["region_id"] == text]
        if len(exact_id) == 1:
            return exact_id.iloc[0]

        full = frame[(frame["province_name"] + " " + frame["region_name"]) == text]
        if len(full) == 1:
            return full.iloc[0]

        by_name = frame[frame["region_name"] == text]
        if len(by_name) == 1:
            return by_name.iloc[0]
        if len(by_name) > 1:
            options = ", ".join(
                f"{r.province_name} {r.region_name}" for r in by_name.itertuples()
            )
            raise LookupError(f"'{text}'가 여러 곳입니다. 시도명을 함께 쓰세요: {options}")

        partial = frame[frame["region_name"].str.contains(text, regex=False)]
        if len(partial) == 1:
            return partial.iloc[0]
        raise LookupError(f"'{text}'에 해당하는 시군구를 찾지 못했습니다.")


def parent_city_code(ldong_code: str) -> str:
    """일반구 코드 -> 모 시 코드. (43113 -> 43110)"""
    code = str(ldong_code).strip()
    if len(code) != 5 or not code.isdigit():
        return ""
    return code[:4] + "0"


def parse_address(address: str) -> tuple[str, str, str] | None:
    """주소를 (시도, 시군구, 일반구) 로 나눈다. 일반구가 없으면 빈 문자열.

    '충청북도 청주시 흥덕구 가경동' -> ('충청북도', '청주시', '흥덕구')
    '경상북도 경주시 북군3길 12-1'  -> ('경상북도', '경주시', '')
    '세종특별자치시 연서면 …'        -> ('세종특별자치시', '세종특별자치시', '')
    """
    tokens = str(address).split()
    if len(tokens) < 2:
        return None

    province = tokens[0]
    # 세종특별자치시는 시도명이 곧 기초자치단체명이다.
    if province.startswith("세종"):
        return province, province, ""

    sigungu = ""
    gu = ""
    for token in tokens[1:4]:
        matched = _SIGUNGU_PATTERN.match(token)
        if not matched:
            continue
        if not sigungu:
            sigungu = token
            continue
        # 이미 시를 잡은 상태에서 또 '구'가 나오면 일반구다.
        if sigungu.endswith("시") and token.endswith("구"):
            gu = token
        break

    if not sigungu:
        return None
    return province, sigungu, gu


def canonical_province_name(name: str) -> str:
    """KTO 지역코드의 짧은 시도명을 공식 표기 쪽으로 정규화한다."""
    text = str(name).strip()
    return KTO_PROVINCE_NAMES.get(text, text)


def load_tourapi_region_lookup() -> dict[tuple[str, str], tuple[str, str]]:
    """TourAPI areaCode2 시군구 마스터를 이름 보정용 lookup으로 읽는다.

    분석 키는 결측이 적은 법정동 시군구 코드 5자리지만, 지역명은 가능하면
    KTO가 제공한 areaCode2 마스터를 따른다. areaCode2에는 폐지 지역도 남아
    있으므로 이 표만으로 분석 단위를 만들지는 않는다.
    """
    if not TOURAPI_REGIONS_PATH.exists():
        return {}
    rows = json.loads(TOURAPI_REGIONS_PATH.read_text(encoding="utf-8"))
    lookup: dict[tuple[str, str], tuple[str, str]] = {}
    for row in rows:
        area_code = str(row.get("area_code") or "").strip()
        sigungu_code = str(row.get("sigungu_code") or "").strip()
        province_name = canonical_province_name(row.get("province_name", ""))
        sigungu_name = str(row.get("sigungu_name") or "").strip()
        if area_code and sigungu_code and province_name and sigungu_name:
            lookup[(area_code, sigungu_code)] = (province_name, sigungu_name)
    return lookup


def build_code_rollup(resources: pd.DataFrame) -> dict[str, str]:
    """법정동 코드 -> 기초자치단체 코드.

    주소가 '시 + 구'로 읽히는 코드만 모 시로 올린다. 코드 하나에 여러
    주소 형태가 섞일 수 있으므로 최빈값으로 정한다.
    """
    votes: dict[str, Counter] = defaultdict(Counter)
    for code, address in zip(
        resources["ldong_code"], resources["address"], strict=True
    ):
        if not code:
            continue
        parsed = parse_address(address)
        if parsed is None:
            continue
        votes[code][bool(parsed[2])] += 1

    rollup: dict[str, str] = {}
    for code, counter in votes.items():
        is_district = counter.most_common(1)[0][0]
        rollup[code] = parent_city_code(code) if is_district else code
    return rollup


def admin_type(region_name: str, province_name: str) -> str:
    """시 / 군 / 자치구 / 특별자치시.

    peer 탐색에서 '군'에 광역시 자치구가 붙는 사고를 막는 데 쓴다.
    """
    if region_name.endswith("군"):
        return "군"
    if region_name.endswith("구"):
        return "자치구"
    if region_name.endswith("시"):
        return "특별자치시" if province_name == region_name else "시"
    return "기타"


def load_resources() -> pd.DataFrame:
    """수집된 전국 관광자원을 하나의 DataFrame으로."""
    if not RESOURCES_DIR.exists():
        raise FileNotFoundError(
            f"{RESOURCES_DIR} 가 없습니다. 먼저 `python -m tourgap.collect --all`."
        )
    frames = []
    for path in sorted(RESOURCES_DIR.glob("*.json")):
        records = json.loads(path.read_text(encoding="utf-8"))
        if records:
            frames.append(pd.DataFrame.from_records(records))
    if not frames:
        raise FileNotFoundError("수집된 자원이 없습니다.")

    frame = pd.concat(frames, ignore_index=True)
    frame = frame.drop_duplicates(subset=["content_id"], keep="first")
    rollup = build_code_rollup(frame)
    frame["region_id"] = frame["ldong_code"].map(lambda c: rollup.get(c, ""))
    return frame


def build_region_master(resources: pd.DataFrame) -> pd.DataFrame:
    """KTO 실제 자원 데이터 기준 지역 마스터를 만든다.

    분석 단위는 실제 자원에 붙은 법정동 시군구 코드 5자리다. 다만 주소
    문자열에는 '전남광주통합특별시'처럼 비공식 표기가 섞여 있으므로,
    지역명은 TourAPI areaCode2 마스터를 우선 사용하고 없는 경우에만
    주소를 fallback으로 쓴다.
    """
    names: dict[str, Counter] = defaultdict(Counter)
    tourapi_regions = load_tourapi_region_lookup()
    for row in resources.itertuples():
        region_id = row.region_id
        if not region_id:
            continue
        key = (str(row.area_code or "").strip(), str(row.sigungu_code or "").strip())
        if key in tourapi_regions:
            names[region_id][tourapi_regions[key]] += 1
            continue

        parsed = parse_address(row.address)
        if parsed:
            province_name, region_name, _ = parsed
            names[region_id][
                (
                    _canonical_province_for_region(
                        region_id, province_name, region_name
                    ),
                    region_name,
                )
            ] += 1

    rows = []
    for region_id, counter in names.items():
        if not counter:
            continue
        (province_name, region_name), _ = counter.most_common(1)[0]
        canonical_province = _canonical_province_for_region(
            region_id, province_name, region_name
        )
        rows.append(
            {
                "region_id": region_id,
                "province_name": canonical_province,
                "region_name": region_name,
                "admin_type": admin_type(region_name, canonical_province),
                "resource_count": int((resources["region_id"] == region_id).sum()),
            }
        )

    frame = pd.DataFrame(rows).sort_values("region_id").reset_index(drop=True)
    return _apply_overrides(frame)


def _canonical_province_for_region(
    region_id: str, province_name: str, region_name: str
) -> str:
    """법정동 prefix와 지역명으로 시도명을 정규화한다."""
    if region_id.startswith("12"):
        return "광주광역시" if region_name in GWANGJU_DISTRICTS else "전라남도"
    return PROVINCE_BY_PREFIX.get(region_id[:2], canonical_province_name(province_name))


def _apply_overrides(frame: pd.DataFrame) -> pd.DataFrame:
    if not OVERRIDES_PATH.exists():
        return frame
    overrides = pd.read_csv(OVERRIDES_PATH, dtype=str).fillna("")
    frame = frame.set_index("region_id")
    for row in overrides.itertuples():
        if row.region_id not in frame.index:
            continue
        if row.province_name:
            frame.loc[row.region_id, "province_name"] = row.province_name
        if row.region_name:
            frame.loc[row.region_id, "region_name"] = row.region_name
            frame.loc[row.region_id, "admin_type"] = admin_type(
                row.region_name, frame.loc[row.region_id, "province_name"]
            )
    return frame.reset_index()


def load_region_master() -> RegionMaster:
    return RegionMaster(build_region_master(load_resources()))


def load_lcls_names() -> dict[str, str]:
    path = RAW_DIR / "lcls_codes.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
