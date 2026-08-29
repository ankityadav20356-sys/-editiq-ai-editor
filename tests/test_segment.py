from transcription.models import Segment, Transcript, Word
from transcription.segment import SegmentationConfig, segment_transcript


def _words(specs):
    return [Word(text=t, start=s, end=e) for (t, s, e) in specs]


def test_segment_splits_on_punctuation():
    words = _words([
        ("Hello.", 0.0, 0.5),
        ("World.", 0.6, 1.0),
    ])
    t = Transcript(segments=[Segment(text="Hello. World.", start=0.0, end=1.0, words=words)])
    out = segment_transcript(t)
    assert len(out.segments) == 2
    assert out.segments[0].text == "Hello."
    assert out.segments[1].text == "World."


def test_segment_splits_on_long_pause():
    words = _words([
        ("um", 0.0, 0.2),
        ("yeah", 5.0, 5.2),  # big gap, no punctuation
    ])
    t = Transcript(segments=[Segment(text="um yeah", start=0.0, end=5.2, words=words)])
    out = segment_transcript(t, SegmentationConfig(pause_threshold_s=0.6))
    assert len(out.segments) == 2


def test_segment_respects_max_duration():
    words = _words([(f"w{i}", i * 1.0, i * 1.0 + 0.5) for i in range(10)])
    t = Transcript(segments=[Segment(text="x", start=0.0, end=10.0, words=words)])
    out = segment_transcript(t, SegmentationConfig(max_duration_s=3.0, pause_threshold_s=999, max_words=999))
    for seg in out.segments:
        assert (seg.end - seg.start) <= 3.0 + 1e-6


def test_segment_respects_max_words():
    words = _words([(f"w{i}", i * 0.1, i * 0.1 + 0.05) for i in range(20)])
    t = Transcript(segments=[Segment(text="x", start=0.0, end=2.0, words=words)])
    out = segment_transcript(t, SegmentationConfig(max_words=5, pause_threshold_s=999, max_duration_s=999))
    for seg in out.segments:
        assert len(seg.words) <= 5


def test_segment_empty_transcript():
    t = Transcript(segments=[])
    out = segment_transcript(t)
    assert out.segments == []


def test_segment_single_word():
    words = _words([("Hi.", 0.0, 0.3)])
    t = Transcript(segments=[Segment(text="Hi.", start=0.0, end=0.3, words=words)])
    out = segment_transcript(t)
    assert len(out.segments) == 1
    assert out.segments[0].words[0].start == 0.0


def test_segment_preserves_timestamps():
    words = _words([("Hi.", 1.5, 1.9)])
    t = Transcript(segments=[Segment(text="Hi.", start=1.5, end=1.9, words=words)])
    out = segment_transcript(t)
    assert out.segments[0].start == 1.5
    assert out.segments[0].end == 1.9
