from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

def hitung_bkd(muatan, interval_skala, kelas, keterangan):
    if interval_skala == 0:
        return 0, 0

    m = muatan / interval_skala

    batas = {
        'I'   : [(50000, 0.5), (200000, 1.0), (float('inf'), 1.5)],
        'II'  : [(5000,  0.5), (20000,  1.0), (100000, 1.5)],
        'III' : [(500,   0.5), (2000,   1.0), (10000,  1.5)],
        'IIII': [(50,    0.5), (200,    1.0), (1000,   1.5)],
    }

    koef_dasar = 1.5
    for batas_m, koef in batas.get(kelas, batas['III']):
        if m <= batas_m:
            koef_dasar = koef
            break

    multiplier = 2.0 if keterangan == "Tera Ulang" else 1.0
    koef_final = koef_dasar * multiplier
    bkd_kg = koef_final * interval_skala
    return koef_final, bkd_kg

def safe_str(value):
    """Konversi nilai ke string dengan aman."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "SAH" if value else "TIDAK SAH"
    if isinstance(value, float):
        # Jika float adalah bilangan bulat, tampilkan sebagai int tanpa desimal
        if value.is_integer():
            return str(int(value))
        else:
            return str(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='ignore')
    return str(value)

def format_tanggal_indo(tanggal_str):
    bulan_map = {
        "January": "Januari", "February": "Februari", "March": "Maret",
        "April": "April", "May": "Mei", "June": "Juni",
        "July": "Juli", "August": "Agustus", "September": "September",
        "October": "Oktober", "November": "November", "December": "Desember"
    }
    for en, id in bulan_map.items():
        tanggal_str = tanggal_str.replace(en, id)
    return tanggal_str

def generate_cerapan_pdf(data, filename):
    width, height = A4
    c = canvas.Canvas(filename, pagesize=A4)
    margin = 1.5*cm
    y = height - 1.2*cm

    # Offset untuk menggeser teks ke kanan (sesuaikan nilai)
    offset = 0.4*cm
    center_x = width/2 + offset

    # Title
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(center_x, y, "CERAPAN PENERAAN TIMBANGAN JEMBATAN ELEKTRONIK")
    y -= 0.8*cm

    # Garis ganda
    c.setLineWidth(2)
    c.line(margin, y, width - margin, y)
    y -= 0.1*cm
    c.setLineWidth(0.8)
    c.line(margin, y, width - margin, y)
    y -= 0.45*cm

    # ======================== TABEL INFO UTAMA ========================
    label_x = margin
    colon_x = margin + 1.2*cm   # titik dua di sini, jarak cukup dekat

    # Pemilik
    c.setFont("Helvetica", 9)
    c.drawString(label_x, y, "Pemilik")
    c.drawString(colon_x, y, ":")
    c.drawString(colon_x + 0.3*cm, y, safe_str(data.get('pemilik', '')))
    y -= 0.45*cm

    # Alamat
    c.drawString(label_x, y, "Alamat")
    c.drawString(colon_x, y, ":")
    c.drawString(colon_x + 0.3*cm, y, safe_str(data.get('alamat', '')))
    y -= 0.2*cm

    # Garis single
    c.setLineWidth(1)
    c.line(margin, y, width - margin, y)
    y -= 0.45*cm

    # ======================== SPESIFIKASI ALAT (KIRI) ========================
    x0_spec = margin
    x1_spec = margin + 5.0*cm
    x2_spec = margin + 9.0*cm
    y_start_spec = y
    tinggi_judul = 0.5*cm
    tinggi_baris = 0.55*cm
    baris_data = 8
    y_end_spec = y_start_spec - (tinggi_judul + baris_data * tinggi_baris)

    c.setLineWidth(0.5)
    c.line(x0_spec, y_start_spec, x0_spec, y_end_spec)
    c.line(x2_spec, y_start_spec, x2_spec, y_end_spec)
    c.line(x0_spec, y_start_spec, x2_spec, y_start_spec)
    y_line_bawah_judul = y_start_spec - tinggi_judul
    c.line(x0_spec, y_line_bawah_judul, x2_spec, y_line_bawah_judul)
    c.line(x1_spec, y_line_bawah_judul, x1_spec, y_end_spec)
    y_line = y_line_bawah_judul
    for _ in range(baris_data):
        y_line -= tinggi_baris
        c.line(x0_spec, y_line, x2_spec, y_line)
    c.line(x0_spec, y_end_spec, x2_spec, y_end_spec)

    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(x0_spec + (x2_spec - x0_spec)/2, y_start_spec - 0.40*cm, "SPESIFIKASI ALAT")

    c.setFont("Helvetica", 9)
    y_text = y_line_bawah_judul - 0.40*cm
    specs = [
        ("Merek / buatan", data.get('merek', '')),
        ("Model / tipe", data.get('model', '')),
        ("No. Seri", data.get('no_seri', '')),
        ("Kapasitas Maksimum", f"{data.get('kapasitas_max', '')} kg"),
        ("Kapasitas Minimum", f"{data.get('kapasitas_min', '')} kg"),
        ("Daya Baca", f"{data.get('daya_baca', '')} kg"),
        ("Interval Skala Verifikasi", f"{data.get('interval_skala', '')} kg"),
        ("Kelas", data.get('kelas', '')),
    ]
    for label, value in specs:
        c.drawString(x0_spec + 0.2*cm, y_text, label)
        c.drawString(x1_spec + 0.2*cm, y_text, safe_str(value))
        y_text -= tinggi_baris

    y = y_end_spec - 0.3*cm

    # ======================== DATA PENGUJIAN (KANAN) ========================
    x0_data = margin + 9.3*cm
    x1_data = x0_data + 3.5*cm
    x2_data = width - margin
    y_start_data = y_start_spec
    baris_data_kanan = 6
    y_end_data = y_start_data - (tinggi_judul + baris_data_kanan * tinggi_baris)

    c.line(x0_data, y_start_data, x0_data, y_end_data)
    c.line(x2_data, y_start_data, x2_data, y_end_data)
    c.line(x0_data, y_start_data, x2_data, y_start_data)
    y_line_bawah_judul_data = y_start_data - tinggi_judul
    c.line(x0_data, y_line_bawah_judul_data, x2_data, y_line_bawah_judul_data)
    c.line(x1_data, y_line_bawah_judul_data, x1_data, y_end_data)
    y_line = y_line_bawah_judul_data
    for _ in range(baris_data_kanan):
        y_line -= tinggi_baris
        c.line(x0_data, y_line, x2_data, y_line)
    c.line(x0_data, y_end_data, x2_data, y_end_data)

    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(x0_data + (x2_data - x0_data)/2, y_start_data - 0.4*cm, "DATA PENGUJIAN")

    c.setFont("Helvetica", 9)
    y_text = y_line_bawah_judul_data - 0.4*cm
    test_items = [
        ("Tanggal", format_tanggal_indo(data.get('tanggal_penera', ''))),  # gunakan tanggal_penera
        ("Lokasi", data.get('lokasi', 'Perusahaan')),
        ("Suhu ruangan", data.get('suhu', 'Ambient')),
        ("Kelembaban", data.get('kelembaban', 'Ambient')),
        ("Metode", data.get('metode', 'Beban Substitusi Tunggal')),
        ("Keterangan", data.get('keterangan', 'Tera')),
    ]
    for label, value in test_items:
        c.drawString(x0_data + 0.2*cm, y_text, label)
        c.drawString(x1_data + 0.2*cm, y_text, safe_str(value))
        y_text -= tinggi_baris

    y = min(y_end_spec, y_end_data) - 0.5*cm
    y -= 0.01*cm

        # ======================== PEMERIKSAAN VISUAL (TABEL) ========================
    y_judul_visual = y
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, y_judul_visual, "PEMERIKSAAN VISUAL")
    y = y_judul_visual - 0.15*cm

    visual_data = data.get('visual', {})
    visual_items = ["Tanda Tera", "Alat Penunjuk Kedataran", "Bersih dan Siap Uji", "Sesuai Persetujuan Tipe"]

    x0 = margin
    x1 = margin + 0.7*cm      # No.
    x2 = margin + 5.0*cm      # Uraian
    x3 = margin + 5.7*cm      # Ya (centang)
    x4 = margin + 6.8*cm      # Tidak (centang)
    x5 = margin + 9.0*cm      # Keterangan
    baris_data = len(visual_items)
    tinggi_baris = 0.45*cm
    tinggi_header = 0.45*cm
    y_start = y
    y_end = y_start - (tinggi_header + baris_data * tinggi_baris)

    c.setLineWidth(0.5)
    for x in (x0, x1, x2, x3, x4, x5):
        c.line(x, y_start, x, y_end)
    c.line(x0, y_start, x5, y_start)
    y_header_bottom = y_start - tinggi_header
    c.line(x0, y_header_bottom, x5, y_header_bottom)
    y_line = y_header_bottom
    for _ in range(baris_data):
        y_line -= tinggi_baris
        c.line(x0, y_line, x5, y_line)
    c.line(x0, y_end, x5, y_end)

    c.setFont("Helvetica-Bold", 9)
    y_header_center = y_start - tinggi_header/2 - 0.1*cm
    c.drawCentredString(x0 + (x1-x0)/2, y_header_center, "No.")
    c.drawCentredString(x1 + (x2-x1)/2, y_header_center, "Uraian")
    c.drawCentredString(x2 + (x3-x2)/2, y_header_center, "Ya")
    c.drawCentredString(x3 + (x4-x3)/2, y_header_center, "Tidak")
    c.drawCentredString(x4 + (x5-x4)/2, y_header_center, "Keterangan")

    # Data – gunakan centang (✓) di kolom Ya / Tidak
    c.setFont("Helvetica", 9)
    y_text_start = y_header_bottom - tinggi_baris/2 - 0.1*cm
    y_text = y_text_start
    for i, check in enumerate(visual_items, 1):
        is_ok = visual_data.get(check, False)
        c.drawCentredString(x0 + (x1-x0)/2, y_text, str(i))
        c.drawCentredString(x1 + (x2-x1)/2, y_text, check)
        c.drawCentredString(x2 + (x3-x2)/2, y_text, "✓" if is_ok else "")
        c.drawCentredString(x3 + (x4-x3)/2, y_text, "✓" if not is_ok else "")
        c.drawCentredString(x4 + (x5-x4)/2, y_text, "")
        y_text -= tinggi_baris

    y = y_end - 0.4*cm
    y_start_visual = y_start
    y_end_visual = y_end
    # ======================== REPETABILITY (TABEL DI KANAN) ========================
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin + 9.5*cm, y_judul_visual, "1. REPETABILITY")
    c.setFont("Helvetica", 9)
    c.drawString(margin + 9.5*cm + 3.5*cm, y_judul_visual, "Sekitar 50 % Maks")

    y_start_repet = y_start_visual
    tinggi_baris = 0.45*cm
    tinggi_header = 0.45*cm

    repet_data = data.get('repetability', [])
    rows_repet = []
    for idx, item in enumerate(repet_data[:3], 1):
        rows_repet.append([
            str(idx),
            safe_str(item.get('penunjukan', '')),
            safe_str(item.get('delta_l', '')),
            safe_str(item.get('p_value', '')),
            safe_str(item.get('hasil', True))
        ])
    while len(rows_repet) < 3:
        rows_repet.append(["", "", "", "", ""])

    baris_data = 3
    baris_total = 1 + baris_data + 1

    x0_r = margin + 9.5*cm
    x1_r = x0_r + 0.8*cm
    x2_r = x1_r + 2.5*cm
    x3_r = x2_r + 1.0*cm
    x4_r = x3_r + 2.8*cm
    x5_r = x4_r + 1.5*cm

    y_end_repet = y_start_repet - (tinggi_header + (baris_data + 1) * tinggi_baris)
    y_before_BKD = y_start_repet - (tinggi_header + 3 * tinggi_baris)

    c.setLineWidth(0.5)
    for x in (x0_r, x2_r, x3_r, x4_r, x5_r):
        c.line(x, y_start_repet, x, y_end_repet)
    c.line(x1_r, y_start_repet, x1_r, y_before_BKD)
    c.line(x0_r, y_start_repet, x5_r, y_start_repet)
    y_header_bottom = y_start_repet - tinggi_header
    c.line(x0_r, y_header_bottom, x5_r, y_header_bottom)
    y_line = y_header_bottom
    for _ in range(3):
        y_line -= tinggi_baris
        c.line(x0_r, y_line, x5_r, y_line)
    c.line(x0_r, y_end_repet, x5_r, y_end_repet)

    c.setFont("Helvetica-Bold", 9)
    y_header_center = y_start_repet - tinggi_header/2 - 0.1*cm
    c.drawCentredString(x0_r + (x1_r-x0_r)/2, y_header_center, "No")
    c.drawCentredString(x1_r + (x2_r-x1_r)/2, y_header_center, "Penunjukan (I)")
    c.drawCentredString(x2_r + (x3_r-x2_r)/2, y_header_center, "ΔL")
    c.drawCentredString(x3_r + (x4_r-x3_r)/2, y_header_center, "P = I + 0,5e - ΔL")
    c.drawCentredString(x4_r + (x5_r-x4_r)/2, y_header_center, "HASIL")

    # Data baris (dengan satuan kg)
    c.setFont("Helvetica", 9)
    for idx in range(baris_data):
        y_text = y_start_repet - tinggi_header - (idx + 0.5) * tinggi_baris - 0.1*cm
        row = rows_repet[idx]
        # No
        c.drawCentredString(x0_r + (x1_r-x0_r)/2, y_text, safe_str(row[0]))
        # Penunjukan (I) + kg
        val1 = safe_str(row[1])
        if val1:
            val1 += " kg"
        c.drawCentredString(x1_r + (x2_r-x1_r)/2, y_text, val1)
        # ΔL + kg
        val2 = safe_str(row[2])
        if val2:
            val2 += " kg"
        c.drawCentredString(x2_r + (x3_r-x2_r)/2, y_text, val2)
        # P = I + 0,5e - ΔL + kg
        val3 = safe_str(row[3])
        if val3:
            val3 += " kg"
        c.drawCentredString(x3_r + (x4_r-x3_r)/2, y_text, val3)
        # HASIL
        c.drawCentredString(x4_r + (x5_r-x4_r)/2, y_text, safe_str(row[4]))

        # ===== BARIS BKD (MERGED CELL) – DINAMIS BERDASARKAN PENUNJUKAN =====
    # Ambil nilai penunjukan dari data repetability (baris pertama)
    if repet_data and len(repet_data) > 0:
        penunjukan_str = repet_data[0].get('penunjukan', 0)
        # Konversi ke float/int
        try:
            penunjukan = float(penunjukan_str) if penunjukan_str else 0
        except:
            penunjukan = 0
    else:
        penunjukan = 0

    interval_skala = data.get('interval_skala', 20)
    kelas = data.get('kelas', 'III')
    keterangan = data.get('keterangan', 'Tera')

    # Hitung BKD berdasarkan penunjukan (bukan 50% kapasitas)
    _, bkd_kg = hitung_bkd(penunjukan, interval_skala, kelas, keterangan)
    bkd_kg_str = safe_str(bkd_kg)

    y_text_bkd = y_start_repet - tinggi_header - (3 + 0.5) * tinggi_baris - 0.1*cm
    x_center_merged = x0_r + (x2_r - x0_r)/2
    c.drawCentredString(x_center_merged, y_text_bkd, "BKD")
    c.drawCentredString(x2_r + (x3_r-x2_r)/2, y_text_bkd, f"{bkd_kg_str} kg")
    c.drawCentredString(x3_r + (x4_r-x3_r)/2, y_text_bkd, "Status")
    c.drawCentredString(x4_r + (x5_r-x4_r)/2, y_text_bkd, "SAH")

    y = y_end_repet - 0.5*cm


    # ======================== EKSENTRISITAS ========================
    y_judul_eks = y_end_visual - 0.5*cm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, y_judul_eks, "2. EKSENTRISITAS")
    c.setFont("Helvetica", 9)
    c.drawString(margin + 3.5*cm, y_judul_eks, "Sekitar 1/3 Maks")
    y_start_eks = y_judul_eks - 0.15*cm

    eksen_data = data.get('eksentrisitas', [])
    rows_eks = []
    for idx, item in enumerate(eksen_data[:3], 1):
        rows_eks.append([
            str(idx),
            safe_str(item.get('penunjukan', '')),
            safe_str(item.get('delta_l', '')),
            safe_str(item.get('p_value', '')),
            safe_str(item.get('selisih', '')),
            "0",  # nilai selisih (default)
            safe_str(item.get('bkd_text', '')),  # BKD per baris
            safe_str(item.get('hasil', True))
        ])
    while len(rows_eks) < 3:
        rows_eks.append(["", "", "", "", "", "", "", ""])

    kotak_width = 2.5*cm
    x0 = margin + kotak_width + 0.2*cm
    x1 = x0 + 0.7*cm
    x2 = x1 + 2.8*cm
    x3 = x2 + 1.5*cm
    x4 = x3 + 2.8*cm
    x4_5 = x4 + 1.2*cm
    x5 = x4_5 + 1.0*cm
    x6 = x5 + 0.8*cm
    x7 = x6 + 1.5*cm

    tinggi_baris = 0.45*cm
    tinggi_header = 0.45*cm
    baris_data = len(rows_eks)
    y_end_eks = y_start_eks - (tinggi_header + baris_data * tinggi_baris)
    y_header_bottom = y_start_eks - tinggi_header

    c.setLineWidth(0.5)
    for x in (x0, x1, x2, x3, x4, x5, x6, x7):
        c.line(x, y_start_eks, x, y_end_eks)
    c.line(x4_5, y_header_bottom, x4_5, y_end_eks)
    c.line(x0, y_start_eks, x7, y_start_eks)
    c.line(x0, y_header_bottom, x7, y_header_bottom)
    y_line = y_header_bottom
    for _ in range(baris_data):
        y_line -= tinggi_baris
        c.line(x0, y_line, x7, y_line)
    c.line(x0, y_end_eks, x7, y_end_eks)

    c.setFont("Helvetica-Bold", 9)
    y_header_center = y_start_eks - tinggi_header/2 - 0.1*cm
    c.drawCentredString(x0 + (x1-x0)/2, y_header_center, "No")
    c.drawCentredString(x1 + (x2-x1)/2, y_header_center, "Penunjukan (I)")
    c.drawCentredString(x2 + (x3-x2)/2, y_header_center, "ΔL")
    c.drawCentredString(x3 + (x4-x3)/2, y_header_center, "P = I + 0,5e - ΔL")
    c.drawCentredString(x4 + (x5-x4)/2, y_header_center, "Selisih")
    c.drawCentredString(x5 + (x6-x5)/2, y_header_center, "BKD")
    c.drawCentredString(x6 + (x7-x6)/2, y_header_center, "HASIL")

    c.setFont("Helvetica", 9)
    for idx, row in enumerate(rows_eks):
        y_text = y_start_eks - tinggi_header - (idx + 0.5) * tinggi_baris - 0.1*cm
        # No
        c.drawCentredString(x0 + (x1-x0)/2, y_text, safe_str(row[0]))
        # Penunjukan (I) + kg
        val1 = safe_str(row[1])
        if val1:
            val1 += " kg"
        c.drawCentredString(x1 + (x2-x1)/2, y_text, val1)
        # ΔL + kg
        val2 = safe_str(row[2])
        if val2:
            val2 += " kg"
        c.drawCentredString(x2 + (x3-x2)/2, y_text, val2)
        # P = I + 0,5e - ΔL + kg
        val3 = safe_str(row[3])
        if val3:
            val3 += " kg"
        c.drawCentredString(x3 + (x4-x3)/2, y_text, val3)
        # Selisih (label)
        c.drawCentredString(x4 + (x4_5-x4)/2, y_text, safe_str(row[4]))
        # Selisih (nilai)
        c.drawCentredString(x4_5 + (x5-x4_5)/2, y_text, safe_str(row[5]))
        # BKD
        c.drawCentredString(x5 + (x6-x5)/2, y_text, safe_str(row[6]))
        # HASIL
        c.drawCentredString(x6 + (x7-x6)/2, y_text, safe_str(row[7]))

    kotak_x = margin
    kotak_y = y_end_eks
    kotak_height = y_start_eks - y_end_eks
    c.rect(kotak_x, kotak_y, kotak_width, kotak_height, stroke=1, fill=0)
    cell_width = kotak_width / 3.0
    c.setFont("Helvetica-Bold", 9)
    for i, angka in enumerate(['1', '2', '3']):
        x_center = kotak_x + (i + 0.5) * cell_width
        y_center = kotak_y + kotak_height/2
        c.drawCentredString(x_center, y_center, angka)

    y = y_end_eks - 0.55*cm

    # ======================== PENGUJIAN KEBENARAN ========================
    y_judul = y
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, y_judul, "3. PENGUJIAN KEBENARAN")
    y_tbl_top = y_judul - 0.3 * cm

    TH1 = 0.50 * cm
    TH2 = 0.65 * cm
    TDR = 0.45 * cm

    W_eff = width - 2 * margin
    w = {
        'no'      : 0.60,
        'std_v'   : 1.10,  'std_kg'  : 0.50,
        'bal_v'   : 1.10,  'bal_kg'  : 0.50,
        'muat_v'  : 1.30,  'muat_kg' : 0.50,
        'timb_v'  : 1.30,  'timb_kg' : 0.50,
        'imbuh'   : 0.65,
        'pakt_v'  : 1.20,  'pakt_kg' : 0.50,
        'kes_v'   : 1.30,  'kes_kg'  : 0.00,
        'bkd_pm'  : 0.45,  'bkd_n'   : 0.55,  'bkd_e': 0.45,
        'hasil'   : 0.90,
    }
    _total_raw = sum(w.values()) * cm
    _scale = W_eff / _total_raw
    for k in w:
        w[k] = w[k] * cm * _scale

    order = ['no',
             'std_v', 'std_kg',
             'bal_v', 'bal_kg',
             'muat_v', 'muat_kg',
             'timb_v', 'timb_kg',
             'imbuh',
             'pakt_v', 'pakt_kg',
             'kes_v', 'kes_kg',
             'bkd_pm', 'bkd_n', 'bkd_e',
             'hasil']

    x = {}
    cur = margin
    for k in order:
        x[k] = cur
        cur += w[k]
    x['end'] = cur

    test_results = data.get('hasil_pengujian', [])
    n_data = len(test_results)

    y_h1_top = y_tbl_top
    y_h1_bot = y_h1_top - TH1
    y_h2_bot = y_h1_bot - TH2
    y_tbl_bot = y_h2_bot - n_data * TDR

    def ctext(text, xl_key, xr_key, yc, bold=False, size=7.5):
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        xm = (x[xl_key] + x[xr_key]) / 2
        c.drawCentredString(xm, yc - size * 0.38, safe_str(text))

    def hline(y_pos, x_from_key='no', x_to_key='end'):
        c.line(x[x_from_key], y_pos, x[x_to_key], y_pos)

    def vline(x_key, y_top, y_bot):
        c.line(x[x_key], y_top, x[x_key], y_bot)

    c.setLineWidth(0.5)
    hline(y_h1_top)
    c.line(x['std_v'], y_h1_bot, x['bkd_pm'], y_h1_bot)
    hline(y_h2_bot)
    for i in range(1, n_data):
        hline(y_h2_bot - i * TDR)
    hline(y_tbl_bot)

    full_vlines = ['no', 'std_v', 'timb_v', 'bkd_pm', 'hasil', 'end']
    for k in full_vlines:
        vline(k, y_h1_top, y_tbl_bot)

    partial_vlines = ['std_kg', 'bal_v', 'bal_kg', 'muat_v', 'muat_kg',
                      'timb_kg', 'imbuh', 'pakt_v', 'pakt_kg',
                      'kes_v']
    for k in partial_vlines:
        vline(k, y_h1_bot, y_tbl_bot)

    for k in ['bkd_n', 'bkd_e']:
        vline(k, y_h2_bot, y_tbl_bot)

    yc1 = y_h1_top - TH1 / 2
    ctext("Muatan ( L )", 'std_v', 'timb_v', yc1, bold=True)
    ctext("Penunjukan",  'timb_v', 'bkd_pm', yc1, bold=True)
    yc_merged = (y_h1_top + y_h2_bot) / 2
    ctext("BKD",         'bkd_pm', 'hasil', yc_merged, bold=True)
    ctext("HASIL",       'hasil', 'end',   yc_merged, bold=True)

    def header2(line1, line2, xl_key, xr_key):
        """Header 2 baris: line1 di atas, line2 di bawah."""
        xm = (x[xl_key] + x[xr_key]) / 2
        c.setFont("Helvetica-Bold", 6.5)
        c.drawCentredString(xm, y_h1_bot - TH2 * 0.38, line1)   # lebih turun
        c.setFont("Helvetica", 6.0)
        c.drawCentredString(xm, y_h1_bot - TH2 * 0.72, line2)   # lebih turun

    c.setFont("Helvetica-Bold", 7.5)
    c.drawCentredString(
        (x['no'] + x['std_v']) / 2,
        (y_h1_top + y_h2_bot) / 2 - 7.5 * 0.38,
        "No"
    )

    header2("Standar",        "S",             'std_v',  'std_kg')
    header2("Balas (B)",      "( Pi-E )",      'bal_v',  'bal_kg')
    header2("Muatan",         "( S+B )",       'muat_v', 'muat_kg')
    header2("Timbangan",      "( I )",         'timb_v', 'timb_kg')
    header2("Imbuh",          "(\u0394L)",     'imbuh',  'pakt_v')
    header2("P.Aktual (Pi)",  "I+0,5e-\u0394L",'pakt_v', 'pakt_kg')
    header2("Kesalahan (E)",  "Pi - L",        'kes_v',  'bkd_pm')

    for idx, res in enumerate(test_results):
        y_row_top = y_h2_bot - idx * TDR
        yc = y_row_top - TDR / 2

        standar   = safe_str(res.get('standar', ''))
        balas     = safe_str(res.get('balas', ''))
        muatan_sb = safe_str(res.get('muatan_sb', ''))
        timbangan = safe_str(res.get('timbangan', ''))
        imbuh     = safe_str(res.get('imbuh', ''))
        p_aktual  = safe_str(res.get('p_aktual', ''))
        kesalahan = safe_str(res.get('kesalahan', '0'))
        bkd_koef  = res.get('bkd_koef', 0)
        hasil_ok  = res.get('hasil', True)

        def td(text, xl, xr, sz=7.5, bold=False):
            c.setFont("Helvetica-Bold" if bold else "Helvetica", sz)
            c.drawCentredString((x[xl] + x[xr]) / 2, yc - sz * 0.38, safe_str(text))

        td(str(idx + 1), 'no', 'std_v')
        td(standar,    'std_v',  'std_kg')
        if standar: td("kg", 'std_kg', 'bal_v', sz=7.0)
        td(balas,      'bal_v',  'bal_kg')
        if balas:   td("kg", 'bal_kg', 'muat_v', sz=7.0)
        td(muatan_sb,  'muat_v', 'muat_kg')
        if muatan_sb: td("kg", 'muat_kg', 'timb_v', sz=7.0)
        td(timbangan,  'timb_v', 'timb_kg')
        if timbangan: td("kg", 'timb_kg', 'imbuh', sz=7.0)
        td(imbuh,      'imbuh',  'pakt_v')
        td(p_aktual,   'pakt_v', 'pakt_kg')
        if p_aktual: td("kg", 'pakt_kg', 'kes_v', sz=7.0)
        td(kesalahan,  'kes_v',  'bkd_pm')

        if bkd_koef:
            if bkd_koef == int(bkd_koef):
                bkd_display = str(int(bkd_koef))
            else:
                bkd_display = f"{bkd_koef:g}"
        else:
            bkd_display = ""
        td("\u00b1",            'bkd_pm', 'bkd_n')
        td(bkd_display,         'bkd_n',  'bkd_e')
        td("e" if bkd_koef else "", 'bkd_e', 'hasil')
        td("SAH" if hasil_ok else "TIDAK", 'hasil', 'end', bold=hasil_ok)

    y = y_tbl_bot - 0.3 * cm

    # ======================== PENGUJIAN PENYETELAN NOL ========================
    y_judul_nol = y - 0.3*cm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, y_judul_nol, "4. PENGUJIAN PENYETELAN NOL")
    y_start_nol = y_judul_nol - 0.15*cm

    nol_data = data.get('penyetelan_nol', {})
    setel_nol = safe_str(nol_data.get('setel_nol', '0'))
    muatan_10e = safe_str(nol_data.get('muatan_10e', '100'))
    awal = safe_str(nol_data.get('awal', '100'))
    plus025e = safe_str(nol_data.get('plus025e', '100'))
    plus05e = safe_str(nol_data.get('plus05e', '110'))

    rows_nol = [[setel_nol, muatan_10e, awal, plus025e, plus05e]]
    baris_data = len(rows_nol)
    baris_total = 1 + baris_data

    x0 = margin
    x1 = x0 + 2.0*cm
    x2 = x1 + 3.3*cm
    x3 = x2 + 1.8*cm
    x4 = x3 + 1.8*cm
    x5 = x4 + 1.8*cm

    tinggi_baris = 0.45*cm
    tinggi_header = 0.45*cm
    y_end_nol = y_start_nol - (tinggi_header + baris_data * tinggi_baris)

    c.setLineWidth(0.5)
    for x in (x0, x1, x2, x3, x4, x5):
        c.line(x, y_start_nol, x, y_end_nol)
    c.line(x0, y_start_nol, x5, y_start_nol)
    y_header_bottom = y_start_nol - tinggi_header
    c.line(x0, y_header_bottom, x5, y_header_bottom)
    y_line = y_header_bottom
    for _ in range(baris_data):
        y_line -= tinggi_baris
        c.line(x0, y_line, x5, y_line)
    c.line(x0, y_end_nol, x5, y_end_nol)

    c.setFont("Helvetica-Bold", 9)
    y_header_center = y_start_nol - tinggi_header/2 - 0.1*cm
    c.drawCentredString(x0 + (x1-x0)/2, y_header_center, "SETEL NOL")
    c.drawCentredString(x1 + (x2-x1)/2, y_header_center, "MUATAN 10e (kg)")
    c.drawCentredString(x2 + (x3-x2)/2, y_header_center, "AWAL (kg)")
    c.drawCentredString(x3 + (x4-x3)/2, y_header_center, "+0,25e (kg)")
    c.drawCentredString(x4 + (x5-x4)/2, y_header_center, "+0,5e (kg)")

    c.setFont("Helvetica", 9)
    for idx, row in enumerate(rows_nol):
        y_text = y_start_nol - tinggi_header - (idx + 0.5) * tinggi_baris - 0.1*cm
        c.drawCentredString(x0 + (x1-x0)/2, y_text, safe_str(row[0]))
        c.drawCentredString(x1 + (x2-x1)/2, y_text, safe_str(row[1]))
        c.drawCentredString(x2 + (x3-x2)/2, y_text, safe_str(row[2]))
        c.drawCentredString(x3 + (x4-x3)/2, y_text, safe_str(row[3]))
        c.drawCentredString(x4 + (x5-x4)/2, y_text, safe_str(row[4]))

    y = y_end_nol - 0.5*cm

    # ======================== PENGUJIAN PENYETEL TARA (TERA) ========================
    keterangan = data.get('keterangan', '')
    if keterangan == "Tera":
        y_judul_tara = y_judul_nol
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x5 + 0.5*cm, y_judul_tara, "5. PENGUJIAN PENYETEL TARA (TERA)")
        y_start_tara = y_start_nol

        kapasitas_max = data.get('kapasitas_max', 60000)
        interval_skala = data.get('interval_skala', 20)
        muatan_tara = int(0.2 * kapasitas_max)
        muatan_10e = 10 * interval_skala
        imbuh_025e = muatan_10e
        imbuh_05e = 11 * interval_skala

        rows_tara = [
            ["SETEL NOL", "0"],
            ["MUATAN TARA (20% MAKS)", f"{muatan_tara}"],
            ["AKTIFKAN TARA", "0"],
            ["+ muatan 10e", f"{muatan_10e}"],
            ["+ imbuh 0,25e", f"{imbuh_025e}"],
            ["+ imbuh 0,5e", f"{imbuh_05e}"]
        ]
        baris_data = len(rows_tara)
        baris_total = 1 + baris_data

        x0_t = x5 + 0.5*cm
        x1_t = x0_t + 4.5*cm
        x2_t = x1_t + 2.9*cm

        tinggi_baris = 0.45*cm
        tinggi_header = 0.45*cm
        y_end_tara = y_start_tara - (tinggi_header + baris_data * tinggi_baris)

        c.setLineWidth(0.5)
        for x in (x0_t, x1_t, x2_t):
            c.line(x, y_start_tara, x, y_end_tara)
        c.line(x0_t, y_start_tara, x2_t, y_start_tara)
        y_header_bottom = y_start_tara - tinggi_header
        c.line(x0_t, y_header_bottom, x2_t, y_header_bottom)
        y_line = y_header_bottom
        for _ in range(baris_data):
            y_line -= tinggi_baris
            c.line(x0_t, y_line, x2_t, y_line)
        c.line(x0_t, y_end_tara, x2_t, y_end_tara)

        c.setFont("Helvetica-Bold", 9)
        y_header_center = y_start_tara - tinggi_header/2 - 0.1*cm
        c.drawCentredString(x0_t + (x1_t-x0_t)/2, y_header_center, "KEGIATAN")
        c.drawCentredString(x1_t + (x2_t-x1_t)/2, y_header_center, "PENUNJUKKAN")

        c.setFont("Helvetica", 9)
        for idx, row in enumerate(rows_tara):
            y_text = y_start_tara - tinggi_header - (idx + 0.5) * tinggi_baris - 0.1*cm
            c.drawString(x0_t + 0.2*cm, y_text, safe_str(row[0]))
            c.drawCentredString(x1_t + (x2_t-x1_t)/2, y_text, safe_str(row[1]))

        y = min(y_end_nol, y_end_tara) - 0.5*cm
    else:
        y = y_end_nol - 0.5*cm

    # ======================== PENERA ========================
    y_start_penera = y - 0.3*cm

    rows_penera = [[
        "1.",
        safe_str(data.get('nama_penera', '')),
        "",
        format_tanggal_indo(data.get('tanggal_penera', '')),
        "SAH"
    ]]
    baris_data = len(rows_penera)
    tinggi_baris = 0.45*cm
    tinggi_header1 = 0.45*cm
    tinggi_header2 = 0.45*cm

    x0 = margin
    x1 = x0 + 0.8*cm
    x2 = x1 + 4.5*cm
    x3 = x2 + 1.5*cm
    x4 = x3 + 2.5*cm
    x5 = x4 + 4.0*cm

    y_header1_bottom = y_start_penera - tinggi_header1
    y_header2_bottom = y_header1_bottom - tinggi_header2
    y_end_penera = y_header2_bottom - (baris_data * tinggi_baris)

    c.setLineWidth(0.5)
    c.rect(x0, y_end_penera, x5 - x0, y_start_penera - y_end_penera, stroke=1, fill=0)

    c.line(x4, y_start_penera, x4, y_end_penera)
    for x in (x1, x2, x3):
        c.line(x, y_header1_bottom, x, y_end_penera)

    c.line(x0, y_header1_bottom, x5, y_header1_bottom)
    c.line(x0, y_header2_bottom, x4, y_header2_bottom)
    y_line = y_header2_bottom
    for _ in range(baris_data):
        y_line -= tinggi_baris
        c.line(x0, y_line, x5, y_line)

    c.setFont("Helvetica-Bold", 9)
    y_h1_center = y_start_penera - tinggi_header1 / 2 - 0.1*cm
    c.drawCentredString((x0 + x4) / 2, y_h1_center, "PENERA")
    c.drawCentredString((x4 + x5) / 2, y_h1_center, "KETERANGAN")

    c.setFont("Helvetica-Bold", 9)
    y_h2_center = y_header1_bottom - tinggi_header2 / 2 - 0.1*cm
    c.drawCentredString((x0 + x1) / 2, y_h2_center, "No.")
    c.drawCentredString((x1 + x2) / 2, y_h2_center, "Nama")
    c.drawCentredString((x2 + x3) / 2, y_h2_center, "Paraf")
    c.drawCentredString((x3 + x4) / 2, y_h2_center, "TANGGAL")

    y_sah_center = y_header1_bottom - (tinggi_header2 + baris_data * tinggi_baris) / 2 - 0.1*cm
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString((x4 + x5) / 2, y_sah_center, "SAH")

    for idx, row in enumerate(rows_penera):
        y_text = y_header2_bottom - (idx + 0.5) * tinggi_baris - 0.1*cm
        c.setFont("Helvetica", 9)
        c.drawCentredString((x0 + x1) / 2, y_text, safe_str(row[0]))
        c.drawString(x1 + 0.2*cm, y_text, safe_str(row[1]))
        c.drawCentredString((x2 + x3) / 2, y_text, safe_str(row[2]))
        c.drawCentredString((x3 + x4) / 2, y_text, safe_str(row[3]))

    y = y_end_penera - 0.5*cm
    c.save()
    return filename
