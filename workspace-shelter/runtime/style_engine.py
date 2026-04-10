from __future__ import annotations

import re
from dataclasses import dataclass


EMOTION_ORDER = ["calm", "intrigued", "playful", "intense"]


@dataclass
class StyleDirective:
    mode: str
    persona: str
    user_tone: str
    mood: str
    pacing_hint: str
    narrative_density: str
    tension_level: float


def detect_user_tone(text: str) -> str:
    lowered = text.lower().strip()
    if not lowered:
        return "neutral"

    if re.search(r"\b(sad|hurt|lonely|anxious|stressed|overwhelmed)\b", lowered):
        return "vulnerable"
    if re.search(r"\b(joke|haha|lol|lmao|tease|play)\b", lowered):
        return "playful"
    if re.search(r"\b(angry|mad|annoyed|upset|frustrated)\b", lowered):
        return "tense"
    if re.search(r"\b(why|how|what|explain|help)\b", lowered):
        return "inquisitive"
    if re.search(r"\b(miss you|want you|need you|closer|hold me)\b", lowered):
        return "attached"
    return "neutral"


def update_mood(previous: str, user_tone: str, mode: str) -> str:
    try:
        idx = EMOTION_ORDER.index(previous)
    except ValueError:
        idx = 0

    if user_tone in {"playful", "attached"}:
        idx = min(idx + 1, len(EMOTION_ORDER) - 1)
    elif user_tone == "vulnerable":
        idx = max(idx - 1, 0)
    elif user_tone == "tense":
        idx = max(idx - 1, 0)

    if mode == "casual":
        idx = min(idx, 1)
    if mode == "intense":
        idx = max(idx, 1)

    return EMOTION_ORDER[idx]


def build_style_directive(
    *,
    mode: str,
    persona: str,
    user_tone: str,
    mood: str,
) -> StyleDirective:
    if mode == "casual":
        pacing = "short to medium replies, low-pressure rhythm"
        density = "light narration, mostly dialogue"
        tension = 0.35
    elif mode == "intense":
        pacing = "measured rhythm with meaningful pauses and implication"
        density = "rich narration blended with dialogue"
        tension = 0.85
    else:
        pacing = "natural pacing with gentle rises in tension"
        density = "balanced narration and dialogue"
        tension = 0.65

    if user_tone == "vulnerable":
        pacing = "softer tempo, reassuring and grounded"
        tension = min(tension, 0.45)
    if user_tone == "playful":
        pacing = "quick, teasing cadence"
        tension = max(tension, 0.6)

    return StyleDirective(
        mode=mode,
        persona=persona,
        user_tone=user_tone,
        mood=mood,
        pacing_hint=pacing,
        narrative_density=density,
        tension_level=tension,
    )
