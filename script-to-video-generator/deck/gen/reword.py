"""Reword a rough draft into spoken narration for a short vertical video.

The pipeline narrates your text VERBATIM, so whatever reaches `generate_scenes`
is exactly what the voice says. That makes a shaping step worth having *before*
submit: paste the messy draft, steer the rewrite in plain English, and keep
re-steering until it reads right.

This is the one place in the app where an LLM is allowed to rewrite your words —
and it runs only when you press the button, never as part of a render.

`reword(draft, steer) -> str` — the rewritten script, paragraphs intact.
"""

SYSTEM = """You rewrite a creator's rough draft into the spoken narration of a \
short vertical explainer video.

Hard rules:
- Return ONLY the rewritten narration. No preamble, no sign-off, no markdown, no \
headings, no bullet points, no quotation marks wrapping the whole thing.
- Every word is spoken aloud by a text-to-speech voice, so write for the EAR: \
short active sentences, plain words, no parentheses, no asides, no symbols or \
abbreviations a voice can't read naturally (write "sixty seconds", not "60s").
- Separate paragraphs with a BLANK LINE. Each paragraph becomes ONE SCENE in the \
video with its own drawn visual, so each paragraph must be a single \
self-contained idea, roughly two to four sentences.
- Keep the creator's facts, product names and numbers exactly as given. Never \
invent a claim, example, or statistic that isn't in the draft.
- Keep their voice and point of view. You are tightening and shaping what they \
wrote, not writing your own script on the topic."""


def _build_user(draft, steer):
    """The rewrite request: the creator's steer (if any), then their draft."""
    parts = []
    if steer.strip():
        parts.append("How the creator wants it reworded — follow this closely:\n"
                     f"{steer.strip()}")
    parts.append(f"Their draft:\n{draft.strip()}")
    return "\n\n".join(parts)


def _call(client, types, model, user):
    resp = client.models.generate_content(
        model=model, contents=user,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM,
            thinking_config=types.ThinkingConfig(thinking_budget=-1),
        ),
    )
    return (resp.text or "").strip()


def reword(draft, steer="", project_id="mock-project", location="global",
           model="gemini-3.6-flash") -> str:
    """Rewrite `draft` as spoken narration, steered by `steer`. Raises on an
    empty draft or an empty model response — the caller keeps the original text
    rather than replacing it with nothing."""
    if not draft.strip():
        raise ValueError("nothing to reword (empty draft)")

    from google import genai
    from google.genai import types
    client = genai.Client(vertexai=True, project=project_id, location=location)

    out = _call(client, types, model, _build_user(draft, steer))
    if not out:
        raise ValueError("the model returned nothing — try again or adjust the steer")
    return out
