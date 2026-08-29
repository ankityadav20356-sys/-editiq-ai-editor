"""Deterministic mock transcription backend for unit tests and CI.

Does not import faster-whisper, does not require the media file to
actually exist, and always returns the same transcript for the same
configured script -- so tests never depend on a real ML model.
"""

from __future__ import annotations

import re
from typing import Optional

from .models import Segment, Transcript, Word

# Default script chosen to exercise punctuation-based segmentation (two
# sentences) in downstream tests without every test needing its own fixture.
_DEFAULT_SCRIPT = "Your money should never sit idle. Put it to work today."


def _fake_words(script: str, words_per_second: float = 2.5):
    tokens = script.split()
    words = []
    t = 0.0
    step = 1.0 / words_per_second
    for tok in tokens:
        start = round(t, 3)
        end = round(t + step * 0.8, 3)
        words.append(Word(text=tok, start=start, end=end, confidence=0.95))
        t += step
    return words


class MockTranscriptionBackend:
    """Deterministic stand-in for a real ASR backend.

    Parameters
    ----------
    script:
        The text to "transcribe". Defaults to a short two-sentence script.
    duration:
        Optional total media duration in seconds. If omitted, it is
        derived from the last generated word's end time plus a pad.
    language:
        Reported language code.
    """

    def __init__(self, script: str = _DEFAULT_SCRIPT, duration: Optional[float] = None, language: str = "en") -> None:
        self.script = script
        self._duration_override = duration
        self.language = language

    def transcribe(self, media_path: str) -> Transcript:
        # Deliberately does not require the file to exist -- the mock
        # backend's whole point is to be usable without real media or a
        # real ML model in unit tests.
        words = _fake_words(self.script)
        segments = []
        toks = self.script.split()
        current = []
        for i, tok in enumerate(toks):
            current.append(words[i])
            if tok.endswith((".", "!", "?")):
                seg_text = " ".join(w.text for w in current)
                segments.append(Segment(text=seg_text, start=current[0].start, end=current[-1].end, words=list(current)))
                current = []
        if current:
            seg_text = " ".join(w.text for w in current)
            segments.append(Segment(text=seg_text, start=current[0].start, end=current[-1].end, words=list(current)))

        duration = self._duration_override
        if duration is None:
            duration = (words[-1].end + 0.5) if words else 0.0
        return Transcript(segments=segments, language=self.language, duration=duration)
