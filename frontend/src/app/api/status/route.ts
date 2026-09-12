import { NextResponse } from "next/server";

import { fetchPlatformStatus } from "@/lib/api";

export const dynamic = "force-dynamic";

/** Proxy do estado da plataforma. O browser chama aqui, nunca o FastAPI. */
export async function GET() {
  const status = await fetchPlatformStatus();
  return NextResponse.json(status, { status: status.reachable ? 200 : 503 });
}
