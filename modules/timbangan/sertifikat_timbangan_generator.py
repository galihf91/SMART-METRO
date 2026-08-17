from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.colors import black, gray
from datetime import datetime
from pathlib import Path
import textwrap
import os
from reportlab.lib.utils import ImageReader

BASE_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = BASE_DIR / "assets"

watermark_path = ASSETS_DIR / "logo_metrologi.png"
logo_path = ASSETS_DIR / "logo.png"

def format_tanggal_indonesia(tanggal_str):
    if not tanggal_str:
        return ""
    bulan_map = {
        "January": "Januari", "February": "Februari", "March": "Maret",
        "April": "April", "May": "Mei", "June": "Juni",
        "July": "Juli", "August": "Agustus", "September": "September",
        "October": "Oktober", "November": "November", "December": "Desember"
    }
    # Coba parse format YYYY-MM-DD
    try:
        t = datetime.strptime(tanggal_str, '%Y-%m-%d')
        bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
                 "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
        return f"{t.day} {bulan[t.month-1]} {t.year}"
    except:
        pass
    # Coba format DD Month YYYY (misal: 30 June 2026)
    try:
        parts = tanggal_str.split()
        if len(parts) == 3:
            day = parts[0]
            month_en = parts[1]
            year = parts[2]
            month_id = bulan_map.get(month_en, month_en)
            return f"{day} {month_id} {year}"
    except:
        pass
    # Jika gagal, kembalikan string asli
    return tanggal_str
        
def ambil_nilai_angka(value, default=0.0):
    """
    Mengambil nilai angka dari int, float, string, list, atau tuple.
    Contoh:
    5000.0          -> 5000.0
    (5000.0, "kg")  -> 5000.0
    [2.0, "kg"]     -> 2.0
    """
    if isinstance(value, (tuple, list)):
        if not value:
            return default
        value = value[0]

    try:
        return float(value)
    except (TypeError, ValueError):
        return default
def kg_ke_satuan_tampilan(nilai_kg, satuan):
    try:
        nilai = float(nilai_kg)
    except (TypeError, ValueError):
        return nilai_kg

    if satuan == "g":
        return nilai * 1000

    return nilai


def format_angka_ringkas(value):
    if value in (None, ""):
        return ""

    angka = ambil_nilai_angka(value)

    if angka.is_integer():
        return str(int(angka))

    return (
        f"{angka:.10f}"
        .rstrip("0")
        .rstrip(".")
        .replace(".", ",")
    )
def generate_sertifikat_pdf(data, filename, nomor_sertifikat):
    width, height = A4
    c = canvas.Canvas(filename, pagesize=A4)
    nama_alat_normal = str(
        data.get(
            "nama_alat",
            "Timbangan Elektronik"
        )
    ).strip().lower()

    is_timbangan_elektronik = (
        nama_alat_normal == "timbangan elektronik"
    )
    
    is_timbangan_meja = (
        nama_alat_normal == "timbangan meja"
    )
    
    is_neraca_obat = nama_alat_normal in {
        "neraca obat",
        "timbangan neraca obat",
    }
    # ===== MARGIN =====
    margin_old = 1.5*cm                     # margin untuk kop, footer, header halaman 2, tanda tangan
    margin_left_content = 3.0*cm            # margin kiri untuk isi
    # margin kanan untuk isi tetap 1.5 cm (sama seperti sebelumnya)
    right_limit_content = width - margin_old   # batas kanan untuk isi (1.5 cm dari kanan)
    right_limit_old = width - margin_old       # untuk elemen lama
    
    y = height - 1.2*cm

    # ======================== WATERMARK LOGO METROLOGI ========================
    if watermark_path.exists():
        try:
            wm = ImageReader(str(watermark_path))

            wm_width = 12 * cm
            wm_height = 12 * cm

            c.saveState()
            c.setFillAlpha(0.15)

            c.drawImage(
                wm,
                (width - wm_width) / 2,
                (height - wm_height) / 2,
                width=wm_width,
                height=wm_height,
                mask="auto"
            )

            c.restoreState()

        except Exception as e:
            print(f"Error watermark: {e}")

    # ======================== LOGO KOP SURAT ========================
    if logo_path.exists():
        try:
            logo = ImageReader(str(logo_path))

            logo_width = 1.9 * cm
            logo_height = 2.2 * cm
            logo_y = y - logo_height + 0.45 * cm

            c.drawImage(
                logo,
                margin_old,
                logo_y,
                width=logo_width,
                height=logo_height,
                mask="auto"
            )

        except Exception as e:
            print(f"Error logo kop surat: {e}")

    # ======================== TEKS KOP SURAT ========================
    offset = 0.4*cm
    center_x = width/2 + offset

    c.setFont("Helvetica", 14)
    c.drawCentredString(center_x, y, "PEMERINTAH KABUPATEN TANGERANG")
    y -= 0.8*cm

    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(center_x, y, "DINAS PERINDUSTRIAN DAN PERDAGANGAN")
    y -= 0.45*cm

    c.setFont("Helvetica", 10)
    alamat_kop = "Jl. Atik Soewardi, Gedung Usaha-Usaha Daerah Lt. 3 Tigaraksa, Tangerang, Banten 15720"
    c.drawCentredString(center_x, y, alamat_kop)
    y -= 0.45*cm

    c.drawCentredString(center_x, y, "Laman: disperindag.tangerangkab.go.id  Pos-el: disperindag@tangerangkab.go.id")
    y -= 0.35*cm

    # ===== GARIS GANDA (menggunakan margin lama) =====
    c.setLineWidth(2)
    c.line(margin_old, y, right_limit_old, y)
    y -= 0.1*cm
    c.setLineWidth(0.8)
    c.line(margin_old, y, right_limit_old, y)
    y -= 0.8*cm

    # ======================== JUDUL & NOMOR ========================
    # Untuk judul, tetap di tengah halaman, tidak terpengaruh margin
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(width/2, y, "SURAT KETERANGAN HASIL PENGUJIAN")
    y -= 0.45*cm
    c.setFont("Helvetica-Oblique", 12)
    c.drawCentredString(width/2, y, "Verification Report")
    y -= 0.45*cm
    c.setFont("Helvetica", 12)
    c.drawCentredString(width/2, y, f"Nomor : {nomor_sertifikat}")
    y -= 0.9*cm

    # ======================== TABEL INFO UTAMA ========================
    # Gunakan margin kiri content (3 cm) untuk semua isi
    left_col_x = margin_left_content
    right_col_x = margin_left_content + 7.0*cm   # posisi kolom kanan (relatif)
    colon_x = margin_left_content + 3.2*cm
    colon_right_x = right_col_x + 0.5*cm

    # Hitung posisi titik dua yang konsisten untuk kiri (berdasarkan label terpanjang)
    label_left = [
        "Nomor Order", "Nama Alat", "Merk / Buatan",
        "Model / Tipe", "Nomor Seri",
        "Pemilik", "Alamat", "Penera", "Hasil",
        "Berlaku sampai", "Catatan"
    ]
    max_width_left = max(c.stringWidth(lbl, "Helvetica", 12) for lbl in label_left)
    colon_x_fixed = left_col_x + max_width_left + 0.5*cm

    # Untuk kanan
    label_right = [
        "Kapasitas / Daya baca",
        "Interval Skala Verifikasi",
        "Kelas"
    ]
    max_width_right = max(c.stringWidth(lbl, "Helvetica", 12) for lbl in label_right)
    colon_right_fixed = right_col_x + max_width_right + 0.5*cm

    # ===== BARIS 1: NOMOR ORDER (dengan offset ekstra) =====
    special_offset = 1.2*cm               # tambahan offset (sesuaikan)
    colon_special = colon_x_fixed + special_offset

    c.setFont("Helvetica", 12)
    c.drawString(left_col_x, y, "Nomor Order")
    bold_width = c.stringWidth("Nomor Order", "Helvetica-Bold", 12)
    c.line(left_col_x, y - 0.08*cm, left_col_x + bold_width, y - 0.08*cm)
    line_spacing = 0.45*cm
    c.setFont("Helvetica-Oblique", 12)
    c.drawString(left_col_x, y - line_spacing, "Order Number")
    c.setFont("Helvetica", 12)
    c.drawString(colon_special, y, ":")
    c.drawString(colon_special + 0.3*cm, y, data.get('nomor_order', ''))
    y -= 0.9*cm

    # ===== BARIS 2: NAMA ALAT (dengan offset ekstra) =====
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left_col_x, y, "Nama Alat")
    bold_width = c.stringWidth("Nama Alat", "Helvetica-Bold", 12)
    c.line(left_col_x, y - 0.08*cm, left_col_x + bold_width, y - 0.08*cm)
    c.setFont("Helvetica-BoldOblique", 12)
    c.drawString(left_col_x, y - line_spacing, "Measuring Instrument")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(colon_special, y, ":")                 # titik dua di posisi khusus
    nama_alat = data.get("nama_alat", "Timbangan Elektronik")
    c.drawString(
        colon_special + 0.3 * cm,
        y,
        nama_alat
    )
    y -= 1.0*cm

    # --------------------- BARIS 3: MERK / BUATAN (KIRI) & KAPASITAS (KANAN) ---------------------
    y_row = y
    # --- KIRI ---
    c.setFont("Helvetica", 12)
    c.drawString(left_col_x, y_row, "Merk / Buatan")
    bold_width_left = c.stringWidth("Merk / Buatan", "Helvetica", 12)
    c.line(left_col_x, y_row - 0.08*cm, left_col_x + bold_width_left, y_row - 0.08*cm)
    line_spacing1 = 0.45*cm
    c.setFont("Helvetica-Oblique", 12)
    c.drawString(left_col_x, y_row - line_spacing1, "Trade Mark /")
    line_spacing2 = 0.45*cm
    c.drawString(left_col_x, y_row - line_spacing1 - line_spacing2, "Manufactured by")

    # Titik dua dan nilai (wrap)
    c.setFont("Helvetica", 12)
    c.drawString(colon_x_fixed, y_row, ":")
    start_x_val = colon_x_fixed + 0.3*cm
    safe_right = right_col_x - 0.2 * cm

    max_val_width = (
        safe_right
        - start_x_val
    )
    char_width_val = c.stringWidth(
        "A",
        "Helvetica",
        12
    )

    chars_per_line_val = max(
        10,
        int(
            max_val_width
            / char_width_val
        )
    )
    merek = data.get('merek', '')
    wrapped_merek = textwrap.wrap(merek, width=chars_per_line_val)
    if wrapped_merek:
        c.drawString(start_x_val, y_row, wrapped_merek[0])
        for i, line in enumerate(wrapped_merek[1:], start=1):
            c.drawString(start_x_val, y_row - i*0.45*cm, line)
        y_row_kiri = y_row - (0.45*cm * (len(wrapped_merek)-1))
    else:
        y_row_kiri = y_row
    
    # ---------- KOLOM KANAN: KAPASITAS / DAYA BACA ----------
    satuan_tampilan = str(
        data.get("satuan")
        or data.get("satuan_tampilan")
        or "kg"
    ).strip()

    if satuan_tampilan not in ["kg", "g"]:
        satuan_tampilan = "kg"

    # Neraca Obat tidak mempunyai Daya Baca
    if is_neraca_obat or is_timbangan_meja:
        label_kapasitas = "Kapasitas Maksimum"
        label_kapasitas_en = "Maximum Capacity"
    else:
        label_kapasitas = "Kapasitas / Daya baca"
        label_kapasitas_en = "Capacity / Accuracy"

    c.setFont("Helvetica", 12)
    c.drawString(
        right_col_x,
        y_row,
        label_kapasitas
    )

    lebar_label_kapasitas = c.stringWidth(
        label_kapasitas,
        "Helvetica",
        12
    )

    c.line(
        right_col_x,
        y_row - 0.08 * cm,
        right_col_x + lebar_label_kapasitas,
        y_row - 0.08 * cm
    )

    c.setFont("Helvetica-Oblique", 12)
    c.drawString(
        right_col_x,
        y_row - line_spacing1,
        label_kapasitas_en
    )

    c.setFont("Helvetica", 12)
    c.drawString(
        colon_right_fixed,
        y_row,
        ":"
    )

    kapasitas_nilai = kg_ke_satuan_tampilan(
        data.get("kapasitas_max", ""),
        satuan_tampilan
    )

    kapasitas_text = format_angka_ringkas(
        kapasitas_nilai
    )

    if is_neraca_obat or is_timbangan_meja:
        # Neraca Obat dan Timbangan Meja
        # hanya menampilkan kapasitas maksimum
        nilai_kapasitas = (
            f"{kapasitas_text} {satuan_tampilan}"
        )

    else:
        daya_baca_nilai = kg_ke_satuan_tampilan(
            data.get("daya_baca", ""),
            satuan_tampilan
        )

        daya_baca_text = format_angka_ringkas(
            daya_baca_nilai
        )

        nilai_kapasitas = (
            f"{kapasitas_text} {satuan_tampilan} / "
            f"{daya_baca_text} {satuan_tampilan}"
        )

    c.drawString(
        colon_right_fixed + 0.3 * cm,
        y_row,
        nilai_kapasitas
    )

    y = min(
        y_row_kiri - 0.5 * cm,
        y_row - 1.5 * cm
    )

   # ============================================================
    # BARIS 4
    # Timbangan Elektronik : Model/Tipe + Interval Skala
    # Alat lain            : Nomor Seri + Interval Skala
    # ============================================================

    y_row = y

    # ---------------- KOLOM KIRI ----------------
    if is_timbangan_elektronik:
        label_kiri = "Model / Tipe"
        label_kiri_en = "Model / Type"
        nilai_kiri = str(
            data.get("model", "")
        )
    else:
        label_kiri = "Nomor Seri"
        label_kiri_en = "Serial Number"
        nilai_kiri = str(
            data.get("no_seri", "")
        )

    c.setFont("Helvetica", 12)

    c.drawString(
        left_col_x,
        y_row,
        label_kiri
    )

    lebar_label_kiri = c.stringWidth(
        label_kiri,
        "Helvetica",
        12
    )

    c.line(
        left_col_x,
        y_row - 0.08 * cm,
        left_col_x + lebar_label_kiri,
        y_row - 0.08 * cm
    )

    c.setFont(
        "Helvetica-Oblique",
        12
    )

    c.drawString(
        left_col_x,
        y_row - 0.45 * cm,
        label_kiri_en
    )

    c.setFont("Helvetica", 12)

    c.drawString(
        colon_x_fixed,
        y_row,
        ":"
    )

    wrapped_nilai_kiri = textwrap.wrap(
        nilai_kiri,
        width=chars_per_line_val
    )

    if wrapped_nilai_kiri:
        c.drawString(
            start_x_val,
            y_row,
            wrapped_nilai_kiri[0]
        )

        for i, line in enumerate(
            wrapped_nilai_kiri[1:],
            start=1
        ):
            c.drawString(
                start_x_val,
                y_row - i * 0.45 * cm,
                line
            )

    # ---------------- KOLOM KANAN: INTERVAL SKALA ----------------
    c.setFont("Helvetica", 12)
    c.drawString(
        right_col_x,
        y_row,
        "Interval Skala Verifikasi"
    )

    bold_width_right = c.stringWidth(
        "Interval Skala Verifikasi",
        "Helvetica",
        12
    )

    c.line(
        right_col_x,
        y_row - 0.08 * cm,
        right_col_x + bold_width_right,
        y_row - 0.08 * cm
    )

    c.setFont("Helvetica-Oblique", 12)
    c.drawString(
        right_col_x,
        y_row - 0.45 * cm,
        "Verification Scale Interval"
    )

    c.setFont("Helvetica", 12)
    c.drawString(
        colon_right_fixed,
        y_row,
        ":"
    )

    interval_skala_nilai = kg_ke_satuan_tampilan(
        data.get("interval_skala", ""),
        satuan_tampilan
    )

    interval_skala_text = format_angka_ringkas(
        interval_skala_nilai
    )

    c.drawString(
        colon_right_fixed + 0.3 * cm,
        y_row,
        f"{interval_skala_text} {satuan_tampilan}"
    )

    jumlah_baris_kiri = max(
        1,
        len(wrapped_nilai_kiri)
    )

    tambahan_turun = (
        (jumlah_baris_kiri - 1)
        * 0.25 * cm
    )

    y = (
        y_row
        - 1.0 * cm
        - tambahan_turun
    )


    # ============================================================
    # BARIS 5
    # Timbangan Elektronik : Nomor Seri + Kelas
    # Alat lain            : Kelas saja
    # ============================================================

    # Posisi BARIS 5 mengikuti posisi baru hasil BARIS 4
    y_row = y
    y_row_kiri = y_row

    # Nomor Seri belum dicetak pada Timbangan Elektronik
    wrapped_seri = []

    if is_timbangan_elektronik:
        c.setFont("Helvetica", 12)
        c.drawString(
            left_col_x,
            y_row,
            "Nomor Seri"
        )

        bold_width_left = c.stringWidth(
            "Nomor Seri",
            "Helvetica",
            12
        )

        c.line(
            left_col_x,
            y_row - 0.08 * cm,
            left_col_x + bold_width_left,
            y_row - 0.08 * cm
        )

        c.setFont("Helvetica-Oblique", 12)
        c.drawString(
            left_col_x,
            y_row - 0.45 * cm,
            "Serial Number"
        )

        c.setFont("Helvetica", 12)
        c.drawString(
            colon_x_fixed,
            y_row,
            ":"
        )

        no_seri = str(
            data.get("no_seri", "")
        )

        wrapped_seri = textwrap.wrap(
            no_seri,
            width=chars_per_line_val
        )

        if wrapped_seri:

            c.drawString(
                start_x_val,
                y_row,
                wrapped_seri[0]
            )

            for i, line in enumerate(
                wrapped_seri[1:],
                start=1
            ):
                c.drawString(
                    start_x_val,
                    y_row - i * 0.45 * cm,
                    line
                )

            y_row_kiri = (
                y_row
                - (
                    0.45 * cm
                    * (len(wrapped_seri) - 1)
                )
            )


    # ---------------- KOLOM KANAN: KELAS ----------------
    c.setFont("Helvetica", 12)
    c.drawString(
        right_col_x,
        y_row,
        "Kelas"
    )

    bold_width_right = c.stringWidth(
        "Kelas",
        "Helvetica",
        12
    )

    c.line(
        right_col_x,
        y_row - 0.08 * cm,
        right_col_x + bold_width_right,
        y_row - 0.08 * cm
    )

    c.setFont("Helvetica-Oblique", 12)
    c.drawString(
        right_col_x,
        y_row - 0.45 * cm,
        "Class"
    )

    c.setFont("Helvetica", 12)
    c.drawString(
        colon_right_fixed,
        y_row,
        ":"
    )

    c.drawString(
        colon_right_fixed + 0.3 * cm,
        y_row,
        str(data.get("kelas", ""))
    )

    if is_timbangan_elektronik:
        jumlah_baris_seri = max(
            1,
            len(wrapped_seri)
        )

        tambahan_turun_seri = (
            (jumlah_baris_seri - 1)
            * 0.45 * cm
        )
    else:
        tambahan_turun_seri = 0

    y = (
        y_row
        - 1.3 * cm
        - tambahan_turun_seri
    )

        # ======================== PEMILIK, ALAMAT, PENERA, DLL ========================
    # Semua menggunakan margin kiri content
    # Tentukan posisi titik dua yang digeser untuk bagian ini (sama dengan baris 1&2)
    special_offset = 1.2*cm   # sesuaikan
    colon_fixed_shifted = colon_x_fixed + special_offset

    # ======================== PEMILIK ========================
    c.setFont(
        "Helvetica-Bold",
        12
    )

    c.drawString(
        left_col_x,
        y,
        "Pemilik"
    )

    bold_width = c.stringWidth(
        "Pemilik",
        "Helvetica-Bold",
        12
    )

    c.line(
        left_col_x,
        y - 0.08 * cm,
        left_col_x + bold_width,
        y - 0.08 * cm
    )

    c.setFont(
        "Helvetica-BoldOblique",
        12
    )

    c.drawString(
        left_col_x,
        y - line_spacing,
        "User"
    )

    c.setFont(
        "Helvetica-Bold",
        12
    )

    c.drawString(
        colon_fixed_shifted,
        y,
        ":"
    )

    start_x_pemilik = (
        colon_fixed_shifted
        + 0.3 * cm
    )

    max_width_pemilik = (
        right_limit_content
        - start_x_pemilik
    )

    char_width_pemilik = c.stringWidth(
        "A",
        "Helvetica-Bold",
        12
    )

    chars_per_line_pemilik = max(
        10,
        int(
            max_width_pemilik
            / char_width_pemilik
        )
    )

    pemilik_text = str(
        data.get(
            "pemilik",
            ""
        )
    )

    wrapped_pemilik = textwrap.wrap(
        pemilik_text,
        width=chars_per_line_pemilik
    )

    if wrapped_pemilik:

        c.drawString(
            start_x_pemilik,
            y,
            wrapped_pemilik[0]
        )

        for i, line in enumerate(
            wrapped_pemilik[1:],
            start=1
        ):
            c.drawString(
                start_x_pemilik,
                y - i * 0.45 * cm,
                line
            )

        y -= (
            0.45 * cm
            * (len(wrapped_pemilik) - 1)
        )

    # Jarak ke Alamat
    y -= 1.0 * cm

    # Alamat
    c.setFont("Helvetica", 12)
    c.drawString(left_col_x, y, "Alamat")
    bold_width = c.stringWidth("Alamat", "Helvetica", 12)
    c.line(left_col_x, y - 0.08*cm, left_col_x + bold_width, y - 0.08*cm)
    c.setFont("Helvetica-Oblique", 12)
    c.drawString(left_col_x, y - line_spacing, "Address")
    c.setFont("Helvetica", 12)
    c.drawString(colon_fixed_shifted, y, ":")
    # Wrap alamat
    max_width_alamat = right_limit_content - colon_fixed_shifted - 0.3*cm
    char_width = c.stringWidth("a", "Helvetica", 12)
    chars_per_line = int(max_width_alamat / char_width) if char_width > 0 else 40
    alamat = data.get('alamat', '')
    wrapped_lines = textwrap.wrap(alamat, width=chars_per_line)
    if wrapped_lines:
        start_x = colon_fixed_shifted + 0.3*cm
        line_height = 0.45*cm
        c.drawString(start_x, y, wrapped_lines[0])
        for i, line in enumerate(wrapped_lines[1:], start=1):
            c.drawString(start_x, y - i*line_height, line)
        y -= (line_height * (len(wrapped_lines) - 1)) + 0.9*cm
    else:
        y -= 0.6*cm

    # Penera
    c.setFont("Helvetica", 12)
    c.drawString(left_col_x, y, "Penera")
    bold_width_penera = c.stringWidth("Penera", "Helvetica", 12)
    c.line(left_col_x, y - 0.08*cm, left_col_x + bold_width_penera, y - 0.08*cm)
    c.setFont("Helvetica-Oblique", 12)
    c.drawString(left_col_x, y - line_spacing, "Calibration Technician")
    c.setFont("Helvetica", 12)
    c.drawString(colon_fixed_shifted, y, ":")
    penera_text = f"{data.get('nama_penera', '')} / NIP. {data.get('nip_penera', '')}"
    c.drawString(colon_fixed_shifted + 0.3*cm, y, penera_text)
    y -= 1.0*cm
    
    # ============================================================
    # JENIS PENGUJIAN DAN TAHUN TANDA
    # ============================================================

    jenis_pengujian = str(
        data.get(
            "keterangan",
            "Tera Ulang"
        )
    ).strip()

    tanggal_pengujian_raw = (
        data.get("tanggal")
        or data.get("tanggal_penera")
        or ""
    )

    try:
        if isinstance(tanggal_pengujian_raw, str):
            tanggal_obj = datetime.strptime(
                tanggal_pengujian_raw,
                "%Y-%m-%d"
            )
        else:
            tanggal_obj = tanggal_pengujian_raw

        tahun_pengujian = tanggal_obj.year

    except Exception:
        tahun_pengujian = datetime.now().year

    tahun_tanda = str(
        tahun_pengujian
    )[-2:]
    
    # Hasil
    c.setFont("Helvetica", 12)
    c.drawString(left_col_x, y, "Hasil")
    bold_width = c.stringWidth("Hasil", "Helvetica", 12)
    c.line(left_col_x, y - 0.08*cm, left_col_x + bold_width, y - 0.08*cm)
    c.setFont("Helvetica-Oblique", 12)
    c.drawString(left_col_x, y - line_spacing, "Results")
    c.setFont("Helvetica", 12)
    c.drawString(colon_fixed_shifted, y, ":")
    start_x = colon_fixed_shifted + 0.3*cm
    c.drawString(
        start_x,
        y,
        f"Disahkan untuk {jenis_pengujian} Tahun {tahun_pengujian}"
    )
    y -= 0.45*cm
    # Teks bawah hasil menggunakan posisi start yang sama
    c.drawString(start_x, y, "Berdasarkan Undang - Undang RI No. 2 Tahun 1981")
    y -= 0.45*cm
    c.drawString(start_x, y, "Tentang Metrologi Legal")
    y -= 0.6*cm

    # Berlaku sampai
    c.setFont("Helvetica", 12)
    c.drawString(left_col_x, y, "Berlaku sampai")
    bold_width = c.stringWidth("Berlaku sampai", "Helvetica", 12)
    c.line(left_col_x, y - 0.08*cm, left_col_x + bold_width, y - 0.08*cm)
    c.setFont("Helvetica-Oblique", 12)
    c.drawString(left_col_x, y - line_spacing, "This report due to")
    berlaku_str = format_tanggal_indonesia(data.get('berlaku_sampai', ''))
    c.setFont("Helvetica", 12)
    c.drawString(colon_fixed_shifted, y, ":")
    c.drawString(colon_fixed_shifted + 0.3*cm, y, berlaku_str)
    y -= 1.0*cm

   # ======================== CATATAN ========================
    c.setFont("Helvetica", 12)
    c.drawString(left_col_x, y, "Catatan")

    bold_width = c.stringWidth(
        "Catatan",
        "Helvetica",
        12
    )

    c.line(
        left_col_x,
        y - 0.08 * cm,
        left_col_x + bold_width,
        y - 0.08 * cm
    )

    c.setFont("Helvetica-Oblique", 12)
    c.drawString(
        left_col_x,
        y - line_spacing,
        "Note"
    )

    c.setFont("Helvetica", 12)
    c.drawString(
        colon_fixed_shifted,
        y,
        ":"
    )

    bullet = "•"
    x_catatan = colon_fixed_shifted + 0.3 * cm
    line_height = 0.45 * cm


    # ========================================================
    # JIKA USER MEMILIH TERA
    # ========================================================
    if jenis_pengujian.lower() == "tera":
        c.drawString(
            x_catatan,
            y,
            "Pembubuhan Tanda Tera :"
        )

        y -= line_height

        c.drawString(
            x_catatan,
            y,
            f'{bullet} Tanda Tera Sah SL6 "{tahun_tanda}", Tanda Daerah D8 dan'
        )

        y -= line_height

        c.drawString(
            x_catatan,
            y,
            "  Tanda Pegawai Berhak H pada lemping yang dililit"
        )

        y -= line_height

        c.drawString(
            x_catatan,
            y,
            "  dengan kawat yang disegel dengan Tanda Jaminan JP8."
        )

        y -= line_height

        c.drawString(
            x_catatan,
            y,
            f"{bullet} Tanda Jaminan JP8 pada bagian yang dapat menjadi"
        )

        y -= line_height

        c.drawString(
            x_catatan,
            y,
            "  potensi dilakukan perubahan yang mempengaruhi"
        )

        y -= line_height

        c.drawString(
            x_catatan,
            y,
            "  karakteristik kemetrologiannya."
        )


    # ========================================================
    # JIKA USER MEMILIH TERA ULANG
    # ========================================================
    else:
        c.drawString(
            x_catatan,
            y,
            "Pembubuhan Tanda Tera Ulang :"
        )

        y -= line_height

        c.drawString(
            x_catatan,
            y,
            f'{bullet} Tanda Tera SAH SP6 "{tahun_tanda}" dan JP8 pada Alat Justir'
        )

        y -= line_height

        c.drawString(
            x_catatan,
            y,
            f"{bullet} Tanda Jaminan JP8 pada bagian yang dapat menjadi"
        )

        y -= line_height

        c.drawString(
            x_catatan,
            y,
            "  potensi dilakukan perubahan yang mempengaruhi"
        )

        y -= line_height

        c.drawString(
            x_catatan,
            y,
            "  karakteristik kemetrologiannya."
        )


    # Jarak sebelum peringatan
    y -= 0.9 * cm

    # ======================== PERINGATAN SEGEL ========================
    c.setFont("Helvetica-Bold", 12)

    c.drawString(
        x_catatan,
        y,
        "Dilarang Memutus Segel Tera tanpa sepengetahuan"
    )

    y -= line_height

    c.drawString(
        x_catatan,
        y,
        "Unit Metrologi Legal"
    )

    y -= 0.9 * cm

    # ======================== TANDA TANGAN (HALAMAN 1) ========================
    # Gunakan margin lama agar posisi tidak berubah
    x_right_align = width - margin_old - 10*cm   # posisi seperti sebelumnya
    c.setFont("Helvetica", 12)
    tanggal_ttd = (
        data.get("tanggal_tanda_tangan")
        or data.get("tanggal_sertifikat")
        or data.get("tanggal")
        or ""
    )

    c.drawString(
        x_right_align,
        y,
        f"Tangerang, {format_tanggal_indonesia(tanggal_ttd)}"
    )
    y -= 0.9*cm
    c.drawString(x_right_align, y, "A.n Kepala Dinas Perindustrian dan Perdagangan")
    y -= 0.45*cm
    c.drawString(x_right_align, y, "Kabupaten Tangerang")
    y -= 0.45*cm
    c.drawString(x_right_align, y, "Kepala Bidang Kemetrologian")
    y -= 2.0*cm
    c.drawString(x_right_align, y, "Priatin Saputra, S.Kom.,M.Si")
    y -= 0.45*cm
    c.drawString(x_right_align, y, "Penata Tk.I (III/d)")
    y -= 0.45*cm
    c.drawString(x_right_align, y, "NIP. 198505152011011004")
    y -= 0.45*cm

    # ======================== FOOTER HALAMAN 1 ========================
    c.setLineWidth(0.5)
    c.line(margin_old, 1.8*cm, right_limit_old, 1.8*cm)
    c.setFillGray(0)
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(margin_old, 1.5*cm, "Dilarang menggandakan sebagian dan atau seluruh isi Surat Keterangan Hasil Pengujian ini tanpa seizin dari")
    c.drawString(margin_old, 1.2*cm, "Bidang Kemetrologian Kabupaten Tangerang")
    c.drawRightString(right_limit_old, 0.9*cm, "Halaman 1 dari 2")

    # ======================== HALAMAN BARU (2) ========================
    c.showPage()
    y = height - margin_old   # gunakan margin lama untuk header

    # ======================== HEADER HALAMAN 2 ========================
    c.setFillGray(0)
    c.setFont("Helvetica", 10)
    c.drawRightString(right_limit_old, y, f"Lampiran Sertifikat Nomor : {nomor_sertifikat}")
    c.setFillGray(0)
    y -= 1.8*cm

    # ======================== SPESIFIKASI TEKNIS STANDAR ========================
    # Gunakan margin kiri content (3 cm)
    left_col_x = margin_left_content
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left_col_x, y, "SPESIFIKASI TEKNIS STANDAR")
    y -= 0.45*cm
    c.setFont("Helvetica-Oblique", 12)
    c.drawString(left_col_x, y, "Standard Technical Specification")
    y -= 0.9*cm
    c.setFont("Helvetica", 12)
    c.drawString(left_col_x, y, "Metode, Standar, dan Telusuran")
    y -= 0.45*cm
    c.setFont("Helvetica", 12)
    c.drawString(left_col_x, y, "Metode")
    c.drawString(colon_x_fixed, y, ":")
    normal_text = "Membandingkan langsung dengan standar ("
    italic_text = "Direct Comparison"
    closing_text = ")"
    c.drawString(colon_x_fixed + 0.3*cm, y, normal_text)
    normal_width = c.stringWidth(normal_text, "Helvetica", 12)
    x_italic = colon_x_fixed + 0.3*cm + normal_width
    c.setFont("Helvetica-Oblique", 12)
    c.drawString(x_italic, y, italic_text)
    italic_width = c.stringWidth(italic_text, "Helvetica-Oblique", 12)
    x_closing = x_italic + italic_width
    c.setFont("Helvetica", 12)
    c.drawString(x_closing, y, closing_text)
    y -= 0.45*cm

    c.setFont("Helvetica", 12)

    # Standar
    c.drawString(left_col_x, y, "Standar")
    c.drawString(colon_x_fixed, y, ":")

    kelas_standar = str(
        data.get("at_standar")
        or data.get("kelas_standar")
        or "M2"
    ).strip()

    standar_text = f"Anak Timbangan Standar Kelas {kelas_standar}"

    c.drawString(
        colon_x_fixed + 0.3 * cm,
        y,
        standar_text
    )

    y -= 0.45 * cm

    # Telusuran
    c.drawString(left_col_x, y, "Telusuran")
    c.drawString(colon_x_fixed, y, ":")
    c.drawString(
        colon_x_fixed + 0.3 * cm,
        y,
        "Direktorat Metrologi Bandung"
    )

    y -= 0.9 * cm

    # ======================== KONDISI PENGUJIAN ========================
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left_col_x, y, "KONDISI PENGUJIAN")
    y -= 0.45 * cm

    c.setFont("Helvetica-Oblique", 12)
    c.drawString(left_col_x, y, "Condition of Verification")
    y -= 0.9 * cm

    labels = [
        "- Lokasi",
        "- Suhu ruangan",
        "- Kelembaban relatif",
        "- Tanggal"
    ]

    max_label_width = max(
        c.stringWidth(label, "Helvetica", 12)
        for label in labels
    )

    x_bullet = left_col_x + 0.6 * cm
    x_colon_cond = x_bullet + max_label_width + 0.2 * cm
    x_value_cond = x_colon_cond + 0.3 * cm

    # --------------------------------------------------------
    # TENTUKAN LOKASI PENGUJIAN
    # --------------------------------------------------------
    pilihan_lokasi = str(
        data.get("lokasi_pengujian")
        or data.get("lokasi")
        or ""
    ).strip()

    pilihan_lokasi_lower = pilihan_lokasi.lower()

    if pilihan_lokasi_lower in [
        "perusahaan",
        "di perusahaan",
        "lokasi perusahaan"
    ]:
        lokasi_nilai = str(
            data.get("nama_perusahaan")
            or data.get("pemilik")
            or ""
        ).strip()

    elif pilihan_lokasi_lower in [
        "dalam kantor",
        "kantor",
        "di kantor",
        "unit metrologi legal"
    ]:
        lokasi_nilai = "Unit Metrologi Legal Kabupaten Tangerang"

    else:
        # Fallback bila data aplikasi langsung menyimpan nama lokasi
        lokasi_nilai = pilihan_lokasi

    # --------------------------------------------------------
    # TENTUKAN METODE PENGUJIAN
    # --------------------------------------------------------
    metode_nilai = str(
        data.get("metode")
        or data.get("metode_pengujian")
        or "Beban Substitusi Tunggal"
    ).strip()

    c.setFont("Helvetica", 12)
    c.drawString(
        left_col_x + 0.3 * cm,
        y,
        "1. Pengujian dilakukan dalam ruangan dengan kondisi sebagai berikut :"
    )

    y -= 0.45 * cm

    # Lokasi
    c.drawString(x_bullet, y, "- Lokasi")
    c.drawString(x_colon_cond, y, ":")
    c.drawString(x_value_cond, y, lokasi_nilai)

    y -= 0.45 * cm

    # Suhu
    c.drawString(x_bullet, y, "- Suhu ruangan")
    c.drawString(x_colon_cond, y, ":")
    c.drawString(
        x_value_cond,
        y,
        str(data.get("suhu") or "Ambient")
    )

    y -= 0.45 * cm

    # Kelembaban
    c.drawString(x_bullet, y, "- Kelembaban relatif")
    c.drawString(x_colon_cond, y, ":")
    c.drawString(
        x_value_cond,
        y,
        str(data.get("kelembaban") or "Ambient")
    )

    y -= 0.45 * cm

    # Tanggal
    c.drawString(x_bullet, y, "- Tanggal")
    c.drawString(x_colon_cond, y, ":")

    tanggal_nilai = format_tanggal_indonesia(
        data.get("tanggal_penera")
        or data.get("tanggal_pengujian")
        or ""
    )

    c.drawString(x_value_cond, y, tanggal_nilai)

    y -= 0.45 * cm

    # Metode
    c.drawString(
        left_col_x + 0.3 * cm,
        y,
        f"2. Metode yang digunakan adalah {metode_nilai}."
    )

    y -= 1.3 * cm

    # ======================== TABEL HASIL PENGUJIAN ========================
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left_col_x, y, "HASIL PENGUJIAN")
    y -= 0.45 * cm

    c.setFont("Helvetica-Oblique", 12)
    c.drawString(left_col_x, y, "Verification Results")
    y -= 0.45 * cm

    # Satuan mengikuti pilihan user pada aplikasi
    satuan_tampilan = str(
        data.get("satuan")
        or data.get("satuan_tampilan")
        or "kg"
    ).strip()

    if satuan_tampilan not in ["kg", "g"]:
        satuan_tampilan = "kg"

    x_kiri = left_col_x
    x_no_kanan = left_col_x + 1.5 * cm
    x_penunjukan_kiri = x_no_kanan + 0.2 * cm
    x_penunjukan_kanan = x_penunjukan_kiri + 4.0 * cm
    x_kesalahan_kiri = x_penunjukan_kanan + 0.3 * cm

    c.setFont("Helvetica-Bold", 12)
    lebar_kesalahan = c.stringWidth(
        f"Kesalahan ({satuan_tampilan})",
        "Helvetica-Bold",
        12
    )

    x_kesalahan_kanan = (
        x_kesalahan_kiri
        + lebar_kesalahan
        + 0.5 * cm
    )

    x_akhir = x_kesalahan_kanan

    # ---------------- HEADER TABEL ----------------
    y_header = y
    c.line(x_kiri, y_header, x_akhir, y_header)

    c.setFont("Helvetica-Bold", 12)

    y_center_no = y_header - 0.6 * cm
    c.drawCentredString(
        x_kiri + (x_no_kanan - x_kiri) / 2,
        y_center_no,
        "No."
    )

    y_line1 = y_header - 0.4 * cm
    y_line2 = y_header - 0.8 * cm

    x_pen_tengah = (
        x_penunjukan_kiri
        + (x_penunjukan_kanan - x_penunjukan_kiri) / 2
    )

    c.drawCentredString(
        x_pen_tengah,
        y_line1,
        "Penunjukan"
    )

    c.drawCentredString(
        x_pen_tengah,
        y_line2,
        f"({satuan_tampilan})"
    )

    x_kes_tengah = (
        x_kesalahan_kiri
        + (x_kesalahan_kanan - x_kesalahan_kiri) / 2
    )

    c.drawCentredString(
        x_kes_tengah,
        y_line1,
        "Kesalahan"
    )

    c.drawCentredString(
        x_kes_tengah,
        y_line2,
        f"({satuan_tampilan})"
    )

    y_line_bawah_header = y_header - 1.0 * cm
    c.line(
        x_kiri,
        y_line_bawah_header,
        x_akhir,
        y_line_bawah_header
    )

    # ---------------- DATA HASIL PENGUJIAN ----------------
    test_results = list(
        data.get("hasil_pengujian", []) or []
    )

    c.setFont("Helvetica", 12)

    # Neraca Obat hanya memiliki satu baris pengujian aktif
    if is_neraca_obat or is_timbangan_meja:
        indeks_yang_ditampilkan = [0]
    else:
        indeks_yang_ditampilkan = [0, 1, 2, 3, 4]

    jumlah_baris = len(
        indeks_yang_ditampilkan
    )

    tinggi_baris = 0.45 * cm
    padding_vertikal = 0.1 * cm

    y_data = (
        y_line_bawah_header
        - padding_vertikal
        - tinggi_baris
    )


    def ambil_angka_tanpa_satuan(value):
        """
        Menghapus tulisan kg atau g jika data sudah berbentuk:
        '50 kg', '50,00 g', dan sejenisnya.
        """
        if value is None:
            return ""

        text = str(value).strip()

        text = text.replace(" kg", "")
        text = text.replace(" KG", "")
        text = text.replace(" g", "")
        text = text.replace(" G", "")

        return text.strip()


    for nomor, idx in enumerate(
        indeks_yang_ditampilkan,
        start=1
    ):
        if idx < len(test_results):
            res = test_results[idx] or {}

            # Prioritas pengambilan nilai Penunjukan:
            # 1. penunjukan_text
            # 2. penunjukan_tampil
            # 3. penunjukan
            # 4. timbangan_text
            # 5. timbangan
            penunjukan = res.get(
                "penunjukan_text",
                ""
            )

            if penunjukan in [None, ""]:
                penunjukan = res.get(
                    "penunjukan_tampil",
                    ""
                )

            if penunjukan in [None, ""]:
                penunjukan = res.get(
                    "penunjukan",
                    ""
                )

            if penunjukan in [None, ""]:
                penunjukan = res.get(
                    "timbangan_text",
                    ""
                )

            if penunjukan in [None, ""]:
                penunjukan = res.get(
                    "timbangan",
                    ""
                )

            penunjukan = ambil_angka_tanpa_satuan(
                penunjukan
            )
#kesalahan
            kesalahan = "0"

        else:
            penunjukan = ""
            kesalahan = "0"

        c.drawCentredString(
            x_kiri + (x_no_kanan - x_kiri) / 2,
            y_data,
            f"{nomor}."
        )

        c.drawCentredString(
            x_pen_tengah,
            y_data,
            str(penunjukan)
        )

        c.drawCentredString(
            x_kes_tengah,
            y_data,
            str(kesalahan)
        )

        y_data -= tinggi_baris

    # ---------------- GARIS TABEL ----------------
    y_bottom = (
        y_line_bawah_header
        - padding_vertikal
        - (jumlah_baris * tinggi_baris)
        - padding_vertikal
    )

    c.line(
        x_kiri,
        y_bottom,
        x_akhir,
        y_bottom
    )

    y_top = y_header

    c.line(
        x_kiri,
        y_top,
        x_kiri,
        y_bottom
    )

    c.line(
        x_no_kanan,
        y_top,
        x_no_kanan,
        y_bottom
    )

    c.line(
        x_penunjukan_kanan,
        y_top,
        x_penunjukan_kanan,
        y_bottom
    )

    c.line(
        x_akhir,
        y_top,
        x_akhir,
        y_bottom
    )

    y = y_bottom - 1.8 * cm

    # ---------------- KETERANGAN ----------------
    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        left_col_x,
        y,
        "Keterangan :"
    )

    y -= 0.45 * cm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        left_col_x,
        y,
        "Penunjukan sebenarnya : Penunjukan – Kesalahan"
    )

    y -= 1.8 * cm

    # ======================== TANDA TANGAN PENERA (HALAMAN 2) ========================
    # Gunakan margin lama agar posisi tidak berubah
    x_right_align = width - margin_old - 10*cm
    c.setFont("Helvetica", 12)
    c.drawString(x_right_align, y, "Pegawai Berhak,")
    y -= 2.0*cm
    c.drawString(x_right_align, y, data.get('nama_penera', ''))
    y -= 0.45*cm
    golongan = data.get('golongan_penera', '')
    c.drawString(x_right_align, y, golongan if golongan else "Penata Muda Tk. I (III/b)")
    y -= 0.45*cm
    c.drawString(x_right_align, y, f"NIP. {data.get('nip_penera', '')}")
    y -= 0.8*cm

    # ======================== FOOTER HALAMAN 2 ========================
    c.setLineWidth(0.5)
    c.line(margin_old, 1.8*cm, right_limit_old, 1.8*cm)
    c.setFillGray(0)
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(margin_old, 1.5*cm, "Dilarang menggandakan sebagian dan atau seluruh isi Surat Keterangan Hasil Pengujian ini tanpa seizin dari")
    c.drawString(margin_old, 1.2*cm, "Bidang Kemetrologian Kabupaten Tangerang")
    c.drawRightString(right_limit_old, 0.9*cm, "Halaman 2 dari 2")

    c.save()
    return filename