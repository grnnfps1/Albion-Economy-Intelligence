import { SidebarNav } from "@/components/SidebarNav";
import { UserChip } from "@/components/UserChip";
import type { Session } from "@/lib/session";

/**
 * Barra lateral: marca, navegação e quem está logado.
 *
 * Fica como componente de servidor porque recebe a sessão; só a navegação é
 * cliente, por causa do `usePathname` que acende o item ativo. Trazer a sessão
 * para o cliente só para pintar um item seria pagar caro por uma cor.
 */
export function Sidebar({ session }: { session: Session | null }) {
  return (
    <nav
      aria-label="Seções"
      className="flex w-full shrink-0 flex-col border-line border-b bg-sunken p-3 md:h-dvh md:w-[188px] md:border-r md:border-b-0 md:p-4"
    >
      <div className="mb-6 hidden md:block">
        <p className="display text-accent text-h2 leading-tight">
          Albion
          <br />
          Economy
        </p>
        {/* Uma régua dourada curta em vez de uma segunda linha de texto: separa
            marca de navegação sem gastar mais uma palavra. */}
        <span
          aria-hidden
          className="mt-1.5 mb-2 block h-px w-8 bg-gradient-to-r from-accent to-transparent"
        />
        <p className="lbl text-dim">Intelligence</p>
      </div>

      <SidebarNav />

      {session && <UserChip session={session} />}
    </nav>
  );
}
