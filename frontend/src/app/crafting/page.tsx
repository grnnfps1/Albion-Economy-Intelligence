import { CraftRow } from "@/components/CraftRow";
import { FeeSettings } from "@/components/FeeSettings";
import { fetchCrafting } from "@/lib/api";

export const dynamic = "force-dynamic";

const EXTRA = [
  { name: "return_rate", label: "Retorno de material", placeholder: "0.15" },
  { name: "station_fee", label: "Taxa da estação", placeholder: "100" },
  { name: "crafts", label: "Execuções", placeholder: "1" },
];

export default async function CraftingPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const query = Object.fromEntries(
    Object.entries(raw).map(([k, v]) => [k, Array.isArray(v) ? v[0] : v]),
  ) as Record<string, string | undefined>;

  const data = await fetchCrafting({ ...query, limit: "30" });

  return (
    <div>
      <header className="mb-6">
        <h1 className="font-semibold text-2xl text-body tracking-tight">Crafting</h1>
        <p className="mt-2 max-w-prose text-muted text-sm leading-relaxed">
          O ranking ordena por prata por focus, não por lucro absoluto. Focus é o recurso
          escasso: um craft que rende mais prata gastando três vezes mais focus é o pior
          negócio dos dois.
        </p>
      </header>

      <FeeSettings action="/crafting" extraFields={EXTRA} />

      {data === null && (
        <div className="rounded-sm border border-down/40 bg-down/5 p-4 text-sm">
          <p className="text-body">A API não respondeu.</p>
        </div>
      )}

      {data && !data.params.complete && (
        <div className="mb-6 rounded-sm border border-warn/40 bg-warn/5 p-4 text-sm leading-relaxed">
          <p className="text-body">Parâmetros faltando — o lucro não é calculado.</p>
          <p className="mt-1 text-muted">
            Faltam: <span className="figure">{data.params.missing.join(", ")}</span>. Nenhum
            deles é constante: o retorno muda com Focus e especialização, a taxa da estação é
            definida pelo dono e varia por cidade, e o imposto muda com Premium. Uma
            calculadora que fixa os três está errada para quase todo mundo.
          </p>
        </div>
      )}

      {data && data.params.complete && (
        <p className="mb-4 text-muted text-xs">
          Retorno de{" "}
          <span className="figure text-body">
            {((data.params.return_rate ?? 0) * 100).toFixed(1)}%
          </span>
          , estação a <span className="figure text-body">{data.params.station_fee}</span> por
          craft, imposto de{" "}
          <span className="figure text-body">
            {((data.params.fees.sales_tax_pct ?? 0) * 100).toFixed(2)}%
          </span>
          {data.params.fees.premium ? " (Premium)" : ""} · {data.crafts} execução(ões) ·
          comprando em {data.buy_location}, vendendo em {data.sell_location}
        </p>
      )}

      {data && data.total === 0 && (
        <div className="rounded-sm border border-line bg-ink-raised p-4 text-sm">
          <p className="text-body">Nenhuma receita com dados suficientes.</p>
          <p className="mt-1 max-w-prose text-muted">
            As receitas vêm do dump do jogo, mas o custo precisa de cotação de cada material
            na cidade escolhida. Rode a coleta e tente outra cidade.
          </p>
        </div>
      )}

      {data?.opportunities.map((opportunity) => (
        <CraftRow
          key={`${opportunity.item}-${opportunity.recipe_variant}`}
          opportunity={opportunity}
        />
      ))}

      {data && data.total > 0 && (
        <p className="mt-6 max-w-prose text-muted text-xs leading-relaxed">
          {data.data_source_note}
        </p>
      )}
    </div>
  );
}
