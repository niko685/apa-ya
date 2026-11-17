// GET /ramayana.txt (via rewrite) → jumlah kunjungan (plain text)
const COUNTER_KEY = "ctf-makam-china-vercel-visits-2026";
const GET_URL = `https://countapi.mileshilliard.com/api/v1/get/${COUNTER_KEY}`;

module.exports = async function handler(req, res) {
  res.setHeader("Content-Type", "text/plain; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");

  try {
    const r = await fetch(GET_URL, {
      headers: { "user-agent": "Mozilla/5.0 (compatible; makam-china-counter/1.0)" },
    });
    const data = await r.json();
    const n = data.value ?? data.count ?? 0;
    res.status(200).send(String(n) + "\n");
  } catch {
    res.status(200).send("0\n");
  }
};
