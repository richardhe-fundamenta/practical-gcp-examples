# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard He
"""MCP server exposing SharePoint Online and OneDrive to an AI assistant via Microsoft Graph."""

import os
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import uvicorn
from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from . import office
from .audit import BridgeError, audited, note
from .graph import Graph, drive_path, item_path, list_path, site_path, summarize, validate_id

READ = {"readOnlyHint": True}
WRITE = {"readOnlyHint": False}
Replacements = list[dict[str, str]] | dict[str, str] | None

mcp = FastMCP(
    name="sharepoint-mcp-bridge",
    instructions=(
        "Search, read, create and edit files in the user's SharePoint Online sites and OneDrive, with the "
        "user's own Microsoft 365 permissions. File tools take drive='onedrive' or 'sharepoint' (or a driveId) "
        "plus a plain file_name (optionally folder_path); the server resolves IDs itself, so do not look them "
        "up first. Edits preserve the original formatting. Each write needs user approval, so do all changes "
        "to one file in a single compound call (e.g. several replacements plus appended rows) instead of "
        "many small calls."
    ),
)


async def _text(g: Graph, item: dict, suffix: str = "/content", max_chars: int = 200_000) -> str:
    return office.extract_text(item["name"], await g.download(item, suffix), max_chars)


def _need_ext(item: dict, *exts: str) -> None:
    if office.ext(item["name"]) not in exts:
        raise ValueError(f"'{item['name']}' is not a {'/'.join(exts)} file.")


# ---------------- read tools ----------------

@mcp.tool(annotations=READ)
@audited("SEARCH")
async def search_documents(query: str, max_results: int = 10, drive: str | None = None) -> dict:
    """Search files by keywords, phrases or KQL (e.g. 'budget filetype:xlsx') across SharePoint and OneDrive.

    Falls back to a live scan of filenames and document text when the search index has no results yet
    (new tenants or files uploaded minutes ago). Optional drive ('onedrive', 'sharepoint' or a driveId)
    restricts the search to one drive. Returns name, item_id, drive_id, web_url and a snippet per hit.
    """
    note(query_chars=len(query))
    async with Graph() as g:
        return await g.search(query, max_results, drive)


@mcp.tool(annotations=READ)
@audited("SEARCH")
async def semantic_search(query: str, max_results: int = 10) -> dict:
    """Natural-language search that returns relevant text passages from SharePoint and OneDrive files.

    Uses the Microsoft 365 Copilot Retrieval API when the user has a Copilot licence; otherwise falls back
    to search_documents behaviour automatically. Use for questions like 'what is our travel policy for
    contractors?' rather than filename lookups.
    """
    note(query_chars=len(query))
    n = max(1, min(max_results, 25))
    async with Graph() as g:
        hits, failures = [], 0
        for source in ("sharePoint", "oneDriveBusiness"):
            r = await g.call("POST", "/copilot/retrieval", ok=(400, 401, 403, 404),
                             json={"queryString": query[:1500], "dataSource": source, "maximumNumberOfResults": n,
                                   "resourceMetadata": ["title", "author"]})
            if r.status_code >= 400:
                failures += 1
                continue
            hits += [{"source": source, "web_url": h.get("webUrl"), "metadata": h.get("resourceMetadata"),
                      "extracts": [e.get("text") for e in h.get("extracts", [])]}
                     for h in r.json().get("retrievalHits", [])]
        if failures == 2:
            return {"mode": "search_fallback", "fallback_reason": "Copilot Retrieval unavailable (no licence?).",
                    **await g.search(query, n)}
        return {"mode": "copilot_retrieval", "results": hits[: n * 2]}


@mcp.tool(annotations=READ)
@audited("DISCOVERY")
async def list_sites_and_drives(site_query: str = "*") -> dict:
    """List SharePoint sites the user can access (filtered by site_query, '*' for all), each site's
    document libraries (driveIds), and the user's own OneDrive."""
    async with Graph() as g:
        r = await g.call("GET", "/sites", ok=(400, 403, 404), params={"search": site_query or "*"})
        sites = r.json().get("value", []) if r.status_code == 200 else []
        if not sites:
            sites = [await g.json("GET", "/sites/root")]
        out = []
        for s in sites[:15]:
            d = await g.call("GET", f"/sites/{validate_id(s['id'], 'site')}/drives", ok=(403, 404),
                             params={"$select": "id,name,webUrl"})
            out.append({"site_id": s["id"], "name": s.get("displayName") or s.get("name"), "web_url": s.get("webUrl"),
                        "libraries": d.json().get("value", []) if d.status_code == 200 else []})
        me = await g.call("GET", "/me/drive", ok=(403, 404), params={"$select": "id,name,webUrl,driveType"})
        return {"sites": out, "onedrive": me.json() if me.status_code == 200 else None}


@mcp.tool(annotations=READ)
@audited("DISCOVERY")
async def list_folder(drive: str = "onedrive", folder_path: str = "") -> dict:
    """List files and subfolders in a folder. folder_path '' is the drive root, e.g. 'Projects/2026'.
    drive: 'onedrive' (user's OneDrive), 'sharepoint' (root site's default library) or a driveId.
    """
    async with Graph() as g:
        folder = await g.item(drive, folder_path=folder_path)
        items = (await g.json("GET", item_path(folder) + "/children", params={"$top": 200})).get("value", [])
        return {"folder": folder_path or "/", "count": len(items), "items": [summarize(i) for i in items]}


@mcp.tool(annotations=READ)
@audited("DISCOVERY")
async def list_recent_and_shared(limit: int = 20) -> dict:
    """List files the user opened or edited recently and files other people shared with them."""
    async with Graph() as g:
        out = {}
        for key, path in (("recent", "/me/drive/recent"), ("shared_with_me", "/me/drive/sharedWithMe")):
            r = await g.call("GET", path, ok=(400, 403, 404, 410), params={"$top": max(1, min(limit, 100))})
            out[key] = [summarize(i) for i in r.json().get("value", [])][:limit] if r.status_code == 200 else []
        return out


@mcp.tool(annotations=READ)
@audited("READ")
async def read_document(drive: str = "onedrive", file_name: str | None = None, item_id: str | None = None,
                        folder_path: str = "", max_chars: int = 60_000) -> dict:
    """Read the full text of a file: Word (headings, paragraphs, tables), Excel (every sheet as rows,
    formulas shown when no cached value), PowerPoint (per slide), PDF, Markdown, text, CSV or JSON (max 10 MB).

    Give file_name (plus folder_path if known) or item_id.
    drive: 'onedrive' (user's OneDrive), 'sharepoint' (root site's default library) or a driveId.
    """
    async with Graph() as g:
        it = await g.item(drive, file_name, item_id, folder_path)
        text = await _text(g, it, max_chars=max(1000, min(max_chars, 200_000)))
        return {"file": summarize(it), "content": text}


@mcp.tool(annotations=READ)
@audited("READ")
async def get_file_details(drive: str = "onedrive", file_name: str | None = None, item_id: str | None = None,
                           folder_path: str = "") -> dict:
    """Get a file's properties: size, link, created/modified by and when, SharePoint column values,
    sensitivity label (if any) and version history.
    drive: 'onedrive' (user's OneDrive), 'sharepoint' (root site's default library) or a driveId.
    """
    async with Graph() as g:
        it = await g.item(drive, file_name, item_id, folder_path)
        r = await g.call("GET", item_path(it), ok=(400,), params={"$expand": "listItem($expand=fields)"})
        full = r.json() if r.status_code == 200 else it
        v = await g.call("GET", item_path(it) + "/versions", ok=(400, 403, 404))
        fields = (full.get("listItem") or {}).get("fields") or {}
        return {
            "file": summarize(full),
            "created": full.get("createdDateTime"),
            "created_by": (full.get("createdBy") or {}).get("user", {}).get("displayName"),
            "mime_type": (full.get("file") or {}).get("mimeType"),
            "columns": {k: val for k, val in fields.items() if not k.startswith(("@", "_")) and k != "id"},
            "sensitivity_label": full.get("sensitivityLabel"),
            "versions": [{"version": x.get("id"), "modified": x.get("lastModifiedDateTime"), "size": x.get("size"),
                          "modified_by": (x.get("lastModifiedBy") or {}).get("user", {}).get("displayName")}
                         for x in (v.json().get("value", []) if v.status_code == 200 else [])],
        }


@mcp.tool(annotations=READ)
@audited("READ")
async def compare_versions(drive: str = "onedrive", file_name: str | None = None, item_id: str | None = None,
                           folder_path: str = "", version_a: str | None = None, version_b: str | None = None,
                           other_file_name: str | None = None, other_item_id: str | None = None,
                           other_folder_path: str = "") -> dict:
    """Show what changed, as a unified diff of the extracted text.

    Either two versions of one file (defaults: previous version vs current; version ids come from
    get_file_details) or, with other_file_name/other_item_id (same drive), two different files.
    drive: 'onedrive' (user's OneDrive), 'sharepoint' (root site's default library) or a driveId.
    """
    async with Graph() as g:
        it = await g.item(drive, file_name, item_id, folder_path)
        if other_file_name or other_item_id:
            other = await g.item(drive, other_file_name, other_item_id, other_folder_path)
            return office.diff(await _text(g, it), await _text(g, other), it["name"], other["name"])
        versions = [x["id"] for x in (await g.json("GET", item_path(it) + "/versions")).get("value", [])]
        if len(versions) < 2 and not (version_a and version_b):
            raise BridgeError("NO_PREVIOUS_VERSION", "This file has only one version; nothing to compare.")
        a = version_a or versions[1]
        b = version_b or versions[0]

        async def text(v: str) -> str:
            if versions and v == versions[0] or v == "current":
                return await _text(g, it)
            return await _text(g, it, f"/versions/{validate_id(v, 'version')}/content")

        return {"file": it["name"], "version_a": a, "version_b": b,
                **office.diff(await text(a), await text(b), f"v{a}", f"v{b}")}


@mcp.tool(annotations=READ)
@audited("READ")
async def get_permissions(drive: str = "onedrive", file_name: str | None = None, item_id: str | None = None,
                          folder_path: str = "") -> dict:
    """Who has access to a file or folder: users/groups, roles, sharing links and their scope
    (anonymous / organization / specific users) and whether access is inherited. Anonymous links are
    flagged as oversharing_risk. Leave file_name and item_id empty to check the folder_path folder.
    drive: 'onedrive' (user's OneDrive), 'sharepoint' (root site's default library) or a driveId.
    """
    async with Graph() as g:
        it = await g.item(drive, file_name, item_id, folder_path)
        perms = (await g.json("GET", item_path(it) + "/permissions")).get("value", [])
        out = []
        for p in perms:
            ids = [p.get("grantedToV2") or p.get("grantedTo") or {}] + (p.get("grantedToIdentitiesV2") or [])
            who = [x.get("displayName") or x.get("email") for i in ids for x in i.values() if isinstance(x, dict)]
            link = p.get("link") or {}
            out.append({"roles": p.get("roles"), "who": [w for w in who if w], "inherited": bool(p.get("inheritedFrom")),
                        "link_scope": link.get("scope"), "link_type": link.get("type"), "expires": p.get("expirationDateTime"),
                        "oversharing_risk": link.get("scope") == "anonymous"})
        return {"file": summarize(it), "permissions": out, "anonymous_links": sum(p["oversharing_risk"] for p in out)}


@mcp.tool(annotations=READ)
@audited("LIST")
async def query_list(list_name: str, site: str | None = None, filter: str | None = None, top: int = 50) -> dict:
    """Read items from a SharePoint list (SharePoint only, not OneDrive).

    site: omit for the root site, or a site id, or 'contoso.sharepoint.com:/sites/team'.
    filter: optional OData filter on columns, e.g. "fields/Status eq 'Open'".
    """
    params = {"$expand": "fields", "$top": max(1, min(top, 200))}
    headers = {}
    if filter:
        params["$filter"] = filter
        headers["Prefer"] = "HonorNonIndexedQueriesWarningMayFailRandomly"
    async with Graph() as g:
        items = (await g.json("GET", list_path(site, list_name) + "/items", params=params, headers=headers)).get("value", [])
        rows = [{"id": i.get("id"), "web_url": i.get("webUrl"),
                 **{k: v for k, v in (i.get("fields") or {}).items() if not k.startswith(("@", "_"))}} for i in items]
        return {"list": list_name, "count": len(rows), "items": rows}


# ---------------- write tools ----------------

@mcp.tool(annotations=WRITE)
@audited("WRITE")
async def create_file(file_name: str, drive: str = "onedrive", folder_path: str = "", content: str = "",
                      title: str | None = None, rows: list[list[Any]] | None = None,
                      slides: list[dict[str, Any]] | None = None, overwrite: bool = False) -> dict:
    """Create a new .docx, .xlsx, .pptx, .md, .txt, .csv or .json file and upload it.

    content: text (Word supports '# Heading' and '- bullet' lines; Excel/CSV accept CSV text).
    rows: table rows for Excel/CSV (or a table in Word). slides: PowerPoint slides as
    [{"title": ..., "bullets": [...]}]. overwrite=False fails if the file exists.
    drive: 'onedrive' (user's OneDrive), 'sharepoint' (root site's default library) or a driveId.
    """
    data = office.build_file(office.sanitize_name(file_name), content, title, rows, slides)
    async with Graph() as g:
        return await g.upload_new(drive, folder_path, file_name, data, "replace" if overwrite else "fail")


@mcp.tool(annotations=WRITE)
@audited("WRITE")
async def create_from_template(new_file_name: str, values: dict[str, str] | list[dict[str, str]],
                               drive: str = "onedrive", template_file_name: str | None = None,
                               template_item_id: str | None = None, folder_path: str = "",
                               target_folder: str = "") -> dict:
    """Create a new document from a .docx/.pptx/.xlsx template by filling {{placeholder}} fields.

    values: {"client_name": "Contoso"} or [{"key": ..., "value": ...}]. folder_path locates the template;
    target_folder is where the new file goes. Reports placeholders left unfilled.
    drive: 'onedrive' (user's OneDrive), 'sharepoint' (root site's default library) or a driveId.
    """
    vals = dict(office.pairs(values)) if isinstance(values, list) else values
    async with Graph() as g:
        tpl = await g.item(drive, template_file_name, template_item_id, folder_path)
        if office.ext(new_file_name) != office.ext(tpl["name"]):
            raise ValueError(f"new_file_name must keep the template's {office.ext(tpl['name'])} extension.")
        data, filled, unfilled = office.fill_template(tpl["name"], await g.download(tpl), vals)
        res = await g.upload_new(drive, target_folder, new_file_name, data)
        return {**res, "filled": filled, "unfilled_placeholders": unfilled}


@mcp.tool(annotations=WRITE)
@audited("WRITE")
async def edit_word_document(drive: str = "onedrive", file_name: str | None = None, item_id: str | None = None,
                             folder_path: str = "", replacements: Replacements = None,
                             find_text: str | None = None, replace_text: str | None = None,
                             append_heading: str | None = None, append_paragraphs: list[str] | None = None,
                             table_rows: list[list[Any]] | None = None, table_index: int = 0) -> dict:
    """Edit a Word .docx in place, keeping fonts, styles, headers and images. Saved as a new version.

    replacements: [{"find": "old", "replace": "new"}] or {"old": "new"} (body, tables, headers, footers).
    Optionally append a heading, paragraphs, and rows to table number table_index (0 = first).
    Put every change in one call.
    drive: 'onedrive' (user's OneDrive), 'sharepoint' (root site's default library) or a driveId.
    """
    async with Graph() as g:
        it = await g.item(drive, file_name, item_id, folder_path)
        _need_ext(it, ".docx")
        data, stats = office.edit_docx(await g.download(it), office.pairs(replacements, find_text, replace_text),
                                       append_heading, append_paragraphs, table_rows, table_index)
        return {**stats, **await g.upload_existing(it, data)}


@mcp.tool(annotations=WRITE)
@audited("WRITE")
async def edit_presentation(drive: str = "onedrive", file_name: str | None = None, item_id: str | None = None,
                            folder_path: str = "", replacements: Replacements = None,
                            find_text: str | None = None, replace_text: str | None = None,
                            add_slides: list[dict[str, Any]] | None = None) -> dict:
    """Edit a PowerPoint .pptx in place, keeping the theme and formatting. Saved as a new version.

    replacements: [{"find": "old", "replace": "new"}] or {"old": "new"} across all slides and tables.
    add_slides: [{"title": ..., "bullets": [...]}] appended at the end.
    drive: 'onedrive' (user's OneDrive), 'sharepoint' (root site's default library) or a driveId.
    """
    async with Graph() as g:
        it = await g.item(drive, file_name, item_id, folder_path)
        _need_ext(it, ".pptx")
        data, stats = office.edit_pptx(await g.download(it), office.pairs(replacements, find_text, replace_text),
                                       add_slides)
        return {**stats, **await g.upload_existing(it, data)}


@mcp.tool(annotations=WRITE)
@audited("WRITE")
async def update_workbook(drive: str = "onedrive", file_name: str | None = None, item_id: str | None = None,
                          folder_path: str = "", sheet: str | None = None, create_if_missing: bool = False,
                          initial_rows: list[list[Any]] | None = None, cell_updates: dict[str, Any] | None = None,
                          append_rows: list[list[Any]] | None = None, add_sheet: str | None = None,
                          add_column: dict[str, Any] | None = None, create_table: dict[str, str] | None = None) -> dict:
    """Change an Excel .xlsx workbook in one step, keeping existing formatting and formulas.

    sheet: worksheet to change (created if missing). create_if_missing: create the workbook (by file_name)
    if it does not exist, filled with initial_rows. cell_updates: {"B2": 42, "C5": "=SUM(C2:C4)"}.
    append_rows: rows added at the bottom. add_sheet: new worksheet name. add_column: {"header": ..,
    "values": [...]}. create_table: {"name": "Sales", "range": "A1:D10"} (range defaults to used area).
    All changes are applied together and uploaded once.
    drive: 'onedrive' (user's OneDrive), 'sharepoint' (root site's default library) or a driveId.
    """
    async with Graph() as g:
        it = await g.item(drive, file_name, item_id, folder_path, missing_ok=create_if_missing)
        if it:
            _need_ext(it, ".xlsx")
        elif office.ext(file_name or "") != ".xlsx":
            raise ValueError("file_name must end with .xlsx")
        data, stats = office.edit_xlsx(await g.download(it) if it else None, sheet, initial_rows, cell_updates,
                                       append_rows, add_sheet, add_column, create_table)
        up = await g.upload_existing(it, data) if it else await g.upload_new(drive, folder_path, file_name, data)
        return {**stats, **up, "created": it is None}


@mcp.tool(annotations=WRITE)
@audited("WRITE")
async def update_file_metadata(fields: dict[str, Any], drive: str = "sharepoint", file_name: str | None = None,
                               item_id: str | None = None, folder_path: str = "") -> dict:
    """Set SharePoint column values (metadata such as Status or Owner) on a file in a document library.
    SharePoint only: use the column's internal name.
    drive: 'onedrive' (user's OneDrive), 'sharepoint' (root site's default library) or a driveId.
    """
    async with Graph() as g:
        it = await g.item(drive, file_name, item_id, folder_path)
        note(fields=sorted(fields))
        return {"file": it["name"], "fields": await g.json("PATCH", item_path(it) + "/listItem/fields", json=fields)}


@mcp.tool(annotations=WRITE)
@audited("LIST")
async def upsert_list_item(list_name: str, fields: dict[str, Any], item_id: str | None = None,
                           site: str | None = None) -> dict:
    """Add a new item to a SharePoint list, or update item_id if given. SharePoint only.

    fields: column internal names to values, e.g. {"Title": "Kickoff", "Status": "Open"}.
    site: omit for the root site, or a site id, or 'contoso.sharepoint.com:/sites/team'.
    """
    base = list_path(site, list_name)
    note(fields=sorted(fields))
    async with Graph() as g:
        if item_id:
            res = await g.json("PATCH", f"{base}/items/{validate_id(item_id, 'item_id')}/fields", json=fields)
            return {"action": "updated", "item_id": item_id, "fields": res}
        res = await g.json("POST", f"{base}/items", json={"fields": fields})
        note(item_id=res.get("id"))
        return {"action": "created", "item_id": res.get("id"), "web_url": res.get("webUrl")}


@mcp.tool(annotations=WRITE)
@audited("WRITE")
async def organize_files(action: Literal["create_folder", "move", "copy", "rename"], drive: str = "onedrive",
                         file_name: str | None = None, item_id: str | None = None, folder_path: str = "",
                         new_name: str | None = None, destination_folder: str | None = None) -> dict:
    """Create folders and move, copy or rename files/folders within a drive.

    create_folder: makes new_name inside folder_path. move/copy: the file (file_name in folder_path, or
    item_id) goes to destination_folder ('' = root), optionally renamed to new_name. rename: needs new_name.
    Copy runs in the background; the result contains a monitor URL.
    drive: 'onedrive' (user's OneDrive), 'sharepoint' (root site's default library) or a driveId.
    """
    async with Graph() as g:
        if action == "create_folder":
            parent = await g.item(drive, folder_path=folder_path)
            res = await g.json("POST", item_path(parent) + "/children", json={
                "name": office.sanitize_name(new_name or ""), "folder": {}, "@microsoft.graph.conflictBehavior": "fail"})
            return {"folder": summarize(res)}
        it = await g.item(drive, file_name, item_id, folder_path)
        body: dict[str, Any] = {"name": office.sanitize_name(new_name)} if new_name else {}
        if action == "rename":
            if not new_name:
                raise ValueError("rename needs new_name.")
            return {"file": summarize(await g.json("PATCH", item_path(it), json=body))}
        if destination_folder is None:
            raise ValueError(f"{action} needs destination_folder ('' for the drive root).")
        dest = await g.item(drive, folder_path=destination_folder)
        body["parentReference"] = {"driveId": dest["parentReference"]["driveId"], "id": dest["id"]}
        note(destination=destination_folder)
        if action == "move":
            return {"file": summarize(await g.json("PATCH", item_path(it), json=body))}
        r = await g.call("POST", item_path(it) + "/copy", json=body)
        return {"copy_started": True, "monitor_url": r.headers.get("Location")}


@mcp.tool(annotations=WRITE)
@audited("WRITE")
async def export_to_pdf(drive: str = "onedrive", file_name: str | None = None, item_id: str | None = None,
                        folder_path: str = "", target_folder: str | None = None,
                        new_file_name: str | None = None) -> dict:
    """Convert a Word, PowerPoint or Excel file (and other supported types) to PDF and save it next to
    the original, or in target_folder. An existing PDF with the same name is not overwritten.
    drive: 'onedrive' (user's OneDrive), 'sharepoint' (root site's default library) or a driveId.
    """
    async with Graph() as g:
        it = await g.item(drive, file_name, item_id, folder_path)
        r = await g.call("GET", item_path(it) + "/content", params={"format": "pdf"})
        name = new_file_name or it["name"].rsplit(".", 1)[0] + ".pdf"
        if target_folder is not None:
            return await g.upload_new(drive, target_folder, name, r.content, "rename")
        parent = {"id": it["parentReference"]["id"], "parentReference": it["parentReference"]}
        return await g.upload_new(drive, "", name, r.content, "rename", parent=parent)


@mcp.tool(annotations=WRITE)
@audited("SHARING")
async def create_sharing_link(drive: str = "onedrive", file_name: str | None = None, item_id: str | None = None,
                              folder_path: str = "", link_type: Literal["view", "edit"] = "view",
                              scope: Literal["organization", "users", "anonymous"] = "organization",
                              recipients: list[str] | None = None, expiration_days: int | None = None) -> dict:
    """Share a file or folder: create a view/edit link for the organization, or with scope 'users' and
    recipients (email addresses) grant those people access and send them an invitation.
    Anonymous links are disabled unless the administrator enabled them.
    drive: 'onedrive' (user's OneDrive), 'sharepoint' (root site's default library) or a driveId.
    """
    note(link_scope=scope, recipients=len(recipients or []))
    if scope == "anonymous" and os.environ.get("ALLOW_ANONYMOUS_LINKS", "").lower() != "true":
        raise BridgeError("ANONYMOUS_LINKS_DISABLED", "Anonymous sharing links are disabled on this server.")
    if any(not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", r) for r in recipients or []):
        raise ValueError("recipients must be email addresses.")
    expires = (datetime.now(UTC) + timedelta(days=expiration_days)).strftime("%Y-%m-%dT%H:%M:%SZ") \
        if expiration_days else None
    async with Graph() as g:
        it = await g.item(drive, file_name, item_id, folder_path)
        if scope == "users" and recipients:
            body = {"recipients": [{"email": r} for r in recipients], "roles": ["write" if link_type == "edit" else "read"],
                    "requireSignIn": True, "sendInvitation": True}
            if expires:
                body["expirationDateTime"] = expires
            res = await g.json("POST", item_path(it) + "/invite", json=body)
            return {"file": it["name"], "granted": [p.get("roles") for p in res.get("value", [])],
                    "web_url": it.get("webUrl")}
        body = {"type": link_type, "scope": scope, **({"expirationDateTime": expires} if expires else {})}
        res = await g.json("POST", item_path(it) + "/createLink", json=body)
        return {"file": it["name"], "link": (res.get("link") or {}).get("webUrl"), "scope": scope, "expires": expires}


# ---------------- HTTP app ----------------

async def healthz(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


SECURITY_HEADERS = {"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Cache-Control": "no-store",
                    "Strict-Transport-Security": "max-age=63072000; includeSubDomains"}


async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.update(SECURITY_HEADERS)
    return resp


def create_app() -> Starlette:
    mcp_app = mcp.http_app(path="/mcp", transport="streamable-http")
    return Starlette(routes=[Route("/healthz", healthz), Mount("/", app=mcp_app)], lifespan=mcp_app.lifespan,
                     middleware=[Middleware(BaseHTTPMiddleware, dispatch=security_headers)])


app = create_app()


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))


if __name__ == "__main__":
    main()
