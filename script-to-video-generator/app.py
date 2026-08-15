"""Script-to-video GUI.

Mirrors the `deck.gen.generate` CLI: paste a title and your script, hit
generate, and the render runs in the background on a Cloud Run Job. Your script
is narrated verbatim over hand-sketched concept visuals. Sensible defaults live
in an Advanced expander. A downloads section lists previously generated videos
from GCS, newest-first, paginated.

Access control is IAP's job (see terraform/main.tf): the service is only
reachable through Identity-Aware Proxy, which requires a Google login from the
allowed Workspace domain before a request ever reaches this process.
"""
import os

import streamlit as st
import streamlit.components.v1 as components

from deck.infra.gcs import GCS
from deck.infra.job import (dispatch_draft_job, list_videos, make_name,
                            save_draft)

# --- config (env overrides; defaults match terraform/terraform.tfvars) -----------
BUCKET = os.environ.get("GCS_BUCKET", "script-to-video-rocketech-de-pgcp-sandbox")
INFRA_PROJECT = os.environ.get("INFRA_PROJECT", "rocketech-de-pgcp-sandbox")
REGION = os.environ.get("REGION", "us-central1")
JOB_NAME = os.environ.get("DECK_JOB_NAME", "script-to-video-render")

VOICES = ["Leda", "Puck", "Charon", "Kore", "Fenrir", "Aoede", "Zephyr"]
# ElevenLabs cloned voices: display name -> voice id. Add new voices here.
ELEVEN_VOICES = {"Richard He": "RMkyYHMiYJR8hoJhwICu"}
MODELS = ["gemini-3.6-flash", "gemini-3.6-pro"]
PER_PAGE = 10
MAX_VIDEOS = 100


@st.cache_resource
def _gcs():
    return GCS(BUCKET)


@st.cache_data(show_spinner=False)
def _video_bytes(name):
    return _gcs().download_bytes(f"output/{name}")


def _drop_scene_widgets(prefixes):
    """Drop stale per-slide widget state. Streamlit ignores a widget's `value=`
    once its key exists in session_state, so when scene data changes underneath a
    stable key (a redraw's new cues, or a fresh draft reusing slide 0's keys) the
    old value silently masks the new one. Purge the keys so `value=` takes."""
    for k in [k for k in st.session_state if k.startswith(tuple(prefixes))]:
        del st.session_state[k]


def _review_ui():
    from deck.gen.review import invalid_cues, recompose_scene
    from deck.visual.scene import build_preview_html
    d = st.session_state.draft
    scenes = d["scenes"]
    n = len(scenes)
    st.subheader(f"Review & edit — {d['title']}")
    st.caption("Preview each slide, fix the narration or cues, redraw a visual, "
               "then send the approved version to render.")

    # Key the selectbox so its value IS session_state["active_slide"] in the same
    # run — passing index= from a lagging copy took two clicks to switch slides.
    # Clamp before the widget instantiates (slide count varies between drafts).
    st.session_state.active_slide = min(st.session_state.get("active_slide", 0),
                                        n - 1)
    i = st.selectbox("Slide", range(n), key="active_slide",
                     format_func=lambda k: f"Slide {k + 1} of {n}")
    sc = scenes[i]

    components.html(build_preview_html(d["title"], sc), height=820, scrolling=False)

    sc["narration"] = st.text_area("Narration (spoken)", value=sc["narration"],
                                   key=f"narr_{i}", height=120)
    st.caption("Cues — each must be an exact phrase copied from the narration.")
    for j, step in enumerate(sc.get("steps", [])):
        step["cue"] = st.text_input(f"Cue {j + 1}", value=step.get("cue", ""),
                                    key=f"cue_{i}_{j}")
    bad = invalid_cues(sc)
    if bad:
        st.warning("Not exact substrings of the narration: "
                   + "; ".join(repr(c) for _, c in bad))

    if st.button("♻️ Regenerate this slide's visual"):
        try:
            with st.spinner("Redrawing…"):
                new = recompose_scene(d["title"], sc["narration"],
                                      project_id=d["settings"]["project_id"],
                                      location=d["settings"]["location"],
                                      model=d["model"])
            sc["base"], sc["steps"] = new["base"], new["steps"]
            _drop_scene_widgets([f"cue_{i}_"])  # let the new cues render
            st.rerun()
        except Exception as e:  # noqa: BLE001
            st.error(f"Redraw failed: {e}")

    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("✅ Approve & render", type="primary"):
        problems = {k + 1: invalid_cues(s) for k, s in enumerate(scenes)}
        problems = {k: v for k, v in problems.items() if v}
        if problems:
            st.error("Fix invalid cues before rendering — slides: "
                     + ", ".join(map(str, problems)))
        else:
            try:
                save_draft(_gcs(), d["name"], d["title"], scenes, d["settings"])
                dispatch_draft_job(BUCKET, d["name"], INFRA_PROJECT, REGION, JOB_NAME)
                st.toast(f"Rendering in the background: {d['name']}", icon="🎬")
                del st.session_state.draft
                st.rerun()
            except Exception as e:  # noqa: BLE001
                st.error(f"Could not start the render job: {e}")
    if c2.button("🗑 Discard draft"):
        del st.session_state.draft
        st.rerun()


st.set_page_config(page_title="Script to video", page_icon="🎬")
# Mobile fit: stack columns and tighten padding on narrow screens.
# ponytail: relies on Streamlit's internal data-testids; revisit after a major
# Streamlit upgrade if columns stop stacking on phones.
st.markdown(
    """<style>@media (max-width:640px){
      [data-testid="stMainBlockContainer"]{padding:1rem 0.8rem;}
      [data-testid="stColumn"]{min-width:100%!important;flex:1 1 100%!important;}
    }</style>""",
    unsafe_allow_html=True,
)
st.title("🎬 Script to video")

# --- generate ----------------------------------------------------------------
if "draft" not in st.session_state:
    submitted = st.session_state.pop("submitted", None)  # set by the auto path below
    if submitted:
        st.success(f"✅ Submitted — generating & rendering **{submitted}** in the "
                   "background. It'll appear under “Generated videos” below when done.")
    topic = st.text_input("Title", key="topic",
                          placeholder="Why caching is hard")

    # Rewriting the script box has to happen HERE, before the widget exists.
    # Streamlit only accepts a programmatic write to a widget's key while the
    # widget is not yet instantiated this run; assigning afterwards raises, and
    # deleting the key + passing a new `value=` does NOT reach the browser — the
    # mounted textarea keeps its own text and the rewrite silently vanishes.
    # So the buttons below only record intent, then rerun into this block.
    pending = st.session_state.pop("reword_pending", None)
    if pending:
        try:
            from deck.gen.reword import reword
            with st.spinner("Rewording…"):
                st.session_state["reference"] = reword(
                    pending["draft"], pending["steer"],
                    project_id=st.session_state.get("project_id", INFRA_PROJECT),
                    location=st.session_state.get("location", "global"),
                    model=st.session_state.get("model", MODELS[0]))
        except Exception as e:  # noqa: BLE001 - surface it, keep their text
            st.error(f"Reword failed (your draft is unchanged): {e}")
        else:
            st.session_state.script_original = pending["draft"]
    if "revert_pending" in st.session_state:
        del st.session_state["revert_pending"]
        st.session_state["reference"] = st.session_state.pop("script_original", "")

    reference = st.text_area(
        "Script (spoken verbatim)", key="reference",
        placeholder="Paste your draft — one paragraph per scene, spoken word-for-word.",
        height=200,
    )

    with st.expander("✍️ Reword with Gemini (optional — shape a rough draft first)"):
        st.caption("Paste everything you want to cover, then steer the rewrite until "
                   "it reads right. Nothing is sent to the renderer until you hit "
                   "Generate.")
        steer = st.text_area(
            "How should it be reworded?", key="steer", height=80,
            placeholder="e.g. cut it to about 45 seconds, keep the caching examples, "
                        "open with the punchiest line, drop the jargon",
        )
        c1, c2 = st.columns([1, 1])
        if c1.button("✨ Reword", disabled=not reference.strip()):
            # Reword always runs from the ORIGINAL draft, never from the previous
            # rewrite — re-steering should change the result, not compound on it.
            st.session_state.reword_pending = {
                "draft": st.session_state.get("script_original") or reference,
                "steer": steer,
            }
            st.rerun()                    # the rewrite happens at the top of the run
        if st.session_state.get("script_original"):
            if c2.button("↩︎ Back to my draft"):
                st.session_state.revert_pending = True
                st.rerun()
            st.caption("Reworded. Each reword re-runs from your original draft, so "
                       "changing the steer re-steers instead of drifting further.")

    with st.expander("Advanced (sensible defaults — nothing to change for a normal run)"):
        tts_provider = st.selectbox("Voice engine", ["elevenlabs", "gemini"], index=0,
                                    format_func=lambda p: {"gemini": "Gemini TTS",
                                                           "elevenlabs": "ElevenLabs (cloned voice)"}[p])
        if tts_provider == "elevenlabs":
            eleven_name = st.selectbox("Voice", list(ELEVEN_VOICES), index=0)
            eleven_voice_id = ELEVEN_VOICES[eleven_name]
            voice = "Leda"
        else:
            eleven_voice_id = None
            voice = st.selectbox("Voice", VOICES, index=0)
        # keyed so the reword block above can read them (it renders first, so on
        # the very first run it falls back to these same defaults)
        model = st.selectbox("Model", MODELS, index=0, key="model")
        project_id = st.text_input("Vertex project", value=INFRA_PROJECT, key="project_id")
        location = st.text_input("Vertex location", value="global", key="location")
        review_first = st.checkbox(
            "Review & edit scenes before rendering", value=False, key="review_first",
            help="Off (default): generate and render fully in the background. "
                 "On: preview each slide and fix cues/narration before rendering.")

    _ready = bool(topic.strip() and reference.strip())
    name_from = topic.strip()
    if st.button("🚀 Generate video", type="primary", disabled=not _ready):
        settings = dict(voice=voice, project_id=project_id, location=location,
                        tts_provider=tts_provider, eleven_voice_id=eleven_voice_id,
                        script=reference, model=model)
        if not review_first:
            # Fully automated: one Cloud Run Job generates + records, fire-and-forget.
            from deck.infra.job import dispatch_deck_job
            try:
                name = dispatch_deck_job(BUCKET, topic.strip(), settings,
                                         INFRA_PROJECT, REGION, JOB_NAME,
                                         name=make_name(name_from))
            except Exception as e:  # noqa: BLE001 - surface dispatch failures in the UI
                st.error(f"Could not start the job: {e}")
            else:
                # A toast doesn't survive st.rerun(); stash a flag for a persistent
                # banner and clear the inputs so it's clear the submit landed.
                st.session_state.submitted = name
                for k in ("topic", "reference", "steer", "script_original"):
                    st.session_state.pop(k, None)
                st.rerun()
        else:
            from deck.gen.generate import generate_scenes
            try:
                with st.status("Generating scenes — this runs on the service…",
                               expanded=True) as status:
                    def _p(msg):
                        status.update(label=msg)
                        status.write(f"• {msg}")
                    title, scenes = generate_scenes(
                        topic.strip(), reference,
                        project_id=project_id, location=location, model=model,
                        progress=_p)
                    status.update(label="Scenes ready — opening the editor",
                                  state="complete")
                _drop_scene_widgets(["cue_", "narr_"])  # clear any prior draft's edits
                st.session_state.draft = dict(
                    name=make_name(name_from), title=title, model=model,
                    scenes=scenes, settings=settings)
                st.session_state.active_slide = 0
                st.rerun()
            except Exception as e:  # noqa: BLE001 - surface generation failures in the UI
                st.error(f"Generation failed: {e}")
else:
    _review_ui()

# --- downloads ---------------------------------------------------------------
st.divider()
h1, h2 = st.columns([5, 1])
h1.subheader("Generated videos")
if h2.button("🔄", key="refresh", help="Refresh the list"):
    st.rerun()

if "page" not in st.session_state:
    st.session_state.page = 0

try:
    items, total = list_videos(_gcs(), page=st.session_state.page,
                               per_page=PER_PAGE, cap=MAX_VIDEOS)
except Exception as e:  # noqa: BLE001 - render the app even without GCS creds
    items, total = [], 0
    st.info(f"Could not list videos from GCS: {e}")

if not total:
    st.caption("No videos yet.")
else:
    pages = -(-min(total, MAX_VIDEOS) // PER_PAGE)  # ceil
    st.session_state.page = min(st.session_state.page, pages - 1)
    for it in items:
        label = f"**{it['when']}** — {it['topic']}" if it["when"] else f"**{it['topic']}**"
        c1, c2 = st.columns([4, 1])
        c1.markdown(label)
        if c2.button("Prepare ⬇", key=f"p_{it['name']}"):
            st.session_state.dl = it["name"]
        if st.session_state.get("dl") == it["name"]:
            st.download_button("Save video", _video_bytes(it["name"]),
                               file_name=it["name"], mime="video/mp4",
                               key=f"d_{it['name']}")

    col_prev, col_mid, col_next = st.columns([1, 2, 1])
    if col_prev.button("← Prev", disabled=st.session_state.page <= 0):
        st.session_state.page -= 1
        st.rerun()
    col_mid.markdown(
        f"<div style='text-align:center'>Page {st.session_state.page + 1} / {pages}"
        f"  ·  {min(total, MAX_VIDEOS)} videos</div>",
        unsafe_allow_html=True,
    )
    if col_next.button("Next →", disabled=st.session_state.page >= pages - 1):
        st.session_state.page += 1
        st.rerun()
