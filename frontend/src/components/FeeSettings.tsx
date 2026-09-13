"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";

/**
 * Taxas do usuário.
 *
 * Ficam aqui e não numa configuração de servidor porque o imposto depende de a
 * conta ter Premium. Um valor fixo mostraria lucro errado para metade das
 * pessoas.
 *
 * Enquanto não houver contas, o estado mora na URL: o recorte fica
 * compartilhável e sobrevive ao refresh. Quando login existir, isto vira
 * preferência salva sem mudar o cálculo.
 */
export function FeeSettings({
  action = "/arbitrage",
  extraFields = [],
}: {
  action?: string;
  extraFields?: { name: string; label: string; placeholder: string }[];
}) {
  const router = useRouter();
  const params = useSearchParams();
  const [pending, startTransition] = useTransition();

  function aplicar(form: HTMLFormElement) {
    const dados = new FormData(form);
    const next = new URLSearchParams(params.toString());
    const campos = ["setup_fee_pct", "sales_tax_pct", "quantity", "transport_cost_per_unit",
      ...extraFields.map((f) => f.name)];
    for (const chave of campos) {
      const valor = String(dados.get(chave) ?? "").trim();
      if (valor) next.set(chave, valor);
      else next.delete(chave);
    }
    next.set("premium", dados.get("premium") ? "true" : "false");
    next.set("strategy", String(dados.get("strategy") ?? "IMEDIATA"));
    next.delete("offset");
    startTransition(() => router.push(`${action}?${next.toString()}`));
  }

  const campo =
    "figure rounded-sm border border-line bg-ink-raised px-2 py-1.5 text-body text-sm w-24";

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        aplicar(event.currentTarget);
      }}
      className="mb-6 flex flex-wrap items-end gap-3 rounded-sm border border-line bg-ink-raised/40 p-3"
    >
      <label className="flex flex-col gap-1">
        <span className="text-muted text-xs">Setup fee</span>
        <input
          name="setup_fee_pct"
          className={campo}
          placeholder="0.025"
          defaultValue={params.get("setup_fee_pct") ?? ""}
        />
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-muted text-xs">Imposto de venda</span>
        <input
          name="sales_tax_pct"
          className={campo}
          placeholder="0.04"
          defaultValue={params.get("sales_tax_pct") ?? ""}
        />
      </label>
      <label className="flex items-center gap-2 pb-2">
        <input
          type="checkbox"
          name="premium"
          defaultChecked={params.get("premium") === "true"}
          className="size-4 accent-silver"
        />
        <span className="text-body text-sm">Premium</span>
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-muted text-xs">Estratégia</span>
        <select
          name="strategy"
          defaultValue={params.get("strategy") ?? "IMEDIATA"}
          className="rounded-sm border border-line bg-ink-raised px-2 py-1.5 text-body text-sm"
        >
          <option value="IMEDIATA">Imediata</option>
          <option value="PACIENTE">Paciente</option>
        </select>
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-muted text-xs">Quantidade</span>
        <input name="quantity" className={campo} placeholder="100"
               defaultValue={params.get("quantity") ?? ""} />
      </label>
      {action === "/arbitrage" && (
        <label className="flex flex-col gap-1">
          <span className="text-muted text-xs">Transporte/un</span>
          <input name="transport_cost_per_unit" className={campo} placeholder="0"
                 defaultValue={params.get("transport_cost_per_unit") ?? ""} />
        </label>
      )}
      {extraFields.map((field) => (
        <label key={field.name} className="flex flex-col gap-1">
          <span className="text-muted text-xs">{field.label}</span>
          <input name={field.name} className={campo} placeholder={field.placeholder}
                 defaultValue={params.get(field.name) ?? ""} />
        </label>
      ))}
      <button
        type="submit"
        disabled={pending}
        className="rounded-sm border border-line-strong px-3 py-1.5 text-muted text-sm hover:text-body disabled:opacity-50"
      >
        {pending ? "Calculando…" : "Recalcular"}
      </button>
    </form>
  );
}
