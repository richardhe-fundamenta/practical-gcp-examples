"""Background render for the deck (chalkboard) pipeline on Cloud Run Jobs.

Flow: the GUI calls ``dispatch_deck_job(...)`` — it picks a distinct,
timestamped name, uploads the render payload to ``jobs/<id>.json``, and triggers
one Cloud Run Job execution (fire-and-forget). The Job container runs
``python -m deck.infra.job`` which reads ``DECK_NAME`` + ``GCS_BUCKET`` from the env,
renders via ``deck.gen.generate.run``, and uploads the mp4 to ``output/<name>``.

Output naming: ``<YYYYMMDD-HHMMSS>-<topic-slug>-<rand>.mp4``. The leading UTC
timestamp makes the name self-describing (when + what); the downloads list
orders by GCS creation time so legacy uploads still sort correctly.
"""
import os
import re
import sys
import uuid
from datetime import datetime, timezone

from deck.infra.gcs import GCS

# Settings the GUI may override; everything else uses deck.gen.generate.run defaults.
_SETTING_KEYS = ("script", "voice", "project_id", "location", "model",
                 "mock", "tts_provider", "eleven_voice_id")

# The subset a record-only job needs (generation knobs are already spent).
_RECORD_SETTING_KEYS = ("voice", "project_id", "location", "tts_provider",
                        "eleven_voice_id")


def _job_id(name):
    return name[:-4] if name.endswith(".mp4") else name


def save_draft(gcs, name, title, scenes, settings):
    """Persist an editable draft at drafts/<id>.json for the record-only job."""
    gcs.upload_json({
        "name": name, "title": title, "scenes": scenes,
        "settings": {k: settings[k] for k in _RECORD_SETTING_KEYS
                     if k in settings},
    }, f"drafts/{_job_id(name)}.json")


def load_draft(gcs, name):
    return gcs.download_json(f"drafts/{_job_id(name)}.json")


def dispatch_draft_job(bucket_name, name, infra_project, region, job_name,
                       run_client=None):
    """Trigger the render job to RECORD an already-saved draft (no generation)."""
    from google.cloud import run_v2
    run_client = run_client or run_v2.JobsClient()
    request = run_v2.RunJobRequest(
        name=f"projects/{infra_project}/locations/{region}/jobs/{job_name}",
        overrides=run_v2.RunJobRequest.Overrides(
            container_overrides=[
                run_v2.RunJobRequest.Overrides.ContainerOverride(
                    env=[run_v2.EnvVar(name="DECK_NAME", value=name),
                         run_v2.EnvVar(name="DECK_SOURCE", value="draft")]
                )
            ]
        ),
    )
    run_client.run_job(request=request)
    return name


def slugify(text: str, maxlen: int = 40) -> str:
    """Lowercase, keep alnum, collapse the rest to single dashes."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:maxlen].strip("-") or "video"


def make_name(topic: str, now=None) -> str:
    """Distinct, sortable, self-describing mp4 name (see module docstring)."""
    now = now or datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%d-%H%M%S")
    return f"{ts}-{slugify(topic)}-{uuid.uuid4().hex[:4]}.mp4"


def parse_name(name: str):
    """(display_time, topic) parsed back out of a make_name() string.

    Returns ("2026-08-08 21:35", "mcp vs agent skills") — falls back to the raw
    stem for anything that doesn't match the pattern (e.g. legacy uploads).
    """
    stem = name[:-4] if name.endswith(".mp4") else name
    m = re.match(r"^(\d{8})-(\d{6})-(.+)-[0-9a-f]{4}$", stem)
    if not m:
        return "", stem.replace("-", " ")
    d, t, slug = m.groups()
    when = f"{d[:4]}-{d[4:6]}-{d[6:]} {t[:2]}:{t[2:4]}"
    return when, slug.replace("-", " ")


def build_payload(name: str, title: str, settings: dict) -> dict:
    return {
        "name": name,
        "title": title,
        "settings": {k: settings[k] for k in _SETTING_KEYS if k in settings},
    }


def dispatch_deck_job(bucket_name, title, settings, infra_project, region,
                      job_name, name=None, now=None, gcs=None, run_client=None):
    """Upload the payload and trigger one Cloud Run Job execution. Returns the name."""
    name = name or make_name(title, now=now)
    job_id = name[:-4]
    gcs = gcs or GCS(bucket_name)
    gcs.upload_json(build_payload(name, title, settings), f"jobs/{job_id}.json")

    from google.cloud import run_v2
    run_client = run_client or run_v2.JobsClient()
    request = run_v2.RunJobRequest(
        name=f"projects/{infra_project}/locations/{region}/jobs/{job_name}",
        overrides=run_v2.RunJobRequest.Overrides(
            container_overrides=[
                run_v2.RunJobRequest.Overrides.ContainerOverride(
                    env=[run_v2.EnvVar(name="DECK_NAME", value=name)]
                )
            ]
        ),
    )
    run_client.run_job(request=request)
    return name


def run_job(name, bucket, source="prompt", gcs=None):
    """Worker body: produce the mp4 for `name` and upload it to output/.

    source="draft": download drafts/<id>.json, compile, and RECORD only.
    source="prompt": the original path — download jobs/<id>.json and compose+record.
    """
    gcs = gcs or GCS(bucket)
    local = f"/tmp/{name}"
    if source == "draft":
        from deck.gen.generate import compile_deck
        from deck.render.record import record_deck
        draft = load_draft(gcs, name)
        html, timeline = compile_deck(draft["title"], draft["scenes"])
        html_path = f"/tmp/{_job_id(name)}.html"
        with open(html_path, "w") as f:
            f.write(html)
        s = draft.get("settings", {})
        record_deck(html_path, timeline, local,
                    project_id=s.get("project_id", "mock-project"),
                    location=s.get("location", "global"),
                    voice=s.get("voice", "Leda"),
                    tts_provider=s.get("tts_provider", "gemini"),
                    eleven_voice_id=s.get("eleven_voice_id"))
    else:
        from deck.gen.generate import run
        payload = gcs.download_json(f"jobs/{_job_id(name)}.json")
        s = dict(payload.get("settings", {}))
        run(payload["title"], s.pop("script", ""), out=local, **s)
    gcs.upload_file(local, f"output/{name}")
    return f"output/{name}"


def list_videos(gcs, page=0, per_page=10, cap=100):
    """(items, total) of rendered mp4s, newest-first, capped. Each item is a
    dict: {name, when, topic}. Sorted by GCS creation time so legacy
    (non-timestamped) uploads still order correctly alongside timestamped ones."""
    vids = sorted(
        ((n[len("output/"):], t) for n, t in gcs.list_blobs_meta("output/")
         if n.endswith(".mp4")),
        key=lambda nt: nt[1], reverse=True,
    )
    names = [n for n, _ in vids][:cap]
    total = len(names)
    start = page * per_page
    items = [dict(name=n, **dict(zip(("when", "topic"), parse_name(n))))
             for n in names[start:start + per_page]]
    return items, total


if __name__ == "__main__":
    # Cloud Run Job entrypoint: `python -m deck.infra.job`.
    if os.environ.get("DECK_PROBE") == "1":     # sandbox health check, not a render
        from deck.infra.sandbox_probe import run as probe
        probe()
        raise SystemExit(0)
    name = os.environ.get("DECK_NAME") or (sys.argv[1] if len(sys.argv) > 1 else "")
    bucket = os.environ["GCS_BUCKET"]
    source = os.environ.get("DECK_SOURCE", "prompt")
    if not name:
        raise SystemExit("DECK_NAME env (or argv[1]) required")
    print(run_job(name, bucket, source=source))
