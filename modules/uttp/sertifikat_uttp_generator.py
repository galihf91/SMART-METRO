from datetime import datetime
from pathlib import Path
import textwrap
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


# =========================================================
# PATH PROYEK
# =========================================================
def find_project_root():
    current = Path(__file__).resolve()

    for parent in [current.parent] + list(current.parents):
        if (parent / "assets").exists() or (parent / "modules").exists():
            return parent

    return current.parent


BASE_DIR = find_project_root()
ASSETS_DIR = BASE_DIR / "assets"

WATERMARK_PATH = ASSETS_DIR / "logo_metrologi.png"
LOGO_PATH = ASSETS_DIR / "logo.png"


# =========================================================
# FORMAT DATA
# =========================================================
def parse_tanggal(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return datetime(value.year, value.month, value.day)

    try:
        return datetime.strptime(str(value), "%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def format_tanggal(value):
    tanggal = parse_tanggal(value)

    if tanggal is None:
        return str(value or "")

    bulan = [
        "Januari", "Februari", "Maret", "April",
        "Mei", "Juni", "Juli", "Agustus",
        "September", "Oktober", "November", "Desember",
    ]

    return f"{tanggal.day} {bulan[tanggal.month - 1]} {tanggal.year}"


def tambah_satu_tahun(value):
    tanggal = parse_tanggal(value)

    if tanggal is None:
        return value

    try:
        return tanggal.replace(year=tanggal.year + 1)
    except ValueError:
        return tanggal.replace(
            year=tanggal.year + 1,
            month=2,
            day=28,
        )


def get_tahun_pengujian(data):
    tanggal = parse_tanggal(
        data.get("tanggal_pengujian")
        or data.get("tanggal")
    )

    return tanggal.year if tanggal else datetime.now().year


def get_tahun_tanda(data):
    return str(get_tahun_pengujian(data))[-2:]


def terbilang_indonesia(angka):
    """Mengubah bilangan bulat non-negatif menjadi teks bahasa Indonesia."""
    try:
        angka = int(angka)
    except (TypeError, ValueError):
        return str(angka or "")

    if angka < 0:
        return "minus " + terbilang_indonesia(abs(angka))

    dasar = [
        "", "satu", "dua", "tiga", "empat",
        "lima", "enam", "tujuh", "delapan",
        "sembilan", "sepuluh", "sebelas",
    ]

    if angka < 12:
        return dasar[angka]

    if angka < 20:
        return terbilang_indonesia(angka - 10) + " belas"

    if angka < 100:
        puluhan = angka // 10
        sisa = angka % 10
        hasil = terbilang_indonesia(puluhan) + " puluh"
        if sisa:
            hasil += " " + terbilang_indonesia(sisa)
        return hasil

    if angka < 200:
        sisa = angka - 100
        hasil = "seratus"
        if sisa:
            hasil += " " + terbilang_indonesia(sisa)
        return hasil

    if angka < 1000:
        ratusan = angka // 100
        sisa = angka % 100
        hasil = terbilang_indonesia(ratusan) + " ratus"
        if sisa:
            hasil += " " + terbilang_indonesia(sisa)
        return hasil

    if angka < 2000:
        sisa = angka - 1000
        hasil = "seribu"
        if sisa:
            hasil += " " + terbilang_indonesia(sisa)
        return hasil

    if angka < 1_000_000:
        ribuan = angka // 1000
        sisa = angka % 1000
        hasil = terbilang_indonesia(ribuan) + " ribu"
        if sisa:
            hasil += " " + terbilang_indonesia(sisa)
        return hasil

    if angka < 1_000_000_000:
        jutaan = angka // 1_000_000
        sisa = angka % 1_000_000
        hasil = terbilang_indonesia(jutaan) + " juta"
        if sisa:
            hasil += " " + terbilang_indonesia(sisa)
        return hasil

    return str(angka)


def susun_nama_alat_sertifikat(data):
    """
    Menyusun nama alat halaman 1.
    Contoh:
    10 (sepuluh) Unit Timbangan Elektronik (Terlampir)
    """
    daftar_alat = data.get("daftar_alat_uttp", [])

    if not isinstance(daftar_alat, list):
        daftar_alat = []

    baris = []

    for item in daftar_alat:
        if not isinstance(item, dict):
            continue

        nama = str(item.get("nama_alat", "")).strip()

        try:
            jumlah = int(item.get("jumlah", 0))
        except (TypeError, ValueError):
            jumlah = 0

        if not nama or jumlah <= 0:
            continue

        baris.append(
            f"{jumlah} ({terbilang_indonesia(jumlah)}) "
            f"Unit {nama} (Terlampir)"
        )

    if baris:
        return "\n".join(baris)

    nama_alat = str(data.get("nama_alat", "UTTP")).strip()

    try:
        jumlah = int(data.get("jumlah_alat", 1))
    except (TypeError, ValueError):
        jumlah = 1

    return (
        f"{jumlah} ({terbilang_indonesia(jumlah)}) "
        f"Unit {nama_alat} (Terlampir)"
    )


# =========================================================
# ELEMEN BERSAMA
# =========================================================
def draw_watermark(c, width, height):
    if not WATERMARK_PATH.exists():
        return

    try:
        watermark = ImageReader(str(WATERMARK_PATH))

        c.saveState()

        try:
            c.setFillAlpha(0.15)
        except Exception:
            pass

        size = 12 * cm

        c.drawImage(
            watermark,
            (width - size) / 2,
            (height - size) / 2,
            width=size,
            height=size,
            mask="auto",
        )

        c.restoreState()

    except Exception as exc:
        print(f"Watermark UTTP tidak dapat dimuat: {exc}")


def draw_header(c, width, height):
    margin = 1.5 * cm
    right_limit = width - margin
    y = height - 1.2 * cm

    if LOGO_PATH.exists():
        try:
            logo = ImageReader(str(LOGO_PATH))

            c.drawImage(
                logo,
                margin,
                y - 2.2 * cm + 0.45 * cm,
                width=1.9 * cm,
                height=2.2 * cm,
                mask="auto",
            )

        except Exception as exc:
            print(f"Logo UTTP tidak dapat dimuat: {exc}")

    center_x = width / 2 + 0.4 * cm

    c.setFont("Helvetica", 14)
    c.drawCentredString(
        center_x,
        y,
        "PEMERINTAH KABUPATEN TANGERANG",
    )
    y -= 0.8 * cm

    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(
        center_x,
        y,
        "DINAS PERINDUSTRIAN DAN PERDAGANGAN",
    )
    y -= 0.45 * cm

    c.setFont("Helvetica", 10)
    c.drawCentredString(
        center_x,
        y,
        "Jl. Atik Soewardi, Gedung Usaha-Usaha Daerah Lt. 3 Tigaraksa, Tangerang, Banten 15720",
    )
    y -= 0.45 * cm

    c.drawCentredString(
        center_x,
        y,
        "Laman: disperindag.tangerangkab.go.id  Pos-el: disperindag@tangerangkab.go.id",
    )
    y -= 0.35 * cm

    c.setLineWidth(2)
    c.line(margin, y, right_limit, y)

    y -= 0.1 * cm

    c.setLineWidth(0.8)
    c.line(margin, y, right_limit, y)

    return y


def draw_footer(c, width, page_text):
    margin = 1.5 * cm
    right_limit = width - margin

    c.setLineWidth(0.5)
    c.line(margin, 1.8 * cm, right_limit, 1.8 * cm)

    c.setFont("Helvetica-Oblique", 10)
    c.drawString(
        margin,
        1.5 * cm,
        "Dilarang menggandakan sebagian dan atau seluruh isi Surat Keterangan Hasil Pengujian ini tanpa seizin dari",
    )
    c.drawString(
        margin,
        1.2 * cm,
        "Bidang Kemetrologian Kabupaten Tangerang",
    )
    c.drawRightString(
        right_limit,
        0.9 * cm,
        page_text,
    )


def draw_wrapped_text(
    c,
    text,
    x,
    y,
    max_width,
    font_name="Helvetica",
    font_size=12,
    line_height=0.45 * cm,
):
    text = str(text or "")
    paragraphs = text.splitlines() or [""]

    lines = []

    for paragraph in paragraphs:
        words = paragraph.split()

        if not words:
            lines.append("")
            continue

        current = ""

        for word in words:
            candidate = word if not current else f"{current} {word}"

            if c.stringWidth(
                candidate,
                font_name,
                font_size,
            ) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word

        if current:
            lines.append(current)

    c.setFont(font_name, font_size)

    for index, line in enumerate(lines):
        c.drawString(
            x,
            y - index * line_height,
            line,
        )

    return y - max(0, len(lines) - 1) * line_height


def draw_bullet_notes(
    c,
    text,
    x,
    y,
    max_width,
    font_size=12,
    leading=0.42 * cm,
):
    bullet_indent = 0.45 * cm

    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()

        if not line:
            y -= leading
            continue

        if not line.startswith("•"):
            c.setFont("Helvetica-Bold", font_size)
            c.drawString(x, y, line)
            y -= leading
            continue

        body = line[1:].strip()

        c.setFont("Helvetica", font_size)
        c.drawString(x, y, "•")

        words = body.split()
        current = ""

        for word in words:
            candidate = word if not current else f"{current} {word}"

            if c.stringWidth(
                candidate,
                "Helvetica",
                font_size,
            ) <= max_width - bullet_indent:
                current = candidate
            else:
                if current:
                    c.drawString(
                        x + bullet_indent,
                        y,
                        current,
                    )
                    y -= leading
                current = word

        if current:
            c.drawString(
                x + bullet_indent,
                y,
                current,
            )
            y -= leading

    return y


# =========================================================
# CATATAN
# =========================================================
def buat_catatan_uttp(data):
    jenis_pengujian = str(
        data.get("jenis_pengujian", "Tera Ulang")
    ).strip()

    tahun_tanda = get_tahun_tanda(data)

    if jenis_pengujian.lower() == "tera":
        return (
            "Pembubuhan Tanda Tera :\n"
            f'• Tanda Tera Sah SL6 "{tahun_tanda}", '
            "Tanda Daerah D8 dan Tanda Pegawai Berhak H "
            "pada lemping yang dililit dengan kawat yang disegel "
            "dengan Tanda Jaminan JP8.\n"
            "• Tanda Jaminan JP8 pada bagian yang dapat menjadi "
            "potensi dilakukan perubahan yang mempengaruhi "
            "karakteristik kemetrologiannya."
        )

    return (
        "Pembubuhan Tanda Tera Ulang :\n"
        f'• Tanda Tera Sah SP6 "{tahun_tanda}" '
        "dan JP8 pada Alat Justir.\n"
        "• Tanda Jaminan JP8 pada bagian yang dapat menjadi "
        "potensi dilakukan perubahan yang mempengaruhi "
        "karakteristik kemetrologiannya."
    )


# =========================================================
# HALAMAN 1
# =========================================================
def draw_halaman_1(c, width, height, data, total_pages):
    margin = 1.5 * cm
    content_left = 3.0 * cm
    right_limit = width - margin

    draw_watermark(c, width, height)

    y = draw_header(c, width, height)
    y -= 0.8 * cm

    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(
        width / 2,
        y,
        "SURAT KETERANGAN HASIL PENGUJIAN",
    )
    y -= 0.45 * cm

    c.setFont("Helvetica-Oblique", 12)
    c.drawCentredString(
        width / 2,
        y,
        "Verification Report",
    )
    y -= 0.45 * cm

    c.setFont("Helvetica", 12)
    c.drawCentredString(
        width / 2,
        y,
        f"Nomor : {data.get('nomor_sertifikat', '')}",
    )
    y -= 0.9 * cm

    labels = [
        "Nomor Order",
        "Nama Alat",
        "Pemilik",
        "Alamat",
        "Penera",
        "Tanggal Pengujian",
        "Hasil",
        "Berlaku sampai",
        "Catatan",
    ]

    max_label_width = max(
        c.stringWidth(label, "Helvetica", 12)
        for label in labels
    )

    colon_x = content_left + max_label_width + 1.5 * cm
    value_x = colon_x + 0.3 * cm
    line_spacing = 0.45 * cm

    def draw_field(
        label,
        sublabel,
        value,
        y_value,
        bold_label=False,
        bold_value=False,
        value_font_size=12,
    ):
        label_font = (
            "Helvetica-Bold"
            if bold_label
            else "Helvetica"
        )
        sublabel_font = (
            "Helvetica-BoldOblique"
            if bold_label
            else "Helvetica-Oblique"
        )
        value_font = (
            "Helvetica-Bold"
            if bold_value
            else "Helvetica"
        )

        c.setFont(label_font, 12)
        c.drawString(content_left, y_value, label)

        underline_width = c.stringWidth(
            label,
            label_font,
            12,
        )
        c.line(
            content_left,
            y_value - 0.08 * cm,
            content_left + underline_width,
            y_value - 0.08 * cm,
        )

        c.setFont(sublabel_font, 12)
        c.drawString(
            content_left,
            y_value - line_spacing,
            sublabel,
        )

        c.setFont("Helvetica", 12)
        c.drawString(colon_x, y_value, ":")

        low_y = draw_wrapped_text(
            c,
            value,
            value_x,
            y_value,
            right_limit - value_x,
            font_name=value_font,
            font_size=value_font_size,
        )

        return min(
            low_y - 0.5 * cm,
            y_value - 0.9 * cm,
        )

    y = draw_field(
        "Nomor Order",
        "Order Number",
        data.get("nomor_order", ""),
        y,
    )

    y = draw_field(
        "Nama Alat",
        "Measuring Instrument",
        susun_nama_alat_sertifikat(data),
        y,
        bold_label=True,
        bold_value=True,
    )

    y = draw_field(
        "Pemilik",
        "User",
        data.get("pemilik", ""),
        y,
        bold_label=True,
        bold_value=True,
    )

    y = draw_field(
        "Alamat",
        "Address",
        data.get("alamat", ""),
        y,
    )

    y -= 0.2 * cm

    # Penera
    c.setFont("Helvetica", 12)
    c.drawString(content_left, y, "Penera")
    c.line(
        content_left,
        y - 0.08 * cm,
        content_left + c.stringWidth(
            "Penera",
            "Helvetica",
            12,
        ),
        y - 0.08 * cm,
    )

    c.setFont("Helvetica-Oblique", 12)
    c.drawString(
        content_left,
        y - line_spacing,
        "Calibration Technician",
    )

    c.setFont("Helvetica", 12)
    c.drawString(colon_x, y, ":")

    penera_lines = []

    if data.get("penera_1"):
        penera_lines.append(
            f"{data.get('penera_1', '')} / "
            f"NIP. {data.get('nip_penera_1', '')}"
        )

    if (
        int(data.get("jumlah_penera", 1) or 1) == 2
        and data.get("penera_2")
    ):
        penera_lines.append(
            f"{data.get('penera_2', '')} / "
            f"NIP. {data.get('nip_penera_2', '')}"
        )

    if not penera_lines:
        penera_lines = [""]

    for index, penera in enumerate(penera_lines):
        font_size = 12

        while (
            c.stringWidth(
                penera,
                "Helvetica",
                font_size,
            ) > right_limit - value_x
            and font_size > 9
        ):
            font_size -= 0.25

        c.setFont("Helvetica", font_size)
        c.drawString(
            value_x,
            y - index * 0.45 * cm,
            penera,
        )

    y -= (
        1.15 * cm
        if len(penera_lines) > 1
        else 0.9 * cm
    )

    y = draw_field(
        "Tanggal Pengujian",
        "Date Of Verification",
        format_tanggal(
            data.get("tanggal_pengujian")
            or data.get("tanggal")
        ),
        y,
    )

    # Hasil
    jenis = data.get(
        "jenis_pengujian",
        "Tera Ulang",
    )
    hasil = (
        f"Disahkan untuk {jenis} "
        f"Tahun {get_tahun_pengujian(data)}"
    )

    c.setFont("Helvetica", 12)
    c.drawString(content_left, y, "Hasil")
    c.line(
        content_left,
        y - 0.08 * cm,
        content_left + c.stringWidth(
            "Hasil",
            "Helvetica",
            12,
        ),
        y - 0.08 * cm,
    )

    c.setFont("Helvetica-Oblique", 12)
    c.drawString(
        content_left,
        y - line_spacing,
        "Results",
    )

    c.setFont("Helvetica", 12)
    c.drawString(colon_x, y, ":")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(value_x, y, hasil)

    c.setFont("Helvetica", 12)
    y -= 0.45 * cm
    c.drawString(
        value_x,
        y,
        "Berdasarkan Undang-Undang RI No. 2 Tahun 1981",
    )
    y -= 0.45 * cm
    c.drawString(
        value_x,
        y,
        "tentang Metrologi Legal",
    )
    y -= 0.65 * cm

    # Berlaku sampai
    tanggal_uji = (
        data.get("tanggal_pengujian")
        or data.get("tanggal")
    )
    berlaku_sampai = tambah_satu_tahun(tanggal_uji)

    c.setFont("Helvetica", 12)
    c.drawString(content_left, y, "Berlaku sampai")
    c.line(
        content_left,
        y - 0.08 * cm,
        content_left + c.stringWidth(
            "Berlaku sampai",
            "Helvetica",
            12,
        ),
        y - 0.08 * cm,
    )

    c.setFont("Helvetica-Oblique", 12)
    c.drawString(
        content_left,
        y - line_spacing,
        "This report due to",
    )

    c.setFont("Helvetica", 12)
    c.drawString(colon_x, y, ":")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        value_x,
        y,
        format_tanggal(berlaku_sampai),
    )
    y -= 1.0 * cm

    # Catatan
    c.setFont("Helvetica", 12)
    c.drawString(content_left, y, "Catatan")
    c.line(
        content_left,
        y - 0.08 * cm,
        content_left + c.stringWidth(
            "Catatan",
            "Helvetica",
            12,
        ),
        y - 0.08 * cm,
    )

    c.setFont("Helvetica-Oblique", 12)
    c.drawString(
        content_left,
        y - line_spacing,
        "Note",
    )

    c.setFont("Helvetica", 12)
    c.drawString(colon_x, y, ":")

    y = draw_bullet_notes(
        c,
        buat_catatan_uttp(data),
        value_x,
        y,
        right_limit - value_x,
        font_size=11,
        leading=0.42 * cm,
    )

    y -= 0.35 * cm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        value_x,
        y,
        "Dilarang memutus segel tera tanpa sepengetahuan",
    )
    y -= 0.4 * cm
    c.drawString(
        value_x,
        y,
        "Unit Metrologi Legal.",
    )
    y -= 0.65 * cm

    # Tanda tangan Kepala Bidang
    signature_x = width - margin - 10 * cm

    tanggal_cetak = (
        data.get("tanggal_sertifikat")
        or data.get("tanggal_cetak")
        or data.get("tanggal_pengujian")
    )

    c.setFont("Helvetica", 12)
    c.drawString(
        signature_x,
        y,
        f"Tangerang, {format_tanggal(tanggal_cetak)}",
    )
    y -= 0.75 * cm

    c.drawString(
        signature_x,
        y,
        "A.n. Kepala Dinas Perindustrian dan Perdagangan",
    )
    y -= 0.4 * cm

    c.drawString(
        signature_x,
        y,
        "Kabupaten Tangerang",
    )
    y -= 0.4 * cm

    c.drawString(
        signature_x,
        y,
        "Kepala Bidang Kemetrologian",
    )
    y -= 1.8 * cm

    c.drawString(
        signature_x,
        y,
        "Priatin Saputra, S.Kom., M.Si.",
    )
    y -= 0.4 * cm

    c.drawString(
        signature_x,
        y,
        "Penata Tk. I (III/d)",
    )
    y -= 0.4 * cm

    c.drawString(
        signature_x,
        y,
        "NIP. 198505152011011004",
    )

    draw_footer(
        c,
        width,
        f"Halaman 1 dari {total_pages}"
    )


# =========================================================
# HALAMAN 2
# =========================================================
def draw_halaman_2(
    c,
    width,
    height,
    data,
    total_pages,
    maksimal_baris=24
):
    margin_old = 1.5 * cm
    margin_left_content = 3.0 * cm
    right_limit_old = width - margin_old

    nomor_sertifikat = str(
        data.get("nomor_sertifikat", "")
    )

    daftar_rincian = data.get(
        "daftar_rincian_uttp",
        []
    )

    if not isinstance(daftar_rincian, list):
        daftar_rincian = []

    # Pecah daftar menjadi maksimal 24 baris per halaman
    kelompok_halaman = [
        daftar_rincian[i:i + maksimal_baris]
        for i in range(
            0,
            len(daftar_rincian),
            maksimal_baris
        )
    ]

    # Tetap buat satu halaman lampiran jika data kosong
    if not kelompok_halaman:
        kelompok_halaman = [[]]

    # Nama UTTP mengikuti pilihan pengguna
    daftar_alat = data.get(
        "daftar_alat_uttp",
        []
    )

    nama_alat_uttp = str(
        data.get("nama_alat", "UTTP")
    ).strip()

    if (
        isinstance(daftar_alat, list)
        and daftar_alat
        and isinstance(daftar_alat[0], dict)
    ):
        nama_alat_uttp = str(
            daftar_alat[0].get(
                "nama_alat",
                nama_alat_uttp
            )
        ).strip()

    if not nama_alat_uttp:
        nama_alat_uttp = "UTTP"
    tampilkan_kolom_nama_alat = (
        nama_alat_uttp.strip().lower() == "timbangan"
    )
    if tampilkan_kolom_nama_alat:
        # Tabel 7 kolom dibuat lebih lebar
        table_margin_left = 1.0 * cm

        col_widths = [
            0.7 * cm,   # No.
            3.0 * cm,   # Nama Alat
            2.0 * cm,   # Merek
            2.6 * cm,   # Model / Tipe
            2.3 * cm,   # Nomor Seri
            2.4 * cm,   # Kapasitas
            2.4 * cm,   # Daya Baca
            1.2 * cm,   # Kelas
        ]
    else:
        table_margin_left = margin_left_content

        col_widths = [
            0.8 * cm,   # No.
            2.4 * cm,   # Merek
            3.0 * cm,   # Model / Tipe
            2.8 * cm,   # Nomor Seri
            2.8 * cm,   # Kapasitas
            2.8 * cm,   # Daya Baca
            1.5 * cm,   # Kelas
        ]

    table_total_width = sum(col_widths)

    table_center_x = (
        table_margin_left
        + table_total_width / 2
    )

    # =====================================================
    # BUAT SETIAP HALAMAN LAMPIRAN
    # =====================================================
    for halaman_index, kelompok_data in enumerate(
        kelompok_halaman
    ):
        nomor_halaman = halaman_index + 2

        # Halaman kedua sudah dibuat oleh generator.
        # Tambahkan halaman baru mulai lampiran kedua.
        if halaman_index > 0:
            c.showPage()

        y = height - margin_old

        # Header lampiran tetap muncul di semua halaman
        c.setFillGray(0)
        c.setFont("Helvetica", 10)

        c.drawRightString(
            right_limit_old,
            y,
            (
                "Lampiran Sertifikat Nomor : "
                f"{nomor_sertifikat}"
            )
        )

        # =================================================
        # HALAMAN LAMPIRAN PERTAMA / HALAMAN 2
        # =================================================
        if halaman_index == 0:
            y -= 0.9 * cm

            left_col_x = margin_left_content

            label_spesifikasi = [
                "Metode",
                "Standar",
                "Telusuran",
            ]

            max_label_width = max(
                c.stringWidth(
                    label,
                    "Helvetica",
                    12
                )
                for label in label_spesifikasi
            )

            colon_x_fixed = (
                left_col_x
                + max_label_width
                + 0.5 * cm
            )

            value_x = colon_x_fixed + 0.3 * cm

            # =============================================
            # METODE, STANDAR, DAN TELUSURAN
            # =============================================
            c.setFont("Helvetica-Bold", 12)
            c.drawString(
                left_col_x,
                y,
                "Metode, Standar, dan Telusuran"
            )

            y -= 0.45 * cm

            # Metode
            c.setFont("Helvetica", 12)
            c.drawString(left_col_x, y, "Metode")
            c.drawString(colon_x_fixed, y, ":")

            normal_text = (
                "Membandingkan langsung dengan standar ("
            )
            italic_text = "Direct Comparison"
            closing_text = ")"

            c.drawString(
                value_x,
                y,
                normal_text
            )

            normal_width = c.stringWidth(
                normal_text,
                "Helvetica",
                12
            )

            x_italic = value_x + normal_width

            c.setFont("Helvetica-Oblique", 12)
            c.drawString(
                x_italic,
                y,
                italic_text
            )

            italic_width = c.stringWidth(
                italic_text,
                "Helvetica-Oblique",
                12
            )

            c.setFont("Helvetica", 12)
            c.drawString(
                x_italic + italic_width,
                y,
                closing_text
            )

            y -= 0.45 * cm

            # Standar
            c.setFont("Helvetica", 12)
            c.drawString(
                left_col_x,
                y,
                "Standar"
            )
            c.drawString(
                colon_x_fixed,
                y,
                ":"
            )

            # Ambil pilihan alat standar dari aplikasi
            daftar_standar = data.get(
                "alat_standar",
                []
            )

            # Pastikan bentuk datanya selalu list
            if isinstance(daftar_standar, list):
                daftar_standar = [
                    str(item).strip().upper()
                    for item in daftar_standar
                    if str(item).strip()
                ]
            else:
                nilai_standar = str(
                    daftar_standar or ""
                ).strip().upper()

                daftar_standar = (
                    [nilai_standar]
                    if nilai_standar
                    else []
                )

            # Urutan kelas standar tertinggi ke terendah
            urutan_kelas_standar = {
                "F1": 1,
                "F2": 2,
                "M1": 3,
                "M2": 4,
            }

            daftar_standar = sorted(
                daftar_standar,
                key=lambda item: urutan_kelas_standar.get(
                    item,
                    999
                )
            )

            # Hilangkan pilihan yang sama
            daftar_standar = list(
                dict.fromkeys(daftar_standar)
            )

            # Nilai bawaan jika belum ada pilihan
            if not daftar_standar:
                daftar_standar = ["M2"]

            # Format penulisan
            if len(daftar_standar) == 1:
                kelas_standar_text = daftar_standar[0]

            elif len(daftar_standar) == 2:
                kelas_standar_text = (
                    f"{daftar_standar[0]} dan "
                    f"{daftar_standar[1]}"
                )

            else:
                kelas_standar_text = (
                    ", ".join(daftar_standar[:-1])
                    + ", dan "
                    + daftar_standar[-1]
                )

            standar_text = (
                "Anak Timbangan Standar Kelas "
                f"{kelas_standar_text}"
            )

            c.drawString(
                value_x,
                y,
                standar_text
            )

            y -= 0.45 * cm

            # Telusuran
            c.drawString(
                left_col_x,
                y,
                "Telusuran"
            )

            c.drawString(
                colon_x_fixed,
                y,
                ":"
            )

            c.drawString(
                value_x,
                y,
                "Direktorat Metrologi Bandung"
            )

            y -= 0.8 * cm

            # =============================================
            # JUDUL DAFTAR UTTP
            # =============================================
            c.setFont("Helvetica-Bold", 12)

            c.drawCentredString(
                table_center_x,
                y,
                "DAFTAR UTTP"
            )

            y -= 0.45 * cm

            c.drawCentredString(
                table_center_x,
                y,
                nama_alat_uttp.upper()
            )

            y -= 0.7 * cm

        # =================================================
        # HALAMAN LANJUTAN / HALAMAN 3 DAN SETERUSNYA
        # =================================================
        else:
            # Langsung beri jarak dari header menuju tabel
            y -= 0.8 * cm

        # =================================================
        # DATA TABEL
        # =================================================
        if tampilkan_kolom_nama_alat:
            table_data = [[
                "No.",
                "Nama Alat",
                "Merek",
                "Model / Tipe",
                "Nomor Seri",
                "Kapasitas",
                "Daya Baca",
                "Kelas",
            ]]
        else:
            table_data = [[
                "No.",
                "Merek",
                "Model / Tipe",
                "Nomor Seri",
                "Kapasitas",
                "Daya Baca",
                "Kelas",
            ]]

        nomor_awal = (
            halaman_index * maksimal_baris
        )
        # Style teks isi tabel agar teks panjang dapat turun baris
        styles = getSampleStyleSheet()

        cell_style = ParagraphStyle(
            "CellStyle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=11,
            alignment=0,
            spaceAfter=0,
            spaceBefore=0,
        )
        for index, item in enumerate(
            kelompok_data,
            start=1
        ):
            if not isinstance(item, dict):
                continue

            satuan = str(
                item.get("satuan", "")
            ).strip()

            kapasitas = (
                f"{item.get('kapasitas', '')} "
                f"{satuan}"
            ).strip()

            nilai_daya_baca = str(
                item.get(
                    "daya_baca",
                    ""
                )
            ).strip()
            
            daya_baca = (
                "-"
                if nilai_daya_baca == "-"
                else f"{nilai_daya_baca} {satuan}".strip()
            )
            model_tipe = str(
                item.get(
                    "model_tipe",
                    item.get("tipe_no_seri", "")
                )
            ).strip()

            nomor_seri = str(
                item.get(
                    "nomor_seri",
                    ""
                )
            ).strip()
            if tampilkan_kolom_nama_alat:
                table_data.append([
                    str(nomor_awal + index),
                    Paragraph(
                        str(item.get("nama_alat", "")),
                        cell_style
                    ),
                    Paragraph(
                        str(item.get("merek", "")),
                        cell_style
                    ),
                    Paragraph(
                        model_tipe,
                        cell_style
                    ),
                    Paragraph(
                        nomor_seri,
                        cell_style
                    ),
                    kapasitas,
                    daya_baca,
                    str(item.get("kelas", "")),
                ])
            else:
                table_data.append([
                    str(nomor_awal + index),
                    Paragraph(
                        str(item.get("merek", "")),
                        cell_style
                    ),
                    Paragraph(
                        model_tipe,
                        cell_style
                    ),
                    Paragraph(
                        nomor_seri,
                        cell_style
                    ),
                    kapasitas,
                    daya_baca,
                    str(item.get("kelas", "")),
                ])

        if len(table_data) == 1:
            if tampilkan_kolom_nama_alat:
                table_data.append([
                    "1", "", "", "", "", "", "", ""
                ])
            else:
                table_data.append([
                    "1", "", "", "", "", "", ""
                ])

        table = Table(
            table_data,
            colWidths=col_widths,
            repeatRows=1,
        )

        table.setStyle(
            TableStyle([
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#D9EAF7"),
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold",
                ),
                (
                    "FONTNAME",
                    (0, 1),
                    (-1, -1),
                    "Helvetica",
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    10,
                ),
                (
                    "ALIGN",
                    (0, 0),
                    (0, -1),
                    "CENTER",
                ),
                (
                    "ALIGN",
                    (0, 0),
                    (-1, 0),
                    "CENTER",
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.7,
                    colors.black,
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
            ])
        )

        table_width, table_height = table.wrap(
            table_total_width,
            height,
        )

        table.drawOn(
            c,
            table_margin_left,
            y - table_height,
        )

        y = y - table_height - 0.9 * cm

        # =================================================
        # TANDA TANGAN HANYA PADA HALAMAN TERAKHIR
        # =================================================
        if halaman_index == len(kelompok_halaman) - 1:
            signature_x = (
                width
                - margin_old
                - 7.0 * cm
            )

            c.setFont("Helvetica", 12)
            c.drawString(
                signature_x,
                y,
                "Pegawai Berhak,"
            )

            y -= 1.8 * cm

            pegawai = (
                data.get("pegawai_berhak")
                or data.get("penera_1")
                or ""
            )

            nip_pegawai = (
                data.get("nip_pegawai_berhak")
                or data.get("nip_penera_1")
                or ""
            )

            golongan = (
                data.get("golongan_pegawai_berhak")
                or data.get("golongan_penera_1")
                or ""
            )

            c.setFont("Helvetica", 12)

            c.drawString(
                signature_x,
                y,
                str(pegawai)
            )

            y -= 0.4 * cm

            if golongan:
                c.drawString(
                    signature_x,
                    y,
                    str(golongan)
                )

                y -= 0.4 * cm

            c.drawString(
                signature_x,
                y,
                f"NIP. {nip_pegawai}"
            )

        draw_footer(
            c,
            width,
            (
                f"Halaman {nomor_halaman} "
                f"dari {total_pages}"
            )
        )


# =========================================================
# GENERATOR UTAMA
# =========================================================
def generate_sertifikat_uttp_pdf(
    data,
    output_path="sertifikat_uttp.pdf",
):
    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    daftar_rincian = data.get(
        "daftar_rincian_uttp",
        []
    )

    if not isinstance(daftar_rincian, list):
        daftar_rincian = []

    maksimal_baris = 24

    jumlah_halaman_lampiran = max(
        1,
        (
            len(daftar_rincian)
            + maksimal_baris
            - 1
        ) // maksimal_baris
    )

    total_pages = (
        1
        + jumlah_halaman_lampiran
    )

    c = canvas.Canvas(
        str(output_path),
        pagesize=A4,
    )

    width, height = A4

    draw_halaman_1(
        c,
        width,
        height,
        data,
        total_pages,
    )

    c.showPage()

    draw_halaman_2(
        c,
        width,
        height,
        data,
        total_pages,
        maksimal_baris=maksimal_baris,
    )

    c.save()

    return str(output_path)


# Alias agar mudah dipanggil dari versi aplikasi lain.
generate_sertifikat_uttp = generate_sertifikat_uttp_pdf
