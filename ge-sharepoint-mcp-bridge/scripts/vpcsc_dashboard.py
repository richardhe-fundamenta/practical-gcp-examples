#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard He
"""Local dashboard for VPC Service Controls dry-run violations.

Every page load reads cloudaudit.googleapis.com/policy entries with dryRun=true
through gcloud (your credentials), sorts each caller into a part of the
solution (runtime, delivery, people, unrelated), then groups by direction,
caller, source and service. One group is roughly one ingress/egress rule or
access-level entry you would need before enforcing the perimeter.

    python3 scripts/vpcsc_dashboard.py --project "$PROJECT_ID" [--project other]
    open http://localhost:8765/?hours=24
    python3 scripts/vpcsc_dashboard.py --self-test

Stdlib only, binds to 127.0.0.1.
"""

from __future__ import annotations

import argparse
import html
import json
import subprocess
import sys
import urllib.parse
from collections import Counter, defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

FILTER = 'logName="projects/{p}/logs/cloudaudit.googleapis.com%2Fpolicy" AND protoPayload.metadata.dryRun=true'

# key, title, colour, what it means, what to do. Display order.
PARTS = [
    ("runtime", "Solution runtime", "#c2410c",
     "Gemini Enterprise, the Agent Gateway and the MCP server's runtime account. These break the product when enforced.",
     "Ingress/egress rules for these service agents and the runtime service account."),
    ("delivery", "Build & deploy", "#b45309",
     "Cloud Build and the default compute account building and rolling out images.",
     "Run builds in a private pool inside the perimeter, or add an ingress rule for the build identity."),
    ("people", "People", "#0f766e",
     "Admins in the console or gcloud, and end users: Gemini Enterprise chat calls the API from the user's browser.",
     "An access level (corporate IP ranges or device policy) that covers admins and every Gemini Enterprise user."),
    ("other", "Unrelated", "#64748b",
     "Callers that aren't part of this deployment.",
     "Usually safe to ignore here; fix in the owning project if it matters."),
]
MAX_ROWS = 200  # ponytail: per-group cap keeps the page light; the Logs Explorer link shows the rest


def part_of(principal: str, runtime_sa_prefix: str) -> str:
    p = principal
    if "@gcp-sa-cloudbuild." in p or p.endswith(("@cloudbuild.gserviceaccount.com", "-compute@developer.gserviceaccount.com")):
        return "delivery"
    if "@gcp-sa-" in p or p.startswith(f"{runtime_sa_prefix}@") or p.endswith("@cloudservices.gserviceaccount.com"):
        return "runtime"
    if p and not p.endswith(".gserviceaccount.com"):
        return "people"
    return "other"


def fetch(project: str, hours: int, limit: int) -> list[dict]:
    out = subprocess.run(
        ["gcloud", "logging", "read", FILTER.format(p=project), f"--project={project}",
         f"--freshness={hours}h", f"--limit={limit}", "--format=json"],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out or "[]")


def flatten(entry: dict, runtime_sa_prefix: str) -> dict:
    pp = entry.get("protoPayload", {})
    md = pp.get("metadata", {})
    direction = "ingress" if md.get("ingressViolations") else "egress" if md.get("egressViolations") else "?"
    v = (md.get("ingressViolations") or md.get("egressViolations") or [{}])[0]
    who = pp.get("authenticationInfo", {}).get("principalEmail", "")
    ip = pp.get("requestMetadata", {}).get("callerIp", "")
    return {
        "project": entry.get("resource", {}).get("labels", {}).get("project_id", ""),
        "time": entry.get("timestamp", "")[:19].replace("T", " "),
        "direction": direction,
        "part": part_of(who, runtime_sa_prefix),
        "principal": who,
        "ip": ip,
        "source": v.get("source") or v.get("sourceType") or ip,
        "service": pp.get("serviceName", ""),
        "method": pp.get("methodName", ""),
        "target": v.get("targetResource") or pp.get("resourceName", ""),
        "permissions": v.get("targetResourcePermissions", []),
        "reason": md.get("violationReason", ""),
        "uid": md.get("vpcServiceControlsUniqueId", ""),
    }


def group(rows: list[dict]) -> list[dict]:
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        buckets[(r["direction"], r["principal"], r["source"], r["service"])].append(r)
    groups = []
    for (direction, principal, source, service), items in buckets.items():
        items.sort(key=lambda r: r["time"], reverse=True)
        groups.append({
            "direction": direction, "principal": principal, "source": source, "service": service,
            "items": items, "last": items[0]["time"],
            "methods": Counter(r["method"] for r in items).most_common(),
            "permissions": sorted({p for r in items for p in r["permissions"]}),
            "reasons": sorted({r["reason"] for r in items}),
        })
    return sorted(groups, key=lambda g: -len(g["items"]))


def log_link(r: dict) -> str:
    q = urllib.parse.quote(f'protoPayload.metadata.vpcServiceControlsUniqueId="{r["uid"]}"')
    return f"https://console.cloud.google.com/logs/query;query={q}?project={r['project']}"


def render(projects: list[str], hours: int, rows: list[dict], errors: list[str]) -> str:
    e = html.escape
    by_part: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_part[r["part"]].append(r)
    ours = [r for r in rows if r["part"] != "other"]

    sections = []
    for key, title, colour, meaning, fix in PARTS:
        items = by_part.get(key, [])
        groups_html = []
        for g in group(items):
            events = "".join(
                f"<tr><td>{e(r['time'])}</td><td>{e(r['project'])}</td><td>{e(r['method'])}</td>"
                f"<td>{e(r['target'])}</td><td>{e(r['ip'])}</td><td><a href=\"{e(log_link(r))}\" target=_blank>log</a></td></tr>"
                for r in g["items"][:MAX_ROWS])
            more = f"<p class=muted>First {MAX_ROWS} of {len(g['items'])}.</p>" if len(g["items"]) > MAX_ROWS else ""
            methods = ", ".join(f"{e(m)} ({n})" for m, n in g["methods"])
            groups_html.append(
                f"<details class=group><summary><b>{len(g['items'])}</b> {e(g['service'])} "
                f"&larr; {e(g['principal'] or '(unknown)')} <span class=muted>{e(g['direction'])}, "
                f"from {e(g['source'])}, last {e(g['last'])}</span></summary>"
                f"<p><b>Methods:</b> {methods}<br><b>Permissions:</b> {e(', '.join(g['permissions']) or '-')}"
                f"<br><b>Reason:</b> {e(', '.join(g['reasons']))}</p>"
                f"<table><tr><th>Time (UTC)</th><th>Project</th><th>Method</th><th>Target</th><th>Caller IP</th><th></th></tr>"
                f"{events}</table>{more}</details>")
        sections.append(
            f"<details class=part style=\"--c:{colour}\"{' data-empty' if not items else ''}><summary>"
            f"<span class=count>{len(items)}</span><span><b>{e(title)}</b><br>"
            f"<span class=muted>{len(groups_html)} caller/service groups</span></span></summary>"
            f"<p>{e(meaning)}<br><b>Fix:</b> {e(fix)}</p>{''.join(groups_html) or '<p class=muted>None.</p>'}</details>")

    windows = " ".join(f'<a href="?hours={h}">{h}h</a>' for h in (1, 6, 24, 168))
    errs = "".join(f"<p class=err>{e(x)}</p>" for x in errors)
    return f"""<!doctype html><meta charset=utf-8><title>VPC-SC dry run</title>
<style>
body{{font:14px/1.45 ui-sans-serif,system-ui,sans-serif;margin:28px auto;max-width:1300px;color:#0f172a;padding:0 16px}}
h1{{font-size:22px;margin:0 0 4px}}.muted{{color:#64748b;font-size:12px}}.err{{color:#b91c1c}}
.total{{background:#f1f5f9;border-radius:10px;padding:14px 18px;margin:16px 0}}.total b{{font-size:30px}}
.part{{border:1px solid #e2e8f0;border-top:4px solid var(--c);border-radius:10px;margin:12px 0;padding:10px 16px}}
.part[data-empty]{{opacity:.55}}.part>summary{{display:flex;gap:18px;align-items:center;cursor:pointer;list-style:none}}
.count{{font-size:32px;font-weight:700;color:var(--c);min-width:70px;text-align:right}}
.group{{border-top:1px dashed #e2e8f0;padding:6px 0}}.group>summary{{cursor:pointer}}
table{{border-collapse:collapse;width:100%;font-size:12px}}th,td{{text-align:left;padding:3px 8px;border-bottom:1px solid #e2e8f0;vertical-align:top}}
th{{background:#f8fafc}}a{{color:#0f766e}}
</style>
<h1>VPC Service Controls: dry-run violations</h1>
<p class=muted>{e(', '.join(projects))} &middot; last {hours}h ({windows}) &middot; reload to refresh</p>{errs}
<div class=total><b>{len(ours)}</b> violations from this solution
<span class=muted>&middot; {len(rows) - len(ours)} unrelated &middot; {len(rows)} total</span></div>
{''.join(sections)}"""


def serve(args: argparse.Namespace) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            hours = int(qs.get("hours", ["24"])[0])
            rows, errors = [], []
            for project in args.project:
                try:
                    rows += [flatten(x, args.runtime_sa_prefix) for x in fetch(project, hours, args.limit)]
                except subprocess.CalledProcessError as exc:
                    errors.append(f"{project}: {exc.stderr.strip()}")
            body = render(args.project, hours, rows, errors).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

    print(f"http://localhost:{args.port}/?hours=24  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


def self_test() -> None:
    entry = {
        "timestamp": "2026-10-18T09:15:00Z",
        "resource": {"labels": {"project_id": "p"}},
        "protoPayload": {
            "serviceName": "run.googleapis.com", "methodName": "Services.GetService",
            "authenticationInfo": {"principalEmail": "1-compute@developer.gserviceaccount.com"},
            "requestMetadata": {"callerIp": "203.0.113.7"},
            "metadata": {"violationReason": "NETWORK_NOT_IN_SAME_SERVICE_PERIMETER",
                         "ingressViolations": [{"source": "projects/9", "targetResource": "projects/1"}]},
        },
    }
    r = flatten(entry, "spmcp-runtime")
    assert (r["direction"], r["part"], r["source"]) == ("ingress", "delivery", "projects/9")
    assert part_of("service-1@gcp-sa-discoveryengine.iam.gserviceaccount.com", "spmcp-runtime") == "runtime"
    assert part_of("spmcp-runtime@p.iam.gserviceaccount.com", "spmcp-runtime") == "runtime"
    assert part_of("someone@example.com", "spmcp-runtime") == "people"
    assert part_of("batch-job@other.iam.gserviceaccount.com", "spmcp-runtime") == "other"
    assert len(group([r, dict(r, method="Services.ReplaceService")])) == 1
    page = render(["p"], 1, [dict(r, principal="<script>"), dict(r, part="other")], [])
    assert "<script>" not in page and "<b>1</b> violations from this solution" in page
    print("self-test ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        self_test()
        sys.exit()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", action="append", required=True, help="Repeat for each project in the perimeter.")
    ap.add_argument("--runtime-sa-prefix", default="spmcp-runtime", help="Account ID of the Cloud Run runtime SA.")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--limit", type=int, default=2000, help="Max log entries per project.")
    serve(ap.parse_args())
