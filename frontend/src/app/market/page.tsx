import Link from "next/link";

import { MarketFilters } from "@/components/MarketFilters";
import { MarketRow } from "@/components/MarketRow";
import { MarketSort } from "@/components/MarketSort";
import { fetchCatalogMeta, fetchMarketPrices, type MarketQuery } from "@/lib/api";
import { formatSilver } from "@/lib/format";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 100;

export default async function MarketPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const query: MarketQuery = Object.fromEntries(
    Object.entries(raw).map(([key, value]) => [key, Array.isArray(value) ? value[0] : value]),
  );
  query.limit = String(PAGE_SIZE);

  const [meta, page] = await Promise.all([fetchCatalogMeta(), fetchMarketPrices(query)]);

  const params = new URLSearchParams(
    Object.entries(query).filter(([, value]) => value) as [string, string][],
  );
  const offset = Number(query.offset ?? 0);

  return (
    <div>
      <header className="mb-6">
        <h1 className="font-semibold text-2xl text-body tracking-tight">Mercado</h1>
        <p className="mt-2 max-w-prose text-muted text-sm leading-relaxed">
          Preços coletados do Albion Online Data Project. Cada cotação mostra quando foi
          vista no jogo — um preço de ontem continua aparecendo até alguém abrir aquele
          mercado de novo.
        </p>
      </header>

      {meta && (
        <MarketFilters
          servers={meta.servers.map((server) => ({
            value: server.code,
            label: server.display_name,
          }))}
          locations={meta.locations.map((location) => ({
            value: location.slug,
            label: location.display_name,
          }))}
        />
      )}

      {page === null && (
        <div className="rounded-sm border border-down/40 bg-down/5 p-4 text-sm">
          <p className="text-body">A API não respondeu.</p>
          <p className="mt-1 text-muted">
            Verifique com <code className="figure text-body">docker compose ps</code> e{" "}
            <code className="figure text-body">docker compose logs -f backend</code>.
          </p>
        </div>
      )}

      {page !== null && page.total === 0 && (
        <div className="rounded-sm border border-line bg-ink-raised p-4 text-sm">
          <p className="text-body">Nenhum preço para este recorte.</p>
          <p className="mt-1 max-w-prose text-muted">
            Se o banco ainda está vazio, rode a coleta:{" "}
            <code className="figure text-body">
              docker compose exec backend python -m app.cli.collect_market --server{" "}
              {page.server}
            </code>
            . Se já coletou, pode ser que ninguém tenha aberto esse mercado no jogo
            recentemente — ausência de cotação não é preço baixo.
          </p>
        </div>
      )}

      {page !== null && page.total > 0 && (
        <>
          <MarketSort params={params} sortBy={page.sort_by} descending={page.descending} />

          <div>
            {page.prices.map((price) => (
              <MarketRow
                key={`${price.item}-${price.location}-${price.quality}`}
                price={price}
              />
            ))}
          </div>

          <div className="mt-4 flex items-center justify-between text-muted text-xs">
            <span className="figure">
              {formatSilver(offset + 1)}–{formatSilver(offset + page.prices.length)} de{" "}
              {formatSilver(page.total)}
            </span>
            <span className="flex gap-3">
              {offset > 0 && (
                <PageLink params={params} offset={Math.max(0, offset - PAGE_SIZE)}>
                  anterior
                </PageLink>
              )}
              {offset + PAGE_SIZE < page.total && (
                <PageLink params={params} offset={offset + PAGE_SIZE}>
                  próxima
                </PageLink>
              )}
            </span>
          </div>

          <p className="mt-6 max-w-prose text-muted text-xs leading-relaxed">
            {page.data_source_note}
          </p>
        </>
      )}
    </div>
  );
}

function PageLink({
  params,
  offset,
  children,
}: {
  params: URLSearchParams;
  offset: number;
  children: React.ReactNode;
}) {
  const next = new URLSearchParams(params.toString());
  next.set("offset", String(offset));
  return (
    <Link href={`/market?${next.toString()}`} className="hover:text-body">
      {children}
    </Link>
  );
}
