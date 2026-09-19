"use client";

import { useRouter, useSearchParams } from "next/navigation";

import type { MaterialReturn, ReturnOption } from "@/lib/api";
import { COOKIE, type Preferences } from "@/lib/preferences-shared";

/**
 * O retorno **antes** do cálculo, e não depois.
 *
 * Esta informação já existia no motor desde a fase 20: a fórmula, os
 * componentes, a melhor cidade e a diferença. O que faltava era ela aparecer na
 * hora de escolher. Um usuário em Caerleon sem Focus via 27 linhas vermelhas e
 * nenhuma pista de que trocar de cidade resolveria — o sistema sabia, e só
 * contava depois de o prejuízo estar na tela.
 *
 * ## Três níveis, porque são três perguntas
 *
 * | Nível | Pergunta | Onde |
 * |---|---|---|
 * | componentes | *de onde vem?* | `18% + 40% + 59% = 117%` |
 * | resultado | *o que entra na conta?* | `retorno 53,9%` |
 * | comparação | *estou perdendo o quê?* | `Martlock daria 36,7%` |
 *
 * Só o resultado seria um número sem alça: correto e inacionável. Só os
 * componentes seriam aritmética sem conclusão. A comparação sozinha não
 * ensinaria a mecânica. Os três juntos transformam o número numa decisão.
 *
 * ## O bônus depende da família, e a tela tem de reagir
 *
 * Martlock dá 40% para couro e **zero** para tábuas. Trocar de aba muda o
 * número, e é por isso que a lista de locais vem do backend por família em vez
 * de ser uma tabela fixa aqui — replicá-la no frontend violaria a regra 3 e
 * divergiria da fórmula no primeiro ajuste.
 */
export function RetornoPainel({
  retorno,
  opcoes,
  familiaLabel,
  prefs,
}: {
  retorno: MaterialReturn;
  opcoes: ReturnOption[];
  familiaLabel: string;
  prefs: Preferences;
}) {
  const router = useRouter();
  const params = useSearchParams();

  /**
   * A cidade é **preferência**; a ilha é **cenário desta tela**.
   *
   * Parece detalhe e não é. A cidade em que você está vale para /market, para
   * arbitragem e para o refino — guardá-la só na URL faria a escolha sumir ao
   * trocar de tela, e deixaria o campo "Comprar em" das preferências mostrando
   * outra coisa. Por isso ela grava o mesmo cookie que o formulário grava: um
   * lugar só, dois caminhos até ele.
   *
   * Produzir na ilha não é onde você está — é uma pergunta que só este
   * calculador faz ("e se eu refinasse na ilha?"). Fica na URL, junto dos
   * outros filtros de cenário, e é compartilhável com o link.
   */
  function escolher(opcao: ReturnOption) {
    const next = new URLSearchParams(params.toString());
    next.set("produce_on_island", opcao.is_island ? "true" : "false");

    if (!opcao.is_island && opcao.slug !== prefs.buyLocation) {
      document.cookie = `${COOKIE}=${encodeURIComponent(
        JSON.stringify({ ...prefs, buyLocation: opcao.slug }),
      )};path=/;max-age=31536000;samesite=lax`;
    }
    router.push(`?${next.toString()}`);
  }

  const atual = opcoes.find((o) => o.is_current);
  const melhor = opcoes.find((o) => o.is_best);
  const perde =
    retorno.rate !== null && melhor?.rate != null ? melhor.rate - retorno.rate : null;

  return (
    <div className="border-line border-b px-4 py-2.5">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1.5">
        {/* Nível 1: de onde vem. As parcelas que **não** se aplicam ficam na
            soma, apagadas — são exatamente o que está sobre a mesa. */}
        <span className="flex flex-wrap items-baseline gap-x-1.5 text-note">
          <span className="lbl">retorno</span>
          {retorno.components.map((parte, i) => (
            <span key={parte.key} className="flex items-baseline gap-1.5">
              {i > 0 && <span className="text-dim">+</span>}
              <span
                className={parte.applies ? "text-body" : "text-dim line-through"}
                title={
                  parte.applies
                    ? `${parte.label}: entra em B`
                    : `${parte.label}: não entra neste cenário`
                }
              >
                {parte.label} {(parte.value * 100).toFixed(0)}%
              </span>
            </span>
          ))}
          {retorno.bonus_total !== null && (
            <>
              <span className="text-dim">=</span>
              <span className="figure text-body">
                B {(retorno.bonus_total * 100).toFixed(0)}%
              </span>
            </>
          )}
        </span>

        {/* Nível 2: o que entra na conta. É o maior número da tira, porque é o
            único que o cálculo usa. */}
        <span className="flex items-baseline gap-1.5">
          <span className="figure font-semibold text-val text-body">
            {retorno.rate === null ? "—" : `${(retorno.rate * 100).toFixed(1)}%`}
          </span>
          <span className="text-aux text-muted" title="B ÷ (1 + B)">
            é o que volta
          </span>
        </span>

        {/* Nível 3: o que se perde. A frase que faltava quando as margens
            apareceram negativas. */}
        {perde !== null && perde > 0.001 && melhor && (
          <span className="text-note text-warn">
            {melhor.is_island
              ? `a ilha daria ${(melhor.rate! * 100).toFixed(1)}%`
              : `${melhor.name} dá ${(melhor.rate! * 100).toFixed(1)}% para ${familiaLabel}`}
            ; aqui você está em {(retorno.rate! * 100).toFixed(1)}% —{" "}
            <b className="font-semibold">
              {(perde * 100).toFixed(1)} pontos a menos
            </b>
          </span>
        )}
        {perde !== null && perde <= 0.001 && (
          <span className="text-note text-up">
            é o melhor cenário desta família com os parâmetros de agora
          </span>
        )}
      </div>

      {/* A lista de locais: a escolha deixa de ser às cegas. */}
      <div className="flex flex-wrap items-center gap-1 pt-2">
        {opcoes.map((opcao) => {
          const ativo = opcao.is_current;
          return (
            <button
              key={opcao.slug}
              type="button"
              onClick={() => escolher(opcao)}
              title={
                opcao.is_island
                  ? "Ilha não tem a base de cidade: sem Focus o retorno é zero de verdade"
                  : opcao.has_city_bonus
                    ? `${opcao.name} tem o bônus de refino desta família`
                    : `${opcao.name} não tem bônus para esta família`
              }
              className={`flex items-baseline gap-1.5 whitespace-nowrap rounded-sm border px-2 py-[5px] text-note ${
                ativo
                  ? "border-line-strong bg-line-strong text-body"
                  : "border-line bg-raised text-muted hover:text-body"
              }`}
            >
              <span>{opcao.name}</span>
              <span
                className={`figure ${
                  opcao.is_best ? "text-up" : ativo ? "text-body" : "text-dim"
                }`}
              >
                {opcao.rate === null ? "—" : `${(opcao.rate * 100).toFixed(1)}%`}
              </span>
            </button>
          );
        })}
      </div>

      {/* A ilha é o único caso em que o Focus não é melhoria marginal. Dizê-lo
          só quando ela está selecionada evita virar ruído nas outras. */}
      {atual?.is_island && (
        <p className="m-0 max-w-prose pt-1.5 text-note text-muted leading-relaxed">
          Na ilha o Focus <b>não é melhoria marginal</b>: é a diferença entre haver retorno e
          não haver. Sem a base de cidade, <code>B</code> é zero e nada volta;{" "}
          {retorno.use_focus ? "com Focus" : "ligando o Focus"} o retorno vai a 37,1%.
        </p>
      )}
    </div>
  );
}
