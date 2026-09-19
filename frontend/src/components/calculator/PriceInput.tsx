"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { formatSilver } from "@/lib/format";

/**
 * Preço editável na linha, que recalcula a tabela inteira.
 *
 * ## Por que o recálculo é no servidor
 *
 * A regra 3 do projeto é que **nenhuma aritmética de lucro, margem ou taxa
 * aparece no frontend** — há até verificação no CI. Então "recalcula na hora"
 * não pode ser um `useMemo` refazendo a conta aqui.
 *
 * O caminho é: editar grava um **preço manual** (a tabela da fase 17, que já
 * existe para isto), e `router.refresh()` faz o servidor recalcular e devolver
 * a linha pronta. Uma ida e volta em vez de uma multiplicação local — e em
 * troca a conta é a mesma que o resto do produto usa, sem risco de a tela
 * divergir da API.
 *
 * ## O editado precisa ser distinto do coletado
 *
 * Preço que o usuário digitou e preço que a coleta trouxe têm confiabilidade
 * diferente, e confundi-los é como uma planilha vira decisão errada. O editado
 * fica em âmbar, com o coletado riscado ao lado e um botão de restaurar.
 */
export function PriceInput({
  server,
  location,
  item,
  quality = 1,
  kind,
  value,
  collected,
  isManual,
  ageSeconds,
}: {
  server: string;
  location: string;
  item: string;
  quality?: number;
  /** COMPRA = o que você paga; VENDA = o que você recebe. */
  kind: "COMPRA" | "VENDA";
  value: number | null;
  collected: number | null;
  isManual: boolean;
  ageSeconds: number | null;
}) {
  const router = useRouter();
  const [rascunho, setRascunho] = useState<string>(value === null ? "" : String(value));
  const [pendente, startTransition] = useTransition();
  const [erro, setErro] = useState<string | null>(null);

  async function gravar() {
    const numero = Number(rascunho.replace(/\s/g, "").replace(",", "."));
    if (!Number.isFinite(numero) || numero <= 0) {
      // Zero não é preço, é ausência — e ausência se remove, não se grava.
      setErro("preço precisa ser maior que zero");
      return;
    }
    if (numero === value) return;

    setErro(null);
    const resposta = await fetch("/api/precos-manuais", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ server, location, item, quality, price: numero, kind }),
    });
    if (!resposta.ok) {
      setErro("não foi possível gravar");
      return;
    }
    startTransition(() => router.refresh());
  }

  async function restaurar() {
    setErro(null);
    const params = new URLSearchParams({
      server,
      location,
      item,
      quality: String(quality),
      kind,
    });
    const resposta = await fetch(`/api/precos-manuais?${params}`, { method: "DELETE" });
    if (!resposta.ok) {
      setErro("não foi possível restaurar");
      return;
    }
    setRascunho(collected === null ? "" : String(collected));
    startTransition(() => router.refresh());
  }

  const tom = isManual
    ? "border-warn text-warn"
    : ageSeconds !== null && ageSeconds > 21_600
      ? "border-line text-down"
      : "border-line text-body";

  return (
    <span className="flex flex-col items-end gap-px">
      <span className="flex items-center gap-1">
        <input
          value={rascunho}
          onChange={(e) => setRascunho(e.target.value)}
          onBlur={gravar}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
            if (e.key === "Escape") setRascunho(value === null ? "" : String(value));
          }}
          disabled={pendente}
          aria-label={`preço de ${item}`}
          className={`figure w-[5.6rem] rounded-sm border bg-sunken px-1 py-px text-right text-note focus:border-warn focus:outline-none disabled:opacity-50 ${tom}`}
        />
        {isManual && (
          <button
            type="button"
            onClick={restaurar}
            title="voltar ao preço coletado"
            aria-label="restaurar preço coletado"
            className="cursor-pointer border-0 bg-transparent px-0.5 text-note leading-none text-dim hover:text-body"
          >
            ↺
          </button>
        )}
      </span>

      {isManual && collected !== null && (
        <span className="figure text-micro text-dim line-through" title="o que a coleta dizia">
          {formatSilver(collected)}
        </span>
      )}
      {erro && <span className="text-micro text-down">{erro}</span>}
    </span>
  );
}
