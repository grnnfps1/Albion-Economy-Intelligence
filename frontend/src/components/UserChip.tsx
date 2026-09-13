import type { Session } from "@/lib/session";

/** Quem está logado, e como sair. Fica no rodapé da barra lateral. */
export function UserChip({ session }: { session: Session }) {
  const avatar = session.avatar
    ? `https://cdn.discordapp.com/avatars/${session.id}/${session.avatar}.png?size=64`
    : null;

  return (
    <form action="/api/auth/logout" method="post" className="mt-auto hidden md:block">
      <div className="flex items-center gap-2 border-line border-t pt-3">
        {avatar ? (
          <img src={avatar} alt="" width={26} height={26} className="rounded-full" />
        ) : (
          <span className="grid size-[26px] place-items-center rounded-full bg-line-strong text-[10px]">
            {session.username.slice(0, 2).toUpperCase()}
          </span>
        )}
        <span className="min-w-0 flex-1 truncate text-[11.5px] text-muted">
          {session.username}
        </span>
        <button type="submit" className="text-[10px] text-dim hover:text-body" title="Sair">
          sair
        </button>
      </div>
    </form>
  );
}
