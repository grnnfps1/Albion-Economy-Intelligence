import { describe, expect, it } from "vitest";

import { formatDataAge, formatLatency, formatSilver, statusLabel, statusTone } from "./format";

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
