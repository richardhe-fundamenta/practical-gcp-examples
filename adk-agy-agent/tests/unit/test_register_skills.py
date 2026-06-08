import base64
import io
import zipfile
from unittest.mock import MagicMock

from tools.register_skills import (
    build_skill_body,
    discover_skills,
    upsert_skill,
    zip_skill,
)


def _skill(tmp_path, name, frontmatter, extra=None):
    d = tmp_path / name
    (d / "scripts").mkdir(parents=True) if extra else d.mkdir()
    (d / "SKILL.md").write_text(frontmatter)
    if extra:
        (d / extra).write_text("print(1)")
    return d


def test_discover_skills_only_dirs_with_skill_md(tmp_path):
    _skill(tmp_path, "a", "---\nname: a\ndescription: A\n---\n")
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "notes.txt").write_text("x")  # no SKILL.md
    _skill(tmp_path, "c", "---\nname: c\ndescription: C\n---\n")
    assert [p.name for p in discover_skills(tmp_path)] == ["a", "c"]


def test_zip_skill_files_at_archive_root(tmp_path):
    d = _skill(tmp_path, "s", "hi", extra="scripts/run.py")
    names = zipfile.ZipFile(io.BytesIO(zip_skill(d))).namelist()
    assert "SKILL.md" in names
    assert "scripts/run.py" in names


def test_build_skill_body_from_frontmatter(tmp_path):
    d = _skill(tmp_path, "prime-factors",
               "---\nname: prime-factors\ndescription: Factor integers\n---\nbody")
    body = build_skill_body(d)
    assert body["displayName"] == "prime-factors"
    assert body["description"] == "Factor integers"
    raw = base64.b64decode(body["zippedFilesystem"])
    assert "SKILL.md" in zipfile.ZipFile(io.BytesIO(raw)).namelist()


def _resp(code, state=None):
    r = MagicMock(status_code=code)
    r.json.return_value = {"state": state} if state else {}
    return r


def test_upsert_skill_creates_when_missing():
    s = MagicMock()
    s.get.side_effect = [_resp(404), _resp(200, "ACTIVE")]  # check missing, then wait
    s.post.return_value = _resp(200)
    assert upsert_skill(s, "BASE", "prime-factors", {"displayName": "x"}) == "created"
    assert s.post.called and not s.patch.called
    _, kwargs = s.post.call_args
    assert kwargs["params"]["skillId"] == "prime-factors"


def test_upsert_skill_updates_when_exists():
    s = MagicMock()
    s.get.side_effect = [_resp(200), _resp(200, "ACTIVE")]  # check exists, then wait
    s.patch.return_value = _resp(200)
    assert upsert_skill(s, "BASE", "prime-factors", {"displayName": "x"}) == "updated"
    assert s.patch.called and not s.post.called
    _, kwargs = s.patch.call_args
    assert kwargs["params"]["updateMask"] == "display_name,description,zipped_filesystem"
