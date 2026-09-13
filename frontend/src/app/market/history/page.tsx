import Link from "next/link";

import { PriceChart } from "@/components/PriceChart";
import { TrendTag } from "@/components/TrendTag";
import { fetchHistory } from "@/lib/api";
import { formatSilver } from "@/lib/format";

export const dynamic = "force-dynamic";

const PERIODOS = ["24H", "3D", "7D", "14D", "30D", "90D"];

export default async function HistoryPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const get = (key: string) => {
    const value = raw[key];
    return Array.isArray(value) ? value[0] : value;
  };

  const item = get("item");
  const server = get("server") ?? "west";
  const period = get("period") ?? "7D";

  const data = item ? await fetchHistory({ item, server, period }) : null;

  return (
    <div>
      <header className="mb-6">
        <h1 className="font-semibold text-2xl text-body tracking-tight">Histórico</h1>
        <p className="mt-2 max-w-prose text-muted text-sm leading-relaxed">
          O histórico do Albion Online Data Project cobre apenas ordens de venda e vem
          agregado por média. Um único preço manipulado contamina o bucket inteiro, então
          os pontos suspeitos ficam marcados e fora das estatísticas — mas continuam
          visíveis no gráfico.
        </p>
      </header>

      <form className="mb-6 flex flex-wrap items-end gap-2" action="/market/history">
        <input type="hidden" name="server" value={server} />
        <label className="flex min-w-56 flex-col gap-1">
          <span className="text-muted text-xs">Item</span>
          <input
            name="item"
            defaultValue={item ?? ""}
            placeholder="T5_LEATHER"
            className="figure rounded-sm border border-line bg-ink-raised px-2 py-1.5 text-body text-sm"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-muted text-xs">Período</span>
          <select
            name="period"
            defaultValue={period}
            className="rounded-sm border border-line bg-ink-raised px-2 py-1.5 text-body text-sm"
          >
            {PERIODOS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          className="rounded-sm border border-line-strong px-3 py-1.5 text-muted text-sm hover:text-body"
        >
          Ver série
        </button>
      </form>

      {!item && (
        <p className="text-muted text-sm">
          Informe um item para ver a série. Encontre o id técnico em{" "}
          <Link href="/market" className="text-body underline">
            Mercado
          </Link>
          .
        </p>
      )}

      {item && data === null && (
        <div className="rounded-sm border border-down/40 bg-down/5 p-4 text-sm">
          <p className="text-body">Não foi possível carregar a série.</p>
          <p className="mt-1 text-muted">
            Confirme que o item existe no catálogo e que a API está de pé.
          </p>
        </div>
      )}

      {data && data.series.length === 0 && (
        <div className="rounded-sm border border-line bg-ink-raised p-4 text-sm">
          <p className="text-body">Sem histórico para {data.item} neste período.</p>
          <p className="mt-1 max-w-prose text-muted">
            Rode{" "}
            <code className="figure text-body">
              docker compose exec backend python -m app.cli.collect_history --server {server}
            </code>
            . Se já coletou, esse mercado pode simplesmente não ter movimento registrado.
          </p>
        </div>
      )}

      {data?.series.map((serie) => (
        <section key={`${serie.location_slug}-${serie.quality}`} className="mb-10">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-3 border-line border-b pb-2">
            <h2 className="font-medium text-body text-sm">
              {serie.location}
              <span className="figure ml-2 text-muted text-xs">
                Q{serie.quality} · {data.item_name ?? data.item}
              </span>
            </h2>
            <TrendTag trend={serie.trend} changePct={serie.change_pct} />
          </div>

          <PriceChart points={serie.points} median={serie.median} label={serie.location} />

          <dl className="mt-3 flex flex-wrap gap-x-8 gap-y-2 text-xs">
            <Stat label="mediana" value={serie.median} />
            <Stat label="média" value={serie.average} />
            <Stat label="mínimo" value={serie.minimum} />
            <Stat label="máximo" value={serie.maximum} />
            <span className="flex gap-1.5">
              <dt className="text-muted">outliers</dt>
              <dd
                className={`figure ${serie.outlier_count ? "text-warn" : "text-muted"}`}
              >
                {serie.outlier_count}
              </dd>
            </span>
          </dl>
        </section>
      ))}

      {data && data.series.length > 0 && (
        <p className="max-w-prose text-muted text-xs leading-relaxed">
          {data.data_source_note} A linha tracejada é a mediana do período; os círculos no
          topo marcam pontos descartados das estatísticas.
        </p>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | null }) {
  return (
    <span className="flex gap-1.5">
      <dt className="text-muted">{label}</dt>
      <dd className="figure text-body">
        {value === null ? "—" : formatSilver(Math.round(value))}
      </dd>
    </span>
  );
}
