"""
Manga Page Grouper — Gabungkan Halaman Mentah ke Beberapa Halaman Output
========================================================================

Menggabungkan halaman-halaman mentah (misal 33 file .jpg) menjadi
sejumlah halaman output yang sudah dikelompokkan dan ditempel vertikal.

CONTOH:
  60 raw pages → 12 output pages (5 raw per page) ✅ pas
  33 raw pages →  6 output pages (5-6 raw per page)
  20 raw pages →  4 output pages (5 raw per page)
   8 raw pages →  2 output pages (4 raw per page)

STRUCTURE YANG DIHARAPKAN:
    input/
      Chapter 1/
        001.jpg
        002.jpg
        003.jpg
        ...
      Chapter 2/
        ...

OUTPUT:
    output/
      Chapter 1/
        1.jpg          ← gabungan raw page 1-3
        2.jpg          ← gabungan raw page 4-6
        ...
      Chapter 2/
        ...

INSTALASI:
    pip install Pillow

CARA PAKAI:
    1. Masukkan folder chapter ke dalam folder "input"
    2. Atur SETTINGS di bawah sesuai selera
    3. Jalankan:  python group_to_pages.py
    4. Hasil ada di folder "output"
"""

import os
import shutil
from pathlib import Path
from PIL import Image

# ──────────────────────────────────────────────────────────────────────────
# SETTINGS — sesuaikan dengan kebutuhan
# ──────────────────────────────────────────────────────────────────────────

INPUT_DIR = "input"           # folder berisi folder-folder chapter
OUTPUT_DIR = "output"          # tempat hasil halaman output

# ─── Aturan jumlah halaman output ────────────────────────────────────────
# Tiap 5 raw pages digabung jadi 1 halaman output.
# Contoh: 33 raw -> 6 page, 20 raw -> 4 page
RAW_PER_OUTPUT_PAGE = 5        # jumlah raw pages per 1 halaman output
MIN_OUTPUT_PAGES = 2            # minimal halaman output (jika raw sedikit)

# ─── Lebar halaman output ────────────────────────────────────────────────
# Tiap halaman output lebarnya akan di-resize ke nilai ini.
OUTPUT_WIDTH = 800             # lebar final halaman output (px, 500-800)
MIN_OUTPUT_WIDTH = 500         # lebar minimum (px, untuk validasi)
MAX_OUTPUT_WIDTH = 800         # lebar maksimum (px, untuk validasi)

# ─── Format gambar & optimasi ukuran ───────────────────────────────────
# Script otomatis pilih format terbaik:
#   1. Coba WebP dulu (lebih kecil, kualitas lebih baik)
#   2. Jika file > MAX_FILE_SIZE, fallback ke JPEG dengan quality turun
ENABLE_WEBP = True              # True = coba WebP dulu, False = langsung JPEG
MAX_FILE_SIZE_MB = 3            # maksimal ukuran file (MB), jika lebih -> turunkan quality
WEBP_QUALITY_START = 90         # quality awal untuk WebP
JPEG_QUALITY_START = 85         # quality awal untuk JPEG (turun otomatis jika > MAX)
MIN_JPEG_QUALITY = 45           # batas bawah quality JPEG (biar tidak jelek banget)

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

# ─── Hapus folder output sebelumnya ─────────────────────────────────────
CLEAN_OUTPUT_BEFORE_RUN = False  # True = hapus isi folder output dulu


# ──────────────────────────────────────────────────────────────────────────
# LOGIKA — tidak perlu diedit di bawah sini
# ──────────────────────────────────────────────────────────────────────────


def natural_sort_key(path: Path):
    """Sort '2.jpg' before '10.jpg' (natural order)."""
    import re
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.stem)]


def find_chapter_folders(input_dir: Path):
    folders = [f for f in input_dir.iterdir() if f.is_dir()]
    folders.sort(key=lambda f: natural_sort_key(Path(f.name)))
    return folders


def find_images(chapter_dir: Path):
    images = [f for f in chapter_dir.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS]
    images.sort(key=natural_sort_key)
    return images


def calculate_output_pages(raw_count: int) -> int:
    """
    Hitung jumlah halaman output berdasarkan jumlah raw pages.

    Tiap RAW_PER_OUTPUT_PAGE (5) raw = 1 halaman output.
    Minimal MIN_OUTPUT_PAGES (2) halaman.

    Contoh:
      60 raw -> max(2, 60//5=12) = 12 page
      33 raw -> max(2, 33//5=6)  =  6 page
      20 raw -> max(2, 20//5=4)  =  4 page
       8 raw -> max(2,  8//5=1)  =  2 page
    """
    if raw_count <= 0:
        return 0
    return max(MIN_OUTPUT_PAGES, raw_count // RAW_PER_OUTPUT_PAGE)


def distribute_raw_to_pages(raw_count: int, output_pages: int):
    """
    Distribusikan raw pages merata ke setiap halaman output.
    Returns list of (start_index, count) tuples.
    """
    base = raw_count // output_pages
    extra = raw_count % output_pages

    groups = []
    start = 0
    for i in range(output_pages):
        count = base + (1 if i < extra else 0)
        groups.append((start, count))
        start += count

    return groups


def stitch_images_vertically(image_paths, target_width: int):
    """
    Gabungkan beberapa gambar menjadi satu strip vertikal.
    Semua gambar di-resize ke target_width, aspect ratio dipertahankan.
    Return (PIL.Image, width, height).
    """
    resized = []
    total_height = 0

    for img_path in image_paths:
        img = Image.open(img_path).convert("RGB")
        w, h = img.size
        new_h = int(h * (target_width / w))
        img = img.resize((target_width, new_h), Image.LANCZOS)
        resized.append(img)
        total_height += new_h

    strip = Image.new("RGB", (target_width, total_height), "white")
    y_offset = 0
    for img in resized:
        strip.paste(img, (0, y_offset))
        y_offset += img.height

    return strip, target_width, total_height


def save_optimized_image(image: Image.Image, base_path: Path):
    """
    Simpan gambar dengan format terbaik otomatis.

    Strategi:
      1. Coba WebP dulu (kualitas tinggi, ukuran kecil)
      2. Jika file > MAX_FILE_SIZE, turunkan quality WebP
      3. Jika WebP masih > MAX_FILE_SIZE di quality minimum, fallback ke JPEG
      4. Di JPEG, turunkan quality bertahap sampai <= MAX_FILE_SIZE

    Args:
        image: PIL Image object (RGB mode)
        base_path: Path object dengan ekstensi (misal '1.jpg')

    Returns:
        (final_path, format_used, file_size_mb)
    """
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024

    # ── Strategy 1: WebP ──
    if ENABLE_WEBP:
        webp_path = base_path.with_suffix('.webp')
        # Coba WebP dari quality tinggi turun bertahap
        for q in range(WEBP_QUALITY_START, 50, -5):  # 90, 85, 80, ... 55
            image.save(webp_path, 'WEBP', quality=q)
            size = webp_path.stat().st_size
            if size <= max_bytes:
                # WebP cocok! 
                file_mb = size / (1024 * 1024)
                return webp_path, 'WEBP', file_mb

        # WebP gagal mencapai target → hapus, lanjut JPEG
        if webp_path.exists():
            webp_path.unlink()

    # ── Strategy 2: JPEG fallback ──
    jpg_path = base_path.with_suffix('.jpg')
    for q in range(JPEG_QUALITY_START, MIN_JPEG_QUALITY - 1, -5):  # 85, 80, 75, ... 45
        image.save(jpg_path, 'JPEG', quality=q)
        size = jpg_path.stat().st_size
        if size <= max_bytes:
            file_mb = size / (1024 * 1024)
            return jpg_path, f'JPEG (q{q})', file_mb

    # Emergency: simpan di quality minimal
    image.save(jpg_path, 'JPEG', quality=MIN_JPEG_QUALITY)
    size = jpg_path.stat().st_size
    file_mb = size / (1024 * 1024)
    return jpg_path, f'JPEG (q{MIN_JPEG_QUALITY})', file_mb


def process_chapter(chapter_dir: Path, output_dir: Path):
    name = chapter_dir.name
    print(f"\n{'='*50}")
    print(f"  >> Chapter: {name}")
    print(f"{'='*50}")

    images = find_images(chapter_dir)
    if not images:
        print(f"  [SKIP] Tidak ada gambar ditemukan. Lewati.")
        return

    raw_count = len(images)
    output_pages = calculate_output_pages(raw_count)
    output_width = OUTPUT_WIDTH

    # Validasi width
    if output_width < MIN_OUTPUT_WIDTH:
        print(f"  [WARN] OUTPUT_WIDTH ({output_width}) < MIN_OUTPUT_WIDTH ({MIN_OUTPUT_WIDTH}), pakai {MIN_OUTPUT_WIDTH}")
        output_width = MIN_OUTPUT_WIDTH
    elif output_width > MAX_OUTPUT_WIDTH:
        print(f"  [WARN] OUTPUT_WIDTH ({output_width}) > MAX_OUTPUT_WIDTH ({MAX_OUTPUT_WIDTH}), pakai {MAX_OUTPUT_WIDTH}")
        output_width = MAX_OUTPUT_WIDTH

    print(f"\n  Raw pages       : {raw_count}")
    print(f"  Target output   : {output_pages} pages")
    print(f"  Output width    : {output_width}px")
    print(f"  Rata-rata/page  : {raw_count / output_pages:.1f} raw pages")

    groups = distribute_raw_to_pages(raw_count, output_pages)

    # Buat folder output untuk chapter ini
    chapter_output = output_dir / name
    chapter_output.mkdir(parents=True, exist_ok=True)

    for i, (start, count) in enumerate(groups):
        group_images = images[start:start + count]
        base_path = chapter_output / f"{i+1}.jpg"

        print(f"  Page {i+1:2d}/{output_pages}  <- {count} raw page(s)  [{group_images[0].name} - {group_images[-1].name}]")

        # Gabung gambar jadi 1 strip
        strip_img, w, h = stitch_images_vertically(group_images, output_width)

        # Simpan dengan format optimal (WebP dulu, fallback JPEG)
        final_path, fmt, size_mb = save_optimized_image(strip_img, base_path)
        print(f"      -> {final_path.name}  ({w}x{h}px, {fmt}, {size_mb:.2f}MB)")

    print(f"\n  [OK] Selesai! {output_pages} halaman output -> {chapter_output}")


def main():
    input_dir = Path(INPUT_DIR)
    output_dir = Path(OUTPUT_DIR)

    print("+==============================================+")
    print("|   Manga Page Grouper v1.0                |")
    print("|   Gabungkan raw pages ke halaman output  |")
    print("+==============================================+")

    if not input_dir.exists():
        print(f"\n[ERROR] Folder input '{INPUT_DIR}' tidak ditemukan.")
        print(f"   Buat folder '{INPUT_DIR}/' dan taruh folder chapter di dalamnya.")
        return

    if CLEAN_OUTPUT_BEFORE_RUN and output_dir.exists():
        print(f"\n[INFO] Membersihkan folder output sebelumnya...")
        shutil.rmtree(output_dir)

    output_dir.mkdir(exist_ok=True)

    chapters = find_chapter_folders(input_dir)
    if not chapters:
        print(f"\n[ERROR] Tidak ada folder chapter di dalam '{INPUT_DIR}'.")
        return

    print(f"\nDitemukan {len(chapters)} chapter(s):")
    for c in chapters:
        img_count = len(find_images(c))
        print(f"   - {c.name} ({img_count} raw pages)")

    for chapter_dir in chapters:
        process_chapter(chapter_dir, output_dir)

    print(f"\n{'='*50}")
    print(f"  SELESAI! Cek folder '{OUTPUT_DIR}/'")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
