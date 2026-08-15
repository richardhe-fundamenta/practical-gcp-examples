"""Chromium render/record step — the ONLY part of the pipeline that executes
model-authored JS, isolated so it can run inside a Cloud Run sandbox with zero
network egress and no credentials.

`drive(html_path, schedule, work)` loads the (fully self-contained, no-CDN) deck
page in headless Chromium, reveals each visual group at the instant its cue is
spoken — timing supplied by `schedule` (word timestamps + per-slide durations,
computed upstream from EITHER Gemini+whisper OR ElevenLabs' native timings) —
and records the whole thing to a webm.

It imports nothing from Google Cloud and makes no network calls: the page's
Rough.js / anime.js / fonts are inlined by deck.visual.scene, and all timing is
passed in. That is what lets the browser run behind a no-egress boundary.

Two ways in:
  * in-process: `deck.render.record` calls `drive(...)` directly (local dev / tests).
  * sandboxed:  `deck.render.record` runs THIS module as a CLI via `sandbox exec`
    (`python -m deck.render.sandbox_render WORK`), reading WORK/page.html + WORK/schedule.json
    and writing WORK/render.webm. See the `main()` contract below.
"""
import json
import os
import shutil
import sys
import time

from playwright.sync_api import sync_playwright

# Reuse the cue-alignment resolver (pure, well-tested) from deck.render.record. record
# does NOT import this module at top level, so there's no import cycle.
from deck.render.record import _resolve_reveal_times

_OUT_NAME = "render.webm"     # fixed output name inside the work dir (CLI contract)


def drive(html_path, schedule, work):
    """Record the deck at `html_path` to a webm in `work`, returning its path.

    schedule: {
      "W": int, "H": int, "init_ms": int, "tail_ms": int, "dwell_ms": int,
      "slides": [{"cues": [str], "dur": float, "words": [{"w","start"}, ...]}]
    }
    `words` is whatever the upstream aligner produced (whisper for Gemini TTS,
    ElevenLabs' native char timings otherwise) — this loop is provider-agnostic.
    """
    html_path = os.path.abspath(html_path)
    W, H = schedule["W"], schedule["H"]
    slides = schedule["slides"]
    with sync_playwright() as pw:
        # --no-sandbox / --disable-dev-shm-usage: Chromium's own sandbox can't nest
        # inside the Cloud Run sandbox (and /dev/shm is tiny there); the outer
        # sandbox + zero-egress is the real isolation boundary.
        browser = pw.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = browser.new_context(
            viewport={"width": W, "height": H},
            record_video_dir=work,
            record_video_size={"width": W, "height": H},
        )
        page = ctx.new_page()
        page.goto("file://" + html_path)
        page.wait_for_function("window.__ready === true")
        scene_groups = page.evaluate("window.SCENE_GROUPS")  # group count per scene
        page.wait_for_timeout(schedule["init_ms"])
        # Schedule every reveal against an ABSOLUTE deadline off a fixed `base`
        # (slide start = base + sum of prior clip durs, element = + its cue time).
        # Deadlining self-corrects the per-call `evaluate` latency so audio and
        # video stay locked regardless of machine load.
        base = time.monotonic()
        elapsed = 0.0
        drift = 0.0
        for i, entry in enumerate(slides):
            g = scene_groups[i]
            dur = entry["dur"]
            rel = _resolve_reveal_times(entry["cues"], g, entry["words"], dur)
            for k in range(g):
                nxt = rel[k + 1] if k + 1 < g else dur
                draw_ms = int(max(280, min(1200, (nxt - rel[k]) * 1000 * 0.9)))
                target = base + elapsed + rel[k]
                wait = target - time.monotonic()
                if wait > 0:
                    page.wait_for_timeout(int(wait * 1000))
                drift = max(drift, abs((time.monotonic() - base) - (elapsed + rel[k])))
                page.evaluate(f"window.playGroups({i},{k},{k + 1},{draw_ms})")
            elapsed += dur
            remaining = base + elapsed - time.monotonic()  # hold to end of this clip
            if remaining > 0:
                page.wait_for_timeout(int(remaining * 1000))
            # Breathing room: hold the finished slide before cutting to the next.
            # Matched by dwell_ms of silence in the concatenated audio downstream.
            page.wait_for_timeout(schedule["dwell_ms"])
            elapsed += schedule["dwell_ms"] / 1000
        page.wait_for_timeout(schedule["tail_ms"])
        print(f"[sync] max reveal drift: {drift * 1000:.0f} ms "
              f"over {len(slides)} slides")
        errors = page.evaluate("window.__errors || []")
        if errors:
            print(f"[scene] {len(errors)} draw error(s): {errors[:3]}")
        video_path = page.video.path()
        ctx.close()
        browser.close()
    return video_path


def main():
    """CLI contract for `sandbox exec`: argv[1] = work dir holding page.html and
    schedule.json. Records to <work>/render.webm and exits non-zero on failure so
    the caller (a synchronous `sandbox exec`) sees the error."""
    work = sys.argv[1]
    html_path = os.path.join(work, "page.html")
    schedule = json.load(open(os.path.join(work, "schedule.json")))
    video_path = drive(html_path, schedule, work)
    out = os.path.join(work, _OUT_NAME)
    if os.path.abspath(video_path) != os.path.abspath(out):
        shutil.move(video_path, out)
    print(out)


if __name__ == "__main__":
    main()
