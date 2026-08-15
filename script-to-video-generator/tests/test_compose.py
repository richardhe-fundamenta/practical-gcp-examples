"""visual_compose count guard: never return fewer scenes than input slides
(a dropped slide became a blank board with narration over it)."""
import deck.visual.compose as compose


def _slides(n):
    return [{"narration": f"Paragraph number {i} says something real."}
            for i in range(n)]


def test_ensure_count_rerequests_dropped_tail(monkeypatch):
    # model truncated the array to 1 of 3 scenes; the tail is re-requested
    slides = _slides(3)
    data = [{"narration": "s0", "base": "b0", "steps": []}]
    monkeypatch.setattr(compose, "_generate",
                        lambda c, t, m, user: [
                            {"narration": "s1", "base": "b1", "steps": []},
                            {"narration": "s2", "base": "b2", "steps": []}])
    out = compose._ensure_count(None, None, "m", "t", slides, data,
                                lambda *_: None)
    assert len(out) == 3
    assert all(s["base"] for s in out)           # no blank board anywhere


def test_ensure_count_falls_back_to_title_card_when_rerequest_fails(monkeypatch):
    slides = _slides(2)
    data = [{"narration": "s0", "base": "b0", "steps": []}]
    def boom(*a, **k):
        raise RuntimeError("truncated again")
    monkeypatch.setattr(compose, "_generate", boom)
    out = compose._ensure_count(None, None, "m", "t", slides, data,
                                lambda *_: None)
    assert len(out) == 2
    assert out[1]["base"]                         # fallback drew a title, not blank
    assert out[1]["steps"] == []


def test_ensure_count_leaves_full_output_untouched():
    slides = _slides(2)
    data = [{"narration": "a", "base": "x", "steps": []},
            {"narration": "b", "base": "y", "steps": []}]
    out = compose._ensure_count(None, None, "m", "t", slides, data,
                                lambda *_: None)
    assert [s["base"] for s in out] == ["x", "y"]
