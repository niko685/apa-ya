import { next } from "@vercel/edge";

const COUNTER_KEY = "ctf-makam-china-vercel-visits-2026";
const HIT_URL = `https://countapi.mileshilliard.com/api/v1/hit/${COUNTER_KEY}`;

/**
 * Tolak CLI UA + catat kunjungan (kecuali saat cek /ramayana.txt).
 */
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};

export default async function middleware(request) {
  const ua = request.headers.get("user-agent") || "";
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

  const path = new URL(request.url).pathname;
  const skipCount =
    path === "/ramayana.txt" ||
    path === "/api/ramayana" ||
    path.startsWith("/api/ramayana");

  if (!skipCount) {
    fetch(HIT_URL, {
      headers: { "user-agent": "Mozilla/5.0 (compatible; makam-china-counter/1.0)" },
    }).catch(function () {});
  }

  return next();
}
