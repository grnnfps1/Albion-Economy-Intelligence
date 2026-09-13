/**
 * Cidade com a cor heráldica dela.
 *
 * As sete cidades reais têm identidade visual própria no jogo. Usar essa cor
 * aqui não é decoração: o jogador reconhece "laranja = Bridgewatch" antes de
 * ler o texto, e numa tela densa isso economiza uma leitura por linha.
 */
const CORES: Record<string, string> = {
  Caerleon: "bg-caerleon",
  Bridgewatch: "bg-bridgewatch",
  Lymhurst: "bg-lymhurst",
  "Fort Sterling": "bg-fortsterling",
  Martlock: "bg-martlock",
  Thetford: "bg-thetford",
  Brecilien: "bg-brecilien",
};

export function CityChip({ city, kind }: { city: string; kind?: string }) {
  const cor = CORES[city] ?? "bg-line-strong";
  return (
    <span className="inline-flex items-center gap-1.5 rounded-sm bg-ink px-1.5 py-0.5 text-xs">
      <span aria-hidden className={`inline-block size-1.5 rounded-full ${cor}`} />
      <span className="text-body">{city}</span>
      {kind === "black_market" && <span className="text-muted">BM</span>}
    </span>
  );
}
