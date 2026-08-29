from transcription.mock_backend import MockTranscriptionBackend


def test_mock_backend_deterministic():
    backend = MockTranscriptionBackend()
    t1 = backend.transcribe("nonexistent.mp4")
    t2 = backend.transcribe("nonexistent.mp4")
    assert t1.to_dict() == t2.to_dict()


def test_mock_backend_default_script_two_sentences():
    backend = MockTranscriptionBackend()
    t = backend.transcribe("x.mp4")
    assert len(t.segments) == 2
    assert t.segments[0].text.endswith(".")
    assert t.segments[1].text.endswith(".")


def test_mock_backend_words_have_increasing_timestamps():
    backend = MockTranscriptionBackend()
    t = backend.transcribe("x.mp4")
    words = t.words
    for prev, nxt in zip(words, words[1:]):
        assert nxt.start >= prev.start
        assert prev.end >= prev.start


def test_mock_backend_custom_script():
    backend = MockTranscriptionBackend(script="One word.")
    t = backend.transcribe("x.mp4")
    assert t.text == "One word."


def test_mock_backend_duration_override():
    backend = MockTranscriptionBackend(duration=42.0)
    t = backend.transcribe("x.mp4")
    assert t.duration == 42.0
