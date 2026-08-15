"""On-cloud validation that the render sandbox actually works.

Runs the REAL sandbox path (deck.render.record._run_browser) on a trivial 1-slide deck
to confirm two things that can only be checked on live Cloud Run:
  * nested Chromium launches inside the sandbox and renders the vendored (no-CDN)
    page to a non-empty webm, and
  * egress is truly blocked (a fetch inside the sandbox must fail).

Trigger without a full render:
  gcloud run jobs execute <job> --region <r> --update-env-vars DECK_PROBE=1
Then read the execution logs for the final JSON line. Diagnostic only — safe to
delete once the sandbox is confirmed healthy.
"""
import json
import os
import subprocess
import sys
import tempfile

from deck.render.record import _SANDBOX_BIN, _run_browser
from deck.visual.scene import build_html


def _egress_blocked():
    """True if an outbound request inside the sandbox fails (i.e. no egress)."""
    name = "egressprobe"
    code = "import urllib.request; urllib.request.urlopen('https://example.com', timeout=8)"
    subprocess.check_call([_SANDBOX_BIN, "run", name, "--detach", "--write",
                           "--", "/bin/sleep", "infinity"])
    try:
        r = subprocess.run([_SANDBOX_BIN, "exec", name, "--", sys.executable, "-c", code])
        return r.returncode != 0        # nonzero => the fetch failed => blocked (good)
    finally:
        # Bounded best-effort delete: --force graceful-stops first and hangs
        # ~120s on the sleep-infinity container; the instance teardown reaps it.
        try:
            subprocess.run([_SANDBOX_BIN, "delete", name, "--force"], timeout=10,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (subprocess.TimeoutExpired, OSError):
            pass


def run():
    assert os.environ.get("DECK_RENDER_SANDBOX") == "1", "DECK_RENDER_SANDBOX!=1"
    work = tempfile.mkdtemp(prefix="probe-")
    html, timeline = build_html("probe", [{
        "narration": "hi there",
        "base": "s.text(100,300,'Probe',{title:true,size:80});",
        "steps": [{"cue": "hi", "draw": "s.add(s.rc.circle(400,700,140,{stroke:s.color.white}));"}],
    }])
    html_path = os.path.join(work, "in.html")
    with open(html_path, "w") as f:
        f.write(html)
    schedule = {"W": 1080, "H": 1920, "init_ms": 50, "tail_ms": 50, "dwell_ms": 50,
                "slides": [{"cues": timeline[0]["cues"], "dur": 0.5,
                            "words": [{"w": "hi", "start": 0.1}]}]}
    webm = _run_browser(html_path, schedule, work)
    size = os.path.getsize(webm)
    blocked = _egress_blocked()
    ok = size > 0 and blocked
    print("PROBE " + json.dumps({"webm_bytes": size, "egress_blocked": blocked, "ok": ok}))
    if not ok:
        raise SystemExit(1)
