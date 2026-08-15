/* Generate the README's hand-drawn diagrams as standalone SVGs.
 *
 *   node docs/diagrams.js        ->  docs/pipeline.svg, docs/architecture.svg
 *
 * Uses the SAME vendored Rough.js the videos are drawn with, so the docs look
 * like the product. Runs headless in plain node (rough's generator emits path
 * data, no DOM needed) — no Chromium, no npm install, no new dependency.
 * Every shape passes an explicit seed, so re-running produces a byte-identical
 * file instead of a noisy diff.
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const src = fs.readFileSync(path.join(ROOT, 'deck/visual/vendor/rough.js'), 'utf8');
const R = eval(src + '; rough');
const gen = R.generator();

const FONT = fs.readFileSync(path.join(ROOT, 'deck/visual/vendor/patrick-hand.woff2')).toString('base64');

const C = {
  bg: '#20292d', chalk: '#f2efe6', dim: '#93a0a4',
  yellow: '#ffd166', blue: '#74c7ff', green: '#8bd17c', pink: '#ff9db0',
};

let seed = 1;
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/** A rough shape -> SVG <path> elements. `dash` marks an optional/branch path. */
function shape(drawable, color, width, dash) {
  const da = dash ? ` stroke-dasharray="${dash}"` : '';
  return drawable.sets
    .filter((s) => s.type === 'path')
    .map((s) => `<path d="${gen.opsToPath(s, 2)}" stroke="${color}" stroke-width="${width}" fill="none" stroke-linecap="round"${da}/>`)
    .join('');
}

const rect = (x, y, w, h, color = C.chalk, width = 2, dash = null) =>
  shape(gen.rectangle(x, y, w, h, { stroke: color, roughness: 1.5, bowing: 1.2, seed: seed++ }), color, width, dash);

const line = (x1, y1, x2, y2, color = C.dim, width = 2, dash = null) =>
  shape(gen.line(x1, y1, x2, y2, { stroke: color, roughness: 1.4, seed: seed++ }), color, width, dash);

/** Arrow: a rough line plus a rough head. */
function arrow(x1, y1, x2, y2, color = C.dim, dash = null) {
  const head = 9;
  let a, b;
  if (Math.abs(x2 - x1) > Math.abs(y2 - y1)) {
    const s = x2 > x1 ? 1 : -1;
    a = [x2 - s * head, y2 - head]; b = [x2 - s * head, y2 + head];
  } else {
    const s = y2 > y1 ? 1 : -1;
    a = [x2 - head, y2 - s * head]; b = [x2 + head, y2 - s * head];
  }
  return line(x1, y1, x2, y2, color, 2, dash) + line(a[0], a[1], x2, y2, color) + line(b[0], b[1], x2, y2, color);
}

/** Elbow arrow: down/up from (x1,y1) to the turn row, across, then into (x2,y2). */
function elbow(x1, y1, x2, y2, turnY, color = C.dim, dash = null) {
  return line(x1, y1, x1, turnY, color, 2, dash)
    + line(x1, turnY, x2, turnY, color, 2, dash)
    + arrow(x2, turnY, x2, y2, color, dash);
}

const text = (x, y, str, { size = 20, color = C.chalk, anchor = 'middle', weight = 'normal' } = {}) =>
  `<text x="${x}" y="${y}" font-family="PatrickHand, 'Patrick Hand', 'Comic Sans MS', cursive, sans-serif" ` +
  `font-size="${size}" fill="${color}" text-anchor="${anchor}" font-weight="${weight}">${esc(str)}</text>`;

/** A labelled box: heading, then one line per entry in `lines`. */
function card(x, y, w, h, heading, lines, color) {
  let out = rect(x, y, w, h, color);
  out += text(x + w / 2, y + 30, heading, { size: 22, color, weight: 'bold' });
  lines.forEach((l, i) => {
    out += text(x + w / 2, y + 58 + i * 25, l, { size: 17, color: C.chalk });
  });
  return out;
}

/** Compact card for the dense deployment view: smaller heading + tighter lines. */
function box(x, y, w, h, heading, lines, color, { dash = null, headSize = 18, lineSize = 14 } = {}) {
  let out = rect(x, y, w, h, color, 2, dash);
  out += text(x + w / 2, y + 26, heading, { size: headSize, color, weight: 'bold' });
  lines.forEach((l, i) => {
    out += text(x + w / 2, y + 50 + i * 21, l, { size: lineSize, color: C.chalk });
  });
  return out;
}

function svg(width, height, body, title) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="${esc(title)}">
<title>${esc(title)}</title>
<defs><style>
@font-face{font-family:PatrickHand;src:url(data:font/woff2;base64,${FONT}) format('woff2');}
</style></defs>
<rect width="${width}" height="${height}" fill="${C.bg}"/>
${body}
</svg>
`;
}

/* ---------------------------------------------------------------- pipeline */
function pipeline() {
  const W = 1180, H = 570;
  let s = '';
  s += text(W / 2, 40, 'script  →  video', { size: 30, color: C.yellow, weight: 'bold' });

  // input
  s += rect(30, 90, 150, 90, C.green);
  s += text(105, 125, 'your script', { size: 20, color: C.green, weight: 'bold' });
  s += text(105, 152, 'one paragraph', { size: 15, color: C.dim });
  s += text(105, 171, 'per scene', { size: 15, color: C.dim });
  s += arrow(185, 135, 218, 135);

  // three stages
  s += card(225, 80, 285, 250, '1 · COMPOSE', [
    'Gemini draws each',
    'paragraph in Rough.js',
    '',
    'rubric → safety →',
    'integrity gates',
    '',
    'VERBATIM LOCK:',
    'your words restored',
  ], C.blue);
  s += arrow(515, 200, 548, 200);

  s += card(555, 80, 285, 250, '2 · VOICE + RECORD', [
    'TTS clip per scene',
    '',
    'whisper forced-align',
    '⇒ word timestamps',
    '',
    'Chromium records in',
    'real time; each cue',
    'fires on its word',
  ], C.pink);
  s += arrow(845, 200, 878, 200);

  s += card(885, 80, 265, 250, '3 · MUX', [
    'trim the lead-in',
    '',
    'concat narration',
    'mux over video',
    '',
    'speed up 1.1×',
    '(A/V stay locked)',
  ], C.yellow);

  // output
  s += arrow(1017, 335, 1017, 375, C.dim);
  s += text(1017, 405, '1080 × 1920 · 25 fps · mp4', { size: 18, color: C.green });

  // the through-line
  s += text(105, 230, 'nothing', { size: 17, color: C.dim });
  s += text(105, 252, 'rewrites', { size: 17, color: C.dim });
  s += text(105, 274, 'your words', { size: 17, color: C.dim });

  // optional human-in-the-loop review: a detour between compose and record
  const DASH = '9 7';
  s += rect(225, 440, 615, 105, C.green, 2, DASH);
  s += text(532, 470, 'optional · review & edit  (GUI checkbox)', { size: 20, color: C.green, weight: 'bold' });
  s += text(532, 498, 'preview each scene · fix narration & cues · redraw a visual', { size: 16, color: C.chalk });
  s += text(532, 524, 'approved draft → drafts/<id>.json → record-only job (skips compose)', { size: 15, color: C.dim });
  s += elbow(330, 335, 300, 435, 400, C.green, DASH);
  s += elbow(760, 435, 700, 335, 400, C.green, DASH);

  return svg(W, H, s, 'Pipeline: script to video in three stages, with the optional review step');
}

/* ------------------------------------------------------------ architecture */
function architecture() {
  const W = 1180, H = 560;
  let s = '';
  s += text(W / 2, 40, 'what runs where', { size: 30, color: C.yellow, weight: 'bold' });

  // entrypoints
  s += rect(60, 75, 240, 80, C.green);
  s += text(180, 108, 'app.py', { size: 21, color: C.green, weight: 'bold' });
  s += text(180, 134, 'Streamlit GUI · review UI', { size: 15, color: C.dim });

  s += rect(340, 75, 240, 80, C.green);
  s += text(460, 108, 'deck.gen.generate', { size: 21, color: C.green, weight: 'bold' });
  s += text(460, 134, 'the CLI', { size: 15, color: C.dim });

  s += rect(700, 75, 300, 80, C.pink);
  s += text(850, 108, 'Cloud Run Job', { size: 21, color: C.pink, weight: 'bold' });
  s += text(850, 134, 'deck.infra.job · fire-and-forget', { size: 15, color: C.dim });

  s += arrow(300, 115, 336, 115);
  s += arrow(584, 115, 696, 115);
  s += text(640, 103, 'dispatch', { size: 14, color: C.dim });

  // the core
  s += rect(60, 205, 940, 215, C.chalk, 2);
  s += text(90, 235, 'the pipeline', { size: 19, color: C.dim, anchor: 'start' });

  s += card(90, 255, 270, 145, 'deck/gen', [
    'generate.py — split,',
    'compose, lock, record',
    'review.py — cue repair',
  ], C.blue);

  s += card(400, 255, 270, 145, 'deck/visual', [
    'compose.py — the LLM call',
    'rubric · safety · integrity',
    'scene.py — build_html()',
  ], C.blue);

  s += card(710, 255, 270, 145, 'deck/render', [
    'record.py — TTS + mux',
    '_align.py — word times',
    'sandbox_render.py',
  ], C.blue);

  s += arrow(365, 325, 395, 325);
  s += arrow(675, 325, 705, 325);

  // infra
  s += rect(1035, 205, 110, 215, C.yellow);
  s += text(1090, 245, 'deck', { size: 18, color: C.yellow, weight: 'bold' });
  s += text(1090, 268, 'infra', { size: 18, color: C.yellow, weight: 'bold' });
  s += text(1090, 305, 'gcs', { size: 16, color: C.chalk });
  s += text(1090, 330, 'job', { size: 16, color: C.chalk });
  s += text(1090, 355, 'auth', { size: 16, color: C.chalk });
  s += line(1005, 312, 1030, 312, C.dim);

  // storage — hangs off deck/infra, the only package that touches GCS
  s += rect(620, 460, 525, 75, C.yellow);
  s += text(882, 490, 'GCS bucket', { size: 20, color: C.yellow, weight: 'bold' });
  s += text(882, 516, 'jobs/  ·  drafts/  ·  output/*.mp4', { size: 16, color: C.chalk });
  s += arrow(1090, 425, 1090, 455, C.dim);
  s += text(90, 480, 'the GUI and the Job both reach', { size: 17, color: C.dim, anchor: 'start' });
  s += text(90, 505, 'storage through deck/infra —', { size: 17, color: C.dim, anchor: 'start' });
  s += text(90, 530, 'nothing else imports GCS.', { size: 17, color: C.dim, anchor: 'start' });

  return svg(W, H, s, 'Architecture: entrypoints, pipeline packages, and storage');
}

/* -------------------------------------------------------------- deployment */
/* The concrete GCP surfaces: who authenticates, which identity runs what, where
   every secret and artifact lives, and how the page is built at render time. */
function deployment() {
  const W = 1420, H = 1000;
  const DASH = '9 7';
  let s = '';
  s += text(W / 2, 42, 'the deployed system', { size: 30, color: C.yellow, weight: 'bold' });
  s += text(W / 2, 68, 'project rocketech-de-pgcp-sandbox · region us-central1', { size: 15, color: C.dim });

  // --- access path -----------------------------------------------------------
  s += box(40, 95, 165, 82, 'browser', [
    'any signed-in',
    'rocketech.co.uk user',
  ], C.green);
  s += arrow(210, 136, 243, 136);

  s += box(250, 95, 265, 82, 'Identity-Aware Proxy', [
    'roles/iap.httpsResourceAccessor',
    'domain:rocketech.co.uk',
  ], C.green);
  s += text(382, 192, 'unsigned → 302 to Google', { size: 13, color: C.dim });
  s += arrow(520, 136, 553, 136);

  s += box(560, 95, 400, 82, 'Cloud Run service · script-to-video-web', [
    'Streamlit · max 1 instance · scales to zero',
    'SA script-to-video-web · iap_enabled = true',
  ], C.green);

  s += box(1000, 95, 380, 82, 'Artifact Registry · script-to-video', [
    'render-base:<hash> (torch, whisper, Chromium)',
    'render:latest · web:latest  ← Cloud Build',
  ], C.dim, { headSize: 17 });

  // service -> job dispatch
  s += elbow(700, 181, 470, 232, 210, C.pink);
  s += text(688, 204, 'run.jobs.runWithOverrides (DECK_NAME)', { size: 13, color: C.dim, anchor: 'end' });

  // --- the render job --------------------------------------------------------
  s += rect(40, 232, 920, 610, C.pink);
  s += text(62, 262, 'Cloud Run Job · script-to-video-render', { size: 21, color: C.pink, weight: 'bold', anchor: 'start' });
  s += text(62, 285, '4 vCPU · 8 GiB · SA script-to-video-render · sandboxLauncher: true', { size: 14, color: C.dim, anchor: 'start' });

  s += box(65, 305, 415, 120, '1 · compose  (deck/visual/compose.py)', [
    'one Gemini call → per-paragraph Rough.js JS',
    'rubric → safety → integrity gates',
    'verbatim lock restores your words',
  ], C.blue, { headSize: 16 });

  s += box(510, 305, 425, 120, '2 · build_html  (dynamic page)', [
    'scene-kit harness + the LLM-authored JS',
    'rough.js · anime.js · woff2 all INLINED',
    '⇒ self-contained page.html, zero fetches',
  ], C.blue, { headSize: 16 });
  s += arrow(485, 365, 505, 365, C.dim);

  s += box(65, 450, 415, 120, '3 · voice + align', [
    'ElevenLabs cloned voice (native word times)',
    'or Gemini TTS → whisper-timestamped',
    'aligner runs in an isolated py3.11 subprocess',
  ], C.blue, { headSize: 16 });

  s += box(510, 450, 425, 195, '4 · sandbox  (zero egress)', [
    '/usr/local/gcp/bin/sandbox run --detach',
    '  → exec (synchronous) → delete --force',
    '',
    'nested Chromium records page.html in',
    'real time · bind-mounted work dir',
    'NO network · NO credentials',
  ], C.pink, { dash: DASH, headSize: 16 });
  s += arrow(485, 545, 505, 545, C.dim);
  s += text(722, 668, 'the only step that runs model-authored JS', { size: 13, color: C.dim, anchor: 'middle' });

  s += box(65, 665, 415, 100, '5 · mux  (ffmpeg)', [
    'trim lead-in · concat narration · 1.1×',
    '⇒ 1080 × 1920 · 25 fps · mp4',
  ], C.yellow, { headSize: 16 });
  s += arrow(272, 575, 272, 658, C.dim);
  s += arrow(272, 430, 272, 445, C.dim);

  s += text(62, 800, 'DECK_PROBE=1 runs the sandbox health check instead of a render', { size: 14, color: C.dim, anchor: 'start' });
  s += text(62, 824, 'DECK_SOURCE=draft records an approved draft and skips compose', { size: 14, color: C.dim, anchor: 'start' });

  // --- managed dependencies --------------------------------------------------
  s += box(1000, 232, 380, 105, 'Vertex AI', [
    'gemini-3.6-flash — visual compose',
    'gemini TTS (when not using ElevenLabs)',
    'SA roles: aiplatform.user',
  ], C.yellow, { headSize: 17 });
  s += arrow(995, 300, 940, 330, C.dim);

  s += box(1000, 365, 380, 105, 'Secret Manager', [
    'elevenlabs-api-key → ELEVENLABS_API_KEY',
    'injected by Cloud Run as an env var',
    'SA roles: secretmanager.secretAccessor',
  ], C.yellow, { headSize: 17 });
  s += arrow(995, 430, 940, 470, C.dim);

  s += box(1000, 498, 380, 82, 'ElevenLabs API', [
    'cloned voice + native word timestamps',
    'called from OUTSIDE the sandbox',
  ], C.dim, { headSize: 17 });

  s += box(1000, 608, 380, 180, 'GCS · script-to-video-…-sandbox', [
    'jobs/<id>.json    title + script + settings',
    'drafts/<id>.json  reviewed scenes',
    'output/<name>.mp4 finished videos',
    '',
    'written by BOTH the service and the Job',
    'SA roles: storage.objectAdmin',
  ], C.yellow, { headSize: 17 });
  s += arrow(965, 700, 995, 700, C.dim);

  s += text(1190, 822, 'terraform state', { size: 15, color: C.dim });
  s += text(1190, 844, 'gs://script-to-video-tfstate-…', { size: 13, color: C.dim });

  // --- footer: what is NOT reachable ----------------------------------------
  s += rect(40, 868, 1340, 105, C.green, 2, DASH);
  s += text(64, 898, 'trust boundaries', { size: 18, color: C.green, weight: 'bold', anchor: 'start' });
  s += text(64, 925, '· IAP authenticates before any request reaches the container — the app itself has no login code.', { size: 15, color: C.chalk, anchor: 'start' });
  s += text(64, 948, '· LLM-authored JS is statically vetted, then executed only inside the no-egress sandbox: no metadata server, no SA token, no network.', { size: 15, color: C.chalk, anchor: 'start' });

  return svg(W, H, s, 'Deployment: IAP, Cloud Run service and job, secrets, storage, and the render sandbox');
}

fs.writeFileSync(path.join(__dirname, 'pipeline.svg'), pipeline());
seed = 1;
fs.writeFileSync(path.join(__dirname, 'architecture.svg'), architecture());
seed = 1;
fs.writeFileSync(path.join(__dirname, 'deployment.svg'), deployment());
console.log('wrote docs/pipeline.svg, docs/architecture.svg, docs/deployment.svg');
