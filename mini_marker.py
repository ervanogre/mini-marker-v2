import os, io, re, math, base64, textwrap
from flask import Flask, request, render_template_string, send_file
import ezdxf
from ezdxf import path as ezpath
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.collections import LineCollection

app = Flask(__name__)
UP = "uploads"
os.makedirs(UP, exist_ok=True)
CUR = os.path.join(UP, "cur.dxf")

STATE = {
    "pieces": [], "judul": "JSOA47JK (008 BLACK)", "kode": "KT26JN001", "satuan": "mm", "kolom": "6",
    "fabrics": {"1": "POLY 600D SOLID 100% RECYCLED 58\" PU #MP6C (BLACK 008)"},
    "catatan": [], "font_family": "sans-serif",
    "sz_judul": 18, "sz_kode": 9, "sz_piece": 6.5, "sz_tag": 6.5, "sz_ket": 7.0
}

def get_pts(e):
    try:
        p = ezpath.make_path(e)
        return [(float(v.x), float(v.y)) for v in p.flattening(2.0)]
    except Exception:
        return []

def ekstrak_entitas(container, tx=0.0, ty=0.0):
    ol, il, txts = [], [], []
    for e in container:
        if e.dxftype() == "INSERT":
            blk = e.doc.blocks.get(e.dxf.name)
            if blk:
                ix, iy = float(e.dxf.insert.x), float(e.dxf.insert.y)
                sol, sil, st = ekstrak_entitas(blk, tx + ix, ty + iy)
                ol.extend(sol); il.extend(sil); txts.extend(st)
        elif e.dxftype() in ("TEXT", "MTEXT"):
            raw_t = e.dxf.text if e.dxftype() == "TEXT" else e.text
            clean_t = re.sub(r'\\[A-Za-z0-9]+;|[{}]', ' ', str(raw_t)).strip()
            if clean_t:
                txts.append(clean_t)
        else:
            pts = get_pts(e)
            if pts:
                shifted = [(x + tx, y + ty) for x, y in pts]
                layer = str(e.dxf.layer).upper()
                ltype = str(getattr(e.dxf, "linetype", "")).upper()
                if layer in ("1", "0", "CUT", "BOUNDARY", "OUTLINE", "PERIMETER") and "DASH" not in ltype:
                    ol.append(shifted)
                else:
                    il.append(shifted)
    return ol, il, txts

def putar_pts(lines, rot):
    if rot % 360 == 0:
        return lines
    rad = math.radians(rot)
    c, s = math.cos(rad), math.sin(rad)
    return [[(x * c - y * s, x * s + y * c) for x, y in l] for l in lines]

def hitung_dim(ol, il, satuan="mm"):
    pts = [pt for l in (ol + il) for pt in l]
    if not pts:
        return 10.0, 10.0, "0*0"
    xs = [x for x, y in pts]
    ys = [y for x, y in pts]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    f = 0.1 if satuan == "mm" else 1.0
    ws, hs = f"{round(w * f, 1):g}", f"{round(h * f, 1):g}"
    dim_str = f"{hs}*{ws}" if h > w and w < 150 else f"{ws}*{hs}"
    return max(w, 1.0), max(h, 1.0), dim_str

def deteksi_info_dxf(txts, fallback_name, layers):
    nama = str(fallback_name).upper()
    tag = ""
    mat = ""
    right_txt = ""
    qty_num = 1
    tag_kw = ("OCM", "BORDIR", "AUTOMATION", "PREPARING", "PRINTING", "EMBOSS", "HOTMELT", "AUTO")
    fab_kw = ("MA", "L2", "NON", "MESH", "600D", "200D", "840D", "420D", "1680D", "PVC", "EVA", "FOAM", "LINING", "SATIN", "NYLON", "POLY")
    all_tokens = []
    for t in txts:
        tu = t.upper().strip()
        all_tokens.extend(re.split(r"[-_/,\s:;()]+", tu))
        if any(k in tu for k in ("PIECE NAME", "NAME:", "PART:")):
            nama = tu.split(":", 1)[-1].strip()
        elif any(k in tu for k in ("MATERIAL", "FABRIC", "MAT:", "FAB:", "BAHAN", "MAT=")):
            val = tu.split(":", 1)[-1].split("=")[-1].strip()
            for pref in ("MATERIAL", "FABRIC", "BAHAN"):
                val = val.replace(pref, "").strip()
            if val: mat = val
        elif any(kw in tu for kw in tag_kw) and len(tu) <= 30:
            tag = (tag + "\n" + tu).strip() if tag else tu
        elif len(tu) > 2 and not tu.replace(".", "").isdigit() and nama == str(fallback_name).upper():
            if not any(x in tu for x in ("SIZE", "QTY", "ANNOTATION", "SCALE", "GRADE")) and tu not in fab_kw:
                nama = tu
    all_tokens.extend(re.split(r"[-_/,\s:;()]+", str(fallback_name).upper()))
    gabung_teks = " ".join([str(fallback_name).upper()] + [str(t).upper() for t in txts])
    m_kali = re.search(r"(?:[A-Z0-9]*X|X)(\d+)|(\d+)X(?:\b|[^A-Z0-9])", gabung_teks)
    if m_kali:
        angka = m_kali.group(1) or m_kali.group(2)
        if angka and int(angka) >= 2:
            right_txt = "A/B" if int(angka) == 2 else f"x{int(angka)}"
            qty_num = int(angka)
    if not mat:
        for tok in all_tokens:
            if tok in fab_kw:
                mat = tok
                break
    if not mat:
        std_layers = ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "CUT", "BOUNDARY", "OUTLINE", "PERIMETER", "TEXT", "ANNOTATION", "SEAM", "NOTCH", "GRAINLINE", "DRILL")
        non_std = [l for l in layers if l not in std_layers and not l.isdigit()]
        if non_std:
            mat = str(next(iter(non_std)))
    return nama[:40], tag[:30], mat, right_txt, qty_num

def baca_dxf(path, satuan="mm"):
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    msp_texts = []
    for e in msp:
        if e.dxftype() in ("TEXT", "MTEXT"):
            raw_t = e.dxf.text if e.dxftype() == "TEXT" else e.text
            clean_t = re.sub(r"\\[A-Za-z0-9]+;|[{}]", " ", str(raw_t)).strip()
            if clean_t and hasattr(e.dxf, "insert"):
                msp_texts.append((float(e.dxf.insert.x), float(e.dxf.insert.y), clean_t))
    raw = []
    inserts = [e for e in msp if e.dxftype() == "INSERT"]
    if inserts:
        for ins in inserts:
            blk = doc.blocks.get(ins.dxf.name)
            if blk:
                ix, iy = float(ins.dxf.insert.x), float(ins.dxf.insert.y)
                ol, il, txts = ekstrak_entitas(blk, ix, iy)
                for att in getattr(ins, "attribs", []):
                    if att.dxf.text: txts.append(str(att.dxf.text).strip())
                all_p = [pt for l in (ol + il) for pt in l]
                if all_p:
                    xs, ys = [x for x, y in all_p], [y for x, y in all_p]
                    minx, maxx, miny, maxy = min(xs) - 15, max(xs) + 15, min(ys) - 15, max(ys) + 15
                    for tx, ty, tt in msp_texts:
                        if minx <= tx <= maxx and miny <= ty <= maxy:
                            txts.append(tt)
                lays = list({str(e.dxf.layer).upper() for e in blk})
                if ol or il: raw.append((ins.dxf.name, txts, ol, il, lays))
    if not raw:
        for blk in doc.blocks:
            if not blk.name.startswith("*"):
                ol, il, txts = ekstrak_entitas(blk)
                lays = list({str(e.dxf.layer).upper() for e in blk})
                if ol or il: raw.append((blk.name, txts, ol, il, lays))
    if not raw:
        ol, il, _ = ekstrak_entitas(msp)
        clusters = []
        for is_out, line in [(True, l) for l in ol] + [(False, l) for l in il]:
            xs = [x for x, y in line]; ys = [y for x, y in line]
            b = [min(xs), min(ys), max(xs), max(ys)]
            merged = False
            for c in clusters:
                cb = c["box"]
                if not (b > cb + 5 or b < cb - 5 or b > cb + 5 or b < cb - 5):
                    (c["ol"] if is_out else c["il"]).append(line)
                    cb, cb = min(cb, b), min(cb, b)
                    cb, cb = max(cb, b), max(cb, b)
                    merged = True; break
            if not merged: clusters.append({"box": b, "ol": [line] if is_out else [], "il": [] if is_out else [line]})
        for idx, c in enumerate(clusters, 1):
            b = c["box"]
            txts = [tt for tx, ty, tt in msp_texts if (b - 15) <= tx <= (b + 15) and (b - 15) <= ty <= (b + 15)]
            raw.append((f"KOMPONEN {idx}", txts, c["ol"], c["il"], []))
    mat_map, fabrics_found, pieces = {}, {}, []
    for idx, (bname, txts, ol, il, lays) in enumerate(raw, 1):
        if not ol and il: ol, il = il, []
        nama, tag, mat, right_txt, qty_num = deteksi_info_dxf(txts, bname, lays)
        mat_key = str(mat).strip() if str(mat).strip() else "MAIN FABRIC"
        if mat_key not in mat_map:
            no_fab = str(len(mat_map) + 1)
            mat_map[mat_key] = no_fab
            fabrics_found[no_fab] = mat_key
        no_fab = mat_map[mat_key]
        w, h, dim_str = hitung_dim(ol, il, satuan)
        pieces.append({"nama": nama, "qty": qty_num, "dim": dim_str, "urut": idx, "fabric": no_fab, "tag": tag, "tag_color": "#111111", "right_txt": right_txt, "rot": 0, "w": w, "h": h, "ol": ol, "il": il})
    STATE["fabrics"] = fabrics_found if fabrics_found else {"1": "MAIN FABRIC"}
    return pieces


DEPT_COLORS = {
    "OCM": "#dc2626",
    "BORDIR": "#1d4ed8",
    "AUTOMATION": "#7e22ce",
    "AUTO": "#7e22ce",
    "PREPARING": "#047857",
    "PRINTING": "#d97706",
    "EMBOSS": "#be185d"
}

def warna_otomatis_tag(tag_str, current_color):
    if current_color and current_color != "#111111":
        return current_color
    tu = str(tag_str).upper()
    for kw, col in DEPT_COLORS.items():
        if kw in tu:
            return col
    return current_color or "#111111"

def buat_a4(st, export_mode=False):
    from matplotlib.backends.backend_pdf import PdfPages
    # Kelompokkan dan urutkan pattern berdasarkan nomor fabric (1, 2, 3, dst)
    pieces = sorted(
        st["pieces"],
        key=lambda p: (
            int(str(p.get("fabric", "1")).strip()) if str(p.get("fabric", "1")).strip().isdigit() else 999,
            str(p.get("nama", ""))
        )
    )
    ff = st["font_family"]
    grup_cnt = {}
    for p in pieces:
        g = str(p.get('fabric', '1')).strip() or '1'
        grup_cnt[g] = grup_cnt.get(g, 0) + 1
        p['kode_urut'] = f"{g}.{grup_cnt[g]}"

    total_all = len(pieces)

    # Tentukan jumlah halaman (maksimal 3 lembar A4)
    mp = str(st.get("max_pages", 3))
    if mp in ("1", "2", "3"):
        total_pages = min(int(mp), max(1, total_all))
    else:
        total_pages = min(3, max(1, math.ceil(total_all / 35)))

    per_page = max(1, math.ceil(total_all / total_pages))
    pdf_path = os.path.join(UP, "hasil.pdf")
    img_list = []

    pdf = PdfPages(pdf_path) if export_mode else None
    if True:
        for page_idx in range(total_pages):
            page_pieces = pieces[page_idx * per_page : (page_idx + 1) * per_page]
            if not page_pieces and page_idx > 0:
                continue

            # Hitung jumlah komponen per fabric KHUSUS pada lembar ini
            page_cnt = {}
            for p in page_pieces:
                g = str(p.get('fabric', '1')).strip() or '1'
                page_cnt[g] = page_cnt.get(g, 0) + 1

            # Susun Keterangan HANYA sesuai nomor fabric yang tampil pada lembar ini
            sorted_keys = sorted(set(st["fabrics"].keys()) | set(page_cnt.keys()), key=lambda x: int(x) if x.isdigit() else 999)
            baris_ket = []
            for g_id in sorted_keys:
                nama_fab = st["fabrics"].get(g_id, f"FABRIC {g_id}").upper()
                jml_komp = page_cnt.get(g_id, 0)
                baris_ket.append(f"{g_id}. {nama_fab} ({jml_komp} KOMPONEN)")

            # Tambahkan catatan tambahan di lembar terakhir
            if page_idx == total_pages - 1:
                for cat in st["catatan"]:
                    if cat.strip():
                        baris_ket.append(f"* {cat.strip().upper()}")

            fs_k = float(st["sz_ket"])
            # Hitung tinggi area keterangan secara fleksibel mengikuti jumlah baris dan ukuran font keterangan
            ket_area_h = 2.6 + max(1, len(baris_ket)) * (fs_k * 0.34 + 0.45)

            fig = plt.figure(figsize=(11.69, 8.27), dpi=115 if not export_mode else 180)
            fig.patch.set_facecolor('white')
            ax = fig.add_axes([0.015, 0.015, 0.97, 0.97])
            ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis('off')

            # Batas atas kotak menyesuaikan ukuran font Judul/Style
            box_top = min(93.5, max(82.0, 96.5 - (float(st["sz_judul"]) * 0.22)))
            box_bot = min(55.0, max(5.5, ket_area_h + 1.0))

            if str(st.get("kode", "")).strip():
                ax.text(0.6, 93.2, str(st["kode"]).upper(), ha='left', va='center', fontsize=st["sz_kode"], fontweight='bold', family=ff, color='#111')

            ax.text(50, 96.2, str(st["judul"]).upper(), ha='center', va='center', fontsize=st["sz_judul"], fontweight='bold', family=ff, color='#111')
            if total_pages > 1:
                ax.text(99.4, 93.2, f"LEMBAR {page_idx + 1}/{total_pages}", ha='right', va='center', fontsize=max(2.0, st["sz_kode"] - 1.5), fontweight='bold', family=ff, color='#333')

            # Kotak Border Utama (Berhenti tepat di atas area Keterangan di setiap lembar)
            ax.add_patch(patches.Rectangle((0.5, box_bot), 99.0, box_top - box_bot, lw=1.1, ec='#111', fc='none'))

            # Keterangan di bagian bawah SETIAP lembar sesuai fabric di lembar tersebut
            y_ket_title = box_bot - 1.2
            ax.text(0.8, y_ket_title, "KETERANGAN :", fontsize=fs_k + 0.4, fontweight='bold', family=ff, color='#111', va='top')
            ax.plot([0.8, 0.8 + (fs_k * 1.35)], [y_ket_title - 1.25, y_ket_title - 1.25], color='#111', lw=0.8)
            if baris_ket:
                ax.text(0.8, y_ket_title - 1.7, "\n".join(baris_ket), fontsize=fs_k, fontweight='bold', family=ff, va='top', linespacing=1.4, color='#111')

            tot = len(page_pieces)
            if tot > 0:
                avail_box_h = max(25.0, box_top - box_bot)
                if str(st["kolom"]).isdigit():
                    cols = int(st["kolom"])
                else:
                    # Semakin pendek kotak (karena keterangan banyak), kolom otomatis bertambah agar isi tidak gepeng
                    faktor_tinggi = 82.0 / avail_box_h
                    cols = max(4, min(8, math.ceil((tot / 5.0) * math.sqrt(faktor_tinggi))))
                col_w = 97.6 / cols
                per_col = math.ceil(tot / cols)
                rotated_data, max_dim = [], 1.0
                for p in page_pieces:
                    rol, ril = putar_pts(p['ol'], p.get('rot', 0)), putar_pts(p['il'], p.get('rot', 0))
                    pts = [pt for l in (rol + ril) for pt in l]
                    if pts:
                        xs, ys = [x for x, y in pts], [y for x, y in pts]
                        pw, ph = max(max(xs) - min(xs), 0.01), max(max(ys) - min(ys), 0.01)
                        max_dim = max(max_dim, pw, ph)
                    else:
                        pw, ph = 10.0, 10.0
                    rotated_data.append((rol, ril, pw, ph))

                base_scale = (col_w * 0.78) / max_dim
                for c in range(cols):
                    start_i, end_i = c * per_col, min(tot, (c + 1) * per_col)
                    if start_i >= tot:
                        break
                    n_items = end_i - start_i
                    x_left = 1.2 + c * col_w
                    x_center = x_left + col_w / 2
                    y_top_start, y_bottom_limit = box_top - 0.9, box_bot + 0.9
                    slot_h = (y_top_start - y_bottom_limit) / n_items

                    for r, idx in enumerate(range(start_i, end_i)):
                        p = page_pieces[idx]
                        rol, ril, pw, ph = rotated_data[idx]
                        y_top, y_bot = y_top_start - r * slot_h, y_top_start - (r + 1) * slot_h

                        tag_txt = str(p.get('tag', '')).strip()
                        tag_lines = tag_txt.count('\n') + 1 if tag_txt else 0
                        top_space = (tag_lines * (st["sz_tag"] * 0.25 + 0.55)) if tag_txt else 0.35

                        nama_wrapped = "\n".join(textwrap.wrap(str(p['nama']), width=22))
                        nama_lines = nama_wrapped.count('\n') + 1
                        fs_p = st["sz_piece"]
                        bot_space = (fs_p * 0.25) + (nama_lines * (fs_p * 0.24 + 0.35)) + 0.65

                        draw_h = max(slot_h - top_space - bot_space - 0.6, 1.8)
                        r_txt = str(p.get('right_txt', '')).strip()
                        draw_w = col_w * (0.64 if r_txt else 0.80)
                        all_pts = [pt for l in (rol + ril) for pt in l]

                        if all_pts:
                            xs, ys = [x for x, y in all_pts], [y for x, y in all_pts]
                            minx, miny = min(xs), min(ys)
                            # Skala fleksibel: menyesuaikan tinggi slot (akibat perubahan Keterangan) & lebar kolom
                            tinggi_rasio = max(0.35, min(1.35, avail_box_h / 80.0))
                            sc = min(base_scale * tinggi_rasio, draw_w / pw, draw_h / ph)
                            if pw * sc < draw_w * 0.35 and ph * sc < draw_h * 0.45:
                                sc = min(draw_w * 0.65 / pw, draw_h * 0.78 / ph)
                            w_drawn, h_drawn = pw * sc, ph * sc
                            y_mid_slot = y_bot + bot_space + (slot_h - top_space - bot_space) / 2
                            x_shift = (col_w * 0.08) if r_txt else 0.0
                            ox, oy = (x_center - x_shift) - w_drawn / 2, y_mid_slot - h_drawn / 2
                            top_edge, bot_edge = oy + h_drawn, oy

                            if tag_txt:
                                ax.text(x_center, top_edge + 0.45, tag_txt.upper(), ha='center', va='bottom', fontsize=st["sz_tag"], fontweight='bold', family=ff, color=p.get('tag_color', '#111111'), linespacing=1.15)
                            if r_txt:
                                ax.text(ox + w_drawn + 0.6, y_mid_slot, r_txt, ha='left', va='center', fontsize=st["sz_tag"], fontweight='bold', family=ff, color=p.get('tag_color', '#111111'), clip_on=False)
                            kode_lbl = p.get('kode_urut', '1.1')
                            ax.text(max(x_left + 1.4, ox - 1.5), top_edge - 0.35, kode_lbl, ha='center', va='center', fontsize=max(1.5, fs_p - 0.5), fontweight='bold', family=ff, bbox=dict(boxstyle='round,pad=0.22,rounding_size=0.8', fc='white', ec='#111', lw=0.75))

                            for l in ril:
                                ax.plot([ox + (x - minx) * sc for x, y in l], [oy + (y - miny) * sc for x, y in l], color='#1d4ed8', lw=0.55, ls='--')
                            for l in rol:
                                ax.plot([ox + (x - minx) * sc for x, y in l], [oy + (y - miny) * sc for x, y in l], color='#111111', lw=0.85)

                            ax.text(x_center, bot_edge - 0.35, p['dim'], ha='center', va='top', fontsize=max(1.5, fs_p - 0.3), family=ff, color='#111')
                            ax.text(x_center, bot_edge - 0.35 - (fs_p * 0.25 + 0.25), nama_wrapped, ha='center', va='top', fontsize=fs_p, family=ff, color='#111', linespacing=1.1)

            if export_mode:
                pdf.savefig(fig, dpi=300)
                if page_idx == 0:
                    fig.savefig(os.path.join(UP, "hasil.png"), format='png', dpi=220)
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=115)
            plt.close(fig)
            buf.seek(0)
            img_list.append(base64.b64encode(buf.getvalue()).decode('utf-8'))
    if pdf:
        pdf.close()
    return img_list

HTML = """<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box;font-family:sans-serif}body{margin:0;background:#0b1120;color:#f8fafc;padding:12px}
.box{max-width:560px;margin:auto}.up{display:block;border:2px dashed #334155;background:#131c31;border-radius:14px;padding:35px 15px;text-align:center;cursor:pointer;margin:16px 0}
.btn{width:100%;background:#2563eb;color:#fff;border:0;padding:13px;border-radius:10px;font-size:15px;font-weight:bold;cursor:pointer}
.bar{display:flex;justify-content:space-between;align-items:center;background:#131c31;padding:10px;border-radius:10px;margin-bottom:10px;border:1px solid #1e293b}
.bsm{background:#1e293b;color:#f8fafc;border:1px solid #334155;padding:7px 10px;border-radius:8px;font-size:12px;text-decoration:none}
.card{background:#131c31;padding:14px;border-radius:12px;margin-top:12px;border:1px solid #1e293b}
h4{margin:0 0 10px 0;font-size:13px;color:#94a3b8;text-transform:uppercase}
label{display:block;font-size:12px;color:#94a3b8;margin-bottom:4px}
input,select{width:100%;background:#0b1120;border:1px solid #283548;color:#f8fafc;padding:8px;border-radius:8px;font-size:13px}
.prow{display:grid;grid-template-columns:1.5fr 0.5fr 0.5fr 1.0fr 1.0fr 26px 28px;gap:4px;margin-bottom:7px;align-items:center}
.cbtn{width:30px;height:33px;padding:2px;border:1px solid #334155;border-radius:7px;background:#0b1120;cursor:pointer}
.rot{background:#1e293b;border:1px solid #334155;color:#fff;height:33px;border-radius:7px;cursor:pointer}
.frow{display:grid;grid-template-columns:88px 1fr 34px;gap:7px;align-items:center;margin-bottom:7px}
.del{background:#1e293b;border:1px solid #334155;color:#ef4444;height:34px;border-radius:8px;cursor:pointer}
.out{flex:1;background:#1e293b;border:1px solid #334155;color:#e2e8f0;padding:9px;border-radius:8px;font-size:13px;cursor:pointer}
.sz{display:flex;justify-content:space-between;align-items:center;background:#0b1120;border:1px solid #283548;padding:7px 10px;border-radius:8px;margin-top:7px}
.stp{background:#1e293b;border:1px solid #334155;color:#fff;width:28px;height:28px;border-radius:6px;cursor:pointer}

@media (min-width: 768px), (orientation: landscape) and (min-width: 560px) {
  .box { max-width: 1440px !important; }
  .desk-grid { display: grid; grid-template-columns: 1.55fr 1fr; gap: 16px; align-items: start; }
  .desk-left { position: sticky; top: 12px; }
  .desk-right { max-height: calc(100vh - 80px); overflow-y: auto; padding-right: 4px; }
}

body{padding-bottom:78px !important}
.float-save-bar{
  position:fixed;bottom:0;left:0;right:0;
  background:rgba(11,17,32,0.92);backdrop-filter:blur(8px);
  border-top:1px solid #334155;padding:10px 14px;
  z-index:999;display:flex;justify-content:center;
  box-shadow:0 -6px 20px rgba(0,0,0,0.45);
}
.float-save-bar .btn{max-width:560px;margin:0 !important;box-shadow:0 4px 12px rgba(37,99,235,0.4);}

.prow{display:block;background:#0b1120 !important;border:1px solid #283548 !important;border-radius:10px !important;padding:9px !important;margin-bottom:9px !important;width:100% !important}
.prow-top{display:grid !important;grid-template-columns:46px 1fr !important;gap:8px !important;align-items:center !important;margin-bottom:7px !important;width:100% !important}
.prow-bot{display:grid !important;grid-template-columns:1fr 1.15fr 0.85fr 36px !important;gap:6px !important;align-items:center !important;width:100% !important}
.prow input[type="text"]{width:100% !important;min-width:0 !important;background:#131c31 !important;border:1px solid #334155 !important;padding:8px 9px !important;font-size:13px !important;color:#f8fafc !important;border-radius:8px !important}
.prow input[type="color"]{width:36px !important;height:36px !important;padding:2px !important;border-radius:8px !important}
</style></head><body><div class="box">
{% if mode=='home' %}
<div style="text-align:center;margin-bottom:8px">
  <svg viewBox="0 0 540 95" style="width:100%;max-width:480px;height:auto;display:block;margin:auto">
    <defs>
      <linearGradient id="titleGrad" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#f43f5e"/>
        <stop offset="50%" stop-color="#38bdf8"/>
        <stop offset="100%" stop-color="#22c55e"/>
      </linearGradient>
      <filter id="titleShadow" x="-10%" y="-10%" width="130%" height="130%">
        <feDropShadow dx="2" dy="3" stdDeviation="2" flood-color="#000000" flood-opacity="0.9"/>
      </filter>
    </defs>
    <g transform="rotate(-1.5 270 50)" filter="url(#titleShadow)">
      <text x="270" y="62" text-anchor="middle" font-family="Impact, Arial Black, sans-serif" font-size="42" font-weight="900" font-style="italic" letter-spacing="1.5" stroke="#020617" stroke-width="8" stroke-linejoin="round" fill="none">MINI MARKER STUDIO</text>
      <text x="270" y="62" text-anchor="middle" font-family="Impact, Arial Black, sans-serif" font-size="42" font-weight="900" font-style="italic" letter-spacing="1.5" stroke="#ffffff" stroke-width="2" stroke-linejoin="round" fill="none">MINI MARKER STUDIO</text>
      <text x="270" y="62" text-anchor="middle" font-family="Impact, Arial Black, sans-serif" font-size="42" font-weight="900" font-style="italic" letter-spacing="1.5" fill="url(#titleGrad)">MINI MARKER STUDIO</text>
    </g>
  </svg>
</div>

<div style="margin:18px 0 12px 0;text-align:center;background:radial-gradient(circle at center,#1e293b 0%,#0b1120 100%);border:1px solid #334155;border-radius:14px;padding:12px 8px;box-shadow:0 8px 20px rgba(0,0,0,0.4)">
  <svg viewBox="0 0 500 135" style="width:100%;max-width:440px;height:auto;display:block;margin:auto">
    <defs>
      <linearGradient id="grafGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#38bdf8"/>
        <stop offset="50%" stop-color="#3b82f6"/>
        <stop offset="100%" stop-color="#a855f7"/>
      </linearGradient>
      <filter id="neonShadow" x="-10%" y="-10%" width="130%" height="130%">
        <feDropShadow dx="3" dy="4" stdDeviation="2.5" flood-color="#000000" flood-opacity="0.85"/>
      </filter>
    </defs>
    <!-- Aksen percikan cat grafiti -->
    <circle cx="45" cy="30" r="6" fill="#38bdf8" opacity="0.7"/>
    <circle cx="34" cy="42" r="3" fill="#a855f7" opacity="0.8"/>
    <circle cx="455" cy="95" r="7" fill="#a855f7" opacity="0.7"/>
    <circle cx="468" cy="82" r="3.5" fill="#38bdf8" opacity="0.8"/>
    <path d="M 35 105 Q 250 125 465 98" stroke="url(#grafGrad)" stroke-width="3.5" fill="none" stroke-linecap="round" opacity="0.85"/>
    <path d="M 75 113 Q 250 128 425 108" stroke="#f43f5e" stroke-width="2" fill="none" stroke-linecap="round" opacity="0.8"/>

    <!-- Subjudul kecil "Design by" -->
    <text x="250" y="34" text-anchor="middle" fill="#cbd5e1" font-family="Comic Sans MS, Chalkboard SE, Impact, sans-serif" font-size="15" font-weight="bold" font-style="italic" letter-spacing="3">
      DESIGN BY
    </text>

    <!-- Tulisan Utama Grafiti "ERVAN ALVIAN" -->
    <g transform="rotate(-2.5 250 75)" filter="url(#neonShadow)">
      <!-- Lapisan Outline Hitam Tebal -->
      <text x="250" y="82" text-anchor="middle" font-family="Impact, Arial Black, sans-serif" font-size="48" font-weight="900" font-style="italic" letter-spacing="2" stroke="#020617" stroke-width="9" stroke-linejoin="round" fill="none">
        ERVAN ALVIAN
      </text>
      <!-- Lapisan Highlight Putih -->
      <text x="250" y="82" text-anchor="middle" font-family="Impact, Arial Black, sans-serif" font-size="48" font-weight="900" font-style="italic" letter-spacing="2" stroke="#ffffff" stroke-width="2.5" stroke-linejoin="round" fill="none">
        ERVAN ALVIAN
      </text>
      <!-- Isi Gradien Grafiti -->
      <text x="250" y="82" text-anchor="middle" font-family="Impact, Arial Black, sans-serif" font-size="48" font-weight="900" font-style="italic" letter-spacing="2" fill="url(#grafGrad)">
        ERVAN ALVIAN
      </text>
    </g>
  </svg>
</div>
<form method="POST" action="/proses" enctype="multipart/form-data">
<label class="up" for="f" style="padding:22px 14px;margin:10px 0">
  <svg viewBox="0 0 240 62" style="width:160px;height:auto;display:block;margin:0 auto 2px auto">
  <g transform="rotate(-2 120 31)" filter="url(#neonShadow)">
    <text x="120" y="45" text-anchor="middle" font-family="Impact, Arial Black, sans-serif" font-size="44" font-weight="900" font-style="italic" letter-spacing="2" stroke="#020617" stroke-width="8" stroke-linejoin="round" fill="none">DXF</text>
    <text x="120" y="45" text-anchor="middle" font-family="Impact, Arial Black, sans-serif" font-size="44" font-weight="900" font-style="italic" letter-spacing="2" stroke="#ffffff" stroke-width="2" stroke-linejoin="round" fill="none">DXF</text>
    <text x="120" y="45" text-anchor="middle" font-family="Impact, Arial Black, sans-serif" font-size="44" font-weight="900" font-style="italic" letter-spacing="2" fill="url(#grafGrad)">DXF</text>
  </g>
</svg>
  <span id="lbl" style="font-size:12px;color:#94a3b8">Wajib — Ketuk untuk memilih file DXF atau Proyek</span>
  <input type="file" id="f" name="file_dxf" accept=".dxf,.json" required style="display:none" onchange="document.getElementById('lbl').innerText=this.files.item(0).name">
</label>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px">
  <label class="up" for="f_jacci" style="padding:16px 10px;margin:0;border-color:#1e3a8a;background:#0f172a">
    <svg viewBox="0 0 240 58" style="width:130px;height:auto;display:block;margin:0 auto 2px auto">
  <g transform="rotate(-2 120 29)" filter="url(#neonShadow)">
    <text x="120" y="42" text-anchor="middle" font-family="Impact, Arial Black, sans-serif" font-size="38" font-weight="900" font-style="italic" letter-spacing="1.5" stroke="#020617" stroke-width="7" stroke-linejoin="round" fill="none">JACJI</text>
    <text x="120" y="42" text-anchor="middle" font-family="Impact, Arial Black, sans-serif" font-size="38" font-weight="900" font-style="italic" letter-spacing="1.5" stroke="#ffffff" stroke-width="1.8" stroke-linejoin="round" fill="none">JACJI</text>
    <text x="120" y="42" text-anchor="middle" font-family="Impact, Arial Black, sans-serif" font-size="38" font-weight="900" font-style="italic" letter-spacing="1.5" fill="url(#grafGrad)">JACJI</text>
  </g>
</svg>
    <span id="lbl_jacci" style="font-size:11px;color:#64748b">Opsional (.xlsx)</span>
    <input type="file" id="f_jacci" name="file_jacci" accept=".xlsx,.xls" style="display:none" onchange="document.getElementById('lbl_jacci').innerText=this.files.item(0).name">
  </label>
  <label class="up" for="f_spread" style="padding:16px 10px;margin:0;border-color:#065f46;background:#0f172a">
    <svg viewBox="0 0 280 68" style="width:148px;height:auto;display:block;margin:0 auto 2px auto">
  <g transform="rotate(-2 140 34)" filter="url(#neonShadow)">
    <text x="140" y="30" text-anchor="middle" font-family="Impact, Arial Black, sans-serif" font-size="27" font-weight="900" font-style="italic" letter-spacing="1" stroke="#020617" stroke-width="6" stroke-linejoin="round" fill="none">PLANNING</text>
    <text x="140" y="30" text-anchor="middle" font-family="Impact, Arial Black, sans-serif" font-size="27" font-weight="900" font-style="italic" letter-spacing="1" stroke="#ffffff" stroke-width="1.5" stroke-linejoin="round" fill="none">PLANNING</text>
    <text x="140" y="30" text-anchor="middle" font-family="Impact, Arial Black, sans-serif" font-size="27" font-weight="900" font-style="italic" letter-spacing="1" fill="url(#titleGrad)">PLANNING</text>
    <text x="140" y="58" text-anchor="middle" font-family="Impact, Arial Black, sans-serif" font-size="27" font-weight="900" font-style="italic" letter-spacing="1" stroke="#020617" stroke-width="6" stroke-linejoin="round" fill="none">SPREAD</text>
    <text x="140" y="58" text-anchor="middle" font-family="Impact, Arial Black, sans-serif" font-size="27" font-weight="900" font-style="italic" letter-spacing="1" stroke="#ffffff" stroke-width="1.5" stroke-linejoin="round" fill="none">SPREAD</text>
    <text x="140" y="58" text-anchor="middle" font-family="Impact, Arial Black, sans-serif" font-size="27" font-weight="900" font-style="italic" letter-spacing="1" fill="url(#titleGrad)">SPREAD</text>
  </g>
</svg>
    <span id="lbl_spread" style="font-size:11px;color:#64748b">Opsional (.xlsx)</span>
    <input type="file" id="f_spread" name="file_spread" accept=".xlsx,.xls" style="display:none" onchange="document.getElementById('lbl_spread').innerText=this.files.item(0).name">
  </label>
</div>
<button class="btn" type="submit">Buat Mini Marker</button></form>
{% else %}
<div style="background:#131c31;padding:12px 14px;border-radius:10px;margin-bottom:8px;border:1px solid #1e293b;text-align:center">
  <div style="font-size:17px;font-weight:bold;color:#f8fafc;letter-spacing:0.5px">{{st.judul}}</div>
  <div style="font-size:11px;color:#94a3b8;margin-top:2px">{{st.kode}} · {{st.pieces|length}} Komponen</div>
</div>
<div class="bar" style="justify-content:center;flex-wrap:wrap;gap:6px">
  <a href="/dl/proj" class="bsm" style="background:#0f766e;border-color:#14b8a6">Save</a>
  <a href="/dl/png" class="bsm">PNG</a>
  <a href="/dl/pdf" class="bsm">Cetak/PDF</a>
  <a href="/dl/checklist" class="bsm" style="background:#1e3a8a;border-color:#3b82f6">Distribusi Panel</a>
  <a href="/" class="bsm" style="background:#334155">Tutup</a>
</div>
<div class="desk-grid">
<div class="desk-left">
<form method="POST" action="/update" style="display:flex;align-items:center;gap:6px;background:#131c31;padding:8px 10px;border-radius:10px;margin-bottom:10px;border:1px solid #1e293b">
<span style="font-size:12px;color:#94a3b8;font-weight:bold;margin-right:auto">Pilih Jumlah Lembar:</span>
{% for p_opt in range(1, 4) %}<button type="submit" name="max_pages" value="{{p_opt}}" style="padding:7px 12px;border-radius:8px;font-size:12px;font-weight:bold;cursor:pointer;border:1px solid {{'#2563eb' if st.max_pages==p_opt else '#334155'}};background:{{'#2563eb' if st.max_pages==p_opt else '#1e293b'}};color:#fff">{{p_opt}} Lembar</button>{% endfor %}
</form>
<div style="background:#020617;padding:6px;border-radius:10px;overflow:auto">{% for im in img %}<div style="margin-bottom:8px"><small style="color:#94a3b8;display:block;margin-bottom:4px">Halaman {{loop.index}} dari {{img|length}}</small><img src="data:image/png;base64,{{im}}" onclick="openPreview(this.src)" title="Ketuk untuk memperbesar" style="width:100%;border-radius:4px;cursor:zoom-in"></div>{% endfor %}</div>
</div>
<div class="desk-right">
<form method="POST" action="/update"><div class="card">
<div onclick="toggleSec('secLembar','icLembar')" style="display:flex;justify-content:space-between;align-items:center;cursor:pointer">
  <h4 style="margin:0">Edit Lembar</h4><span id="icLembar" style="font-size:12px;color:#38bdf8">▶</span>
</div>
<div id="secLembar" style="display:none;margin-top:10px">
<label>STYLE (Top Center)</label><input type="text" name="judul" value="{{st.judul}}" style="margin-bottom:8px">
<div style="display:flex;gap:8px;margin-bottom:8px">
<div style="flex:1"><label>KT ORDER (Kiri Atas)</label><input type="text" name="kode" value="{{st.kode}}"></div>
<div style="flex:1"><label>Satuan</label><select name="satuan"><option value="mm" {{'selected' if st.satuan=='mm' else ''}}>Milimeter (mm)</option><option value="cm" {{'selected' if st.satuan=='cm' else ''}}>Sentimeter (cm)</option></select></div></div>
<div style="display:flex;gap:8px;margin-bottom:12px"><div style="flex:1"><label>Maks Piece / Lembar</label><select name="per_page">{% for pp in [18,24,30,36,42] %}<option value="{{pp}}" {{ 'selected' if st.per_page==pp else '' }}>{{pp}} Piece / A4</option>{% endfor %}</select></div></div></div><div style="flex:1"><div style="display:flex;gap:8px;margin-bottom:8px">
<div style="flex:1"><label>Susunan Kelompok</label>
<select name="sort_mode">
  <option value="fabric" {{'selected' if st.sort_mode=='fabric' else ''}}>Per Grup Fabric (1.1, 2.1...)</option>
  <option value="dept" {{'selected' if st.sort_mode=='dept' else ''}}>Per Departemen (OCM, Bordir...)</option>
</select></div>
<div style="flex:1"><label>Rekap Distribusi</label>
<select name="show_dist_summary">
  <option value="1" {{'selected' if st.show_dist_summary else ''}}>Tampilkan di Bawah</option>
  <option value="0" {{'selected' if not st.show_dist_summary else ''}}>Sembunyikan</option>
</select></div>
</div>
<label>Jumlah Kolom</label><select name="kolom" style="margin-bottom:12px"><option value="auto" {{'selected' if st.kolom=='auto' else ''}}>Otomatis</option>{% for k in ['4','5','6','7','8'] %}<option value="{{k}}" {{'selected' if st.kolom==k else ''}}>{{k}} Kolom</option>{% endfor %}</select>
</div></div>
<div class="card">
<div onclick="toggleSec('secFont','icFont')" style="display:flex;justify-content:space-between;align-items:center;cursor:pointer">
  <h4 style="margin:0">Font & Ukuran Teks</h4><span id="icFont" style="font-size:12px;color:#38bdf8">▶</span>
</div>
<div id="secFont" style="display:none;margin-top:10px">
<select name="font_family"><option value="sans-serif" {{'selected' if st.font_family=='sans-serif' else ''}}>Arial (standar)</option><option value="monospace" {{'selected' if st.font_family=='monospace' else ''}}>Monospace</option><option value="serif" {{'selected' if st.font_family=='serif' else ''}}>Times</option></select>
<div class="sz"><span>STYLE</span><div style="display:flex;gap:6px"><button type="button" class="stp" onclick="adj('sz_judul',-1)">-</button><input type="number" step="0.5" min="1" id="sz_judul" name="sz_judul" value="{{st.sz_judul}}" style="width:48px;text-align:center;padding:4px"><button type="button" class="stp" onclick="adj('sz_judul',1)">+</button></div></div>
<div class="sz"><span>KT ORDER</span><div style="display:flex;gap:6px"><button type="button" class="stp" onclick="adj('sz_kode',-1)">-</button><input type="number" step="0.5" min="1" id="sz_kode" name="sz_kode" value="{{st.sz_kode}}" style="width:48px;text-align:center;padding:4px"><button type="button" class="stp" onclick="adj('sz_kode',1)">+</button></div></div>
<div class="sz"><span>Teks piece</span><div style="display:flex;gap:6px"><button type="button" class="stp" onclick="adj('sz_piece',-1)">-</button><input type="number" step="0.5" min="1" id="sz_piece" name="sz_piece" value="{{st.sz_piece}}" style="width:48px;text-align:center;padding:4px"><button type="button" class="stp" onclick="adj('sz_piece',1)">+</button></div></div>
<div class="sz"><span>LUAR LINE</span><div style="display:flex;gap:6px"><button type="button" class="stp" onclick="adj('sz_tag',-1)">-</button><input type="number" step="0.5" min="1" id="sz_tag" name="sz_tag" value="{{st.sz_tag}}" style="width:48px;text-align:center;padding:4px"><button type="button" class="stp" onclick="adj('sz_tag',1)">+</button></div></div>
<div class="sz"><span>Keterangan</span><div style="display:flex;gap:6px"><button type="button" class="stp" onclick="adj('sz_ket',-1)">-</button><input type="number" step="0.5" min="1" id="sz_ket" name="sz_ket" value="{{st.sz_ket}}" style="width:48px;text-align:center;padding:4px"><button type="button" class="stp" onclick="adj('sz_ket',1)">+</button></div></div>
</div>
<div class="card">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
<div onclick="togglePieces()" style="display:flex;align-items:center;gap:6px;cursor:pointer;flex:1">
  <span id="piecesIcon" style="font-size:12px;color:#38bdf8">▶</span>
  <h4 style="margin:0">Pieces ({{st.pieces|length}})</h4>
</div>
<div style="display:flex;gap:6px">
  <button type="button" onclick="togglePieces()" id="piecesBtnTxt" class="bsm" style="cursor:pointer">Tampilkan</button>
  <button type="submit" name="aksi" value="add_piece" class="bsm" style="cursor:pointer">+ Tambah</button>
</div>
</div>
<div id="piecesList" style="display:none;margin-top:10px">
<div style="display:flex;gap:6px;margin-bottom:9px">
  <input type="text" id="searchPieceInp" onkeyup="filterPieces()" placeholder="Cari nomor (1.2) atau nama piece..." style="flex:1;background:#0b1120;border:1px solid #38bdf8;padding:8px 10px;border-radius:8px;font-size:13px;color:#f8fafc">
  <button type="button" onclick="clearSearchPiece()" class="bsm" style="padding:0 12px;font-weight:bold;color:#f87171" title="Hapus Pencarian">✕</button>
</div>
{% for p in st.pieces %}
<div class="prow">
  <input type="hidden" name="q_{{loop.index0}}" value="{{p.qty}}">
  <input type="hidden" name="f_{{loop.index0}}" value="{{p.fabric}}">
  <div class="prow-top">
    <span style="font-size:11px;font-weight:bold;color:#38bdf8;text-align:center;background:#131c31;border:1px solid #334155;padding:7px 2px;border-radius:7px">{{p.get('kode_urut', loop.index)}}</span>
    <input type="text" name="n_{{loop.index0}}" value="{{p.nama}}" placeholder="Nama Komponen">
    
  </div>
  <div class="prow-bot">
    <input type="text" name="d_{{loop.index0}}" value="{{p.dim}}" placeholder="Ukuran">
    <input type="text" name="t_{{loop.index0}}" value="{{p.tag}}" placeholder="LUAR LINE">
    <input type="text" name="rt_{{loop.index0}}" value="{{p.get('right_txt', '')}}" placeholder="A/B">
    <input type="color" name="tc_{{loop.index0}}" value="{{p.tag_color}}" class="cbtn" title="Warna Tag">
  </div>
</div>
{% endfor %}
<small style="color:#64748b;font-size:11px">Kolom: Nama · Qty · No Fabric · LUAR LINE · A/B · Warna · Putar</small></div></div>
<div class="card">
<div onclick="toggleSec('secKet','icKet')" style="display:flex;justify-content:space-between;align-items:center;cursor:pointer">
  <h4 style="margin:0">Keterangan</h4><span id="icKet" style="font-size:12px;color:#38bdf8">▶</span>
</div>
<div id="secKet" style="display:none;margin-top:10px">
{% for k, v in st.fabrics.items() %}<div class="frow"><div><b style="font-size:12px">Fabric {{k}}</b><br><small style="color:#64748b">{{counts.get(k,0)}} komp</small></div><input type="text" name="fab_val_{{k}}" value="{{v}}"><button type="submit" name="del_fab" value="{{k}}" class="del">🗑</button></div>{% endfor %}
{% for c in st.catatan %}<div class="frow"><small style="color:#94a3b8">Catatan {{loop.index}}</small><input type="text" name="cat_{{loop.index0}}" value="{{c}}"><button type="submit" name="del_cat" value="{{loop.index0}}" class="del">🗑</button></div>{% endfor %}
<div style="display:flex;gap:8px;margin-top:8px"><button type="submit" name="aksi" value="add_fab" class="out">+ Tambah Fabric</button><button type="submit" name="aksi" value="add_cat" class="out">+ Tambah Catatan</button></div></div>
<div class="float-save-bar"><button class="btn" type="submit">Simpan Perubahan</button></div></form>
</div>
</div>
<script>function filterPieces(){
  let q = document.getElementById('searchPieceInp').value.toLowerCase().trim();
  let cards = document.querySelectorAll('#piecesList .prow');
  cards.forEach(function(c){
    let noTxt = (c.querySelector('span')?.innerText || '').toLowerCase();
    let nmVal = (c.querySelector('input[name^="n_"]')?.value || '').toLowerCase();
    let dmVal = (c.querySelector('input[name^="d_"]')?.value || '').toLowerCase();
    let tgVal = (c.querySelector('input[name^="t_"]')?.value || '').toLowerCase();
    let match = (!q || noTxt.includes(q) || nmVal.includes(q) || dmVal.includes(q) || tgVal.includes(q));
    c.style.display = match ? 'block' : 'none';
  });
}
function clearSearchPiece(){
  document.getElementById('searchPieceInp').value = '';
  filterPieces();
}
function adj(i,d){let e=document.getElementById(i);e.value=Math.max(1,parseFloat(e.value||10)+d);}
function toggleSec(id, icId){
  let el=document.getElementById(id);
  let ic=document.getElementById(icId);
  let show=(el.style.display==='none');
  el.style.display=show?'block':'none';
  ic.innerText=show?'▼':'▶';
  localStorage.setItem('st_'+id, show?'1':'0');
}
function togglePieces(){
  let el=document.getElementById('piecesList');
  let ic=document.getElementById('piecesIcon');
  let bt=document.getElementById('piecesBtnTxt');
  let show=(el.style.display==='none');
  el.style.display=show?'block':'none';
  ic.innerText=show?'▼':'▶';
  bt.innerText=show?'Minimize':'Tampilkan';
  localStorage.setItem('st_pieces', show?'1':'0');
}
['secLembar','secFont','secKet'].forEach(function(id){
  if(localStorage.getItem('st_'+id)==='1'){
    let el=document.getElementById(id);
    let ic=document.getElementById(id.replace('sec','ic'));
    if(el){el.style.display='block'; if(ic)ic.innerText='▼';}
  }
});
if(localStorage.getItem('st_pieces')==='1'){togglePieces();}
</script>
{% endif %}</div>
<div id="pvModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.95);z-index:9999;flex-direction:column">
  <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;background:#131c31;border-bottom:1px solid #334155">
    <span style="font-size:13px;font-weight:bold;color:#f8fafc">Pratinjau Lembar A4</span>
    <div style="display:flex;gap:8px;align-items:center">
      <button type="button" onclick="zoomPv(-0.3)" style="background:#1e293b;color:#fff;border:1px solid #475569;width:32px;height:32px;border-radius:8px;font-size:16px">−</button>
      <span id="pvPct" style="font-size:12px;color:#94a3b8;min-width:42px;text-align:center">100%</span>
      <button type="button" onclick="zoomPv(0.3)" style="background:#1e293b;color:#fff;border:1px solid #475569;width:32px;height:32px;border-radius:8px;font-size:16px">+</button>
      <button type="button" onclick="closePreview()" style="background:#ef4444;color:#fff;border:0;padding:7px 12px;border-radius:8px;font-size:12px;font-weight:bold">✕ Tutup</button>
    </div>
  </div>
  <div style="flex:1;overflow:auto;padding:12px;display:flex;align-items:flex-start;justify-content:center">
    <img id="pvImg" src="" style="width:100%;max-width:1100px;background:#fff;border-radius:4px;transform-origin:top left;transition:transform 0.15s">
  </div>
</div>
<script>
let pvScale = 1.0;
function openPreview(src){
  pvScale = 1.0;
  let im = document.getElementById('pvImg');
  im.src = src;
  im.style.transform = 'scale(1)';
  document.getElementById('pvPct').innerText = '100%';
  document.getElementById('pvModal').style.display = 'flex';
}
function closePreview(){ document.getElementById('pvModal').style.display = 'none'; }
function zoomPv(d){
  pvScale = Math.max(0.7, Math.min(3.5, pvScale + d));
  document.getElementById('pvImg').style.transform = 'scale(' + pvScale + ')';
  document.getElementById('pvPct').innerText = Math.round(pvScale * 100) + '%';
}
</script>
</body></html>"""


def urutkan_pieces():
    by_fab = sorted(
        STATE["pieces"],
        key=lambda p: (
            int(str(p.get("fabric", "1")).strip()) if str(p.get("fabric", "1")).strip().isdigit() else 999,
            str(p.get("nama", ""))
        )
    )
    grup_cnt = {}
    for p in by_fab:
        g = str(p.get("fabric", "1")).strip() or "1"
        grup_cnt[g] = grup_cnt.get(g, 0) + 1
        p["kode_urut"] = f"{g}.{grup_cnt[g]}"
        p["tag_color"] = warna_otomatis_tag(p.get("tag", ""), p.get("tag_color", "#111111"))

    if STATE.get("sort_mode") == "dept":
        STATE["pieces"] = sorted(
            by_fab,
            key=lambda p: (
                0 if str(p.get("tag", "")).strip() else 1,
                str(p.get("tag", "")).strip().upper(),
                int(str(p.get("fabric", "1")).strip()) if str(p.get("fabric", "1")).strip().isdigit() else 999,
                p.get("kode_urut", "")
            )
        )
    else:
        STATE["pieces"] = by_fab


def urutkan_pieces():
    by_fab = sorted(
        STATE["pieces"],
        key=lambda p: (
            int(str(p.get("fabric", "1")).strip()) if str(p.get("fabric", "1")).strip().isdigit() else 999,
            str(p.get("nama", ""))
        )
    )
    grup_cnt = {}
    for p in by_fab:
        g = str(p.get("fabric", "1")).strip() or "1"
        grup_cnt[g] = grup_cnt.get(g, 0) + 1
        p["kode_urut"] = f"{g}.{grup_cnt[g]}"
        p["tag_color"] = warna_otomatis_tag(p.get("tag", ""), p.get("tag_color", "#111111"))

    if STATE.get("sort_mode") == "dept":
        STATE["pieces"] = sorted(
            by_fab,
            key=lambda p: (
                0 if str(p.get("tag", "")).strip() else 1,
                str(p.get("tag", "")).strip().upper(),
                int(str(p.get("fabric", "1")).strip()) if str(p.get("fabric", "1")).strip().isdigit() else 999,
                p.get("kode_urut", "")
            )
        )
    else:
        STATE["pieces"] = by_fab

def hitung_counts():
    c = {}
    for p in STATE["pieces"]:
        g = str(p.get("fabric", "1")).strip() or "1"
        c[g] = c.get(g, 0) + 1
    return c

@app.route("/")
def home(): return render_template_string(HTML, mode="home")


def terapkan_excel_bantu(f_jacci, f_spread):
    try:
        import openpyxl
    except ImportError:
        return
    jacci_map = {}  # key (ukuran/nama) -> (nama_piece, kode_fab)
    if f_jacci and f_jacci.filename:
        wb = openpyxl.load_workbook(f_jacci, data_only=True)
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                vals = [str(c).strip() for c in row if c is not None and str(c).strip()]
                if len(vals) >= 2:
                    row_up = [v.upper() for v in vals]
                    # Cari kode fabric umum (MA, L2, NON, MESH, 600D, dll) di baris Excel
                    fab_c = next((v for v in row_up if v in ("MA", "L2", "NON", "MESH", "600D", "200D", "840D", "420D", "PVC", "EVA", "FOAM")), "")
                    dim_c = next((v for v in row_up if "*" in v or "X" in v and any(ch.isdigit() for ch in v)), "")
                    name_c = next((v for v in vals if len(v) > 3 and v.upper() != fab_c and v.upper() != dim_c), "")
                    if fab_c:
                        if dim_c: jacci_map[dim_c.replace(" ", "")] = (name_c, fab_c)
                        if name_c: jacci_map[name_c.upper()] = (name_c, fab_c)

    spread_desc = {}  # kode_fab -> deskripsi lengkap
    if f_spread and f_spread.filename:
        wb2 = openpyxl.load_workbook(f_spread, data_only=True)
        for ws in wb2.worksheets:
            for row in ws.iter_rows(values_only=True):
                vals = [str(c).strip() for c in row if c is not None and str(c).strip()]
                if len(vals) >= 2:
                    row_up = [v.upper() for v in vals]
                    fab_c = next((v for v in row_up if v in ("MA", "L2", "NON", "MESH", "600D", "200D", "840D", "420D", "PVC", "EVA", "FOAM")), "")
                    desc_c = max(vals, key=len)
                    if fab_c and len(desc_c) > len(fab_c):
                        spread_desc[fab_c] = desc_c

    if jacci_map or spread_desc:
        fab_to_no = {}
        new_fabrics = {}
        for p in STATE["pieces"]:
            d_key = str(p.get("dim", "")).upper().replace(" ", "")
            n_key = str(p.get("nama", "")).upper().strip()
            matched = jacci_map.get(d_key) or jacci_map.get(n_key)
            if matched:
                nm_baru, kd_fab = matched
                if nm_baru: p["nama"] = nm_baru[:40]
                if kd_fab not in fab_to_no:
                    no_f = str(len(fab_to_no) + 1)
                    fab_to_no[kd_fab] = no_f
                    new_fabrics[no_f] = spread_desc.get(kd_fab, kd_fab)
                p["fabric"] = fab_to_no[kd_fab]
        if new_fabrics:
            STATE["fabrics"] = new_fabrics

@app.route("/proses", methods=["POST"])
def proses():
    f = request.files.get("file_dxf")
    if not f: return render_template_string(HTML, mode="home")
    f.save(CUR)
    STATE["judul"] = re.sub(r"\.(dxf|json)$", "", os.path.basename(f.filename), flags=re.IGNORECASE)
    STATE["pieces"] = baca_dxf(CUR, STATE["satuan"])
    terapkan_excel_bantu(request.files.get("file_jacci"), request.files.get("file_spread"))
    urutkan_pieces()
    urutkan_pieces()
    mu = request.form.get("move_up")
    if mu and mu.isdigit():
        idx = int(mu)
        if 0 < idx < len(STATE["pieces"]):
            STATE["pieces"][idx], STATE["pieces"][idx - 1] = STATE["pieces"][idx - 1], STATE["pieces"][idx]
    md = request.form.get("move_dn")
    if md and md.isdigit():
        idx = int(md)
        if 0 <= idx < len(STATE["pieces"]) - 1:
            STATE["pieces"][idx], STATE["pieces"][idx + 1] = STATE["pieces"][idx + 1], STATE["pieces"][idx]
    urutkan_pieces()
    urutkan_pieces()
    return render_template_string(HTML, mode="edit", img=buat_a4(STATE), st=STATE, counts=hitung_counts())

@app.route("/update", methods=["POST"])
def update():
    if request.form.get("max_pages"): STATE["max_pages"] = int(request.form.get("max_pages"))
    if request.form.get("show_dist_summary") is not None: STATE["show_dist_summary"] = (request.form.get("show_dist_summary") == "1")
    for k in ("judul", "kode", "satuan", "kolom", "font_family", "sort_mode"):
        STATE[k] = request.form.get(k, STATE.get(k, "fabric"))
    for k in ("sz_judul", "sz_kode", "sz_piece", "sz_tag", "sz_ket"):
        try:
            val = float(request.form.get(k, STATE.get(k, "fabric")))
            if val >= 1: STATE[k] = round(val, 1)
        except Exception:
            pass
    for i, p in enumerate(STATE["pieces"]):
        try:
            p["urut"] = float(request.form.get(f"u_{i}", p.get("urut", i + 1)))
        except Exception:
            pass
        p["nama"] = request.form.get(f"n_{i}", p["nama"])
        p["qty"] = request.form.get(f"q_{i}", p["qty"])
        p["fabric"] = request.form.get(f"f_{i}", p["fabric"])
        p["tag"] = request.form.get(f"t_{i}", p["tag"])
        p["tag_color"] = request.form.get(f"tc_{i}", p["tag_color"])
        p["right_txt"] = request.form.get(f"rt_{i}", p.get("right_txt", ""))
    ri = request.form.get("rot_idx")
    if ri and ri.isdigit() and int(ri) < len(STATE["pieces"]):
        STATE["pieces"][int(ri)]["rot"] = (STATE["pieces"][int(ri)].get("rot", 0) + 90) % 360
    STATE["fabrics"] = {k: request.form.get(f"fab_val_{k}", v) for k, v in STATE["fabrics"].items()}
    STATE["fabrics"].pop(request.form.get("del_fab"), None)
    STATE["catatan"] = [request.form.get(f"cat_{i}", "") for i in range(len(STATE["catatan"]))]
    dc = request.form.get("del_cat")
    if dc and dc.isdigit() and int(dc) < len(STATE["catatan"]):
        STATE["catatan"].pop(int(dc))
    aksi = request.form.get("aksi")
    if aksi == "add_fab":
        nxt = str(max([int(k) for k in STATE["fabrics"] if k.isdigit()] + [0]) + 1)
        STATE["fabrics"][nxt] = f"FABRIC {nxt}"
    elif aksi == "add_cat":
        STATE["catatan"].append("")
    elif aksi == "add_piece":
        STATE["pieces"].append({"urut": len(STATE["pieces"]) + 1, "nama": "BARU", "qty": 1, "dim": "0*0", "fabric": "1", "tag": "", "tag_color": "#111111", "right_txt": "", "rot": 0, "w": 10.0, "h": 10.0, "ol": [[(0,0),(10,0),(10,10),(0,10),(0,0)]], "il": []})
    urutkan_pieces()
    urutkan_pieces()
    return render_template_string(HTML, mode="edit", img=buat_a4(STATE), st=STATE, counts=hitung_counts())


@app.route("/dl/checklist")
def dl_checklist():
    from matplotlib.backends.backend_pdf import PdfPages
    by_fab = sorted(
        STATE["pieces"],
        key=lambda p: (
            int(str(p.get("fabric", "1")).strip()) if str(p.get("fabric", "1")).strip().isdigit() else 999,
            str(p.get("nama", ""))
        )
    )
    g_cnt = {}
    dept_groups = {}
    for p in by_fab:
        g = str(p.get("fabric", "1")).strip() or "1"
        g_cnt[g] = g_cnt.get(g, 0) + 1
        kode_u = f"{g}.{g_cnt[g]}"
        dept = str(p.get("tag", "")).strip().upper().replace("\n", " ") or "LANGSUNG SEWING (TANPA PROSES)"
        fab_nm = STATE["fabrics"].get(g, f"FABRIC {g}").upper()
        dept_groups.setdefault(dept, []).append((kode_u, p, fab_nm))

    chk_pdf = os.path.join(UP, "distribusi_panel.pdf")
    with PdfPages(chk_pdf) as pdf:
        fig = plt.figure(figsize=(8.27, 11.69), dpi=180)
        fig.patch.set_facecolor('white')
        ax = fig.add_axes([0.04, 0.04, 0.92, 0.92])
        ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis('off')

        def draw_header(page_no):
            ax.text(50, 98.2, f"DISTRIBUSI PANEL — {(STATE['judul'][0] if isinstance(STATE['judul'], tuple) else str(STATE['judul'])).upper()}", ha='center', va='top', fontsize=13, fontweight='bold', color='#111')
            ax.text(50, 95.8, f"{STATE['kode'].upper()}   |   TOTAL: {len(by_fab)} PANEL   |   HAL. {page_no}", ha='center', va='top', fontsize=8.5, color='#333')
            ax.plot((0, 100), [94.0, 94.0], color='#111', lw=1.2)

        page_num = 1
        draw_header(page_num)
        y = 92.5

        for dept, rows in sorted(dept_groups.items()):
            if y < 12:
                pdf.savefig(fig, dpi=300); plt.close(fig)
                fig = plt.figure(figsize=(8.27, 11.69), dpi=180); fig.patch.set_facecolor('white')
                ax = fig.add_axes([0.04, 0.04, 0.92, 0.92]); ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis('off')
                page_num += 1; draw_header(page_num); y = 92.5

            # Header Departemen
            ax.add_patch(patches.Rectangle((0, y - 2.6), 100, 2.7, fc='#e2e8f0', ec='#111', lw=0.8))
            ax.text(1.5, y - 1.25, f"DEPARTEMEN: {dept}  ({len(rows)} PANEL)", va='center', fontsize=8.5, fontweight='bold', color='#0f172a')
            y -= 3.0

            for ku, p, fn in rows:
                row_h = 5.4
                if y - row_h < 3:
                    pdf.savefig(fig, dpi=300); plt.close(fig)
                    fig = plt.figure(figsize=(8.27, 11.69), dpi=180); fig.patch.set_facecolor('white')
                    ax = fig.add_axes([0.04, 0.04, 0.92, 0.92]); ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis('off')
                    page_num += 1; draw_header(page_num); y = 92.5
                    ax.add_patch(patches.Rectangle((0, y - 2.6), 100, 2.7, fc='#e2e8f0', ec='#111', lw=0.8))
                    ax.text(1.5, y - 1.25, f"DEPARTEMEN: {dept} (LANJUTAN)", va='center', fontsize=8.5, fontweight='bold', color='#0f172a')
                    y -= 3.0

                mid_y = y - row_h / 2
                # Kotak Centang & Nomor Panel (1.1, 1.2)
                ax.text(1.5, mid_y, f"[   ]  {ku}", fontsize=8, fontweight='bold', va='center', color='#111')

                # Gambar Mini Bentuk Panel di dalam kotak (x: 13..26)
                rol = putar_pts(p.get("ol", []), p.get("rot", 0))
                ril = putar_pts(p.get("il", []), p.get("rot", 0))
                pts = [pt for l in (rol + ril) for pt in l]
                if pts:
                    xs = [x for x, yy in pts]; ys = [yy for x, yy in pts]
                    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
                    pw, ph = max(maxx - minx, 0.01), max(maxy - miny, 0.01)
                    sc = min(11.0 / pw, (row_h - 1.0) / ph)
                    ox = 19.5 - (pw * sc) / 2
                    oy = mid_y - (ph * sc) / 2
                    if ril:
                        segs_in = [[(ox + (x - minx) * sc, oy + (yy - miny) * sc) for x, yy in l] for l in ril]
                        ax.add_collection(LineCollection(segs_in, colors='#2563eb', linewidths=0.45, linestyles='--'))
                    if rol:
                        segs_out = [[(ox + (x - minx) * sc, oy + (yy - miny) * sc) for x, yy in l] for l in rol]
                        ax.add_collection(LineCollection(segs_out, colors='#111111', linewidths=0.75))

                # Nama Panel & Ukuran Panel
                ax.text(28, mid_y + 0.9, f"{p['nama'][:28]}", fontsize=8, fontweight='bold', va='center', color='#111')
                ax.text(28, mid_y - 1.0, f"Ukuran: {p['dim']} cm", fontsize=7.5, va='center', color='#1e40af', fontweight='bold')

                # Qty & Keterangan Fabric
                qt_lbl = p.get("right_txt") or f"x{p.get('qty', 1)}"
                ax.text(63, mid_y, f"{qt_lbl}", fontsize=8.5, fontweight='bold', va='center', color='#111')
                ax.text(70, mid_y, f"{fn[:28]}", fontsize=7, va='center', color='#334155')

                ax.plot((0, 100), [y - row_h, y - row_h], color='#cbd5e1', lw=0.6)
                y -= row_h
            y -= 1.2

        pdf.savefig(fig, dpi=300)
        plt.close(fig)

    return send_file(chk_pdf, as_attachment=True, download_name=f"{STATE['judul']}_DISTRIBUSI_PANEL.pdf")

@app.route("/dl/<fmt>")
def dl(fmt):
    import json
    if fmt == "proj":
        proj_path = os.path.join(UP, "proyek.json")
        with open(proj_path, "w") as jf:
            json.dump(STATE, jf)
        return send_file(proj_path, as_attachment=True, download_name=f"{STATE['judul']}_PROYEK.json")
    buat_a4(STATE, export_mode=True)
    fn = "hasil.pdf" if fmt == "pdf" else "hasil.png"
    return send_file(os.path.join(UP, fn), as_attachment=True, download_name=f"{STATE['judul']}_A4.{fmt}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
