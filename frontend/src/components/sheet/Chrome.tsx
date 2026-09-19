/**
 * O esqueleto das telas densas.
 *
 * ## Por que existe
 *
 * As seis telas foram nascendo uma a uma e cada uma resolveu o mesmo problema
 * do seu jeito: a faixa de parâmetros tinha altura diferente em cada, o aviso
 * de dado incompleto aparecia em lugares diferentes com formatos diferentes, e
 * o texto auxiliar usava **dez** tamanhos distintos — 8,5px, 9, 9,5, 10, 10,5,
 * 11, 11,5, 12, 13 e 15. Lado a lado pareciam produtos diferentes.
 *
 * Uniformidade aqui é **requisito, não consequência**: ela não sai de usar os
 * mesmos componentes, sai de as telas não terem onde divergir. Por isso a
 * faixa, o aviso e os tamanhos moram neste arquivo, e uma tela que precise de
 * algo a mais o encaixa no mesmo esqueleto em vez de montar o seu.
 */

/**
 * Tamanho de ícone, por papel.
 *
 * Um número por papel, não por tela. O calculador usava 38 na identidade e 30
 * no material, com a justificativa (fase 19) de que "são 27 linhas para
 * examinar, não 40 para varrer" — e o efeito colateral era ele parecer outro
 * produto ao lado do ranking. Uniformidade ganhou, e de quebra a tela ficou
 * mais densa, que era o outro pedido.
 */
export const SHEET_ICON = {
  /** Identidade da linha: o item de que a linha trata. */
  linha: 22,
  /** Material ou entrada, dentro de uma coluna estreita. */
  material: 20,
} as const;

/**
 * A faixa de parâmetros, igual em todas as telas.
 *
 * Mesma altura, mesmo espaçamento, mesmo tratamento de rótulo — porque é a
 * primeira coisa abaixo dos filtros em todas elas, e altura diferente ali é o
 * que mais faz duas telas parecerem de produtos diferentes.
 */
export function ParamStrip({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-[2.125rem] flex-wrap items-center gap-x-5 gap-y-1 border-line border-b px-4 py-2 text-note">
      {children}
    </div>
  );
}

/** Um parâmetro da faixa: rótulo em caixa alta, valor em fonte de número. */
export function Param({
  rotulo,
  valor,
  dica,
  tom,
}: {
  rotulo: string;
  valor: React.ReactNode;
  dica?: string;
  /** `warn` para parâmetro ausente ou não verificado. */
  tom?: "warn";
}) {
  return (
    <span className="flex items-center gap-1.5" title={dica}>
      <span className="lbl">{rotulo}</span>
      <span className={`figure ${tom === "warn" ? "text-warn" : "text-body"}`}>{valor}</span>
    </span>
  );
}

/**
 * O aviso de dado incompleto — sempre **antes** dos números.
 *
 * O lugar é a regra, não o texto. Em `/agricultura` as ressalvas existiam no
 * rodapé, embaixo de uma tabela mostrando margem de −3.307%: quando o sintoma é
 * grande e a explicação está longe, o usuário acredita no sintoma e conclui que
 * a conta quebrou, quando ela está incompleta **e dizendo isso**. O mesmo já
 * tinha acontecido com a taxa da estação no calculador.
 *
 * Fica curto de propósito. O texto longo vive no `ComoLer`, ao pé da tabela.
 */
export function Aviso({
  children,
  acao,
}: {
  children: React.ReactNode;
  /** Um campo ou botão que resolve o aviso ali mesmo, sem trocar de tela. */
  acao?: React.ReactNode;
}) {
  return (
    <div className="border-warn/40 border-b bg-warn/5 px-4 py-2">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <p className="m-0 max-w-prose text-note text-warn leading-relaxed">{children}</p>
        {acao}
      </div>
    </div>
  );
}

type Taxas = {
  setup_fee_pct: number | null;
  sales_tax_pct: number | null;
  premium: boolean | null;
};

/** Percentual, ou traço quando o parâmetro não foi informado (regra 1). */
export function pctOuTraco(v: number | null | undefined): string {
  return v === null || v === undefined ? "—" : `${(v * 100).toFixed(1)}%`;
}

function pct(v: number | null): string {
  return v === null ? "—" : `${(v * 100).toFixed(1)}%`;
}

/**
 * Os dois parâmetros que **toda** tela de cálculo usa.
 *
 * Imposto e setup fee aparecem em craft, refino, focus, arbitragem,
 * agricultura e no calculador — e antes só o calculador os mostrava. Uma tela
 * que calcula lucro sem dizer com que imposto calculou está pedindo confiança
 * sem dar como conferir; e duas telas que os mostram de jeitos diferentes
 * fazem o usuário reaprender a ler.
 */
export function ParamsDeTaxa({ fees }: { fees: Taxas | null | undefined }) {
  if (!fees) return null;
  return (
    <>
      <Param
        rotulo="imposto"
        valor={pct(fees.sales_tax_pct)}
        tom={fees.sales_tax_pct === null ? "warn" : undefined}
        dica={
          fees.premium === null
            ? "4% com Premium, 8% sem — medido no jogo na fase 21"
            : fees.premium
              ? "4%, conta com Premium"
              : "8%, conta sem Premium"
        }
      />
      <Param
        rotulo="setup fee"
        valor={pct(fees.setup_fee_pct)}
        tom={fees.setup_fee_pct === null ? "warn" : undefined}
        dica="cobrado ao criar a ordem, e pago mesmo que ela não execute"
      />
    </>
  );
}

/**
 * A segunda linha de uma célula.
 *
 * ## A regra, lida do Calculador
 *
 * O Calculador usa `lbl` — caixa alta com tracking — **só** sob valores de
 * tamanho normal (a coluna de focus). Sob o número que decide, ele não usa
 * nada: o lucro fica sozinho na célula, e a margem, que é o mesmo fato em
 * razão, leva um sub-texto **minúsculo e apagado**.
 *
 * Refino e Focus colavam `lbl` embaixo do número grande e colorido —
 * `+1.326.913,49` com `6,61 UN · FOCUS` logo abaixo. Duas ênfases empilhadas
 * viram um bloco pesado, e o olho não sabe qual das duas ler primeiro.
 *
 * `Sub` é o sub-texto quieto: mesma cor apagada, mesma caixa baixa, mesmo
 * respiro. Quem precisa de rótulo em caixa alta usa `lbl`, e só sob valor
 * pequeno.
 */
export function Sub({ children, tom }: { children: React.ReactNode; tom?: "warn" }) {
  return (
    <span className={`mt-px block text-micro ${tom === "warn" ? "text-warn" : "text-dim"}`}>
      {children}
    </span>
  );
}

/**
 * Um acento de cor por linha.
 *
 * O Calculador colore **o lucro e a margem** — o número que decide e o mesmo
 * fato em razão, lado a lado — e deixa todo o resto neutro. Refino coloria
 * também prata/focus, lucro/dia e a idade; arbitragem enchia a linha de
 * pílulas (MODERADA, zona azul, RUIM). Com tudo colorido, nada se destaca, e a
 * cor deixa de carregar informação para virar decoração — que é exatamente o
 * que a linguagem visual do projeto proíbe.
 *
 * Use em qualquer número que **não** seja o lucro da linha.
 */
export const TOM_NEUTRO = "text-body";
