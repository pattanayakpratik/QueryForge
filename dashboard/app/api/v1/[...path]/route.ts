import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const resolved = await params;
  return handleProxy(request, resolved);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const resolved = await params;
  return handleProxy(request, resolved);
}

async function handleProxy(request: NextRequest, params: { path: string[] }) {
  const backendBase =
    process.env.BACKEND_URL || "http://queryforge-api:8000";
  const path = (params.path || []).join("/");
  const search = request.nextUrl.search;
  const targetUrl = `${backendBase}/v1/${path}${search}`;

  try {
    const headers = new Headers();
    request.headers.forEach((value, key) => {
      if (key.toLowerCase() !== "host") {
        headers.set(key, value);
      }
    });

    const body =
      request.method !== "GET" && request.method !== "HEAD"
        ? await request.arrayBuffer()
        : undefined;

    const res = await fetch(targetUrl, {
      method: request.method,
      headers,
      body,
      // @ts-ignore
      duplex: "half",
    });

    return new Response(res.body, {
      status: res.status,
      statusText: res.statusText,
      headers: res.headers,
    });
  } catch (error: any) {
    console.error(`[Proxy Error] Connecting to ${targetUrl}:`, error.message);
    return NextResponse.json(
      {
        error: "Backend service unreachable",
        target: targetUrl,
        details: error.message,
      },
      { status: 502 }
    );
  }
}
