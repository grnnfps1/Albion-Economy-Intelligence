"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { Aviso } from "@/components/sheet/Chrome";
import { COOKIE, type Preferences } from "@/lib/preferences-shared";

/**
 * O estado vazio da taxa da estação.
 *
 * ## Por que existe uma tela inteira para um campo
 *
 * A taxa da estação nasce `UNKNOWN` de propósito (regra 2: não inventar
 * número; regra 5: taxa não é hardcode). A decisão está certa e não muda aqui.
 * O que estava errado era a **consequência visível**: sem ela, as 27 linhas
 * ficavam com traço em oito colunas, e traço repetido não se lê como "falta um
 * dado" — se lê como "quebrou".
 *
 * A tira do topo já dizia "taxa da loja: desconhecida", em âmbar. Não bastou, e
 * a razão é de hierarquia: um rótulo de 10px entre outros cinco parâmetros
 * compete com eles, enquanto o vazio da tabela ocupa a tela inteira. Quando o
 * sintoma é grande e a explicação é pequena, o usuário acredita no sintoma.
 *
 * ## Por que o campo está aqui e não só nas preferências
 *
 * Mandar "informe nas preferências" cria um segundo passo — abrir o painel,
 * achar o campo entre quinze, voltar. Para o único parâmetro que bloqueia a
 * tela inteira, o campo vem junto do aviso. Ele grava exatamente a mesma
 * preferência, no mesmo cookie: é um atalho para o mesmo lugar, não uma
 * segunda fonte de verdade.
 */
export function StationFeePrompt({ prefs }: { prefs: Preferences }) {
  const router = useRouter();
  const [texto, setTexto] = useState("");
  const [pendente, startTransition] = useTransition();
  const [erro, setErro] = useState<string | null>(null);

  function salvar() {
    const numero = parseFloat(texto.trim().replace(",", "."));
    if (!Number.isFinite(numero) || numero < 0) {
      setErro("informe o número que está na tela da estação");
      return;
    }
    setErro(null);
    const proximo: Preferences = { ...prefs, stationFeePer100Nutrition: numero };
    document.cookie = `${COOKIE}=${encodeURIComponent(
      JSON.stringify(proximo),
    )};path=/;max-age=31536000;samesite=lax`;
    startTransition(() => router.refresh());
  }

  // A casca é a mesma de todo aviso de dado incompleto (`Chrome.Aviso`):
  // mesmo lugar, mesma cor, mesma altura. O que esta tela tem a mais — o
  // campo que resolve o aviso ali mesmo — entra pelo `acao`, no esqueleto,
  // em vez de virar um arranjo próprio.
  return (
    <Aviso
      acao={
        <span className="flex items-center gap-1.5">
          <input
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") salvar();
            }}
            disabled={pendente}
            placeholder="ex.: 184"
            aria-label="taxa da estação, em prata por 100 de nutrição"
            className="figure w-[7rem] rounded-sm border border-warn bg-sunken px-1.5 py-px text-right text-note text-body focus:outline-none disabled:opacity-50"
          />
          <span className="text-aux text-muted">prata / 100 nutrição</span>
          <button
            type="button"
            onClick={salvar}
            disabled={pendente}
            className="cursor-pointer rounded-sm border border-line-strong bg-raised px-2.5 py-px text-note text-body hover:border-warn disabled:opacity-50"
          >
            {pendente ? "Aplicando…" : "Calcular"}
          </button>
          {erro && <span className="text-aux text-down">{erro}</span>}
        </span>
      }
    >
      <b>Informe a taxa da estação para calcular.</b>{" "}
      Ela é escolha do dono da estação, muda por cidade e por hora, e está na tela da
      estação dentro do jogo — não há valor defensável para pré-preencher. A planilha de
      referência usava 184, que serve de ordem de grandeza e não de padrão.
    </Aviso>
  );
}
