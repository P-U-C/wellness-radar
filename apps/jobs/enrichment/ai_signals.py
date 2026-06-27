from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from packages.shared.normalizers import strip_html, truncate_text

PROMPT_VERSION = "m2_signal_enrichment_v1"
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-5"


class EnrichmentRepository(Protocol):
    def fetch_signals_for_enrichment(self, limit: int) -> list[dict[str, Any]]:
        ...

    def update_signal_ai_enrichment(self, signal_id: str, enrichment: SignalEnrichment) -> None:
        ...

    def close(self) -> None:
        ...


class SignalEnricher(Protocol):
    model_name: str

    def enrich(self, signal: dict[str, Any]) -> SignalEnrichment:
        ...


@dataclass(frozen=True)
class SignalEnrichment:
    summary: str | None
    why_it_matters: str | None
    category_suggestions: list[str]
    severity_suggestion: str | None
    confidence: float
    prompt_version: str
    model_name: str
    generated_fields: list[str]


class DeterministicSignalEnricher:
    model_name = "deterministic-local-v1"

    def enrich(self, signal: dict[str, Any]) -> SignalEnrichment:
        title = str(signal.get("title") or "Source-backed signal")
        summary = signal.get("summary") or _fallback_summary(signal)
        why = signal.get("why_it_matters") or _fallback_why(signal)
        categories = _category_suggestions(f"{title} {summary}")
        severity = _severity_suggestion(f"{title} {summary}", str(signal.get("severity") or "info"))
        generated_fields = []
        if not signal.get("summary"):
            generated_fields.append("summary")
        if not signal.get("why_it_matters"):
            generated_fields.append("why_it_matters")
        generated_fields.extend(["category_suggestions", "severity_suggestion"])
        return SignalEnrichment(
            summary=summary,
            why_it_matters=why,
            category_suggestions=categories,
            severity_suggestion=severity,
            confidence=0.62,
            prompt_version=PROMPT_VERSION,
            model_name=self.model_name,
            generated_fields=generated_fields,
        )


class ClaudeSignalEnricher:
    def __init__(
        self,
        api_key: str,
        *,
        model_name: str = DEFAULT_CLAUDE_MODEL,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.client = client or httpx.Client(timeout=45.0)

    def enrich(self, signal: dict[str, Any]) -> SignalEnrichment:
        payload = {
            "model": self.model_name,
            "max_tokens": 500,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Return strict JSON for this source-backed wellness market signal. "
                        "Use only supplied fields. Do not add facts or medical advice. "
                        "Allowed keys: summary, why_it_matters, category_suggestions, "
                        "severity_suggestion, confidence.\n\n"
                        f"{json.dumps(_signal_prompt_payload(signal), sort_keys=True, default=str)}"
                    ),
                }
            ],
        }
        response = self.client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        body = response.json()
        text = _anthropic_text(body)
        parsed = json.loads(text)
        return SignalEnrichment(
            summary=_clean_optional(parsed.get("summary")),
            why_it_matters=_clean_optional(parsed.get("why_it_matters")),
            category_suggestions=[
                str(item) for item in parsed.get("category_suggestions", []) if str(item).strip()
            ][:5],
            severity_suggestion=_severity_value(parsed.get("severity_suggestion")),
            confidence=float(parsed.get("confidence") or 0.5),
            prompt_version=PROMPT_VERSION,
            model_name=self.model_name,
            generated_fields=[
                "summary",
                "why_it_matters",
                "category_suggestions",
                "severity_suggestion",
            ],
        )


class SignalEnrichmentService:
    def __init__(
        self,
        repository: EnrichmentRepository,
        enricher: SignalEnricher | None = None,
    ) -> None:
        self.repository = repository
        self.enricher = enricher or enricher_from_env()

    def enrich_pending(self, limit: int = 100) -> int:
        count = 0
        for signal in self.repository.fetch_signals_for_enrichment(limit):
            enrichment = self.enricher.enrich(signal)
            self.repository.update_signal_ai_enrichment(str(signal["id"]), enrichment)
            count += 1
        self.repository.close()
        return count


def enricher_from_env() -> SignalEnricher:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return DeterministicSignalEnricher()
    return ClaudeSignalEnricher(
        api_key,
        model_name=os.getenv("ANTHROPIC_MODEL", DEFAULT_CLAUDE_MODEL),
    )


def _fallback_summary(signal: dict[str, Any]) -> str:
    payload = signal.get("event_payload") or {}
    description = strip_html(str(payload.get("description") or ""))
    if description:
        return truncate_text(description, 260)
    return truncate_text(str(signal.get("title") or "Source-backed signal"), 180)


def _fallback_why(signal: dict[str, Any]) -> str:
    source_name = str(signal.get("source_name") or "the source")
    signal_type = str(signal.get("type") or "market signal").replace("_", " ")
    trust = str(signal.get("trust_tier") or "source-backed")
    return (
        f"This {signal_type} from {source_name} adds {trust} evidence to the Metro Vancouver "
        "wellness market timeline without changing deterministic source facts."
    )


def _category_suggestions(text: str) -> list[str]:
    lowered = text.lower()
    suggestions: list[str] = []
    if any(term in lowered for term in ["sauna", "cold plunge", "contrast", "recovery"]):
        suggestions.append("recovery_contrast_therapy")
    if any(term in lowered for term in ["cryo", "normatec", "compression", "mobility"]):
        suggestions.append("recovery_modalities")
    if any(term in lowered for term in ["spa", "massage", "thermal"]):
        suggestions.append("spa_thermal")
    if any(term in lowered for term in ["botox", "injectable", "filler", "medical aesthetics"]):
        suggestions.append("aesthetics_medspa")
    if any(term in lowered for term in ["prenatal", "postnatal", "pelvic floor", "doula"]):
        suggestions.append("womens_health")
    if any(term in lowered for term in ["sober social", "wellness cafe", "wellness coworking"]):
        suggestions.append("social_hospitality")
    if any(term in lowered for term in ["fitness", "active", "movement"]):
        suggestions.append("fitness_movement")
    if not suggestions and "health" in lowered:
        suggestions.append("allied_health")
    return suggestions[:4]


def _severity_suggestion(text: str, existing: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ["recall", "warning", "unsafe", "serious"]):
        return "high"
    if any(term in lowered for term in ["opens", "opening", "funding", "approved", "regulation"]):
        return "notable"
    return existing if existing in {"info", "notable", "high"} else "info"


def _signal_prompt_payload(signal: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": signal.get("id"),
        "title": signal.get("title"),
        "summary": signal.get("summary"),
        "why_it_matters": signal.get("why_it_matters"),
        "source_name": signal.get("source_name"),
        "type": signal.get("type"),
        "severity": signal.get("severity"),
        "trust_tier": signal.get("trust_tier"),
        "source_refs": signal.get("source_refs"),
        "event_payload": signal.get("event_payload"),
    }


def _anthropic_text(body: dict[str, Any]) -> str:
    chunks = body.get("content") or []
    for chunk in chunks:
        if chunk.get("type") == "text" and chunk.get("text"):
            return str(chunk["text"])
    raise ValueError("Claude response did not include text content")


def _clean_optional(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _severity_value(value: Any) -> str | None:
    cleaned = _clean_optional(value)
    if cleaned in {"info", "notable", "high"}:
        return cleaned
    return None
