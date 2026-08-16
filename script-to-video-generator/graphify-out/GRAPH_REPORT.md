# Graph Report - script-to-video-generator  (2026-08-16)

## Corpus Check
- 43 files · ~142,722 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 490 nodes · 963 edges · 23 communities (17 shown, 6 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 61 edges (avg confidence: 0.57)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d30fcb78`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Rough.js Sketch Vendor
- Streamlit GUI & Job Dispatch
- Voice Recording & Alignment
- Anime.js Vendor
- Pipeline Architecture Concepts (stale docs)
- Visual Compose & Cue Repair
- Chromium Render Sandbox
- Rough.js Generator Internals
- GCS Storage Wrapper
- App Authentication
- Scene JS Quality Gates
- Script Pipeline Core
- App UI Tests
- Forced Alignment Helper
- Visual Package Docstring
- Streamlit Cache Decorator
- Pydantic BaseModel Ref
- Pydantic BaseModel Ref (dup)
- Repository Root

## God Nodes (most connected - your core abstractions)
1. `GCS` - 24 edges
2. `_resolve_reveal_times()` - 18 edges
3. `et` - 18 edges
4. `st` - 16 edges
5. `ot` - 16 edges
6. `L()` - 15 edges
7. `generate_scenes()` - 14 edges
8. `k()` - 14 edges
9. `build_html()` - 13 edges
10. `run_job()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `_gcs()` --uses--> `GCS`  [INFERRED]
  app.py → deck/infra/gcs.py
- `_review_ui()` --calls--> `invalid_cues()`  [EXTRACTED]
  app.py → deck/gen/review.py
- `_review_ui()` --calls--> `recompose_scene()`  [EXTRACTED]
  app.py → deck/gen/review.py
- `_review_ui()` --calls--> `build_preview_html()`  [EXTRACTED]
  app.py → deck/visual/scene.py
- `test_compile_deck_roundtrips_scenes_to_timeline()` --calls--> `compile_deck()`  [EXTRACTED]
  tests/test_generate_split.py → deck/gen/generate.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Pre-record Visual Gate Chain** — readme_visual_compose, readme_rubric_gate, readme_safety_gate, readme_integrity_gate, readme_outro_slide [EXTRACTED 1.00]
- **Voice-sync Mechanism** — readme_cue_phrase, readme_forced_alignment, readme_overlap_scored_matching, readme_resolve_reveal_times, readme_absolute_deadline_scheduling, readme_reveal_group [EXTRACTED 1.00]
- **Cloud Render Dispatch Path** — readme_streamlit_ui, readme_fire_and_forget_dispatch, readme_cloud_run_job, readme_gcs_bucket_layout, readme_terraform_infra, cloudbuild_base_render_base_build [INFERRED 0.85]

## Communities (23 total, 6 thin omitted)

### Community 0 - "Rough.js Sketch Vendor"
Cohesion: 0.08
Nodes (26): a(), b(), c, D(), et, F(), G(), h (+18 more)

### Community 1 - "Streamlit GUI & Job Dispatch"
Cohesion: 0.06
Nodes (46): _drop_scene_widgets(), _gcs(), Script-to-video GUI. Mirrors the `deck.gen.generate` CLI: paste a title and…, Drop stale per-slide widget state. Streamlit ignores a widget's `value=` once…, _review_ui(), _video_bytes(), cache_data, cache_resource (+38 more)

### Community 2 - "Voice Recording & Alignment"
Cohesion: 0.07
Nodes (46): _align_all(), _duration(), _find_seq(), _interp(), _lead_in(), _norm(), Record a chalkboard deck to an mp4 with a Gemini TTS voiceover.…, Fill None reveal times by linear interpolation (by index) between known… (+38 more)

### Community 3 - "Anime.js Vendor"
Cohesion: 0.14
Nodes (40): a(), B(), C(), cn(), d(), E(), en(), f() (+32 more)

### Community 4 - "Pipeline Architecture Concepts (stale docs)"
Cohesion: 0.06
Nodes (42): E2_HIGHCPU_8 Machine Type Choice, Cloud Build Base Image Config, Absolute-deadline Reveal Scheduling, Thin App Image (build/Dockerfile), Heavy Base Image (Dockerfile.base), Cloud Run Render Job, Compose Pass (Deck DSL fill), Cue Phrase (+34 more)

### Community 5 - "Visual Compose & Cue Repair"
Cohesion: 0.15
Nodes (20): _build_user(), _content_digest(), _ensure_count(), _fallback_scene(), _generate(), LLM "visual compose": turn deck content into bespoke, per-topic Rough.js…, Compact per-slide content the model visualizes (layout + all text fields + any…, One compose call -> parsed, shape-checked slide list (retries bad JSON). (+12 more)

### Community 6 - "Chromium Render Sandbox"
Cohesion: 0.07
Nodes (42): invalid_cues(), Small helpers for the in-GUI draft review (Phase 1 human-in-the-loop): validate…, [(step_index, cue)] for cues that are NOT verbatim substrings of the scene's…, Return a verbatim substring of `narration` matching `cue` as closely as…, Snap every step's cue to a verbatim substring of its slide's narration (mutates…, Redraw ONE slide's visual for the (possibly edited) narration, keeping the…, recompose_scene(), repair_cues() (+34 more)

### Community 9 - "App Authentication"
Cohesion: 0.22
Nodes (21): architecture(), arrow(), box(), C, card(), deployment(), elbow(), esc() (+13 more)

### Community 10 - "Scene JS Quality Gates"
Cohesion: 0.14
Nodes (22): _clean(), _dedupe(), dedupe_and_repair(), _demo(), _literals_ok(), Quality gate for LLM-authored scene JS — runs AFTER the safety gate.…, True if every JS string literal in `code` is properly closed (honours backslash…, Fix the trailing-backslash footgun. Returns the (possibly) repaired code. (+14 more)

### Community 11 - "Script Pipeline Core"
Cohesion: 0.18
Nodes (17): compile_deck(), generate_scenes(), main(), _mock_scene(), script -> LLM-authored concept visuals -> recorded mp4. You supply the script;…, scenes -> (html, timeline) — the single place both the app (preview) and the…, Blank-line-separated paragraphs, trimmed. Internal newlines collapse to spaces…, Offline placeholder scene (no cloud): a title + one drawn shape. Used only by… (+9 more)

### Community 12 - "App UI Tests"
Cohesion: 0.38
Nodes (8): _click(), _enter_review(), test_generate_defaults_to_background_job(), test_generate_enters_review_mode(), test_regenerate_replaces_stale_cue(), test_reword_failure_keeps_the_users_text(), test_reword_replaces_the_script_and_keeps_the_original(), test_second_reword_re_steers_from_the_original_not_the_rewrite()

### Community 15 - "Streamlit Cache Decorator"
Cohesion: 0.24
Nodes (12): _build_user(), _call(), Reword a rough draft into spoken narration for a short vertical video. The…, The rewrite request: the creator's steer (if any), then their draft., Rewrite `draft` as spoken narration, steered by `steer`. Raises on an empty…, reword(), Draft rewording: prompt shape and the guards around a bad model response., test_build_user_puts_the_steer_before_the_draft() (+4 more)

### Community 16 - "Pydantic BaseModel Ref"
Cohesion: 0.40
Nodes (4): Knowledge graph, Map, script-to-video-generator, Testing

## Knowledge Gaps
- **16 isolated node(s):** `fs`, `path`, `ROOT`, `src`, `R` (+11 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `visual_compose()` connect `Visual Compose & Cue Repair` to `Scene JS Quality Gates`, `Script Pipeline Core`, `Chromium Render Sandbox`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Why does `record_deck()` connect `Voice Recording & Alignment` to `Streamlit GUI & Job Dispatch`, `Script Pipeline Core`, `Chromium Render Sandbox`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `GCS` (e.g. with `_gcs()` and `dispatch_deck_job()`) actually correct?**
  _`GCS` has 9 INFERRED edges - model-reasoned connections that need verification._
- **What connects `fs`, `path`, `ROOT` to the rest of the system?**
  _16 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Rough.js Sketch Vendor` be split into smaller, more focused modules?**
  _Cohesion score 0.08082706766917293 - nodes in this community are weakly interconnected._
- **Should `Streamlit GUI & Job Dispatch` be split into smaller, more focused modules?**
  _Cohesion score 0.05754475703324808 - nodes in this community are weakly interconnected._
- **Should `Voice Recording & Alignment` be split into smaller, more focused modules?**
  _Cohesion score 0.07183673469387755 - nodes in this community are weakly interconnected._