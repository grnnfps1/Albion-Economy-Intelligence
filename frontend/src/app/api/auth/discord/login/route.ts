import { NextResponse } from "next/server";

import { authConfig } from "@/lib/auth";

export const dynamic = "force-dynamic";

/**
 * Início do fluxo OAuth.
 *
 * O `state` é gerado aqui e guardado num cookie de curta duração. Sem ele,
 * qualquer site poderia forjar um callback e logar a vítima numa conta que não
 * é dela.
 *
 * Escopos: `identify` traz nome e avatar; `guilds` traz a lista de servidores,
 * que é como o acesso é decidido. Nada além disso — pedir escopo a mais assusta
 * quem autoriza e aumenta o estrago se o token vazar.
 */
export async function GET() {
  const { clientId, redirectUri, habilitado } = authConfig();
  if (!habilitado) {
    return NextResponse.json({ erro: "login não configurado" }, { status: 503 });
  }

  const state = crypto.randomUUID();
  const url = new URL("https://discord.com/api/oauth2/authorize");
  url.searchParams.set("client_id", clientId);
  url.searchParams.set("redirect_uri", redirectUri);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("scope", "identify guilds");
  url.searchParams.set("state", state);
  url.searchParams.set("prompt", "none");

  const resposta = NextResponse.redirect(url.toString());
  resposta.cookies.set("aei_state", state, {
    httpOnly: true, sameSite: "lax", path: "/", maxAge: 600,
    secure: process.env.NODE_ENV === "production",
  });
  return resposta;
}
