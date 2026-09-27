/**
 * Resolve the signed-in user from the forwarded OAuth token. The token is used
 * ONLY for identity here: we call the OIDC userinfo endpoint and read `sub`
 * (stable subject id, used as the GCS folder prefix) and `email` (kept in
 * object metadata for audit). All GCS/Vertex access uses the runtime SA.
 */

export interface Identity {
  sub: string;
  email: string;
}

const USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo";

export async function getIdentity(token?: string): Promise<Identity> {
  if (!token) {
    throw new Error("Sign-in required: no user credentials were forwarded to the app.");
  }
  const res = await fetch(USERINFO_URL, {
    headers: { authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error(`Could not verify your identity (userinfo ${res.status}).`);
  }
  const info = (await res.json()) as { sub?: string; email?: string };
  if (!info.sub) {
    throw new Error("Could not verify your identity: token is missing the 'sub' claim (needs the 'openid' scope).");
  }
  return { sub: info.sub, email: info.email ?? "" };
}
