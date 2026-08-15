"""Deterministic quality rubric for composed scenes — run BEFORE recording.

Recording (TTS + forced-alignment + real-time Playwright capture) is the slow,
expensive stage. This module scores the composed JSON instantly (no cloud call)
so `visual_compose` can catch quality problems and have the model FIX them before
any of that runs. The checks encode hard-won failure modes:

  - a cue that isn't a verbatim phrase of the narration can't be voice-synced;
  - cues bunched at the end make every visual rush in at once;
  - a duplicated label reads as duplicated on screen;
  - an empty / unparseable step renders as a missing item;
  - content drawn in the base shows from the first frame, before it's spoken;
  - an over-dense step reveals too much at once.

  evaluate(scenes) -> list[str]   ([] == passes)  — human-readable problems the
  model can act on directly; feed them straight back for a repair round.
"""
import re

from deck.visual.integrity import _EMPTY_LABEL, _literals_ok

_NODE = re.compile(r"s\.(?:add|text|label|arrow)\(")
_LABEL = re.compile(r"s\.(?:text|label)\(\s*[^,]+,\s*[^,]+,\s*'((?:\\.|[^'\\])*)'")


def _norm(s):
    """Comparable word tokens (lowercase alphanumeric), matching how the recorder
    aligns cues to the spoken transcript."""
    return re.findall(r"[a-z0-9]+", s.lower())


def _sublist_index(hay, needle):
    """First index where `needle` occurs as a contiguous run in `hay`, else -1."""
    if not needle:
        return -1
    for k in range(len(hay) - len(needle) + 1):
        if hay[k:k + len(needle)] == needle:
            return k
    return -1


def _nodes(code):
    return len(_NODE.findall(code or ""))


def _labels(code):
    return [m.group(1) for m in _LABEL.finditer(code or "")]


def evaluate(scenes):
    """Return a list of quality problems ([] means the deck passes the rubric)."""
    issues = []
    for i, sl in enumerate(scenes):
        n = i + 1
        ntoks = _norm(sl.get("narration", ""))
        steps = sl.get("steps", [])

        # base must be the persistent frame only (title / empty scaffold): content
        # drawn here shows from the first frame, before the narration names it.
        base = sl.get("base", "")
        if "fillStyle:'solid'" in base or _nodes(base) > 4:
            issues.append(f"slide {n}: the base draws content elements — keep the "
                          "base to the title and at most an empty scaffold; move "
                          "every named element into the step whose cue introduces it")

        positions = []
        prev = -1
        for j, st in enumerate(steps):
            w = f"slide {n} step {j + 1}"
            cue, draw = st.get("cue", ""), st.get("draw", "")
            if not draw.strip():
                issues.append(f"{w}: empty draw — every step must draw something")
            elif not _literals_ok(draw):
                issues.append(f"{w}: broken JS string literal (a trailing "
                              "backslash escapes the closing quote and breaks the "
                              "whole step) — remove the stray backslash")
            if _EMPTY_LABEL.search(draw):
                issues.append(f"{w}: empty label s.text(...,'') — draw real text "
                              "or remove it")
            if _nodes(draw) > 6:
                issues.append(f"{w}: too dense ({_nodes(draw)} elements) — split "
                              "across more steps (aim for at most ~6 per step)")
            if not cue:
                issues.append(f"{w}: missing cue")
                continue
            pos = _sublist_index(ntoks, _norm(cue))
            if pos < 0:
                issues.append(f"{w}: cue {cue!r} is not a verbatim phrase of this "
                              "slide's narration — copy an exact substring")
            else:
                positions.append(pos)
                if pos < prev:
                    issues.append(f"{w}: cue {cue!r} is out of order — cues must "
                                  "appear in the narration in step order")
                prev = pos

        # duplicated labels within the slide
        labels = _labels(base) + [l for st in steps for l in _labels(st.get("draw", ""))]
        for l in sorted({l for l in labels if len(l) > 2 and labels.count(l) > 1}):
            issues.append(f"slide {n}: label {l!r} is drawn more than once — draw "
                          "it a single time")

        # pacing: cues must span the narration, not cluster near the end
        if len(positions) >= 3 and ntoks:
            L = len(ntoks)
            if positions[0] > 0.55 * L or (positions[-1] - positions[0]) < 0.3 * L:
                issues.append(f"slide {n}: the cues are bunched together in the "
                              "narration, so the visuals reveal all at once at the "
                              "end — rewrite the narration so the cue phrases are "
                              "spread from the beginning to the end, one per beat")
    return issues


def _demo():
    good = [{
        "narration": "First a query becomes a vector, then it is matched against "
                     "stored vectors, and finally we find the nearest neighbors.",
        "base": "s.text(540,170,'Search',{title:true,anchor:'middle'});",
        "steps": [
            {"cue": "a query becomes a vector", "draw": "s.add(s.rc.circle(1,1,9,{}));"},
            {"cue": "matched against stored vectors", "draw": "s.text(1,1,'db',{});"},
            {"cue": "find the nearest neighbors", "draw": "s.text(1,1,'near',{});"},
        ],
    }]
    assert evaluate(good) == [], evaluate(good)

    bad = [{
        "narration": "We will get to the details of deployment and subprocess use.",
        "base": "s.add(s.rc.circle(1,1,9,{fill:s.color.green,fillStyle:'solid'}));",
        "steps": [
            {"cue": "not in narration at all", "draw": "s.text(1,1,'Native ADK',{});s.text(2,2,'Native ADK',{});"},
            {"cue": "deployment", "draw": "s.text(1,1,'x \\',{});"},   # broken literal
            {"cue": "subprocess", "draw": "s.text(1,1,'',{});"},       # empty label
        ],
    }]
    got = evaluate(bad)
    assert any("not a verbatim phrase" in x for x in got)
    assert any("drawn more than once" in x for x in got)      # 'A' duplicated
    assert any("broken JS string literal" in x for x in got)
    assert any("empty label" in x for x in got)
    assert any("base draws content" in x for x in got)
    print("deck.visual.rubric self-check ok")


if __name__ == "__main__":
    _demo()
