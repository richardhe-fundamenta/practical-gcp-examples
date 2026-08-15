from deck.infra import job


class FakeGCS:
    def __init__(self):
        self.store = {}
        self.uploaded_files = {}

    def upload_json(self, obj, blob):
        self.store[blob] = obj

    def download_json(self, blob):
        return self.store[blob]

    def upload_file(self, local, blob):
        self.uploaded_files[blob] = local


def test_save_and_load_draft_roundtrips_and_filters_settings():
    gcs = FakeGCS()
    scenes = [{"narration": "Hi.", "base": "", "steps": []}]
    settings = {"voice": "Leda", "tts_provider": "elevenlabs",
                "eleven_voice_id": "vid", "project_id": "p", "location": "global",
                "script": "should be dropped"}
    job.save_draft(gcs, "20260101-000000-x-abcd.mp4", "T", scenes, settings)
    d = job.load_draft(gcs, "20260101-000000-x-abcd.mp4")
    assert d["title"] == "T" and d["scenes"] == scenes
    assert "script" not in d["settings"]
    assert d["settings"]["tts_provider"] == "elevenlabs"


def test_run_job_draft_records_without_generating(monkeypatch):
    gcs = FakeGCS()
    name = "20260101-000000-x-abcd.mp4"
    scenes = [{"narration": "Hi there.", "base": "",
               "steps": [{"cue": "Hi there", "draw": ""}]}]
    job.save_draft(gcs, name, "T", scenes,
                   {"voice": "Leda", "project_id": "p", "location": "global",
                    "tts_provider": "gemini", "eleven_voice_id": None})

    calls = {}

    def fake_record(html_path, timeline, out, **kw):
        calls["timeline"] = timeline
        calls["out"] = out
        with open(out, "w") as f:
            f.write("mp4")
        return out

    monkeypatch.setattr("deck.render.record.record_deck", fake_record)
    out = job.run_job(name, "bucket", source="draft", gcs=gcs)
    assert out == f"output/{name}"
    assert calls["timeline"][0]["cues"] == ["Hi there"]
    assert f"output/{name}" in gcs.uploaded_files
