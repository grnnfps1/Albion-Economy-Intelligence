"use client";

import { useState } from "react";

/**
 * A explicação da tela, recolhida por padrão.
 *
 * ## Por que recolher, e não mover
 *
 * O texto é bom e precisa continuar existindo — mas **explicação não pode
 * ocupar mais tela que o dado que explica**. Como irmão da tabela, ele entrava
 * na conta de altura (`SheetScroll` subtrai o que vem depois) e comia um terço
 * da janela: a tabela do calculador ficou com cinco linhas e meia, para uma
 * família de 27.
 *
 * Foram consideradas três saídas, e as outras duas têm defeito de natureza:
 *
 * | Saída | Por que não |
 * |---|---|
 * | ao fim da tabela, **dentro** da área rolável | só se alcança depois de rolar 27 linhas, e o contêiner rola nos **dois** eixos — prosa deslizando para o lado não se lê |
 * | balão no ícone de ajuda | `hover-tip` é `::after` com 22rem de largura máxima: dois parágrafos ali ficam ilegíveis, não se selecionam para copiar e somem no toque |
 *
 * Recolhido custa uma linha de ~24px, continua sendo texto de verdade —
 * selecionável, copiável, acessível pelo teclado — e a conta de altura fica
 * coerente sozinha: medindo a altura **real** do elemento, abrir encolhe a
 * tabela e fechar a devolve, sem caso especial em lugar nenhum.
 */
export function ComoLer({ children }: { children: React.ReactNode }) {
  const [aberto, setAberto] = useState(false);

  return (
    <div className="border-line border-t">
      <button
        type="button"
        onClick={() => setAberto((v) => !v)}
        aria-expanded={aberto}
        className="flex w-full cursor-pointer items-center gap-1.5 border-0 bg-transparent px-4 py-1.5 text-left text-note text-dim hover:text-body"
      >
        <span aria-hidden>{aberto ? "▾" : "▸"}</span>
        <span>como ler esta tabela</span>
      </button>
      {aberto && children}
    </div>
  );
}
