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
        
def generate_sertifikat_pdf(data, filename, nomor_sertifikat):
    width, height = A4
    c = canvas.Canvas(filename, pagesize=A4)
    
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
    right_col_x = margin_left_content + 7.5*cm   # posisi kolom kanan (relatif)
    colon_x = margin_left_content + 3.2*cm
    colon_right_x = right_col_x + 0.5*cm

    # Hitung posisi titik dua yang konsisten untuk kiri (berdasarkan label terpanjang)
    label_left = [
        "Nomor Order", "Nama Alat", "Merek / Buatan",
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
    c.drawString(colon_special + 0.3*cm, y, "Timbangan Jembatan Elektronik")
    y -= 1.0*cm

        # --------------------- BARIS 3: MERK / BUATAN (KIRI) & KAPASITAS (KANAN) ---------------------
    y_row = y
    # --- KIRI ---
    c.setFont("Helvetica", 12)
    c.drawString(left_col_x, y_row, "Merek / Buatan")
    bold_width_left = c.stringWidth("Merek / Buatan", "Helvetica", 12)
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
    # Batas sebelum kolom kanan
    safe_right = right_col_x - 0.5*cm
    max_val_width = safe_right - start_x_val
    char_width_val = c.stringWidth("A", "Helvetica", 12)
    chars_per_line_val = max(
        10,
        int(max_val_width / char_width_val)
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

    # ---------- KOLOM KANAN: Kapasitas / Daya baca ----------
    c.setFont("Helvetica", 12)
    c.drawString(right_col_x, y_row, "Kapasitas / Daya baca")
    bold_width_right = c.stringWidth("Kapasitas / Daya baca", "Helvetica", 12)
    c.line(right_col_x, y_row - 0.08*cm, right_col_x + bold_width_right, y_row - 0.08*cm)
    c.setFont("Helvetica-Oblique", 12)
    c.drawString(right_col_x, y_row - line_spacing1, "Capacity / Accuracy")
    c.setFont("Helvetica", 12)
    c.drawString(colon_right_fixed, y_row, ":")
    kapasitas = f"{int(data.get('kapasitas_max', 0)):,}".replace(",", ".")
    daya_baca = f"{int(data.get('daya_baca', 0)):,}".replace(",", ".")

    c.drawString(
        colon_right_fixed + 0.3*cm,
        y_row,
        f"{kapasitas} kg / {daya_baca} kg"
    )

    # Update y berdasarkan posisi terendah (kiri bisa wrap)
    # Turun minimal 1.3 cm agar tidak menabrak baris berikutnya
    y = min(y_row_kiri - 0.5*cm, y_row - 1.3*cm)

    # --------------------- BARIS 4: MODEL / TIPE (KIRI) & INTERVAL SKALA (KANAN) ---------------------
    y_row = y
    # --- KIRI ---
    c.setFont("Helvetica", 12)
    c.drawString(left_col_x, y_row, "Model / Tipe")
    bold_width_left = c.stringWidth("Model / Tipe", "Helvetica", 12)
    c.line(left_col_x, y_row - 0.08*cm, left_col_x + bold_width_left, y_row - 0.08*cm)
    c.setFont("Helvetica-Oblique", 12)
    c.drawString(left_col_x, y_row - 0.45*cm, "Model / Type")
    c.setFont("Helvetica", 12)
    c.drawString(colon_x_fixed, y_row, ":")
    start_x_val = colon_x_fixed + 0.3*cm
    model = data.get('model', '')
    wrapped_model = textwrap.wrap(model, width=chars_per_line_val)
    if wrapped_model:
        c.drawString(start_x_val, y_row, wrapped_model[0])
        for i, line in enumerate(wrapped_model[1:], start=1):
            c.drawString(start_x_val, y_row - i*0.45*cm, line)
        y_row_kiri = y_row - (0.45*cm * (len(wrapped_model)-1))
    else:
        y_row_kiri = y_row

    # ---------- KOLOM KANAN: Interval Skala Verifikasi ----------
    c.setFont("Helvetica", 12)
    c.drawString(right_col_x, y_row, "Interval Skala Verifikasi")
    bold_width_right = c.stringWidth("Interval Skala Verifikasi", "Helvetica", 12)
    c.line(right_col_x, y_row - 0.08*cm, right_col_x + bold_width_right, y_row - 0.08*cm)
    c.setFont("Helvetica-Oblique", 12)
    c.drawString(right_col_x, y_row - 0.45*cm, "Verification Scale Interval")
    c.setFont("Helvetica", 12)
    c.drawString(colon_right_fixed, y_row, ":")
    c.drawString(colon_right_fixed + 0.3*cm, y_row, f"{data.get('interval_skala', '')} kg")

    # Turun minimal 1.3 cm agar baris berikutnya tetap stabil
    y = min(y_row_kiri - 0.5*cm, y_row - 1.3*cm)

    # --------------------- BARIS 5: NOMOR SERI (KIRI) & KELAS (KANAN) ---------------------
    y_row = y
    # --- KIRI ---
    c.setFont("Helvetica", 12)
    c.drawString(left_col_x, y_row, "Nomor Seri")
    bold_width_left = c.stringWidth("Nomor Seri", "Helvetica", 12)
    c.line(left_col_x, y_row - 0.08*cm, left_col_x + bold_width_left, y_row - 0.08*cm)
    c.setFont("Helvetica-Oblique", 12)
    c.drawString(left_col_x, y_row - 0.45*cm, "Serial Number")
    c.setFont("Helvetica", 12)
    c.drawString(colon_x_fixed, y_row, ":")
    start_x_val = colon_x_fixed + 0.3*cm
    no_seri = data.get('no_seri', '')
    wrapped_seri = textwrap.wrap(no_seri, width=chars_per_line_val)
    if wrapped_seri:
        c.drawString(start_x_val, y_row, wrapped_seri[0])
        for i, line in enumerate(wrapped_seri[1:], start=1):
            c.drawString(start_x_val, y_row - i*0.45*cm, line)
        y_row_kiri = y_row - (0.45*cm * (len(wrapped_seri)-1))
    else:
        y_row_kiri = y_row

    # ---------- KOLOM KANAN: Kelas ----------
    c.setFont("Helvetica", 12)
    c.drawString(right_col_x, y_row, "Kelas")
    bold_width_right = c.stringWidth("Kelas", "Helvetica", 12)
    c.line(right_col_x, y_row - 0.08*cm, right_col_x + bold_width_right, y_row - 0.08*cm)
    c.setFont("Helvetica-Oblique", 12)
    c.drawString(right_col_x, y_row - 0.45*cm, "Class")
    c.setFont("Helvetica", 12)
    c.drawString(colon_right_fixed, y_row, ":")
    c.drawString(colon_right_fixed + 0.3*cm, y_row, data.get('kelas', ''))

    y = min(y_row_kiri - 0.5*cm, y_row - 1.3*cm)

        # ======================== PEMILIK, ALAMAT, PENERA, DLL ========================
    # Semua menggunakan margin kiri content
    # Tentukan posisi titik dua yang digeser untuk bagian ini (sama dengan baris 1&2)
    special_offset = 1.2*cm   # sesuaikan
    colon_fixed_shifted = colon_x_fixed + special_offset

    # Pemilik
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left_col_x, y, "Pemilik")
    bold_width = c.stringWidth("Pemilik", "Helvetica-Bold", 12)
    c.line(left_col_x, y - 0.08*cm, left_col_x + bold_width, y - 0.08*cm)
    c.setFont("Helvetica-BoldOblique", 12)
    c.drawString(left_col_x, y - line_spacing, "User")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(colon_fixed_shifted, y, ":")
    c.drawString(colon_fixed_shifted + 0.3*cm, y, data.get('pemilik', ''))
    y -= 1.0*cm

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
    jenis_pengujian = data.get('keterangan', 'Tera Ulang')
    tahun_tera = datetime.now().year
    # Teks hasil dibuat bold
    c.setFont("Helvetica-Bold", 12)
    c.drawString(start_x, y, f"Disahkan untuk {jenis_pengujian} Tahun {tahun_tera}")
    # Kembali ke font normal
    c.setFont("Helvetica", 12)
    y -= 0.45*cm
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
    # Nilai tanggal dibuat bold
    c.setFont("Helvetica-Bold", 12)
    c.drawString(colon_fixed_shifted + 0.3*cm, y, berlaku_str)
    # Kembali ke font normal
    c.setFont("Helvetica", 12)
    y -= 1.0*cm

    # Catatan
    c.setFont("Helvetica", 12)
    c.drawString(left_col_x, y, "Catatan")
    bold_width = c.stringWidth("Catatan", "Helvetica", 12)
    c.line(left_col_x, y - 0.08*cm, left_col_x + bold_width, y - 0.08*cm)

    c.setFont("Helvetica-Oblique", 12)
    c.drawString(left_col_x, y - line_spacing, "Note")

    c.setFont("Helvetica", 12)
    c.drawString(colon_fixed_shifted, y, ":")

    start_x = colon_fixed_shifted + 0.3*cm
    bullet = "•"

    jenis_pengujian = data.get("keterangan", "Tera Ulang")
    tahun = datetime.now().strftime("%y")

    if jenis_pengujian == "Tera":
        c.drawString(start_x, y, "Pembubuhan Tanda Tera :")
        y -= 0.45*cm

        c.drawString(start_x, y, f"{bullet} Tanda Daerah D4, Tanda Pegawai Berhak H dan Tanda")
        y -= 0.45*cm

        c.drawString(start_x, y, f"  Tera Sah SL4 \"{tahun}\" pada lemping yang dililit dengan kawat")
        y -= 0.45*cm

        c.drawString(start_x, y, f"  yang disegel dengan Tanda Jaminan JP8")
        y -= 0.45*cm

        c.drawString(start_x, y, f"{bullet} Tanda Jaminan JP8 pada bagian yang dapat menjadi")
        y -= 0.45*cm

        c.drawString(start_x, y, "  potensi di lakukan perubahan yang mempengaruhi")
        y -= 0.45*cm

        c.drawString(start_x, y, "  karakteristik kemetrologiannya")

    else:
        c.drawString(start_x, y, "Pembubuhan Tanda Tera Ulang :")
        y -= 0.45*cm

        c.drawString(start_x, y, f"{bullet} Tanda Tera SAH SP6 \"{tahun}\" dan JP8 pada Alat Justir")
        y -= 0.45*cm

        c.drawString(start_x, y, f"{bullet} Tanda Jaminan JP8 pada bagian yang dapat menjadi")
        y -= 0.45*cm

        c.drawString(start_x, y, "  potensi di lakukan perubahan yang mempengaruhi")
        y -= 0.45*cm

        c.drawString(start_x, y, "  karakteristik kemetrologiannya")

    y -= 0.9*cm

    # Dilarang memutus segel
    c.setFont("Helvetica-Bold", 12)
    c.drawString(start_x, y, "Dilarang Memutus Segel Tera tanpa sepengetahuan")
    y -= 0.45*cm
    c.drawString(start_x, y, "Unit Metrologi Legal")
    y -= 0.9*cm

    # ======================== TANDA TANGAN (HALAMAN 1) ========================
    # Gunakan margin lama agar posisi tidak berubah
    x_right_align = width - margin_old - 10*cm   # posisi seperti sebelumnya
    c.setFont("Helvetica", 12)
    c.drawString(x_right_align, y, f"Tangerang, {format_tanggal_indonesia(data.get('tanggal_sertifikat', ''))}")
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
    c.setFont("Helvetica-Oblique", 10)
    c.drawRightString(
        right_limit_old,
        y,
        f"Lampiran Sertifikat Nomor : {nomor_sertifikat}"
    )
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
    c.drawString(left_col_x, y, "Standar")
    c.drawString(colon_x_fixed, y, ":")
    c.drawString(colon_x_fixed + 0.3*cm, y, "Anak Timbangan Standar Kelas M2")
    y -= 0.45*cm
    c.drawString(left_col_x, y, "Telusuran")
    c.drawString(colon_x_fixed, y, ":")
    c.drawString(colon_x_fixed + 0.3*cm, y, "Direktorat Metrologi")
    y -= 0.9*cm

    # ======================== KONDISI PENGUJIAN ========================
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left_col_x, y, "KONDISI PENGUJIAN")
    y -= 0.45*cm
    c.setFont("Helvetica-Oblique", 12)
    c.drawString(left_col_x, y, "Condition of Verification")
    y -= 0.9*cm

    labels = ["- Lokasi", "- Suhu ruangan", "- Kelembaban relatif", "- Tanggal"]
    max_label_width = max(c.stringWidth(label, "Helvetica", 12) for label in labels)
    x_bullet = left_col_x + 0.6*cm
    x_colon_cond = x_bullet + max_label_width + 0.2*cm
    x_value_cond = x_colon_cond + 0.3*cm

    c.setFont("Helvetica", 12)
    c.drawString(left_col_x + 0.3*cm, y, "1. Pengujian dilakukan dalam ruangan dengan kondisi sebagai berikut :")
    y -= 0.45*cm
    c.drawString(x_bullet, y, "- Lokasi")
    c.drawString(x_colon_cond, y, ":")
    c.drawString(
        x_value_cond,
        y,
        data.get('pemilik') or data.get('lokasi', '')
    )
    y -= 0.45*cm
    c.drawString(x_bullet, y, "- Suhu ruangan")
    c.drawString(x_colon_cond, y, ":")
    c.drawString(x_value_cond, y, f"{data.get('suhu', 'Ambient')}")
    y -= 0.45*cm
    c.drawString(x_bullet, y, "- Kelembaban relatif")
    c.drawString(x_colon_cond, y, ":")
    c.drawString(x_value_cond, y, f"{data.get('kelembaban', 'Ambient')}")
    y -= 0.45*cm
    # Tanggal
    c.drawString(x_bullet, y, "- Tanggal")
    c.drawString(x_colon_cond, y, ":")
    tanggal_nilai = format_tanggal_indonesia(data.get('tanggal_penera', ''))
    c.drawString(x_value_cond, y, tanggal_nilai)
    y -= 0.45*cm
    c.drawString(left_col_x + 0.3*cm, y, f"2. Metode yang digunakan menggunakan metode {data.get('metode', 'Beban Substitusi Tunggal')}.")
    y -= 1.3*cm

    # ======================== TABEL HASIL PENGUJIAN ========================
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left_col_x, y, "HASIL PENGUJIAN")
    y -= 0.45*cm
    c.setFont("Helvetica-Oblique", 12)
    c.drawString(left_col_x, y, "Verification Results")
    y -= 0.45*cm

    x_kiri = left_col_x
    x_no_kanan = left_col_x + 1.5*cm
    x_penunjukan_kiri = x_no_kanan + 0.2*cm
    x_penunjukan_kanan = x_penunjukan_kiri + 4.0*cm
    x_kesalahan_kiri = x_penunjukan_kanan + 0.3*cm

    c.setFont("Helvetica-Bold", 12)
    lebar_kesalahan = c.stringWidth("Kesalahan (kg)", "Helvetica-Bold", 12)
    x_kesalahan_kanan = x_kesalahan_kiri + lebar_kesalahan + 0.5*cm
    x_akhir = x_kesalahan_kanan

    y_header = y
    c.line(x_kiri, y_header, x_akhir, y_header)
    c.setFont("Helvetica-Bold", 12)
    y_center_no = y_header - 0.6*cm
    c.drawCentredString(x_kiri + (x_no_kanan - x_kiri)/2, y_center_no, "No.")
    y_line1 = y_header - 0.4*cm
    y_line2 = y_header - 0.8*cm
    x_pen_tengah = x_penunjukan_kiri + (x_penunjukan_kanan - x_penunjukan_kiri)/2
    c.drawCentredString(x_pen_tengah, y_line1, "Penunjukan")
    c.drawCentredString(x_pen_tengah, y_line2, "(kg)")
    x_kes_tengah = x_kesalahan_kiri + (x_kesalahan_kanan - x_kesalahan_kiri)/2
    c.drawCentredString(x_kes_tengah, y_line1, "Kesalahan")
    c.drawCentredString(x_kes_tengah, y_line2, "(kg)")
    y_line_bawah_header = y_header - 1.0*cm
    c.line(x_kiri, y_line_bawah_header, x_akhir, y_line_bawah_header)
    test_results = data.get('hasil_pengujian', [])
    c.setFont("Helvetica", 12)

    indeks_yang_ditampilkan = [0, 1, 3, 5, 7]
    jumlah_baris = len(indeks_yang_ditampilkan)
    tinggi_baris = 0.45*cm
    padding_vertikal = 0.1*cm  # jarak sama di atas baris pertama & di bawah baris terakhir

    y_data = y_line_bawah_header - padding_vertikal - tinggi_baris
    for i, idx in enumerate(indeks_yang_ditampilkan, 1):
        if idx < len(test_results):
            res = test_results[idx]
            penunjukan = str(res.get('timbangan', ''))
            kesalahan = str(res.get('kesalahan', '0'))
        else:
            penunjukan = ""
            kesalahan = ""
        c.drawCentredString(x_kiri + (x_no_kanan - x_kiri)/2, y_data, f"{i}.")
        c.drawCentredString(x_pen_tengah, y_data, penunjukan)
        c.drawCentredString(x_kes_tengah, y_data, kesalahan)
        y_data -= tinggi_baris

    y_bottom = y_line_bawah_header - padding_vertikal - (jumlah_baris * tinggi_baris) - padding_vertikal
    c.line(x_kiri, y_bottom, x_akhir, y_bottom)
    y_top = y_header
    c.line(x_kiri, y_top, x_kiri, y_bottom)
    c.line(x_no_kanan, y_top, x_no_kanan, y_bottom)
    c.line(x_penunjukan_kanan, y_top, x_penunjukan_kanan, y_bottom)
    c.line(x_akhir, y_top, x_akhir, y_bottom)
    y = y_bottom - 1.8*cm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(left_col_x, y, "Keterangan :")
    y -= 0.45*cm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left_col_x, y, "Penunjukan sebenarnya : Penunjukan – Kesalahan")
    y -= 1.8*cm

    # ======================== TANDA TANGAN PENERA (HALAMAN 2) ========================
    # Posisi dikembalikan seperti awal

    x_right_align = width - margin_old - 10 * cm

    c.setFont("Helvetica", 12)
    c.drawString(x_right_align, y, "Pegawai Berhak,")
    y -= 2.0 * cm

    nama_penera = data.get("nama_penera", "")
    nip_penera = data.get("nip_penera", "")
    golongan_penera = data.get("golongan_penera", "")

    c.drawString(
        x_right_align,
        y,
        nama_penera
    )
    y -= 0.45 * cm

    if golongan_penera:
        c.drawString(
            x_right_align,
            y,
            golongan_penera
        )
        y -= 0.45 * cm

    c.drawString(
        x_right_align,
        y,
        f"NIP. {nip_penera}"
    )
    y -= 0.8 * cm

    # ======================== FOOTER HALAMAN 2 ========================
    c.setLineWidth(0.5)
    c.line(margin_old, 1.8 * cm, right_limit_old, 1.8 * cm)

    c.setFillGray(0)
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(
        margin_old,
        1.5 * cm,
        "Dilarang menggandakan sebagian dan atau seluruh isi Surat Keterangan Hasil Pengujian ini tanpa seizin dari"
    )
    c.drawString(
        margin_old,
        1.2 * cm,
        "Bidang Kemetrologian Kabupaten Tangerang"
    )

    c.drawRightString(
        right_limit_old,
        0.9 * cm,
        "Halaman 2 dari 2"
    )

    c.save()
    return filename
