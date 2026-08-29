"""Backend interface: the contract every transcription backend must satisfy.

The planner/pipeline depend only on this ``Protocol`` -- never on a
concrete backend -- so Faster-Whisper can be swapped for the mock (tests)
or a future backend without touching downstream code.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import Transcript


@runtime_checkable
class TranscriptionBackend(Protocol):
    """Anything with a ``transcribe(media_path) -> Transcript`` method."""

    def transcribe(self, media_path: str) -> Transcript:
        ...
