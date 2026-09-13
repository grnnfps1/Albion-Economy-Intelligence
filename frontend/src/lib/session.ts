/**
 * Sessão assinada em cookie.
 *
 * Usa Web Crypto (HMAC-SHA256) em vez do módulo `crypto` do Node porque o
 * middleware roda no runtime edge, onde o módulo de Node não existe. O mesmo
 * código serve para middleware e para route handlers.
 *
 * O cookie é assinado, não criptografado: o conteúdo é legível por quem o
 * inspecionar, e por isso só guarda o que pode ser público — id, nome e avatar
 * do Discord. Nada de token de acesso, que daria a quem roubasse o cookie o
 * poder de agir no Discord em nome do usuário.
 */
export type Session = {
  id: string;
  username: string;
  avatar: string | null;
  /** Quando a sessão foi criada, em segundos. */
  iat: number;
};

export const SESSION_COOKIE = "aei_session";
export const SESSION_MAX_AGE = 60 * 60 * 24 * 30;

const enc = new TextEncoder();

function base64url(bytes: Uint8Array): string {
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function fromBase64url(texto: string): ArrayBuffer {
  const b64 = texto.replace(/-/g, "+").replace(/_/g, "/");
  const bin = atob(b64.padEnd(Math.ceil(b64.length / 4) * 4, "="));
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
}

async function chave(segredo: string): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "raw", enc.encode(segredo), { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"],
  );
}

export async function assinar(session: Session, segredo: string): Promise<string> {
  const corpo = base64url(enc.encode(JSON.stringify(session)));
  const assinatura = await crypto.subtle.sign("HMAC", await chave(segredo), enc.encode(corpo));
  return `${corpo}.${base64url(new Uint8Array(assinatura))}`;
}

export async function verificar(token: string, segredo: string): Promise<Session | null> {
  const [corpo, assinatura] = token.split(".");
  if (!corpo || !assinatura) return null;

  const valida = await crypto.subtle.verify(
    "HMAC", await chave(segredo), fromBase64url(assinatura), enc.encode(corpo),
  );
  if (!valida) return null;

  try {
    const session = JSON.parse(
      new TextDecoder().decode(new Uint8Array(fromBase64url(corpo))),
    ) as Session;
    // Assinatura válida não basta: um cookie antigo continua assinado para
    // sempre. A expiração é verificada aqui, não só pelo max-age do navegador.
    if (Date.now() / 1000 - session.iat > SESSION_MAX_AGE) return null;
    return session;
  } catch {
    return null;
  }
}
