// Endpoint pengecoh — sengaja mengembalikan flag palsu.
module.exports = function handler(req, res) {
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.status(200).json({
    status: "ok",
    message: "Kamu terlalu cepat. Ini bukan jalan yang benar.",
    flag: process.env.FAKE_FLAG_API || "PETER{4p1_g0_bukan_j4l4n_1n1}",
  });
};
