"""LLM "visual compose": turn deck content into bespoke, per-topic Rough.js scenes.

The whole bet: instead of filling a constrained DSL that a fixed renderer
draws, the model AUTHORS the drawing code itself — tailored to the
topic, visualization-heavy, less text. It writes JS against the scene-kit `s`
(see `deck.visual.scene`). We keep the sync contract by requiring
`s.step(cue, ...)` per revealed element, with `cue` a verbatim phrase of that
slide's narration. The output is statically safety-vetted (`deck.visual.safety`)
before it ever runs in the page.

`visual_compose(title, slides, ...)` -> list of
  {"narration": str, "base": js, "steps": [{"cue": str, "draw": js}]}
"""
import json

SYSTEM = r"""You are a motion-graphics director who draws hand-sketched
"chalkboard" explainer visuals with Rough.js. You are given a slide's factual
content and you output the NARRATION plus the DRAWING CODE that visualizes it.

PHILOSOPHY — VISUALS FIRST, TEXT LAST.
The voice-over carries the words. The screen must carry a PICTURE, not a wall of
text. For every slide, ask "what diagram makes this idea obvious?" — then draw
it: boxes and flows, before/after, a pipeline, nested containers, a comparison,
quantities shown as sizes/bars, spatial relationships, arrows showing movement.
On-screen text is ONLY short labels (1-3 words) attached to shapes. NEVER put a
sentence or a bullet list on screen. If you catch yourself writing a paragraph
of text, replace it with a drawing.

CANVAS: 1080 x 1920 portrait (9:16), dark green chalkboard. Chalk colours live
in `s.color`: white, yellow, blue, green, salmon, purple, dim. Use colour with
meaning (e.g. green = good/success, salmon = problem, blue = neutral component).

THE SCENE-KIT `s` (the ONLY API you may use — no DOM, no external libs):
- `s.rc` — a Rough.js SVG instance. Methods return an SVG node:
    s.rc.rectangle(x,y,w,h,opts) · s.rc.line(x1,y1,x2,y2,opts)
    s.rc.circle(cx,cy,diameter,opts) · s.rc.ellipse(cx,cy,w,h,opts)
    s.rc.polygon([[x,y],...],opts) · s.rc.path("M.. L.. C..",opts)
    s.rc.curve([[x,y],...],opts) · s.rc.linearPath([[x,y],...],opts)
  opts: {stroke, strokeWidth, fill, fillStyle:'hachure'|'solid'|'cross-hatch'|'zigzag',
         fillWeight, hachureGap, roughness}. Pass colours as s.color.NAME.
- `s.add(node)` — YOU MUST pass every s.rc.* node through s.add() so it draws on
  and reveals with its group. e.g. `s.add(s.rc.circle(300,500,120,{stroke:s.color.yellow}));`
- `s.text(x,y,str,{size,anchor,color,title,maxW})` — short hand-written label.
  anchor 'start'|'middle'|'end'. title:true = big display font. Keep labels tiny.
- `s.arrow(x1,y1,x2,y2,{color})` — hand-drawn arrow (line + head), auto-added.
- `s.W`(1080) `s.H`(1920) `s.SAFE` = {x:70,y:250,w:940,h:1560,cx:540}. Keep all
  drawing inside SAFE. The title band is the top ~120-230px; the chalk tray is
  the bottom ~34px — don't draw over them.

STRUCTURE OF YOUR OUTPUT per slide:
- "narration": one natural, spoken sentence or two for the slide (what the
  presenter says). Specific and accurate to the given content.
- "base": JS that draws GROUP 0 — ONLY the persistent frame meant to stay up for
  the WHOLE slide: a short title/heading at top, and at most an EMPTY structural
  scaffold (an axis, an outer container box, a baseline). Do NOT draw any content
  element here — no dots, nodes, markers, bars, icons, or labels that the
  narration introduces later. If a thing represents something the voice-over
  names, it belongs in the STEP whose cue names it, so it appears exactly when
  spoken — never pre-drawn up front and "filled in" later. When in doubt, put it
  in a step, not the base. Shown as narration starts.
- "steps": an ORDERED list; each item reveals ONE visual element as it is named.
    - "cue": a short phrase COPIED VERBATIM from THIS slide's narration (an exact
      substring), marking the moment the element should appear.
    - "draw": JS drawing that element with the kit. Multiple s.add()/s.text()
      calls are fine — they reveal together as one group.
  Aim for 3-6 steps per slide. The cues must appear in the narration in the same
  order as the steps. Keep each step DIGESTIBLE — at most ~6 drawn nodes
  (shapes + labels) in a single step. If an idea needs more detail, split it
  across MORE steps rather than cramming one dense step; a step that draws a
  dozen things at once reveals too much at once and rushes its draw-on.

PACING — SPREAD THE CUES ACROSS THE WHOLE NARRATION (critical):
  Each element reveals exactly when its cue is spoken, so the cues must be
  DISTRIBUTED through the narration: the first cue near the beginning, the last
  cue near the end, the rest spaced roughly evenly between. NEVER cluster the cue
  phrases in the final sentence — if every cue lands in the last few words, all
  the visuals pop in at once, rushed, right before the slide ends. Write the
  narration long enough that consecutive cues are about one clause or sentence
  apart (roughly one spoken beat per step), and order the sentences so the
  drawing builds up progressively as the presenter talks — not all at the end.

RULES:
- Output MUST be valid JS statements using ONLY `s`. No comments needed. No
  `function`, no `return`, no imports — just statements, e.g.
  `s.add(s.rc.rectangle(200,400,300,180,{stroke:s.color.blue,fill:s.color.blue,fillStyle:'hachure'}));`
- NO DUPLICATION: never draw the same label or element twice, and do not
  re-explain a point already covered on another slide — each slide earns its
  place. Every step must draw something real; never emit an empty label
  (`s.text(x,y,'')`) or a placeholder.
- Watch string literals: a JS string ends at its quote, so NEVER end one with a
  backslash (e.g. a shell line-continuation `gcloud ... \`); it escapes the
  quote and breaks the whole step. Write such text without the trailing `\`.
- Coordinates are absolute px. Space elements generously; do not overlap shapes
  or let labels collide. Think about layout before drawing.
- READABILITY: NEVER put text on top of a filled/hachure/cross-hatch shape — the
  fill strokes cut through the letters (green hachure is the worst). If a box
  needs a label inside it, draw the box STROKE-ONLY (no fill). Use fills only on
  shapes that carry no text (icons, accent dots, quantity bars).
- Prefer drawing the MECHANISM over labelling it. Show data moving, structures
  nesting, sizes differing.

WORKED EXAMPLE (one slide) — study the shape, then do better for the real content:
{
  "narration": "A query is turned into a vector, then matched against millions of stored vectors to find the nearest neighbors.",
  "base": "s.text(s.W/2,170,'Vector Search',{size:66,anchor:'middle',title:true,color:s.color.yellow});",
  "steps": [
    {"cue":"query is turned into a vector","draw":"s.add(s.rc.rectangle(90,360,360,150,{stroke:s.color.white,fill:s.color.white,fillStyle:'hachure',hachureGap:14}));s.text(120,450,'query',{size:40});s.arrow(470,435,650,435,{color:s.color.salmon});s.add(s.rc.circle(760,435,120,{stroke:s.color.blue,fill:s.color.blue,fillStyle:'solid'}));s.text(760,448,'vec',{size:34,anchor:'middle',color:s.color.white});"},
    {"cue":"matched against millions of stored vectors","draw":"for(let k=0;k<12;k++){s.add(s.rc.circle(200+((k*140)%760),760+Math.floor(k/6)*180,70,{stroke:s.color.dim}));}"},
    {"cue":"find the nearest neighbors","draw":"s.add(s.rc.circle(340,760,90,{stroke:s.color.green,strokeWidth:4}));s.add(s.rc.circle(480,760,90,{stroke:s.color.green,strokeWidth:4}));s.text(s.W/2,1080,'nearest',{size:38,anchor:'middle',color:s.color.green});"}
  ]
}

Return ONLY a JSON array of such slide objects, one per input slide, in order."""


def _content_digest(slides):
    """Compact per-slide content the model visualizes (layout + all text fields +
    any existing narration), stripped of DSL noise."""
    out = []
    for i, s in enumerate(slides):
        fields = {k: v for k, v in s.items() if k not in ("cues",)}
        out.append(f"--- SLIDE {i + 1} (layout={s.get('layout', '?')}) ---\n"
                   + json.dumps(fields, ensure_ascii=False))
    return "\n".join(out)


# How many times to hand the rubric's complaints back to the model for a fix
# before giving up and rendering the best result anyway. Each round is one cheap
# LLM call — far cheaper than discovering the problem after TTS + recording.
_MAX_REPAIR = 2


def _generate(client, types, model, user):
    """One compose call -> parsed, shape-checked slide list (retries bad JSON)."""
    last_err = None
    for _ in range(3):
        resp = client.models.generate_content(
            model=model, contents=user,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM,
                response_mime_type="application/json",
                thinking_config=types.ThinkingConfig(thinking_budget=-1),
            ),
        )
        try:
            data = json.loads(resp.text)
            if not isinstance(data, list) or not data:
                raise ValueError("expected a non-empty JSON array")
            for sl in data:                       # minimal shape check
                sl.setdefault("base", "")
                sl.setdefault("steps", [])
                if "narration" not in sl:
                    raise ValueError("slide missing narration")
            return data
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
    raise last_err


def _repair_prompt(data, issues):
    """Ask the model to fix the rubric's specific complaints in its own output."""
    return ("The scene JSON you produced has the quality problems listed below. "
            "Return the FULL corrected JSON array for ALL slides — fix EVERY "
            "problem and keep everything else exactly as it was.\n\nPROBLEMS:\n"
            + "\n".join(f"- {x}" for x in issues)
            + "\n\nYOUR PREVIOUS OUTPUT:\n"
            + json.dumps(data, ensure_ascii=False))


def _build_user(title, slides):
    """The compose user prompt for `slides` (also reused to re-request a dropped
    tail — same instructions, fewer slides). The narration is a VERBATIM script:
    the model only draws and picks cues, it never rewords."""
    return (f"Deck title: {title}\n\nDraw a visual for each of the following "
            f"{len(slides)} slides — ONE scene per slide, in the SAME ORDER.\n\n"
            f"The narration of each slide is FIXED. Copy it into your output "
            f'"narration" field EXACTLY, word for word — do NOT rewrite, '
            f"shorten, translate, or rephrase it (not even punctuation). Your "
            f"job is ONLY to draw an intuitive, abstract visual for the concept "
            f"and to choose that slide's cues as short phrases copied VERBATIM "
            f"from its fixed narration, spread evenly from the first sentence to "
            f"the last so the drawing builds up as the presenter speaks.\n\n"
            f"{_content_digest(slides)}")


def _fallback_scene(slide):
    """A minimal but REAL scene — never a blank board. Draws the slide's opening
    words as a chalk title so a slide the model failed to draw still shows
    something relevant instead of narration over an empty board."""
    narr = slide.get("narration", "")
    head = " ".join(narr.split()[:6]) or "…"
    return {"narration": narr, "steps": [],
            "base": f"s.text(s.W/2,s.H/2,{json.dumps(head)},"
                    "{size:56,anchor:'middle',title:true,color:s.color.yellow});"}


def _ensure_count(client, types, model, title, slides, data, say):
    """Guarantee exactly one scene per input slide. Long decks can get truncated
    mid-array (the model drops trailing slides), and a missing scene became a blank
    board with narration over it. Re-request the dropped tail in a small follow-up
    call (few slides -> no truncation); if that still falls short, fill with a
    title-card fallback. Never returns fewer — or more — than len(slides)."""
    if len(data) < len(slides):
        missing = slides[len(data):]
        say(f"Model returned {len(data)}/{len(slides)} scenes; drawing the rest…")
        print(f"[compose] short by {len(missing)} scene(s); re-requesting the tail")
        try:
            data = data + _generate(client, types, model,
                                    _build_user(title, missing))
        except Exception as e:                       # noqa: BLE001 - fall back, don't crash
            print(f"[compose] tail re-request failed ({e}); using title-card fallback")
        while len(data) < len(slides):
            data.append(_fallback_scene(slides[len(data)]))
    return data[:len(slides)]


def visual_compose(title, slides, project_id, location="global",
                   model="gemini-3.6-flash", progress=None):
    """Deck content -> bespoke Rough.js scenes (see module doc).

    Composes, then scores the result against a deterministic rubric
    (`deck.visual.rubric`) and, while it fails, hands the model its own JSON plus
    the exact list of problems for up to `_MAX_REPAIR` fix rounds — all BEFORE the
    expensive TTS/recording stage, so only clean decks reach it.

    The incoming narration is a VERBATIM script that must not be reworded: the
    model only draws + picks cues, and is told to echo each slide's narration
    unchanged. The caller still force-restores the exact text afterwards."""
    from google import genai
    from google.genai import types

    from deck.visual.rubric import evaluate
    say = progress or (lambda *_: None)
    client = genai.Client(vertexai=True, project=project_id, location=location)

    user = _build_user(title, slides)

    say(f"Drawing visuals for {len(slides)} slide(s)…")
    data = _generate(client, types, model, user)
    issues = evaluate(data)
    rounds = 0
    while issues and rounds < _MAX_REPAIR:
        rounds += 1
        say(f"Refining visuals (quality pass {rounds}/{_MAX_REPAIR})…")
        print(f"[rubric] {len(issues)} issue(s); repair round {rounds}/{_MAX_REPAIR}:")
        for x in issues:
            print("  -", x)
        data = _generate(client, types, model, _repair_prompt(data, issues))
        issues = evaluate(data)
    if issues:
        print(f"[rubric] {len(issues)} issue(s) remain after repair; continuing:")
        for x in issues:
            print("  -", x)
    elif rounds:
        print("[rubric] all issues resolved after repair")
    return _ensure_count(client, types, model, title, slides, data, say)
