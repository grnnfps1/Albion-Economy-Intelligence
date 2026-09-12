"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";

type Option = { value: string; label: string };

/**
 * Filtros como parâmetros de URL.
 *
 * Assim um recorte útil é compartilhável e sobrevive ao refresh — é o que se
 * espera de uma ferramenta que alguém vai consultar várias vezes por dia.
 */
export function MarketFilters({
  servers,
  locations,
}: {
  servers: Option[];
  locations: Option[];
}) {
  const router = useRouter();
  const params = useSearchParams();
  const [pending, startTransition] = useTransition();

  function update(key: string, value: string) {
    const next = new URLSearchParams(params.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    next.delete("offset");
    startTransition(() => router.push(`/market?${next.toString()}`));
  }

  const field = "rounded-sm border border-line bg-ink-raised px-2 py-1.5 text-body text-sm";

  return (
    <div className="mb-6 flex flex-wrap items-end gap-2" data-pending={pending}>
      <label className="flex flex-col gap-1">
        <span className="text-muted text-xs">Servidor</span>
        <select
          className={field}
          value={params.get("server") ?? "west"}
          onChange={(event) => update("server", event.target.value)}
        >
          {servers.map((server) => (
            <option key={server.value} value={server.value}>
              {server.label}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-muted text-xs">Cidade</span>
        <select
          className={field}
          value={params.get("locations") ?? ""}
          onChange={(event) => update("locations", event.target.value)}
        >
          <option value="">Todas</option>
          {locations.map((location) => (
            <option key={location.value} value={location.value}>
              {location.label}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-muted text-xs">Tier</span>
        <select
          className={field}
          value={params.get("tier") ?? ""}
          onChange={(event) => update("tier", event.target.value)}
        >
          <option value="">Todos</option>
          {[1, 2, 3, 4, 5, 6, 7, 8].map((tier) => (
            <option key={tier} value={tier}>
              T{tier}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-muted text-xs">Encanto</span>
        <select
          className={field}
          value={params.get("enchantment") ?? ""}
          onChange={(event) => update("enchantment", event.target.value)}
        >
          <option value="">Todos</option>
          {[0, 1, 2, 3, 4].map((enchantment) => (
            <option key={enchantment} value={enchantment}>
              .{enchantment}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-muted text-xs">Qualidade</span>
        <select
          className={field}
          value={params.get("qualities") ?? ""}
          onChange={(event) => update("qualities", event.target.value)}
        >
          <option value="">Todas</option>
          {[1, 2, 3, 4, 5].map((quality) => (
            <option key={quality} value={quality}>
              Q{quality}
            </option>
          ))}
        </select>
      </label>

      <label className="flex min-w-48 flex-1 flex-col gap-1">
        <span className="text-muted text-xs">Item</span>
        <input
          className={field}
          type="search"
          placeholder="couro, T5_LEATHER…"
          defaultValue={params.get("search") ?? ""}
          onKeyDown={(event) => {
            if (event.key === "Enter") update("search", event.currentTarget.value);
          }}
        />
      </label>
    </div>
  );
}
