import "server-only";

import { cookies } from "next/headers";

import { COOKIE, DEFAULTS, type Preferences } from "@/lib/preferences-shared";

export { feeParams } from "@/lib/preferences-shared";
export type { Preferences } from "@/lib/preferences-shared";

/**
 * Preferências do usuário, lidas do cookie.
 *
 * Cookie e não URL: a URL obrigava a repetir o formulário em toda tela e a
 * recarregar a cada ajuste. Com cookie, a configuração é feita uma vez e vale
 * em tudo. Quando existir login, vira preferência no banco — o cálculo não
 * muda, só a origem do valor.
 */
export async function getPreferences(): Promise<Preferences> {
  const bruto = (await cookies()).get(COOKIE)?.value;
  if (!bruto) return DEFAULTS;
  try {
    const salvo = JSON.parse(decodeURIComponent(bruto)) as Partial<Preferences>;
    return { ...DEFAULTS, ...salvo };
  } catch {
    // Cookie corrompido não pode derrubar a página inteira.
    return DEFAULTS;
  }
}
