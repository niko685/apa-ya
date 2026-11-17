import { next } from "@vercel/edge";

/**
 * Tolak request yang User-Agent-nya curl (dan CLI sejenis).
 * Catatan: UA bisa dipalsukan; ini bukan ban IP permanen.
 */
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};

export default function middleware(request) {
  const ua = request.headers.get("user-agent") || "";
  // curl, wget, httpie, python urllib/requests, Go default, etc.
  if (
    /\bcurl\b/i.test(ua) ||
    /\bwget\b/i.test(ua) ||
    /\bHTTPie\b/i.test(ua) ||
    /\bpython-requests\b/i.test(ua) ||
    /\bPython-urllib\b/i.test(ua) ||
    /\bGo-http-client\b/i.test(ua)
  ) {
    return new Response("Forbidden", {
      status: 403,
      headers: {
        "content-type": "text/plain; charset=utf-8",
        "cache-control": "no-store",
      },
    });
  }

  return next();
}
