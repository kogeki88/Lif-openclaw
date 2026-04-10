from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from runtime.style_engine import update_mood
except ImportError:  # pragma: no cover - direct script fallback
    from style_engine import update_mood


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class UserState:
    user_key: str
    display_name: str
    mode: str
    persona: str
    mood: str
    relationship_summary: str
    tone_tendency: str
    last_scene: str
    updated_at: str


class ShelterMemoryStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_state (
                  user_key TEXT PRIMARY KEY,
                  display_name TEXT NOT NULL,
                  mode TEXT NOT NULL,
                  persona TEXT NOT NULL,
                  mood TEXT NOT NULL,
                  relationship_summary TEXT NOT NULL,
                  tone_tendency TEXT NOT NULL,
                  last_scene TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS interaction_log (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_key TEXT NOT NULL,
                  ts TEXT NOT NULL,
                  user_message TEXT NOT NULL,
                  assistant_message TEXT NOT NULL,
                  user_tone TEXT NOT NULL,
                  mood_after TEXT NOT NULL,
                  scene_snapshot TEXT NOT NULL,
                  story_beat TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS storyline (
                  storyline_id TEXT PRIMARY KEY,
                  user_key TEXT NOT NULL,
                  title TEXT NOT NULL,
                  summary TEXT NOT NULL,
                  status TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS identity_state (
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )

    def get_or_create_user_state(
        self,
        user_key: str,
        display_name: str,
        default_mode: str,
        default_persona: str,
    ) -> UserState:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM user_state WHERE user_key = ?",
                (user_key,),
            ).fetchone()
            if not row:
                state = UserState(
                    user_key=user_key,
                    display_name=display_name or user_key,
                    mode=default_mode,
                    persona=default_persona,
                    mood="calm",
                    relationship_summary="New connection. Building trust and rhythm.",
                    tone_tendency="unknown",
                    last_scene="No active scene yet.",
                    updated_at=now_iso(),
                )
                conn.execute(
                    """
                    INSERT INTO user_state (
                      user_key, display_name, mode, persona, mood,
                      relationship_summary, tone_tendency, last_scene, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        state.user_key,
                        state.display_name,
                        state.mode,
                        state.persona,
                        state.mood,
                        state.relationship_summary,
                        state.tone_tendency,
                        state.last_scene,
                        state.updated_at,
                    ),
                )
                return state

            return UserState(**dict(row))

    def set_mode(self, user_key: str, mode: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE user_state SET mode = ?, updated_at = ? WHERE user_key = ?",
                (mode, now_iso(), user_key),
            )

    def set_persona(self, user_key: str, persona: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE user_state SET persona = ?, updated_at = ? WHERE user_key = ?",
                (persona, now_iso(), user_key),
            )

    def reset_user(self, user_key: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM interaction_log WHERE user_key = ?", (user_key,))
            conn.execute("DELETE FROM storyline WHERE user_key = ?", (user_key,))
            conn.execute("DELETE FROM user_state WHERE user_key = ?", (user_key,))

    def add_interaction(
        self,
        *,
        user_key: str,
        user_message: str,
        assistant_message: str,
        user_tone: str,
        scene_snapshot: str,
        story_beat: str,
    ) -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT mood FROM user_state WHERE user_key = ?",
                (user_key,),
            ).fetchone()
            mood_before = row["mood"] if row else "calm"
            new_mood = update_mood(mood_before, user_tone, self.get_mode(user_key))
            conn.execute(
                """
                INSERT INTO interaction_log (
                  user_key, ts, user_message, assistant_message,
                  user_tone, mood_after, scene_snapshot, story_beat
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_key,
                    now_iso(),
                    user_message,
                    assistant_message,
                    user_tone,
                    new_mood,
                    scene_snapshot,
                    story_beat,
                ),
            )
            conn.execute(
                """
                UPDATE user_state
                   SET mood = ?,
                       tone_tendency = ?,
                       last_scene = ?,
                       updated_at = ?
                 WHERE user_key = ?
                """,
                (new_mood, user_tone, scene_snapshot, now_iso(), user_key),
            )

    def upsert_storyline(
        self,
        *,
        storyline_id: str,
        user_key: str,
        title: str,
        summary: str,
        status: str = "active",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO storyline (storyline_id, user_key, title, summary, status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(storyline_id)
                DO UPDATE SET
                  title = excluded.title,
                  summary = excluded.summary,
                  status = excluded.status,
                  updated_at = excluded.updated_at
                """,
                (storyline_id, user_key, title, summary, status, now_iso()),
            )

    def get_mode(self, user_key: str) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT mode FROM user_state WHERE user_key = ?",
                (user_key,),
            ).fetchone()
        return row["mode"] if row else "immersive"

    def get_context(self, user_key: str, *, max_logs: int = 8) -> dict[str, Any]:
        with self._connect() as conn:
            state_row = conn.execute(
                "SELECT * FROM user_state WHERE user_key = ?",
                (user_key,),
            ).fetchone()
            logs = conn.execute(
                """
                SELECT ts, user_message, assistant_message, user_tone, mood_after, scene_snapshot, story_beat
                  FROM interaction_log
                 WHERE user_key = ?
                 ORDER BY id DESC
                 LIMIT ?
                """,
                (user_key, max_logs),
            ).fetchall()
            storylines = conn.execute(
                """
                SELECT storyline_id, title, summary, status, updated_at
                  FROM storyline
                 WHERE user_key = ?
                 ORDER BY updated_at DESC
                 LIMIT 6
                """,
                (user_key,),
            ).fetchall()

        return {
            "state": dict(state_row) if state_row else {},
            "recent_interactions": [dict(x) for x in logs][::-1],
            "storylines": [dict(x) for x in storylines],
        }

    def summary(self, user_key: str) -> dict[str, Any]:
        ctx = self.get_context(user_key, max_logs=6)
        state = ctx["state"] or {}
        interactions = ctx["recent_interactions"]
        return {
            "user_key": user_key,
            "mode": state.get("mode", "immersive"),
            "persona": state.get("persona", "velvet"),
            "mood": state.get("mood", "calm"),
            "relationship_summary": state.get("relationship_summary", "No summary yet."),
            "last_scene": state.get("last_scene", "No active scene."),
            "recent_moments": [
                {
                    "time": item["ts"],
                    "tone": item["user_tone"],
                    "scene": item["scene_snapshot"],
                    "beat": item["story_beat"],
                }
                for item in interactions
            ],
            "active_storylines": ctx["storylines"],
        }

    def to_json(self, payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=True, indent=2)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Shelter memory CLI")
    parser.add_argument("--db", required=True, help="Path to sqlite db")
    sub = parser.add_subparsers(dest="cmd", required=True)

    init_p = sub.add_parser("init")
    init_p.add_argument("--user", required=True)
    init_p.add_argument("--display-name", default="")
    init_p.add_argument("--mode", default="immersive")
    init_p.add_argument("--persona", default="velvet")

    ctx_p = sub.add_parser("context")
    ctx_p.add_argument("--user", required=True)
    ctx_p.add_argument("--max-logs", type=int, default=8)

    set_mode_p = sub.add_parser("set-mode")
    set_mode_p.add_argument("--user", required=True)
    set_mode_p.add_argument("--mode", required=True)

    set_persona_p = sub.add_parser("set-persona")
    set_persona_p.add_argument("--user", required=True)
    set_persona_p.add_argument("--persona", required=True)

    reset_p = sub.add_parser("reset")
    reset_p.add_argument("--user", required=True)

    summary_p = sub.add_parser("summary")
    summary_p.add_argument("--user", required=True)

    add_p = sub.add_parser("add")
    add_p.add_argument("--user", required=True)
    add_p.add_argument("--user-message", required=True)
    add_p.add_argument("--assistant-message", required=True)
    add_p.add_argument("--user-tone", required=True)
    add_p.add_argument("--scene", default="ambient")
    add_p.add_argument("--beat", default="continuing")

    args = parser.parse_args()
    store = ShelterMemoryStore(args.db)

    if args.cmd == "init":
        state = store.get_or_create_user_state(
            user_key=args.user,
            display_name=args.display_name or args.user,
            default_mode=args.mode,
            default_persona=args.persona,
        )
        print(store.to_json(asdict(state)))
        return

    if args.cmd == "context":
        print(store.to_json(store.get_context(args.user, max_logs=args.max_logs)))
        return

    if args.cmd == "set-mode":
        store.set_mode(args.user, args.mode)
        print(store.to_json({"status": "ok", "user": args.user, "mode": args.mode}))
        return

    if args.cmd == "set-persona":
        store.set_persona(args.user, args.persona)
        print(
            store.to_json({"status": "ok", "user": args.user, "persona": args.persona})
        )
        return

    if args.cmd == "reset":
        store.reset_user(args.user)
        print(store.to_json({"status": "ok", "user": args.user, "reset": True}))
        return

    if args.cmd == "summary":
        print(store.to_json(store.summary(args.user)))
        return

    if args.cmd == "add":
        store.add_interaction(
            user_key=args.user,
            user_message=args.user_message,
            assistant_message=args.assistant_message,
            user_tone=args.user_tone,
            scene_snapshot=args.scene,
            story_beat=args.beat,
        )
        print(store.to_json({"status": "ok", "user": args.user}))
        return


if __name__ == "__main__":
    main()
