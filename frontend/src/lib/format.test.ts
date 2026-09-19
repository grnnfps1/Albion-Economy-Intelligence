import { describe, expect, it } from "vitest";

import {
  formatDataAge,
  formatLatency,
  formatSilver,
  formatSilverCompact,
  statusLabel,
  statusTone,
} from "./format";

describe("formatSilver", () => {
  it("agrupa milhares no padrão pt-BR", () => {
    expect(formatSilver(1250)).toBe("1.250");
    expect(formatSilver(420000)).toBe("420.000");
  });

  it("distingue ausência de dado de zero", () => {
    expect(formatSilver(null)).toBe("—");
    expect(formatSilver(undefined)).toBe("—");
    expect(formatSilver(0)).toBe("0");
  });
});

describe("formatDataAge", () => {
  it("sem dado não vira 'agora'", () => {
    expect(formatDataAge(null)).toBe("sem dado");
    expect(formatDataAge(0)).toBe("agora");
  });

  it("escala minuto, hora e dia", () => {
    expect(formatDataAge(480)).toBe("há 8 min");
    expect(formatDataAge(7200)).toBe("há 2 h");
    expect(formatDataAge(172800)).toBe("há 2 d");
  });
});

describe("formatLatency", () => {
  it("formata ou mostra travessão", () => {
    expect(formatLatency(1234)).toBe("1.234 ms");
    expect(formatLatency(null)).toBe("—");
  });
});

describe("status", () => {
  it("traduz os estados do health check", () => {
    expect(statusLabel("ok")).toBe("operacional");
    expect(statusLabel("degraded")).toBe("parcial");
    expect(statusLabel("down")).toBe("fora do ar");
    expect(statusLabel(undefined)).toBe("desconhecido");
  });

  it("normaliza tom desconhecido", () => {
    expect(statusTone("ok")).toBe("ok");
    expect(statusTone("banana")).toBe("unknown");
  });
});

describe("formatSilverCompact", () => {
  it("abrevia milhar, milhão e bilhão com vírgula e uma casa", () => {
    expect(formatSilverCompact(12_500)).toBe("12,5K");
    expect(formatSilverCompact(133_086_292)).toBe("133,1M");
    expect(formatSilverCompact(1_200_000_000)).toBe("1,2B");
  });

  it("não abrevia abaixo de 10.000", () => {
    // `9,9K` é menos legível que `9.870` e ainda perde precisão.
    expect(formatSilverCompact(9_870)).toBe("9.870");
    expect(formatSilverCompact(4_500)).toBe("4.500");
    expect(formatSilverCompact(0)).toBe("0");
  });

  it("o limiar é exclusivo abaixo e inclusivo a partir de 10.000", () => {
    expect(formatSilverCompact(9_999)).toBe("9.999");
    expect(formatSilverCompact(10_000)).toBe("10,0K");
  });

  it("ausência continua sendo traço, não zero", () => {
    expect(formatSilverCompact(null)).toBe("—");
    expect(formatSilverCompact(undefined)).toBe("—");
  });

  it("negativo mantém o sinal e a magnitude decide a abreviação", () => {
    expect(formatSilverCompact(-133_086_292)).toBe("-133,1M");
    expect(formatSilverCompact(-9_870)).toBe("-9.870");
  });

  it("a abreviação perde precisão, e é por isso que o lucro não usa esta função", () => {
    // Dois lucros diferentes viram o mesmo texto. Na coluna de contexto isso é
    // aceitável; na coluna que decide, não.
    expect(formatSilverCompact(133_086_292)).toBe(formatSilverCompact(133_086_291));
    expect(formatSilver(133_086_292)).not.toBe(formatSilver(133_086_291));
  });
});
