import { NextResponse } from "next/server";

import { authConfig } from "@/lib/auth";
import { SESSION_COOKIE, SESSION_MAX_AGE, assinar } from "@/lib/session";

export const dynamic = "force-dynamic";

type Guild = { id: string; name: string };

/**
 * Volta do Discord.
 *
 * O acesso é decidido pela presença no servidor configurado. Sair do servidor
 * tira o acesso na próxima vez que a pessoa logar — a fonte da verdade é o
 * Discord, não uma lista paralela que alguém precisa lembrar de atualizar.
 */
export async function GET(request: Request) {
  const { clientId, clientSecret, redirectUri, guildId, segredo, habilitado } = authConfig();
  if (!habilitado) {
    return NextResponse.json({ erro: "login não configurado" }, { status: 503 });
  }

  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  const esperado = request.headers
    .get("cookie")
    ?.split(";")
    .find((c) => c.trim().startsWith("aei_state="))
    ?.split("=")[1];

  if (url.searchParams.get("error")) {
    return NextResponse.redirect(new URL("/login?erro=recusado", url.origin));
  }
  // State ausente ou diferente significa callback forjado. Falha sem detalhe.
  if (!code || !state || state !== esperado) {
    return NextResponse.redirect(new URL("/login?erro=estado", url.origin));
  }

  const troca = await fetch("https://discord.com/api/oauth2/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: clientId,
      client_secret: clientSecret,
      grant_type: "authorization_code",
      code,
      redirect_uri: redirectUri,
    }),
  });
  if (!troca.ok) {
    return NextResponse.redirect(new URL("/login?erro=token", url.origin));
  }
  const { access_token } = (await troca.json()) as { access_token: string };
  const auth = { Authorization: `Bearer ${access_token}` };

  const [respUsuario, respGuilds] = await Promise.all([
    fetch("https://discord.com/api/users/@me", { headers: auth }),
    fetch("https://discord.com/api/users/@me/guilds", { headers: auth }),
  ]);
  if (!respUsuario.ok || !respGuilds.ok) {
    return NextResponse.redirect(new URL("/login?erro=discord", url.origin));
  }

  const usuario = (await respUsuario.json()) as {
    id: string; username: string; global_name?: string | null; avatar: string | null;
  };
  const guilds = (await respGuilds.json()) as Guild[];

  if (guildId && !guilds.some((g) => g.id === guildId)) {
    return NextResponse.redirect(new URL("/sem-acesso", url.origin));
  }

  const token = await assinar(
    {
      id: usuario.id,
      username: usuario.global_name || usuario.username,
      avatar: usuario.avatar,
      iat: Math.floor(Date.now() / 1000),
    },
    segredo,
  );

  const resposta = NextResponse.redirect(new URL("/", url.origin));
  resposta.cookies.set(SESSION_COOKIE, token, {
    httpOnly: true, sameSite: "lax", path: "/", maxAge: SESSION_MAX_AGE,
    secure: process.env.NODE_ENV === "production",
  });
  resposta.cookies.delete("aei_state");
  return resposta;
}
