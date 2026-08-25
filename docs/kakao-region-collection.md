# 카카오맵 시군구 콘텐츠 수집

`hankkeut-kakao-regions`는 관광명소 주변 검색이 아니라 행정경계 전체에서 카카오 로컬 API의 장소 카테고리를 집계한다.

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
$env:PYTHONPATH = 'packages/analysis'
python -m hankkeut_analysis.kakao_places.boundary_builder --source data/reference/Local_HangJeongDong/hangjeongdong_경기도.geojson
```

```powershell
$env:PYTHONPATH = 'packages/analysis'
python -m hankkeut_analysis.kakao_places.region_cli --boundaries data/raw/gyeonggi_sigungu.geojson --region-name 수원시 --category CT1
```

기본값은 모든 입력 시군구와 지원 카테고리(`CT1`, `AT4`, `AD5`, `FD6`, `CE7`, `PK6`, `SW8`, `PO3`)를 수집하여 `data/analysis/kakao_regions/kakao_region_categories.json`에 저장한다.

밀집 지역에서는 결과 한도를 피하기 위해 처음 5 km 격자에서 시작해 필요 시 250 m까지 4분할한다. 출력의 `truncated_tile_count`가 0보다 크면 해당 카테고리는 여전히 누락 가능성이 있으므로 더 작은 `--minimum-tile-meters`로 재수집하거나 분석에서 제외한다.

각 카테고리 결과에는 경계 좌표로 필터링한 장소 목록과 함께 주소 검증 지표도 저장한다. `address_match_count`는 카카오의 도로명/지번 주소에 대상 시·군명이 포함된 건수이고, `address_mismatch_samples`는 경계에는 포함되지만 주소 표기가 다른 사례이므로 수집 후 검토 대상이다.

## 체크포인트와 재개

수집은 시군·카테고리 하나씩 순차적으로 진행하며, 완료 직후 각각 별도 JSON 체크포인트를 저장한다. 기본적으로 다시 실행하면 완료된 체크포인트를 재사용하므로, 중간에 종료돼도 미완료 항목만 이어서 수집한다. `--no-resume`을 지정하면 선택 범위를 다시 수집한다.
