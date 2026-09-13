"use client";

import { useRouter, useSearchParams } from "next/navigation";

type Coluna = { rotulo: string; ordenavel?: string; alinhamento?: "left" | "right" };

/**
 * Cabeçalho da tabela densa.
 *
 * Os rótulos dizem o que o número significa na prática — "você gasta", "você
 * recebe" — e não o nome do campo na API. Rótulo vago esconde taxa.
 */
export function ColumnHeader({
  colunas, columns, ordemPadrao,
}: {
  colunas: Coluna[];
  columns: string;
  ordemPadrao: string;
}) {
  const router = useRouter();
  const params = useSearchParams();
  const atual = params.get("sort_by") ?? ordemPadrao;

  function ordenar(valor: string) {
    const next = new URLSearchParams(params.toString());
    next.set("sort_by", valor);
    next.delete("offset");
    router.push(`?${next.toString()}`);
  }

  return (
    <div
      className="sticky top-0 z-10 grid border-line border-b bg-sunken px-4 py-[7px] text-[10px] text-dim uppercase tracking-[0.06em]"
      style={{ gridTemplateColumns: columns }}
    >
      {colunas.map((coluna) => (
        <span
          key={coluna.rotulo}
          className={coluna.alinhamento === "right" ? "pr-3 text-right" : ""}
        >
          {coluna.ordenavel ? (
            <button
              type="button"
              onClick={() => ordenar(coluna.ordenavel!)}
              className={atual === coluna.ordenavel ? "text-warn" : "hover:text-body"}
            >
              {coluna.rotulo}
            </button>
          ) : (
            coluna.rotulo
          )}
        </span>
      ))}
    </div>
  );
}
