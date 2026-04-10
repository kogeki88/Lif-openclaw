from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any


VALID_PERSONA_TYPES = {"canon", "inspired", "original"}


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "unnamed-persona"


def _listify(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def normalize_persona_type(persona_type: str) -> str:
    kind = (persona_type or "canon").strip().lower()
    return kind if kind in VALID_PERSONA_TYPES else "canon"


def default_profile(
    *,
    name: str,
    slug: str,
    source: str = "Unknown",
    persona_type: str = "canon",
) -> dict[str, Any]:
    return {
        "name": name,
        "slug": slug,
        "source": source,
        "persona_type": normalize_persona_type(persona_type),
        "summary": "",
        "core_traits": [],
        "tone": [],
        "speech_style": {
            "formality": "",
            "pace": "",
            "humor": "",
            "vocabulary": "",
            "signature_patterns": [],
        },
        "motivations": [],
        "fears": [],
        "values": [],
        "relationships": [],
        "behavior_rules": [],
        "do_not_break": [],
        "catchphrases": [],
        "scenario_notes": [],
        "knowledge_scope": {
            "knows_canon_only": True,
            "can_adapt_to_new_scenarios": True,
        },
        "portrayal_guidelines": [],
        "research_notes": [],
        "confidence_notes": [],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def normalize_profile(candidate: dict[str, Any]) -> dict[str, Any]:
    profile = default_profile(
        name=str(candidate.get("name", "Unknown Character")).strip(),
        slug=slugify(str(candidate.get("slug", candidate.get("name", "character")))),
        source=str(candidate.get("source", "Unknown")).strip() or "Unknown",
        persona_type=str(candidate.get("persona_type", "canon")),
    )

    profile["summary"] = str(candidate.get("summary", "")).strip()
    profile["core_traits"] = _listify(candidate.get("core_traits"))
    profile["tone"] = _listify(candidate.get("tone"))

    speech = candidate.get("speech_style", {}) if isinstance(candidate, dict) else {}
    profile["speech_style"] = {
        "formality": str(speech.get("formality", "")).strip(),
        "pace": str(speech.get("pace", "")).strip(),
        "humor": str(speech.get("humor", "")).strip(),
        "vocabulary": str(speech.get("vocabulary", "")).strip(),
        "signature_patterns": _listify(speech.get("signature_patterns")),
    }

    profile["motivations"] = _listify(candidate.get("motivations"))
    profile["fears"] = _listify(candidate.get("fears"))
    profile["values"] = _listify(candidate.get("values"))
    profile["relationships"] = _listify(candidate.get("relationships"))
    profile["behavior_rules"] = _listify(candidate.get("behavior_rules"))
    profile["do_not_break"] = _listify(candidate.get("do_not_break"))
    profile["catchphrases"] = _listify(candidate.get("catchphrases"))
    profile["scenario_notes"] = _listify(candidate.get("scenario_notes"))

    scope = candidate.get("knowledge_scope", {})
    if not isinstance(scope, dict):
        scope = {}
    profile["knowledge_scope"] = {
        "knows_canon_only": bool(scope.get("knows_canon_only", True)),
        "can_adapt_to_new_scenarios": bool(scope.get("can_adapt_to_new_scenarios", True)),
    }

    profile["portrayal_guidelines"] = _listify(candidate.get("portrayal_guidelines"))
    profile["research_notes"] = _listify(candidate.get("research_notes"))
    profile["confidence_notes"] = _listify(candidate.get("confidence_notes"))

    profile["created_at"] = str(candidate.get("created_at", profile["created_at"]))
    profile["updated_at"] = now_iso()
    return profile


def default_persona_memory(character_name: str) -> dict[str, Any]:
    return {
        "character": character_name,
        "last_active": "",
        "user_relationship_notes": [],
        "story_arcs": [],
        "continuity_notes": [],
        "important_interactions": [],
        "learned_preferences": [],
        "persona_state": {
            "current_mood": "calm",
            "current_dynamic": "neutral",
            "current_context": "",
        },
    }

