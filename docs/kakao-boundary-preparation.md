# Kakao collection boundary preparation

Kakao content collection uses the bundled administrative-dong GeoJSON directly;
it does not require an SGIS API key or an SGIS boundary download.

Build the WGS84 municipality boundary file once before running the collector:

```powershell
python -m scripts.build_kakao_boundaries `
  --source data/HangJeongDong_ver20260701.geojson `
  --output data/raw/national_sigungu.geojson
```

The command merges dong/eup/myeon polygons into the project's 230 collection
regions and writes the `region_id`, `area_code`, `sigungu_code`,
`province_name`, and `region_name` properties required by
`hankkeut-kakao-tourism-content`.

For the eight handover regions, run:

```powershell
hankkeut-kakao-tourism-content --boundaries data/raw/national_sigungu.geojson `
  --region-name 해운대구 --region-name 화성시 --region-name 강릉시 `
  --region-name 경주시 --region-name 여수시 --region-name 강남구 `
  --region-name 양주시 --region-name 파주시
```
