"""Record a chalkboard deck to an mp4 with a Gemini TTS voiceover.

`record_deck(html_path, timeline, out)` generates one natural TTS clip per slide,
forced-aligns each clip to word timestamps (deck.render._align, run in an isolated env),
then drives the chalkboard page in headless Chromium: each visual element is
revealed at the exact moment its cue phrase is spoken, via
window.playGroups(i, k, k+1). Finally it muxes the narration over the video.
Because reveals are timed to the words themselves, sync holds regardless of
machine load.

Voice is Gemini TTS (`gemini-3.1-flash-tts-preview`), which returns raw 24kHz
mono PCM that we wrap into WAV. Change the voice via the `voice` arg — see VOICES.
"""
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import wave
from concurrent.futures import ThreadPoolExecutor

W, H = 1080, 1920
_FPS = 25               # constant output frame rate (iOS Photos rejects VFR)
_INIT_MS = 500          # let the page + first scene settle before narration
_TAIL_MS = 600          # hold the last scene briefly after its narration
_DWELL_MS = 450         # hold every slide's final frame this long before cutting
                        # to the next, so the last-revealed element gets to land
                        # instead of vanishing the instant it appears (added on
                        # top of whatever natural pause ends the narration)
_SPEED = 1.1            # final playback speed-up: the recording is muxed at this
                        # rate (video setpts + audio atempo, applied equally so
                        # A/V stay locked) to tighten the pacing end to end
_TTS_MODEL = "gemini-3.1-flash-tts-preview"
# a few prebuilt Gemini voices; pass one as `voice=`. Default is Leda.
VOICES = ("Leda", "Kore", "Puck", "Charon", "Aoede", "Fenrir")
# Parallel TTS backend: an ElevenLabs cloned voice. Its /with-timestamps endpoint
# returns pcm_24000 (raw 24kHz mono 16-bit, same as Gemini) AND character-level
# timings in one call, so this path skips whisper forced-alignment entirely.
# Key comes from the ELEVENLABS_API_KEY env var; voice id is passed per-render.
_ELEVEN_MODEL = "eleven_multilingual_v2"
_ELEVEN_URL = ("https://api.elevenlabs.io/v1/text-to-speech/{vid}"
               "/with-timestamps?output_format=pcm_24000")
_ELEVEN_CONCURRENCY = 3   # ElevenLabs caps concurrent requests by plan tier; keep
                          # the per-slide fan-out low and retry 429s (below)
# Voice settings to match the ElevenLabs playground the voice was tuned in
# (Stability ~mid-low, Similarity ~max, low Style, speaker boost on, speed ~1.0).
# Tweak to re-tune; speed here stacks with the pipeline's _SPEED mux (1.1x).
_ELEVEN_SETTINGS = {
    "stability": 0.45,
    "similarity_boost": 1.0,
    "style": 0.20,
    "use_speaker_boost": True,
    "speed": 1.0,
}
# Gemini TTS style prompt (Vertex embeds it as "{prompt}: {text}"). It steers
# delivery only and is NOT spoken aloud. Aim: professional-but-engaging — a
# confident expert, not a hype-person. Avoid "excited/passionate/warm/breathy"
# wording; that tips the model into an over-eager, flirty register. No bracketed
# markup tags either — some of those get vocalized.
_STYLE = ("Say the following as a knowledgeable technical presenter explaining "
          "something genuinely interesting to a smart, professional audience: "
          "clear, confident, and articulate, with a crisp measured pace and "
          "natural emphasis on the key ideas. Engaged and direct — composed and "
          "authoritative, never hyped, breathy, or salesy")


def _norm(s):
    """Collapse to comparable tokens: lowercase alphanumeric words (drop
    punctuation/casing so ASR 'database.' matches cue 'database')."""
    return [t for t in re.sub(r"[^a-z0-9\s]", " ", s.lower()).split() if t]


def _find_seq(toks, needle, start):
    """Start index in `toks` (>= start) that best aligns with the cue `needle`,
    else -1. Scores each candidate window by how many tokens line up positionally
    and returns the earliest best window, provided it clears ~half the cue. This
    tolerates the ASR rendering numbers/units differently than the written cue
    (e.g. "1 MB" spoken as "one megabyte") by anchoring on the tokens that DO
    match, while rejecting a weak hit so it falls back to interpolation rather
    than latching onto an unrelated later token (e.g. the "1" inside "1,000")."""
    if not needle:
        return -1
    n = len(needle)
    threshold = (n + 1) // 2                  # need ~half the cue to align (>=1)
    best_i, best_score = -1, 0
    for i in range(start, len(toks)):
        score = sum(1 for j in range(n)
                    if i + j < len(toks) and toks[i + j] == needle[j])
        if score > best_score:                # earliest window wins ties
            best_score, best_i = score, i
    return best_i if best_score >= threshold else -1


def _interp(times, clip_dur):
    """Fill None reveal times by linear interpolation (by index) between known
    anchors, bracketed by 0.0 at the start and clip_dur at the end, then clamp to
    a non-decreasing sequence within [0, clip_dur]."""
    n = len(times)
    anchors = [(-1, 0.0)] + [(i, t) for i, t in enumerate(times) if t is not None] \
        + [(n, clip_dur)]
    out = list(times)
    for (i0, t0), (i1, t1) in zip(anchors, anchors[1:]):
        for i in range(i0 + 1, i1):
            if out[i] is None:
                out[i] = t0 + (i - i0) / (i1 - i0) * (t1 - t0)
    prev = 0.0
    for i in range(n):
        out[i] = min(clip_dur, max(prev, out[i]))
        prev = out[i]
    return out


def _resolve_reveal_times(cues, n_groups, words, clip_dur):
    """Reveal time (s) for each of `n_groups` visual groups. Group 0 (the
    frame/heading) reveals at 0.0; content group k (1..n_groups-1) reveals when
    cues[k-1]'s phrase is spoken — located as a consecutive word run searched
    forward from the previous match (keeps times monotonic, handles repeats).
    Cues absent or not found are interpolated between the found neighbors, so the
    render degrades gracefully to even spacing rather than breaking."""
    n_content = max(0, n_groups - 1)
    toks = [t for w in words for t in _norm(w["w"])]
    # map each transcript token back to its word's start time
    starts = [w["start"] for w in words for _ in _norm(w["w"])]
    times = [None] * n_content
    pos = 0
    for j in range(min(n_content, len(cues))):
        needle = _norm(cues[j])
        hit = _find_seq(toks, needle, pos)
        if hit >= 0:
            times[j] = starts[hit]
            pos = hit + 1
    return [0.0] + _interp(times, clip_dur)


def _align_all(wav_paths, work):
    """Forced-align each WAV to word timestamps via the isolated deck.render._align env
    (whisper-timestamped needs Python 3.11; the main app runs 3.14). Returns one
    word list per WAV. On any failure, returns empty lists so timing falls back to
    even spacing — a broken aligner must never block a render."""
    script = os.path.join(os.path.dirname(__file__), "_align.py")
    out_json = os.path.join(work, "align.json")
    try:
        subprocess.check_call(
            ["uv", "run", "--no-project", "--python", "3.11",
             "--with", "whisper-timestamped", "python", script, out_json, *wav_paths],
            stdout=subprocess.DEVNULL)
        return json.load(open(out_json))["clips"]
    except Exception as e:                       # noqa: BLE001 - degrade, don't crash
        print(f"[sync] alignment unavailable ({e}); falling back to even spacing")
        return [[] for _ in wav_paths]


def _lead_in(raw_dur, content_dur, tail):
    """Seconds before scene 0 (page load + settle, blank board) to trim off the
    front so the video opens on real content. raw_dur = recorded length;
    content_dur = every per-scene hold incl. dwells; tail = the trailing hold."""
    return max(0.0, raw_dur - (content_dur + tail))


def _duration(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", path])
    return float(out.strip())


def _write_wav(pcm, path, rate):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)          # mono
        w.setsampwidth(2)          # L16 = 16-bit
        w.setframerate(rate)
        w.writeframes(pcm)


def _write_silence(path, ms, rate=24000):
    """A mono 16-bit WAV of `ms` silence — inserted between narration clips so the
    concatenated audio matches the per-slide video dwell (keeps A/V in sync)."""
    _write_wav(b"\x00\x00" * int(rate * ms / 1000), path, rate)


def _tts(client, types, text, path, voice, model):
    """Gemini TTS -> WAV file at `path`. Prepends `_STYLE` so delivery has energy
    (Vertex reads style as "{prompt}: {text}"; the style prompt isn't spoken)."""
    resp = client.models.generate_content(
        model=model, contents=f"{_STYLE}: {text}",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice))),
        ),
    )
    part = resp.candidates[0].content.parts[0]
    mime = part.inline_data.mime_type or ""
    rate = int(mime.split("rate=")[1].split(";")[0]) if "rate=" in mime else 24000
    _write_wav(part.inline_data.data, path, rate)


def _words_from_alignment(alignment):
    """ElevenLabs char-level timings -> [{"w": word, "start": s}], the exact shape
    _resolve_reveal_times consumes (so this replaces whisper's output). A word
    starts at its first non-whitespace character."""
    chars = alignment["characters"]
    starts = alignment["character_start_times_seconds"]
    words, cur, cur_start = [], "", None
    for c, s in zip(chars, starts):
        if c.isspace():
            if cur:
                words.append({"w": cur, "start": cur_start})
                cur, cur_start = "", None
        else:
            if not cur:
                cur_start = s
            cur += c
    if cur:
        words.append({"w": cur, "start": cur_start})
    return words


def _tts_elevenlabs(text, path, voice_id, api_key):
    """ElevenLabs cloned-voice TTS -> WAV at `path`; returns native word timestamps.
    Delivery is set by the cloned voice itself, so _STYLE isn't prepended here."""
    body = json.dumps({"text": text, "model_id": _ELEVEN_MODEL,
                       "voice_settings": _ELEVEN_SETTINGS}).encode()
    for attempt in range(6):
        req = urllib.request.Request(
            _ELEVEN_URL.format(vid=voice_id), data=body, method="POST",
            headers={"xi-api-key": api_key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                payload = json.load(r)
            break
        except urllib.error.HTTPError as e:      # back off + retry on rate limit
            if e.code == 429 and attempt < 5:
                time.sleep(min(float(e.headers.get("retry-after") or 2 ** attempt), 30))
                continue
            raise
    _write_wav(base64.b64decode(payload["audio_base64"]), path, 24000)
    return _words_from_alignment(payload["alignment"])


_SANDBOX_BIN = "/usr/local/gcp/bin/sandbox"


def _run_browser(html_path, schedule, work):
    """Run the Chromium render/record step and return the recorded webm path.

    Only this step executes model-authored JS, so when DECK_RENDER_SANDBOX=1 it
    runs inside a Cloud Run sandbox with NO network egress and NO credentials
    (see deck.render.sandbox_render). Otherwise it runs in-process (local dev / tests).
    Everything else in record_deck — TTS, alignment, ffmpeg — stays out here where
    it still has network + Vertex/ElevenLabs creds."""
    if os.environ.get("DECK_RENDER_SANDBOX") != "1":
        from deck.render.sandbox_render import drive
        return drive(html_path, schedule, work)

    # Sandboxed path: stage inputs in the (bind-mounted) work dir, then
    # run(--detach) -> exec(the render, synchronous) -> delete. `exec` blocks for
    # the whole render and surfaces its exit code, so no polling is needed.
    work = os.path.abspath(work)
    shutil.copy(html_path, os.path.join(work, "page.html"))
    with open(os.path.join(work, "schedule.json"), "w") as fh:
        json.dump(schedule, fh)
    name = "deckrender"
    env = ["--env", "PYTHONPATH=/app",
           "--env", f"PLAYWRIGHT_BROWSERS_PATH="
           f"{os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '/opt/ms-playwright')}"]
    mount = f"type=bind,source={work},destination={work}"
    try:
        subprocess.check_call([_SANDBOX_BIN, "run", name, "--detach", "--write",
                               "--mount", mount, *env, "--", "/bin/sleep", "infinity"])
        # No --allow-egress => zero internet inside the sandbox.
        subprocess.check_call([_SANDBOX_BIN, "exec", name, *env, "--",
                               sys.executable, "-m", "deck.render.sandbox_render", work])
    finally:
        # Best-effort teardown. `delete --force` still graceful-stops first and
        # blocks ~120s on our `sleep infinity` container before failing, so cap
        # the wait: the Cloud Run instance is torn down at execution end, which
        # reaps the sandbox regardless. ponytail: bounded wait, revisit if we
        # ever render multiple decks per execution (name would collide).
        try:
            subprocess.run([_SANDBOX_BIN, "delete", name, "--force"], timeout=10,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (subprocess.TimeoutExpired, OSError):
            pass
    out_webm = os.path.join(work, "render.webm")
    if not os.path.exists(out_webm):
        raise RuntimeError("sandbox render produced no video (render.webm missing)")
    return out_webm


def record_deck(html_path, timeline, out, work_dir=None,
                project_id="mock-project", location="global", voice="Leda",
                tts_provider="gemini", eleven_voice_id=None):
    """timeline: per-slide list of {"narration": str, "cues": [str, ...]}.

    One TTS clip per slide; each clip is aligned to word timestamps and every
    visual element is revealed at the instant its cue phrase is spoken.

    tts_provider: "gemini" (default) uses Gemini TTS + whisper forced-alignment;
    "elevenlabs" uses the cloned voice `eleven_voice_id` (key from the
    ELEVENLABS_API_KEY env var) and its native word timestamps (no whisper)."""
    html_path = os.path.abspath(html_path)
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    work = work_dir or tempfile.mkdtemp(prefix="deck-")
    os.makedirs(work, exist_ok=True)

    # 1. One narration WAV per slide (independent network I/O -> run concurrently).
    #    ElevenLabs returns word timestamps inline; Gemini needs a whisper pass.
    clips = [os.path.join(work, f"n{i}.wav") for i in range(len(timeline))]
    if tts_provider == "elevenlabs":
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            raise RuntimeError("ELEVENLABS_API_KEY env var required for tts_provider='elevenlabs'")
        if not eleven_voice_id:
            raise RuntimeError("eleven_voice_id required for tts_provider='elevenlabs'")

        def _clip(i):
            words = _tts_elevenlabs(timeline[i]["narration"], clips[i],
                                    eleven_voice_id, api_key)
            return _duration(clips[i]), words

        with ThreadPoolExecutor(max_workers=_ELEVEN_CONCURRENCY) as ex:
            results = list(ex.map(_clip, range(len(timeline))))
        durs = [d for d, _ in results]
        aligned = [w for _, w in results]      # native timestamps, no whisper
    else:
        from google import genai
        from google.genai import types
        client = genai.Client(vertexai=True, project=project_id, location=location)

        def _clip(i):
            _tts(client, types, timeline[i]["narration"], clips[i], voice, _TTS_MODEL)
            return _duration(clips[i])

        with ThreadPoolExecutor(max_workers=8) as ex:
            durs = list(ex.map(_clip, range(len(timeline))))
        # 2. Forced-align every clip to word timestamps (isolated whisper env).
        aligned = _align_all(clips, work)

    # 3. Record the deck, revealing each group when its cue is spoken. This is the
    #    only step that executes model-authored JS; _run_browser isolates it in a
    #    zero-egress sandbox on Cloud Run (DECK_RENDER_SANDBOX=1). The `words` are
    #    provider-agnostic — ElevenLabs' native timestamps or whisper's — so voice
    #    sync is preserved either way.
    schedule = {
        "W": W, "H": H, "init_ms": _INIT_MS, "tail_ms": _TAIL_MS, "dwell_ms": _DWELL_MS,
        "slides": [{"cues": timeline[i]["cues"], "dur": durs[i], "words": aligned[i]}
                   for i in range(len(timeline))],
    }
    video_path = _run_browser(html_path, schedule, work)

    # 3. Concatenate narration (re-encode; WAV headers don't survive -c copy).
    #    A _DWELL_MS silence after each clip matches the per-slide video dwell.
    with wave.open(clips[0]) as w0:              # match the clips' rate exactly
        rate = w0.getframerate()
    silence = os.path.join(work, "dwell.wav")
    _write_silence(silence, _DWELL_MS, rate)
    listfile = os.path.join(work, "list.txt")
    with open(listfile, "w") as fh:
        for p in clips:
            fh.write(f"file '{p}'\n")
            fh.write(f"file '{silence}'\n")
    audio_all = os.path.join(work, "all.wav")
    subprocess.check_call(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                           "-i", listfile, audio_all],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 4. Trim the page-load + settle lead-in off the front so the video opens on
    #    scene 0's content (no blank/white first frame), then mux narration from 0.
    content_dur = sum(durs) + len(timeline) * _DWELL_MS / 1000
    lead = _lead_in(_duration(video_path), content_dur, _TAIL_MS / 1000)
    subprocess.check_call([
        "ffmpeg", "-y", "-ss", f"{lead}", "-i", video_path, "-i", audio_all,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        # setpts speeds the video up but leaves non-integer frame intervals ->
        # a variable frame rate that iOS Photos refuses to import; fps={_FPS}
        # resamples back to a constant rate. scale first, then speed, then CFR.
        "-vf", f"scale={W}:{H},setpts=PTS/{_SPEED},fps={_FPS}",
        "-af", f"atempo={_SPEED}",
        # iOS Photos' import validator is stricter than its player: a 24kHz-mono
        # / isom-brand / moov-at-end / VFR mp4 plays fine in Files but Photos
        # silently refuses to save it. Force 48kHz stereo audio, the mp42 brand,
        # faststart (moov up front) and CFR so the render imports to the camera roll.
        "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest",
        "-movflags", "+faststart", "-brand", "mp42", out],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out
