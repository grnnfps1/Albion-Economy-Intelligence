import { RefreshButton } from "@/components/RefreshButton";
import { StatusDot } from "@/components/StatusDot";
import { fetchCatalogMeta, fetchPlatformStatus } from "@/lib/api";
import { formatLatency, formatSilver } from "@/lib/format";

export const dynamic = "force-dynamic";

const SERVER_NAMES: Record<string, string> = {
  west: "Americas",
  east: "Asia",
  europe: "Europe",
};

export default async function StatusPage() {
  const [status, meta] = await Promise.all([fetchPlatformStatus(), fetchCatalogMeta()]);

  return (
    <div className="mx-auto max-w-3xl">
      <header className="mb-10">
        <h1 className="font-semibold text-2xl text-body tracking-tight">
          Estado do pipeline
        </h1>
        <p className="mt-2 max-w-prose text-muted text-sm leading-relaxed">
          A plataforma ainda não coleta preços. A fase 1 entrega a infraestrutura, e o
          que faz sentido mostrar agora é se cada peça do caminho do dado está de pé.
        </p>
      </header>

      {!status.reachable && (
        <div className="mb-8 rounded-sm border border-down/40 bg-down/5 p-4">
          <p className="text-body text-sm">A API não respondeu.</p>
          <p className="mt-1 text-muted text-sm">
            {status.error}. Suba o backend com{" "}
            <code className="figure text-body">docker compose up -d backend</code> e
            verifique com{" "}
            <code className="figure text-body">docker compose logs -f backend</code>.
          </p>
        </div>
      )}

      {status.mockData && (
        <div className="mb-8 rounded-sm border border-warn/40 bg-warn/5 p-4 text-sm">
          Esta instância está configurada para dado mock. Nada aqui representa o mercado
          real.
        </div>
      )}

      <section className="mb-10">
        <h2 className="mb-3 border-line border-b pb-2 font-medium text-body text-sm">
          Infraestrutura
        </h2>
        <dl className="divide-y divide-line">
          <Row
            label="API"
            value={<StatusDot status={status.reachable ? "ok" : "down"} />}
            detail={status.version ? `v${status.version} · ${status.environment}` : null}
          />
          <Row
            label="PostgreSQL"
            value={<StatusDot status={status.database?.status} />}
            detail={
              status.database?.detail ?? formatLatency(status.database?.latency_ms ?? null)
            }
          />
          <Row
            label="Redis"
            value={<StatusDot status={status.cache?.status} />}
            detail={status.cache?.detail ?? formatLatency(status.cache?.latency_ms ?? null)}
          />
        </dl>
      </section>

      {meta && (
        <section className="mb-10">
          <h2 className="mb-3 border-line border-b pb-2 font-medium text-body text-sm">
            Catálogo
          </h2>
          <dl className="divide-y divide-line">
            <Row
              label="Itens importados"
              value={<span className="figure text-body text-sm">{formatSilver(meta.catalog.total)}</span>}
              detail="ao-bin-dumps"
            />
            <Row
              label="Itens marcados para coleta"
              value={<span className="figure text-body text-sm">{formatSilver(meta.catalog.tracked)}</span>}
              detail="varridos pelos collectors"
            />
            <Row
              label="Locais de mercado"
              value={<span className="figure text-body text-sm">{meta.locations.length}</span>}
              detail={`${meta.locations.filter((l) => l.kind === "royal_city").length} cidades + Black Market`}
            />
            <Row
              label="Categorias"
              value={<span className="figure text-body text-sm">{meta.categories.length}</span>}
              detail={null}
            />
          </dl>
          {meta.catalog.total === 0 && (
            <p className="mt-4 text-muted text-sm">
              O catálogo está vazio. Importe com{" "}
              <code className="figure text-body">
                docker compose exec backend python -m app.cli.import_items
              </code>
              .
            </p>
          )}
        </section>
      )}

      <section className="mb-10">
        <h2 className="mb-3 border-line border-b pb-2 font-medium text-body text-sm">
          Fonte de mercado
        </h2>
        <dl className="divide-y divide-line">
          {status.aodp.length === 0 && (
            <p className="py-3 text-muted text-sm">Sem resposta da fonte.</p>
          )}
          {status.aodp.map((server) => (
            <Row
              key={server.server}
              label={SERVER_NAMES[server.server] ?? server.server}
              value={<StatusDot status={server.status} />}
              detail={server.detail ?? formatLatency(server.latency_ms)}
            />
          ))}
        </dl>
        <p className="mt-4 max-w-prose text-muted text-xs leading-relaxed">
          Os preços vêm do Albion Online Data Project, que depende de jogadores abrirem o
          mercado no jogo com o client de coleta. Um mercado pouco visitado tem cotação
          velha ou nenhuma. Por isso toda tela do produto mostra a idade do dado, e
          ausência de preço nunca é exibida como zero.
        </p>
      </section>

      <RefreshButton />
    </div>
  );
}

function Row({
  label,
  value,
  detail,
}: {
  label: string;
  value: React.ReactNode;
  detail: string | null;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <dt className="text-body text-sm">{label}</dt>
      <dd className="flex items-center gap-4">
        {detail && <span className="figure text-muted text-xs">{detail}</span>}
        {value}
      </dd>
    </div>
  );
}
