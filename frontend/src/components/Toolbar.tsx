"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

type Grupo = { chave: string; opcoes: { valor: string; rotulo: string }[]; padrao: string };

/**
 * Filtros como pílulas, não como formulário.
 *
 * Um clique troca o recorte. O estado vai para a URL, então o recorte é
 * compartilhável — mas sem os campos de taxa, que agora vivem nas preferências.
 */
export function Toolbar({
  grupos, busca = true, onConfig,
}: {
  grupos: Grupo[];
  busca?: boolean;
  onConfig?: () => void;
}) {
  const router = useRouter();
  const params = useSearchParams();
  const [texto, setTexto] = useState(params.get("search") ?? "");

  function aplicar(chave: string, valor: string) {
    const next = new URLSearchParams(params.toString());
    if (valor) next.set(chave, valor);
    else next.delete(chave);
    next.delete("offset");
    router.push(`?${next.toString()}`);
  }

  return (
    <div className="flex flex-wrap items-center gap-2 border-line border-b px-4 py-2.5">
      {grupos.map((grupo) => {
        const atual = params.get(grupo.chave) ?? grupo.padrao;
        return (
          <div key={grupo.chave} className="flex items-center gap-1 rounded border border-line bg-raised p-0.5">
            {grupo.opcoes.map((opcao) => (
              <button
                key={opcao.valor}
                type="button"
                onClick={() => aplicar(grupo.chave, opcao.valor)}
                className={`whitespace-nowrap rounded-[3px] px-2.5 py-[5px] text-[11px] ${
                  atual === opcao.valor ? "bg-line-strong text-body" : "text-muted hover:text-body"
                }`}
              >
                {opcao.rotulo}
              </button>
            ))}
          </div>
        );
      })}

      {busca && (
        <input
          type="search"
          value={texto}
          placeholder="buscar item…"
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") aplicar("search", texto.trim());
          }}
          className="max-w-72 min-w-40 flex-1 rounded border border-line bg-raised px-2.5 py-1.5 text-[12px] text-body"
        />
      )}

      {onConfig && (
        <button
          type="button"
          onClick={onConfig}
          className="rounded border border-line bg-raised px-3 py-1.5 text-[11px] text-muted hover:border-line-strong hover:text-body"
        >
          ⚙ taxas e focus
        </button>
      )}
    </div>
  );
}
