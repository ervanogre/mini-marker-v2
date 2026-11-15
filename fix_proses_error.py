with open("mini_marker.py", "r") as f:
    code = f.read()

# 1. Perbaiki pengambilan koordinat x dan y pada baca_dxf_murni (p[0] dan p[1])
code = code.replace("xs = [p for p in poly]; ys = [p for p in poly]", "xs = [p[0] for p in poly]; ys = [p[1] for p in poly]")
code = code.replace("xs = [p for p in cur_pts]; ys = [p for p in cur_pts]", "xs = [p[0] for p in cur_pts]; ys = [p[1] for p in cur_pts]")

# 2. Pastikan pembagian halaman saat export PDF menggunakan pdf_pages[0].save(...)
code = code.replace("pdf_pages.save(os.path.join(UP, \"hasil.pdf\")", "pdf_pages[0].save(os.path.join(UP, \"hasil.pdf\")")

with open("mini_marker.py", "w") as f:
    f.write(code)
print("PERBAIKAN /PROSES SELESAI!")
