import type { ApiFailure, TipoDeFalha } from "@/lib/api";

/**
 * Lista vazia e API fora do ar, com moldura.
 *
 * O texto já era bom — cada tela explica por que não há linha, em vez de dizer
 * "nenhum resultado". O que faltava era o enquadramento: um parágrafo solto
 * embaixo de um cabeçalho de tabela parece resto de renderização, não resposta.
 *
 * A moldura tracejada é o que diz "aqui teria conteúdo". É a mesma convenção do
 * card indisponível do painel, pelo mesmo motivo: sumir deixaria um buraco sem
 * explicação.
 */
export function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <div className="m-4 flex max-w-prose items-start gap-3 rounded-sm border border-line border-dashed bg-sunken/40 p-4">
      <svg
        aria-hidden
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.4}
        strokeLinecap="round"
        strokeLinejoin="round"
        className="mt-px size-4 shrink-0 text-dim"
      >
        {/* Balança vazia: a leitura é "não há o que pesar", não "deu erro". */}
        <path d="M12 4v16M8 20h8M12 7l-7 2 3.5 6a3.5 3.5 0 01-7 0L5 9M12 7l7 2-3.5 6a3.5 3.5 0 007 0L19 9" />
      </svg>
      <p className="text-muted text-note leading-relaxed">{children}</p>
    </div>
  );
}

/**
 * O que dizer de cada falha, e o que fazer a respeito.
 *
 * As três primeiras pedem **ações opostas**, e chamar todas de "a API não
 * respondeu" mandava investigar a errada. O caso que motivou isto: `/focus`
 * devolvia 500 por um campo mal tipado, e a tela apontava para a
 * infraestrutura — que estava saudável, com o container de pé e as outras
 * telas funcionando.
 */
const FALHAS: Record<TipoDeFalha, { titulo: string; o_que_fazer: React.ReactNode }> = {
  "fora-do-ar": {
    titulo: "O backend não está respondendo.",
    o_que_fazer: (
      <>
        A conexão foi recusada — o serviço provavelmente está parado. Confira com{" "}
        <code>docker compose ps</code>.
      </>
    ),
  },
  "tempo-limite": {
    titulo: "O backend demorou demais.",
    o_que_fazer: (
      <>
        A requisição passou de 10 segundos e foi cancelada. O serviço está de pé; é{" "}
        <b>esta rota</b> que está lenta — não adianta reiniciar nada.
      </>
    ),
  },
  "erro-do-servidor": {
    titulo: "O backend respondeu com erro.",
    o_que_fazer: (
      <>
        Há uma exceção no log, e ela diz exatamente o quê:{" "}
        <code>docker compose logs backend --tail 30</code>. A infraestrutura está bem.
      </>
    ),
  },
  "requisicao-invalida": {
    titulo: "O backend recusou a requisição.",
    o_que_fazer: (
      <>
        Algum parâmetro desta tela saiu fora do que a rota aceita. O log do backend não
        vai ter nada de anormal — o erro está no que foi pedido, não no serviço.
      </>
    ),
  },
};

/**
 * A API não entregou os dados.
 *
 * Separado do vazio de propósito: lista vazia é uma resposta sobre o mercado,
 * API fora é uma resposta sobre nós. Misturar as duas faz o usuário procurar
 * oportunidade onde o problema é infraestrutura.
 *
 * `falha` é opcional para a tela não quebrar quando ninguém a passar — mas sem
 * ela o texto volta a ser o genérico, que é justamente o que se está
 * consertando.
 */
export function ApiDown({ falha }: { falha?: ApiFailure | null }) {
  const detalhe = falha ? FALHAS[falha.tipo] : null;
  return (
    <div className="m-4 flex max-w-prose items-start gap-3 rounded-sm border border-down/30 bg-down-dim/40 p-4">
      <svg
        aria-hidden
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.4}
        strokeLinecap="round"
        strokeLinejoin="round"
        className="mt-px size-4 shrink-0 text-down"
      >
        <path d="M12 8v5M12 17h.01M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z" />
      </svg>
      <p className="text-note leading-relaxed">
        <span className="text-down">{detalhe?.titulo ?? "A API não respondeu."}</span>{" "}
        <span className="text-muted">
          {detalhe ? detalhe.o_que_fazer : "Os números desta tela viriam do backend."} Veja{" "}
          <a href="/status" className="underline decoration-line-strong hover:text-body">
            Pipeline
          </a>{" "}
          para o estado da coleta.
          {falha && (
            <span className="figure mt-1 block text-[10.5px] text-dim">
              {falha.rota}
              {falha.status ? ` · HTTP ${falha.status}` : ""}
            </span>
          )}
        </span>
      </p>
    </div>
  );
}
