#!/usr/bin/env python3
"""
CTF Probset Generator — Makam China / Neverland
Jalankan: python build.py
Semua nilai yang bisa berubah ada di bagian CONFIG di bawah.
"""

from __future__ import annotations

import base64
import io
import os
import re
import shutil
import struct
import sys
import wave
from pathlib import Path

import numpy as np
import piexif
import pyzipper
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

# =============================================================================
# CONFIG — ubah nilai di sini saja
# =============================================================================

# Domain Vercel (tanpa trailing slash). Diganti otomatis di HTML & EXIF.
DOMAIN_VERCEL = "https://ctf-makam-china.vercel.app"

# Flag asli = FLAG_HALF_PDF + FLAG_HALF_SPEC  →  PETER{...}
FLAG_HALF_PDF = "PETER{k3n4ng4n_t3rs3mbun71_"
FLAG_HALF_SPEC = "d1_n3v3rl4nd}"

# Flag palsu
FLAG_FAKE_API = "PETER{4p1_g0_bukan_j4l4n_1n1}"
FLAG_FAKE_LAPORAN = "PETER{l4p0r4n_k0s0ng_t1d4k_b3nar}"

# Password zip (juga ditanam sebagai JPEG comment di kenangan.jpg)
ZIP_PASSWORD = "nanopeter"

# Morse word → jalur PDF: /neverland.pdf
MORSE_WORD = "NEVERLAND"

# Teks spektrogram
SPEC_TRAP_TEXT = "laporan.pdf"       # suara_a (pengecoh)
SPEC_FLAG_TEXT = FLAG_HALF_SPEC      # suara_b (setengah flag)

# Petunjuk samar di neverland.pdf (teks abu-abu tipis, masih kebaca)
NEVERLAND_HINT = "Yang kedua bicara lewat warna suara."

# GitHub / Instagram (untuk output panduan)
GITHUB_USER = "nanopeterpen"
GITHUB_REPO = "kenangan"
IG_HANDLE = "nanopeterpen"  # sesuaikan akun IG-mu

# Streamable embed (sudah di public/pora/index.html)
STREAMABLE_URL = "https://streamable.com/e/29jp1w"

# Path
ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
PUBLIC = ROOT / "public"
MEDIA = PUBLIC / "media"
BUILD_TMP = ROOT / ".build_tmp"
COVER_SRC = ASSETS / "cover.jpg"  # sumber image.jpg halaman utama
KENANGAN_SRC = ASSETS / "kenangan_base.jpg"  # optional; digenerate jika tidak ada

SAMPLE_RATE = 44100

# =============================================================================
# Helpers
# =============================================================================


def ensure_dirs() -> None:
    for p in (ASSETS, PUBLIC, MEDIA, BUILD_TMP, PUBLIC / "pora", PUBLIC / "peter"):
        p.mkdir(parents=True, exist_ok=True)


def load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def replace_domain_in_html() -> None:
    """Ganti placeholder DOMAIN jika ada di HTML (opsional)."""
    marker = "https://YOUR-PROJECT.vercel.app"
    if DOMAIN_VERCEL == marker:
        return
    for html in PUBLIC.rglob("*.html"):
        text = html.read_text(encoding="utf-8")
        if marker in text:
            html.write_text(text.replace(marker, DOMAIN_VERCEL), encoding="utf-8")


# =============================================================================
# 1) Cover image + EXIF ImageDescription → /pora
# =============================================================================


def make_cover_if_missing() -> None:
    if COVER_SRC.exists():
        return
    img = Image.new("RGB", (1200, 800), (28, 24, 20))
    draw = ImageDraw.Draw(img)
    font = load_font(64)
    draw.text((80, 340), "MAKAM CHINA", fill=(220, 210, 195), font=font)
    img.save(COVER_SRC, quality=92)


def write_exif_cover() -> Path:
    make_cover_if_missing()
    out = PUBLIC / "image.jpg"
    img = Image.open(COVER_SRC).convert("RGB")

    description = f"{DOMAIN_VERCEL}/pora"
    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
    exif_dict["0th"][piexif.ImageIFD.ImageDescription] = description.encode("utf-8")
    exif_dict["0th"][piexif.ImageIFD.Software] = b"makam-china-ctf"
    exif_bytes = piexif.dump(exif_dict)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, exif=exif_bytes)
    out.write_bytes(buf.getvalue())
    print(f"[+] {out}  ImageDescription={description}")
    return out


# =============================================================================
# 2) Audio: Morse NEVERLAND
# =============================================================================

MORSE_MAP = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
    " ": "/",
}


def tone(freq: float, duration: float, volume: float = 0.35) -> np.ndarray:
    n = int(SAMPLE_RATE * duration)
    t = np.arange(n) / SAMPLE_RATE
    wave_ = volume * np.sin(2 * np.pi * freq * t)
    # envelope singkat biar tidak klik
    fade = min(200, n // 4)
    if fade > 0:
        env = np.ones(n)
        env[:fade] = np.linspace(0, 1, fade)
        env[-fade:] = np.linspace(1, 0, fade)
        wave_ *= env
    return wave_


def silence(duration: float) -> np.ndarray:
    return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float64)


def write_wav(path: Path, samples: np.ndarray) -> None:
    samples = np.clip(samples, -1.0, 1.0)
    # noise ringan
    noise = np.random.normal(0, 0.008, size=samples.shape)
    mixed = np.clip(samples + noise, -1.0, 1.0)
    pcm = (mixed * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())
    print(f"[+] {path}")


def build_morse_wav(path: Path, word: str) -> None:
    unit = 0.09
    freq = 680.0
    parts: list[np.ndarray] = [silence(0.3)]
    for ch in word.upper():
        code = MORSE_MAP.get(ch, "")
        if ch == " ":
            parts.append(silence(unit * 7))
            continue
        for i, sym in enumerate(code):
            if sym == ".":
                parts.append(tone(freq, unit))
            elif sym == "-":
                parts.append(tone(freq, unit * 3))
            parts.append(silence(unit))
        parts.append(silence(unit * 2))
    parts.append(silence(0.4))
    write_wav(path, np.concatenate(parts))


# =============================================================================
# 3) Audio: Spektrogram text (suara_a / suara_b)
# =============================================================================


def text_to_spectrogram_wav(
    path: Path,
    text: str,
    duration: float = 4.5,
    f_low: float = 400.0,
    f_high: float = 3800.0,
) -> None:
    """Gambar teks → tiap kolom piksel jadi spektrum frekuensi sepanjang waktu."""
    font = load_font(72)
    # ukur teks
    tmp = Image.new("L", (10, 10), 0)
    d = ImageDraw.Draw(tmp)
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = 20
    img = Image.new("L", (tw + pad * 2, th + pad * 2), 0)
    draw = ImageDraw.Draw(img)
    draw.text((pad, pad), text, fill=255, font=font)
    # flip vertical: baris atas = frekuensi tinggi
    arr = np.asarray(img, dtype=np.float64) / 255.0
    arr = np.flipud(arr)
    h, w = arr.shape

    n_samples = int(SAMPLE_RATE * duration)
    audio = np.zeros(n_samples, dtype=np.float64)
    samples_per_col = n_samples / w

    # frekuensi per baris
    freqs = np.linspace(f_low, f_high, h)

    for col in range(w):
        start = int(col * samples_per_col)
        end = int((col + 1) * samples_per_col)
        if end <= start:
            continue
        t = np.arange(start, end) / SAMPLE_RATE
        column = arr[:, col]
        active = np.where(column > 0.15)[0]
        if len(active) == 0:
            continue
        chunk = np.zeros_like(t)
        for row in active:
            amp = column[row] * 0.045
            chunk += amp * np.sin(2 * np.pi * freqs[row] * t)
        audio[start:end] += chunk

    # soft normalize
    peak = np.max(np.abs(audio)) or 1.0
    audio = audio / peak * 0.7
    write_wav(path, audio)


# =============================================================================
# 4) Zip terenkripsi + polyglot kenangan.jpg
# =============================================================================


def make_kenangan_base() -> Path:
    if KENANGAN_SRC.exists():
        return KENANGAN_SRC
    img = Image.new("RGB", (1000, 700), (32, 28, 24))
    draw = ImageDraw.Draw(img)
    font = load_font(48)
    draw.text((60, 300), "kenangan", fill=(200, 190, 175), font=font)
    draw.text((60, 370), "yang tak sempat diucapkan", fill=(140, 130, 120), font=load_font(28))
    KENANGAN_SRC.parent.mkdir(parents=True, exist_ok=True)
    img.save(KENANGAN_SRC, quality=90)
    return KENANGAN_SRC


def jpeg_with_comment(src: Path, comment: str) -> bytes:
    """Sisipkan COM segment JPEG berisi password (kebaca exiftool/strings)."""
    img = Image.open(src).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    data = bytearray(buf.getvalue())
    com_payload = comment.encode("utf-8") + b"\x00"
    com_seg = b"\xff\xfe" + struct.pack(">H", len(com_payload) + 2) + com_payload
    if data[:2] != b"\xff\xd8":
        raise ValueError("Bukan JPEG valid")
    return bytes(data[:2] + com_seg + data[2:])


def create_encrypted_zip(zip_path: Path, files: dict[str, Path], password: str) -> None:
    # AES — ekstrak dengan 7-Zip / pyzipper
    with pyzipper.AESZipFile(
        zip_path,
        "w",
        compression=pyzipper.ZIP_DEFLATED,
        encryption=pyzipper.WZ_AES,
    ) as zf:
        zf.setpassword(password.encode("utf-8"))
        for arcname, fpath in files.items():
            zf.write(fpath, arcname=arcname)
    print(f"[+] {zip_path}  (password={password})")


def fix_zip_offsets(zip_data: bytes, prepend_len: int) -> bytes:
    """Sesuaikan offset di central directory setelah byte JPEG di-prepend (mirip zip -A)."""
    eocd = zip_data.rfind(b"\x50\x4b\x05\x06")
    if eocd < 0:
        raise ValueError("EOCD tidak ditemukan")
    cd_size = struct.unpack_from("<I", zip_data, eocd + 12)[0]
    cd_offset = struct.unpack_from("<I", zip_data, eocd + 16)[0]
    data = bytearray(zip_data)

    pos = cd_offset
    end_cd = cd_offset + cd_size
    while pos < end_cd:
        if data[pos : pos + 4] != b"\x50\x4b\x01\x02":
            break
        old_local = struct.unpack_from("<I", data, pos + 42)[0]
        struct.pack_into("<I", data, pos + 42, old_local + prepend_len)
        name_len = struct.unpack_from("<H", data, pos + 28)[0]
        extra_len = struct.unpack_from("<H", data, pos + 30)[0]
        comment_len = struct.unpack_from("<H", data, pos + 32)[0]
        pos += 46 + name_len + extra_len + comment_len

    struct.pack_into("<I", data, eocd + 16, cd_offset + prepend_len)
    return bytes(data)


def build_kenangan_polyglot(wav_files: dict[str, Path]) -> Path:
    base = make_kenangan_base()
    jpg_bytes = jpeg_with_comment(base, ZIP_PASSWORD)

    zip_path = BUILD_TMP / "payload.zip"
    create_encrypted_zip(zip_path, wav_files, ZIP_PASSWORD)
    zip_bytes = zip_path.read_bytes()

    combined = jpg_bytes + fix_zip_offsets(zip_bytes, len(jpg_bytes))

    out = MEDIA / "kenangan.jpg"
    out.write_bytes(combined)
    print(f"[+] {out}  (JPEG+ZIP polyglot, comment={ZIP_PASSWORD})")
    return out


# =============================================================================
# 5) PDF: neverland.pdf (asli) & laporan.pdf (pengecoh)
# =============================================================================


def nearly_white_text_image(text: str, width: int = 900, height: int = 200) -> Image.Image:
    """Teks RGB ~250 di atas putih 255 — hampir tak terlihat, kebaca setelah contrast."""
    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = load_font(42)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (width - tw) // 2
    y = (height - th) // 2
    draw.text((x, y), text, fill=(250, 250, 250), font=font)
    return img


def build_neverland_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    # halaman hampir kosong + hint samar
    c.setFillColorRGB(0.82, 0.82, 0.82)
    c.setFont("Helvetica", 9)
    c.drawString(72, h - 72, NEVERLAND_HINT)

    # setengah flag sebagai gambar hampir putih
    img = nearly_white_text_image(FLAG_HALF_PDF, width=1000, height=180)
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    c.drawImage(ImageReader(bio), 48, h / 2 - 40, width=w - 96, height=90, mask="auto")
    c.showPage()
    c.save()
    print(f"[+] {path}  (half flag as near-white image)")


def build_laporan_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    # teks putih di atas putih — kebaca pdftotext / select-all
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica", 14)
    c.drawString(72, h / 2, FLAG_FAKE_LAPORAN)
    c.setFillColorRGB(0.9, 0.9, 0.9)
    c.setFont("Helvetica", 10)
    c.drawString(72, h - 60, "Laporan — tidak ada yang perlu dilihat.")
    c.showPage()
    c.save()
    print(f"[+] {path}  (fake flag white-on-white)")


# =============================================================================
# 6) Output base64 untuk Instagram + ringkasan
# =============================================================================


def b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def write_output_notes() -> Path:
    full_flag = FLAG_HALF_PDF + FLAG_HALF_SPEC
    ig1 = f"{DOMAIN_VERCEL}/peter/index.html"
    ig2 = f"{DOMAIN_VERCEL}/media/kenangan.jpg"
    notes = f"""# OUTPUT BUILD — salin ke Instagram / cek flag

## Flag asli
{full_flag}

## Flag palsu
- api/go     : {FLAG_FAKE_API}
- laporan.pdf: {FLAG_FAKE_LAPORAN}

## Instagram (post teks = base64 murni)
Post 1 (jebakan):
  plaintext : {ig1}
  base64    : {b64(ig1)}

Post 2 (file asli):
  plaintext : {ig2}
  base64    : {b64(ig2)}

## Zip
password / JPEG comment: {ZIP_PASSWORD}

## Morse
kata: {MORSE_WORD}  →  buka {DOMAIN_VERCEL}/neverland.pdf

## EXIF
ImageDescription: {DOMAIN_VERCEL}/pora

## GitHub
user/repo: {GITHUB_USER}/{GITHUB_REPO}
IG_URL untuk commit lama (contoh): https://www.instagram.com/{IG_HANDLE}/
"""
    out = ROOT / "BUILD_OUTPUT.txt"
    out.write_text(notes, encoding="utf-8")
    print(f"[+] {out}")
    return out


def patch_api_fake_flag() -> None:
    api = ROOT / "api" / "go.js"
    if not api.exists():
        return
    text = api.read_text(encoding="utf-8")
    text2 = re.sub(
        r'process\.env\.FAKE_FLAG_API \|\| "[^"]*"',
        f'process.env.FAKE_FLAG_API || "{FLAG_FAKE_API}"',
        text,
    )
    if text2 != text:
        api.write_text(text2, encoding="utf-8")
        print(f"[+] patched {api}")


# =============================================================================
# Main
# =============================================================================


def main() -> int:
    print("=== CTF build: Makam China ===")
    if DOMAIN_VERCEL.endswith("YOUR-PROJECT.vercel.app"):
        print("[!] DOMAIN_VERCEL masih placeholder — set di CONFIG sebelum deploy final.")

    ensure_dirs()
    if BUILD_TMP.exists():
        shutil.rmtree(BUILD_TMP)
    BUILD_TMP.mkdir()

    write_exif_cover()

    wav_a = BUILD_TMP / "suara_a.wav"
    wav_b = BUILD_TMP / "suara_b.wav"
    wav_m = BUILD_TMP / "suara_morse.wav"
    build_morse_wav(wav_m, MORSE_WORD)
    text_to_spectrogram_wav(wav_a, SPEC_TRAP_TEXT)
    text_to_spectrogram_wav(wav_b, SPEC_FLAG_TEXT)

    build_kenangan_polyglot(
        {
            "suara_a.wav": wav_a,
            "suara_b.wav": wav_b,
            "suara_morse.wav": wav_m,
        }
    )

    build_neverland_pdf(PUBLIC / "neverland.pdf")
    build_laporan_pdf(PUBLIC / "laporan.pdf")

    patch_api_fake_flag()
    replace_domain_in_html()
    write_output_notes()

    print("\nSelesai. Deploy ke Vercel. Ringkasan lokal: BUILD_OUTPUT.txt (jangan di-commit).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
