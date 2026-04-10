from __future__ import annotations

from typing import Any

from core.persona_types import default_profile, normalize_profile, normalize_persona_type, slugify


class ProfileBuilder:
    def build(
        self,
        *,
        character_name: str,
        persona_type: str,
        research_payload: dict[str, Any],
        source_hint: str = "",
    ) -> dict[str, Any]:
        clean_name = character_name.strip() or "Unknown Character"
        normalized_type = normalize_persona_type(persona_type)
        base = default_profile(
            name=clean_name,
            slug=slugify(clean_name),
            source=source_hint or str(research_payload.get("source", "Unknown")),
            persona_type=normalized_type,
        )
        merged = {**base, **research_payload}
        merged["name"] = clean_name
        merged["slug"] = slugify(clean_name)
        merged["persona_type"] = normalized_type
        if source_hint:
            merged["source"] = source_hint
        return normalize_profile(merged)

    @staticmethod
    def infer_persona_type_from_text(raw_text: str, default: str = "canon") -> str:
        lowered = raw_text.lower()
        if "original character" in lowered or "oc" in lowered:
            return "original"
        if "inspired by" in lowered or "like the vibe of" in lowered:
            return "inspired"
        if "canon" in lowered:
            return "canon"
        return default

