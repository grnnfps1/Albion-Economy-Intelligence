import type { Session } from "@/lib/session";

/**
 * Quem está logado, e como sair. Fica no rodapé da barra lateral.
 *
 * O botão de sair era um "sair" de 10px na cor mais apagada da paleta, do lado
 * de um nome truncado — parecia legenda, não ação. Agora é um alvo de clique de
 * verdade, com borda e área própria.
 */
export function UserChip({ session }: { session: Session }) {
  const avatar = session.avatar
    ? `https://cdn.discordapp.com/avatars/${session.id}/${session.avatar}.png?size=64`
    : null;

  return (
    <form action="/api/auth/logout" method="post" className="mt-auto hidden pt-4 md:block">
      <div className="flex items-center gap-2.5 border-line border-t pt-3">
        {avatar ? (
          // Avatar único, do CDN do Discord: um <img> direto, como os ícones
          // de item. Um salto pelo otimizador do Next para uma imagem de 28px
          // custa mais do que economiza.
          <img
            src={avatar}
            alt=""
            width={28}
            height={28}
            className="size-7 rounded-full border border-line"
          />
        ) : (
          <span className="grid size-7 shrink-0 place-items-center rounded-full border border-line bg-raised font-medium text-aux text-muted">
            {session.username.slice(0, 2).toUpperCase()}
          </span>
        )}
        <span className="min-w-0 flex-1 truncate text-body text-note" title={session.username}>
          {session.username}
        </span>
      </div>

      <button
        type="submit"
        className="mt-2 w-full rounded-sm border border-line px-3 py-1.5 text-muted text-note transition-colors duration-150 hover:border-line-strong hover:bg-raised hover:text-body"
      >
        Sair
      </button>
    </form>
  );
}
