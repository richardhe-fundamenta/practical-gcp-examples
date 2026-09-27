/**
 * GCS-backed, stateless storage for the app. The bucket is owned by the Cloud
 * Run runtime SA; per-user isolation is enforced in code by prefixing every
 * object with the verified `sub`. Cloud Run holds nothing between calls.
 *
 * Layout:  gs://$BUCKET/{sub}/{docId}/original.pdf
 *                                      index.json
 *                                      meta.json         (filename, uploadedAt)
 *                                      pages/{n}.png     (cached renders)
 */
import { Storage } from "@google-cloud/storage";

export interface DocMeta {
  docId: string;
  filename: string;
  pageCount: number;
  uploadedAt: string;
}

const DOC_ID_RE = /^[A-Za-z0-9_-]+$/;

/** `${sub}/` — the user's root prefix. */
export function userPrefix(sub: string): string {
  if (!sub) throw new Error("missing user id");
  return `${sub}/`;
}

/**
 * `${sub}/${docId}/` — throws if docId could escape the user's prefix.
 * docId is the only client-supplied path segment, so it is validated hard.
 */
export function docPrefix(sub: string, docId: string): string {
  if (!DOC_ID_RE.test(docId)) {
    throw new Error(`invalid document id: ${JSON.stringify(docId)}`);
  }
  return `${userPrefix(sub)}${docId}/`;
}

const bucketName = () => {
  const b = process.env.BUCKET;
  if (!b) throw new Error("BUCKET env var is not set");
  return b;
};

let _storage: Storage | undefined;
const storage = () => (_storage ??= new Storage());
const bucket = () => storage().bucket(bucketName());

export async function writeDoc(
  sub: string,
  docId: string,
  pdf: Buffer,
  email: string,
): Promise<void> {
  await bucket()
    .file(`${docPrefix(sub, docId)}original.pdf`)
    .save(pdf, { contentType: "application/pdf", metadata: { metadata: { email } } });
}

export async function readDoc(sub: string, docId: string): Promise<Buffer> {
  const [buf] = await bucket().file(`${docPrefix(sub, docId)}original.pdf`).download();
  return buf;
}

export async function writeMeta(sub: string, docId: string, meta: DocMeta): Promise<void> {
  await bucket()
    .file(`${docPrefix(sub, docId)}meta.json`)
    .save(JSON.stringify(meta), { contentType: "application/json" });
}

export async function writeIndex(sub: string, docId: string, index: unknown): Promise<void> {
  await bucket()
    .file(`${docPrefix(sub, docId)}index.json`)
    .save(JSON.stringify(index), { contentType: "application/json" });
}

export async function readIndex<T = unknown>(sub: string, docId: string): Promise<T> {
  const [buf] = await bucket().file(`${docPrefix(sub, docId)}index.json`).download();
  return JSON.parse(buf.toString("utf-8")) as T;
}

export async function listDocs(sub: string): Promise<DocMeta[]> {
  const [files] = await bucket().getFiles({ prefix: userPrefix(sub) });
  const metas = files.filter((f) => f.name.endsWith("/meta.json"));
  const out: DocMeta[] = [];
  for (const f of metas) {
    const [buf] = await f.download();
    out.push(JSON.parse(buf.toString("utf-8")) as DocMeta);
  }
  return out.sort((a, b) => b.uploadedAt.localeCompare(a.uploadedAt));
}

/** Return a cached page PNG, rendering + caching via `render` on first miss. */
export async function getOrRenderPage(
  sub: string,
  docId: string,
  page: number,
  render: () => Promise<Buffer>,
): Promise<Buffer> {
  const file = bucket().file(`${docPrefix(sub, docId)}pages/${page}.png`);
  const [exists] = await file.exists();
  if (exists) {
    const [buf] = await file.download();
    return buf;
  }
  const png = await render();
  await file.save(png, { contentType: "image/png" });
  return png;
}
