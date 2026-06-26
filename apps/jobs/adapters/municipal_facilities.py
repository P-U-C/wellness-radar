from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from packages.schemas.canonical import CanonicalOperator
from packages.shared.ids import stable_id
from packages.shared.normalizers import compact_address, normalize_categories, normalize_name
from packages.shared.provenance import source_ref

FIXTURE_DIR = Path(__file__).parents[1] / "tests" / "fixtures"


@dataclass(frozen=True)
class MunicipalSource:
    key: str
    registry_name: str
    label: str
    municipality: str
    kind: str
    url: str
    licence: str
    category_hint: str
    source_url: str | None = None
    where: str = "1=1"
    enabled: bool = True
    name_fields: tuple[str, ...] = ("name", "NAME", "DESCRIPTION", "PARK_NAME")
    facility_fields: tuple[str, ...] = (
        "facilitytype",
        "OUTDOOR_REC_FAC_TYPE2",
        "COURT_TYPE",
        "PRIMARY_USE",
        "SPORTS_FIELD_TYPE2",
        "PLACETYPE",
    )
    address_fields: tuple[str, ...] = ("address", "ADDRESS", "LOCATION", "OPERATING_LOCATION")
    neighborhood_fields: tuple[str, ...] = ("neighbourhoodname", "COMMUNITY")
    extra_tags: dict[str, str] = field(default_factory=dict)
    force_public_recreation: bool = True


class MunicipalFacilitiesAdapter:
    name = "municipal_facilities"
    family = "directory/public_recreation"
    cadence = "weekly"
    trust_tier = "official"
    geo_aware = True
    dedupe_existing = True
    base_url = "https://opendata.vancouver.ca/"
    licence = "municipal open data terms"

    def __init__(
        self,
        limit: int = 2000,
        client: httpx.Client | None = None,
        sources: tuple[MunicipalSource, ...] | None = None,
        fixture_dir: Path | None = FIXTURE_DIR,
        source_name: str | None = None,
    ) -> None:
        if source_name is not None:
            self.name = source_name
        self.limit = limit
        self.client = client or httpx.Client(
            timeout=60.0,
            headers={"user-agent": "wellness-radar/0.1", "accept": "application/json,*/*"},
        )
        self.sources = sources or MUNICIPAL_SOURCES
        self.fixture_dir = fixture_dir

    def fetch(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for source in self.sources:
            if len(records) >= self.limit:
                break
            if not source.enabled:
                continue
            remaining = self.limit - len(records)
            try:
                fetched = self._fetch_source(source, remaining)
            except Exception as exc:
                fetched = self._fixture_records(source, error=str(exc), limit=remaining)
            records.extend(fetched[:remaining])
        return records[: self.limit]

    def source_record_id(self, raw: dict[str, Any]) -> str:
        source_raw = raw.get("_source")
        source: dict[str, Any] = source_raw if isinstance(source_raw, dict) else {}
        source_key = str(source.get("key") or "unknown")
        raw_id = raw.get("_record_id") or raw.get("id") or raw.get("OBJECTID") or raw.get("parkid")
        return f"{source_key}/{raw_id or stable_id('municipal', source_key, raw)}"

    def normalize(self, raw: dict[str, Any], raw_payload_id: str) -> list[CanonicalOperator]:
        source_raw = raw.get("_source")
        source: dict[str, Any] = source_raw if isinstance(source_raw, dict) else {}
        source_record_id = self.source_record_id(raw)
        name = _clean(
            raw.get("_name") or _first_present(raw, *tuple(source.get("name_fields") or ()))
        )
        if not name:
            return []

        facility_type = _clean(
            raw.get("_facility_type")
            or _first_present(raw, *tuple(source.get("facility_fields") or ()))
            or source.get("category_hint")
        )
        tags = _tags_for_raw(raw, facility_type)
        categories = normalize_categories(
            name,
            facility_type,
            source.get("category_hint"),
            *(str(value) for value in tags.values()),
        )
        if "public_recreation" not in categories and bool(
            source.get("force_public_recreation", True)
        ):
            categories.append("public_recreation")
        if not categories:
            return []

        lat, lng = _point_for_raw(raw)
        address = _address_for_raw(raw, source)
        municipality = str(source.get("municipality") or "").strip() or None
        source_url = _clean(raw.get("_source_url") or source.get("source_url") or source.get("url"))
        now = datetime.now(timezone.utc)
        seen_at = now.isoformat().replace("+00:00", "Z")
        adapter_ref = source_ref(
            source_name=self.name,
            url=source_url,
            trust_tier=self.trust_tier,
            source_record_id=source_record_id,
            licence=self.licence,
            seen_at=seen_at,
        )
        municipal_ref = source_ref(
            source_name=str(source.get("registry_name") or self.name),
            url=source_url,
            trust_tier=self.trust_tier,
            source_record_id=source_record_id,
            licence=str(source.get("licence") or self.licence),
            seen_at=seen_at,
        )
        refs = [adapter_ref, municipal_ref] if municipal_ref != adapter_ref else [adapter_ref]
        confidence = 0.88 if lat is not None and lng is not None else 0.68
        source_status = str(raw.get("_source_status") or "live")

        return [
            CanonicalOperator(
                id=stable_id("op", self.name, source_record_id),
                source_name=self.name,
                source_record_id=source_record_id,
                raw_payload_id=raw_payload_id,
                name=name,
                normalized_name=normalize_name(name),
                categories=categories,
                status=_status_for_raw(raw),
                address=address,
                municipality=municipality,
                province="BC",
                country="CA",
                neighborhood=_clean(
                    _first_present(raw, *tuple(source.get("neighborhood_fields") or ()))
                ),
                lat=lat,
                lng=lng,
                licence_ref=source_record_id,
                source_url=source_url,
                source_refs=refs,
                confidence_score=confidence,
                occurred_at=now,
                payload={
                    "event_type": "public_facility_observed",
                    "signal_type": "public_facility_observed",
                    "signal_title": f"Municipal recreation facility observed: {name}",
                    "signal_summary": (
                        f"{name} appears in {source.get('label') or 'municipal'} "
                        "public recreation facility data."
                    ),
                    "trust_tier": self.trust_tier,
                    "municipal_source_key": source.get("key"),
                    "municipal_source_name": source.get("label"),
                    "municipal_facility_type": facility_type,
                    "source_status": source_status,
                    "source_error": raw.get("_source_error"),
                    "tags": tags,
                },
            )
        ]

    def _fetch_source(self, source: MunicipalSource, limit: int) -> list[dict[str, Any]]:
        if source.kind == "arcgis_geojson":
            return self._fetch_arcgis_geojson(source, limit)
        if source.kind == "vancouver_parks_facilities":
            return self._fetch_vancouver_parks_facilities(source, limit)
        raise ValueError(f"unsupported municipal source kind {source.kind}")

    def _fetch_arcgis_geojson(self, source: MunicipalSource, limit: int) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        offset = 0
        page_size = min(1000, max(limit, 1))
        while len(records) < limit:
            response = self.client.get(
                f"{source.url.rstrip('/')}/query",
                params={
                    "where": source.where,
                    "outFields": "*",
                    "outSR": "4326",
                    "f": "geojson",
                    "resultRecordCount": min(page_size, limit - len(records)),
                    "resultOffset": offset,
                },
            )
            response.raise_for_status()
            payload = response.json()
            page = [
                _raw_from_feature(feature, source=source, source_status="live")
                for feature in payload.get("features", [])
                if isinstance(feature, dict)
            ]
            records.extend(page)
            if not payload.get("properties", {}).get("exceededTransferLimit") or not page:
                break
            offset += len(page)
        return records[:limit]

    def _fetch_vancouver_parks_facilities(
        self, source: MunicipalSource, limit: int
    ) -> list[dict[str, Any]]:
        parks_url = (
            "https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/parks/records"
        )
        facilities: list[dict[str, Any]] = []
        offset = 0
        while len(facilities) < limit:
            page_limit = min(100, limit - len(facilities))
            facilities_response = self.client.get(
                source.url,
                params={"limit": page_limit, "offset": offset, "order_by": "parkid"},
            )
            facilities_response.raise_for_status()
            page = list(facilities_response.json().get("results", []))
            facilities.extend(page)
            if len(page) < page_limit:
                break
            offset += len(page)
        park_ids = sorted(
            {str(facility.get("parkid")) for facility in facilities if facility.get("parkid")}
        )
        parks_by_id: dict[str, dict[str, Any]] = {}
        parks_offset = 0
        while len(parks_by_id) < len(park_ids):
            park_response = self.client.get(
                parks_url,
                params={"limit": 100, "offset": parks_offset, "order_by": "parkid"},
            )
            park_response.raise_for_status()
            park_results = park_response.json().get("results", [])
            for park in park_results:
                if isinstance(park, dict) and park.get("parkid"):
                    parks_by_id[str(park["parkid"])] = dict(park)
            if len(park_results) < 100:
                break
            parks_offset += len(park_results)

        records: list[dict[str, Any]] = []
        for facility in facilities:
            park = parks_by_id.get(str(facility.get("parkid")), {})
            merged = {**park, **facility}
            facility_type = _clean(facility.get("facilitytype"))
            park_name = _clean(park.get("name") or facility.get("name"))
            merged["_name"] = " ".join(part for part in [park_name, facility_type] if part)
            merged["_facility_type"] = facility_type
            merged["_record_id"] = f"{facility.get('parkid')}:{facility_type}"
            merged["_geometry"] = {
                "type": "Point",
                "coordinates": [
                    (park.get("googlemapdest") or {}).get("lon"),
                    (park.get("googlemapdest") or {}).get("lat"),
                ],
            }
            merged["_source_url"] = facility.get("facilityurl") or source.source_url or source.url
            records.append(_annotate_raw(merged, source=source, source_status="live"))
        return records[:limit]

    def _fixture_records(
        self, source: MunicipalSource, *, error: str, limit: int
    ) -> list[dict[str, Any]]:
        if self.fixture_dir is None:
            raise RuntimeError(error)
        path = self.fixture_dir / f"municipal_facilities_{source.key}.json"
        if not path.exists():
            raise RuntimeError(error)
        payload = json.loads(path.read_text())
        rows = payload.get("records", []) if isinstance(payload, dict) else payload
        return [
            _annotate_raw(
                dict(row),
                source=source,
                source_status="fixture_fallback",
                source_error=error,
            )
            for row in rows[:limit]
            if isinstance(row, dict)
        ]


def _raw_from_feature(
    feature: dict[str, Any],
    *,
    source: MunicipalSource,
    source_status: str,
    source_error: str | None = None,
) -> dict[str, Any]:
    properties = dict(feature.get("properties") or {})
    properties["_geometry"] = feature.get("geometry")
    properties["_record_id"] = feature.get("id") or properties.get("OBJECTID")
    return _annotate_raw(
        properties,
        source=source,
        source_status=source_status,
        source_error=source_error,
    )


def _annotate_raw(
    raw: dict[str, Any],
    *,
    source: MunicipalSource,
    source_status: str,
    source_error: str | None = None,
) -> dict[str, Any]:
    annotated = dict(raw)
    annotated["_source"] = {
        "key": source.key,
        "registry_name": source.registry_name,
        "label": source.label,
        "municipality": source.municipality,
        "url": source.url,
        "source_url": source.source_url or source.url,
        "licence": source.licence,
        "category_hint": source.category_hint,
        "name_fields": source.name_fields,
        "facility_fields": source.facility_fields,
        "address_fields": source.address_fields,
        "neighborhood_fields": source.neighborhood_fields,
        "extra_tags": source.extra_tags,
        "force_public_recreation": source.force_public_recreation,
    }
    annotated["_source_status"] = source_status
    if source_error:
        annotated["_source_error"] = source_error
    return annotated


def _tags_for_raw(raw: dict[str, Any], facility_type: str | None) -> dict[str, str]:
    source_raw = raw.get("_source")
    source: dict[str, Any] = source_raw if isinstance(source_raw, dict) else {}
    tags: dict[str, str] = {
        "municipal_facility_type": _clean(source.get("category_hint")) or "public recreation",
    }
    if facility_type:
        tags["facility_type"] = facility_type
    for raw_key, tag_key in [
        ("COURT_TYPE", "court_type"),
        ("PRIMARY_USE", "primary_use"),
        ("FIELD_TYPE", "field_type"),
        ("SPORTS_FIELD_TYPE2", "field_type"),
        ("OUTDOOR_REC_FAC_TYPE2", "facility_type"),
    ]:
        value = _clean(raw.get(raw_key))
        if value:
            tags[tag_key] = value
    extra_tags_raw = source.get("extra_tags")
    extra_tags: dict[Any, Any] = extra_tags_raw if isinstance(extra_tags_raw, dict) else {}
    for key, value in extra_tags.items():
        cleaned = _clean(value)
        if cleaned:
            tags[str(key)] = cleaned
    return tags


def _address_for_raw(raw: dict[str, Any], source: dict[str, Any]) -> str | None:
    address = _clean(_first_present(raw, *tuple(source.get("address_fields") or ())))
    if address:
        return compact_address(address, source.get("municipality"), "BC")
    street_number = _clean(raw.get("streetnumber"))
    street_name = _clean(raw.get("streetname"))
    return compact_address(
        compact_address(street_number, street_name),
        source.get("municipality"),
        "BC",
    )


def _point_for_raw(raw: dict[str, Any]) -> tuple[float | None, float | None]:
    geometry_raw = raw.get("_geometry")
    geometry = geometry_raw if isinstance(geometry_raw, dict) else None
    if geometry:
        point = _point_for_geometry(geometry)
        if point is not None:
            lng, lat = point
            return lat, lng
    google_raw = raw.get("googlemapdest")
    google: dict[str, Any] = google_raw if isinstance(google_raw, dict) else {}
    google_lat = _float_or_none(google.get("lat") or raw.get("lat") or raw.get("POINT_Y"))
    google_lng = _float_or_none(google.get("lon") or raw.get("lon") or raw.get("POINT_X"))
    return google_lat, google_lng


def _point_for_geometry(geometry: dict[str, Any]) -> tuple[float, float] | None:
    geometry_type = str(geometry.get("type") or "")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Point" and isinstance(coordinates, list) and len(coordinates) >= 2:
        lng = _float_or_none(coordinates[0])
        lat = _float_or_none(coordinates[1])
        if lat is not None and lng is not None:
            return lng, lat
    points = list(_flatten_coordinate_pairs(coordinates))
    if not points:
        return None
    lngs = [point[0] for point in points]
    lats = [point[1] for point in points]
    return (sum(lngs) / len(lngs), sum(lats) / len(lats))


def _flatten_coordinate_pairs(value: Any) -> list[tuple[float, float]]:
    if (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], int | float)
        and isinstance(value[1], int | float)
    ):
        return [(float(value[0]), float(value[1]))]
    points: list[tuple[float, float]] = []
    if isinstance(value, list):
        for item in value:
            points.extend(_flatten_coordinate_pairs(item))
    return points


def _status_for_raw(raw: dict[str, Any]) -> str:
    status = str(raw.get("STATUS") or raw.get("status") or "").strip().lower()
    if status in {"operating", "open", "active"}:
        return "open"
    if status in {"closed", "inactive"}:
        return "closed"
    return "open"


def _first_present(raw: dict[str, Any], *keys: str) -> Any:
    lowered = {key.lower().replace(" ", "").replace("-", "_"): value for key, value in raw.items()}
    for key in keys:
        value = raw.get(key)
        if value is not None and str(value).strip():
            return value
        compact_key = key.lower().replace(" ", "").replace("-", "_")
        value = lowered.get(compact_key)
        if value is not None and str(value).strip():
            return value
    return None


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


MUNICIPAL_SOURCES: tuple[MunicipalSource, ...] = (
    MunicipalSource(
        key="new_westminster_business_licences",
        registry_name="municipal_facilities_new_westminster",
        label="City of New Westminster business licences",
        municipality="New Westminster",
        kind="arcgis_geojson",
        url=(
            "https://services3.arcgis.com/A7O8YnTNtzRPIn7T/arcgis/rest/services/"
            "BUSINESS_LICENSES/FeatureServer/0"
        ),
        source_url=(
            "https://data-60320-newwestcity.opendata.arcgis.com/datasets/"
            "newwestcity::business-licenses-all"
        ),
        licence="Open Government Licence - New Westminster",
        category_hint="wellness or fitness business licence",
        where=(
            "NAICS_CODE LIKE '713%' OR NAICS_CODE LIKE '8121%' OR NAICS_CODE LIKE '6213%' "
            "OR NAICS_DESCRIPTION LIKE '%Fitness%' OR NAICS_DESCRIPTION LIKE '%Health%' "
            "OR NAICS_DESCRIPTION LIKE '%Personal care%' OR BUSINESS_NAME LIKE '%FITNESS%' "
            "OR BUSINESS_NAME LIKE '%YOGA%' OR BUSINESS_NAME LIKE '%SPA%' "
            "OR BUSINESS_NAME LIKE '%WELLNESS%'"
        ),
        name_fields=("BUSINESS_NAME", "LICENCEE_NAME"),
        facility_fields=("NAICS_DESCRIPTION", "NAICS_CODE"),
        address_fields=("CIVIC_ADDRESS", "MAILING_ADDRESS"),
        extra_tags={"source_record_type": "business_licence"},
        force_public_recreation=False,
    ),
    MunicipalSource(
        key="delta_business_licences",
        registry_name="municipal_facilities_delta",
        label="City of Delta business licences",
        municipality="Delta",
        kind="arcgis_geojson",
        url=(
            "https://services9.arcgis.com/w2mu7sRltY6PiQ7J/arcgis/rest/services/"
            "Business_Licenses/FeatureServer/0"
        ),
        source_url="https://opendata-deltabc.hub.arcgis.com/datasets/a77ef0a02cc14bf1b6d5dd8e66991784_0",
        licence="Open Government Licence - Delta",
        category_hint="wellness or fitness business licence",
        where=(
            "TRADE_NAICS_CODE = '713940' OR BUSINESS_TYPE LIKE '%Fitness%' "
            "OR BUSINESS_TYPE LIKE '%Massage%' OR BUSINESS_TYPE LIKE '%Spa%' "
            "OR BUSINESS_TYPE LIKE '%Physio%' OR BUSINESS_TYPE LIKE '%Yoga%' "
            "OR TRADE_NAME LIKE '%FITNESS%' OR TRADE_NAME LIKE '%YOGA%' "
            "OR TRADE_NAME LIKE '%SPA%' OR TRADE_NAME LIKE '%WELLNESS%' "
            "OR TRADE_NAME LIKE '%MASSAGE%' OR TRADE_NAME LIKE '%PHYSIO%' "
            "OR TRADE_NAME LIKE '%RMT%'"
        ),
        name_fields=("TRADE_NAME",),
        facility_fields=("BUSINESS_TYPE", "TRADE_NAICS_CODE"),
        address_fields=("ADDRESS",),
        extra_tags={"source_record_type": "business_licence"},
        force_public_recreation=False,
    ),
    MunicipalSource(
        key="north_vancouver_district_parks",
        registry_name="municipal_facilities_north_vancouver",
        label="District of North Vancouver parks and recreation amenities",
        municipality="North Vancouver",
        kind="arcgis_geojson",
        url="https://geoweb.dnv.org/arcgis/rest/services/Basemap_ParksAppV2/MapServer/0",
        source_url="https://geoweb.dnv.org/data/",
        licence="Open Government Licence - North Vancouver",
        category_hint="public recreation park",
        where=(
            "Baseball = 1 OR Basketball = 1 OR Cricket_Pitch = 1 OR Lacrosse = 1 "
            "OR Multi_Purpose = 1 OR Pitch_N_Putt = 1 OR Soccer = 1 OR Skateboard = 1 "
            "OR Tennis = 1 OR Practice_Court = 1 OR Rec_Pool = 1 OR Fitness_Trail = 1 "
            "OR Playground = 1 OR Water_Park = 1 OR Swimming = 1 OR Change_Rooms = 1 "
            "OR Washrooms = 1"
        ),
        name_fields=("Park_Name",),
        facility_fields=(),
        address_fields=(),
        extra_tags={"leisure": "park", "source_record_type": "park_recreation_amenity"},
    ),
    MunicipalSource(
        key="west_vancouver_parks",
        registry_name="municipal_facilities_west_vancouver",
        label="District of West Vancouver parks open data",
        municipality="West Vancouver",
        kind="arcgis_geojson",
        url="https://services9.arcgis.com/rLkpFp1GxgPDr9HL/arcgis/rest/services/PWV/FeatureServer/0",
        source_url="https://www.arcgis.com/home/item.html?id=3d1cfad854f246d98b1e04bff9819b3f",
        licence="Open Government Licence - West Vancouver",
        category_hint="public recreation park",
        name_fields=("PARK_NAME", "MAP_NAME"),
        facility_fields=("Data_Title", "Description"),
        address_fields=("ADDRESS",),
        extra_tags={"leisure": "park"},
    ),
    MunicipalSource(
        key="vancouver_parks_facilities",
        registry_name="municipal_facilities_vancouver",
        label="City of Vancouver parks facilities",
        municipality="Vancouver",
        kind="vancouver_parks_facilities",
        url=(
            "https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/"
            "parks-facilities/records"
        ),
        source_url="https://opendata.vancouver.ca/explore/dataset/parks-facilities/",
        licence="City of Vancouver Open Data Portal terms",
        category_hint="public recreation facility",
        name_fields=("_name", "name"),
        facility_fields=("_facility_type", "facilitytype"),
        address_fields=("streetname",),
        neighborhood_fields=("neighbourhoodname",),
    ),
    MunicipalSource(
        key="surrey_outdoor_recreation",
        registry_name="municipal_facilities_surrey",
        label="City of Surrey park outdoor recreation facilities",
        municipality="Surrey",
        kind="arcgis_geojson",
        url=(
            "https://services5.arcgis.com/YRpe0VKTJytZSSIB/arcgis/rest/services/"
            "Park%20Outdoor%20Recreation%20Facilities/FeatureServer/0"
        ),
        source_url="https://opendata-surrey.hub.arcgis.com/",
        licence="Open Government Licence - City of Surrey",
        category_hint="public recreation courts",
        name_fields=("DESCRIPTION", "PARK"),
        facility_fields=("COURT_TYPE", "PRIMARY_USE", "OUTDOOR_REC_FAC_TYPE2"),
        address_fields=("OPERATING_LOCATION", "LOCATION"),
        neighborhood_fields=("COMMUNITY",),
    ),
    MunicipalSource(
        key="surrey_sport_fields",
        registry_name="municipal_facilities_surrey",
        label="City of Surrey park sport fields",
        municipality="Surrey",
        kind="arcgis_geojson",
        url=(
            "https://services5.arcgis.com/YRpe0VKTJytZSSIB/arcgis/rest/services/"
            "Park%20Sport%20Fields/FeatureServer/0"
        ),
        source_url="https://opendata-surrey.hub.arcgis.com/",
        licence="Open Government Licence - City of Surrey",
        category_hint="public recreation sports fields",
        name_fields=("DESCRIPTION", "PARK"),
        facility_fields=("PRIMARY_USE", "SPORTS_FIELD_TYPE2"),
        address_fields=("LOCATION",),
        neighborhood_fields=("COMMUNITY",),
    ),
    MunicipalSource(
        key="burnaby_civic_places",
        registry_name="municipal_facilities_burnaby",
        label="City of Burnaby civic places",
        municipality="Burnaby",
        kind="arcgis_geojson",
        url="https://gis.burnaby.ca/arcgis/rest/services/OpenData/OpenData1/MapServer/1",
        source_url="https://opendata-burnaby.hub.arcgis.com/",
        licence="City of Burnaby Open Data terms",
        category_hint="public recreation civic place",
        where="PLACETYPE IN (100,300)",
        name_fields=("DESCRIPTION",),
        facility_fields=("PLACETYPE", "FCODE"),
        extra_tags={"municipal_facility_type": "public recreation"},
    ),
    MunicipalSource(
        key="richmond_needs_review",
        registry_name="municipal_facilities_richmond",
        label="City of Richmond recreation facilities",
        municipality="Richmond",
        kind="needs_review",
        url="https://www.richmond.ca/services/digital/maps.htm",
        licence="needs_review",
        category_hint="public recreation",
        enabled=False,
    ),
)
