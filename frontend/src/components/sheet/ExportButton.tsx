"use client";

import { useState } from "react";

import {
  buildCsvFromSheet,
  download,
  exportFilename,
  type ExportSheet,
} from "@/lib/export";

/**
 * Exporta **o recorte visível**, não o conjunto inteiro.
 *
 * É o comportamento que corresponde ao que a pessoa está vendo: ela filtrou
 * por T5 e refino, clicou em exportar, e espera o T5 de refino. Exportar tudo
 * ignoraria o trabalho que ela acabou de ter com os filtros — e exportar 12 mil
 * linhas quando ela olhava 40 é uma surpresa ruim.
 *
 * Pelo mesmo motivo **o filtro vai no nome do arquivo**: três exportações da
 * mesma tela na pasta de downloads precisam ser distinguíveis sem abrir.
 *
 * ## Erro visível, nunca calado
 *
 * Se a geração falhar — ambiente sem `Blob`, sem `URL.createObjectURL`,
 * qualquer peça que não carregue —, o botão mostra a falha ao lado, em âmbar.
 * Clicar e não acontecer nada é o pior resultado: a pessoa não sabe se o
 * arquivo foi para algum lugar ou se o clique não pegou, e clica de novo.
 */
export function ExportButton({
  sheet,
  screen,
  filters,
  className = "",
}: {
  /** A tabela já achatada pelo servidor — função não atravessa a fronteira
   *  servidor→cliente, então a coluna vira dado antes de chegar aqui. */
  sheet: ExportSheet;
  /** Nome da tela, primeira parte do arquivo: `crafting`, `market`… */
  screen: string;
  /** O recorte em vigor. Entra no nome do arquivo. */
  filters: Record<string, string | number | null | undefined>;
  className?: string;
}) {
  const [erro, setErro] = useState<string | null>(null);

  function exportar() {
    setErro(null);
    try {
      download(exportFilename(screen, filters), buildCsvFromSheet(sheet));
    } catch (e) {
      setErro(e instanceof Error ? e.message : "não foi possível gerar o arquivo");
    }
  }

  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <button
        type="button"
        onClick={exportar}
        disabled={sheet.rows.length === 0}
        title={
          sheet.rows.length === 0
            ? "nada para exportar neste recorte"
            : `exporta as ${sheet.rows.length} linhas visíveis em CSV (separador ;, abre no Excel e no Sheets)`
        }
        className="lbl cursor-pointer rounded-sm border border-line-strong bg-raised px-2.5 py-1 text-body transition-colors hover:border-warn disabled:cursor-not-allowed disabled:opacity-40"
      >
        exportar csv
      </button>
      {erro && (
        <span role="alert" className="text-aux text-warn">
          exportação falhou: {erro}
        </span>
      )}
    </span>
  );
}
