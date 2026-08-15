from datetime import datetime, timezone

from deck.infra.gcs import GCS
from deck.infra.job import (build_payload, dispatch_deck_job, list_videos, make_name,
                      parse_name, run_job, slugify)
from tests.test_gcs import FakeClient


def test_slugify():
    assert slugify("MCP vs Agent Skills!") == "mcp-vs-agent-skills"
    assert slugify("   ") == "video"


def test_make_name_is_sortable_and_parses_back():
    older = make_name("topic a", now=datetime(2026, 8, 8, 9, 0, 0, tzinfo=timezone.utc))
    newer = make_name("topic b", now=datetime(2026, 8, 8, 21, 35, 0, tzinfo=timezone.utc))
    assert newer.endswith(".mp4")
    # descending name-sort == newest-first (the whole point of the timestamp prefix)
    assert sorted([older, newer], reverse=True)[0] == newer
    when, topic = parse_name(newer)
    assert when == "2026-08-08 21:35"
    assert topic == "topic b"


def test_parse_name_falls_back_for_unstructured_names():
    when, topic = parse_name("legacy-clip.mp4")
    assert when == ""
    assert "legacy" in topic


class FakeRun:
    def __init__(self):
        self.requests = []

    def run_job(self, request):
        self.requests.append(request)
        return object()


def test_dispatch_uploads_payload_and_triggers_one_job():
    gcs = GCS("b", client=FakeClient())
    run_client = FakeRun()
    name = dispatch_deck_job(
        "b", "How reranking works", {"voice": "Leda", "script": "ref", "junk": 1},
        "proj", "us-central1", "script-to-video-render",
        now=datetime(2026, 8, 8, 21, 35, 0, tzinfo=timezone.utc),
        gcs=gcs, run_client=run_client)

    payload = gcs.download_json(f"jobs/{name[:-4]}.json")
    assert payload["title"] == "How reranking works"
    assert payload["settings"]["voice"] == "Leda"
    assert payload["settings"]["script"] == "ref"
    assert "junk" not in payload["settings"]  # only whitelisted keys travel

    assert len(run_client.requests) == 1
    req = run_client.requests[0]
    assert req.name.endswith("/jobs/script-to-video-render")
    env = req.overrides.container_overrides[0].env
    assert env[0].name == "DECK_NAME" and env[0].value == name


def test_build_payload_whitelists_settings():
    p = build_payload("x.mp4", "topic", {"voice": "Puck", "secret": "no"})
    assert p == {"name": "x.mp4", "title": "topic", "settings": {"voice": "Puck"}}


def test_list_videos_paginates_newest_first():
    gcs = GCS("b", client=FakeClient())
    names = [make_name(f"topic {i}", now=datetime(2026, 8, 8, i, 0, 0, tzinfo=timezone.utc))
             for i in range(1, 13)]  # 12 videos, increasing timestamps
    for n in names:
        gcs.upload_file_bytes = None
        gcs.bucket.blob(f"output/{n}").upload_from_string("v")
    gcs.bucket.blob("jobs/ignore.json").upload_from_string("{}")  # not an mp4/output

    p0, total = list_videos(gcs, page=0, per_page=10)
    assert total == 12
    assert len(p0) == 10
    assert p0[0]["name"] == names[-1]  # newest (hour 12) first

    p1, total = list_videos(gcs, page=1, per_page=10)
    assert total == 12
    assert len(p1) == 2


def test_list_videos_orders_by_creation_time_not_name():
    gcs = GCS("b", client=FakeClient())
    # timestamped name sorting HIGH lexically, uploaded first (older)
    gcs.bucket.blob("output/20260808-235959-zeta-9999.mp4").upload_from_string("v")
    # legacy UUID name sorting LOW lexically, uploaded last (newest)
    gcs.bucket.blob("output/03968140-035b-legacy.mp4").upload_from_string("v")

    items, total = list_videos(gcs, page=0, per_page=10)
    assert total == 2
    assert items[0]["name"] == "03968140-035b-legacy.mp4"  # newest by time wins


def test_run_job_renders_and_uploads(monkeypatch):
    gcs = GCS("b", client=FakeClient())
    name = "20260808-213500-topic-abcd.mp4"
    gcs.upload_json({"title": "hi", "settings": {"script": "One.", "mock": True}},
                    f"jobs/{name[:-4]}.json")

    calls = {}

    def fake_run(title, script, out=None, **kw):
        calls["title"], calls["script"], calls["kw"] = title, script, kw
        with open(out, "wb") as f:
            f.write(b"VIDEO")
        return out

    monkeypatch.setattr("deck.gen.generate.run", fake_run)
    blob = run_job(name, "b", gcs=gcs)

    assert blob == f"output/{name}"
    assert gcs.download_bytes(f"output/{name}") == b"VIDEO"
    assert calls["title"] == "hi" and calls["script"] == "One."
    assert calls["kw"]["mock"] is True
