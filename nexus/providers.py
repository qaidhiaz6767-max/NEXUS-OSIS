"""Replaceable language-provider boundary. The provider never executes tools."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
import json
import os


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict


@dataclass(frozen=True)
class ModelReply:
    text: str = ""
    calls: tuple[ToolCall, ...] = ()
    complete: bool = True


class Provider(Protocol):
    def respond(
        self, *, instructions: str, history: list[dict], tools: list[dict]
    ) -> ModelReply: ...


class ProviderUnavailable(Exception):
    pass


class InvalidModelOutput(ValueError):
    pass


class OpenAIResponsesProvider:
    def respond(self, *, instructions, history, tools):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderUnavailable(
                "Optional OpenAI package is unavailable."
            ) from exc
        try:
            response = OpenAI(timeout=25.0, max_retries=0).responses.create(
                model=os.getenv("NEXUS_MODEL", "gpt-4.1-mini"),
                instructions=instructions,
                input=history,
                tools=tools,
                tool_choice="auto",
                max_output_tokens=3000,
                store=False,
            )
        except Exception as exc:
            raise ProviderUnavailable(type(exc).__name__) from exc
        if getattr(response, "status", "completed") != "completed":
            raise InvalidModelOutput(
                "The model response was incomplete; no actions were prepared."
            )
        calls = []
        try:
            for output in getattr(response, "output", []):
                if getattr(output, "type", "") == "function_call":
                    name = getattr(output, "name", None)
                    raw = getattr(output, "arguments", None)
                    if (
                        not isinstance(name, str)
                        or not isinstance(raw, str)
                        or len(raw) > 32000
                    ):
                        raise InvalidModelOutput("Invalid tool envelope.")
                    arguments = json.loads(raw)
                    if not isinstance(arguments, dict):
                        raise InvalidModelOutput("Tool arguments must be an object.")
                    calls.append(ToolCall(name, arguments))
            text = getattr(response, "output_text", "") or ""
            if not isinstance(text, str):
                raise InvalidModelOutput("Invalid model response text.")
        except (TypeError, json.JSONDecodeError) as exc:
            raise InvalidModelOutput("Malformed model tool output.") from exc
        if len(calls) > 5:
            raise InvalidModelOutput("Use at most five tool operations per turn.")
        return ModelReply(text=text[:6000], calls=tuple(calls))
