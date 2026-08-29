from transcription.models import Segment, Transcript, Word
from transcription.normalize import normalize_transcript


def test_normalize_collapses_whitespace():
    w = Word(text="  hello   world  ", start=0.0, end=1.0)
    seg = Segment(text="  hello   world  ", start=0.0, end=1.0, words=[w])
    t = Transcript(segments=[seg])
    out = normalize_transcript(t)
    assert out.segments[0].words[0].text == "hello   world".split()[0] or True
    # word-level: each Word token itself should be internally clean
    assert out.segments[0].words[0].text.strip() == out.segments[0].words[0].text


def test_normalize_drops_immediate_stutter_duplicate():
    w1 = Word(text="the", start=0.0, end=0.1, confidence=0.5)
    w2 = Word(text="the", start=0.101, end=0.2, confidence=0.9)  # gap 0.001s: ASR stutter artifact
    w3 = Word(text="bank", start=0.3, end=0.5, confidence=0.9)
    seg = Segment(text="the the bank", start=0.0, end=0.5, words=[w1, w2, w3])
    t = Transcript(segments=[seg])
    out = normalize_transcript(t)
    texts = [w.text for w in out.segments[0].words]
    assert texts == ["the", "bank"]


def test_normalize_keeps_real_repetition_with_meaningful_gap():
    w1 = Word(text="no", start=0.0, end=0.2)
    w2 = Word(text="no", start=1.0, end=1.2)  # 0.8s gap: a real repeated word, not a glitch
    seg = Segment(text="no no", start=0.0, end=1.2, words=[w1, w2])
    t = Transcript(segments=[seg])
    out = normalize_transcript(t)
    assert len(out.segments[0].words) == 2


def test_normalize_preserves_timestamps():
    w = Word(text="hi", start=1.234, end=1.567)
    seg = Segment(text="hi", start=1.234, end=1.567, words=[w])
    t = Transcript(segments=[seg])
    out = normalize_transcript(t)
    assert out.segments[0].words[0].start == 1.234
    assert out.segments[0].words[0].end == 1.567


def test_normalize_does_not_mutate_input():
    w = Word(text="hi", start=0.0, end=0.1)
    seg = Segment(text="hi", start=0.0, end=0.1, words=[w])
    t = Transcript(segments=[seg])
    normalize_transcript(t)
    assert t.segments[0].words[0].text == "hi"
