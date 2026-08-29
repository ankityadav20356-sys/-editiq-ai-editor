"""Real transcription backend using faster-whisper.

Imports faster_whisper lazily (inside __init__), so importing this module
never fails in environments where the model/package isn't installed --
only actually instantiating FasterWhisperBackend does.
"""

from __future__ import annotations

from typing import Optional

from .models import Segment, Transcript, Word


class FasterWhisperBackend:
    """Wraps faster-whisper's WhisperModel behind the TranscriptionBackend protocol.

    Parameters
    ----------
    model_size:
        e.g. "tiny", "base", "small", "medium", "large-v3".
    device:
        "cpu" or "cuda".
    compute_type:
        e.g. "int8", "float16", "float32". "int8" is a reasonable default
        for CPU-only environments.
    language:
        Force a language code (e.g. "en"), or None to auto-detect.
    beam_size:
        Decoding beam size; higher is slower but can be more accurate.
    """

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        language: Optional[str] = None,
        beam_size: int = 5,
    ) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # pragma: no cover - exercised only without the dep
            raise ImportError(
                "faster-whisper is not installed. Install it (see requirements.txt) "
                "or use transcription.mock_backend.MockTranscriptionBackend for tests."
            ) from exc

        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size
        self._model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, media_path: str) -> Transcript:
        segments_iter, info = self._model.transcribe(
            media_path,
            language=self.language,
            beam_size=self.beam_size,
            word_timestamps=True,
        )

        segments = []
        for seg in segments_iter:
            words = []
            for w in (seg.words or []):
                # faster-whisper word objects: .word, .start, .end, .probability
                text = (w.word or "").strip()
                if not text:
                    continue
                words.append(
                    Word(
                        text=text,
                        start=float(w.start),
                        end=float(w.end),
                        confidence=float(w.probability) if w.probability is not None else None,
                    )
                )
            if not words:
                # Backend returned a segment with no word-level timing; skip
                # rather than fabricate word boundaries we don't actually have.
                continue
            segments.append(
                Segment(
                    text=seg.text.strip(),
                    start=words[0].start,
                    end=words[-1].end,
                    words=words,
                )
            )

        duration = getattr(info, "duration", None)
        language = getattr(info, "language", None) or self.language

        return Transcript(segments=segments, language=language, duration=duration)
