"""Internal data models for transcription output.

Deliberately plain dataclasses (stdlib only) -- consistent with the
existing project convention in schemas/validate.py of not adding a hard
runtime dependency (pydantic/jsonschema) for something this project can
fully control itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Word:
    """A single transcribed word with timing."""

    text: str
    start: float
    end: float
    confidence: Optional[float] = None

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(
                f"Word {self.text!r}: end ({self.end}) before start ({self.start})"
            )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Segment:
    """A contiguous run of words (a phrase/sentence-ish unit)."""

    text: str
    start: float
    end: float
    words: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(
                f"Segment {self.text!r}: end ({self.end}) before start ({self.start})"
            )

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "words": [w.to_dict() for w in self.words],
        }


@dataclass
class Transcript:
    """Full transcription result for one media file."""

    segments: list = field(default_factory=list)
    language: Optional[str] = None
    duration: Optional[float] = None

    @property
    def words(self):
        out = []
        for seg in self.segments:
            out.extend(seg.words)
        return out

    @property
    def text(self) -> str:
        return " ".join(seg.text.strip() for seg in self.segments if seg.text.strip())

    def to_dict(self) -> dict:
        return {
            "segments": [s.to_dict() for s in self.segments],
            "language": self.language,
            "duration": self.duration,
        }
