"""Quality gate for LLM-authored scene JS — runs AFTER the safety gate.

`safety.py` guards against malicious/unsafe code; this guards against sloppy code
that renders wrong even though it's safe. Two failure modes seen in the wild:

  1. DUPLICATION — the model draws the exact same element twice in one slide
     (e.g. a label repeated), so it reads as duplicated on screen.
  2. BROKEN / EMPTY STEPS — a malformed string literal (classically a trailing
     backslash the model meant as a shell line-continuation, `'... \'`, which in
     a single-quoted JS string escapes the closing quote) makes `new Function`
     throw, so the WHOLE step silently draws nothing. On a numbered list that
     shows up as a missing/empty item.

Both are repaired deterministically (no cloud call):
  - the trailing-backslash footgun is fixed so the step runs;
  - exact-duplicate draw statements within a slide are dropped (keep first);
  - anything still unparseable is blanked and reported, so a broken step is
    surfaced loudly instead of shipping as a silent empty item.

  dedupe_and_repair(scenes) -> (scenes, warnings)   (mutates in place)
"""
import re

# A trailing backslash right before a string's closing quote swallows the quote
# (`'...\'` -> the quote is escaped, string runs on). The model only ever emits
# this by mistake (shell line-continuation leaking into JS), so drop the stray
# backslash when it directly precedes a quote that a terminator (, or )) follows.
_TRAILING_BS = re.compile(r"\\+('\s*[,)])")
_TRAILING_BS_DQ = re.compile(r'\\+("\s*[,)])')

# An empty label draws nothing but takes a slot — e.g. s.text(x,y,'',{...}).
_EMPTY_LABEL = re.compile(r"s\.(?:text|label)\([^,]*,[^,]*,\s*(''|\"\")")


def _literals_ok(code):
    """True if every JS string literal in `code` is properly closed (honours
    backslash escapes exactly like the JS parser). A trailing-backslash bug
    leaves a literal open, so this returns False for it."""
    i, n, quote = 0, len(code), None
    while i < n:
        ch = code[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        i += 1
    return quote is None


def _repair_literals(code):
    """Fix the trailing-backslash footgun. Returns the (possibly) repaired code."""
    code = _TRAILING_BS.sub(r"\1", code)
    code = _TRAILING_BS_DQ.sub(r"\1", code)
    return code


def _dedupe(code, seen):
    """Drop statements that exactly repeat one already drawn in this slide. Splits
    on ';' and only ever removes fragments that are complete `s.*` draw calls, so
    control flow (for/if bodies, whose fragments don't start with `s.`) is never
    touched. `seen` accumulates across a slide's base + steps."""
    kept = []
    for frag in code.split(";"):
        key = frag.strip()
        if key.startswith("s.") and key in seen:      # exact-duplicate draw call
            continue
        if key.startswith("s."):
            seen.add(key)
        kept.append(frag)
    return ";".join(kept)


def _clean(code, where, seen, warnings):
    """Repair + dedupe one draw snippet; blank it if still unparseable."""
    if not code:
        return code
    if not _literals_ok(code):
        fixed = _repair_literals(code)
        if _literals_ok(fixed):
            warnings.append(f"{where}: repaired malformed string literal")
            code = fixed
        else:
            warnings.append(f"{where}: unparseable draw code — blanked")
            return ""
    if _EMPTY_LABEL.search(code):
        warnings.append(f"{where}: empty label")
    return _dedupe(code, seen)


def dedupe_and_repair(scenes):
    """Return (scenes, warnings). Repairs broken string literals, drops
    exact-duplicate draw statements within each slide, and flags empty labels."""
    warnings = []
    for i, sl in enumerate(scenes):
        seen = set()                                   # per-slide draw statements
        sl["base"] = _clean(sl.get("base", ""), f"slide {i + 1} base",
                            seen, warnings)
        for j, st in enumerate(sl.get("steps", [])):
            cue = st.get("cue", "")
            st["draw"] = _clean(st.get("draw", ""),
                                f"slide {i + 1} step {j + 1} ({cue!r})",
                                seen, warnings)
    return scenes, warnings


def _demo():
    # the trailing-backslash footgun breaks parsing, and is repaired
    bad = "s.text(180,560,'gcloud run deploy my-service \\',{size:28});"
    assert not _literals_ok(bad)
    fixed = _repair_literals(bad)
    assert _literals_ok(fixed), fixed
    # well-formed code is left alone
    ok = "s.add(s.rc.circle(1,1,1,{}));s.text(0,0,'hi',{size:40});"
    assert _literals_ok(ok)
    seen = set()
    assert _dedupe(ok, seen) == ok
    # exact-duplicate draw call within a slide is dropped (keep first)
    dup = "s.text(1,1,'A',{});s.text(1,1,'A',{});s.add(s.rc.line(0,0,1,1,{}));"
    out = _dedupe(dup, set())
    assert out.count("s.text(1,1,'A',{})") == 1, out
    # a for-loop (fragments don't start with 's.') is never touched
    loop = "for(let k=0;k<3;k++){s.add(s.rc.circle(k,k,1,{}));}"
    assert _dedupe(loop, set()) == loop
    # end to end: broken step repaired, duplicate label dropped, empty flagged
    scenes = [{
        "narration": "n",
        "base": "s.text(540,170,'T',{title:true});",
        "steps": [
            {"cue": "a", "draw": "s.text(140,430,'1. Deploy',{});"
                                 "s.text(180,560,'run deploy \\',{size:28});"},
            {"cue": "b", "draw": "s.text(140,430,'1. Deploy',{});"        # dup
                                 "s.text(200,700,'',{size:28});"},        # empty
        ],
    }]
    clean, warns = dedupe_and_repair(scenes)
    assert _literals_ok(clean[0]["steps"][0]["draw"])                     # repaired
    assert clean[0]["steps"][1]["draw"].count("'1. Deploy'") == 0         # dup gone
    assert any("repaired" in w for w in warns)
    assert any("empty label" in w for w in warns)
    print("deck.visual.integrity self-check ok")


if __name__ == "__main__":
    _demo()
