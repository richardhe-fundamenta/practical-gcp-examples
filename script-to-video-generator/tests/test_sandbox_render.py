"""Offline Chromium render/record smoke test.

Proves the vendored (no-CDN) page loads and playGroups drives to a non-empty
webm in headless Chromium with NO network — the local stand-in for the
zero-egress Cloud Run sandbox render. Skips if Playwright/Chromium isn't
installed in the dev env (it is in the render image)."""
import pytest

from deck.visual.scene import build_html

pytest.importorskip("playwright.sync_api")


def test_drive_renders_offline_to_webm(tmp_path):
    from deck.render.sandbox_render import drive

    scenes = [{
        "narration": "hello world here",
        "base": "s.text(100,300,'Title',{title:true,size:80});",
        "steps": [
            {"cue": "hello", "draw": "s.add(s.rc.circle(400,700,140,{stroke:s.color.white}));"},
            {"cue": "world", "draw": "s.text(100,1000,'point two',{});"},
        ],
    }]
    html, timeline = build_html("Smoke", scenes)
    html_path = tmp_path / "page.html"
    html_path.write_text(html)
    schedule = {
        "W": 1080, "H": 1920, "init_ms": 50, "tail_ms": 50, "dwell_ms": 50,
        "slides": [{"cues": timeline[0]["cues"], "dur": 0.6,
                    "words": [{"w": "hello", "start": 0.1},
                              {"w": "world", "start": 0.35}]}],
    }
    try:
        webm = drive(str(html_path), schedule, str(tmp_path))
    except Exception as e:  # no browser binary in this env -> not a code failure
        if "Executable doesn't exist" in str(e) or "playwright install" in str(e):
            pytest.skip(f"chromium not installed: {e}")
        raise
    import os
    assert os.path.getsize(webm) > 0
