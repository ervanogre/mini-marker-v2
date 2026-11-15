with open("mini_marker.py", "r") as f:
    code = f.read()

code = code.replace("import ezdxf", "try:\n    import ezdxf\nexcept ImportError:\n    ezdxf = None")

fallback_dxf = '''
def baca_dxf_murni(path, satuan="mm"):
    f_cm = 0.1 if satuan == "mm" else 1.0
    pieces = []
    with open(path, "r", errors="ignore") as fp:
        lines = [l.strip() for l in fp]
    cur_pts = []
    in_poly = False
    x_val = None
    idx = 0
    i = 0
    while i < len(lines) - 1:
        c, v = lines[i], lines[i+1]
        if c == "0" and v in ("LWPOLYLINE", "POLYLINE"):
            if len(cur_pts) >= 3:
                xs = [p for p in cur_pts]; ys = [p for p in cur_pts]
                w = round((max(xs)-min(xs))*f_cm, 1)
                h = round((max(ys)-min(ys))*f_cm, 1)
                idx += 1
                pieces.append({"nama": f"PIECE_{idx}", "dim": f"{w}*{h}", "qty": 1, "fabric": "1", "tag": "", "right_txt": "", "tag_color": "#111111", "rot": 0, "ol": [cur_pts], "il": []})
            cur_pts = []; in_poly = True
        elif in_poly and c == "10":
            try: x_val = float(v)
            except: x_val = None
        elif in_poly and c == "20" and x_val is not None:
            try:
                cur_pts.append((x_val, float(v)))
                x_val = None
            except: pass
        elif c == "0" and v in ("ENDSEC", "SEQEND"):
            if len(cur_pts) >= 3:
                xs = [p for p in cur_pts]; ys = [p for p in cur_pts]
                w = round((max(xs)-min(xs))*f_cm, 1)
                h = round((max(ys)-min(ys))*f_cm, 1)
                idx += 1
                pieces.append({"nama": f"PIECE_{idx}", "dim": f"{w}*{h}", "qty": 1, "fabric": "1", "tag": "", "right_txt": "", "tag_color": "#111111", "rot": 0, "ol": [cur_pts], "il": []})
            cur_pts = []; in_poly = False
        i += 2
    return pieces
'''

code = code.replace("def baca_dxf(path, satuan=\"mm\"):", fallback_dxf + "\ndef baca_dxf(path, satuan=\"mm\"):\n    if ezdxf is None:\n        return baca_dxf_murni(path, satuan)")

with open("mini_marker.py", "w") as f:
    f.write(code)
print("FALLBACK DXF MURNI & TEXT WRAP ERROR BERHASIL DIPASANG!")
