# script-to-video-generator

Your script → LLM-authored Rough.js concept visuals → Chromium-recorded vertical
mp4 with a TTS voiceover, cue-synced by forced alignment. The script is narrated
**verbatim**: one blank-line paragraph per scene, force-restored after compose.
There are no other modes — no research, no deck DSL, no fact-check.

## Map

| Path | What |
| --- | --- |
| `app.py` | Streamlit GUI (Title + Script) + optional human-in-the-loop scene review. Mirrors the `deck.gen.generate` CLI. |
| `deck/gen/generate.py` | The pipeline: paragraph split → compose → gates → **verbatim lock** → `compile_deck` → record. CLI entrypoint. |
| `deck/gen/reword.py` | Pre-submit draft rewrite (GUI **Reword** button). The one place an LLM rewrites your words; never runs during a render. |
| `deck/gen/review.py` | Cue validation/snapping (`repair_cues`, `snap_cue`) and single-scene redraw for the GUI. |
| `deck/visual/compose.py` | The one LLM call: paragraph → bespoke scene JS + cues. Narration is always locked. |
| `deck/visual/rubric.py` → `safety.py` → `integrity.py` | Pre-record gate chain, in that order. |
| `deck/visual/scene.py` `vendor/` | `build_html()` scene-kit harness; vendored anime.js, rough.js, fonts. |
| `deck/render/record.py` `sandbox_render.py` | Chromium record + TTS (Gemini or ElevenLabs) → mp4. |
| `deck/render/_align.py` | Forced alignment, `_resolve_reveal_times()`, absolute-deadline scheduling. |
| `deck/infra/gcs.py` `job.py` | `GCS` bucket layout, fire-and-forget Cloud Run job dispatch. No app-layer auth — IAP gates the service. |
| `examples/talk.txt` | Sample script for `--mock --html-only` smoke tests. |
| `docs/diagrams.js` | Generates the README's 3 SVGs (pipeline, architecture, deployment) with the vendored Rough.js (`node docs/diagrams.js`). Seeded — output is byte-stable. |
| `build/` `Dockerfile.base` `terraform/` | Heavy base image + thin app image, Cloud Run job, infra. |

Job payload: `jobs/<id>.json` = `{name, title, settings{script, voice, …}}`.
Reviewed scenes go to `drafts/<id>.json` for a record-only run.

Infra (project `rocketech-de-pgcp-sandbox`): job/SA `script-to-video-render`,
service/SA `script-to-video-web`, bucket + AR repo `script-to-video*`, TF state
prefix `script-to-video-generator`. Separate from the older edu-video-gen stack.

## Testing

`uv run pytest` — fully offline. `tests/test_record.py::test_record_deck_feeds_elevenlabs_timestamps_to_sandbox`
fails locally without `ffmpeg`/`ffprobe` installed; that is environmental, not a regression.

## Knowledge graph

`graphify-out/` holds a graph of this repo (490 nodes, 963 edges), updated after
the script-only refactor. The doc nodes from `README.md`/`CLAUDE.md` are still the
pre-refactor ones (semantic extraction was skipped) — code nodes are current.

- **Never read `graphify-out/graph.json` or `graph.html`** — ~136k tokens and larger.
- Ask it instead: `/graphify query "<question>" --budget 1500`, `/graphify path "A" "B"`, `/graphify explain "<node>"`.

Source is ~3k lines total, so reading the actual code is usually cheaper than a
graph query. Prefer it.
