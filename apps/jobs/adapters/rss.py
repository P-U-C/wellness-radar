from __future__ import annotations

import email.utils
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from packages.schemas.canonical import SignalRecord, SourceEventRecord
from packages.shared.ids import stable_id
from packages.shared.normalizers import strip_html, truncate_text
from packages.shared.provenance import source_ref

WELLNESS_TERMS = {
    "sauna",
    "cold plunge",
    "contrast",
    "recovery",
    "spa",
    "wellness",
    "fitness",
    "health",
    "active",
    "nutrition",
    "massage",
    "hearing aids",
    "recall",
}


@dataclass(frozen=True)
class RssFeedConfig:
    outlet: str
    url: str
    location_text: str
    licence: str


class RssFeedAdapter:
    name = "local_rss"
    family = "feed"
    cadence = "hourly/daily"
    trust_tier = "reputable_press"
    geo_aware = False
    text_gate = True
    event_type = "news_article"
    signal_type = "news_signal"
    licence = "source-specific"

    feeds: tuple[RssFeedConfig, ...] = (
        RssFeedConfig(
            "Daily Hive Vancouver",
            "https://dailyhive.com/feed",
            "Vancouver BC Metro Vancouver",
            "Daily Hive site/feed terms",
        ),
        RssFeedConfig(
            "Vancouver Sun",
            "https://vancouversun.com/feed",
            "Vancouver BC Metro Vancouver",
            "Vancouver Sun site/feed terms",
        ),
        RssFeedConfig(
            "Business in Vancouver",
            "https://biv.com/rss",
            "Vancouver BC Metro Vancouver",
            "BIV site/feed terms",
        ),
        RssFeedConfig(
            "STIR Vancouver",
            "https://www.stirvancouver.com/feed/",
            "Vancouver BC Metro Vancouver",
            "STIR site/feed terms",
        ),
        RssFeedConfig(
            "Scout Magazine",
            "https://scoutmagazine.ca/feed/",
            "Vancouver BC Metro Vancouver",
            "Scout Magazine site/feed terms",
        ),
    )

    def __init__(self, limit: int = 50, client: httpx.Client | None = None) -> None:
        self.limit = limit
        self.client = client or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={"user-agent": "wellness-radar/0.1"},
        )
        self.fetch_errors: list[str] = []

    def fetch(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for feed in self.feeds:
            if len(records) >= self.limit:
                break
            try:
                response = self.client.get(feed.url)
                response.raise_for_status()
            except Exception as exc:
                self.fetch_errors.append(f"{feed.outlet}: {exc}")
                continue
            records.extend(_parse_feed(response.text, feed, self.name))
        return records[: self.limit]

    def source_record_id(self, raw: dict[str, Any]) -> str:
        return str(raw.get("guid") or raw.get("link") or raw.get("title") or "")

    def normalize(
        self, raw: dict[str, Any], raw_payload_id: str
    ) -> list[tuple[SourceEventRecord, SignalRecord]]:
        text = _record_text(raw)
        if not _has_wellness_relevance(text):
            return []
        return [_event_and_signal(self, raw, raw_payload_id, self.event_type, self.signal_type)]


class BCGovHealthNewsAdapter(RssFeedAdapter):
    name = "bc_gov_news_rss"
    family = "regulatory/feed"
    cadence = "hourly/daily"
    trust_tier = "official"
    event_type = "regulatory_update"
    signal_type = "official_health_update"
    licence = "BC Government website terms"
    feeds = (
        RssFeedConfig(
            "BC Gov News Health",
            "https://news.gov.bc.ca/ministries/health/feed",
            "British Columbia BC",
            licence,
        ),
    )

    def normalize(
        self, raw: dict[str, Any], raw_payload_id: str
    ) -> list[tuple[SourceEventRecord, SignalRecord]]:
        return [_event_and_signal(self, raw, raw_payload_id, self.event_type, self.signal_type)]


class HealthCanadaRecallsAdapter(RssFeedAdapter):
    name = "health_canada_recalls"
    family = "recall/feed"
    cadence = "as_published"
    trust_tier = "official"
    text_gate = False
    event_type = "recall_alert"
    signal_type = "health_canada_recall"
    licence = "Government of Canada terms"
    feeds = (
        RssFeedConfig(
            "Health Canada recalls",
            "https://recalls-rappels.canada.ca/en/feed/health-products-alerts-recalls",
            "Canada",
            licence,
        ),
    )

    def normalize(
        self, raw: dict[str, Any], raw_payload_id: str
    ) -> list[tuple[SourceEventRecord, SignalRecord]]:
        return [_event_and_signal(self, raw, raw_payload_id, self.event_type, self.signal_type)]


def _event_and_signal(
    adapter: RssFeedAdapter,
    raw: dict[str, Any],
    raw_payload_id: str,
    event_type: str,
    signal_type: str,
) -> tuple[SourceEventRecord, SignalRecord]:
    source_record_id = adapter.source_record_id(raw)
    occurred_at = _parse_datetime(raw.get("published_at"))
    refs = [
        source_ref(
            source_name=adapter.name,
            url=raw.get("link"),
            trust_tier=adapter.trust_tier,
            source_record_id=source_record_id,
            licence=raw.get("licence") or adapter.licence,
        )
    ]
    title = str(raw.get("title") or "Untitled RSS item").strip()
    description = truncate_text(strip_html(raw.get("description")), 360)
    event_id = stable_id("evt", adapter.name, source_record_id, event_type)
    signal_id = stable_id("sig", adapter.name, source_record_id, signal_type)
    severity = _suggest_deterministic_severity(event_type, f"{title} {description}")
    payload = {
        "outlet": raw.get("outlet"),
        "description": description,
        "categories": raw.get("categories", []),
        "link": raw.get("link"),
        "bc_gate_text": _record_text(raw),
    }
    event = SourceEventRecord(
        id=event_id,
        source_name=adapter.name,
        raw_payload_id=raw_payload_id,
        source_record_id=source_record_id,
        event_type=event_type,
        entity_type=None,
        entity_id=None,
        title=title,
        occurred_at=occurred_at,
        trust_tier=adapter.trust_tier,
        lat=None,
        lng=None,
        source_refs=refs,
        confidence_score=0.82 if adapter.trust_tier == "official" else 0.68,
        payload=payload,
    )
    signal = SignalRecord(
        id=signal_id,
        type=signal_type,
        severity=severity,
        title=title,
        summary=description or None,
        why_it_matters=None,
        source_name=adapter.name,
        source_url=raw.get("link"),
        trust_tier=adapter.trust_tier,
        occurred_at=occurred_at,
        lat=None,
        lng=None,
        related_operator_id=None,
        source_event_ids=[event.id],
        raw_payload_id=raw_payload_id,
        source_refs=refs,
        confidence_score=0.82 if adapter.trust_tier == "official" else 0.68,
    )
    return event, signal


def _parse_feed(xml_text: str, feed: RssFeedConfig, source_name: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text.lstrip("\ufeff"))
    records: list[dict[str, Any]] = []
    for item in root.findall(".//item"):
        record = {
            "source_name": source_name,
            "outlet": feed.outlet,
            "feed_url": feed.url,
            "licence": feed.licence,
            "location_text": feed.location_text,
            "title": _child_text(item, "title"),
            "link": _child_text(item, "link"),
            "guid": _child_text(item, "guid"),
            "description": _child_text(item, "description"),
            "published_at": _child_text(item, "pubDate"),
            "categories": [child.text or "" for child in item.findall("category")],
        }
        records.append(record)
    if records:
        return records

    atom_ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.findall(".//atom:entry", atom_ns):
        link = ""
        for link_node in entry.findall("atom:link", atom_ns):
            if link_node.attrib.get("href"):
                link = link_node.attrib["href"]
                break
        records.append(
            {
                "source_name": source_name,
                "outlet": feed.outlet,
                "feed_url": feed.url,
                "licence": feed.licence,
                "location_text": feed.location_text,
                "title": _child_text(entry, "atom:title", atom_ns),
                "link": link,
                "guid": _child_text(entry, "atom:id", atom_ns),
                "description": _child_text(entry, "atom:summary", atom_ns),
                "published_at": _child_text(entry, "atom:updated", atom_ns),
                "categories": [],
            }
        )
    return records


def _child_text(
    item: ET.Element, tag: str, namespaces: dict[str, str] | None = None
) -> str | None:
    child = item.find(tag, namespaces or {})
    if child is None or child.text is None:
        return None
    return child.text.strip()


def _parse_datetime(value: Any) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    raw = str(value).strip()
    try:
        parsed = email.utils.parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _record_text(raw: dict[str, Any]) -> str:
    return " ".join(
        str(value)
        for value in [
            raw.get("title"),
            raw.get("description"),
            raw.get("outlet"),
            raw.get("location_text"),
            " ".join(raw.get("categories", [])),
        ]
        if value
    )


def _has_wellness_relevance(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in WELLNESS_TERMS)


def _suggest_deterministic_severity(event_type: str, text: str) -> str:
    lowered = text.lower()
    if event_type == "recall_alert":
        return "high"
    if any(term in lowered for term in ["recall", "warning", "safety", "regulation"]):
        return "notable"
    if any(term in lowered for term in ["opens", "opening", "launch", "approved", "funding"]):
        return "notable"
    return "info"
