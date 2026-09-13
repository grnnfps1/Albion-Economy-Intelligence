import { describe, expect, it } from "vitest";

import { TIER_SAFELIST, tierBg, tierBorder, tierColor, tierText } from "./tiers";

describe("cor de tier", () => {
  it("usa a escala do jogo de T1 a T8", () => {
    expect(tierColor(4)).toBe("t4");
    expect(tierColor(8)).toBe("t8");
  });

  it("tier desconhecido vira neutro e nunca a cor de outro tier", () => {
    // O caso que importa: item sem tier não pode ser pintado como se tivesse
    // um. Cor aqui é informação, e uma cor errada mente.
    expect(tierColor(null)).toBe("line-strong");
    expect(tierColor(undefined)).toBe("line-strong");
    expect(tierColor(0)).toBe("line-strong");
    expect(tierColor(9)).toBe("line-strong");
  });

  it("monta as classes de texto, fundo e borda a partir do mesmo token", () => {
    expect(tierText(5)).toBe("text-t5");
    expect(tierBg(5)).toBe("bg-t5");
    expect(tierBorder(5)).toBe("border-t5/50");
    expect(tierBorder(5, 30)).toBe("border-t5/30");
  });

  it("toda classe gerada está na safelist", () => {
    // Classe montada por interpolação não aparece na varredura do Tailwind e
    // some do CSS em produção, funcionando em dev. Este teste é o que impede
    // essa regressão: se alguém adicionar um tier ou uma opacidade nova sem
    // registrar, aqui falha.
    const gerados = [null, 1, 2, 3, 4, 5, 6, 7, 8, 9].flatMap((tier) => [
      tierText(tier),
      tierBg(tier),
      tierBorder(tier),
      tierBorder(tier, 30),
    ]);

    for (const classe of gerados) {
      expect(TIER_SAFELIST).toContain(classe);
    }
  });
});
