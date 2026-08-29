"""Deterministic phrase/sentence segmentation.

Re-segments a transcript's words into caption/edit-friendly segments using
punctuation, pause length, max duration, and max word count -- all
configurable. This is independent from whatever segmentation an ASR
backend produced originally (that's just its own internal sentence
grouping); this module is the single source of truth for segment
boundaries used by the planner and caption generation.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Segment, Transcript, Word

_SENTENCE_END_CHARS = (".", "!", "?")


@dataclass
class SegmentationConfig:
    max_duration_s: float = 6.0
    max_words: int = 14
    pause_threshold_s: float = 0.6


def _flush(words, segments):
    if not words:
        return
    text = " ".join(w.text for w in words)
    segments.append(Segment(text=text, start=words[0].start, end=words[-1].end, words=list(words)))


def segment_transcript(transcript: Transcript, config: SegmentationConfig = None) -> Transcript:
    """Return a new Transcript whose segments obey the segmentation config.

    Words are taken from the input transcript (flattened across its
    existing segments) and re-grouped. Timestamps are preserved exactly;
    only segment boundaries change.
    """

    config = config or SegmentationConfig()
    words = transcript.words

    segments = []
    if not words:
        return Transcript(segments=[], language=transcript.language, duration=transcript.duration)

    current = [words[0]]
    for prev, w in zip(words, words[1:]):
        gap = w.start - prev.end
        duration_if_added = w.end - current[0].start
        word_count_if_added = len(current) + 1

        ends_sentence = prev.text.strip().endswith(_SENTENCE_END_CHARS)
        long_pause = gap >= config.pause_threshold_s
        too_long = duration_if_added > config.max_duration_s
        too_many_words = word_count_if_added > config.max_words

        if ends_sentence or long_pause or too_long or too_many_words:
            _flush(current, segments)
            current = [w]
        else:
            current.append(w)

    _flush(current, segments)

    return Transcript(segments=segments, language=transcript.language, duration=transcript.duration)
