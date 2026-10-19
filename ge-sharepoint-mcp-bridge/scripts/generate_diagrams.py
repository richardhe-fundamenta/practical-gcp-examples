# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard He
# /// script
# requires-python = ">=3.12"
# dependencies = ["google-genai"]
# ///
"""Generate the architecture diagrams in docs/ with Gemini 3 Pro Image on Vertex AI.

The prompts below are the diagram source. Regenerate with:

    uv run scripts/generate_diagrams.py --project <PROJECT_ID> [--only why|overview|network|solution]

Image models are not deterministic: inspect the output and, if a label or arrow is off,
fix it in place with --edit "instruction" (sends the current PNG back with the spec).

Auth uses Application Default Credentials (gcloud auth application-default login).
"""

import argparse
from pathlib import Path

from google import genai
from google.genai import types

MODEL = "gemini-3-pro-image"  # Nano Banana Pro (GA id on Vertex AI)
DOCS = Path(__file__).resolve().parent.parent / "docs"

STYLE = """
STYLE (apply exactly):
- Clean, flat, professional look, landscape 16:9, pure white background. No header or caption text other than the title/subtitle given.
- Crisp modern sans-serif font (like Inter, normal width, never condensed), dark slate text (#1F2A37). Every label must be spelled
  EXACTLY as written in quotes below. Do not add any other text, product logos, trademarks or watermarks.
- Zones are full-width HORIZONTAL BANDS stacked TOP TO BOTTOM, each with a very light tinted fill,
  rounded corners, and the zone name (exactly the quoted name, nothing more) in bold small caps at the
  top-left of the band.
- Palette: deep teal (#0F766E) for the main request path arrows and step badges; slate gray (#475569)
  for box outlines and secondary arrows; warm amber (#D97706) for security-control pills
  (pale amber fill #FEF3C7, amber outline and text). Band tints: very pale slate, pale teal, pale stone.
- Component boxes: white, rounded rectangles, thin slate outline, bold name, small gray subtitle,
  with a tiny MONOCHROME slate outline glyph at the left of every box (generic shapes only: person, gear,
  shield, cloud, database, arrow). Never use colored or vendor product icons or logos. In particular:
  "SharePoint Online" = plain document outline, "OneDrive" = plain folder outline, "Microsoft Entra ID" = key
  outline, "Microsoft Graph API" = three connected dots. No letters inside glyphs, no filled colored shapes.
- Title in bold, dark slate; subtitle (if any) regular weight, gray.
- Numbered step badges (only where a diagram asks for them): small solid deep-teal circles with white numbers.
- Arrows: straight or orthogonal, never crossing labels, clear arrowheads.
- A compact legend in a single row at the bottom.
"""

NETWORK = STYLE + """
DIAGRAM: network request flow.

Title at top (bold, large): "Private request path: Gemini Enterprise to SharePoint via Cloud Run"
Subtitle under it (gray, smaller): "MCP traffic stays on Google's private network until the server calls Microsoft Graph as the signed-in user"

Four horizontal bands, top to bottom:

Band "USER": box "Business user" (subtitle "Gemini Enterprise web app") and box "Microsoft Entra ID" (subtitle "OAuth sign-in").

Band "GOOGLE-MANAGED": box "Gemini Enterprise" (subtitle "custom MCP connector") and box
"Agent Gateway" (subtitle "egress, governed"). Under Agent Gateway two amber pills: "AuthZ policy: ALLOW" and "DNS peering: run.app".

Band "YOUR GOOGLE CLOUD PROJECT — PRIVATE VPC": boxes left to right: "PSC network attachment",
"PSC endpoint" (subtitle "Google APIs · 10.250.0.10") with small caption "Private DNS: *.run.app → PSC endpoint",
a larger box "Cloud Run: MCP server" (no subtitle) containing amber pills "Ingress: internal only" and
"IAM: invoker required" and one bullet "• 20 SharePoint & OneDrive tools", then "Cloud NAT" (subtitle "outbound only").
Also in this band, on a lower row: "Secret Manager" (subtitle "Entra app credentials (setup only)") placed at the far
left with NO arrows touching it, and "Cloud Logging → BigQuery" (subtitle "audit trail") placed directly BELOW
"Cloud Run: MCP server".

Band "MICROSOFT 365", at the right side, three boxes in a row in THIS order: "SharePoint Online", then
"Microsoft Graph API" (subtitle "graph.microsoft.com") in the MIDDLE, then "OneDrive".

ARROWS AND STEPS (each step badge exactly once, numbers 1 to 7):
1 — dashed slate arrow from "Business user" to "Microsoft Entra ID", label "Sign in on first tool call (OAuth)"
    (its step badge is deep teal like all the others);
    an amber pill "Delegated user token" near "Gemini Enterprise".
2 — teal arrow from "Business user" down to "Gemini Enterprise", label "Prompt → MCP tool call".
3 — teal arrow from "Gemini Enterprise" to "Agent Gateway", label "Google ID token + user's Entra token".
4 — teal arrow from "Agent Gateway" down into "PSC network attachment", label "Private connection (no internet)".
5 — teal arrows "PSC network attachment" → "PSC endpoint" → "Cloud Run: MCP server", label "Resolves *.run.app privately".
6 — teal arrow "Cloud Run: MCP server" → "Cloud NAT" → down to "Microsoft Graph API", label "Graph calls as the signed-in user"
    (the 6 badge appears ONCE only, next to the Cloud Run → Cloud NAT arrow);
    then "Microsoft Graph API" fans out with TWO short slate arrows: one pointing LEFT to "SharePoint Online" and
    one pointing RIGHT to "OneDrive".
Every step number 1–7 appears exactly once.
7 — short vertical slate arrow straight DOWN from the bottom of "Cloud Run: MCP server" to "Cloud Logging → BigQuery",
    label "Audit event per tool call". Cloud NAT has exactly one outgoing arrow (to Microsoft Graph API).

Legend (bottom row): teal arrow "Request path", dashed arrow "Sign-in", amber pill "Security control", teal circle "#" "Step number".
"""

SOLUTION = STYLE + """
DIAGRAM: solution architecture overview. IMPORTANT: NO numbered step badges and NO numbers anywhere in this diagram.

Title at top (bold, large): "SharePoint MCP Bridge for Gemini Enterprise: solution architecture"

Three horizontal bands, top to bottom:

Band "USERS": box "Business user" (no subtitle) at the far left, and box "Gemini Enterprise" (subtitle "web app") placed
directly ABOVE the "AI & agents" card so its arrow goes straight down into the connector.

Band "GOOGLE CLOUD" (largest band) containing small labeled sub-group cards in TWO rows.
Top row, left to right (this is the request path):
- "AI & agents": "Gemini Enterprise" (subtitle "custom MCP connector · human approval for edits") → "Agent Gateway" (subtitle "governed egress").
- "Private networking": "Private Service Connect", and "Cloud DNS" (subtitle "private zone") stacked
  BELOW it inside the same card, off the path, with no arrows.
- "Serverless runtime": "Cloud Run" (subtitle "MCP server · 20 tools: search, read, compare, edit, share").
- "Outbound": "Cloud NAT" (at the far right). Keep the area directly BELOW "Cloud NAT" EMPTY all the way down to
  the Microsoft 365 band (a clear vertical channel for its arrow); the bottom-row cards end left of that channel.
Bottom row, left to right:
- "Security": "Secret Manager", "IAM", "VPC Service Controls" (subtitle "dry run").
- "Delivery": "Terraform", "Cloud Build", "Artifact Registry".
- "Observability & audit" (directly below "Serverless runtime"): "Cloud Logging" (subtitle "audit bucket") → "BigQuery"
  side by side, and "Cloud Trace" beside them.

Band "MICROSOFT 365", left to right: "Microsoft Entra ID" (far left, under Business user), then at the right side
three boxes in THIS order: "SharePoint Online", "Microsoft Graph API" (in the middle), "OneDrive".

ARROWS — draw EXACTLY these arrows and no others:
Teal solid "Prompt path":
 a. "Business user" → "Gemini Enterprise" web app (short arrow, boxes close together)
 b. "Gemini Enterprise" web app → down to "Gemini Enterprise" connector
 c. "Gemini Enterprise" connector → "Agent Gateway"
 d. "Agent Gateway" → "Private Service Connect"
 e. "Private Service Connect" → "Cloud Run"
 f. "Cloud Run" → "Cloud NAT"
 g. "Cloud NAT" → straight down through the empty channel to "Microsoft Graph API" (passes through no other box)
 h. "Microsoft Graph API" → LEFT to "SharePoint Online"
 i. "Microsoft Graph API" → RIGHT to "OneDrive"
Slate dashed "Sign-in path":
 j. "Business user" → down to "Microsoft Entra ID", label "OAuth sign-in (first tool call)". This dashed line runs
    straight down the far-left margin, OUTSIDE all Google Cloud cards, touching no other box.
Slate dotted "Config path":
 k. "Secret Manager" → "Gemini Enterprise" connector, label "connector setup"
 l. "Cloud Build" → "Artifact Registry" (short horizontal arrow inside the Delivery card)
 m. ONE arrow "Artifact Registry" → "Cloud Run", label "build & deploy" (Cloud Build itself has no arrow to Cloud Run)
 ("Terraform" has no arrow, only the caption "provisions all resources" under it. "Cloud DNS", "IAM" and
 "VPC Service Controls" have no arrows.)
Thin amber "Audit / traces":
 n. "Cloud Run" → "Cloud Logging", label "audit events"
 o. ONE short arrow "Cloud Logging" → "BigQuery"
 p. "Cloud Run" → "Cloud Trace", label "traces" (Cloud Logging and Cloud Trace are not connected)

Legend (bottom row): "Prompt path" (solid teal), "Sign-in path" (dashed), "Config path" (dotted), "Audit / traces" (thin amber).
"""

OVERVIEW = STYLE + """
DIAGRAM: high-level overview for someone seeing the project for the first time. It must read in five seconds.
OVERRIDES for this diagram only: NO horizontal bands, NO legend, NO step badges, NO numbers. Lots of white space.
Layout is ONE left-to-right flow of four columns, vertically centred, connected by thick deep-teal arrows.

Title at top (bold, large): "SharePoint MCP Bridge for Gemini Enterprise"
Subtitle under it (gray, smaller): "Gemini Enterprise works on your SharePoint and OneDrive files as the signed-in user"

Column 1 (narrow): a box "Gemini Enterprise" (subtitle "chat + custom MCP connector") with a small person glyph box
"Business user" directly ABOVE it and a short slate arrow from "Business user" down into it.

Column 2 (the WIDEST column, about half the canvas, the visual centrepiece): one large rounded box with a pale teal fill,
bold heading "MCP server on Cloud Run" and gray subheading "wraps Microsoft Graph as 20 tools". Inside it, a 2 x 2 grid of
four white cards. Each card has a bold heading, a small pill on the right of the heading, and exactly five tool names
listed below in a monospace font, one per line, spelled EXACTLY as written:
- Card "Find" (pill "runs instantly", pale teal): "search_documents", "semantic_search", "list_sites_and_drives",
  "list_folder", "list_recent_and_shared"
- Card "Read & review" (pill "runs instantly", pale teal): "read_document", "get_file_details", "compare_versions",
  "get_permissions", "query_list"
- Card "Create & edit" (pill "asks for approval", pale amber): "create_file", "create_from_template",
  "edit_word_document", "edit_presentation", "update_workbook"
- Card "Organise & share" (pill "asks for approval", pale amber): "update_file_metadata", "upsert_list_item",
  "organize_files", "export_to_pdf", "create_sharing_link"
Top row of the grid: "Find", "Read & review". Bottom row: "Create & edit", "Organise & share".
Below the grid, inside the large box, one row of three small amber pills: "Private: no public endpoint",
"User's own permissions", "Every call audited".

Column 3 (narrow): box "Microsoft Graph API" (subtitle "graph.microsoft.com").

Column 4 (narrow): two boxes stacked: "SharePoint Online" (subtitle "sites, libraries, lists") on top and
"OneDrive" (subtitle "personal files") below.

ARROWS — exactly these, thick deep teal, each with a short label above it:
- "Gemini Enterprise" → large MCP server box, label "MCP tool calls"
- large MCP server box → "Microsoft Graph API", label "as the signed-in user"
- "Microsoft Graph API" → "SharePoint Online" and "Microsoft Graph API" → "OneDrive" (two short arrows, no labels)
"""

WHY = STYLE + """
DIAGRAM: why this project exists, a before / after comparison. It must read in five seconds.
OVERRIDES for this diagram only: NO horizontal bands, NO legend, NO step badges, NO numbers. Lots of white space.

Title at top (bold, large): "Why a SharePoint bridge for Gemini Enterprise?"
Subtitle under it (gray, smaller): "For teams whose files and everyday apps are in Microsoft 365"

Two equal side-by-side panels with rounded corners, separated by a large deep-teal right-pointing arrow in the middle.

LEFT panel, very pale stone fill, heading "Today: switching between apps" (bold), small gray subheading
"Gemini Enterprise cannot see or change the files".
Inside: a "Business user" person glyph in the centre-left. On the left a box "Gemini Enterprise". On the right a vertical
stack of four small boxes: "SharePoint", "Word", "Excel", "PowerPoint" (each with a plain monochrome document glyph).
Between the user and both sides, several thin slate dashed arrows going BACK AND FORTH (bidirectional, slightly
tangled looking but tidy), with three small gray labels on them: "copy & paste", "download & re-upload",
"check access by hand".
At the bottom of the left panel, three task rows, each a small slate outline pill with a gray caption:
- "Legal" — "compare contract drafts, draft an NDA"
- "Finance" — "update the close tracker, write the board report"
- "Network operations" — "review a change, record the approval"

RIGHT panel, pale teal fill, heading "With the bridge: one conversation" (bold), small gray subheading
"Gemini Enterprise works on the files directly, as the signed-in user".
Inside: the same "Business user" glyph with ONE short solid teal arrow to a box "Gemini Enterprise", then ONE solid
teal arrow to a box "SharePoint & OneDrive" (subtitle "Word · Excel · PowerPoint · lists"). The arrow between them has a
small label "MCP bridge".
At the bottom of the right panel, the same three task rows, each with a small teal check glyph instead of the pill:
- "Legal" — "changes summarised, NDA drafted and shared"
- "Finance" — "tracker updated, commentary written, PDF filed"
- "Network operations" — "past incidents found, change approved"
Below them one row of three small amber pills: "Approval before every change", "User's own permissions",
"Every action audited".
"""

DIAGRAMS = {
    "why": (WHY, "why.png"),
    "overview": (OVERVIEW, "overview.png"),
    "network": (NETWORK, "network_flow.png"),
    "solution": (SOLUTION, "solution_architecture.png"),
}


def generate(client: genai.Client, prompt: str, out: Path, edit: str | None = None) -> None:
    contents = prompt
    if edit:  # refine the existing PNG instead of starting over
        contents = [
            types.Part.from_bytes(data=out.read_bytes(), mime_type="image/png"),
            "Edit this diagram. Change ONLY the following; keep every other box, label, arrow, "
            f"color and position pixel-identical:\n{edit}",
        ]
    resp = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="16:9", image_size="2K"),
        ),
    )
    for part in resp.candidates[0].content.parts:
        if part.inline_data:
            out.write_bytes(part.inline_data.data)
            print(f"wrote {out}")
            return
    raise SystemExit(f"no image returned for {out.name}: {resp.text!r}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", required=True, help="Google Cloud project ID for Vertex AI")
    ap.add_argument("--location", default="global")
    ap.add_argument("--only", choices=DIAGRAMS)
    ap.add_argument("--edit", metavar="TEXT", help="refine the existing PNG(s) with this instruction")
    args = ap.parse_args()

    client = genai.Client(vertexai=True, project=args.project, location=args.location)
    DOCS.mkdir(exist_ok=True)
    for name, (prompt, filename) in DIAGRAMS.items():
        if args.only in (None, name):
            generate(client, prompt, DOCS / filename, args.edit)


if __name__ == "__main__":
    main()
