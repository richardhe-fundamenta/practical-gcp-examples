from deck.gen.review import (invalid_cues, recompose_scene,
                             repair_cues, snap_cue)
from deck.visual.scene import build_preview_html


def test_snap_cue_recovers_verbatim_from_drift():
    narr = "The old way matches letters, the new way matches meaning."
    assert snap_cue("matches letters", narr) == "matches letters"   # exact
    assert snap_cue("Matches Letters", narr) == "matches letters"   # casing
    assert snap_cue("matches meaning!", narr) == "matches meaning"  # punctuation
    # partial overlap snaps to the verbatim run that's actually present
    assert snap_cue("new way matches everything", narr) == "new way matches"
    assert snap_cue("totally unrelated phrase", narr) == ""         # no match -> drop
    # the result, when non-empty, is always a real substring
    for probe in ["the new way", "MEANING.", "old", "letters the new"]:
        s = snap_cue(probe, narr)
        assert s == "" or s in narr


def test_repair_cues_fixes_drifted_cues_in_place():
    scenes = [{"narration": "Cache writes are hard to invalidate.",
               "steps": [{"cue": "Cache Writes", "draw": "a"},      # casing
                         {"cue": "ship on friday", "draw": "b"}]}]  # absent -> ""
    changed = repair_cues(scenes)
    assert changed == 2
    assert scenes[0]["steps"][0]["cue"] == "Cache writes"
    assert scenes[0]["steps"][1]["cue"] == ""
    assert invalid_cues(scenes[0]) == []            # nothing left to block on


def test_invalid_cues_flags_non_substring_cues():
    scene = {"narration": "Cache writes are hard.",
             "steps": [{"cue": "Cache writes", "draw": ""},
                       {"cue": "expire later", "draw": ""}]}
    assert invalid_cues(scene) == [(1, "expire later")]


def test_recompose_scene_keeps_narration_and_swaps_visual(monkeypatch):
    import deck.gen.review as review
    monkeypatch.setattr(review, "visual_compose",
                        lambda title, slides, **k: [
                            {"narration": "REWRITTEN", "base": "NEWBASE",
                             "steps": [{"cue": "Cache writes", "draw": "NEWDRAW"}]}])
    out = recompose_scene("t", "Cache writes are hard.", project_id="p")
    assert out["narration"] == "Cache writes are hard."  # narration is NOT the rewrite
    assert out["base"] == "NEWBASE"
    assert out["steps"][0]["draw"] == "NEWDRAW"


def test_build_preview_html_autoreveals_final_frame():
    scene = {"narration": "Hi.", "base": "", "steps": []}
    html = build_preview_html("T", scene)
    assert "window.showFinal(0)" in html
    assert "<!DOCTYPE html>" in html
