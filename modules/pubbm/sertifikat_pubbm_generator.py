from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import ImageReader
from datetime import datetime
from pathlib import Path
import pandas as pd
import os
import textwrap

BASE_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = BASE_DIR / "assets"

WATERMARK_PATH = ASSETS_DIR / "logo_metrologi.png"
LOGO_PATH = ASSETS_DIR / "logo.png"

def tambah_satu_tahun(tanggal):
    """
    Menambah 1 tahun dari tanggal pengujian.
    Contoh: 27 Januari 2026 -> 27 Januari 2027
    """
    if isinstance(tanggal, str):
        try:
            tanggal = datetime.strptime(tanggal, "%Y-%m-%d")
        except:
            return tanggal

    try:
        return tanggal.replace(year=tanggal.year + 1)
    except ValueError:
        # Untuk kasus 29 Februari
        return tanggal.replace(month=2, day=28, year=tanggal.year + 1)
def format_tanggal(tanggal):
    if not tanggal:
        return ""

    try:
        if isinstance(tanggal, str):
            tanggal = datetime.strptime(tanggal, "%Y-%m-%d")

        bulan = [
            "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"
        ]

        return f"{tanggal.day} {bulan[tanggal.month - 1]} {tanggal.year}"

    except Exception:
        return str(tanggal)
def draw_watermark(c, width, height):
    if WATERMARK_PATH.exists():
        try:
            wm = ImageReader(str(WATERMARK_PATH))
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
            print(f"Error watermark PUBBM: {e}")
    else:
        print(f"Watermark PUBBM tidak ditemukan: {WATERMARK_PATH}")

def draw_header(c, width, height):
    margin_old = 1.5 * cm
    right_limit_old = width - margin_old

    y = height - 1.2 * cm

    # ========================
    # LOGO KOP SURAT
    # ========================
    if LOGO_PATH.exists():
        try:
            logo = ImageReader(str(LOGO_PATH))
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
            print(f"Error logo kop PUBBM: {e}")
    else:
        print(f"Logo PUBBM tidak ditemukan: {LOGO_PATH}")
    # ========================
    # TEKS KOP SURAT
    # ========================
    offset = 0.4 * cm
    center_x = width / 2 + offset

    c.setFont("Helvetica", 14)
    c.drawCentredString(center_x, y, "PEMERINTAH KABUPATEN TANGERANG")
    y -= 0.8 * cm

    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(center_x, y, "DINAS PERINDUSTRIAN DAN PERDAGANGAN")
    y -= 0.45 * cm

    c.setFont("Helvetica", 10)
    c.drawCentredString(
        center_x,
        y,
        "Jl. Atik Soewardi, Gedung Usaha-Usaha Daerah Lt. 3 Tigaraksa, Tangerang, Banten 15720"
    )
    y -= 0.45 * cm

    c.drawCentredString(
        center_x,
        y,
        "Laman: disperindag.tangerangkab.go.id  Pos-el: disperindag@tangerangkab.go.id"
    )
    y -= 0.35 * cm

    # ========================
    # GARIS GANDA
    # ========================
    c.setLineWidth(2)
    c.line(margin_old, y, right_limit_old, y)

    y -= 0.1 * cm

    c.setLineWidth(0.8)
    c.line(margin_old, y, right_limit_old, y)

    return y


def draw_footer(c, width, page_text):
    margin_old = 1.5 * cm
    right_limit_old = width - margin_old

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
        page_text
    )


def label_value(c, x_label, x_colon, x_value, y, label, sublabel, value):
    c.setFont("Helvetica", 10)
    c.drawString(x_label, y, label)

    c.setFont("Helvetica-Oblique", 9)
    c.drawString(x_label, y - 0.33 * cm, sublabel)

    c.setFont("Helvetica", 10)
    c.drawString(x_colon, y, ":")

    c.setFont("Helvetica-Bold" if label in ["Nama Alat", "Pemilik", "Hasil"] else "Helvetica", 10)

    if "\n" in str(value):
        lines = str(value).split("\n")
        for i, line in enumerate(lines):
            c.drawString(x_value, y - (i * 0.35 * cm), line)
    else:
        c.drawString(x_value, y, str(value))
def draw_wrapped_bullet_text(c, text, x, y, max_width, font_name="Helvetica", font_size=9, leading=0.36*cm):
    """
    Menggambar teks catatan dengan bullet rapi.
    Jika kalimat panjang turun ke baris berikutnya,
    baris lanjutan akan menjorok sejajar setelah bullet.
    """
    c.setFont(font_name, font_size)

    bullet_indent = 0.35 * cm
    line_indent = 0.45 * cm

    lines = text.split("\n")

    for line in lines:
        line = line.strip()

        if not line:
            y -= leading
            continue

        # Judul catatan, contoh: Pembubuhan Tanda Tera Ulang :
        if not line.startswith("•"):
            c.setFont("Helvetica-Bold", font_size)
            c.drawString(x, y, line)
            c.setFont(font_name, font_size)
            y -= leading
            continue

        # Kalau baris bullet
        bullet = "•"
        isi = line.replace("•", "", 1).strip()

        c.drawString(x, y, bullet)

        words = isi.split()
        current_line = ""

        available_width_first = max_width - line_indent
        available_width_next = max_width - line_indent

        first_line = True

        for word in words:
            test_line = word if current_line == "" else current_line + " " + word

            if c.stringWidth(test_line, font_name, font_size) <= available_width_first:
                current_line = test_line
            else:
                if first_line:
                    c.drawString(x + line_indent, y, current_line)
                    first_line = False
                else:
                    c.drawString(x + line_indent, y, current_line)

                y -= leading
                current_line = word

        if current_line:
            c.drawString(x + line_indent, y, current_line)

        y -= leading

    return y
def draw_halaman_1_pubbm(c, width, height, data):
    # ===== MARGIN =====
    margin_old = 1.5 * cm
    margin_left_content = 3.0 * cm
    right_limit_content = width - margin_old
    right_limit_old = width - margin_old

    y = height - 1.2 * cm

    # ======================== WATERMARK + HEADER ========================
    draw_watermark(c, width, height)
    y = draw_header(c, width, height)
    y -= 0.8 * cm
    # ======================== JUDUL & NOMOR ========================
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(width / 2, y, "SURAT KETERANGAN HASIL PENGUJIAN")
    y -= 0.45 * cm

    c.setFont("Helvetica-Oblique", 12)
    c.drawCentredString(width / 2, y, "Verification Report")
    y -= 0.45 * cm

    c.setFont("Helvetica", 12)
    c.drawCentredString(width / 2, y, f"Nomor : {data.get('nomor_sertifikat', '')}")
    y -= 0.9 * cm

    # ======================== POSISI KOLOM ========================
    left_col_x = margin_left_content

    label_left = [
        "Nomor Order",
        "Nama Alat",
        "Pemilik",
        "Alamat",
        "Penera",
        "Tanggal Pengujian",
        "Hasil",
        "Berlaku sampai",
        "Catatan"
    ]

    max_width_left = max(c.stringWidth(lbl, "Helvetica", 12) for lbl in label_left)
    colon_x_fixed = left_col_x + max_width_left + 0.5 * cm
    colon_fixed_shifted = colon_x_fixed + 1.0 * cm

    line_spacing = 0.45 * cm

    def draw_wrapped_text(text, x, y_start, max_width, font_name="Helvetica", font_size=12, line_height=0.45 * cm):
        c.setFont(font_name, font_size)

        char_width = c.stringWidth("a", font_name, font_size)
        chars_per_line = int(max_width / char_width) if char_width > 0 else 60
        chars_per_line = max(chars_per_line, 20)

        lines = []
        for raw_line in str(text).split("\n"):
            wrapped = textwrap.wrap(raw_line, width=chars_per_line)
            if wrapped:
                lines.extend(wrapped)
            else:
                lines.append("")

        for i, line in enumerate(lines):
            c.drawString(x, y_start - i * line_height, line)

        return y_start - (len(lines) - 1) * line_height

    def draw_field(label, sublabel, value, y, bold_label=False, bold_value=False, value_font_size=12):
        label_font = "Helvetica-Bold" if bold_label else "Helvetica"
        sublabel_font = "Helvetica-BoldOblique" if bold_label else "Helvetica-Oblique"
        value_font = "Helvetica-Bold" if bold_value else "Helvetica"

        c.setFont(label_font, 12)
        c.drawString(left_col_x, y, label)

        underline_width = c.stringWidth(label, label_font, 12)
        c.line(left_col_x, y - 0.08 * cm, left_col_x + underline_width, y - 0.08 * cm)

        c.setFont(sublabel_font, 12)
        c.drawString(left_col_x, y - line_spacing, sublabel)

        c.setFont(label_font if bold_label else "Helvetica", 12)
        c.drawString(colon_fixed_shifted, y, ":")

        start_x = colon_fixed_shifted + 0.3 * cm
        max_width_value = right_limit_content - start_x

        y_low = draw_wrapped_text(
            value,
            start_x,
            y,
            max_width_value,
            font_name=value_font,
            font_size=value_font_size
        )

        return min(y_low - 0.5 * cm, y - 0.9 * cm)

    # ======================== ISI HALAMAN 1 PUBBM ========================

    # Nomor Order
    y = draw_field(
        "Nomor Order",
        "Order Number",
        data.get("nomor_order", ""),
        y
    )

    # Nama Alat
    y = draw_field(
        "Nama Alat",
        "Measuring Instrument",
        data.get("nama_alat", "Pompa Ukur BBM (Dispenser)"),
        y,
        bold_label=True,
        bold_value=True
    )

    # Pemilik
    y = draw_field(
        "Pemilik",
        "User",
        data.get("pemilik", ""),
        y,
        bold_label=True,
        bold_value=True
    )

    # Alamat
    y = draw_field(
        "Alamat",
        "Address",
        data.get("alamat", ""),
        y
    )
     
    # Tambahan jarak setelah alamat agar tidak terlalu rapat ke Penera
    y -= 0.20 * cm

    # Penera
    c.setFont("Helvetica", 12)
    c.drawString(left_col_x, y, "Penera")
    underline_width = c.stringWidth("Penera", "Helvetica", 12)
    c.line(left_col_x, y - 0.08 * cm, left_col_x + underline_width, y - 0.08 * cm)

    c.setFont("Helvetica-Oblique", 12)
    c.drawString(left_col_x, y - line_spacing, "Calibration Technician")

    c.setFont("Helvetica", 12)
    c.drawString(colon_fixed_shifted, y, ":")

    start_x = colon_fixed_shifted + 0.3 * cm
    max_width_penera = right_limit_content - start_x

    penera_lines = []

    if data.get("penera_1"):
        penera_lines.append(
            f"{data.get('penera_1', '')} / NIP. {data.get('nip_penera_1', '')}"
        )

    if data.get("jumlah_penera") == 2 and data.get("penera_2"):
        penera_lines.append(
            f"{data.get('penera_2', '')} / NIP. {data.get('nip_penera_2', '')}"
        )

    font_size_penera = 12

    for idx, penera_text in enumerate(penera_lines):
        c.setFont("Helvetica", font_size_penera)

        # Jika masih terlalu panjang, kecilkan font sedikit agar tetap satu baris
        while (
            c.stringWidth(penera_text, "Helvetica", font_size_penera) > max_width_penera
            and font_size_penera > 9
        ):
            font_size_penera -= 0.25
            c.setFont("Helvetica", font_size_penera)

        c.drawString(
            start_x,
            y - (idx * 0.45 * cm),
            penera_text
        )

    if len(penera_lines) > 1:
        y -= 1.15 * cm
    else:
        y -= 0.9 * cm

    # Tanggal Pengujian
    y = draw_field(
        "Tanggal Pengujian",
        "Date Of Verification",
        format_tanggal(data.get("tanggal_pengujian", "")),
        y
    )

    # Hasil
    tanggal_pengujian = data.get(
        "tanggal_pengujian",
        ""
    )

    try:
        if isinstance(
            tanggal_pengujian,
            str
        ):
            tanggal_obj = datetime.strptime(
                tanggal_pengujian,
                "%Y-%m-%d"
            )
        else:
            tanggal_obj = tanggal_pengujian

        tahun_pengujian = (
            tanggal_obj.year
        )

    except Exception:
        tahun_pengujian = (
            datetime.now().year
        )

    jenis_pengujian = data.get("jenis_pengujian", "Tera Ulang")
    hasil_pengujian = f"Disahkan untuk {jenis_pengujian} Tahun {tahun_pengujian}"

    c.setFont("Helvetica", 12)
    c.drawString(left_col_x, y, "Hasil")
    underline_width = c.stringWidth("Hasil", "Helvetica", 12)
    c.line(left_col_x, y - 0.08 * cm, left_col_x + underline_width, y - 0.08 * cm)

    c.setFont("Helvetica-Oblique", 12)
    c.drawString(left_col_x, y - line_spacing, "Results")

    c.setFont("Helvetica", 12)
    c.drawString(colon_fixed_shifted, y, ":")

    start_x = colon_fixed_shifted + 0.3 * cm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(start_x, y, hasil_pengujian)

    c.setFont("Helvetica", 12)
    y -= 0.45 * cm
    c.drawString(start_x, y, "Berdasarkan Undang - Undang RI No. 2 Tahun 1981")
    y -= 0.45 * cm
    c.drawString(start_x, y, "Tentang Metrologi Legal")
    y -= 0.65 * cm

    # Berlaku sampai
    berlaku_sampai = tambah_satu_tahun(data.get("tanggal_pengujian"))

    c.setFont("Helvetica", 12)
    c.drawString(left_col_x, y, "Berlaku sampai")
    underline_width = c.stringWidth("Berlaku sampai", "Helvetica", 12)
    c.line(left_col_x, y - 0.08 * cm, left_col_x + underline_width, y - 0.08 * cm)

    c.setFont("Helvetica-Oblique", 12)
    c.drawString(left_col_x, y - line_spacing, "This report due to")

    c.setFont("Helvetica", 12)
    c.drawString(colon_fixed_shifted, y, ":")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(colon_fixed_shifted + 0.3 * cm, y, format_tanggal(berlaku_sampai))
    y -= 1.0 * cm

    # Catatan
    c.setFont("Helvetica", 12)
    c.drawString(left_col_x, y, "Catatan")
    underline_width = c.stringWidth("Catatan", "Helvetica", 12)
    c.line(left_col_x, y - 0.08 * cm, left_col_x + underline_width, y - 0.08 * cm)

    c.setFont("Helvetica-Oblique", 12)
    c.drawString(left_col_x, y - line_spacing, "Note")

    c.setFont("Helvetica", 12)
    c.drawString(colon_fixed_shifted, y, ":")

    start_x = colon_fixed_shifted + 0.3 * cm
    max_width_catatan = right_limit_content - start_x

    catatan = buat_catatan_pubbm(data)

    y_cat = draw_wrapped_bullet_text(
        c,
        catatan,
        start_x,
        y,
        max_width=max_width_catatan,
        font_name="Helvetica",
        font_size=12,
        leading=0.45 * cm
    )

    y = y_cat - 0.5 * cm

    # Dilarang memutus segel
    c.setFont("Helvetica-Bold", 12)
    c.drawString(start_x, y, "Dilarang Memutus Segel Tera tanpa sepengetahuan")
    y -= 0.45 * cm
    c.drawString(start_x, y, "Unit Metrologi Legal")
    y -= 0.75 * cm

    # ======================== TANDA TANGAN HALAMAN 1 ========================
    x_right_align = width - margin_old - 10 * cm

    c.setFont("Helvetica", 12)
    c.drawString(
        x_right_align,
        y,
        f"Tangerang, {format_tanggal(data.get('tanggal_cetak', ''))}"
    )
    y -= 0.9 * cm

    c.drawString(x_right_align, y, "A.n Kepala Dinas Perindustrian dan Perdagangan")
    y -= 0.45 * cm
    c.drawString(x_right_align, y, "Kabupaten Tangerang")
    y -= 0.45 * cm
    c.drawString(x_right_align, y, "Kepala Bidang Kemetrologian")
    y -= 2.0 * cm

    c.drawString(x_right_align, y, "Priatin Saputra, S.Kom.,M.Si")
    y -= 0.45 * cm
    c.drawString(x_right_align, y, "Penata Tk.I (III/d)")
    y -= 0.45 * cm
    c.drawString(x_right_align, y, "NIP. 198505152011011004")

    # ======================== FOOTER HALAMAN 1 ========================
    draw_footer(c, width, "Halaman 1 dari 2")

def buat_catatan_pubbm(data):
    tanggal_pengujian = data.get(
        "tanggal_pengujian",
        ""
    )

    jenis_pengujian = data.get(
        "jenis_pengujian",
        "Tera Ulang"
    )

    try:
        if isinstance(
            tanggal_pengujian,
            str
        ):
            tanggal_obj = datetime.strptime(
                tanggal_pengujian,
                "%Y-%m-%d"
            )
        else:
            tanggal_obj = tanggal_pengujian

        tahun_tanda = str(
            tanggal_obj.year
        )[-2:]

    except Exception:
        tahun_tanda = (
            datetime.now()
            .strftime("%y")
        )

    bullet = "•"

    # ========================================================
    # TERA
    # ========================================================
    if jenis_pengujian == "Tera":
        return (
            "Pembubuhan Tanda Tera :\n"
            f"{bullet} Tanda Daerah D4, Tanda Pegawai Berhak H, "
            f"Tanda Sah Logam SL4 dibubuhkan pada Lemping Tera "
            f"yang disegel dengan Tanda Jaminan JP8.\n"

            f'{bullet} Tanda Tera Sah SP6 "{tahun_tanda}" '
            f"dibubuhkan pada Badan Hitung.\n"

            f'{bullet} Tanda Tera Sah SP6 "{tahun_tanda}" '
            f"dan/atau Tanda Jaminan JP8 dibubuhkan pada Alat Justir.\n"

            f"{bullet} Tanda Jaminan JP8 dibubuhkan pada Badan Ukur, "
            f"Transduser/Pulser, dan/atau penghubung antara "
            f"Badan Ukur dengan Badan Hitung."
        )


    # ========================================================
    # TERA ULANG
    # ========================================================
    return (
        "Pembubuhan Tanda Tera Ulang :\n"

        f'{bullet} Tanda Tera Ulang SAH SP6 "{tahun_tanda}" '
        f"dibubuhkan pada Lemping Tera/segel.\n"

        f'{bullet} Tanda Tera Ulang SAH SP6 "{tahun_tanda}" '
        f"dibubuhkan pada Badan Hitung/Perangkat Penunjuk.\n"

        f'{bullet} Tanda Tera Ulang SAH SP6 "{tahun_tanda}" '
        f"dan/atau Tanda Jaminan JP8 dibubuhkan pada Alat Justir.\n"

        f"{bullet} Tanda Jaminan JP8 dibubuhkan pada Badan Ukur/Assy Meter, "
        f"Transduser/Pulser, dan/atau penghubung antara "
        f"Badan Ukur dengan Badan Hitung."
    )

def tinggi_baris_by_font(jumlah_baris, font_size):
    if jumlah_baris < 1:
        jumlah_baris = 1

    leading = leading_by_font(font_size)

    font_height = {
        11: 0.39 * cm,
        10: 0.35 * cm,
        9: 0.32 * cm,
        8: 0.28 * cm,
        7: 0.25 * cm,
        6: 0.22 * cm,
    }.get(
        font_size,
        0.22 * cm
    )

    top_padding = 0.22 * cm
    bottom_padding = 0.22 * cm

    return (
        top_padding
        + font_height
        + (
            (jumlah_baris - 1)
            * leading
        )
        + bottom_padding
    )


def leading_by_font(font_size):
    leading_cm = {
        11: 0.50,
        10: 0.46,
        9: 0.42,
        8: 0.38,
        7: 0.34,
        6: 0.30,
    }

    return (
        leading_cm.get(
            font_size,
            0.30
        )
        * cm
    )


def pilih_font_tabel(
    rows,
    available_table_height,
    header_total
):
    for font_size in [
        11,
        10,
        9,
        8,
        7,
        6,
    ]:
        total_rows_height = sum(
            tinggi_baris_by_font(
                row.get(
                    "jumlah_baris",
                    1
                ),
                font_size
            )
            for row in rows
        )

        total_table_height = (
            header_total
            + total_rows_height
        )

        if (
            total_table_height
            <= available_table_height
        ):
            return font_size

    return 6

def generate_sertifikat_pubbm(data, output_path="sertifikat_pubbm.pdf"):
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4

    # =========================
    # HALAMAN 1
    # =========================
    draw_halaman_1_pubbm(c, width, height, data)
    c.showPage()
    # =========================
    # HALAMAN 2
    # =========================
    margin_old = 1.5 * cm
    right_limit_old = width - margin_old

    y = height - 1.5 * cm

    # ======================== HEADER HALAMAN 2 ========================
    c.setFillGray(0)
    c.setFont("Helvetica-Oblique", 10)
    c.drawRightString(
        right_limit_old,
        y,
        f"Lampiran Sertifikat Nomor : {data.get('nomor_sertifikat', '')}"
    )

    y -= 1.8 * cm

    # ========================
    # PERANGKAT BEJANA UKUR STANDAR
    # ========================
    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        2.2 * cm,
        y,
        "Perangkat Bejana Ukur Standar"
    )

    y -= 0.65 * cm

    alat_standar_df = data.get(
        "alat_standar"
    )

    if (
        alat_standar_df is not None
        and isinstance(
            alat_standar_df,
            pd.DataFrame
        )
        and not alat_standar_df.empty
    ):
        # Dua alat standar dalam satu baris
        posisi_x = [
            2.2 * cm,
            10.5 * cm,
        ]

        lebar_label = 2.6 * cm
        jarak_titik_dua = 0.25 * cm
        tinggi_satu_baris_alat = 2.25 * cm

        daftar_alat = list(
            alat_standar_df.iterrows()
        )

        for nomor_index, (_, alat) in enumerate(
            daftar_alat
        ):
            nomor_alat = nomor_index + 1

            kolom = nomor_index % 2
            baris = nomor_index // 2

            x_awal = posisi_x[
                kolom
            ]

            y_alat = (
                y
                - (
                    baris
                    * tinggi_satu_baris_alat
                )
            )

            merk = str(
                alat.get(
                    "Merk",
                    ""
                )
                or ""
            ).strip()

            nomor_seri = str(
                alat.get(
                    "Nomor Seri",
                    ""
                )
                or ""
            ).strip()

            telusuran = str(
                alat.get(
                    "Telusuran",
                    ""
                )
                or ""
            ).strip()

            if merk.lower() == "nan":
                merk = ""

            if nomor_seri.lower() == "nan":
                nomor_seri = ""

            if telusuran.lower() == "nan":
                telusuran = ""

            if nomor_seri.endswith(".0"):
                nomor_seri = nomor_seri[:-2]

            c.setFont(
                "Helvetica-Bold",
                11
            )

            c.drawString(
                x_awal,
                y_alat,
                f"Alat Standar {nomor_alat}"
            )

            y_isian = (
                y_alat
                - 0.45 * cm
            )

            c.setFont(
                "Helvetica",
                11
            )

            # Merek / Buatan
            c.drawString(
                x_awal,
                y_isian,
                "Merek / Buatan"
            )

            c.drawString(
                x_awal + lebar_label,
                y_isian,
                ":"
            )

            c.drawString(
                x_awal
                + lebar_label
                + jarak_titik_dua,
                y_isian,
                merk
            )

            y_isian -= 0.4 * cm

            # Nomor Seri
            c.drawString(
                x_awal,
                y_isian,
                "Nomor Seri"
            )

            c.drawString(
                x_awal + lebar_label,
                y_isian,
                ":"
            )

            c.drawString(
                x_awal
                + lebar_label
                + jarak_titik_dua,
                y_isian,
                nomor_seri
            )

            y_isian -= 0.4 * cm

            # Telusuran
            c.drawString(
                x_awal,
                y_isian,
                "Telusuran"
            )

            c.drawString(
                x_awal + lebar_label,
                y_isian,
                ":"
            )

            c.drawString(
                x_awal
                + lebar_label
                + jarak_titik_dua,
                y_isian,
                telusuran
            )

        jumlah_baris_alat = (
            len(alat_standar_df) + 1
        ) // 2

        y -= (
            jumlah_baris_alat
            * tinggi_satu_baris_alat
        )

    else:
        # ==========================================
        # FALLBACK DATA LAMA: HANYA SATU BUS
        # ==========================================
        c.setFont(
            "Helvetica",
            11
        )

        c.drawString(
            2.2 * cm,
            y,
            "Merek / Buatan"
        )

        c.drawString(
            5.0 * cm,
            y,
            ":"
        )

        c.drawString(
            5.4 * cm,
            y,
            str(
                data.get(
                    "merk_bus",
                    ""
                )
            )
        )

        y -= 0.45 * cm

        c.drawString(
            2.2 * cm,
            y,
            "Nomor Seri"
        )

        c.drawString(
            5.0 * cm,
            y,
            ":"
        )

        c.drawString(
            5.4 * cm,
            y,
            str(
                data.get(
                    "nomor_seri_bus",
                    ""
                )
            )
        )

        y -= 0.45 * cm

        c.drawString(
            2.2 * cm,
            y,
            "Telusuran"
        )

        c.drawString(
            5.0 * cm,
            y,
            ":"
        )

        c.drawString(
            5.4 * cm,
            y,
            str(
                data.get(
                    "telusuran_bus",
                    ""
                )
            )
        )

        y -= 0.65 * cm

    # Jarak ke judul tabel
    y -= 0.25 * cm

        # ======================== JUDUL TABEL ========================
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(width / 2, y, "DAFTAR POMPA UKUR BBM")
    y -= 0.6 * cm


    # ======================== FUNGSI BANTU TABEL MANUAL ========================
    from reportlab.pdfbase import pdfmetrics

    def draw_center_text(c, text, x, y, w, h, font_name="Helvetica", font_size=10):
        c.setFont(font_name, font_size)

        text = str(text) if text is not None else ""

        text_width = c.stringWidth(text, font_name, font_size)
        text_x = x + (w - text_width) / 2

        # Hitung posisi vertikal agar benar-benar tengah
        ascent = pdfmetrics.getAscent(font_name) / 1000 * font_size
        descent = pdfmetrics.getDescent(font_name) / 1000 * font_size

        text_y = y + (h - ascent - descent) / 2 - descent - 4

        c.drawString(text_x, text_y, text)


    def draw_multiline_center(c, text, x, y, w, h, font_name="Helvetica", font_size=9, leading=11):
        c.setFont(font_name, font_size)

        text = str(text) if text is not None else ""

        lines = text.split("\n")
        total_text_height = len(lines) * leading

        # Offset -4 untuk menurunkan isi teks dalam sel
        start_y = y + (h + total_text_height) / 2 - font_size - 1

        for line in lines:
            text_width = c.stringWidth(line, font_name, font_size)
            text_x = x + (w - text_width) / 2
            c.drawString(text_x, start_y, line)
            start_y -= leading


    def wrap_merk(text):
        text = "" if text is None else str(text)
        parts = text.split()

        if len(parts) <= 1:
            return text

        # Contoh: "TOMINAGA JEPANG" menjadi 2 baris
        if len(text) > 12:
            tengah = len(parts) // 2
            return " ".join(parts[:tengah]) + "\n" + " ".join(parts[tengah:])

        return text

    def wrap_teks_kolom(text, max_chars):
        text = "" if text is None else str(text).strip()

        if not text:
            return ""

        wrapped = textwrap.wrap(
            text,
            width=max_chars
        )

        return "\n".join(wrapped)

    def count_lines(text):
        text = "" if text is None else str(text).strip()
        if not text:
            return 1
        return len(text.split("\n"))
        
        # ======================== DATA TABEL ========================
    dispenser_df = data.get("dispenser")

    rows = []

    if dispenser_df is not None and not dispenser_df.empty:
        dispenser_df = dispenser_df.copy()

        dispenser_df["No"] = pd.to_numeric(dispenser_df["No"], errors="coerce")

        # Posisi jangan diubah ke angka karena bisa berisi 1.1, 1.2, A1, 3.4, dst.
        dispenser_df["Posisi"] = dispenser_df["Posisi"].fillna("").astype(str)

        dispenser_df = dispenser_df.dropna(subset=["No"])
        dispenser_df = dispenser_df.sort_values(["No"])

        for no_disp, group in dispenser_df.groupby("No", sort=True):
            posisi_text = "\n".join(
                group["Posisi"].fillna("").astype(str).tolist()
            )

            media_text = "\n".join(
                group["Media"].fillna("").astype(str).tolist()
            )

            merk = group["Merk"].fillna("").astype(str).iloc[0]
            tipe = group["Tipe"].fillna("").astype(str).iloc[0]
            no_seri = group["No. Seri"].fillna("").astype(str).iloc[0]
            
            jumlah_nozzle = max(
                1,
                len(group)
            )

            merk_text = wrap_merk(
                merk
            )

            tipe_text = wrap_teks_kolom(
                tipe,
                14
            )

            no_seri_text = wrap_teks_kolom(
                no_seri,
                11
            )

            jumlah_baris = max(
                jumlah_nozzle,
                count_lines(posisi_text),
                count_lines(merk_text),
                count_lines(tipe_text),
                count_lines(no_seri_text),
                count_lines(media_text),
                1
            )

            rows.append({
                "no": f"{int(no_disp)}.",
                "posisi": posisi_text,
                "merk": merk_text,
                "tipe": tipe_text,
                "no_seri": no_seri_text,
                "media": media_text,
                "jumlah_nozzle": jumlah_nozzle,
                "jumlah_baris": jumlah_baris
            })

        # ======================== UKURAN TABEL ========================
    table_x = 2.0 * cm
    table_y_top = y

    col_widths = [
        1.1 * cm,   # NO
        2.0 * cm,   # POSISI
        3.0 * cm,   # MERK
        3.4 * cm,   # TYPE
        2.6 * cm,   # NO. SERI
        4.6 * cm,   # MEDIA
    ]

    total_width = sum(col_widths)

    x_no = table_x
    x_posisi = x_no + col_widths[0]
    x_merk = x_posisi + col_widths[1]
    x_type = x_merk + col_widths[2]
    x_seri = x_type + col_widths[3]
    x_media = x_seri + col_widths[4]

    header_h1 = 0.65 * cm
    header_h2 = 0.65 * cm
    header_total = header_h1 + header_h2

    footer_top_y = 1.8 * cm
    ruang_tanda_tangan = 3.8 * cm
    jarak_aman = 0.4 * cm

    table_bottom_limit = footer_top_y + ruang_tanda_tangan + jarak_aman
    available_table_height = table_y_top - table_bottom_limit

    table_font_size = pilih_font_tabel(
        rows,
        available_table_height,
        header_total
    )

    header_font_size = table_font_size
    table_leading = leading_by_font(table_font_size)

    row_heights = [
        tinggi_baris_by_font(row.get("jumlah_baris", 1), table_font_size)
        for row in rows
    ]

    c.setLineWidth(0.7)

    # ======================== HEADER TABEL ========================
    header_y = table_y_top - header_total

    c.rect(table_x, header_y, total_width, header_total)

    c.line(x_posisi, header_y, x_posisi, header_y + header_total)
    c.line(x_merk, header_y, x_merk, header_y + header_total)
    c.line(x_type, header_y, x_type, header_y + header_total)
    c.line(x_media, header_y, x_media, header_y + header_total)

    # Batas TYPE | NO. SERI hanya untuk header bawah
    c.line(x_seri, header_y, x_seri, header_y + header_h2)

    # Garis horizontal BODY
    c.line(x_type, header_y + header_h2, x_media, header_y + header_h2)

    draw_center_text(c, "NO", x_no, header_y, col_widths[0], header_total, "Helvetica-Bold", header_font_size)
    draw_center_text(c, "POSISI", x_posisi, header_y, col_widths[1], header_total, "Helvetica-Bold", header_font_size)
    draw_center_text(c, "MEREK", x_merk, header_y, col_widths[2], header_total, "Helvetica-Bold", header_font_size)

    draw_center_text(
        c,
        "BODY",
        x_type,
        header_y + header_h2,
        col_widths[3] + col_widths[4],
        header_h1,
        "Helvetica-Bold",
        header_font_size
    )

    draw_center_text(c, "TYPE", x_type, header_y, col_widths[3], header_h2, "Helvetica-Bold", header_font_size)
    draw_center_text(c, "NO. SERI", x_seri, header_y, col_widths[4], header_h2, "Helvetica-Bold", header_font_size)
    draw_center_text(c, "MEDIA", x_media, header_y, col_widths[5], header_total, "Helvetica-Bold", header_font_size)

    # ======================== BARIS ISI ========================
    current_y = header_y

    for idx, row in enumerate(rows):
        row_h = row_heights[idx]
        row_y = current_y - row_h

        c.rect(table_x, row_y, total_width, row_h)

        x_current = table_x
        for w_col in col_widths[:-1]:
            x_current += w_col
            c.line(x_current, row_y, x_current, row_y + row_h)

        draw_center_text(
            c,
            row["no"],
            x_no,
            row_y,
            col_widths[0],
            row_h,
            "Helvetica",
            table_font_size
        )

        draw_multiline_center(
            c,
            row["posisi"],
            x_posisi,
            row_y,
            col_widths[1],
            row_h,
            "Helvetica",
            table_font_size,
            leading=table_leading
        )

        draw_multiline_center(
            c,
            row["merk"],
            x_merk,
            row_y,
            col_widths[2],
            row_h,
            "Helvetica",
            table_font_size,
            leading=table_leading
        )

        draw_multiline_center(
            c,
            row["tipe"],
            x_type,
            row_y,
            col_widths[3],
            row_h,
            "Helvetica",
            table_font_size,
            leading=table_leading
        )

        draw_multiline_center(
            c,
            row["no_seri"],
            x_seri,
            row_y,
            col_widths[4],
            row_h,
            "Helvetica",
            table_font_size,
            leading=table_leading
        )

        draw_multiline_center(
            c,
            row["media"],
            x_media,
            row_y,
            col_widths[5],
            row_h,
            "Helvetica",
            table_font_size,
            leading=table_leading
        )

        current_y = row_y

    # ======================== TANDA TANGAN PEGAWAI BERHAK ========================
    y = current_y - 0.7 * cm

    x_ttd = 11.2 * cm

    c.setFont("Helvetica", 12)
    c.drawString(x_ttd, y, "Pegawai Berhak,")
    y -= 1.7 * cm

    c.drawString(x_ttd, y, data.get("penera_1", ""))
    y -= 0.4 * cm

    c.drawString(x_ttd, y, data.get("golongan_penera_1", ""))
    y -= 0.4 * cm

    c.drawString(x_ttd, y, f"NIP. {data.get('nip_penera_1', '')}")

    draw_footer(c, width, "Halaman 2 dari 2")

    c.save()
    return output_path
