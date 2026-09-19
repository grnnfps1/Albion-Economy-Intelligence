"use client";

import { useState } from "react";

import { PreferencesForm } from "@/components/PreferencesForm";
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
  children: React.ReactNode;
}) {
  const [aberto, setAberto] = useState(false);

  return (
    // Coluna de altura limitada: o cabeçalho, os filtros e o painel de
    // preferências mantêm a altura natural, e o que sobrar vai para `children`
    // — onde mora a tabela, que é quem rola.
    <div className="flex min-w-0 flex-col md:min-h-0 md:flex-1">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 px-4 pt-4 pb-2">
        <h1 className="display text-body text-h1">{titulo}</h1>
        {contagem && <span className="figure text-[11px] text-dim">{contagem}</span>}
        {acoes && <span className="ml-auto">{acoes}</span>}
        <p className="w-full max-w-prose text-muted text-note leading-relaxed">{descricao}</p>
      </div>

      <Toolbar grupos={grupos} busca={busca} onConfig={() => setAberto((v) => !v)} />
      {aberto && <PreferencesForm initial={prefs} />}

      <div className="flex min-w-0 flex-col md:min-h-0 md:flex-1">{children}</div>
    </div>
  );
}
