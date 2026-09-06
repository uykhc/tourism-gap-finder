#!/usr/bin/env zsh

# Detailed Kakao collection for the three structural Peer candidates.
# The collector reads KAKAO_REST_API_KEY from the repository .env file.
# Completed regions are retained in the checkpoint directory and reused on
# the next run, so rerun this exact command after an interruption.

set -euo pipefail

hankkeut-kakao-tourism-content \
  --boundaries data/raw/gyeonggi_sigungu.geojson \
  --region-name 성남시 \
  --region-name 용인시 \
  --region-name 고양시 \
  --initial-tile-meters 5000 \
  --minimum-tile-meters 250 \
  --output data/analysis/kakao_regions/peer_tourism_content_detailed.json \
  --checkpoint-dir data/analysis/kakao_regions/peer_tourism_content_detailed_checkpoints \
  --resume
