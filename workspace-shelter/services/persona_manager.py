from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from core.persona_types import slugify
from services.character_researcher import CharacterResearcher
from services.memory_router import MemoryRouter
from services.profile_builder import ProfileBuilder


@dataclass
class PersonaSwitchOutcome:
    ok: bool
    message: str
    profile: dict[str, Any] | None = None
    created: bool = False


class PersonaManager:
    def __init__(
        self,
        *,
        router: MemoryRouter,
        researcher: CharacterResearcher,
        profile_builder: ProfileBuilder,
    ) -> None:
        self.router = router
        self.researcher = researcher
        self.profile_builder = profile_builder

    def list_personas(self) -> list[dict[str, Any]]:
        return self.router.list_personas()

    def _resolve_slug(self, name_or_slug: str) -> str | None:
        entry = self.router.find_persona_entry(name_or_slug)
        if entry:
            return str(entry.get("slug"))
        guessed = slugify(name_or_slug)
        if self.router.load_profile(guessed):
            return guessed
        return None

    def create_persona(
        self,
        *,
        character_name: str,
        persona_type: str = "canon",
        source_hint: str = "",
    ) -> tuple[dict[str, Any], bool]:
        slug = slugify(character_name)
        existing = self.router.load_profile(slug)
        if existing:
            return existing, False

        research = self.researcher.research(
            character_name=character_name,
            persona_type=persona_type,
            source_hint=source_hint,
        )
        profile = self.profile_builder.build(
            character_name=character_name,
            persona_type=persona_type,
            research_payload=research,
            source_hint=source_hint,
        )
        self.router.save_profile(profile)
        self.router.initialize_persona_memory(profile["slug"], profile["name"])
        self.router.upsert_index_entry(profile)
        return profile, True

    def load_for_user(
        self,
        *,
        user_key: str,
        name_or_slug: str,
        create_if_missing: bool = False,
        persona_type: str = "canon",
        source_hint: str = "",
    ) -> PersonaSwitchOutcome:
        slug = self._resolve_slug(name_or_slug)
        created = False
        profile: dict[str, Any] | None = None

        if not slug and not create_if_missing:
            return PersonaSwitchOutcome(
                ok=False,
                message=f"No saved persona named `{name_or_slug}`.",
            )

        if not slug and create_if_missing:
            profile, created = self.create_persona(
                character_name=name_or_slug,
                persona_type=persona_type,
                source_hint=source_hint,
            )
            slug = profile["slug"]
        else:
            profile = self.router.load_profile(slug or "")

        if not slug or not profile:
            return PersonaSwitchOutcome(ok=False, message="Failed to load persona profile.")

        self.router.set_active_persona(user_key, slug)
        self.router.set_last_used(slug)
        self.router.note_persona_usage(user_key, slug, "load")
        self.router.initialize_persona_memory(slug, profile["name"])

        message = (
            f"Persona `{profile['name']}` created and loaded."
            if created
            else f"Persona switched to `{profile['name']}`."
        )
        return PersonaSwitchOutcome(ok=True, message=message, profile=profile, created=created)

    def turn_off_for_user(self, user_key: str) -> PersonaSwitchOutcome:
        slug = self.router.get_active_persona(user_key)
        if slug:
            self.router.note_persona_usage(user_key, slug, "off")
        self.router.set_active_persona(user_key, None)
        return PersonaSwitchOutcome(ok=True, message="Persona layer off. Shelter base identity restored.")

    def get_active_profile_for_user(self, user_key: str) -> dict[str, Any] | None:
        slug = self.router.get_active_persona(user_key)
        if not slug:
            return None
        return self.router.load_profile(slug)

    def get_active_memory_for_user(self, user_key: str) -> dict[str, Any] | None:
        profile = self.get_active_profile_for_user(user_key)
        if not profile:
            return None
        return self.router.load_persona_memory(profile["slug"], character_name=profile["name"])

    def reset_persona_memory(self, name_or_slug: str) -> PersonaSwitchOutcome:
        slug = self._resolve_slug(name_or_slug)
        if not slug:
            return PersonaSwitchOutcome(ok=False, message=f"No persona found for `{name_or_slug}`.")
        profile = self.router.load_profile(slug)
        if not profile:
            return PersonaSwitchOutcome(ok=False, message=f"Profile missing for `{name_or_slug}`.")
        self.router.reset_persona_memory(slug, profile["name"])
        return PersonaSwitchOutcome(ok=True, message=f"Memory reset for `{profile['name']}`.", profile=profile)

    def get_persona_info(self, name_or_slug: str) -> dict[str, Any] | None:
        slug = self._resolve_slug(name_or_slug)
        if not slug:
            return None
        return self.router.load_profile(slug)

    def record_active_persona_interaction(
        self,
        *,
        user_key: str,
        display_name: str,
        user_message: str,
        assistant_message: str,
        user_tone: str,
        continuity_note: str,
    ) -> None:
        profile = self.get_active_profile_for_user(user_key)
        if not profile:
            return
        self.router.append_persona_interaction(
            slug=profile["slug"],
            character_name=profile["name"],
            user_key=user_key,
            display_name=display_name,
            user_message=user_message,
            assistant_message=assistant_message,
            user_tone=user_tone,
            continuity_note=continuity_note,
        )
        self.router.set_last_used(profile["slug"])
        self.router.note_persona_usage(user_key, profile["slug"], "interaction")

    OFF_PATTERNS = [
        re.compile(r"(?i)\breturn to your normal self\b"),
        re.compile(r"(?i)\breturn to normal\b"),
        re.compile(r"(?i)\bswitch back\b"),
        re.compile(r"(?i)\bpersona off\b"),
        re.compile(r"(?i)\bbe yourself\b"),
    ]

    LOAD_PATTERNS = [
        re.compile(r"(?i)^\s*(?:shelter[,:\s]*)?(?:portray|be|switch to)\s+(.+?)\s*[.!?]*\s*$"),
        re.compile(r"(?i)^\s*load(?: the)? character profile for\s+(.+?)\s*[.!?]*\s*$"),
    ]

    def detect_switch_intent(self, text: str) -> dict[str, Any] | None:
        raw = text.strip()
        if not raw:
            return None
        for pattern in self.OFF_PATTERNS:
            if pattern.search(raw):
                return {"action": "off"}

        for pattern in self.LOAD_PATTERNS:
            match = pattern.match(raw)
            if not match:
                continue
            name = match.group(1).strip(" .!?\"'")
            if name:
                return {
                    "action": "load",
                    "name": name,
                    "switch_only": True,
                }
        return None

