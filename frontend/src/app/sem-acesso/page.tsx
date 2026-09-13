import Link from "next/link";

export default function SemAcessoPage() {
  return (
    <div className="grid min-h-dvh place-items-center px-4">
      <div className="w-full max-w-sm text-center">
        <h1 className="font-semibold text-lg tracking-tight">Acesso restrito</h1>
        <p className="mt-2 text-[12.5px] text-muted leading-relaxed">
          Sua conta do Discord entrou, mas você não está no servidor que dá acesso a esta
          ferramenta. Peça um convite a quem administra e tente de novo.
        </p>
        <Link
          href="/login"
          className="mt-6 inline-block rounded border border-line px-4 py-2 text-[12px] text-muted hover:text-body"
        >
          Voltar
        </Link>
      </div>
    </div>
  );
}
