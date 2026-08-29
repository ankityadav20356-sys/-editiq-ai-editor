"""Transcription layer: backend-agnostic speech-to-text with word timestamps.

The planner and pipeline depend only on the models and the
``TranscriptionBackend`` protocol defined here -- never on a specific
backend implementation (e.g. Faster-Whisper).
"""

from .models import Word, Segment, Transcript
from .backend import TranscriptionBackend
from .mock_backend import MockTranscriptionBackend
from .normalize import normalize_transcript
from .segment import segment_transcript

__all__ = [
    "Word",
    "Segment",
    "Transcript",
    "TranscriptionBackend",
    "MockTranscriptionBackend",
    "normalize_transcript",
    "segment_transcript",
]
