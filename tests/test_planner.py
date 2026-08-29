from planner.generator import generate_edit_plan, generate_operations
from planner.models import PlannerConfig
from transcription.mock_backend import MockTranscriptionBackend
from transcription.normalize import normalize_transcript
from transcription.segment import segment_transcript


def _sample_transcript():
    backend = MockTranscriptionBackend(script="Your money should never sit idle. Put it to work today.")
    t = backend.transcribe("x.mp4")
    return segment_transcript(normalize_transcript(t))


def test_generate_operations_includes_captions_for_each_segment():
    t = _sample_transcript()
    ops = generate_operations(t)
    captions = [op for op in ops if op["type"] == "caption"]
    assert len(captions) == len(t.segments)


def test_generate_operations_emphasis_hits_keyword():
    t = _sample_transcript()
    ops = generate_operations(t, PlannerConfig(emphasis_min_word_len=999, emphasis_keywords=("never",)))
    emphasis = [op for op in ops if op["type"] == "emphasis"]
    assert any(op["word"].strip(".,!?").lower() == "never" for op in emphasis)


def test_generate_operations_zoom_follows_each_emphasis():
    t = _sample_transcript()
    ops = generate_operations(t)
    emphasis = [op for op in ops if op["type"] == "emphasis"]
    zooms = [op for op in ops if op["type"] == "zoom"]
    assert len(zooms) == len(emphasis)


def test_generate_operations_broll_is_suggestion_only():
    t = _sample_transcript()
    ops = generate_operations(t)
    broll = [op for op in ops if op["type"] == "broll"]
    for op in broll:
        assert "query" in op
        assert isinstance(op["query"], str)
        # Phase 1 explicitly never includes a URL/asset path -- suggestion only.
        assert "url" not in op and "asset" not in op


def test_generate_operations_sorted_by_start_time():
    t = _sample_transcript()
    ops = generate_operations(t)
    starts = [op.get("start", op.get("at", 0.0)) for op in ops]
    assert starts == sorted(starts)


def test_generate_edit_plan_shape():
    t = _sample_transcript()
    project = {"width": 1080, "height": 1920, "fps": 30}
    plan = generate_edit_plan(t, "video.mp4", project)
    assert plan["modules"] == []
    assert plan["source"]["media"] == "video.mp4"
    assert "operations" in plan
    assert plan["project"] == project


def test_silence_cut_detected_for_long_gap():
    from transcription.models import Segment, Transcript, Word
    seg1 = Segment(text="Hello.", start=0.0, end=1.0, words=[Word(text="Hello.", start=0.0, end=1.0)])
    seg2 = Segment(text="World.", start=3.0, end=4.0, words=[Word(text="World.", start=3.0, end=4.0)])
    t = Transcript(segments=[seg1, seg2], duration=4.0)
    ops = generate_operations(t, PlannerConfig(min_silence_s=0.8))
    cuts = [op for op in ops if op["type"] == "cut"]
    assert len(cuts) == 1
    assert cuts[0]["start"] > seg1.end
    assert cuts[0]["end"] < seg2.start
