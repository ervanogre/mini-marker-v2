with open("mini_marker.py", "r") as f:
    code = f.read()

# 1. Tambahkan cache font agar tidak membuka file .ttf berulang kali
old_font_fn = '''def get_pil_font(sz, bold=False):'''
new_font_fn = '''_FONT_CACHE = {}
def get_pil_font(sz, bold=False):
    key = (round(sz, 1), bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]'''

code = code.replace(old_font_fn, new_font_fn, 1)
code = code.replace(
    'try: return ImageFont.truetype(fp, sz_px)',
    'try:\n                fnt = ImageFont.truetype(fp, sz_px)\n                _FONT_CACHE[key] = fnt\n                return fnt'
)

# 2. Gunakan resolusi pratinjau cepat saat tampilan biasa, dan resolusi tinggi hanya saat ekspor PNG/PDF
code = code.replace(
    'W, H = 1754, 1240  # A4 Landscape 150 DPI',
    'W, H = (1754, 1240) if export_mode else (1050, 742)'
)

# 3. Sesuaikan skala ukuran font dengan lebar kanvas W
code = code.replace('sz_px = max(10, int(sz * 2.1))', 'sz_px = max(8, int(sz * (W / 835.0)))')

with open("mini_marker.py", "w") as f:
    f.write(code)
print("OPTIMASI KECEPATAN BERHASIL DITERAPKAN!")
