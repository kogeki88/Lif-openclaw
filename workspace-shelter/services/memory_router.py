from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.persona_types import default_persona_memory, now_iso, slugify


class MemoryRouter:
    def __init__(self, agent_root: Path, personas_root: Path | None = None) -> None:
        self.agent_root = agent_root.resolve()
        self.memory_root = self.agent_root / "memory"
        self.personas_root = (
            personas_root.resolve() if personas_root else self.agent_root / "personas"
        )
        self.index_path = self.personas_root / "index.json"
        self.base_memory_path = self.memory_root / "base_memory.json"
        self.ensure_layout()

    def ensure_layout(self) -> None:
        self.memory_root.mkdir(parents=True, exist_ok=True)
        self.personas_root.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self._write_json(self.index_path, {"personas": []})
        if not self.base_memory_path.exists():
            self._write_json(
                self.base_memory_path,
                {
                    "agent": "Shelter",
                    "last_updated": now_iso(),
                    "active_persona_by_user": {},
                    "persona_usage_log": [],
                },
            )

    def _read_json(self, path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return fallback
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return fallback

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

    def load_index(self) -> dict[str, Any]:
        return self._read_json(self.index_path, {"personas": []})

    def save_index(self, payload: dict[str, Any]) -> None:
        self._write_json(self.index_path, payload)

    def list_personas(self) -> list[dict[str, Any]]:
        return list(self.load_index().get("personas", []))

    def find_persona_entry(self, name_or_slug: str) -> dict[str, Any] | None:
        query_slug = slugify(name_or_slug)
        query_name = name_or_slug.strip().lower()
        for entry in self.list_personas():
            if str(entry.get("slug", "")).lower() == query_slug:
                return entry
            if str(entry.get("name", "")).strip().lower() == query_name:
                return entry
        return None

    def persona_dir(self, slug: str) -> Path:
        return self.personas_root / slug

    def profile_path(self, slug: str) -> Path:
        return self.persona_dir(slug) / "profile.json"

    def persona_memory_path(self, slug: str) -> Path:
        return self.persona_dir(slug) / "memory.json"

    def scenes_dir(self, slug: str) -> Path:
        return self.persona_dir(slug) / "scenes"

    def load_profile(self, slug: str) -> dict[str, Any] | None:
        path = self.profile_path(slug)
        if not path.exists():
            return None
        return self._read_json(path, {})

    def save_profile(self, profile: dict[str, Any]) -> None:
        slug = str(profile.get("slug", "")).strip()
        if not slug:
            raise ValueError("Profile missing slug")
        folder = self.persona_dir(slug)
        folder.mkdir(parents=True, exist_ok=True)
        self.scenes_dir(slug).mkdir(parents=True, exist_ok=True)
        self._write_json(self.profile_path(slug), profile)

    def load_persona_memory(self, slug: str, character_name: str = "") -> dict[str, Any]:
        path = self.persona_memory_path(slug)
        default_payload = default_persona_memory(character_name or slug)
        return self._read_json(path, default_payload)

    def save_persona_memory(self, slug: str, payload: dict[str, Any]) -> None:
        payload["last_active"] = payload.get("last_active") or now_iso()
        self._write_json(self.persona_memory_path(slug), payload)

    def initialize_persona_memory(self, slug: str, character_name: str) -> None:
        path = self.persona_memory_path(slug)
        if not path.exists():
            self.save_persona_memory(slug, default_persona_memory(character_name))

    def reset_persona_memory(self, slug: str, character_name: str) -> None:
        self.save_persona_memory(slug, default_persona_memory(character_name))

    def upsert_index_entry(self, profile: dict[str, Any]) -> None:
        index = self.load_index()
        entries = index.get("personas", [])
        slug = profile["slug"]
        now = now_iso()
        payload = {
            "name": profile["name"],
            "slug": slug,
            "source": profile.get("source", "Unknown"),
            "created_at": profile.get("created_at", now),
            "last_used": profile.get("last_used", ""),
            "type": profile.get("persona_type", "canon"),
        }
        found = False
        for entry in entries:
            if entry.get("slug") == slug:
                entry.update(payload)
                found = True
                break
        if not found:
            entries.append(payload)
        index["personas"] = sorted(entries, key=lambda x: x.get("name", "").lower())
        self.save_index(index)

    def set_last_used(self, slug: str) -> None:
        index = self.load_index()
        changed = False
        for entry in index.get("personas", []):
            if entry.get("slug") == slug:
                entry["last_used"] = now_iso()
                changed = True
                break
        if changed:
            self.save_index(index)

    def load_base_memory(self) -> dict[str, Any]:
        return self._read_json(
            self.base_memory_path,
            {
                "agent": "Shelter",
                "last_updated": now_iso(),
                "active_persona_by_user": {},
                "persona_usage_log": [],
            },
        )

    def save_base_memory(self, payload: dict[str, Any]) -> None:
        payload["last_updated"] = now_iso()
        self._write_json(self.base_memory_path, payload)

    def get_active_persona(self, user_key: str) -> str | None:
        data = self.load_base_memory()
        value = data.get("active_persona_by_user", {}).get(user_key)
        return str(value) if value else None

    def set_active_persona(self, user_key: str, slug: str | None) -> None:
        data = self.load_base_memory()
        by_user = data.setdefault("active_persona_by_user", {})
        if slug:
            by_user[user_key] = slug
        else:
            by_user.pop(user_key, None)
        self.save_base_memory(data)

    def note_persona_usage(self, user_key: str, slug: str, event: str) -> None:
        data = self.load_base_memory()
        usage = data.setdefault("persona_usage_log", [])
        usage.append(
            {
                "time": now_iso(),
                "user_key": user_key,
                "persona_slug": slug,
                "event": event,
            }
        )
        data["persona_usage_log"] = usage[-200:]
        self.save_base_memory(data)

    def append_persona_interaction(
        self,
        *,
        slug: str,
        character_name: str,
        user_key: str,
        display_name: str,
        user_message: str,
        assistant_message: str,
        user_tone: str,
        continuity_note: str,
    ) -> None:
        payload = self.load_persona_memory(slug, character_name=character_name)
        payload["character"] = character_name
        payload["last_active"] = now_iso()

        interactions = payload.setdefault("important_interactions", [])
        interactions.append(
            {
                "time": now_iso(),
                "user_key": user_key,
                "display_name": display_name,
                "user_message": user_message,
                "assistant_message": assistant_message,
                "user_tone": user_tone,
            }
        )
        payload["important_interactions"] = interactions[-80:]

        continuity = payload.setdefault("continuity_notes", [])
        if continuity_note:
            continuity.append(continuity_note)
        payload["continuity_notes"] = continuity[-80:]

        relationship_notes = payload.setdefault("user_relationship_notes", [])
        relationship_notes.append(
            {
                "user_key": user_key,
                "note": f"{display_name} tone={user_tone}",
                "updated_at": now_iso(),
            }
        )
        payload["user_relationship_notes"] = relationship_notes[-60:]

        preferences = payload.setdefault("learned_preferences", [])
        lowered = user_message.lower()
        if "prefer" in lowered or "i like" in lowered or "don't like" in lowered:
            preferences.append(
                {
                    "time": now_iso(),
                    "user_key": user_key,
                    "note": user_message[:220],
                }
            )
        payload["learned_preferences"] = preferences[-60:]

        payload.setdefault("persona_state", {})
        payload["persona_state"]["current_mood"] = user_tone
        payload["persona_state"]["current_dynamic"] = "engaged"
        payload["persona_state"]["current_context"] = continuity_note[:180]

        self.save_persona_memory(slug, payload)

