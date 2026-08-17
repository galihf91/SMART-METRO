from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import ImageReader
from datetime import datetime, date
from pathlib import Path
import pandas as pd
import textwrap

def find_assets_dir():
    current = Path(__file__).resolve()

    # Cari folder assets dari lokasi file generator naik ke folder induk
    for parent in [current.parent] + list(current.parents):
        assets = parent / "assets"
        if assets.exists():
            return assets

    # fallback
    return Path("assets")

ASSETS_DIR = find_assets_dir()

LOGO_PATH = ASSETS_DIR / "logo.png"
WATERMARK_PATH = ASSETS_DIR / "logo_metrologi.png"

BULAN_ID = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"
]


def format_tanggal(tanggal, upper=False):
    if not tanggal:
        return ""
    try:
        if isinstance(tanggal, str):
            try:
                tanggal = datetime.strptime(tanggal, "%Y-%m-%d")
            except ValueError:
                tanggal = datetime.fromisoformat(tanggal)
        hasil = f"{tanggal.day} {BULAN_ID[tanggal.month - 1]} {tanggal.year}"
        return hasil.upper() if upper else hasil
    except Exception:
        hasil = str(tanggal)
        return hasil.upper() if upper else hasil


def safe_text(value):
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value)


def draw_wrapped_lines(c, text, x, y, max_width, font="Helvetica", size=9.2, leading=0.32 * cm):
    c.setFont(font, size)
    lines_out = []
    for raw in safe_text(text).split("\n"):
        if not raw.strip():
            lines_out.append("")
            continue
        avg = max(c.stringWidth("abcdefghijklmnopqrstuvwxyz", font, size) / 26, 1)
        width = max(int(max_width / avg), 20)
        lines_out.extend(textwrap.wrap(raw, width=width) or [""])

    for i, line in enumerate(lines_out):
        c.drawString(x, y - i * leading, line)
    return y - max(len(lines_out), 1) * leading


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
            print("Logo gagal dimuat:", e)
    else:
        print("Logo tidak ditemukan:", LOGO_PATH)

    # ========================
    # TEKS KOP SURAT
    # ========================
    offset = 0.4 * cm
    center_x = width / 2 + offset

    c.setFillColor(colors.black)

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

    # Jarak setelah kop, sama seperti PUBBM/Timbangan sebelum judul
    y -= 0.8 * cm

    return y


def draw_watermark(c, width, height):
    if WATERMARK_PATH.exists():
        try:
            wm = ImageReader(str(WATERMARK_PATH))

            c.saveState()
            c.setFillAlpha(0.13)

            wm_width = 13.0 * cm
            wm_height = 13.0 * cm

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
            print("Watermark gagal dimuat:", e)
    else:
        print("Watermark tidak ditemukan:", WATERMARK_PATH)


def draw_footer(c, width,page_text=""):
    margin_old = 1.5 * cm
    right_limit_old = width - margin_old

    c.setFillColor(colors.black)
    c.setLineWidth(0.5)
    c.line(margin_old, 1.8 * cm, right_limit_old, 1.8 * cm)

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

    if page_text:
        c.drawRightString(
            right_limit_old,
            0.9 * cm,
            page_text
        )


def draw_label(
    c,
    x_label,
    x_colon,
    x_value,
    y,
    label,
    sublabel,
    value,
    max_width,
    bold_value=False,
    size=11
):
    sub_y = y - 0.42 * cm
    leading = 0.42 * cm

    c.setFillColor(colors.black)

    # Label Indonesia
    c.setFont("Helvetica", size)
    c.drawString(x_label, y, label)

    underline_width = c.stringWidth(label, "Helvetica", size)
    c.line(
        x_label,
        y - 0.07 * cm,
        x_label + underline_width,
        y - 0.07 * cm
    )

    # Label Inggris, bisa multiline
    c.setFont("Helvetica-Oblique", size)
    for i, line in enumerate(safe_text(sublabel).split("\n")):
        c.drawString(x_label, sub_y - i * 0.36 * cm, line)
    # Titik dua
    c.setFont("Helvetica", size)
    c.drawString(x_colon, y, ":")

    # Nilai
    font_value = "Helvetica-Bold" if bold_value else "Helvetica"

    y_after = draw_wrapped_lines(
        c,
        value,
        x_value,
        y,
        max_width,
        font=font_value,
        size=size,
        leading=leading
    )

    # Minimal turun 0.9 cm agar label dan sublabel berikutnya tidak nabrak
    jumlah_baris_sublabel = max(1, len(safe_text(sublabel).split("\n")))
    minimal_turun = 0.90 * cm + ((jumlah_baris_sublabel - 1) * 0.36 * cm)
    
    return min(y_after, y - minimal_turun)

def build_penera_text(data):
    lines = []
    if data.get("penera_1"):
        lines.append(f"{data.get('penera_1', '')} / NIP. {data.get('nip_penera_1', '')}")
    if data.get("jumlah_penera") == 2 and data.get("penera_2"):
        lines.append(f"{data.get('penera_2', '')} / NIP. {data.get('nip_penera_2', '')}")
    return "\n".join(lines)


def df_to_rows(df_like):
    if df_like is None:
        return []
    if isinstance(df_like, pd.DataFrame):
        df = df_like.copy()
    else:
        try:
            df = pd.DataFrame(df_like)
        except Exception:
            return []
    if df.empty:
        return []
    rows = []
    for _, row in df.iterrows():
        rows.append([
            safe_text(row.get("UNIT", "")),
            safe_text(row.get("TEGANGAN", "")),
            safe_text(row.get("ARUS", "")),
            safe_text(row.get("PHS", "")),
            safe_text(row.get("KLS", "")),
            safe_text(row.get("KONST", "")),
        ])
    return rows


def draw_kwh_table(c, data, x, y):
    rows = [["UNIT", "TEGANGAN", "ARUS", "PHS", "KLS", "KONST"]]
    data_rows = df_to_rows(data.get("kwh_meter"))
    rows.extend(data_rows if data_rows else [["", "", "", "", "", ""]])

    col_widths = [1.6 * cm, 2.65 * cm, 2.55 * cm, 1.35 * cm, 1.35 * cm, 2.85 * cm]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    tw, th = table.wrapOn(c, 100, y)
    table.drawOn(c, x, y - th)
    return y - th


def draw_bullet(c, text, x, y, max_width, size=11, leading=0.46 * cm):
    c.setFont("Helvetica", size)

    bullet_indent = 0.45 * cm

    avg = max(
        c.stringWidth("abcdefghijklmnopqrstuvwxyz", "Helvetica", size) / 26,
        1
    )

    chars = max(
        int((max_width - bullet_indent) / avg),
        25
    )

    wrapped = textwrap.wrap(safe_text(text), width=chars)

    if not wrapped:
        return y

    c.drawString(x, y, "•")
    c.drawString(x + bullet_indent, y, wrapped[0])

    for i, line in enumerate(wrapped[1:], start=1):
        c.drawString(
            x + bullet_indent,
            y - i * leading,
            line
        )

    # Turun sesuai jumlah baris bullet
    return y - len(wrapped) * leading


def draw_sertifikat_satu_halaman(c, data, width, height):
    y = draw_header(c, width, height)
    draw_watermark(c, width, height)

    # ======================== JUDUL & NOMOR ========================
    c.setFillColor(colors.black)

    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width / 2, y, "SURAT KETERANGAN HASIL PENGUJIAN")
    y -= 0.45 * cm

    c.setFont("Helvetica-Oblique", 11)
    c.drawCentredString(width / 2, y, "Verification Report")
    y -= 0.45 * cm

    c.setFont("Helvetica", 11)
    c.drawCentredString(width / 2, y, f"Nomor : {data.get('nomor_sertifikat', '')}")
    y -= 0.9 * cm

    # Margin isi sertifikat disamakan dengan PUBBM
    margin = 3.0 * cm

    x_label = margin
    x_colon = 7.25 * cm
    x_value = x_colon + 0.35 * cm

    right_margin = 1.5 * cm
    value_width = width - x_value - right_margin

        # ========================
    # BARIS 1: NAMA ALAT + NOMOR ORDER SEJAJAR
    # ========================
    y_row = y

    # ---------- KIRI: Nama Alat ----------
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x_label, y_row, "Nama Alat")

    label_w = c.stringWidth("Nama Alat", "Helvetica-Bold", 11)
    c.line(x_label, y_row - 0.08 * cm, x_label + label_w, y_row - 0.08 * cm)

    c.setFont("Helvetica-BoldOblique", 11)
    c.drawString(x_label, y_row - 0.45 * cm, "Measuring Instrument")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(x_colon, y_row, ":")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(x_value, y_row, safe_text(data.get("nama_alat", "kWh Meter")))


    # ---------- KANAN: Nomor Order ----------
    x_order_label = 11.3 * cm
    x_order_colon = 14.0 * cm
    x_order_value = 14.35 * cm

    c.setFont("Helvetica", 11)
    c.drawString(x_order_label, y_row, "Nomor Order")
    label_w = c.stringWidth("Nomor Order", "Helvetica", 11)
    c.line(x_order_label, y_row - 0.08 * cm, x_order_label + label_w, y_row - 0.08 * cm)

    c.setFont("Helvetica-Oblique", 11)
    c.drawString(x_order_label, y_row - 0.45 * cm, "Order Number")

    c.setFont("Helvetica", 11)
    c.drawString(x_order_colon, y_row, ":")

    c.setFont("Helvetica", 11)
    c.drawString(x_order_value, y_row, safe_text(data.get("nomor_order", "")))

    # Turun setelah baris sejajar
    y = y_row - 1.25 * cm

    # ========================
    # MERK / BUATAN
    # ========================
    merk_buatan = safe_text(data.get("merk_buatan", ""))

    y = draw_label(
        c,
        x_label,
        x_colon,
        x_value,
        y,
        "Merk / Buatan",
        "Trade Mark /\nManufactured by",
        merk_buatan,
        value_width,
        bold_value=False,
        size=11
    )
    y -= 0.34 * cm


    # ========================
    # MODEL / TIPE
    # ========================
    model_tipe = safe_text(data.get("model_tipe", ""))

    y = draw_label(
        c,
        x_label,
        x_colon,
        x_value,
        y,
        "Model / Tipe",
        "Model / Type",
        model_tipe,
        value_width,
        bold_value=False,
        size=11
    )
    y -= 0.34 * cm

        # ========================
    # PEMILIK
    # ========================
    pemilik_text = safe_text(data.get("pemilik", ""))
    alamat = safe_text(data.get("alamat", ""))
    untuk = safe_text(data.get("untuk_pengguna", ""))

    gabungan_pemilik = pemilik_text

    if alamat:
        gabungan_pemilik += "\n" + alamat

    if untuk:
        if untuk.strip().lower().startswith("untuk"):
            gabungan_pemilik += "\n" + untuk
        else:
            gabungan_pemilik += "\nUntuk " + untuk

    # ========================
    # PEMILIK
    # ========================
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x_label, y, "Pemilik")
    
    underline_width = c.stringWidth("Pemilik", "Helvetica-Bold", 11)
    c.line(x_label, y - 0.07 * cm, x_label + underline_width, y - 0.07 * cm)
    
    c.setFont("Helvetica-BoldOblique", 11)
    c.drawString(x_label, y - 0.42 * cm, "User")
    
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x_colon, y, ":")
    
    line_height = 0.42 * cm
    
    # Isi Pemilik tetap sejajar aturan x_value dan dibatasi margin kanan
    max_width_pemilik = width - x_value - right_margin
    
    y_after_pemilik = draw_wrapped_lines(
        c,
        gabungan_pemilik,
        x_value,
        y,
        max_width_pemilik,
        font="Helvetica-Bold",
        size=11,
        leading=line_height
    )
    
    y = min(y_after_pemilik, y - 0.95 * cm)
    y -= 0.34 * cm

    # ========================
    # PENERA
    # ========================
    y = draw_label(
        c,
        x_label,
        x_colon,
        x_value,
        y,
        "Penera",
        "Verification Officer",
        build_penera_text(data),
        value_width,
        size=11
    )
    y -= 0.42 * cm


    # ========================
    # TABEL KWH METER
    # ========================
    table_width = (
        1.6 * cm +
        2.65 * cm +
        2.55 * cm +
        1.35 * cm +
        1.35 * cm +
        2.85 * cm
    )

    table_x = (
        width - table_width
    ) / 2

    y = draw_kwh_table(
        c,
        data,
        table_x,
        y
    )

    y -= 0.70 * cm

    # ========================
    # HASIL
    # ========================
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

        tahun_pengujian = tanggal_obj.year

    except Exception:
        tahun_pengujian = datetime.now().year

    jenis_pengujian = data.get("jenis_pengujian", "Tera")
    hasil_pengujian = data.get("hasil_text") or f"Disahkan untuk {jenis_pengujian} Tahun {tahun_pengujian}"

    c.setFont("Helvetica", 11)
    c.drawString(x_label, y, "Hasil")
    underline_width = c.stringWidth("Hasil", "Helvetica", 11)
    c.line(x_label, y - 0.06 * cm, x_label + underline_width, y - 0.06 * cm)

    c.setFont("Helvetica-Oblique", 11)
    c.drawString(x_label, y - 0.45 * cm, "Results")

    c.setFont("Helvetica", 11)
    c.drawString(x_colon, y, ":")

    start_x = x_value

    c.setFont("Helvetica-Bold", 11)
    c.drawString(start_x, y, hasil_pengujian)

    c.setFont("Helvetica", 11)
    y -= 0.58 * cm
    c.drawString(start_x, y, "Berdasarkan Undang-Undang RI Nomor 2 Tahun 1981")
    y -= 0.42 * cm
    c.drawString(start_x, y, "Tentang Metrologi Legal")
    y -= 0.62 * cm


    # ========================
    # BERLAKU SAMPAI
    # ========================
    c.setFont("Helvetica", 11)
    c.drawString(x_label, y, "Berlaku sampai")
    underline_width = c.stringWidth("Berlaku sampai", "Helvetica", 11)
    c.line(x_label, y - 0.06 * cm, x_label + underline_width, y - 0.06 * cm)

    c.setFont("Helvetica-Oblique", 11)
    c.drawString(x_label, y - 0.45 * cm, "This report due to")

    c.setFont("Helvetica", 11)
    c.drawString(x_colon, y, ":")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(
        x_value,
        y,
        format_tanggal(data.get("berlaku_sampai", ""), upper=True)
    )

    y -= 0.98 * cm


    # ========================
    # CATATAN
    # ========================
    c.setFont("Helvetica", 11)
    c.drawString(x_label, y, "Catatan")
    underline_width = c.stringWidth("Catatan", "Helvetica", 11)
    c.line(x_label, y - 0.06 * cm, x_label + underline_width, y - 0.06 * cm)

    c.setFont("Helvetica-Oblique", 11)
    c.drawString(x_label, y - 0.45 * cm, "Note")

    c.setFont("Helvetica", 11)
    c.drawString(x_colon, y, ":")

    start_x = x_colon + 0.25 * cm
    max_width_catatan = width - start_x - 1.5 * cm

    c.setFont("Helvetica", 11)
    c.drawString(start_x, y, f"Pembubuhan Tanda {jenis_pengujian} :")

    y -= 0.50 * cm

    bullets = data.get("catatan_bullets") or [
        "Tanda Pegawai Yang Berhak HP4 dan Tanda Sah SP6 pada baut penutup meter kWh",
        "Tanda Jaminan JP8 pada baut penutup meter kWh yang lain",
    ]

    for bullet in bullets:
        y = draw_bullet(
            c,
            bullet,
            start_x + 0.15 * cm,
            y,
            max_width_catatan - 0.15 * cm,
            size=11,
            leading=0.48 * cm
        )
        y -= 0.18 * cm

    y -= 0.45 * cm


    # ========================
    # DILARANG MEMUTUS SEGEL
    # ========================
    c.setFont("Helvetica-Bold", 11)
    c.drawString(start_x, y, "Dilarang Memutus Segel Tera tanpa sepengetahuan")
    y -= 0.42 * cm
    c.drawString(start_x, y, "Unit Metrologi Legal")
    y -= 0.45 * cm


    # ========================
    # TANDA TANGAN
    # ========================
    # Posisi tanda tangan dibuat seperti PUBBM, berada di kanan dan mengikuti posisi y
    margin_old = 1.5 * cm
    x_right_align = width - margin_old - 10 * cm

    # Kalau posisi y terlalu bawah, naikkan otomatis
    if y < 7.0 * cm:
        y = 7.0 * cm

    c.setFont("Helvetica", 11)
    
    # Geser tanggal sedikit lebih bawah
    y -= 0.35 * cm
    c.drawString(
        x_right_align,
        y,
        f"Tangerang, {format_tanggal(data.get('tanggal_cetak') or data.get('tanggal_pengujian') or date.today())}"
    )
    y -= 0.75 * cm

    c.drawString(x_right_align, y, "A.n Kepala Dinas Perindustrian dan Perdagangan")
    y -= 0.42 * cm

    c.drawString(x_right_align, y, "Kabupaten Tangerang")
    y -= 0.42 * cm

    c.drawString(x_right_align, y, "Kepala Bidang Kemetrologian")
    y -= 1.75 * cm

    c.setFont("Helvetica", 11)
    c.drawString(x_right_align, y, "Priatin Saputra, S.Kom.,M.Si")
    y -= 0.42 * cm

    c.setFont("Helvetica", 11)
    c.drawString(x_right_align, y, "Penata Tk.I (III/d)")
    y -= 0.42 * cm

    c.drawString(x_right_align, y, "NIP. 198505152011011004")

    draw_footer(c, width)


def generate_sertifikat_kwh(data, output_path):
    """Generate SKHP kWh Meter dalam 1 halaman A4."""
    output_path = str(output_path)
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    draw_sertifikat_satu_halaman(c, data, width, height)
    c.save()
    return output_path
