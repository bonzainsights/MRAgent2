"""
MRAgent — DeepSeek LLM Provider
Chat completions via DeepSeek API (OpenAI-compatible SDK).
Supports deepseek-chat (V3) and deepseek-reasoner (R1).

Free tier: https://platform.deepseek.com — generous free credits.
Created: 2026-02-27
"""

import os
import time
from typing import Generator

from openai import OpenAI

from providers.base import LLMProvider
from utils.logger import get_logger

logger = get_logger("providers.deepseek_llm")

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

DEEPSEEK_MODELS = {
    "deepseek-chat": {
        "id": "deepseek-chat",
        "description": "DeepSeek V3 — fast & capable general-purpose LLM (Free API)",
        "supports_tools": True,
        "context_window": 64_000,
        "categories": ["thinking", "fast", "code"],
    },
    "deepseek-reasoner": {
        "id": "deepseek-reasoner",
        "description": "DeepSeek R1 — advanced reasoning & math (Free API)",
        "supports_tools": False,
        "context_window": 64_000,
        "categories": ["thinking"],
    },
}


class DeepSeekLLMProvider(LLMProvider):
    """
    DeepSeek LLM provider using OpenAI-compatible API.

    Supports:
        - deepseek-chat   (DeepSeek V3 — general purpose, tools supported)
        - deepseek-reasoner (DeepSeek R1 — advanced reasoning)

    API key is read from DEEPSEEK_API_KEY environment variable.
    """

    def __init__(self, rate_limit_rpm: int = 30):
        super().__init__(name="deepseek_llm", rate_limit_rpm=rate_limit_rpm)
        self._api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self._client: OpenAI | None = None
        if not self._api_key:
            self.logger.warning("DEEPSEEK_API_KEY not set — DeepSeek provider unavailable")
        else:
            self.logger.info("DeepSeek LLM provider initialized")

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def _get_client(self) -> OpenAI:
        """Lazy-initialise OpenAI client pointing at DeepSeek."""
        if self._client is None:
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=DEEPSEEK_BASE_URL,
                timeout=60.0,
            )
        return self._client

    def chat(
        self,
        messages: list[dict],
        model: str = "deepseek-chat",
        stream: bool = True,
        tools: list[dict] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict | Generator:
        """
        Send a chat completion to DeepSeek API.

        Args:
            messages:    Chat history [{\"role\": \"user\", \"content\": \"...\"}]
            model:       \"deepseek-chat\" or \"deepseek-reasoner\"
            stream:      Stream response chunks
            tools:       Tool definitions for function calling
            temperature: Creativity (0.0-2.0)
            max_tokens:  Max response length

        Returns:
            If stream=False: {\"content\": str, \"tool_calls\": list, \"usage\": dict}
            If stream=True:  Generator yielding {\"delta\": str} or {\"tool_calls\": list}
        """
        if not self.available:
            raise RuntimeError("DeepSeek API key not configured. Set DEEPSEEK_API_KEY in .env")

        # Normalise model name
        if model not in DEEPSEEK_MODELS:
            self.logger.warning(f"Unknown DeepSeek model '{model}', defaulting to deepseek-chat")
            model = "deepseek-chat"

        model_info = DEEPSEEK_MODELS[model]
        client = self._get_client()

        self.logger.debug(f"DeepSeek chat request: model={model}, stream={stream}")
        start_time = time.time()

        def _make_request():
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": stream,
            }
            # R1 (reasoner) does not support tool calling
            if tools and model_info.get("supports_tools", True):
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            elif tools:
                self.logger.debug(f"Skipping tools for {model} — not supported")
            return client.chat.completions.create(**kwargs)

        response = self._retry_call(_make_request)
        duration_ms = (time.time() - start_time) * 1000

        if stream:
            return self._handle_stream(response, model, duration_ms)
        else:
            return self._handle_response(response, model, duration_ms)

    # ──────────────────────────────────────────────
    # Response handlers (mirrored from nvidia_llm)
    # ──────────────────────────────────────────────

    def _handle_response(self, response, model_id: str, duration_ms: float) -> dict:
        """Process a non-streaming response."""
        choice = response.choices[0]
        message = choice.message

        result = {
            "content": message.content or "",
            "tool_calls": [],
            "usage": {},
            "model": model_id,
            "finish_reason": choice.finish_reason,
        }

        if message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]

        if response.usage:
            result["usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        tokens = result["usage"].get("total_tokens", 0)
        self._track_call("chat/completions", model_id, duration_ms,
                         status="ok", tokens_used=tokens)
        return result

    def _handle_stream(self, response, model_id: str, start_duration_ms: float) -> Generator:
        """Process a streaming response, yielding chunks."""
        full_content = ""
        tool_calls_buffer = {}

        try:
            for chunk in response:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                if delta.content:
                    full_content += delta.content
                    yield {"delta": delta.content, "type": "content"}

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_buffer:
                            tool_calls_buffer[idx] = {
                                "id": tc.id or "",
                                "function": {"name": "", "arguments": ""},
                            }
                        if tc.id:
                            tool_calls_buffer[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_buffer[idx]["function"]["name"] += tc.function.name
                            if tc.function.arguments:
                                tool_calls_buffer[idx]["function"]["arguments"] += tc.function.arguments

                if chunk.choices[0].finish_reason:
                    if tool_calls_buffer:
                        yield {
                            "tool_calls": list(tool_calls_buffer.values()),
                            "type": "tool_calls",
                        }
                    yield {
                        "finish_reason": chunk.choices[0].finish_reason,
                        "type": "finish",
                        "full_content": full_content,
                    }

        finally:
            duration_ms = (time.time() * 1000) - start_duration_ms
            self._track_call("chat/completions", model_id, duration_ms,
                             status="ok", tokens_used=len(full_content) // 4)

    def list_models(self) -> list[dict]:
        """Return available DeepSeek models."""
        return [
            {
                "name": name,
                "id": info["id"],
                "description": info["description"],
                "context_window": info["context_window"],
                "available": self.available,
            }
            for name, info in DEEPSEEK_MODELS.items()
        ]
