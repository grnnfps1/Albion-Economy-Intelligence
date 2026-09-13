/**
 * Cor de tier, num lugar só.
 *
 * Antes cada componente carregava seu próprio mapa de tier para classe, e eles
 * já tinham divergido: um pintava T4 com a cor de lucro, outro com a cor do
 * jogo. Numa tela em que cor é informação, dois mapas diferentes para a mesma
 * coisa é o mesmo que nenhum.
 *
 * A escala é a do próprio jogo — T4 azul, T5 vermelho, T6 laranja, T7 dourado,
 * T8 branco — e por isso não é negociável por gosto: o jogador já a conhece de
 * fora da plataforma.
 *
 * Os valores são nomes de token do Tailwind (`t1`…`t8`), não hex. Quem quiser a
 * cor muda `globals.css`, e todo mundo acompanha.
 */
const TIERS = [1, 2, 3, 4, 5, 6, 7, 8] as const;

export type Tier = (typeof TIERS)[number];

function isTier(tier: number | null | undefined): tier is Tier {
  return typeof tier === "number" && tier >= 1 && tier <= 8;
}

/** Nome do token de cor do tier, ou o token neutro quando o tier é desconhecido. */
export function tierColor(tier: number | null | undefined): string {
  return isTier(tier) ? `t${tier}` : "line-strong";
}

/** Classe de texto na cor do tier. */
export function tierText(tier: number | null | undefined): string {
  return `text-${tierColor(tier)}`;
}

/** Classe de fundo na cor do tier. */
export function tierBg(tier: number | null | undefined): string {
  return `bg-${tierColor(tier)}`;
}

/** Classe de borda na cor do tier, com opacidade — moldura não compete com o dado. */
export function tierBorder(tier: number | null | undefined, opacity = 50): string {
  return `border-${tierColor(tier)}/${opacity}`;
}

/**
 * Faixa de tier à esquerda da linha densa.
 *
 * Tier desconhecido devolve transparente, e não o token neutro: a faixa é o
 * primeiro sinal que o olho pega numa lista de quarenta linhas, e uma faixa
 * cinza afirma "tier baixo" quando a verdade é "não sei".
 */
export function tierBorderLeft(tier: number | null | undefined): string {
  return isTier(tier) ? `border-l-t${tier}` : "border-l-transparent";
}

/**
 * Fundo tingido pelo tier, bem fraco.
 *
 * 10% é o teto: acima disso o fundo começa a competir com o número que está
 * por cima, e a moldura já carrega a mesma informação.
 */
export function tierTint(tier: number | null | undefined): string {
  return `bg-${tierColor(tier)}/10`;
}

/**
 * Todas as classes que `tierColor` pode gerar, para o Tailwind não removê-las.
 *
 * O Tailwind 4 varre o código procurando nomes de classe literais. Uma classe
 * montada por interpolação (`bg-${cor}`) não aparece nessa varredura e sai do
 * CSS — o efeito é a cor sumir em produção e funcionar em dev, que é o pior
 * jeito de descobrir. Esta lista existe para ser encontrada pela varredura.
 */
export const TIER_SAFELIST = [
  "text-t1", "text-t2", "text-t3", "text-t4",
  "text-t5", "text-t6", "text-t7", "text-t8",
  "bg-t1", "bg-t2", "bg-t3", "bg-t4",
  "bg-t5", "bg-t6", "bg-t7", "bg-t8",
  "border-t1/50", "border-t2/50", "border-t3/50", "border-t4/50",
  "border-t5/50", "border-t6/50", "border-t7/50", "border-t8/50",
  "border-t1/30", "border-t2/30", "border-t3/30", "border-t4/30",
  "border-t5/30", "border-t6/30", "border-t7/30", "border-t8/30",
  "bg-t1/10", "bg-t2/10", "bg-t3/10", "bg-t4/10",
  "bg-t5/10", "bg-t6/10", "bg-t7/10", "bg-t8/10",
  "border-l-t1", "border-l-t2", "border-l-t3", "border-l-t4",
  "border-l-t5", "border-l-t6", "border-l-t7", "border-l-t8",
  "border-l-transparent",
  "text-line-strong", "bg-line-strong", "border-line-strong/50", "border-line-strong/30",
  "bg-line-strong/10",
] as const;
