"use client";

import { useState } from "react";

import { PreferencesForm, type CampoPref } from "@/components/PreferencesForm";
import { Toolbar } from "@/components/Toolbar";
import type { Preferences } from "@/lib/preferences-shared";

type Grupo = { chave: string; opcoes: { valor: string; rotulo: string }[]; padrao: string };

/**
 * Cabeçalho comum das telas densas: título, contagem, filtros e o painel de
 * preferências recolhido.
 *
 * O painel fica fechado por padrão porque os valores já vêm preenchidos. Quem
 * quiser precisão abre uma vez.
 */
export function PageShell({
  titulo, descricao, contagem, grupos, busca = true, prefs, acoes, children,
  camposPref,
}: {
  titulo: string;
  descricao: string;
  contagem?: string;
  grupos: Grupo[];
  busca?: boolean;
  prefs: Preferences;
  /** Ações da tela — hoje só a exportação. Fica ao lado da contagem, porque é
   *  exatamente o recorte que ela descreve que vai para o arquivo. */
  acoes?: React.ReactNode;
  /**
   * Quais preferências esta tela usa. Omitir mostra todas.
   *
   * Parâmetro que aparece e não afeta nada ensina o usuário a ignorar o painel
   * inteiro — e a partir daí o que importa também passa despercebido.
   */
  camposPref?: CampoPref[];
  children: React.ReactNode;
}) {
  const [aberto, setAberto] = useState(false);

  return (
    <div className="min-w-0">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 px-4 pt-4 pb-2">
        <h1 className="display text-body text-h1">{titulo}</h1>
        {contagem && <span className="figure text-[11px] text-dim">{contagem}</span>}
        {acoes && <span className="ml-auto">{acoes}</span>}
        <p className="w-full max-w-prose text-muted text-note leading-relaxed">{descricao}</p>
      </div>

      <Toolbar grupos={grupos} busca={busca} onConfig={() => setAberto((v) => !v)} />
      {aberto && <PreferencesForm initial={prefs} campos={camposPref} />}

      {children}
    </div>
  );
}
