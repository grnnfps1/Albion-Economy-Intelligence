import { NextResponse } from "next/server";

import { SESSION_COOKIE } from "@/lib/session";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const resposta = NextResponse.redirect(new URL("/login", new URL(request.url).origin));
  resposta.cookies.delete(SESSION_COOKIE);
  return resposta;
}
