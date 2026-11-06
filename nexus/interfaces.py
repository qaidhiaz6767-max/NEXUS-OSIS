"""Extension contracts. Implementations receive scoped data, not file/shell access."""
from typing import Protocol

class SpecialistAgent(Protocol):
    def plan(self, command: str, context: dict) -> dict:
        """Return suggestions; the orchestrator validates and proposes all writes."""
        ...

class VoiceInput(Protocol):
    def transcribe(self, audio: bytes) -> str: ...

class Integration(Protocol):
    def preview(self, arguments: dict) -> dict:
        """No external side effects; execution needs a future approved adapter."""
        ...
