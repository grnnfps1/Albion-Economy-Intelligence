/**
 * Balão de dica próprio, em CSS.
 *
 * Por que não o `title` nativo: o navegador espera quase um segundo antes de
 * mostrá-lo e o esconde ao menor movimento do mouse. Numa tabela densa, em que
 * a pessoa passa o mouse por dez materiais para comparar, isso é lento demais
 * para ser útil — o balão aparece depois que o cursor já saiu.
 *
 * O `title` continua onde o atraso não incomoda: em botões e cabeçalhos, onde
 * a pessoa para em cima do alvo de propósito.
 *
 * Implementado com `::after` e `data-dica` em vez de estado React: são dezenas
 * de células por tela, e um `useState` em cada uma custaria mais do que o
 * recurso vale.
 */
export function HoverTip({
  dica,
  children,
  className = "",
  lista = false,
}: {
  dica: string;
  children: React.ReactNode;
  className?: string;
  /**
   * O balão vira várias linhas, quebrando em `
`.
   *
   * O padrão é `nowrap` porque a dica curta de uma célula não pode rebobinar
   * em três linhas finas. Uma lista de cidades é o caso oposto: ela **é** a
   * quebra, e forçá-la numa linha só sairia mais larga que a tela.
   */
  lista?: boolean;
}) {
  return (
    <span
      data-dica={dica}
      className={`hover-tip relative ${lista ? "hover-tip--lista" : ""} ${className}`}
    >
      {children}
    </span>
  );
}
