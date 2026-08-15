"""Draft rewording: prompt shape and the guards around a bad model response."""
import pytest

from deck.gen.reword import _build_user, reword


def test_build_user_puts_the_steer_before_the_draft():
    user = _build_user("My rough draft.", "make it shorter")
    assert "make it shorter" in user
    assert "My rough draft." in user
    assert user.index("make it shorter") < user.index("My rough draft.")


def test_build_user_without_a_steer_is_just_the_draft():
    user = _build_user("My rough draft.", "   ")
    assert "My rough draft." in user
    assert "How the creator wants it" not in user


def test_empty_draft_is_rejected_before_any_cloud_call():
    with pytest.raises(ValueError, match="empty draft"):
        reword("   \n\n  ", "tighten it")


def test_empty_model_response_raises_rather_than_wiping_the_draft(monkeypatch):
    # The GUI keeps the user's text on failure, so returning "" must be an error
    # and never a "successful" rewrite to nothing.
    monkeypatch.setattr("deck.gen.reword._call", lambda *a, **k: "")
    monkeypatch.setattr("google.genai.Client", lambda **k: object())
    with pytest.raises(ValueError, match="returned nothing"):
        reword("A real draft.", "tighten it", project_id="p")


def test_reword_returns_the_models_text(monkeypatch):
    monkeypatch.setattr("deck.gen.reword._call",
                        lambda *a, **k: "Reworded first.\n\nReworded second.")
    monkeypatch.setattr("google.genai.Client", lambda **k: object())
    out = reword("draft one\n\ndraft two", "punchier", project_id="p")
    assert out == "Reworded first.\n\nReworded second."
