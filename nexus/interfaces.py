"""Future adapters have no implicit authority. No scheduler or swarm is enabled."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CapabilityContext:
    workspace: str
    capabilities: frozenset[str]
    max_operations: int = 5
    authority_level: int = 1


class SpecialistAgent(Protocol):
    def plan(
        self, command: str, context: dict, *, authority: CapabilityContext
    ) -> dict:
        """Return a draft through Core. No direct storage, external or shell authority."""
        ...


class AuthorizedScheduler(Protocol):
    def preview(
        self, *, workspace: str, operation: str, when: str, approval_id: str
    ) -> dict:
        """Future schedule preview; this protocol does not execute recurring work."""
        ...


class SpeechToText(Protocol):
    def transcribe(self, audio: bytes, *, consent: bool, language: str) -> str: ...
    def cancel(self) -> None: ...


class TextToSpeech(Protocol):
    def speak(self, text: str, *, consent: bool, language: str) -> None: ...
    def cancel(self) -> None: ...


class VoiceInput(Protocol):
    def transcribe(self, audio: bytes) -> str: ...


class Integration(Protocol):
    def preview(self, arguments: dict, *, authority: CapabilityContext) -> dict:
        """Future explicit account/scopes boundary; no external connection is installed."""
        ...


SPECIALIST_MANIFESTS = {
    "osis": {"role": "OSIS Coordinator", "active": False, "authority_level": 1},
    "personal": {
        "role": "Personal Executive Assistant",
        "active": False,
        "authority_level": 1,
    },
    "research": {"role": "Research Analyst", "active": False, "authority_level": 1},
    "academic": {"role": "Academic Assistant", "active": False, "authority_level": 1},
    "coding": {"role": "Coding Assistant", "active": False, "authority_level": 1},
    "atlas": {"role": "ATLAS Intelligence", "active": False, "authority_level": 1},
}
