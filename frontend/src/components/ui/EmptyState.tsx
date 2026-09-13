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
 * A API não respondeu.
 *
 * Separado do vazio de propósito: lista vazia é uma resposta sobre o mercado,
 * API fora é uma resposta sobre nós. Misturar as duas faz o usuário procurar
 * oportunidade onde o problema é infraestrutura.
 */
export function ApiDown() {
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
        <span className="text-down">A API não respondeu.</span>{" "}
        <span className="text-muted">
          Os números desta tela viriam do backend — não há o que mostrar até ele voltar. Veja{" "}
          <a href="/status" className="underline decoration-line-strong hover:text-body">
            Pipeline
          </a>{" "}
          para o estado da coleta.
        </span>
      </p>
    </div>
  );
}
