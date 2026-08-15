"""Visual renderer: offline HTML assembly + the static safety gate."""
from deck.visual.safety import check, sanitize_scenes
from deck.visual.scene import build_html


def test_build_html_assembles_offline():
    # build_html is pure assembly (no cloud): scenes -> (html, timeline)
    scenes = [{"narration": "hello world", "base": "s.text(0,0,'hi',{});",
               "steps": [{"cue": "hello", "draw": "s.add(s.rc.circle(1,1,1,{}));"}]}]
    html, timeline = build_html("My Deck", scenes)
    assert "<html" in html.lower()
    assert len(timeline) == 1
    assert timeline[0]["narration"] == "hello world"
    assert timeline[0]["cues"] == ["hello"]


def test_build_html_has_no_external_fetches():
    # Zero-egress rendering depends on every asset being inlined — a stray CDN or
    # Google Fonts reference would draw blank scenes inside the no-egress sandbox.
    # (The SVG XML namespace http://www.w3.org/... is a name, not a fetch, so we
    # check for actual fetch vectors — src=/href=/@import/known hosts — not "http".)
    html, _ = build_html("t", [{"narration": "n", "base": "", "steps": []}])
    for host in ("unpkg.com", "cdnjs", "fonts.googleapis.com", "fonts.gstatic.com"):
        assert host not in html, host
    assert 'src="http' not in html and 'href="http' not in html
    assert "@import" not in html
    # vendored assets are actually present
    assert "roughjs 4.6.6 (vendored)" in html
    assert "animejs 3.2.2 (vendored)" in html
    assert html.count("data:font/woff2;base64,") == 2


def test_safety_allows_drawing_blocks_escape():
    assert check("s.add(s.rc.rectangle(90,360,360,150,{stroke:s.color.white}));") == []
    assert check("for(let k=0;k<5;k++){s.add(s.rc.circle(k*10,10,8,{}));}") == []
    # words that only appear inside a string literal are not violations
    assert check("s.text(0,0,'send data to the window',{});") == []
    # real escapes are caught
    for danger in ["fetch('/x')", "window.location='y'", "new Function('return 1')",
                   "eval('1')", "document.cookie", "import('x')"]:
        assert check(danger), danger


def test_sanitize_keeps_groups_drops_unsafe_code():
    scenes = [{"narration": "n",
               "base": "s.text(0,0,'ok',{});",
               "steps": [{"cue": "a", "draw": "fetch('http://evil')"},
                         {"cue": "b", "draw": "s.add(s.rc.circle(1,1,1,{}));"}]}]
    clean, warns = sanitize_scenes(scenes)
    assert clean[0]["base"] == "s.text(0,0,'ok',{});"    # safe base kept
    assert clean[0]["steps"][0]["draw"] == ""            # unsafe step blanked
    assert clean[0]["steps"][1]["draw"]                  # safe step kept
    assert len(clean[0]["steps"]) == 2                   # groups/cues preserved -> sync intact
    assert warns
