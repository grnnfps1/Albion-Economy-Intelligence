import Link from "next/link";

import { FeeSettings } from "@/components/FeeSettings";
import { ItemIcon } from "@/components/ItemIcon";
import { fetchFocus } from "@/lib/api";
import { formatSilver } from "@/lib/format";

export const dynamic = "force-dynamic";

const EXTRA = [
  { name: "return_rate", label: "Retorno de material", placeholder: "0.15" },
  { name: "station_fee", label: "Taxa da estação", placeholder: "100" },
  { name: "focus_budget", label: "Focus disponível", placeholder: "10000" },
  { name: "horizon_days", label: "Dias para escoar", placeholder: "7" },
];

const LIMITADOR: Record<string, { texto: string; tom: string; dica: string }> = {
  FOCUS: {
    texto: "limitado pelo focus",
    tom: "text-body",
    dica: "dá para vender mais do que dá para produzir",
  },
  LIQUIDEZ: {
    texto: "limitado pelo mercado",
    tom: "text-warn",
    dica: "dá para produzir mais do que dá para escoar",
  },
  DESCONHECIDO: {
    texto: "giro desconhecido",
    tom: "text-muted",
    dica: "sem histórico suficiente para saber se o mercado absorve",
  },
};

export default async function FocusPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const query = Object.fromEntries(
    Object.entries(raw).map(([k, v]) => [k, Array.isArray(v) ? v[0] : v]),
  ) as Record<string, string | undefined>;

  const data = await fetchFocus({ ...query, limit: "30" });
  const params = new URLSearchParams(
    Object.entries(query).filter(([, v]) => v) as [string, string][],
  );
  const ordem = query.sort_by ?? "realizable_profit";

  return (
    <div>
      <header className="mb-6">
        <h1 className="font-semibold text-2xl text-body tracking-tight">Focus</h1>
        <p className="mt-2 max-w-prose text-muted text-sm leading-relaxed">
          Prata por Focus é uma taxa, não um ganho. O que você leva para casa é limitado
          pelo Focus que tem e pelo que o mercado absorve — escoar 5.000 unidades de algo
          que gira 3 por dia leva anos, e a margem evapora antes disso.
        </p>
      </header>

      <FeeSettings action="/focus" extraFields={EXTRA} />

      <div className="mb-4 flex flex-wrap items-center gap-3 border-line border-b pb-2 text-xs">
        <span className="text-muted">ordenar por</span>
        {[
          { value: "realizable_profit", label: "ganho realizável" },
          { value: "profit_per_focus", label: "prata por focus" },
        ].map((opcao) => {
          const next = new URLSearchParams(params.toString());
          next.set("sort_by", opcao.value);
          return (
            <Link
              key={opcao.value}
              href={`/focus?${next.toString()}`}
              className={ordem === opcao.value ? "text-body" : "text-muted hover:text-body"}
            >
              {opcao.label}
            </Link>
          );
        })}
      </div>

      {data === null && (
        <div className="rounded-sm border border-down/40 bg-down/5 p-4 text-sm">
          <p className="text-body">A API não respondeu.</p>
        </div>
      )}

      {data && !data.params.complete && (
        <div className="mb-6 rounded-sm border border-warn/40 bg-warn/5 p-4 text-sm leading-relaxed">
          <p className="text-body">Parâmetros faltando — não há ranking.</p>
          <p className="mt-1 text-muted">
            Faltam: <span className="figure">{data.params.missing.join(", ")}</span>.
          </p>
        </div>
      )}

      {data && data.params.complete && data.focus_budget === null && (
        <div className="mb-6 rounded-sm border border-line bg-ink-raised p-3 text-muted text-xs leading-relaxed">
          Sem informar o Focus disponível, o único teto considerado é o mercado. Preencha o
          campo acima para o ranking responder “onde gasto o Focus que eu tenho” em vez de
          “qual a melhor taxa”.
        </div>
      )}

      {data && data.total === 0 && data.params.complete && (
        <div className="rounded-sm border border-line bg-ink-raised p-4 text-sm">
          <p className="text-body">Nenhuma operação com dados suficientes.</p>
        </div>
      )}

      {data?.plans.map((plano) => {
        const limitador = LIMITADOR[plano.limiter] ?? LIMITADOR.DESCONHECIDO;
        return (
          <article
            key={plano.item}
            className="flex flex-wrap items-stretch gap-4 border-line/60 border-b py-3 last:border-0"
          >
            <div className="flex min-w-48 flex-1 gap-3">
              <ItemIcon
                url={plano.icon_url}
                alt={plano.item_name ?? plano.item}
                tier={plano.tier}
                size={52}
              />
              <div className="min-w-0">
                <div className="mb-1 flex items-center gap-1.5">
                  <span className="figure rounded-sm border border-line-strong px-1.5 py-0.5 text-[11px]">
                    T{plano.tier ?? "?"}
                    {plano.enchantment ? `.${plano.enchantment}` : ""}
                  </span>
                  <span className="rounded-sm bg-ink-raised px-1.5 py-0.5 text-[11px] text-muted">
                    {plano.route.toLowerCase()}
                  </span>
                </div>
                <p className="truncate text-body text-sm leading-tight">
                  {plano.item_name ?? plano.item}
                </p>
                <p className="figure truncate text-muted text-[11px]">{plano.item}</p>
              </div>
            </div>

            <div className="min-w-44 flex-1 border-line border-l pl-3">
              <p className="text-muted text-[11px] uppercase tracking-wide">A taxa</p>
              <p className="mb-1.5 text-muted text-[11px]">rendimento por ponto</p>
              <p className="figure text-body text-base">
                {plano.profit_per_focus === null
                  ? "—"
                  : `${formatSilver(plano.profit_per_focus)}/focus`}
              </p>
              <p className="flex justify-between text-[11px]">
                <span className="text-muted">focus por unidade</span>
                <span className="figure text-body">{plano.focus_per_unit}</span>
              </p>
              <p className="flex justify-between text-[11px]">
                <span className="text-muted">lucro por unidade</span>
                <span className="figure text-body">{formatSilver(plano.profit_per_unit)}</span>
              </p>
            </div>

            <div className="min-w-44 flex-1 border-line border-l pl-3">
              <p className="text-muted text-[11px] uppercase tracking-wide">Os dois tetos</p>
              <p className="mb-1.5 text-muted text-[11px]">o menor é quem manda</p>
              <p className="flex justify-between text-[11px]">
                <span className="text-muted">cabe no focus</span>
                <span className="figure text-body">
                  {plano.units_by_focus === null ? "—" : formatSilver(plano.units_by_focus)}
                </span>
              </p>
              <p className="flex justify-between text-[11px]">
                <span className="text-muted">o mercado escoa</span>
                <span className="figure text-body">
                  {plano.units_by_liquidity === null
                    ? "desconhecido"
                    : formatSilver(plano.units_by_liquidity)}
                </span>
              </p>
              <p className={`mt-1 text-[11px] ${limitador.tom}`} title={limitador.dica}>
                {limitador.texto}
              </p>
            </div>

            <div className="min-w-44 flex-1 border-line border-l pl-3">
              <p className="text-muted text-[11px] uppercase tracking-wide">Ganho realizável</p>
              <p className="mb-1.5 text-muted text-[11px]">
                em {data.horizon_days} dia{data.horizon_days > 1 ? "s" : ""}
              </p>
              <p
                className={`figure text-lg ${
                  (plano.realizable_profit ?? 0) > 0 ? "text-up" : "text-down"
                }`}
              >
                {plano.realizable_profit === null
                  ? "—"
                  : `${(plano.realizable_profit ?? 0) > 0 ? "+" : ""}${formatSilver(plano.realizable_profit)}`}
              </p>
              <p className="flex justify-between text-[11px]">
                <span className="text-muted">unidades</span>
                <span className="figure text-body">{formatSilver(plano.units)}</span>
              </p>
              <p className="flex justify-between text-[11px]">
                <span className="text-muted">tempo para escoar</span>
                <span className="figure text-body">
                  {plano.days_to_sell === null ? "—" : `${plano.days_to_sell} d`}
                </span>
              </p>
            </div>
          </article>
        );
      })}

      {data && data.total > 0 && (
        <p className="mt-6 max-w-prose text-muted text-xs leading-relaxed">
          {data.data_source_note}
        </p>
      )}
    </div>
  );
}
