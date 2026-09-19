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

/**
 * Dispensa a sessão em desenvolvimento, e **só** lá.
 *
 * ## O problema que isto resolve
 *
 * Com o portão ligado, qualquer tela do produto responde `302 /login` para quem
 * não tem cookie. Isso impede conferir uma mudança de layout sem abrir um
 * navegador logado — e o jeito que existia de contornar era apagar
 * `SESSION_SECRET` do `.env`, que é exatamente o hábito que não se quer criar:
 * mexer no segredo para ver a tela, e um dia esquecer de repô-lo.
 *
 * ## Por que é seguro, sem depender de configuração
 *
 * As duas condições precisam valer juntas, e a primeira **não é
 * configurável**:
 *
 * 1. `process.env.NODE_ENV === "development"`. O Next substitui esta expressão
 *    por um literal **no momento do build**, e `next build` compila sempre com
 *    `"production"`. Num artefato de produção a condição vira
 *    `"production" === "development"`, que é falso constante — o bundler
 *    elimina o bloco inteiro, e **o código do desvio não existe** no que foi
 *    publicado. Não há variável de ambiente, painel de deploy ou `.env`
 *    vazado que reative algo que não foi compilado.
 * 2. `DEV_AUTH_BYPASS === "1"`, exato. É o consentimento explícito: a
 *    condição 1 sozinha ligaria o desvio em toda máquina de desenvolvimento,
 *    inclusive na de quem está justamente testando o login.
 *
 * A ordem importa para a leitura, não para a segurança: a garantia forte é a
 * primeira, e a segunda existe para o desvio não ser o padrão de ninguém.
 *
 * ## O que o desvio faz, e o que não faz
 *
 * Ele libera a **passagem**, não forja identidade. A sessão continua nula, que
 * é o mesmo estado do modo aberto que já existia: o preço manual fica anônimo
 * e nada é gravado em nome de ninguém. Assim o desvio não cria um caminho de
 * código que só existe em desenvolvimento — ele cai num que a aplicação já
 * tinha.
 *
 * A resposta sai marcada com `x-dev-auth-bypass: 1`, para o estado ser
 * observável de fora em vez de silencioso.
 */
function desvioDeDesenvolvimento(): boolean {
  return process.env.NODE_ENV === "development" && process.env.DEV_AUTH_BYPASS === "1";
}

export async function middleware(request: NextRequest) {
  const segredo = process.env.SESSION_SECRET;
  const clientId = process.env.DISCORD_CLIENT_ID;
  if (!segredo || !clientId) return NextResponse.next();

  const { pathname } = request.nextUrl;
  if (PUBLICAS.some((rota) => pathname.startsWith(rota))) return NextResponse.next();

  if (desvioDeDesenvolvimento()) {
    const resposta = NextResponse.next();
    resposta.headers.set("x-dev-auth-bypass", "1");
    return resposta;
  }

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
