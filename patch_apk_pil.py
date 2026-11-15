with open("mini_marker.py", "r") as f:
    code = f.read()

# Hapus seluruh import matplotlib & numpy agar tidak ModuleNotFoundError di Android
lines = []
for ln in code.splitlines():
    if any(k in ln for k in ("import matplotlib", "from matplotlib", "import numpy", "matplotlib.use")):
        continue
    lines.append(ln)
code = "\n".join(lines)

# Pastikan folder uploads dibuat di direktori kerja/cache yang dapat ditulis Android
code = code.replace('UP = "uploads"', 'import tempfile\nUP = os.path.join(tempfile.gettempdir(), "minimarker_up")')

# Tambahkan fungsi pengganti buat_a4 & dl_checklist berbasis Pillow (PIL) murni
pil_engine = '''
from PIL import Image, ImageDraw, ImageFont

def get_pil_font(sz, bold=False):
    sz_px = max(10, int(sz * 2.1))
    candidates = [
        "/system/fonts/Roboto-Bold.ttf" if bold else "/system/fonts/Roboto-Regular.ttf",
        "/system/fonts/DroidSans-Bold.ttf" if bold else "/system/fonts/DroidSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    for fp in candidates:
        if os.path.exists(fp):
            try: return ImageFont.truetype(fp, sz_px)
            except: pass
    return ImageFont.load_default()

def buat_a4(st, export_mode=False):
    pieces = st["pieces"]
    total = len(pieces)
    max_pages = max(1, min(3, int(st.get("max_pages", 3))))
    per_page = max(1, math.ceil(total / max_pages)) if total > 0 else 1
    pages = [pieces[i:i + per_page] for i in range(0, total, per_page)] if total > 0 else [[]]
    img_list = []
    W, H = 1754, 1240  # A4 Landscape 150 DPI
    pdf_pages = []

    for page_idx, page_pieces in enumerate(pages):
        im = Image.new("RGB", (W, H), "white")
        draw = ImageDraw.Draw(im)
        page_cnt = {}
        for p in page_pieces:
            fb = str(p.get("fabric", "1")).strip() or "1"
            page_cnt[fb] = page_cnt.get(fb, 0) + 1

        baris_ket = []
        sorted_keys = sorted(set(st["fabrics"].keys()) | set(page_cnt.keys()), key=lambda x: int(x) if x.isdigit() else 999)
        for k in sorted_keys:
            desc = st["fabrics"].get(k, f"FABRIC {k}").upper()
            jml = page_cnt.get(k, 0)
            baris_ket.append(f"{k}. {desc} ({jml} KOMPONEN)")
        for cat in st["catatan"]:
            if cat.strip():
                baris_ket.append(f"* {cat.strip().upper()}")

        fs_k = float(st["sz_ket"])
        ket_h = int((2.6 + max(1, len(baris_ket)) * (fs_k * 0.34 + 0.45)) * (H / 100.0))
        box_top = int(H * 0.085)
        box_bot = H - ket_h - 18
        box_left, box_right = 28, W - 28

        # Header
        f_jdl = get_pil_font(float(st["sz_judul"]), True)
        f_kd = get_pil_font(float(st["sz_kode"]), True)
        jdl_txt = str(st["judul"]).upper()
        if len(pages) > 1:
            jdl_txt += f" (HAL. {page_idx + 1}/{len(pages)})"
        draw.text((W // 2, 22), jdl_txt, fill="#111111", font=f_jdl, anchor="mt")
        draw.text((box_left, box_top - 8), str(st["kode"]).upper(), fill="#111111", font=f_kd, anchor="lb")

        # Bingkai Utama
        draw.rectangle([box_left, box_top, box_right, box_bot], outline="#111111", width=3)

        tot = len(page_pieces)
        if tot > 0:
            cols = int(st["kolom"]) if str(st["kolom"]).isdigit() else max(4, min(8, math.ceil(tot / 5.0)))
            rows = math.ceil(tot / cols)
            col_w = (box_right - box_left) / cols
            slot_h = (box_bot - box_top) / rows

            for c in range(1, cols):
                gx = int(box_left + c * col_w)
                for gy in range(box_top + 4, box_bot - 4, 14):
                    draw.line([(gx, gy), (gx, min(gy + 7, box_bot - 4))], fill="#94a3b8", width=1)

            f_tag = get_pil_font(float(st["sz_tag"]), True)
            f_p = get_pil_font(float(st["sz_piece"]), True)
            f_no = get_pil_font(max(7.0, float(st["sz_piece"]) - 0.5), True)

            for idx, p in enumerate(page_pieces):
                c = idx // rows
                r = idx % rows
                sx = box_left + c * col_w
                sy = box_top + r * slot_h
                cx = sx + col_w / 2

                tag_str = str(p.get("tag", "")).strip()
                if tag_str:
                    draw.text((cx, sy + 6), tag_str, fill=p.get("tag_color", "#111111"), font=f_tag, anchor="mt")

                rol = putar_pts(p["ol"], p.get("rot", 0))
                ril = putar_pts(p["il"], p.get("rot", 0))
                pts = [pt for l in (rol + ril) for pt in l]
                draw_top = sy + (28 if tag_str else 10)
                draw_bot = sy + slot_h - 46
                draw_w = max(20, col_w - 22)
                draw_h = max(20, draw_bot - draw_top)

                if pts:
                    xs = [x for x, y in pts]; ys = [y for x, y in pts]
                    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
                    pw, ph = max(maxx - minx, 0.01), max(maxy - miny, 0.01)
                    sc = min(draw_w / pw, draw_h / ph)
                    ox = cx - (pw * sc) / 2
                    oy = draw_top + (draw_h - ph * sc) / 2
                    for l in ril:
                        pl = [(ox + (x - minx) * sc, oy + (maxy - y) * sc) for x, y in l]
                        if len(pl) > 1: draw.line(pl, fill="#1d4ed8", width=2)
                    for l in rol:
                        pl = [(ox + (x - minx) * sc, oy + (maxy - y) * sc) for x, y in l]
                        if len(pl) > 1: draw.line(pl, fill="#111111", width=2)

                    ku = str(p.get("kode_urut", ""))
                    if ku:
                        bx, by = int(cx), int(oy + (ph * sc) / 2)
                        draw.rounded_rectangle([bx - 18, by - 11, bx + 18, by + 11], radius=8, fill="white", outline="#111111", width=2)
                        draw.text((bx, by), ku, fill="#111111", font=f_no, anchor="mm")

                    rt = str(p.get("right_txt", "")).strip()
                    if rt:
                        draw.text((min(sx + col_w - 6, ox + pw * sc + 6), oy + (ph * sc) / 2), rt, fill="#111111", font=f_p, anchor="lm")

                draw.text((cx, sy + slot_h - 38), str(p.get("dim", "")), fill="#111111", font=f_p, anchor="mt")
                draw.text((cx, sy + slot_h - 21), str(p.get("nama", ""))[:26], fill="#111111", font=f_p, anchor="mt")

        # Kotak Keterangan
        ky = box_bot + 10
        f_ket_h = get_pil_font(fs_k + 0.5, True)
        f_ket = get_pil_font(fs_k, True)
        draw.text((box_left, ky), "Keterangan :", fill="#111111", font=f_ket_h, anchor="lt")
        ky += int(fs_k * 2.4)
        for bk in baris_ket:
            draw.text((box_left, ky), bk, fill="#111111", font=f_ket, anchor="lt")
            ky += int(fs_k * 2.3)

        buf = io.BytesIO()
        im.save(buf, format="PNG")
        img_list.append(base64.b64encode(buf.getvalue()).decode("utf-8"))
        if export_mode:
            pdf_pages.append(im)
            if page_idx == 0:
                im.save(os.path.join(UP, "hasil.png"), format="PNG")

    if export_mode and pdf_pages:
        pdf_pages[0].save(os.path.join(UP, "hasil.pdf"), save_all=True, append_images=pdf_pages[1:])
    return img_list
'''

# Ganti fungsi buat_a4 lama dengan mesin PIL murni
s_ba4 = code.find("def buat_a4(")
e_ba4 = code.find("HTML = ", s_ba4)
if s_ba4 != -1 and e_ba4 != -1:
    code = code[:s_ba4] + pil_engine + "\n" + code[e_ba4:]

with open("mini_marker.py", "w") as f:
    f.write(code)
print("PATCH ANDROID PIL MURNI BERHASIL!")
