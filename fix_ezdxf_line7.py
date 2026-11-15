with open("mini_marker.py", "r") as f:
    code = f.read()

# 1. Hapus ezdxf dari baris import gabungan maupun baris import tunggal
lines = []
for ln in code.splitlines():
    if "import ezdxf" in ln:
        lines.append("ezdxf = None")
    elif "ezdxf" in ln and ln.strip().startswith("import "):
        parts = [p.strip() for p in ln.replace("import ", "").split(",") if p.strip() != "ezdxf"]
        if parts:
            lines.append("import " + ", ".join(parts))
        lines.append("ezdxf = None")
    else:
        lines.append(ln)
code = "\n".join(lines)

# 2. Pastikan fungsi baca_dxf langsung memakai pembaca DXF murni 100% Python jika ezdxf is None
pure_dxf_complete = '''
def baca_dxf_murni(path, satuan="mm"):
    f_cm = 0.1 if satuan == "mm" else 1.0
    polys = []
    texts = []
    with open(path, "r", errors="ignore") as fp:
        lines = [l.strip() for l in fp]
    cur_pts = []
    in_poly = False
    x_val = None
    in_text = False
    tx, ty, tval = None, None, ""
    i = 0
    while i < len(lines) - 1:
        c, v = lines[i], lines[i+1]
        if c == "0":
            if in_poly and len(cur_pts) >= 3:
                polys.append(cur_pts)
            if in_text and tx is not None and ty is not None and tval:
                texts.append((tx, ty, tval))
            cur_pts = []; in_poly = False; x_val = None
            in_text = False; tx = None; ty = None; tval = ""
            if v in ("LWPOLYLINE", "POLYLINE", "LINE"):
                in_poly = True
            elif v in ("TEXT", "MTEXT"):
                in_text = True
        elif in_poly:
            if c == "10":
                try: x_val = float(v)
                except: x_val = None
            elif c == "20" and x_val is not None:
                try:
                    cur_pts.append((x_val, float(v)))
                    x_val = None
                except: pass
        elif in_text:
            if c == "10":
                try: tx = float(v)
                except: pass
            elif c == "20":
                try: ty = float(v)
                except: pass
            elif c == "1":
                tval = v
        i += 2

    pieces = []
    for idx, poly in enumerate(polys, 1):
        xs = [p for p in poly]; ys = [p for p in poly]
        minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
        w = round((maxx - minx) * f_cm, 1)
        h = round((maxy - miny) * f_cm, 1)
        if w < 0.3 and h < 0.3:
            continue
        # Cari teks di dalam batas poligon untuk nama, tag departemen, dan A/B
        inside_txt = [tv for (x, y, tv) in texts if minx - 5 <= x <= maxx + 5 and miny - 5 <= y <= maxy + 5]
        nama = f"PIECE_{idx}"
        tag = ""
        rtxt = ""
        fab = "1"
        for tv in inside_txt:
            tu = tv.upper()
            if any(k in tu for k in ("OCM", "BORDIR", "AUTO", "PREP", "PRINT")):
                tag = tv
            elif "X2" in tu or "2X" in tu:
                rtxt = "A/B"
            elif len(tv) > 2 and not tv.replace(".", "").isdigit():
                nama = tv[:35]
        pieces.append({
            "nama": nama, "dim": f"{w}*{h}", "qty": 2 if rtxt == "A/B" else 1,
            "fabric": fab, "tag": tag, "right_txt": rtxt,
            "tag_color": "#111111", "rot": 0, "ol": [poly], "il": []
        })
    return pieces
'''

if "def baca_dxf_murni(" not in code:
    code = code.replace("def baca_dxf(path, satuan=\"mm\"):", pure_dxf_complete + "\ndef baca_dxf(path, satuan=\"mm\"):\n    if ezdxf is None:\n        return baca_dxf_murni(path, satuan)")
else:
    code = code.replace("def baca_dxf(path, satuan=\"mm\"):", "def baca_dxf(path, satuan=\"mm\"):\n    if ezdxf is None:\n        return baca_dxf_murni(path, satuan)")

with open("mini_marker.py", "w") as f:
    f.write(code)
print("SEMUA IMPORT EZDXF BERHASIL DIGANTI DENGAN PEMBACA DXF MURNI!")
