from scripts.build_kakao_boundaries import build_boundaries


def _feature(sgg: str, sidonm: str, sggnm: str):
    return {"type": "Feature", "properties": {"sgg": sgg, "sidonm": sidonm, "sggnm": sggnm},
            "geometry": {"type": "Polygon", "coordinates": [[[127, 37], [128, 37], [127, 38], [127, 37]]]}}


def test_merges_administrative_dongs_and_collapses_autonomous_districts(monkeypatch):
    monkeypatch.setattr("scripts.build_kakao_boundaries.regions.tour_api_code", lambda _: ("31", "13"))
    result = build_boundaries([_feature("41111", "경기도", "수원시 장안구"), _feature("41113", "경기도", "수원시 권선구")],
                              region_rows=[{"region_id": "41110", "province_name": "경기도", "region_name": "수원시"}])
    feature = result["features"][0]
    assert feature["properties"]["region_id"] == "41110"
    assert feature["properties"]["source_sgg_codes"] == ["41111", "41113"]
    assert len(feature["geometry"]["coordinates"]) == 2
