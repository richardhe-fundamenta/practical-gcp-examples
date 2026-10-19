# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard He
"""Thin Microsoft Graph client: drive aliases, file resolution, uploads, search."""

import re
import urllib.parse

import httpx

from . import office
from .audit import note, request_token

GRAPH = "https://graph.microsoft.com/v1.0"
TRANSPORT: httpx.AsyncBaseTransport | None = None  # tests swap in httpx.MockTransport
_ID = re.compile(r"^[A-Za-z0-9!._\-,:]{1,256}$")
_HOST_PATH_SITE = re.compile(r"^[A-Za-z0-9.\-]+\.sharepoint\.com:/[\w\-/ .]+$")
_STOP = {"a", "an", "and", "the", "of", "for", "in", "on", "to", "my", "is", "are", "with", "find",
         "file", "files", "document", "documents", "doc", "about", "show", "me", "what", "where"}


def validate_id(value: str, what: str = "id") -> str:
    v = (value or "").strip()
    if ".." in v or not _ID.match(v):
        raise ValueError(f"Invalid {what}: {value!r}")
    return v


def drive_path(drive: str | None) -> str:
    """'onedrive' -> /me/drive, 'sharepoint' -> root site default library, else a driveId."""
    alias = (drive or "onedrive").strip().lower()
    if alias in {"onedrive", "me", "my"}:
        return "/me/drive"
    if alias in {"sharepoint", "root", "site"}:
        return "/sites/root/drive"
    return f"/drives/{validate_id(drive, 'drive')}"


def site_path(site: str | None) -> str:
    """None -> root site; accepts a site id or 'contoso.sharepoint.com:/sites/team'."""
    if not site or site.strip().lower() == "root":
        return "/sites/root"
    s = site.strip().rstrip("/")
    if ":/" in s:
        if ".." in s or not _HOST_PATH_SITE.match(s):
            raise ValueError(f"Invalid site: {site!r}")
        return f"/sites/{urllib.parse.quote(s, safe=':/')}:"
    return f"/sites/{validate_id(s, 'site')}"


def list_path(site: str | None, list_name: str) -> str:
    name = office.sanitize_name(list_name)
    return f"{site_path(site)}/lists/{urllib.parse.quote(name, safe='')}"


def summarize(item: dict) -> dict:
    ref = item.get("parentReference") or item.get("remoteItem", {}).get("parentReference") or {}
    return {
        "name": item.get("name"),
        "item_id": item.get("id"),
        "drive_id": ref.get("driveId"),
        "folder": (ref.get("path") or "").split("root:", 1)[-1] or "/",
        "is_folder": "folder" in item,
        "size": item.get("size"),
        "web_url": item.get("webUrl"),
        "last_modified": item.get("lastModifiedDateTime"),
        "modified_by": (item.get("lastModifiedBy") or {}).get("user", {}).get("displayName"),
    }


def item_path(item: dict) -> str:
    return f"/drives/{item['parentReference']['driveId']}/items/{item['id']}"


class Graph:
    """Use as `async with Graph() as g:`; token comes from the current MCP request."""

    def __init__(self, token: str | None = None):
        self.http = httpx.AsyncClient(
            base_url=GRAPH, transport=TRANSPORT, timeout=60, follow_redirects=True,
            headers={"Authorization": f"Bearer {token or request_token()}"},
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.http.aclose()

    async def call(self, method: str, path: str, ok: tuple[int, ...] = (), **kw) -> httpx.Response:
        r = await self.http.request(method, path, **kw)
        if r.status_code >= 400 and r.status_code not in ok:
            r.raise_for_status()
        return r

    async def json(self, method: str, path: str, **kw) -> dict:
        r = await self.call(method, path, **kw)
        return r.json() if r.content else {}

    # ----- files -----

    async def item(self, drive: str | None, file_name: str | None = None, item_id: str | None = None,
                   folder_path: str = "", missing_ok: bool = False) -> dict | None:
        """Resolve item_id, or file_name (+folder_path) by path then by drive search. No name -> the folder."""
        dp, folder = drive_path(drive), office.sanitize_folder(folder_path)
        if item_id:
            it = await self.json("GET", f"{dp}/items/{validate_id(item_id, 'item_id')}")
        else:
            rel = "/".join(p for p in (folder, office.sanitize_name(file_name) if file_name else "") if p)
            r = await self.call("GET", f"{dp}/root:/{urllib.parse.quote(rel)}" if rel else f"{dp}/root", ok=(404,))
            it = r.json() if r.status_code == 200 else None
            if it is None and file_name:
                q = urllib.parse.quote(file_name.replace("'", "''"))
                r = await self.call("GET", f"{dp}/root/search(q='{q}')", ok=(400, 404))
                hits = r.json().get("value", []) if r.status_code == 200 else []
                it = next((h for h in hits if h.get("name", "").lower() == file_name.strip().lower()), None)
            if it is None:
                if missing_ok:
                    return None
                raise FileNotFoundError(f"'{rel}' was not found in drive '{drive}'.")
        note(drive_id=it.get("parentReference", {}).get("driveId"), item_id=it.get("id"), file_name=it.get("name"))
        return it

    async def download(self, item: dict, suffix: str = "/content") -> bytes:
        if (item.get("size") or 0) > office.MAX_BYTES:
            raise ValueError("File is larger than the 10 MB limit.")
        data = (await self.call("GET", item_path(item) + suffix)).content
        if len(data) > office.MAX_BYTES:
            raise ValueError("File is larger than the 10 MB limit.")
        return data

    async def upload_existing(self, item: dict, data: bytes) -> dict:
        """Overwrite in place (new version). If locked (423, open in Office Online) save a renamed copy."""
        r = await self.call("PUT", item_path(item) + "/content", ok=(423,), content=data)
        if r.status_code != 423:
            return {"file": summarize(r.json()), "lock_fallback_renamed": False}
        parent = f"/drives/{item['parentReference']['driveId']}/items/{item['parentReference']['id']}"
        new = await self.json("PUT", f"{parent}:/{urllib.parse.quote(item['name'])}:/content",
                              params={"@microsoft.graph.conflictBehavior": "rename"}, content=data)
        return {"file": summarize(new), "lock_fallback_renamed": True,
                "note": f"'{item['name']}' is open/locked, saved as '{new.get('name')}' instead."}

    async def upload_new(self, drive: str | None, folder: str, name: str, data: bytes,
                         conflict: str = "fail", parent: dict | None = None) -> dict:
        """Create a file by path (or inside `parent` item). conflict: fail | replace | rename."""
        name = office.sanitize_name(name)
        if parent:
            url = f"{item_path(parent)}:/{urllib.parse.quote(name)}:/content"
        else:
            rel = "/".join(p for p in (office.sanitize_folder(folder), name) if p)
            url = f"{drive_path(drive)}/root:/{urllib.parse.quote(rel)}:/content"
        r = await self.call("PUT", url, ok=(423,), params={"@microsoft.graph.conflictBehavior": conflict}, content=data)
        locked = r.status_code == 423
        if locked:
            r = await self.call("PUT", url, params={"@microsoft.graph.conflictBehavior": "rename"}, content=data)
        note(item_id=r.json().get("id"), file_name=r.json().get("name"))
        return {"file": summarize(r.json()), "lock_fallback_renamed": locked}

    # ----- search -----

    async def search(self, query: str, size: int = 10, drive: str | None = None) -> dict:
        """Microsoft Search (KQL); on error or zero hits fall back to a live scan (index lag)."""
        size = max(1, min(size, 25))
        try:
            if drive:
                q = urllib.parse.quote(query.replace("'", "''"))
                hits = [summarize(i) for i in (await self.json("GET", f"{drive_path(drive)}/root/search(q='{q}')",
                                                               params={"$top": size})).get("value", [])]
            else:
                body = {"requests": [{"entityTypes": ["driveItem"], "query": {"queryString": query}, "size": size}]}
                data = await self.json("POST", "/search/query", json=body)
                hits = [{**summarize(h.get("resource", {})), "snippet": h.get("summary")}
                        for v in data.get("value", []) for c in v.get("hitsContainers", []) for h in c.get("hits") or []]
        except httpx.HTTPStatusError:
            hits = []
        if hits:
            return {"source": "microsoft_search", "results": hits[:size]}
        return {"source": "live_scan", "note": "Search index returned nothing (new or lagging index); scanned drives directly.",
                "results": await self.live_scan(query, size, [drive] if drive else ["onedrive", "sharepoint"])}

    async def live_scan(self, query: str, size: int, drives: list[str], max_files: int = 60,
                        max_downloads: int = 25) -> list[dict]:
        """Match filenames and Office/text content in each drive's root plus one folder level."""
        words = [w for w in re.findall(r"[^\W_]{2,}", query.lower()) if w not in _STOP] or [query.lower().strip()]
        files: list[dict] = []
        for drive in drives:
            dp = drive_path(drive)
            r = await self.call("GET", f"{dp}/root/children", ok=(400, 403, 404), params={"$top": 200})
            for it in r.json().get("value", []) if r.status_code == 200 else []:
                if "folder" in it and len(files) < max_files:
                    sub = await self.call("GET", f"{dp}/items/{it['id']}/children", ok=(400, 403, 404), params={"$top": 200})
                    files += [s for s in (sub.json().get("value", []) if sub.status_code == 200 else []) if "file" in s]
                elif "file" in it:
                    files.append(it)
        files = list({f["id"]: f for f in files}.values())
        scored, downloads = [], 0
        for it in files[:max_files]:  # ponytail: shallow capped scan; deep trees need the search index
            name = it.get("name", "")
            score = sum(3 for w in words if w in name.lower())
            snippet = None
            if office.ext(name) in office.OOXML | office.TEXT and (it.get("size") or 0) <= 5 * 1024 * 1024 \
                    and downloads < max_downloads:
                downloads += 1
                try:
                    text = office.extract_text(name, await self.download(it), 200_000)
                    low = text.lower()
                    score += sum(1 for w in words if w in low)
                    pos = min((low.find(w) for w in words if w in low), default=-1)
                    snippet = text[max(0, pos - 100): pos + 200] if pos >= 0 else None
                except Exception:  # noqa: BLE001 - unreadable file just doesn't match on content
                    pass
            if score:
                scored.append((score, {**summarize(it), "snippet": snippet}))
        scored.sort(key=lambda s: -s[0])
        return [hit for _, hit in scored[:size]]
