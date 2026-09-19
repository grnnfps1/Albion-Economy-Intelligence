"use client";

import { useRouter, useSearchParams } from "next/navigation";

/**
 * Cabeçalho que ordena a tabela.
 *
 * Fica em `components/sheet/` e não na tela porque ordenação por coluna tem de
 * se comportar igual em todo lugar. Hoje só o calculador a usa — as telas de
 * ranking ordenam por **pílula** na barra de filtros, que é outro mecanismo em
 * outro lugar. Quando uma delas migrar, migra para cá.
 *
 * ## O ciclo de três cliques
 *
 * | Clique | Estado |
 * |---|---|
 * | 1º | maior para menor |
 * | 2º | menor para maior |
 * | 3º | volta ao padrão da tela |
 *
 * Começar por *descendente* é o que quase sempre se quer de uma coluna de
 * valor: o clique em "lucro" é a pergunta "o que rende mais". O terceiro
 * clique existe para o padrão ser fácil de **recuperar** — no calculador ele é
 * a ordem por tier, que é o motivo de a tabela existir nesse formato, e um
 * padrão que só se recupera recarregando a página deixa de ser padrão.
 *
 * A coluna que já é o padrão tem um ciclo de dois: descendente e de volta.
 *
 * ## Quem decide a ordem é o servidor
 *
 * O clique só reescreve a URL. Comparar lucro é aritmética de negócio e mora no
 * backend (regra 3, com verificação no CI) — aqui não há `sort()` nenhum, e a
 * própria seta vem do que a resposta disse ter usado, não de um estado local.
 * É o mesmo princípio que consertou a pílula "sem focus" na fase 29: a tela não
 * afirma valor de parâmetro cuja fonte é outra.
 */
export type SortState = { by: string; dir: string };

/**
 * A seta só aparece na coluna ativa — e nas outras ela nem ocupa lugar.
 *
 * Uma seta cinza em toda coluna ordenável viraria ruído de doze setas e
 * esconderia qual manda. E uma seta invisível **reservando espaço** faria o
 * rótulo de toda coluna ordenável nascer deslocado em relação ao número.
 */
function Seta({ ativa, dir }: { ativa: boolean; dir: string }) {
  if (!ativa) return null;
  return (
    <span className="text-warn" aria-hidden>
      {dir === "asc" ? "▲" : "▼"}
    </span>
  );
}

export function SortHeader({
  label,
  sortKey,
  ativo,
  padrao,
  title,
  left = false,
}: {
  label: string;
  sortKey: string;
  /** O que a **resposta** disse ter usado. */
  ativo: SortState;
  /** A ordenação de abertura da tela, para onde o terceiro clique volta. */
  padrao: SortState;
  title?: string;
  /**
   * A coluna é de texto (alinhada à esquerda).
   *
   * Muda a **ordem** dos dois elementos, não só o `justify`. Numa coluna
   * numérica o rótulo tem de terminar exatamente onde o número termina, e uma
   * seta depois dele empurraria o último caractere para dentro — por isso ali
   * a seta vem antes. Numa coluna de texto é o espelho: rótulo, depois seta.
   */
  left?: boolean;
}) {
  const router = useRouter();
  const params = useSearchParams();

  const eAtiva = ativo.by === sortKey;
  const proximo: SortState = !eAtiva
    ? { by: sortKey, dir: "desc" }
    : ativo.dir === "desc"
      ? { by: sortKey, dir: "asc" }
      : padrao;

  function ordenar() {
    const next = new URLSearchParams(params.toString());
    next.set("sort_by", proximo.by);
    next.set("sort_dir", proximo.dir);
    router.push(`?${next.toString()}`);
  }

  return (
    <button
      type="button"
      onClick={ordenar}
      title={
        title
          ? `${title} · clique para ordenar`
          : `ordenar por ${label}${eAtiva ? "" : ", do maior para o menor"}`
      }
      aria-sort={eAtiva ? (ativo.dir === "desc" ? "descending" : "ascending") : "none"}
      // `p-0` e `border-0` não são detalhe: qualquer padding próprio do botão
      // desloca o rótulo em relação ao número da coluna, e o desencontro fica
      // visível na vertical porque as outras colunas não têm botão.
      className={`lbl inline-flex w-full cursor-pointer items-baseline gap-1 border-0 bg-transparent p-0 ${
        left ? "justify-start text-left" : "justify-end text-right"
      } ${eAtiva ? "text-body" : "text-dim hover:text-muted"}`}
    >
      {!left && <Seta ativa={eAtiva} dir={ativo.dir} />}
      <span className="truncate">{label}</span>
      {left && <Seta ativa={eAtiva} dir={ativo.dir} />}
    </button>
  );
}
