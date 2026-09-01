"""Tourism-content taxonomy and municipality-wide Kakao place collection."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .client import KakaoLocalClient
from .models import KakaoPlace
from .region_collector import KakaoRegionCollector

DEFAULT_TAXONOMY_PATH = Path("config/kakao/tourism_content_taxonomy.json")


@dataclass(frozen=True, slots=True)
class TourismContentTaxonomy:
    version: str
    content_types: tuple[str, ...]
    category_rules: dict[str, str]
    keyword_rules: dict[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class ClassifiedKakaoPlace:
    place: KakaoPlace
    content_type: str | None
    classification_source: str
    discovered_categories: tuple[str, ...]
    discovered_keywords: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "place": self.place.to_dict(),
            "content_type": self.content_type,
            "classification_source": self.classification_source,
            "discovered_categories": list(self.discovered_categories),
            "discovered_keywords": list(self.discovered_keywords),
        }


@dataclass(frozen=True, slots=True)
class KakaoTourismContentCollection:
    region_name: str
    taxonomy_version: str
    collected_count: int
    classified_count: int
    unclassified_count: int
    content_type_counts: dict[str, int]
    category_collection_summaries: tuple[dict[str, Any], ...]
    keyword_collection_summaries: tuple[dict[str, Any], ...]
    truncated_tile_count: int
    places: tuple[ClassifiedKakaoPlace, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_name": self.region_name,
            "taxonomy_version": self.taxonomy_version,
            "collected_count": self.collected_count,
            "classified_count": self.classified_count,
            "unclassified_count": self.unclassified_count,
            "content_type_counts": self.content_type_counts,
            "category_collection_summaries": list(self.category_collection_summaries),
            "keyword_collection_summaries": list(self.keyword_collection_summaries),
            "truncated_tile_count": self.truncated_tile_count,
            "is_complete": self.truncated_tile_count == 0,
            "places": [item.to_dict() for item in self.places],
        }


def load_tourism_content_taxonomy(path: Path = DEFAULT_TAXONOMY_PATH) -> TourismContentTaxonomy:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Tourism content taxonomy file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Tourism content taxonomy is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Tourism content taxonomy must be an object.")
    version = str(payload.get("version", "")).strip()
    content_types = _string_tuple(payload.get("content_types"), "content_types")
    category_rules = _string_mapping(payload.get("category_rules"), "category_rules")
    raw_keyword_rules = payload.get("keyword_rules")
    if not isinstance(raw_keyword_rules, dict):
        raise ValueError("keyword_rules must be an object.")
    keyword_rules = {
        str(content_type).strip(): _string_tuple(keywords, f"keyword_rules.{content_type}")
        for content_type, keywords in raw_keyword_rules.items()
    }
    if not version or not content_types:
        raise ValueError("Taxonomy version and content_types must not be empty.")
    allowed = set(content_types)
    if set(category_rules.values()) - allowed or set(keyword_rules) - allowed:
        raise ValueError("Every taxonomy rule must target a declared content type.")
    return TourismContentTaxonomy(version, content_types, category_rules, keyword_rules)


class KakaoTourismContentCollector:
    """Collect source places once, then classify them with a versioned taxonomy."""

    def __init__(self, client: KakaoLocalClient, taxonomy: TourismContentTaxonomy) -> None:
        self._taxonomy = taxonomy
        self._region_collector = KakaoRegionCollector(client)

    def collect_region(
        self,
        *,
        region_name: str,
        geometry: dict[str, Any],
        initial_tile_meters: int,
        minimum_tile_meters: int,
    ) -> KakaoTourismContentCollection:
        discoveries: dict[str, dict[str, Any]] = {}
        category_summaries: list[dict[str, Any]] = []
        keyword_summaries: list[dict[str, Any]] = []
        truncated_tile_count = 0

        for category in self._taxonomy.category_rules:
            result = self._region_collector.collect_category(
                region_name=region_name,
                geometry=geometry,
                category_group_code=category,
                initial_tile_meters=initial_tile_meters,
                minimum_tile_meters=minimum_tile_meters,
            )
            category_summaries.append(_summary(result.to_dict()))
            truncated_tile_count += result.truncated_tile_count
            _merge_places(discoveries, result.places, category=category)

        for content_type, keywords in self._taxonomy.keyword_rules.items():
            for keyword in keywords:
                result = self._region_collector.collect_keyword(
                    region_name=region_name,
                    geometry=geometry,
                    query=keyword,
                    initial_tile_meters=initial_tile_meters,
                    minimum_tile_meters=minimum_tile_meters,
                )
                summary = _summary(result.to_dict())
                summary["content_type_candidate"] = content_type
                keyword_summaries.append(summary)
                truncated_tile_count += result.truncated_tile_count
                _merge_places(discoveries, result.places, keyword=keyword)

        classified = tuple(
            sorted(
                (_classify(place_data, self._taxonomy) for place_data in discoveries.values()),
                key=lambda item: (item.content_type is None, item.content_type or "", item.place.name, item.place.place_id),
            )
        )
        counts = Counter(item.content_type for item in classified if item.content_type is not None)
        content_type_counts = {content_type: counts[content_type] for content_type in self._taxonomy.content_types}
        return KakaoTourismContentCollection(
            region_name=region_name,
            taxonomy_version=self._taxonomy.version,
            collected_count=len(classified),
            classified_count=sum(item.content_type is not None for item in classified),
            unclassified_count=sum(item.content_type is None for item in classified),
            content_type_counts=content_type_counts,
            category_collection_summaries=tuple(category_summaries),
            keyword_collection_summaries=tuple(keyword_summaries),
            truncated_tile_count=truncated_tile_count,
            places=classified,
        )


def _merge_places(
    discoveries: dict[str, dict[str, Any]],
    places: tuple[KakaoPlace, ...],
    *,
    category: str | None = None,
    keyword: str | None = None,
) -> None:
    for place in places:
        found = discoveries.setdefault(
            place.place_id,
            {"place": place, "categories": set(), "keywords": set()},
        )
        if category:
            found["categories"].add(category)
        if keyword:
            found["keywords"].add(keyword)


def _classify(place_data: dict[str, Any], taxonomy: TourismContentTaxonomy) -> ClassifiedKakaoPlace:
    categories = tuple(sorted(place_data["categories"]))
    keywords = tuple(sorted(place_data["keywords"]))
    keyword_to_type = {
        keyword: content_type
        for content_type, values in taxonomy.keyword_rules.items()
        for keyword in values
    }
    keyword_types = {keyword_to_type[keyword] for keyword in keywords}
    if len(keyword_types) == 1:
        return ClassifiedKakaoPlace(place_data["place"], next(iter(keyword_types)), "keyword", categories, keywords)
    category_types = {taxonomy.category_rules[category] for category in categories if category in taxonomy.category_rules}
    if len(category_types) == 1:
        return ClassifiedKakaoPlace(place_data["place"], next(iter(category_types)), "category", categories, keywords)
    if len(keyword_types) > 1:
        return ClassifiedKakaoPlace(place_data["place"], None, "ambiguous_keyword", categories, keywords)
    return ClassifiedKakaoPlace(place_data["place"], None, "unclassified", categories, keywords)


def _summary(value: dict[str, Any]) -> dict[str, Any]:
    keys = ("region_name", "category_group_code", "query", "collected_count", "searched_tile_count", "truncated_tile_count", "initial_tile_meters", "minimum_tile_meters")
    return {key: value[key] for key in keys if key in value}


def _string_tuple(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{field} must be a non-empty string array.")
    return tuple(item.strip() for item in value)


def _string_mapping(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object.")
    result = {str(key).strip().upper(): str(item).strip() for key, item in value.items()}
    if not all(result) or not all(result.values()):
        raise ValueError(f"{field} must contain non-empty strings.")
    return result
