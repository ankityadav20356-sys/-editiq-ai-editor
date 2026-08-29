import pytest

from transcription.models import Word, Segment, Transcript


def test_word_basic():
    w = Word(text="hello", start=0.0, end=0.5, confidence=0.9)
    assert w.to_dict() == {"text": "hello", "start": 0.0, "end": 0.5, "confidence": 0.9}


def test_word_rejects_end_before_start():
    with pytest.raises(ValueError):
        Word(text="x", start=1.0, end=0.5)


def test_segment_rejects_end_before_start():
    with pytest.raises(ValueError):
        Segment(text="x", start=1.0, end=0.5)


def test_transcript_words_flattens_segments():
    w1 = Word(text="hi", start=0.0, end=0.3)
    w2 = Word(text="there", start=0.3, end=0.6)
    seg = Segment(text="hi there", start=0.0, end=0.6, words=[w1, w2])
    t = Transcript(segments=[seg], language="en", duration=1.0)
    assert t.words == [w1, w2]
    assert t.text == "hi there"


def test_transcript_to_dict_roundtrip_shape():
    w1 = Word(text="hi", start=0.0, end=0.3)
    seg = Segment(text="hi", start=0.0, end=0.3, words=[w1])
    t = Transcript(segments=[seg], language="en", duration=0.3)
    d = t.to_dict()
    assert d["language"] == "en"
    assert d["duration"] == 0.3
    assert d["segments"][0]["words"][0]["text"] == "hi"
