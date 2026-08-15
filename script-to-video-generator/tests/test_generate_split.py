"""The generation half: paragraph split, the verbatim lock, and scenes -> timeline."""
from deck.gen.generate import _split_paragraphs, compile_deck, generate_scenes


def test_compile_deck_roundtrips_scenes_to_timeline():
    scenes = [
        {"narration": "First line here.", "base": "",
         "steps": [{"cue": "First line", "draw": ""}]},
        {"narration": "Second line here.", "base": "",
         "steps": [{"cue": "Second", "draw": ""}, {"cue": "line", "draw": ""}]},
    ]
    html, timeline = compile_deck("My Deck", scenes)
    assert "<!DOCTYPE html>" in html
    assert [t["narration"] for t in timeline] == \
        ["First line here.", "Second line here."]
    assert [t["cues"] for t in timeline] == [["First line"], ["Second", "line"]]


def test_split_paragraphs_drops_blanks_and_collapses_newlines():
    text = "  Para one.\nstill one.\n\n\n  Para two.  \n\n"
    assert _split_paragraphs(text) == ["Para one. still one.", "Para two."]


def test_generate_scenes_is_offline_and_verbatim():
    title, scenes = generate_scenes("My Talk", "One.\n\nTwo.", mock=True)
    assert title == "My Talk"
    assert [s["narration"] for s in scenes] == ["One.", "Two."]
    assert all("steps" in s for s in scenes)


def test_lock_restores_verbatim_even_if_model_reworded(monkeypatch):
    # Simulate the composer drifting (reworded narration, too few scenes); the
    # hard lock must still speak the exact paragraphs, in order.
    monkeypatch.setattr("deck.visual.compose.visual_compose", lambda *a, **k: [
        {"narration": "A snappy rewrite of idea one", "base": "", "steps": []},
        {"narration": "another rewrite", "base": "", "steps": []},
    ])
    _title, scenes = generate_scenes(
        "t", "First idea here.\n\nSecond idea follows.\n\nThird wraps it up.",
        project_id="p")
    assert [s["narration"] for s in scenes] == [
        "First idea here.", "Second idea follows.", "Third wraps it up."]


def test_empty_script_is_rejected():
    try:
        generate_scenes("t", "   \n\n  ", mock=True)
    except ValueError as e:
        assert "empty script" in str(e)
    else:
        raise AssertionError("empty script should raise")
