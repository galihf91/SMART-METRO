from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from datetime import datetime
from pathlib import Path
import textwrap
from reportlab.lib.utils import ImageReader

BASE_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = BASE_DIR / "assets"

watermark_path = ASSETS_DIR / "logo_metrologi.png"
logo_path = ASSETS_DIR / "logo.png"


def format_tanggal_indonesia(tanggal_str):
    if not tanggal_str:
        return ""

    if isinstance(tanggal_str, datetime):
        t = tanggal_str
        bulan = [
            "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"
        ]
        return f"{t.day} {bulan[t.month - 1]} {t.year}"

    bulan_map = {
        "January": "Januari", "February": "Februari", "March": "Maret",
        "April": "April", "May": "Mei", "June": "Juni",
        "July": "Juli", "August": "Agustus", "September": "September",
        "October": "Oktober", "November": "November", "December": "Desember"
    }

    try:
        t = datetime.strptime(str(tanggal_str), "%Y-%m-%d")
        bulan = [
            "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"
        ]
        return f"{t.day} {bulan[t.month - 1]} {t.year}"
    except Exception:
        pass

    try:
        parts = str(tanggal_str).split()
        if len(parts) == 3:
            day = parts[0]
            month_en = parts[1]
            year = parts[2]
            month_id = bulan_map.get(month_en, month_en)
            return f"{day} {month_id} {year}"
    except Exception:
        pass

    return str(tanggal_str)


def format_angka_id(value, decimals=2):
    if value in ("", None):
        return ""

    try:
        angka = float(value)
    except (TypeError, ValueError):
        return str(value)

    teks = f"{angka:.{decimals}f}".rstrip("0").rstrip(".")
    return teks.replace(".", ",")


def ambil_tahun_pengujian(data):
    for key in ["tanggal_pengujian", "tanggal", "tanggal_penera"]:
        value = data.get(key)

        if isinstance(value, datetime):
            return value.year

        if value:
            try:
                return datetime.strptime(str(value), "%Y-%m-%d").year
            except Exception:
                pass

            try:
                parts = str(value).split()
                if len(parts) == 3:
                    return int(parts[-1])
            except Exception:
                pass

    return datetime.now().year


def generate_sertifikat_meter_air_pdf(data, filename):
    width, height = A4
    c = canvas.Canvas(filename, pagesize=A4)

    # =========================================================
    # MARGIN - SAMA DENGAN SERTIFIKAT TIMBANGAN JEMBATAN
    # =========================================================
    margin_old = 1.5 * cm
    margin_left_content = 3.0 * cm
    right_limit_content = width - margin_old
    right_limit_old = width - margin_old

    y = height - 1.2 * cm

    # =========================================================
    # WATERMARK HALAMAN 1
    # =========================================================
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

    # =========================================================
    # LOGO KOP
    # =========================================================
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

    # =========================================================
    # KOP SURAT
    # =========================================================
    offset = 0.4 * cm
    center_x = width / 2 + offset

    c.setFont("Helvetica", 14)
    c.drawCentredString(
        center_x,
        y,
        "PEMERINTAH KABUPATEN TANGERANG"
    )
    y -= 0.8 * cm

    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(
        center_x,
        y,
        "DINAS PERINDUSTRIAN DAN PERDAGANGAN"
    )
    y -= 0.45 * cm

    c.setFont("Helvetica", 10)
    alamat_kop = (
        "Jl. Atik Soewardi, Gedung Usaha-Usaha Daerah Lt. 3 "
        "Tigaraksa, Tangerang, Banten 15720"
    )
    c.drawCentredString(center_x, y, alamat_kop)
    y -= 0.45 * cm

    c.drawCentredString(
        center_x,
        y,
        "Laman: disperindag.tangerangkab.go.id  "
        "Pos-el: disperindag@tangerangkab.go.id"
    )
    y -= 0.35 * cm

    c.setLineWidth(2)
    c.line(margin_old, y, right_limit_old, y)
    y -= 0.1 * cm

    c.setLineWidth(0.8)
    c.line(margin_old, y, right_limit_old, y)
    y -= 0.8 * cm

    # =========================================================
    # JUDUL & NOMOR
    # =========================================================
    nomor_sertifikat = data.get("nomor_sertifikat", "")

    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(
        width / 2,
        y,
        "SURAT KETERANGAN HASIL PENGUJIAN"
    )
    y -= 0.45 * cm

    c.setFont("Helvetica-Oblique", 12)
    c.drawCentredString(
        width / 2,
        y,
        "Verification Report"
    )
    y -= 0.45 * cm

    c.setFont("Helvetica", 12)
    c.drawCentredString(
        width / 2,
        y,
        f"Nomor : {nomor_sertifikat}"
    )
    y -= 0.9 * cm

    # =========================================================
    # POSISI KOLOM
    # =========================================================
    left_col_x = margin_left_content
    right_col_x = margin_left_content + 7.5 * cm

    label_left = [
        "Nomor Order",
        "Nama Alat",
        "Merek / Buatan",
        "Model / Tipe",
        "Nomor Seri",
        "Pemilik",
        "Alamat",
        "Penera",
        "Hasil",
        "Berlaku sampai",
        "Catatan"
    ]

    max_width_left = max(
        c.stringWidth(lbl, "Helvetica", 12)
        for lbl in label_left
    )

    colon_x_fixed = (
        left_col_x
        + max_width_left
        + 0.5 * cm
    )

    label_right = [
        "Kapasitas",
        "Diameter Nominal",
        "Kelas"
    ]

    max_width_right = max(
        c.stringWidth(lbl, "Helvetica", 12)
        for lbl in label_right
    )

    colon_right_fixed = (
        right_col_x
        + max_width_right
        + 0.5 * cm
    )

    special_offset = 1.2 * cm
    colon_special = colon_x_fixed + special_offset
    line_spacing = 0.45 * cm

    # =========================================================
    # NOMOR ORDER
    # =========================================================
    c.setFont("Helvetica", 12)
    c.drawString(left_col_x, y, "Nomor Order")

    bold_width = c.stringWidth(
        "Nomor Order",
        "Helvetica-Bold",
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
        "Order Number"
    )

    c.setFont("Helvetica", 12)
    c.drawString(colon_special, y, ":")
    c.drawString(
        colon_special + 0.3 * cm,
        y,
        data.get("nomor_order", "")
    )
    y -= 0.9 * cm

    # =========================================================
    # NAMA ALAT
    # =========================================================
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left_col_x, y, "Nama Alat")

    bold_width = c.stringWidth(
        "Nama Alat",
        "Helvetica-Bold",
        12
    )

    c.line(
        left_col_x,
        y - 0.08 * cm,
        left_col_x + bold_width,
        y - 0.08 * cm
    )

    c.setFont("Helvetica-BoldOblique", 12)
    c.drawString(
        left_col_x,
        y - line_spacing,
        "Measuring Instrument"
    )

    c.setFont("Helvetica-Bold", 12)
    c.drawString(colon_special, y, ":")
    c.drawString(
        colon_special + 0.3 * cm,
        y,
        "Meter Air"
    )
    y -= 1.0 * cm

    # =========================================================
    # WRAP OTOMATIS UNTUK MEREK / MODEL / NOMOR SERI
    # =========================================================
    start_x_val = colon_x_fixed + 0.3 * cm
    safe_right = right_col_x - 0.5 * cm
    max_val_width = safe_right - start_x_val

    char_width_val = c.stringWidth(
        "A",
        "Helvetica",
        12
    )

    chars_per_line_val = max(
        10,
        int(max_val_width / char_width_val)
    )

    # =========================================================
    # MEREK / BUATAN + KAPASITAS
    # =========================================================
    y_row = y

    c.setFont("Helvetica", 12)
    c.drawString(
        left_col_x,
        y_row,
        "Merek / Buatan"
    )

    bold_width_left = c.stringWidth(
        "Merek / Buatan",
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
        "Trade Mark /"
    )
    c.drawString(
        left_col_x,
        y_row - 0.90 * cm,
        "Manufactured by"
    )

    c.setFont("Helvetica", 12)
    c.drawString(colon_x_fixed, y_row, ":")

    merek = str(data.get("merek", ""))

    wrapped_merek = textwrap.wrap(
        merek,
        width=chars_per_line_val
    )

    if wrapped_merek:
        c.drawString(
            start_x_val,
            y_row,
            wrapped_merek[0]
        )

        for i, line in enumerate(
            wrapped_merek[1:],
            start=1
        ):
            c.drawString(
                start_x_val,
                y_row - i * 0.45 * cm,
                line
            )

        y_row_kiri = (
            y_row
            - 0.45 * cm
            * (len(wrapped_merek) - 1)
        )
    else:
        y_row_kiri = y_row

    c.setFont("Helvetica", 12)
    c.drawString(
        right_col_x,
        y_row,
        "Kapasitas"
    )

    bold_width_right = c.stringWidth(
        "Kapasitas",
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
        "Capacity"
    )

    c.setFont("Helvetica", 12)
    c.drawString(
        colon_right_fixed,
        y_row,
        ":"
    )
    kapasitas = str(data.get("kapasitas", "")).strip()

    if kapasitas:
        kapasitas = f"{kapasitas} m³/h"

    c.drawString(
        colon_right_fixed + 0.3 * cm,
        y_row,
        kapasitas
    )

    y = min(
        y_row_kiri - 0.5 * cm,
        y_row - 1.3 * cm
    )

    # =========================================================
    # MODEL / TIPE + DIAMETER NOMINAL
    # =========================================================
    y_row = y

    c.setFont("Helvetica", 12)
    c.drawString(
        left_col_x,
        y_row,
        "Model / Tipe"
    )

    bold_width_left = c.stringWidth(
        "Model / Tipe",
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
        "Model / Type"
    )

    c.setFont("Helvetica", 12)
    c.drawString(
        colon_x_fixed,
        y_row,
        ":"
    )

    model = str(
        data.get("model_tipe")
        or data.get("model", "")
    )

    wrapped_model = textwrap.wrap(
        model,
        width=chars_per_line_val
    )

    if wrapped_model:
        c.drawString(
            start_x_val,
            y_row,
            wrapped_model[0]
        )

        for i, line in enumerate(
            wrapped_model[1:],
            start=1
        ):
            c.drawString(
                start_x_val,
                y_row - i * 0.45 * cm,
                line
            )

        y_row_kiri = (
            y_row
            - 0.45 * cm
            * (len(wrapped_model) - 1)
        )
    else:
        y_row_kiri = y_row

    c.setFont("Helvetica", 12)
    c.drawString(
        right_col_x,
        y_row,
        "Diameter Nominal"
    )

    bold_width_right = c.stringWidth(
        "Diameter Nominal",
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
        "Nominal Diameter"
    )

    c.setFont("Helvetica", 12)
    c.drawString(
        colon_right_fixed,
        y_row,
        ":"
    )
    diameter = str(data.get("diameter", "")).strip()

    if diameter:
        diameter = f"{diameter} mm"

    c.drawString(
        colon_right_fixed + 0.3 * cm,
        y_row,
        diameter
    )

    y = min(
        y_row_kiri - 0.5 * cm,
        y_row - 1.3 * cm
    )

    # =========================================================
    # NOMOR SERI + KELAS
    # =========================================================
    y_row = y

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
        data.get("nomor_seri")
        or data.get("no_seri", "")
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
            - 0.45 * cm
            * (len(wrapped_seri) - 1)
        )
    else:
        y_row_kiri = y_row

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

    y = min(
        y_row_kiri - 0.5 * cm,
        y_row - 1.3 * cm
    )

    # =========================================================
    # PEMILIK / ALAMAT / PENERA
    # =========================================================
    colon_fixed_shifted = (
        colon_x_fixed
        + special_offset
    )

    # Pemilik
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left_col_x, y, "Pemilik")

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

    c.setFont("Helvetica-BoldOblique", 12)
    c.drawString(
        left_col_x,
        y - line_spacing,
        "User"
    )

    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        colon_fixed_shifted,
        y,
        ":"
    )
    c.drawString(
        colon_fixed_shifted + 0.3 * cm,
        y,
        str(data.get("pemilik", ""))
    )
    y -= 1.0 * cm

    # Alamat
    c.setFont("Helvetica", 12)
    c.drawString(left_col_x, y, "Alamat")

    bold_width = c.stringWidth(
        "Alamat",
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
        "Address"
    )

    c.setFont("Helvetica", 12)
    c.drawString(
        colon_fixed_shifted,
        y,
        ":"
    )

    max_width_alamat = (
        right_limit_content
        - colon_fixed_shifted
        - 0.3 * cm
    )

    char_width = c.stringWidth(
        "a",
        "Helvetica",
        12
    )

    chars_per_line = (
        int(max_width_alamat / char_width)
        if char_width > 0
        else 40
    )

    alamat = str(data.get("alamat", ""))
    wrapped_lines = textwrap.wrap(
        alamat,
        width=chars_per_line
    )

    if wrapped_lines:
        start_x = colon_fixed_shifted + 0.3 * cm
        line_height = 0.45 * cm

        c.drawString(
            start_x,
            y,
            wrapped_lines[0]
        )

        for i, line in enumerate(
            wrapped_lines[1:],
            start=1
        ):
            c.drawString(
                start_x,
                y - i * line_height,
                line
            )

        y -= (
            line_height * (len(wrapped_lines) - 1)
            + 0.9 * cm
        )
    else:
        y -= 0.6 * cm

    # Penera
    c.setFont("Helvetica", 12)
    c.drawString(left_col_x, y, "Penera")

    bold_width_penera = c.stringWidth(
        "Penera",
        "Helvetica",
        12
    )

    c.line(
        left_col_x,
        y - 0.08 * cm,
        left_col_x + bold_width_penera,
        y - 0.08 * cm
    )

    c.setFont("Helvetica-Oblique", 12)
    c.drawString(
        left_col_x,
        y - line_spacing,
        "Calibration Technician"
    )

    c.setFont("Helvetica", 12)
    c.drawString(
        colon_fixed_shifted,
        y,
        ":"
    )

    penera_text = (
        f"{data.get('nama_penera', '')} "
        f"/ NIP. {data.get('nip_penera', '')}"
    )

    c.drawString(
        colon_fixed_shifted + 0.3 * cm,
        y,
        penera_text
    )
    y -= 1.0 * cm

    # =========================================================
    # HASIL
    # =========================================================
    c.setFont("Helvetica", 12)
    c.drawString(left_col_x, y, "Hasil")

    bold_width = c.stringWidth(
        "Hasil",
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
        "Results"
    )

    c.setFont("Helvetica", 12)
    c.drawString(
        colon_fixed_shifted,
        y,
        ":"
    )

    start_x = colon_fixed_shifted + 0.3 * cm

    jenis_pengujian = (
        data.get("keterangan")
        or data.get("jenis_pengujian")
        or "Tera Ulang"
    )

    tahun_tera = ambil_tahun_pengujian(data)

    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        start_x,
        y,
        f"Disahkan untuk {jenis_pengujian} Tahun {tahun_tera}"
    )

    c.setFont("Helvetica", 12)
    y -= 0.45 * cm

    c.drawString(
        start_x,
        y,
        "Berdasarkan Undang - Undang RI No. 2 Tahun 1981"
    )

    y -= 0.45 * cm

    c.drawString(
        start_x,
        y,
        "Tentang Metrologi Legal"
    )

    y -= 0.6 * cm

    # =========================================================
    # BERLAKU SAMPAI
    # =========================================================
    c.setFont("Helvetica", 12)
    c.drawString(
        left_col_x,
        y,
        "Berlaku sampai"
    )

    bold_width = c.stringWidth(
        "Berlaku sampai",
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
        "This report due to"
    )

    berlaku_str = (
        data.get("masa_berlaku_indonesia")
        or format_tanggal_indonesia(
            data.get("masa_berlaku")
            or data.get("berlaku_sampai", "")
        )
    )

    c.setFont("Helvetica", 12)
    c.drawString(
        colon_fixed_shifted,
        y,
        ":"
    )

    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        colon_fixed_shifted + 0.3 * cm,
        y,
        berlaku_str
    )

    c.setFont("Helvetica", 12)
    y -= 1.0 * cm

    # =========================================================
    # CATATAN
    # =========================================================
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

    start_x = colon_fixed_shifted + 0.3 * cm
    bullet = "•"
    tahun = str(tahun_tera)[-2:]

    if jenis_pengujian == "Tera":
        c.drawString(
            start_x,
            y,
            "Pembubuhan Tanda Tera :"
        )
        y -= 0.45 * cm

        c.drawString(
            start_x,
            y,
            f"{bullet} Tanda Daerah D4, Tanda Pegawai Berhak H dan Tanda"
        )
        y -= 0.45 * cm

        c.drawString(
            start_x,
            y,
            f'  Tera Sah SL4 "{tahun}" pada lemping yang dililit dengan kawat'
        )
        y -= 0.45 * cm

        c.drawString(
            start_x,
            y,
            "  yang disegel dengan Tanda Jaminan JP8"
        )
        y -= 0.45 * cm

        c.drawString(
            start_x,
            y,
            f"{bullet} Tanda Jaminan JP8 pada bagian yang dapat menjadi"
        )
        y -= 0.45 * cm

        c.drawString(
            start_x,
            y,
            "  potensi di lakukan perubahan yang mempengaruhi"
        )
        y -= 0.45 * cm

        c.drawString(
            start_x,
            y,
            "  karakteristik kemetrologiannya"
        )

    else:
        c.drawString(
            start_x,
            y,
            "Pembubuhan Tanda Tera Ulang :"
        )
        y -= 0.45 * cm

        c.drawString(
            start_x,
            y,
            f'{bullet} Tanda Tera SAH SP6 "{tahun}" pada Alat Justir'
        )
        y -= 0.45 * cm

        c.drawString(
            start_x,
            y,
            f"{bullet} Tanda Jaminan JP8 pada bagian yang dapat menjadi"
        )
        y -= 0.45 * cm

        c.drawString(
            start_x,
            y,
            "  potensi di lakukan perubahan yang mempengaruhi"
        )
        y -= 0.45 * cm

        c.drawString(
            start_x,
            y,
            "  karakteristik kemetrologiannya"
        )

    y -= 0.9 * cm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        start_x,
        y,
        "Dilarang Memutus Segel Tera tanpa sepengetahuan"
    )
    y -= 0.45 * cm

    c.drawString(
        start_x,
        y,
        "Unit Metrologi Legal"
    )
    y -= 0.9 * cm

    # =========================================================
    # TANDA TANGAN HALAMAN 1
    # =========================================================
    x_right_align = width - margin_old - 10 * cm

    c.setFont("Helvetica", 12)
    c.drawString(
        x_right_align,
        y,
        f"Tangerang, {format_tanggal_indonesia(data.get('tanggal_sertifikat', ''))}"
    )
    y -= 0.9 * cm

    c.drawString(
        x_right_align,
        y,
        "A.n Kepala Dinas Perindustrian dan Perdagangan"
    )
    y -= 0.45 * cm

    c.drawString(
        x_right_align,
        y,
        "Kabupaten Tangerang"
    )
    y -= 0.45 * cm

    c.drawString(
        x_right_align,
        y,
        "Kepala Bidang Kemetrologian"
    )
    y -= 2.0 * cm

    c.drawString(
        x_right_align,
        y,
        "Priatin Saputra, S.Kom.,M.Si"
    )
    y -= 0.45 * cm

    c.drawString(
        x_right_align,
        y,
        "Penata Tk.I (III/d)"
    )
    y -= 0.45 * cm

    c.drawString(
        x_right_align,
        y,
        "NIP. 198505152011011004"
    )

    # =========================================================
    # FOOTER HALAMAN 1
    # =========================================================
    c.setLineWidth(0.5)

    c.line(
        margin_old,
        1.8 * cm,
        right_limit_old,
        1.8 * cm
    )

    c.setFillGray(0)
    c.setFont(
        "Helvetica-Oblique",
        10
    )

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
        "Halaman 1 dari 2"
    )

    # =========================================================
    # HALAMAN 2
    # =========================================================
    c.showPage()
    y = height - margin_old

    c.setFillGray(0)
    c.setFont(
        "Helvetica-Oblique",
        10
    )

    c.drawRightString(
        right_limit_old,
        y,
        f"Lampiran Sertifikat Nomor : {nomor_sertifikat}"
    )

    y -= 1.8 * cm

    # =========================================================
    # SPESIFIKASI TEKNIS STANDAR
    # =========================================================
    left_col_x = margin_left_content

    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        left_col_x,
        y,
        "SPESIFIKASI TEKNIS STANDAR"
    )
    y -= 0.45 * cm

    c.setFont("Helvetica-Oblique", 12)
    c.drawString(
        left_col_x,
        y,
        "Standard Technical Specification"
    )
    y -= 0.9 * cm

    c.setFont("Helvetica", 12)
    c.drawString(
        left_col_x,
        y,
        "Perangkat Standar Water Meter Test Bench"
    )
    y -= 0.45 * cm


    # Posisi khusus untuk data perangkat standar
    x_label_standar = left_col_x + 1.5 * cm
    x_colon_standar = left_col_x + 5.5 * cm
    x_value_standar = x_colon_standar + 0.3 * cm


    # Merek / Buatan
    c.drawString(
        x_label_standar,
        y,
        "Merek / Buatan"
    )

    c.drawString(
        x_colon_standar,
        y,
        ":"
    )

    c.drawString(
        x_value_standar,
        y,
        str(
            data.get("standar_merek")
            or data.get("bejana_merek", "")
        )
    )

    y -= 0.45 * cm


    # Telusuran
    c.drawString(
        x_label_standar,
        y,
        "Telusuran"
    )

    c.drawString(
        x_colon_standar,
        y,
        ":"
    )

    c.drawString(
        x_value_standar,
        y,
        str(
            data.get(
                "standar_telusuran",
                "Direktorat Metrologi"
            )
        )
    )

    y -= 0.9 * cm

    # =========================================================
    # KONDISI PENGUJIAN
    # =========================================================
    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        left_col_x,
        y,
        "KONDISI PENGUJIAN"
    )
    y -= 0.45 * cm

    c.setFont("Helvetica-Oblique", 12)
    c.drawString(
        left_col_x,
        y,
        "Condition of Verification"
    )
    y -= 0.9 * cm

    labels = [
        "- Lokasi",
        "- Suhu ruangan",
        "- Kelembaban relatif",
        "- Tanggal"
    ]

    max_label_width = max(
        c.stringWidth(
            label,
            "Helvetica",
            12
        )
        for label in labels
    )

    x_bullet = left_col_x + 0.6 * cm
    x_colon_cond = (
        x_bullet
        + max_label_width
        + 0.2 * cm
    )
    x_value_cond = (
        x_colon_cond
        + 0.3 * cm
    )

    c.setFont("Helvetica", 12)

    c.drawString(
        left_col_x + 0.3 * cm,
        y,
        "1. Pengujian dilakukan dalam ruangan dengan kondisi sebagai berikut :"
    )
    y -= 0.45 * cm

    c.drawString(
        x_bullet,
        y,
        "- Lokasi"
    )
    c.drawString(
        x_colon_cond,
        y,
        ":"
    )

    lokasi_pengujian = str(
        data.get(
            "lokasi_pengujian",
            ""
        )
    ).strip()


    if lokasi_pengujian == "Dalam Kantor":
        lokasi_nilai = (
            "Unit Metrologi Legal Kabupaten Tangerang"
        )

    else:
        lokasi_nilai = str(
            data.get(
                "pemilik",
                ""
            )
        ).strip()

    c.drawString(
        x_value_cond,
        y,
        str(lokasi_nilai)
    )
    y -= 0.45 * cm

    c.drawString(
        x_bullet,
        y,
        "- Suhu ruangan"
    )
    c.drawString(
        x_colon_cond,
        y,
        ":"
    )
    c.drawString(
        x_value_cond,
        y,
        str(data.get("suhu", "Ambient"))
    )
    y -= 0.45 * cm

    c.drawString(
        x_bullet,
        y,
        "- Kelembaban relatif"
    )
    c.drawString(
        x_colon_cond,
        y,
        ":"
    )
    c.drawString(
        x_value_cond,
        y,
        str(data.get("kelembaban", "Ambient"))
    )
    y -= 0.45 * cm

    c.drawString(
        x_bullet,
        y,
        "- Tanggal"
    )
    c.drawString(
        x_colon_cond,
        y,
        ":"
    )

    tanggal_nilai = (
        data.get("tanggal_penera")
        or format_tanggal_indonesia(
            data.get("tanggal_pengujian")
            or data.get("tanggal", "")
        )
    )

    c.drawString(
        x_value_cond,
        y,
        str(tanggal_nilai)
    )
    y -= 0.45 * cm

    c.setFont("Helvetica", 12)

    c.drawString(
        left_col_x + 0.3 * cm,
        y,
        "2. Metode yang digunakan membandingkan langsung dengan standar ("
    )

    normal_width = c.stringWidth(
        "2. Metode yang digunakan membandingkan langsung dengan standar (",
        "Helvetica",
        12
    )

    x_italic = (
        left_col_x
        + 0.3 * cm
        + normal_width
    )

    # Baris pertama: Direct
    c.setFont("Helvetica-Oblique", 12)
    c.drawString(
        x_italic,
        y,
        "Direct"
    )

    # Baris kedua: Comparison)
    y -= 0.45 * cm

    c.setFont("Helvetica-Oblique", 12)
    c.drawString(
        left_col_x + 0.75 * cm,
        y,
        "Comparison)"
    )

    y -= 0.85 * cm

    # =========================================================
    # TABEL HASIL PENGUJIAN - 3 BARIS
    # =========================================================
    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        left_col_x,
        y,
        "HASIL PENGUJIAN"
    )
    y -= 0.45 * cm

    c.setFont("Helvetica-Oblique", 12)
    c.drawString(
        left_col_x,
        y,
        "Verification Results"
    )
    y -= 0.45 * cm

    x_kiri = left_col_x
    x_no_kanan = left_col_x + 1.5 * cm
    x_kecepatan_kiri = x_no_kanan + 0.2 * cm
    x_kecepatan_kanan = x_kecepatan_kiri + 4.2 * cm
    x_kesalahan_kiri = x_kecepatan_kanan + 0.3 * cm

    c.setFont("Helvetica-Bold", 12)

    lebar_kesalahan = c.stringWidth(
        "Kesalahan (%)",
        "Helvetica-Bold",
        12
    )

    x_kesalahan_kanan = (
        x_kesalahan_kiri
        + lebar_kesalahan
        + 0.8 * cm
    )

    x_akhir = x_kesalahan_kanan

    y_header = y

    c.line(
        x_kiri,
        y_header,
        x_akhir,
        y_header
    )

    y_center_no = y_header - 0.6 * cm

    c.drawCentredString(
        x_kiri
        + (x_no_kanan - x_kiri) / 2,
        y_center_no,
        "No."
    )

    y_line1 = y_header - 0.4 * cm
    y_line2 = y_header - 0.8 * cm

    x_kecepatan_tengah = (
        x_kecepatan_kiri
        + (x_kecepatan_kanan - x_kecepatan_kiri) / 2
    )

    c.drawCentredString(
        x_kecepatan_tengah,
        y_line1,
        "Kecepatan Alir"
    )

    c.drawCentredString(
        x_kecepatan_tengah,
        y_line2,
        "(m³/h)"
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
        "(%)"
    )

    y_line_bawah_header = y_header - 1.0 * cm

    c.line(
        x_kiri,
        y_line_bawah_header,
        x_akhir,
        y_line_bawah_header
    )

    hasil_pengujian = (
        data.get("hasil_pengujian", [])
        or []
    )

    jumlah_baris = 3
    tinggi_baris = 0.55 * cm
    padding_vertikal = 0.1 * cm

    y_data = (
        y_line_bawah_header
        - padding_vertikal
        - tinggi_baris
    )

    c.setFont("Helvetica", 12)

    for i in range(3):
        if i < len(hasil_pengujian):
            res = hasil_pengujian[i]

            kecepatan_lh = res.get(
                "kecepatan_alir",
                ""
            )

            if kecepatan_lh in ("", None):
                kecepatan_m3h = ""
            else:
                try:
                    kecepatan_m3h = (
                        float(kecepatan_lh)
                        / 1000.0
                    )
                except Exception:
                    kecepatan_m3h = kecepatan_lh

            kesalahan = res.get(
                "kesalahan_meter_air",
                ""
            )

            kecepatan_text = (
                format_angka_id(
                    kecepatan_m3h,
                    3
                )
            )

            kesalahan_text = (
                format_angka_id(
                    kesalahan,
                    2
                )
            )

        else:
            kecepatan_text = ""
            kesalahan_text = ""

        c.drawCentredString(
            x_kiri
            + (x_no_kanan - x_kiri) / 2,
            y_data,
            f"{i + 1}."
        )

        c.drawCentredString(
            x_kecepatan_tengah,
            y_data,
            kecepatan_text
        )

        c.drawCentredString(
            x_kes_tengah,
            y_data,
            kesalahan_text
        )

        y_data -= tinggi_baris

    y_bottom = (
        y_line_bawah_header
        - padding_vertikal
        - jumlah_baris * tinggi_baris
        - padding_vertikal
    )

    c.line(
        x_kiri,
        y_bottom,
        x_akhir,
        y_bottom
    )

    c.line(
        x_kiri,
        y_header,
        x_kiri,
        y_bottom
    )

    c.line(
        x_no_kanan,
        y_header,
        x_no_kanan,
        y_bottom
    )

    c.line(
        x_kecepatan_kanan,
        y_header,
        x_kecepatan_kanan,
        y_bottom
    )

    c.line(
        x_akhir,
        y_header,
        x_akhir,
        y_bottom
    )

    y = y_bottom - 1.8 * cm

    # =========================================================
    # KETERANGAN
    # =========================================================
    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        left_col_x,
        y,
        "Keterangan :"
    )
    y -= 0.45 * cm

    c.drawString(
        left_col_x,
        y,
        "Penunjukan sebenarnya : Penunjukan Alat - Kesalahan"
    )
    y -= 1.8 * cm

    # =========================================================
    # TANDA TANGAN PENERA HALAMAN 2
    # =========================================================
    x_right_align = width - margin_old - 10 * cm

    c.setFont("Helvetica", 12)
    c.drawString(
        x_right_align,
        y,
        "Pegawai Berhak,"
    )
    y -= 2.0 * cm

    nama_penera = data.get(
        "nama_penera",
        ""
    )

    nip_penera = data.get(
        "nip_penera",
        ""
    )

    golongan_penera = data.get(
        "golongan_penera",
        ""
    )

    c.drawString(
        x_right_align,
        y,
        str(nama_penera)
    )
    y -= 0.45 * cm

    if golongan_penera:
        c.drawString(
            x_right_align,
            y,
            str(golongan_penera)
        )
        y -= 0.45 * cm

    c.drawString(
        x_right_align,
        y,
        f"NIP. {nip_penera}"
    )

    # =========================================================
    # FOOTER HALAMAN 2
    # =========================================================
    c.setLineWidth(0.5)

    c.line(
        margin_old,
        1.8 * cm,
        right_limit_old,
        1.8 * cm
    )

    c.setFillGray(0)
    c.setFont(
        "Helvetica-Oblique",
        10
    )

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


# Alias opsional
generate_sertifikat_pdf = generate_sertifikat_meter_air_pdf
