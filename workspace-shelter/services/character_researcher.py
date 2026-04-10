from __future__ import annotations

import json
from typing import Any, Protocol


class ChatClient(Protocol):
    def complete(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 1.08,
        top_p: float = 0.90,
        presence_penalty: float = 0.2,
        max_tokens: int = 450,
    ) -> Any:
        ...


def _extract_json(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return None

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    candidate = stripped[start : end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


class CharacterResearcher:
    def __init__(self, chat_client: ChatClient) -> None:
        self.chat_client = chat_client

    def research(
        self,
        *,
        character_name: str,
        persona_type: str,
        source_hint: str = "",
    ) -> dict[str, Any]:
        system_prompt = """You are a character research assistant for roleplay fidelity.
Return only JSON with these fields:
- name, source, persona_type, summary
- core_traits (array), tone (array)
- speech_style {formality, pace, humor, vocabulary, signature_patterns[]}
- motivations[], fears[], values[], relationships[]
- behavior_rules[], do_not_break[], catchphrases[], scenario_notes[]
- knowledge_scope {knows_canon_only, can_adapt_to_new_scenarios}
- portrayal_guidelines[], research_notes[], confidence_notes[]

Rules:
- If uncertain, mark uncertainty clearly in confidence_notes.
- Do not invent major canon facts as certain.
- Keep claims concise and grounded.
- Output valid JSON only, no markdown.
"""

        user_prompt = f"""Build a roleplay-ready profile for:
character_name: {character_name}
persona_type: {persona_type}
source_hint: {source_hint or "none"}
"""
        try:
            result = self.chat_client.complete(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.55,
                top_p=0.9,
                presence_penalty=0.0,
                max_tokens=1400,
            )
            parsed = _extract_json(result.text)
            if parsed:
                return parsed
        except Exception as exc:
            return {
                "name": character_name,
                "source": source_hint or "Unknown",
                "persona_type": persona_type,
                "summary": f"Research fallback profile for {character_name}.",
                "core_traits": ["composed", "adaptive"],
                "tone": ["immersive"],
                "speech_style": {
                    "formality": "adaptive",
                    "pace": "measured",
                    "humor": "situational",
                    "vocabulary": "contextual",
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
                    "knows_canon_only": persona_type == "canon",
                    "can_adapt_to_new_scenarios": True,
                },
                "portrayal_guidelines": [],
                "research_notes": ["Automated fallback due to research error."],
                "confidence_notes": [f"Research fallback used: {exc}"],
            }

        return {
            "name": character_name,
            "source": source_hint or "Unknown",
            "persona_type": persona_type,
            "summary": f"Grounded fallback profile for {character_name}.",
            "core_traits": ["composed", "adaptive"],
            "tone": ["immersive"],
            "speech_style": {
                "formality": "adaptive",
                "pace": "measured",
                "humor": "situational",
                "vocabulary": "contextual",
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
                "knows_canon_only": persona_type == "canon",
                "can_adapt_to_new_scenarios": True,
            },
            "portrayal_guidelines": [],
            "research_notes": ["Limited source data, fallback profile generated."],
            "confidence_notes": ["Some fields are inferred due to limited available context."],
        }

