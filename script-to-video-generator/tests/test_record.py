"""Trim + cue-alignment reveal timing (pure, no browser)."""
import pytest

from deck.render.record import _lead_in, _resolve_reveal_times, _words_from_alignment


def test_lead_in_is_raw_minus_content():
    # recorded 10s; content (holds incl. dwells) = 6.4, tail 0.6 -> 3.0s to cut
    assert _lead_in(10.0, 6.4, tail=0.6) == 3.0


def test_lead_in_never_negative():
    assert _lead_in(2.0, 3.0, tail=0.6) == 0.0


def _words(pairs):
    """[(text, start)] -> aligner word dicts."""
    return [{"w": w, "start": s, "end": s + 0.1} for w, s in pairs]


def test_group0_reveals_at_zero():
    words = _words([("the", 0.0), ("query", 0.5)])
    times = _resolve_reveal_times(["query"], 2, words, 3.0)
    assert times[0] == 0.0
    assert times[1] == 0.5


def test_cue_found_uses_word_start():
    words = _words([("a", 0.0), ("new", 1.0), ("row", 1.3), ("embeds", 2.0)])
    # two content groups: "new row" at 1.0, "embeds" at 2.0
    times = _resolve_reveal_times(["new row", "embeds"], 3, words, 3.0)
    assert times == [0.0, 1.0, 2.0]


def test_missing_cue_interpolates_between_neighbors():
    words = _words([("start", 0.0), ("end", 4.0)])
    # 3 content groups; only first and last cue found -> middle interpolated
    times = _resolve_reveal_times(["start", "nope", "end"], 4, words, 5.0)
    assert times[1] == 0.0
    assert times[3] == 4.0
    assert 0.0 < times[2] < 4.0        # interpolated between the two anchors


def test_repeated_phrase_stays_monotonic():
    words = _words([("sync", 0.5), ("then", 1.0), ("sync", 2.0)])
    # both cues are "sync"; the second must match the LATER occurrence
    times = _resolve_reveal_times(["sync", "sync"], 3, words, 3.0)
    assert times == [0.0, 0.5, 2.0]


def test_count_mismatch_more_groups_than_cues():
    words = _words([("one", 0.0), ("two", 1.0), ("three", 2.0)])
    # 4 content groups, 1 cue -> rest interpolate up to clip_dur
    times = _resolve_reveal_times(["two"], 5, words, 4.0)
    assert times[0] == 0.0
    assert times[1] == 1.0             # the one cue
    assert times[-1] <= 4.0
    assert times == sorted(times)      # non-decreasing


def test_empty_cues_even_spacing():
    words = _words([("a", 0.0), ("b", 2.0)])
    times = _resolve_reveal_times([], 4, words, 3.0)
    assert times[0] == 0.0
    assert times == sorted(times)
    assert all(t <= 3.0 for t in times)


def test_number_cues_vs_spoken_transcript_anchor_correctly():
    # Regression: written cues use digits/abbrevs ("1 MB", "1,000") but the ASR
    # transcribes speech ("one megabyte", "1 000"). The matcher must anchor on the
    # tokens that DO line up, not latch the lone "1" of "1,000" for the "1 MB" cue
    # (which used to drag every reveal to the end, then fire them in a burst).
    toks = ("a max payload caps at one megabyte per synchronous object both gcs "
            "import allows 200 megabyte json files a grpc batch limit caps at "
            "1 000 objects per request and max dimensions supports up to "
            "4 096 dimensions").split()
    words = _words([(t, float(i)) for i, t in enumerate(toks)])
    cues = ["1 MB per synchronous", "200 MB JSON files",
            "1,000 objects per request", "4,096 dimensions"]
    times = _resolve_reveal_times(cues, 5, words, float(len(toks)))
    # anchors land at each phrase's real position (5, 14, 24, 35), strictly rising
    assert times[1:] == sorted(times[1:])
    assert times[1] == 5.0 and times[2] == 14.0
    assert times[3] == 24.0 and times[4] == 35.0


def test_weak_partial_match_is_rejected():
    # a cue sharing only one token with a 4-token phrase must NOT anchor there
    words = _words([("alpha", 0.0), ("beta", 1.0), ("gamma", 2.0)])
    assert _resolve_reveal_times(["zzz beta qqq www"], 2, words, 3.0)  # doesn't crash
    # "beta" alone (1 of 4 tokens) is below the ~half threshold -> interpolated
    t = _resolve_reveal_times(["zzz qqq www beta"], 2, words, 3.0)
    assert t[1] != 1.0        # not anchored to beta; falls back to interpolation


def test_no_words_degrades_to_spacing():
    # aligner returned nothing (e.g. unavailable) -> still monotonic in [0, dur]
    times = _resolve_reveal_times(["x", "y"], 3, [], 3.0)
    assert times[0] == 0.0
    assert times == sorted(times)
    assert all(t <= 3.0 for t in times)


def test_record_deck_feeds_elevenlabs_timestamps_to_sandbox(monkeypatch, tmp_path):
    # The whole point of the sandbox refactor's schedule: cue-aligned voice sync
    # must survive it. ElevenLabs returns native word timestamps upstream; assert
    # they reach the (sandboxed) browser step verbatim, per slide, with durations.
    import deck.render.record as R
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    words = [{"w": "hello", "start": 0.1}, {"w": "world", "start": 0.4}]

    def fake_tts(text, path, vid, key):
        R._write_wav(b"\x00\x00" * 2400, path, 24000)   # 0.1s real wav so ffprobe works
        return words

    monkeypatch.setattr(R, "_tts_elevenlabs", fake_tts)
    captured = {}

    def fake_browser(html_path, schedule, work):
        captured["schedule"] = schedule
        raise RuntimeError("stop-after-schedule")       # skip downstream ffmpeg mux

    monkeypatch.setattr(R, "_run_browser", fake_browser)
    html = tmp_path / "p.html"
    html.write_text("<html></html>")
    timeline = [{"narration": "hello world", "cues": ["hello", "world"]}]
    with pytest.raises(RuntimeError, match="stop-after-schedule"):
        R.record_deck(str(html), timeline, str(tmp_path / "out.mp4"),
                      work_dir=str(tmp_path), tts_provider="elevenlabs",
                      eleven_voice_id="v1")
    slide = captured["schedule"]["slides"][0]
    assert slide["words"] == words                       # native EL timings preserved
    assert slide["cues"] == ["hello", "world"]
    assert slide["dur"] > 0


def _align(text, starts):
    """Build an ElevenLabs alignment payload from characters + per-char starts."""
    return {"characters": list(text),
            "character_start_times_seconds": starts,
            "character_end_times_seconds": [s + 0.05 for s in starts]}


def test_words_from_alignment_splits_on_whitespace():
    # "Hi you" -> two words, each starting at its first non-space char
    al = _align("Hi you", [0.0, 0.1, 0.2, 0.3, 0.4, 0.5])
    assert _words_from_alignment(al) == [
        {"w": "Hi", "start": 0.0}, {"w": "you", "start": 0.3}]


def test_words_from_alignment_feeds_cue_resolution():
    # native timestamps must plug straight into the reveal resolver
    #                              a   ' '  n    e    w   ' '  r    o    w
    words = _words_from_alignment(_align("a new row",
                                  [0.0, 0.2, 0.6, 0.7, 0.8, 1.0, 1.2, 1.3, 1.4]))
    t = _resolve_reveal_times(["new row"], 2, words, 3.0)
    assert t[1] == 0.6        # anchored to the "new" word start
