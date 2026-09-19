# 06 — Auditoria de segurança

> Levantamento de **19/09/2026**, a pedido. Nada foi corrigido: o documento
> existe para a ordem de trabalho ser decidida com o risco de cada item na
> mesa.
>
> **CAPTCHA está fora, e a razão fica registrada para não voltar à pauta:** o
> acesso já exige conta Discord dentro de um servidor específico, que é
> barreira mais forte do que qualquer desafio anônimo, e não há formulário
> público a proteger. Acrescentá-lo custaria fricção sem fechar nada.

## Resumo

| # | Achado | Risco | Esforço |
|---|---|---|---|
| 1 | Backend na 8000 sem autenticação nenhuma | **Alto** | baixo |
| 2 | `starlette` 0.41.3 com 8 avisos, um deles DoS não autenticado | **Alto** | baixo |
| 3 | `DISCORD_GUILD_ID` vazio libera qualquer conta do Discord | **Alto** | baixo |
| 4 | `SESSION_SECRET` sem validação de entropia | Médio | baixo |
| 5 | Revogação só no login; sessão de 30 dias | Médio | médio |
| 6 | Sem rate limit nas rotas próprias | Médio | médio |
| 7 | `vitest` com path traversal (moderado, só em teste) | Baixo | baixo |
| 8 | `pytest` 8.3.4, DoS local em `/tmp` (só em teste) | Baixo | baixo |

**Limpo, verificado:** injeção SQL, segredo no bundle do cliente, segredo em
log, flags do cookie, validação de entrada no backend.

---

## 1. O backend aceita qualquer requisição — risco ALTO

`docker-compose.yml` publica `${BACKEND_PORT:-8000}:8000` no host. Toda a API
fica alcançável direto, e `api/deps.py` é explícito sobre o que isso significa:

```python
async def current_user_id(x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None):
    """O backend **não** valida sessão: quem valida é o `middleware.ts`."""
```

O comentário chama isso de decisão de confiança, e a decisão está certa
**enquanto a porta não estiver publicada**. Hoje ela está. Quem alcança a 8000
lê tudo e, pior, escreve: `PUT /api/v1/manual-prices` aceita um `X-User-Id`
qualquer e grava preço manual no nome de quem o atacante escolher — o cabeçalho
é a identidade, sem nada que o prove.

O portão inteiro do produto vive no `middleware.ts`, e ele protege o Next, não
a API.

**Duas saídas, e elas não competem:**

- **Tirar a porta do host.** No compose, trocar `ports` por `expose` no serviço
  `backend`. O Next fala com ele pela rede interna (`BACKEND_INTERNAL_URL`), que
  continua funcionando. Custo: `curl localhost:8000` e o `/docs` do FastAPI
  deixam de funcionar da máquina; `docker compose exec` resolve, ou um `ports`
  só no override de desenvolvimento.
- **Exigir a sessão no backend.** O `X-User-Id` vira um cabeçalho assinado — o
  mesmo HMAC de `session.ts`, com o mesmo `SESSION_SECRET` — e o FastAPI o
  verifica. Isso fecha o buraco mesmo se a porta vazar de novo, e é o que
  transforma "decisão de confiança" em garantia.

A primeira é de cinco minutos e fecha o caso concreto. A segunda é defesa em
profundidade e sobrevive a um deploy futuro que reexponha a porta.

## 2. `starlette` 0.41.3 — risco ALTO

Oito avisos distintos. O que pesa é o **PYSEC-2026-1942**: um cabeçalho `Range`
forjado provoca processamento quadrático no `FileResponse`, **sem
autenticação**, e queima CPU do servidor. Combinado com o achado 1, é
exploração direta.

Os outros: reconstrução de URL sem validar `Host` (PYSEC-2026-161 e -248, que
permitem injetar caminho em `request.url`), `max_fields` e `max_part_size`
ignorados fora de `multipart` (PYSEC-2026-249), `getattr` irrestrito no
despacho de método do `HTTPEndpoint` (PYSEC-2026-2280), travessia por caminho
UNC no `StaticFiles` em Windows (PYSEC-2026-2281) e consumo de disco no spool
de upload (PYSEC-2026-1941).

A correção completa pede `starlette >= 1.3.1`, que é salto de major e arrasta o
FastAPI junto. **`0.47.2` já mata o DoS do `Range`** e é bem mais barato. Vale
fazer em duas etapas.

## 3. `DISCORD_GUILD_ID` vazio libera geral — risco ALTO

O `middleware.ts` fecha o portão quando `SESSION_SECRET` **e**
`DISCORD_CLIENT_ID` existem. O `DISCORD_GUILD_ID` **não** entra nessa condição,
e o callback só filtra se ele estiver preenchido:

```ts
if (guildId && !guilds.some((g) => g.id === guildId)) { ... }
```

Um deploy com os dois primeiros e o terceiro vazio exige login e aceita
**qualquer conta do Discord do mundo**. O `.env.example` avisa ("Vazio libera
qualquer conta"), mas comentário não é trava, e a falha é do tipo que abre em
silêncio: a tela de login aparece, o login funciona, e nada denuncia que o
filtro sumiu.

É o mesmo padrão que o projeto já adotou no `middleware.ts` — fechar por padrão
em vez de abrir. Aqui ele não foi aplicado.

## 4. `SESSION_SECRET` sem validação de entropia — risco MÉDIO

`auth.ts` lê `process.env.SESSION_SECRET ?? ""` e repassa a
`crypto.subtle.importKey`. **Não há verificação de comprimento.** Um segredo de
quatro caracteres é aceito, e a Web Crypto não reclama: HMAC aceita chave de
qualquer tamanho. O `.env.example` sugere `secrets.token_urlsafe(48)`, que é a
orientação certa — mas, de novo, sugestão não é trava.

Com segredo fraco, o cookie de sessão é forjável por força bruta, e sessão
forjada é acesso completo.

**O que fecharia:** recusar subir com `SESSION_SECRET` presente e abaixo de ~32
caracteres. Há uma sutileza: a aplicação não pode simplesmente *ignorar* um
segredo curto, porque ignorar cai no modo aberto — que é pior. Tem de falhar.

## 5. Revogação só no login — risco MÉDIO

A conferência de servidor acontece **uma vez**, no callback do OAuth. O cookie
vale 30 dias, e `verificar()` só checa assinatura e `iat`. Quem sai do servidor
do Discord — ou é expulso — continua entrando por até um mês.

O `CLAUDE.md` diz que "sair do servidor tira o acesso no próximo login", e isso
é literalmente verdade: o próximo login pode ser daqui a 30 dias.

**Custo de revalidar:** uma chamada a `https://discord.com/api/users/@me/guilds`
por verificação. A cada carregamento é inviável — o middleware roda no edge, em
toda navegação, e ainda precisaria do `access_token`, que **de propósito** não
está no cookie (ver `session.ts`). Revalidar exigiria guardar o token em algum
lugar, o que reintroduz exatamente o risco que a decisão original evitou.

**Saída mais barata, sem tocar nessa decisão:** encurtar a sessão. Trinta dias é
a janela de exposição; sete dias a reduz em 4×, e o usuário reloga uma vez por
semana num produto que ele abre quase diariamente. Renovação deslizante mantém
a conveniência.

## 6. Sem rate limit nas rotas próprias — risco MÉDIO

O Redis está no projeto desde a fase 1, e o limite de taxa implementado é o
**de saída**, para o AODP (`collectors/aodp/`). Não há nenhum **de entrada**.

`/api/v1/crafting/calculator` é o pior alvo: hoje ele custa cerca de 2 s e uma
leitura de 12.917 receitas por chamada (ver `docs/07-desempenho.md`). Um laço
simples derruba o serviço, e nem precisa de má intenção — basta alguém segurar
o F5.

O mecanismo já existe e é reaproveitável; falta aplicá-lo por `X-User-Id`, ou
por IP onde não houver usuário.

**A ordem importa:** consertar o desempenho do calculador reduz muito o
impacto, mas não substitui o limite. E o limite por usuário só tem sentido
depois do achado 1 — enquanto o `X-User-Id` for forjável, a chave do limite
também é.

## 7 e 8. Dependências de teste — risco BAIXO

- `vitest` / `@vitest/mocker`: path traversal via redirect de mock
  (GHSA-82fw-gwwq-j7x9, moderado). A correção pede `vitest@5`, que é breaking.
- `pytest` 8.3.4, PYSEC-2026-1845: `/tmp/pytest-of-{user}` permite a um usuário
  local do mesmo host causar DoS ou escalar privilégio. Corrigido em 9.0.3.

Nenhum dos dois entra em produção. Ficam por último, e o `vitest` só quando
houver disposição para o major.

---

## O que foi verificado e está limpo

**Injeção SQL.** Todas as queries passam por SQLAlchemy com parâmetros. Há um
único `text()` no código de aplicação, em `health_service.py`, e é
`text("SELECT 1")` — constante. Nenhum `text()` com f-string, `%` ou `.format()`
em `backend/app`. Os outros `text(` que a busca encontra são
`path.read_text(encoding="utf-8")`, sem relação.

**Validação de entrada no backend.** Não é só no frontend. As rotas declaram
faixa: `quantity: int = Query(100, ge=1, le=100_000)`, `return_rate` e as taxas
com `ge=0, le=1`, `spec_*` com `ge=0, le=100`. O preço manual tem `price: int =
Field(gt=0)` e `quality: int = Field(ge=1, le=5)`. A rota do Next valida
também, mas como cortesia — a garantia está no Pydantic, que é justamente o que
continua valendo quando o achado 1 torna a API alcançável direto.

**Nada sem `NEXT_PUBLIC_` vaza para o browser.** Dez usos de `process.env` no
frontend, todos em arquivos de servidor — verificado um a um: nenhum está em
componente com `"use client"`. `lib/auth.ts` e `lib/preferences.ts` têm
`import "server-only"`, que transforma um vazamento futuro em erro de build em
vez de vazamento silencioso. `lib/api.ts` documenta a mesma regra.

**Segredo em log ou em resposta de erro:** nenhum. `SESSION_SECRET`,
`DISCORD_CLIENT_SECRET`, `DATABASE_URL` e `REDIS_URL` não aparecem em
`core/logging.py`, em `main.py` nem nos route handlers.

**Cookie de sessão:** os três presentes.

```ts
httpOnly: true, sameSite: "lax", path: "/", maxAge: SESSION_MAX_AGE,
secure: process.env.NODE_ENV === "production",
```

`lax` é a escolha certa aqui: `strict` quebraria o retorno do OAuth, que chega
por navegação vinda do domínio do Discord. O cookie de `state` usa as mesmas
flags, com `maxAge: 600`.

**Expiração verificada no servidor.** `verificar()` compara `iat` com
`SESSION_MAX_AGE` e não confia só no `max-age` do navegador — um cookie antigo
continua assinado para sempre. Está certo, e é o que limita o achado 5 a 30
dias em vez de para sempre.

**A identidade é propagada, não inventada.** `userHeader()` lê a sessão e só
manda `X-User-Id` quando ela existe; `saveManualPrice`, `deleteManualPrice` e
todo `getJson` a incluem. O preço manual é por usuário de verdade. O que falta
é o backend **provar** que o cabeçalho veio do Next — achado 1.

**`state` obrigatório no OAuth**, com cookie próprio e verificação no callback.
Já estava, e continua.
