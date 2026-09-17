# 카카오맵 시군구 콘텐츠 수집

`hankkeut-kakao-regions`는 관광명소 주변 검색이 아니라 행정경계 전체에서 카카오 로컬 API의 장소 카테고리를 수집한다.

관광 콘텐츠 빈칸 분석의 원천 데이터는 `hankkeut-kakao-tourism-content`로 수집한다.
이 명령은 카테고리와 키워드 검색 결과를 `place_id`로 합치고, 음식·숙박·문화관광·체험관광·레저스포츠·쇼핑 6개 유형으로 분류한다.

## 준비물

- Kakao Developers에서 발급한 REST API 키를 로컬 `.env`의 `KAKAO_REST_API_KEY`에 설정한다. 키는 `.env.example`이나 Git에 커밋하지 않는다.
- 수집할 시군구의 WGS84(EPSG:4326) GeoJSON `FeatureCollection`을 준비한다. 각 feature에는 `properties.region_name`이 있어야 한다.

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": { "region_name": "수원시" },
      "geometry": { "type": "Polygon", "coordinates": [[[127.0, 37.2], [127.1, 37.2], [127.1, 37.3], [127.0, 37.2]]] }
    }
  ]
}
```

## 실행

제공한 행정동 GeoJSON을 경기도 31개 시·군 경계로 먼저 변환한다.

```powershell
hankkeut-build-gyeonggi-boundaries `
  --source data/reference/Local_HangJeongDong/hangjeongdong_경기도.geojson `
  --output data/raw/gyeonggi_sigungu.geojson
```

```powershell
hankkeut-kakao-regions `
  --boundaries data/raw/gyeonggi_sigungu.geojson `
  --region-name 수원시 `
  --category CT1
```

기본값은 모든 입력 시군구와 지원 카테고리(`CT1`, `AT4`, `AD5`, `FD6`, `CE7`, `PK6`, `SW8`, `PO3`)를 수집한다. 이 명령은 원본 장소 목록을 운영 DB에 적재하지 않는다.

밀집 지역에서는 결과 한도를 피하기 위해 처음 5 km 격자에서 시작해 필요 시 250 m까지 4분할한다. 출력의 `truncated_tile_count`가 0보다 크면 해당 카테고리는 여전히 누락 가능성이 있으므로 더 작은 `--minimum-tile-meters`로 재수집하거나 분석에서 제외한다.

각 카테고리 결과에는 경계 좌표로 필터링한 장소 목록과 함께 주소 검증 지표도 저장한다. `address_match_count`는 카카오의 도로명/지번 주소에 대상 시·군명이 포함된 건수이고, `address_mismatch_samples`는 경계에는 포함되지만 주소 표기가 다른 사례이므로 수집 후 검토 대상이다.

## 6개 관광 콘텐츠 유형 수집

분석에 사용할 수집은 아래 명령을 사용한다.

```bash
export CONTENT_DATABASE_URL='postgresql://...'
hankkeut-kakao-tourism-content \
  --boundaries data/raw/national_sigungu.geojson \
  --region-name 수원시
```

관광 콘텐츠 수집기는 원본 장소 목록을 JSON 파일로 저장하지 않는다. 수집 실행 이력은
`content_collection_runs`, 지역 마스터는 `regions`, 6개 유형별 장소 수와 품질 지표는
`region_content_counts`에 저장한다. 분석 리포트는 이 DB 집계를 조회한다.

전국 적재용 GeoJSON feature에는 아래 `properties`가 필요하다.

```json
{
  "region_id": "41:115",
  "area_code": "41",
  "sigungu_code": "115",
  "province_name": "경기도",
  "region_name": "수원시"
}
```

분류 규칙과 키워드 사전은 `config/kakao/tourism_content_taxonomy.json`에 있다.
카테고리(`FD6`, `CE7`, `AD5`, `CT1`, `AT4`)는 음식·숙박·문화관광의 기본 후보를 만들고,
체험·레저·쇼핑은 이 파일의 키워드를 각각 행정경계 전체에서 검색한다. 키워드 결과가
카테고리 결과와 겹치면 하나의 `place_id`로 합치며, 키워드 분류를 우선 적용한다.

출력에는 유형별 장소 수, 원본 장소와 발견 카테고리·키워드, 분류 근거, 잘린 격자 수가
함께 저장된다. `is_complete`가 `false`이면 최소 격자에서도 검색 결과가 잘렸으므로 해당
지역·유형의 공급량을 분석에 사용하기 전에 재수집 또는 검토해야 한다.

## 실행 실패와 재수집

수집 시작 시 실행 이력을 `running`으로 만들고, 모든 선택 지역 적재가 끝나면
`completed`로 확정한다. 중간 실패 시 `failed`로 남으므로 분석은 불완전한 실행을 읽지
않는다. 재수집은 새 실행 이력을 만들며, 최신 `completed` 실행이 분석에 사용된다.
