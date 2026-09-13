import Link from "next/link";

import { FeeSettings } from "@/components/FeeSettings";
import { RefiningRow } from "@/components/RefiningRow";
import { fetchRefining } from "@/lib/api";

export const dynamic = "force-dynamic";

const EXTRA = [
  { name: "return_rate", label: "Retorno de material", placeholder: "0.15" },
  { name: "station_fee", label: "Taxa da estação", placeholder: "100" },
];

const MODOS = [
  { value: "MAIS_BARATO", label: "mais barato por elo" },
  { value: "MERCADO", label: "comprar tudo pronto" },
  { value: "PRODUZIR", label: "produzir a cadeia" },
];

export default async function RefiningPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const query = Object.fromEntries(
    Object.entries(raw).map(([k, v]) => [k, Array.isArray(v) ? v[0] : v]),
  ) as Record<string, string | undefined>;

  const data = await fetchRefining({ ...query, limit: "40" });
  const params = new URLSearchParams(
    Object.entries(query).filter(([, v]) => v) as [string, string][],
  );
  const modoAtual = query.sourcing ?? "MAIS_BARATO";

  return (
    <div>
      <header className="mb-6">
        <h1 className="font-semibold text-2xl text-body tracking-tight">Refinamento</h1>
        <p className="mt-2 max-w-prose text-muted text-sm leading-relaxed">
          Refino encadeia: T5 precisa de T4, que precisa de T3. A pergunta útil não é “vale
          refinar T5?” e sim onde na cadeia está o gargalo — e se o insumo do tier anterior
          sai mais barato comprando pronto ou produzindo.
        </p>
      </header>

      <FeeSettings action="/refining" extraFields={EXTRA} />

      <div className="mb-4 flex flex-wrap items-center gap-3 border-line border-b pb-2 text-xs">
        <span className="text-muted">custear o insumo</span>
        {MODOS.map((modo) => {
          const next = new URLSearchParams(params.toString());
          next.set("sourcing", modo.value);
          return (
            <Link
              key={modo.value}
              href={`/refining?${next.toString()}`}
              className={modoAtual === modo.value ? "text-body" : "text-muted hover:text-body"}
            >
              {modo.label}
            </Link>
          );
        })}
      </div>

      {data && data.families.length > 1 && (
        <div className="mb-4 flex flex-wrap gap-3 text-xs">
          <span className="text-muted">família</span>
          {["", ...data.families].map((familia) => {
            const next = new URLSearchParams(params.toString());
            if (familia) next.set("family", familia);
            else next.delete("family");
            const ativo = (query.family ?? "") === familia;
            return (
              <Link
                key={familia || "todas"}
                href={`/refining?${next.toString()}`}
                className={ativo ? "text-body" : "text-muted hover:text-body"}
              >
                {familia ? familia.toLowerCase() : "todas"}
              </Link>
            );
          })}
        </div>
      )}

      {data === null && (
        <div className="rounded-sm border border-down/40 bg-down/5 p-4 text-sm">
          <p className="text-body">A API não respondeu.</p>
        </div>
      )}

      {data && !data.params.complete && (
        <div className="mb-6 rounded-sm border border-warn/40 bg-warn/5 p-4 text-sm leading-relaxed">
          <p className="text-body">Parâmetros faltando — o lucro não é calculado.</p>
          <p className="mt-1 text-muted">
            Faltam: <span className="figure">{data.params.missing.join(", ")}</span>. Em refino
            isso pesa mais que em craft avulso: cada elo da cadeia paga a taxa da estação, não
            só o último.
          </p>
        </div>
      )}

      {data && data.total === 0 && (
        <div className="rounded-sm border border-line bg-ink-raised p-4 text-sm">
          <p className="text-body">Nenhum recurso refinado com dados suficientes.</p>
          <p className="mt-1 max-w-prose text-muted">
            A cadeia precisa de cotação de cada elo na cidade escolhida. Um tier sem preço
            interrompe o cálculo dos tiers acima dele.
          </p>
        </div>
      )}

      {data?.opportunities.map((opportunity) => (
        <RefiningRow key={opportunity.item} opportunity={opportunity} />
      ))}

      {data && data.total > 0 && (
        <p className="mt-6 max-w-prose text-muted text-xs leading-relaxed">
          {data.data_source_note}
        </p>
      )}
    </div>
  );
}
