"""Small helpers for the in-GUI draft review (Phase 1 human-in-the-loop):
validate cues against narration, snap drifted cues back to verbatim, and redraw
one slide's visual on request."""
import re

from deck.visual.compose import visual_compose
from deck.visual.safety import sanitize_scenes

_WORD = re.compile(r"\w+")


def invalid_cues(scene):
    """[(step_index, cue)] for cues that are NOT verbatim substrings of the
    scene's narration. The recorder aligns reveals on these, so a non-matching
    cue would drop or mis-time a reveal — the render must not proceed with one."""
    narr = scene.get("narration", "")
    return [(j, step.get("cue", ""))
            for j, step in enumerate(scene.get("steps", []))
            if step.get("cue", "") and step["cue"] not in narr]


def snap_cue(cue, narration):
    """Return a verbatim substring of `narration` matching `cue` as closely as
    possible, else "". The composer picks cues against narration it sometimes
    drifts from (script mode force-restores the original paragraph after), so a
    generated cue can fail the verbatim rule by mere casing/punctuation. Recover
    the real substring: exact wins; else align the cue's words to a consecutive
    run of narration words (case/punct-insensitive, needs at least half the cue)
    and return the exact spanned text. The result is always "" or a true
    substring, so a snapped cue can never mis-time the reveal; "" lets the
    recorder fall back to even spacing rather than blocking the render."""
    cue = (cue or "").strip()
    if not cue or cue in narration:
        return cue if cue in narration else ""
    ntok = [(m.group(0).lower(), m.start(), m.end())
            for m in _WORD.finditer(narration)]
    ctok = [m.group(0).lower() for m in _WORD.finditer(cue)]
    if not ctok or not ntok:
        return ""
    nlow = [t[0] for t in ntok]
    floor = max(1, len(ctok) // 2)            # need ~half the cue, like the recorder
    for size in range(len(ctok), floor - 1, -1):
        for cs in range(len(ctok) - size + 1):
            frag = ctok[cs:cs + size]
            for ns in range(len(nlow) - size + 1):
                if nlow[ns:ns + size] == frag:
                    return narration[ntok[ns][1]:ntok[ns + size - 1][2]]
    return ""


def repair_cues(scenes):
    """Snap every step's cue to a verbatim substring of its slide's narration
    (mutates in place). Returns the count of cues that had to be changed/dropped."""
    changed = 0
    for sc in scenes:
        narr = sc.get("narration", "")
        for step in sc.get("steps", []):
            old = step.get("cue", "")
            new = snap_cue(old, narr)
            if new != old:
                step["cue"] = new
                changed += 1
    return changed


def recompose_scene(title, narration, project_id, location="global",
                    model="gemini-3.6-flash"):
    """Redraw ONE slide's visual for the (possibly edited) narration, keeping the
    narration fixed (same lock rule as script mode). Returns a scene dict."""
    scenes = visual_compose(title, [{"narration": narration}],
                            project_id=project_id, location=location,
                            model=model)
    scenes, warnings = sanitize_scenes(scenes)
    if warnings:
        print(f"[safety] neutralized {len(warnings)} unsafe snippet(s):")
        for w in warnings:
            print("  -", w)
    sc = scenes[0] if scenes else {"base": "", "steps": []}
    out = {"narration": narration, "base": sc.get("base", ""),
           "steps": sc.get("steps", [])}
    repair_cues([out])                                 # snap cues to the narration
    return out
