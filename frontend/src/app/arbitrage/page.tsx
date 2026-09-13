import { FeeSettings } from "@/components/FeeSettings";
import { OpportunityRow } from "@/components/OpportunityRow";
import { fetchArbitrage } from "@/lib/api";
import { formatSilver } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function ArbitragePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const query = Object.fromEntries(
    Object.entries(raw).map(([k, v]) => [k, Array.isArray(v) ? v[0] : v]),
  ) as Record<string, string | undefined>;

  const data = await fetchArbitrage({ ...query, limit: "40" });

  return (
    <div>
      <header className="mb-6">
        <h1 className="font-semibold text-2xl text-body tracking-tight">Arbitragem</h1>
        <p className="mt-2 max-w-prose text-muted text-sm leading-relaxed">
          Comprar numa cidade e vender em outra. O spread bruto engana: setup fee e imposto
          de venda comem boa parte dele, e a estratégia paciente paga o setup duas vezes —
          mesmo se a ordem nunca executar.
        </p>
      </header>

      <FeeSettings />

      {data === null && (
        <div className="rounded-sm border border-down/40 bg-down/5 p-4 text-sm">
          <p className="text-body">A API não respondeu.</p>
        </div>
      )}

      {data && !data.fees.complete && (
        <div className="mb-6 rounded-sm border border-warn/40 bg-warn/5 p-4 text-sm leading-relaxed">
          <p className="text-body">Taxas não configuradas — o lucro não é calculado.</p>
          <p className="mt-1 text-muted">
            Preencha o setup fee e o imposto de venda acima. Os valores dependem da sua
            conta: o imposto muda com Premium. Enquanto estiverem vazios, a plataforma
            mostra o spread bruto mas não inventa um lucro — margem sem imposto é sempre
            otimista, e otimista aqui significa recomendar uma operação que perde prata.
          </p>
        </div>
      )}

      {data && data.fees.complete && (
        <p className="mb-4 text-muted text-xs">
          Calculado com setup fee de{" "}
          <span className="figure text-body">
            {((data.fees.setup_fee_pct ?? 0) * 100).toFixed(2)}%
          </span>{" "}
          e imposto de{" "}
          <span className="figure text-body">
            {((data.fees.sales_tax_pct ?? 0) * 100).toFixed(2)}%
          </span>
          {data.fees.premium ? " (Premium)" : ""} · estratégia {data.strategy.toLowerCase()} ·{" "}
          {formatSilver(data.quantity)} unidades · fonte {data.fees.source}
        </p>
      )}

      {data && data.total === 0 && (
        <div className="rounded-sm border border-line bg-ink-raised p-4 text-sm">
          <p className="text-body">Nenhuma rota viável agora.</p>
          <p className="mt-1 max-w-prose text-muted">
            Pode ser que não haja spread suficiente, que as cotações estejam velhas demais,
            ou que o custo de transporte tenha comido a diferença. Nada disso é erro — é o
            mercado.
          </p>
        </div>
      )}

      {data?.opportunities.map((opportunity) => (
        <OpportunityRow
          key={`${opportunity.item}-${opportunity.origin_slug}-${opportunity.destination_slug}-${opportunity.quality}`}
          opportunity={opportunity}
        />
      ))}

      {data && data.total > 0 && (
        <p className="mt-6 max-w-prose text-muted text-xs leading-relaxed">
          {data.data_source_note} O score só é publicado quando há sinal suficiente para
          avaliá-lo: um número alto ao lado de “lucro desconhecido” daria confiança a uma
          oportunidade que ninguém avaliou.
        </p>
      )}
    </div>
  );
}
