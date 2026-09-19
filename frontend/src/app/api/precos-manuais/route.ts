/**
 * Ponte do browser para o preço manual.
 *
 * O browser **nunca** fala com o FastAPI (regra 4): o caminho é
 * `Browser → Next → FastAPI`. Esta rota existe só para isso — ela lê a sessão,
 * repassa a identidade no cabeçalho e devolve o resultado.
 *
 * Sem ela o componente de edição precisaria da URL interna do backend no
 * bundle do cliente, que é exatamente o que a arquitetura evita.
 */
import { NextResponse } from "next/server";

import { deleteManualPrice, saveManualPrice } from "@/lib/api";

type Corpo = {
  server?: string;
  location?: string;
  item?: string;
  quality?: number;
  price?: number;
  kind?: "COMPRA" | "VENDA";
};

export async function PUT(request: Request) {
  let corpo: Corpo;
  try {
    corpo = (await request.json()) as Corpo;
  } catch {
    return NextResponse.json({ erro: "corpo inválido" }, { status: 400 });
  }

  const { server, location, item, kind } = corpo;
  const price = Number(corpo.price);
  const quality = Number(corpo.quality ?? 1);

  if (!server || !location || !item || (kind !== "COMPRA" && kind !== "VENDA")) {
    return NextResponse.json({ erro: "faltam campos" }, { status: 400 });
  }
  // Zero não é preço, é ausência — e ausência se remove, não se grava.
  if (!Number.isFinite(price) || price <= 0) {
    return NextResponse.json({ erro: "preço precisa ser maior que zero" }, { status: 422 });
  }

  const salvo = await saveManualPrice({ server, location, item, quality, price, kind });
  if (salvo === null) {
    return NextResponse.json({ erro: "backend recusou" }, { status: 502 });
  }
  return NextResponse.json(salvo);
}

export async function DELETE(request: Request) {
  const params = new URL(request.url).searchParams;
  const server = params.get("server");
  const location = params.get("location");
  const item = params.get("item");
  const kind = params.get("kind");

  if (!server || !location || !item || !kind) {
    return NextResponse.json({ erro: "faltam campos" }, { status: 400 });
  }

  const ok = await deleteManualPrice({
    server,
    location,
    item,
    quality: Number(params.get("quality") ?? 1),
    kind,
  });
  return ok
    ? new NextResponse(null, { status: 204 })
    : NextResponse.json({ erro: "backend recusou" }, { status: 502 });
}
