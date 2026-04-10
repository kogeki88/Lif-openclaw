from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class ChatResult:
    text: str
    model: str
    provider: str


class OpenRouterError(RuntimeError):
    def __init__(self, *, message: str, status_code: int | None = None, detail: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class OpenRouterClient:
    def __init__(
        self,
        *,
        api_key: str,
        primary_model: str,
        fallback_models: list[str],
        site_url: str,
        app_name: str,
        timeout_seconds: int = 60,
    ) -> None:
        self.api_key = api_key
        self.primary_model = primary_model
        self.fallback_models = fallback_models
        self.site_url = site_url
        self.app_name = app_name
        self.timeout_seconds = timeout_seconds
        self.endpoint = "https://openrouter.ai/api/v1/chat/completions"

    @classmethod
    def from_env(cls) -> "OpenRouterClient":
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is missing")

        primary = os.getenv(
            "OPENROUTER_MODEL_PRIMARY", "openrouter/gryphe/mythomax-l2-13b"
        ).strip()
        fallback_csv = os.getenv(
            "OPENROUTER_MODEL_FALLBACKS",
            "openrouter/deepseek/deepseek-r1",
        )
        fallbacks = [x.strip() for x in fallback_csv.split(",") if x.strip()]
        site_url = os.getenv("OPENROUTER_SITE_URL", "https://openclaw.local")
        app_name = os.getenv("OPENROUTER_APP_NAME", "Shelter")
        return cls(
            api_key=api_key,
            primary_model=primary,
            fallback_models=fallbacks,
            site_url=site_url,
            app_name=app_name,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.site_url,
            "X-Title": self.app_name,
        }

    @staticmethod
    def _normalize_model_id(model: str) -> str:
        # OpenClaw model ids are often stored as "openrouter/<provider>/<model>".
        # OpenRouter chat completions expects "<provider>/<model>".
        if model.startswith("openrouter/"):
            return model.split("openrouter/", 1)[1]
        return model

    def complete(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 1.08,
        top_p: float = 0.90,
        presence_penalty: float = 0.2,
        max_tokens: int = 450,
    ) -> ChatResult:
        candidates = [self.primary_model, *self.fallback_models]
        last_error = ""
        last_status: int | None = None

        for model in candidates:
            request_model = self._normalize_model_id(model)
            payload = {
                "model": request_model,
                "messages": messages,
                "temperature": temperature,
                "top_p": top_p,
                "presence_penalty": presence_penalty,
                "max_tokens": max_tokens,
            }
            try:
                res = requests.post(
                    self.endpoint,
                    headers=self._headers(),
                    data=json.dumps(payload),
                    timeout=self.timeout_seconds,
                )
                if res.status_code >= 400:
                    last_status = res.status_code
                    last_error = f"{res.status_code} {res.text[:300]}"
                    continue
                body: dict[str, Any] = res.json()
                choices = body.get("choices") or []
                if not choices:
                    last_error = f"no choices from {model}"
                    continue
                text = (choices[0].get("message") or {}).get("content", "").strip()
                if not text:
                    last_error = f"empty text from {model}"
                    continue
                return ChatResult(
                    text=text,
                    model=body.get("model", request_model),
                    provider="openrouter",
                )
            except requests.RequestException as exc:
                last_status = None
                last_error = str(exc)
                continue

        raise OpenRouterError(
            message="All OpenRouter models failed",
            status_code=last_status,
            detail=last_error,
        )
