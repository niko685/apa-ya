# Makam China — CTF Probset (solo)

Web statis + OSINT + stego/forensik. Format flag: `PETER{...}`. Peserta kirim flag ke WhatsApp.

## Cepat mulai

```powershell
python -m pip install -r requirements.txt
# Edit CONFIG di build.py (DOMAIN_VERCEL, flag, password, ...)
python build.py
vercel --prod
```

Lanjut: **`docs/LANGKAH_MANUAL.md`** (GitHub, Instagram, deploy).  
Writeup: **`docs/WRITEUP.md`**.

## Struktur

```
├── api/go.js              # flag palsu
├── build.py               # generator semua aset
├── public/
│   ├── index.html         # landing + image.jpg
│   ├── image.jpg          # EXIF → /pora
│   ├── pora/index.html    # Streamable + komentar nanopeterpen
│   ├── peter/index.html   # jebakan → /api/go
│   ├── media/kenangan.jpg # JPEG+ZIP
│   ├── neverland.pdf      # setengah flag (near-white)
│   └── laporan.pdf        # flag palsu
├── assets/                # sumber gambar
└── docs/
```
