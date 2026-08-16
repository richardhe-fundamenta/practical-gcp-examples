# Graph Report - script-to-video-generator  (2026-08-15)

## Corpus Check
- 18 files · ~20,810 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 473 nodes · 888 edges · 23 communities (16 shown, 7 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 50 edges (avg confidence: 0.58)
- Token cost: 0 input · 0 output

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
1. `et` - 18 edges
2. `_resolve_reveal_times()` - 18 edges
3. `ot` - 16 edges
4. `st` - 16 edges
5. `L()` - 15 edges
6. `GCS` - 14 edges
7. `k()` - 14 edges
8. `u()` - 12 edges
9. `nn()` - 12 edges
10. `generate_scenes()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `test_upload_and_download_json()` --uses--> `GCS`  [INFERRED]
  tests/test_gcs.py → deck/infra/gcs.py
- `test_upload_dir_and_list()` --uses--> `GCS`  [INFERRED]
  tests/test_gcs.py → deck/infra/gcs.py
- `test_safety_allows_drawing_blocks_escape()` --calls--> `check()`  [EXTRACTED]
  tests/test_render.py → deck/visual/safety.py
- `test_sanitize_keeps_groups_drops_unsafe_code()` --calls--> `sanitize_scenes()`  [EXTRACTED]
  tests/test_render.py → deck/visual/safety.py
- `test_build_html_assembles_offline()` --calls--> `build_html()`  [EXTRACTED]
  tests/test_render.py → deck/visual/scene.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Pre-record Visual Gate Chain** — readme_visual_compose, readme_rubric_gate, readme_safety_gate, readme_integrity_gate, readme_outro_slide [EXTRACTED 1.00]
- **Voice-sync Mechanism** — readme_cue_phrase, readme_forced_alignment, readme_overlap_scored_matching, readme_resolve_reveal_times, readme_absolute_deadline_scheduling, readme_reveal_group [EXTRACTED 1.00]
- **Cloud Render Dispatch Path** — readme_streamlit_ui, readme_fire_and_forget_dispatch, readme_cloud_run_job, readme_gcs_bucket_layout, readme_terraform_infra, cloudbuild_base_render_base_build [INFERRED 0.85]

## Communities (23 total, 7 thin omitted)

### Community 0 - "Rough.js Sketch Vendor"
Cohesion: 0.08
Nodes (26): a(), b(), c, D(), et, F(), G(), h (+18 more)

### Community 1 - "Streamlit GUI & Job Dispatch"
Cohesion: 0.07
Nodes (40): _drop_scene_widgets(), _gcs(), Script-to-video GUI. Mirrors the `deck.gen.generate` CLI: paste a title and…, Drop stale per-slide widget state. Streamlit ignores a widget's `value=` once…, _review_ui(), _video_bytes(), cache_data, cache_resource (+32 more)

### Community 2 - "Voice Recording & Alignment"
Cohesion: 0.08
Nodes (45): _align_all(), _duration(), _find_seq(), _interp(), _lead_in(), _norm(), Record a chalkboard deck to an mp4 with a Gemini TTS voiceover.…, Fill None reveal times by linear interpolation (by index) between known… (+37 more)

### Community 3 - "Anime.js Vendor"
Cohesion: 0.14
Nodes (40): a(), B(), C(), cn(), d(), E(), en(), f() (+32 more)

### Community 4 - "Pipeline Architecture Concepts (stale docs)"
Cohesion: 0.06
Nodes (42): E2_HIGHCPU_8 Machine Type Choice, Cloud Build Base Image Config, Absolute-deadline Reveal Scheduling, Thin App Image (build/Dockerfile), Heavy Base Image (Dockerfile.base), Cloud Run Render Job, Compose Pass (Deck DSL fill), Cue Phrase (+34 more)

### Community 5 - "Visual Compose & Cue Repair"
Cohesion: 0.09
Nodes (33): invalid_cues(), Small helpers for the in-GUI draft review (Phase 1 human-in-the-loop): validate…, [(step_index, cue)] for cues that are NOT verbatim substrings of the scene's…, Return a verbatim substring of `narration` matching `cue` as closely as…, Snap every step's cue to a verbatim substring of its slide's narration (mutates…, Redraw ONE slide's visual for the (possibly edited) narration, keeping the…, recompose_scene(), repair_cues() (+25 more)

### Community 6 - "Chromium Render Sandbox"
Cohesion: 0.09
Nodes (29): _egress_blocked(), On-cloud validation that the render sandbox actually works. Runs the REAL…, True if an outbound request inside the sandbox fails (i.e. no egress)., run(), drive(), main(), Chromium render/record step — the ONLY part of the pipeline that executes…, CLI contract for `sandbox exec`: argv[1] = work dir holding page.html and… (+21 more)

### Community 8 - "GCS Storage Wrapper"
Cohesion: 0.09
Nodes (8): GCS, [(name, time_created)] — for sorting by actual upload time, which name-sort…, Thin wrapper over google-cloud-storage for a single bucket., FakeBlob, FakeBucket, FakeClient, test_upload_and_download_json(), test_upload_dir_and_list()

### Community 9 - "App Authentication"
Cohesion: 0.14
Nodes (25): attempt(), _creds(), make_token(), cache_resource, App-layer login gate for the public Streamlit Cloud Run service. Validates a…, {'username','password'} from Secret Manager, cached per instance., Random per-instance key for session tokens (coherent under max-instances=1; a…, Signed 'exp.sig' session token, valid for SESSION_TTL from `now`. (+17 more)

### Community 10 - "Scene JS Quality Gates"
Cohesion: 0.14
Nodes (22): _clean(), _dedupe(), dedupe_and_repair(), _demo(), _literals_ok(), Quality gate for LLM-authored scene JS — runs AFTER the safety gate.…, True if every JS string literal in `code` is properly closed (honours backslash…, Fix the trailing-backslash footgun. Returns the (possibly) repaired code. (+14 more)

### Community 11 - "Script Pipeline Core"
Cohesion: 0.18
Nodes (17): compile_deck(), generate_scenes(), main(), _mock_scene(), script -> LLM-authored concept visuals -> recorded mp4. You supply the script;…, scenes -> (html, timeline) — the single place both the app (preview) and the…, Blank-line-separated paragraphs, trimmed. Internal newlines collapse to spaces…, Offline placeholder scene (no cloud): a title + one drawn shape. Used only by… (+9 more)

### Community 12 - "App UI Tests"
Cohesion: 0.38
Nodes (3): _click(), _enter_review(), test_regenerate_replaces_stale_cue()

## Knowledge Gaps
- **5 isolated node(s):** `Gemini TTS (Leda voice)`, `Golden Reference Deck`, `Script Mode (verbatim narration)`, `Short Mode (~60s)`, `script-to-video-generator`
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `visual_compose()` connect `Visual Compose & Cue Repair` to `Script Pipeline Core`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Why does `GCS` connect `GCS Storage Wrapper` to `Streamlit GUI & Job Dispatch`?**
  _High betweenness centrality (0.026) - this node is a cross-community bridge._
- **Why does `generate_scenes()` connect `Script Pipeline Core` to `Streamlit GUI & Job Dispatch`, `Visual Compose & Cue Repair`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **What connects `Gemini TTS (Leda voice)`, `Golden Reference Deck`, `Script Mode (verbatim narration)` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Rough.js Sketch Vendor` be split into smaller, more focused modules?**
  _Cohesion score 0.08082706766917293 - nodes in this community are weakly interconnected._
- **Should `Streamlit GUI & Job Dispatch` be split into smaller, more focused modules?**
  _Cohesion score 0.07239819004524888 - nodes in this community are weakly interconnected._
- **Should `Voice Recording & Alignment` be split into smaller, more focused modules?**
  _Cohesion score 0.07624113475177305 - nodes in this community are weakly interconnected._