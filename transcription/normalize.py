"""Conservative transcript normalization.

Cleans obvious ASR artifacts without rewriting spoken language:
- collapses repeated whitespace
- strips leading/trailing whitespace per word/segment
- de-duplicates immediately-repeated tokens caused by ASR stutter
  artifacts (e.g. "the the bank") ONLY when the repeat is an exact,
  case-insensitive duplicate with near-zero time gap -- never merges
  distinct repeated words a speaker actually said with meaningful pause.
- never invents, translates, or paraphrases content
- never modifies timestamps

This is intentionally NOT an LLM-based rewrite. It is a small set of
deterministic, explainable rules.
"""

from __future__ import annotations

import re

from .models import Segment, Transcript, Word

_WHITESPACE_RE = re.compile(r"\s+")

# If two consecutive identical (case-insensitive) words are separated by
# less than this many seconds, treat the second as a stutter/ASR artifact
# duplicate and drop it. Real speech repetition ("no, no, I mean...") has
# a larger gap than a transcription glitch.
_DUPLICATE_GAP_THRESHOLD = 0.05


def _clean_word_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _dedupe_stutter_words(words):
    if not words:
        return []
    out = [words[0]]
    for w in words[1:]:
        prev = out[-1]
        gap = w.start - prev.end
        if w.text.lower() == prev.text.lower() and gap < _DUPLICATE_GAP_THRESHOLD:
            # Keep the one with the wider time span / higher confidence,
            # drop the duplicate rather than silently merging timestamps.
            if (w.confidence or 0) > (prev.confidence or 0):
                out[-1] = w
            continue
        out.append(w)
    return out


def normalize_transcript(transcript: Transcript) -> Transcript:
    """Return a new, conservatively-normalized Transcript.

    The input transcript is not mutated.
    """

    new_segments = []
    for seg in transcript.segments:
        cleaned_words = []
        for w in _dedupe_stutter_words(seg.words):
            text = _clean_word_text(w.text)
            if not text:
                continue
            cleaned_words.append(Word(text=text, start=w.start, end=w.end, confidence=w.confidence))

        if cleaned_words:
            seg_text = " ".join(w.text for w in cleaned_words)
            start = cleaned_words[0].start
            end = cleaned_words[-1].end
        else:
            seg_text = _clean_word_text(seg.text)
            start = seg.start
            end = seg.end

        new_segments.append(Segment(text=seg_text, start=start, end=end, words=cleaned_words))

    return Transcript(segments=new_segments, language=transcript.language, duration=transcript.duration)
