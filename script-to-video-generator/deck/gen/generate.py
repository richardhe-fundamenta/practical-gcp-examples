"""script -> LLM-authored concept visuals -> recorded mp4.

You supply the script; it is narrated VERBATIM. One scene per blank-line
paragraph, each drawn as an abstract hand-sketched Rough.js visual reflecting
the concept being spoken (little to no text). Nothing rewrites your words.

The composer only draws + picks cues (it never rewords), and this module then
FORCE-restores the exact paragraph text as the narration — a
hard guarantee, even if the model drifts. LLM-authored draw code still goes
through the safety + integrity gates.

CLI: `python -m deck.gen.generate "My title" --script talk.txt`
"""
import argparse
import os
import re

from deck.render.record import record_deck


def compile_deck(title, scenes):
    """scenes -> (html, timeline) — the single place both the app (preview) and
    the record-only job turn an editable scenes list into what record_deck consumes."""
    from deck.visual.scene import build_html
    return build_html(title, scenes)


def _split_paragraphs(text):
    """Blank-line-separated paragraphs, trimmed. Internal newlines collapse to
    spaces so each paragraph is one spoken run."""
    parts = re.split(r"\n\s*\n", text.strip())
    return [re.sub(r"\s+", " ", p).strip() for p in parts if p.strip()]


def _mock_scene(paragraph, i):
    """Offline placeholder scene (no cloud): a title + one drawn shape. Used only
    by tests / --mock; the real path draws bespoke concept visuals via the LLM."""
    return {
        "narration": paragraph,
        "base": "s.text(s.SAFE.cx,300,'Script mode',"
                "{size:60,anchor:'middle',title:true,color:s.color.yellow});",
        "steps": [{"cue": " ".join(paragraph.split()[:3]),
                   "draw": f"s.add(s.rc.circle(s.SAFE.cx,900,{200 + (i % 3) * 60},"
                           "{stroke:s.color.blue,strokeWidth:4}));"}],
    }


def generate_scenes(title, script, mock=False, project_id="mock-project",
                    location="global", model="gemini-3.6-flash", progress=None):
    """Verbatim script -> (title, editable scenes). No recording.
    `progress(msg)`, if given, is called at each phase boundary for a live status."""
    say = progress or (lambda *_: None)
    paragraphs = _split_paragraphs(script)
    if not paragraphs:
        raise ValueError("empty script (no paragraphs)")

    if mock:
        scenes = [_mock_scene(p, i) for i, p in enumerate(paragraphs)]
    else:
        from deck.visual.compose import visual_compose
        from deck.visual.integrity import dedupe_and_repair
        from deck.visual.safety import sanitize_scenes
        say("Composing the visuals — the slowest step…")
        slides = [{"narration": p} for p in paragraphs]
        scenes = visual_compose(title, slides, project_id=project_id,
                                location=location, model=model,
                                progress=progress)
        scenes, warnings = sanitize_scenes(scenes)  # LLM JS -> static safety gate
        for w in warnings:
            print("[safety] neutralized:", w)
        scenes, issues = dedupe_and_repair(scenes)  # JS integrity gate
        for w in issues:
            print("[integrity] fixed:", w)

    # HARD LOCK: the spoken narration is ALWAYS the verbatim paragraph, in order,
    # regardless of what the model echoed. One scene per paragraph is guaranteed
    # (pad a bare scene if the model returned too few; ignore any extras).
    out = []
    for i, para in enumerate(paragraphs):
        sc = scenes[i] if i < len(scenes) else {"base": "", "steps": []}
        sc["narration"] = para
        out.append(sc)

    # Snap any drifted cue back to a verbatim substring of its narration so
    # reveals stay word-aligned and the review gate isn't tripped by casing drift.
    from deck.gen.review import repair_cues
    fixed = repair_cues(out)
    if fixed:
        say(f"Aligned {fixed} cue(s) to the narration")
        print(f"[cues] snapped {fixed} cue(s) to verbatim narration substrings")
    return title, out


def run(title, script, out="output/deck.mp4", mock=False, html_only=False,
        project_id="mock-project", location="global", model="gemini-3.6-flash",
        voice="Leda", tts_provider="gemini", eleven_voice_id=None) -> str:
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    title, scenes = generate_scenes(title, script, mock=mock, project_id=project_id,
                                    location=location, model=model)
    html, timeline = compile_deck(title, scenes)
    html_path = os.path.splitext(out)[0] + ".html"
    with open(html_path, "w") as f:
        f.write(html)
    if html_only:  # stop before TTS/record — with --mock this is a no-cloud check
        return html_path
    return record_deck(html_path, timeline, out, project_id=project_id,
                       location=location, voice=voice,
                       tts_provider=tts_provider, eleven_voice_id=eleven_voice_id)


def main():
    p = argparse.ArgumentParser(
        description="Narrate a script verbatim over hand-sketched concept visuals.")
    p.add_argument("title", help="Video title (shown on screen, names the file)")
    p.add_argument("--script", required=True,
                   help="Path to the script file, narrated VERBATIM "
                        "(one blank-line-separated paragraph per scene)")
    p.add_argument("--out", default="output/deck.mp4")
    p.add_argument("--mock", action="store_true", help="Offline mock scenes; skips the LLM compose")
    p.add_argument("--html-only", action="store_true",
                   help="Write the HTML and stop, skipping TTS/recording (with "
                        "--mock this needs no cloud creds and no ffmpeg)")
    p.add_argument("--project-id", default="mock-project")
    p.add_argument("--location", default="global")
    p.add_argument("--model", default="gemini-3.6-flash")
    p.add_argument("--voice", default="Leda", help="Gemini TTS voice (Leda, Kore, Puck, Charon, Aoede, Fenrir)")
    p.add_argument("--tts", dest="tts_provider", default="gemini",
                   choices=("gemini", "elevenlabs"),
                   help="TTS backend: gemini (default) or elevenlabs (cloned voice)")
    p.add_argument("--eleven-voice-id", default=None,
                   help="ElevenLabs voice id (required with --tts elevenlabs; "
                        "key from the ELEVENLABS_API_KEY env var)")
    a = p.parse_args()
    path = run(a.title, open(a.script).read(), out=a.out, mock=a.mock,
               html_only=a.html_only,
               project_id=a.project_id, location=a.location, model=a.model,
               voice=a.voice, tts_provider=a.tts_provider,
               eleven_voice_id=a.eleven_voice_id)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
