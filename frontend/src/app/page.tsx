import Link from "next/link";

import { ItemIcon } from "@/components/ui/ItemIcon";
import { OpportunityCard } from "@/components/OpportunityCard";
import { fetchDashboard } from "@/lib/api";
import { feeParams, getPreferences } from "@/lib/preferences";
import { formatDataAge, formatSilver } from "@/lib/format";

export const dynamic = "force-dynamic";

const TOM: Record<string, string> = {
  ATUALIZADO: "text-up",
  DESATUALIZADO: "text-warn",
  ANTIGO: "text-down",
  DESCONHECIDO: "text-muted",
};

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const query = Object.fromEntries(
    Object.entries(raw).map(([k, v]) => [k, Array.isArray(v) ? v[0] : v]),
  ) as Record<string, string | undefined>;

  const prefs = await getPreferences();
  const data = await fetchDashboard({
    ...feeParams(prefs),
    buy_location: prefs.buyLocation,
    sell_location: prefs.sellLocation,
    focus_budget: String(prefs.focusBudget),
    ...query,
  });

  // Um destaque só: o primeiro card com dado. Dois destaques não destacam nada.
  const destacado = data?.cards.findIndex((card) => card.available) ?? -1;

  return (
    <div className="px-4 py-4">
      <header className="mb-6">
        <h1 className="display text-body text-h1">Painel</h1>
        <p className="mt-2 max-w-prose text-muted text-sm leading-relaxed">
          A melhor oportunidade de cada tipo, com a idade do dado que a sustenta. Um número
          grande sobre cotação de ontem não é oportunidade — é retrato antigo.
        </p>
      </header>

      {data === null ? (
        <div className="rounded-sm border border-down/40 bg-down/5 p-4 text-sm">
          <p className="text-body">A API não respondeu.</p>
          <p className="mt-1 text-muted">
            Veja o{" "}
            <Link href="/status" className="text-body underline">
              estado do pipeline
            </Link>
            .
          </p>
        </div>
      ) : (
        <>
          {/* O estado da coleta vem antes dos números. Se o collector parou,
              todos os cards abaixo olham um retrato antigo. */}
          <div
            className={`mb-6 flex flex-wrap items-center gap-x-6 gap-y-1 rounded-sm border p-3 text-xs ${
              data.pipeline.freshness === "ATUALIZADO"
                ? "border-line bg-raised/40"
                : "border-warn/40 bg-warn/5"
            }`}
          >
            <span className="flex gap-1.5">
              <span className="text-muted">última coleta</span>
              <span className={`figure ${TOM[data.pipeline.freshness]}`}>
                {formatDataAge(data.pipeline.last_collection_age_seconds)}
              </span>
            </span>
            <span className="flex gap-1.5">
              <span className="text-muted">preços em base</span>
              <span className="figure text-body">
                {formatSilver(data.pipeline.prices_tracked)}
              </span>
            </span>
            {data.pipeline.stale_price_ratio !== null && (
              <span className="flex gap-1.5">
                <span className="text-muted">desatualizados</span>
                <span
                  className={`figure ${
                    data.pipeline.stale_price_ratio > 0.3 ? "text-warn" : "text-muted"
                  }`}
                >
                  {(data.pipeline.stale_price_ratio * 100).toFixed(0)}%
                </span>
              </span>
            )}
            <Link href="/status" className="ml-auto text-muted hover:text-body">
              pipeline →
            </Link>
          </div>

          {!data.params.complete && (
            <div className="mb-6 rounded-sm border border-warn/40 bg-warn/5 p-4 text-sm leading-relaxed">
              <p className="text-body">Configure as taxas para ver os números.</p>
              <p className="mt-1 text-muted">
                Faltam: <span className="figure">{data.params.missing.join(", ")}</span>. Elas
                dependem da sua conta — o imposto muda com Premium, o retorno muda com Focus
                e especialização. Sem elas o painel mostra o que existe, mas não inventa
                lucro.
              </p>
            </div>
          )}

          <div className="mb-8 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {data.cards.map((card, i) => (
              <OpportunityCard key={card.kind} card={card} destaque={i === destacado} />
            ))}
          </div>

          {data.top_opportunities.length > 0 && (
            <section className="mb-8">
              <h2 className="mb-3 border-line border-b pb-2 font-medium text-body text-sm">
                Top oportunidades
                <span className="ml-2 text-muted text-xs">ordenadas por score</span>
              </h2>
              {data.top_opportunities.map((card) => (
                <Link
                  key={`${card.item}-${card.detail}`}
                  href={card.href}
                  className="flex items-center gap-3 border-line/60 border-b py-2.5 last:border-0 hover:bg-raised/30"
                >
                  <ItemIcon
                    url={card.icon_url}
                    alt={card.item_name ?? ""}
                    tier={card.tier}
                    size={32}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-body text-sm">
                      {card.item_name ?? card.item}
                    </span>
                    <span className="block truncate text-muted text-note">
                      {card.detail}
                    </span>
                  </span>
                  <span className="figure shrink-0 text-up text-sm">
                    {formatSilver(card.headline)}
                  </span>
                  <span
                    className={`figure w-16 shrink-0 text-right text-note ${
                      TOM[card.freshness]
                    }`}
                  >
                    {formatDataAge(card.age_seconds)}
                  </span>
                  <span className="figure w-10 shrink-0 text-right text-body text-sm">
                    {card.score}
                  </span>
                </Link>
              ))}
            </section>
          )}

          <p className="max-w-prose text-muted text-xs leading-relaxed">
            {data.data_source_note}
          </p>
        </>
      )}
    </div>
  );
}
