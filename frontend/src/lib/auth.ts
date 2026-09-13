import "server-only";

import { cookies } from "next/headers";

import { SESSION_COOKIE, type Session, verificar } from "@/lib/session";

export function authConfig() {
  const clientId = process.env.DISCORD_CLIENT_ID ?? "";
  const clientSecret = process.env.DISCORD_CLIENT_SECRET ?? "";
  const redirectUri =
    process.env.DISCORD_REDIRECT_URI ?? "http://localhost:3000/api/auth/discord/callback";
  const guildId = process.env.DISCORD_GUILD_ID ?? "";
  const segredo = process.env.SESSION_SECRET ?? "";

  return {
    clientId,
    clientSecret,
    redirectUri,
    guildId,
    segredo,
    /** Sem configuração completa, a aplicação roda aberta — útil em dev local. */
    habilitado: Boolean(clientId && clientSecret && segredo),
  };
}

export async function getSession(): Promise<Session | null> {
  const { segredo, habilitado } = authConfig();
  if (!habilitado) return null;
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  return token ? verificar(token, segredo) : null;
}
