import Link from "next/link";

export const dynamic = "force-dynamic";

const ERROS: Record<string, string> = {
  recusado: "Você cancelou a autorização no Discord.",
  estado: "A sessão de login expirou ou o link não veio do lugar certo. Tente de novo.",
  token: "O Discord recusou a troca de credencial. Tente de novo em alguns instantes.",
  discord: "Não foi possível ler seu perfil no Discord.",
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const erro = typeof raw.erro === "string" ? raw.erro : null;

  return (
    <div className="grid min-h-dvh place-items-center px-4">
      <div className="w-full max-w-sm text-center">
        <h1 className="font-semibold text-xl tracking-tight">Albion Economy Intelligence</h1>
        <p className="mt-2 text-note text-muted leading-relaxed">
          Acesso para quem está no servidor do Discord. Entre com sua conta para continuar.
        </p>

        {erro && (
          <p className="mt-4 rounded border border-down/40 bg-down/5 p-3 text-note text-body">
            {ERROS[erro] ?? "Não foi possível entrar."}
          </p>
        )}

        <Link
          href="/api/auth/discord/login"
          className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded border border-line-strong bg-raised px-4 py-2.5 text-val text-body hover:border-warn"
        >
          Entrar com Discord
        </Link>

        <p className="mt-6 text-note text-dim leading-relaxed">
          Pedimos apenas seu nome, avatar e a lista de servidores — é como o acesso é
          verificado. Nada é publicado no seu Discord.
        </p>
      </div>
    </div>
  );
}
