import os

from streamlit.testing.v1 import AppTest

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.py")


def test_app_renders_with_sensible_defaults():
    # First run inits the (uncached) GCS client + credential lookup, which can
    # exceed AppTest's tight 3s default; give it headroom.
    at = AppTest.from_file(APP_PATH).run(timeout=30)
    assert at.text_input[0].label == "Title"          # title + script are required
    # look selectboxes up by label so adding new ones doesn't shift indices
    sel = {s.label: s.value for s in at.selectbox}
    # defaults: ElevenLabs cloned voice (Richard He). The Gemini "Voice" dropdown
    # only appears when the engine is switched back to Gemini.
    assert sel["Voice engine"] == "elevenlabs"
    assert sel["Voice"] == "Richard He"
    assert any(b.label == "🚀 Generate video" for b in at.button)
    # Listing videos fails without GCS creds, but it's caught — app still renders.
    assert not at.exception


def test_generate_enters_review_mode(monkeypatch):
    import deck.gen.generate
    monkeypatch.setattr(
        deck.gen.generate, "generate_scenes",
        lambda title, script, **k: (title, [
            {"narration": "First.", "base": "",
             "steps": [{"cue": "First", "draw": ""}]}]))
    at = AppTest.from_file(APP_PATH).run(timeout=30)
    at.text_input(key="topic").set_value("My talk")
    at.text_area(key="reference").set_value("First.")
    at.checkbox(key="review_first").set_value(True)
    at.run(timeout=30)
    at = _click(at, "🚀 Generate video")
    assert "draft" in at.session_state
    assert at.session_state.draft["title"] == "My talk"
    assert not at.exception


def test_generate_defaults_to_background_job(monkeypatch):
    # Default (review off): dispatch one generate+record job, no in-process
    # generation and no review draft.
    import deck.infra.job
    called = {}
    monkeypatch.setattr(deck.infra.job, "dispatch_deck_job",
                        lambda bucket, title, settings, *a, **k:
                        called.update(title=title, settings=settings) or "job.mp4")
    at = AppTest.from_file(APP_PATH).run(timeout=30)
    at.text_input(key="topic").set_value("My talk")
    at.text_area(key="reference").set_value("One paragraph.")
    at.run(timeout=30)
    at = _click(at, "🚀 Generate video")
    assert called["title"] == "My talk"
    assert called["settings"]["script"] == "One paragraph."
    assert "draft" not in at.session_state
    # confirmation shown (a toast wouldn't survive the rerun) and inputs cleared
    assert any("Submitted" in s.value for s in at.success)
    assert not at.text_input(key="topic").value
    assert not at.exception


def _enter_review(monkeypatch, scenes):
    import deck.gen.generate
    monkeypatch.setattr(deck.gen.generate, "generate_scenes",
                        lambda title, script, **k: (title, scenes))
    at = AppTest.from_file(APP_PATH).run(timeout=30)
    at.text_input(key="topic").set_value("My talk")
    at.text_area(key="reference").set_value("x")
    at.checkbox(key="review_first").set_value(True)
    at.run(timeout=30)
    return _click(at, "🚀 Generate video")


def _click(at, label):
    for b in at.button:
        if b.label == label:
            return b.click().run(timeout=30)
    raise AssertionError(f"no button {label!r}")


def test_regenerate_replaces_stale_cue(monkeypatch):
    # Stable widget keys would otherwise mask the redraw's new cue with the old
    # one (Streamlit ignores value= once a key exists) — a silent cue/draw
    # mismatch the recorder would then align wrong.
    at = _enter_review(monkeypatch, [
        {"narration": "First and second.", "base": "",
         "steps": [{"cue": "First", "draw": "a"}]}])
    import deck.gen.review
    monkeypatch.setattr(deck.gen.review, "recompose_scene",
                        lambda *a, **k: {"narration": "First and second.",
                                         "base": "b",
                                         "steps": [{"cue": "second", "draw": "c"}]})
    at = _click(at, "♻️ Regenerate this slide's visual")
    step = at.session_state.draft["scenes"][0]["steps"][0]
    assert step["cue"] == "second"      # new cue survived, not masked by "First"
    assert step["draw"] == "c"
    assert not at.exception


def test_reword_replaces_the_script_and_keeps_the_original(monkeypatch):
    # The reword button must actually swap the textarea's contents (Streamlit
    # masks a new value= while the widget key exists), and must keep the original
    # so re-steering re-runs from the draft instead of compounding.
    import deck.gen.reword
    seen = {}
    monkeypatch.setattr(deck.gen.reword, "reword",
                        lambda draft, steer, **k:
                        seen.update(draft=draft, steer=steer) or "REWORDED TEXT")
    at = AppTest.from_file(APP_PATH).run(timeout=30)
    at.text_area(key="reference").set_value("my rough draft")
    at.text_area(key="steer").set_value("make it punchier")
    at.run(timeout=30)
    at = _click(at, "✨ Reword")

    assert seen == {"draft": "my rough draft", "steer": "make it punchier"}
    assert at.text_area(key="reference").value == "REWORDED TEXT"
    assert at.session_state.script_original == "my rough draft"
    assert not at.exception


def test_second_reword_re_steers_from_the_original_not_the_rewrite(monkeypatch):
    import deck.gen.reword
    seen = {}
    monkeypatch.setattr(deck.gen.reword, "reword",
                        lambda draft, steer, **k:
                        seen.update(draft=draft, steer=steer) or f"OUT<{steer}>")
    at = AppTest.from_file(APP_PATH).run(timeout=30)
    at.text_area(key="reference").set_value("my rough draft")
    at.text_area(key="steer").set_value("shorter")
    at.run(timeout=30)
    at = _click(at, "✨ Reword")
    at.text_area(key="steer").set_value("longer")
    at.run(timeout=30)
    at = _click(at, "✨ Reword")

    assert seen["draft"] == "my rough draft"      # NOT "OUT<shorter>"
    assert at.text_area(key="reference").value == "OUT<longer>"
    assert not at.exception


def test_reword_failure_keeps_the_users_text(monkeypatch):
    import deck.gen.reword

    def boom(*a, **k):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(deck.gen.reword, "reword", boom)
    at = AppTest.from_file(APP_PATH).run(timeout=30)
    at.text_area(key="reference").set_value("precious draft")
    at.run(timeout=30)
    at = _click(at, "✨ Reword")

    assert at.text_area(key="reference").value == "precious draft"
    assert any("Reword failed" in e.value for e in at.error)
    assert not at.exception
