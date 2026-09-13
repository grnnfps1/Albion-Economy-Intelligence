import Link from "next/link";

const OPCOES = [
  { chave: "item", rotulo: "item" },
  { chave: "tier", rotulo: "tier" },
  { chave: "sell_price_min", rotulo: "venda mín" },
  { chave: "buy_price_max", rotulo: "compra máx" },
  { chave: "observed_at", rotulo: "coleta" },
];

export function MarketSort({
  params,
  sortBy,
  descending,
}: {
  params: URLSearchParams;
  sortBy: string;
  descending: boolean;
}) {
  return (
    <div className="mb-2 flex flex-wrap items-center gap-3 border-line border-b pb-2 text-xs">
      <span className="text-muted">ordenar por</span>
      {OPCOES.map((opcao) => {
        const ativo = sortBy === opcao.chave;
        const next = new URLSearchParams(params.toString());
        next.set("sort_by", opcao.chave);
        next.set("descending", ativo && !descending ? "true" : "false");
        next.delete("offset");
        return (
          <Link
            key={opcao.chave}
            href={`/market?${next.toString()}`}
            className={ativo ? "text-body" : "text-muted hover:text-body"}
          >
            {opcao.rotulo}
            {ativo ? (descending ? " ↓" : " ↑") : ""}
          </Link>
        );
      })}
    </div>
  );
}
