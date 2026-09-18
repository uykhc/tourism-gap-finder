from __future__ import annotations

from unittest import mock

from apps.api.app.schemas.peers import PeerResult
from apps.api.app.services import artifacts, regions
from scripts.build_peer_artifacts import DEFAULT_FEATURES_PATH, build_payload, load_features


def test_nationwide_feature_snapshot_builds_valid_peer_payloads() -> None:
    features = load_features(DEFAULT_FEATURES_PATH)

    assert len(features) == 230
    for region_id in ("11110", "36110", "47130"):
        payload = build_payload(features, region_id, stored_k=50)
        response_payload = {
            **payload,
            "requested_k": 50,
            "min_similarity": 0.0,
            "provenance": [
                artifacts._provenance_record(item) for item in payload["provenance"]
            ],
        }
        result = PeerResult.model_validate(response_payload)

        assert result.target.region_id == region_id
        assert len(result.peers) == 50
        assert all(peer.region_id != region_id for peer in result.peers)
        assert [peer.rank for peer in result.peers] == list(range(1, 51))
        assert all(
            earlier.similarity >= later.similarity
            for earlier, later in zip(result.peers, result.peers[1:], strict=False)
        )


def test_peer_generation_is_deterministic() -> None:
    features = load_features(DEFAULT_FEATURES_PATH)

    first = build_payload(features, "47130", stored_k=15)
    second = build_payload(features, "47130", stored_k=15)

    assert first == second


def test_committed_peer_artifacts_cover_every_region() -> None:
    expected_ids = set(regions.all_region_ids())
    embedded_root = artifacts.APP_ROOT / "data" / "artifacts"
    artifact_ids = {
        path.stem
        for path in (embedded_root / artifacts.PEER_CANDIDATES_DIR).glob("*.json")
    }

    assert artifact_ids == expected_ids
    with mock.patch.object(artifacts, "ARTIFACT_ROOT", embedded_root):
        for region_id in expected_ids:
            result = PeerResult.model_validate(
                artifacts.peers(region_id, k=50, min_similarity=0.0)
            )
            assert len(result.peers) == 50
            assert all(peer.region_id != region_id for peer in result.peers)
