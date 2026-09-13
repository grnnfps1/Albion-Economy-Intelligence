import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { SESSION_COOKIE, verificar } from "@/lib/session";

/**
 * Portão de entrada.
 *
 * A verificação acontece aqui e não em cada página: esquecer de proteger uma
 * rota nova é o jeito mais comum de furar um sistema de login, e o middleware
 * fecha por padrão em vez de abrir.
 *
 * Sem `SESSION_SECRET` e `DISCORD_CLIENT_ID` configurados, a aplicação roda
 * aberta. É o que permite desenvolver localmente sem montar OAuth — e é seguro
 * porque um deploy real sem esses valores nem chega a autenticar ninguém.
 */
const PUBLICAS = ["/login", "/sem-acesso", "/api/auth"];

export async function middleware(request: NextRequest) {
  const segredo = process.env.SESSION_SECRET;
  const clientId = process.env.DISCORD_CLIENT_ID;
  if (!segredo || !clientId) return NextResponse.next();

  const { pathname } = request.nextUrl;
  if (PUBLICAS.some((rota) => pathname.startsWith(rota))) return NextResponse.next();

  const token = request.cookies.get(SESSION_COOKIE)?.value;
  const session = token ? await verificar(token, segredo) : null;
  if (session) return NextResponse.next();

  const destino = new URL("/login", request.url);
  // Guarda para onde a pessoa ia, para devolver depois do login.
  if (pathname !== "/") destino.searchParams.set("de", pathname);
  return NextResponse.redirect(destino);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
