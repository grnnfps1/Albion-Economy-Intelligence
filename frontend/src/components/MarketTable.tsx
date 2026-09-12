import Link from "next/link";

import type { MarketPrice } from "@/lib/api";

import { FreshnessTag } from "./FreshnessTag";
import { PriceCell } from "./PriceCell";

type Column = { key: string; label: string; hint?: string };

/**
 * Buy e sell ficam em grupos visualmente separados.
 *
 * Quem compra do mercado paga `sell min`; quem vende na hora recebe `buy max`.
 * Uma tabela que mistura as quatro colunas faz o usuário ler a linha errada e
 * calcular o lucro invertido.
 */
const COLUMNS: Column[] = [
  { key: "sell_price_min", label: "Venda mín", hint: "o que você paga comprando agora" },
  { key: "sell_price_max", label: "Venda máx" },
  { key: "buy_price_max", label: "Compra máx", hint: "o que você recebe vendendo agora" },
  { key: "buy_price_min", label: "Compra mín" },
];

function sortHref(params: URLSearchParams, key: string): string {
  const next = new URLSearchParams(params.toString());
  const jaOrdenado = next.get("sort_by") === key;
  next.set("sort_by", key);
  next.set("descending", jaOrdenado && next.get("descending") !== "true" ? "true" : "false");
  next.delete("offset");
  return `/market?${next.toString()}`;
}

export function MarketTable({
  prices,
  params,
  sortBy,
  descending,
}: {
  prices: MarketPrice[];
  params: URLSearchParams;
  sortBy: string;
  descending: boolean;
}) {
  return (
    <div className="-mx-5 overflow-x-auto px-5 md:mx-0 md:px-0">
      <table className="w-full min-w-[52rem] border-collapse text-sm">
        <thead>
          <tr className="border-line border-b text-left">
            <th className="py-2 pr-3 font-medium text-muted text-xs">
              <Link href={sortHref(params, "item")} className="hover:text-body">
                Item {sortBy === "item" ? (descending ? "↓" : "↑") : ""}
              </Link>
            </th>
            <th className="py-2 pr-3 font-medium text-muted text-xs">Cidade</th>
            <th className="py-2 pr-3 text-center font-medium text-muted text-xs">Q</th>
            {COLUMNS.map((column) => (
              <th
                key={column.key}
                title={column.hint}
                className="py-2 pr-3 text-right font-medium text-muted text-xs"
              >
                <Link href={sortHref(params, column.key)} className="hover:text-body">
                  {column.label} {sortBy === column.key ? (descending ? "↓" : "↑") : ""}
                </Link>
              </th>
            ))}
            <th className="py-2 text-right font-medium text-muted text-xs">Coleta</th>
          </tr>
        </thead>
        <tbody>
          {prices.map((price) => (
            <tr
              key={`${price.item}-${price.location}-${price.quality}`}
              className="border-line/60 border-b last:border-0"
            >
              <td className="py-2.5 pr-3">
                <span className="block text-body">{price.item_name ?? price.item}</span>
                <span className="figure block text-muted text-xs">
                  {price.item}
                  {price.tier ? ` · T${price.tier}` : ""}
                  {price.enchantment ? `.${price.enchantment}` : ""}
                </span>
              </td>
              <td className="py-2.5 pr-3 text-body">
                {price.location}
                {price.location_kind === "black_market" && (
                  <span className="ml-1 text-muted text-xs">(BM)</span>
                )}
              </td>
              <td className="figure py-2.5 pr-3 text-center text-muted">{price.quality}</td>
              <td className="py-2.5 pr-3 text-right">
                <PriceCell field={price.sell_min} />
              </td>
              <td className="py-2.5 pr-3 text-right">
                <PriceCell field={price.sell_max} />
              </td>
              <td className="py-2.5 pr-3 text-right">
                <PriceCell field={price.buy_max} />
              </td>
              <td className="py-2.5 pr-3 text-right">
                <PriceCell field={price.buy_min} />
              </td>
              <td className="py-2.5 text-right">
                <FreshnessTag
                  freshness={price.observed_freshness}
                  ageSeconds={price.observed_age_seconds}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
