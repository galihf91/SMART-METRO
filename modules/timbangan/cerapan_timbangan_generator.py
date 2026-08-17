from __future__ import annotations

from datetime import datetime
import math
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Path as DrawingPath
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle


# ============================================================
# HELPER UMUM
# ============================================================

def register_unicode_font() -> str:
    """
    Mendaftarkan font Unicode untuk simbol seperti ≠.
    Mengembalikan nama font yang berhasil didaftarkan.
    """

    current_file = Path(__file__).resolve()

    kandidat_font = [
        # Font yang disimpan di folder assets proyek
        current_file.parent / "assets" / "DejaVuSans.ttf",
        current_file.parent.parent / "assets" / "DejaVuSans.ttf",

        # Streamlit Cloud / Linux
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),

        # Windows
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf"),
    ]

    for font_path in kandidat_font:
        if font_path.exists():
            try:
                pdfmetrics.registerFont(
                    TTFont(
                        "UnicodeFont",
                        str(font_path)
                    )
                )
                return "UnicodeFont"
            except Exception:
                continue

    # Fallback jika tidak ada font Unicode
    return "Helvetica"
def safe_str(value: Any) -> str:
    """Mengubah nilai menjadi string dengan aman."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "SAH" if value else "TIDAK SAH"
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return str(value)


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, str):
            value = value.strip().replace(".", "").replace(",", ".")
        return float(value)
    except (TypeError, ValueError):
        return default


def format_angka_id(value: Any, decimals: int | None = None) -> str:
    """Format angka Indonesia tanpa nol desimal yang tidak diperlukan."""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return safe_str(value)

    if decimals is not None:
        text = f"{float(number):.{decimals}f}"
    else:
        text = format(number.normalize(), "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")

    if text in {"-0", "-0.0", ""}:
        text = "0"
    return text.replace(".", ",")


def format_tanggal_indo(value: Any) -> str:
    """Mengubah tanggal menjadi format Indonesia, misalnya 15 Juli 2026."""
    if not value:
        return ""

    if isinstance(value, datetime):
        dt = value
    else:
        raw = safe_str(value).strip()
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                dt = datetime.strptime(raw, fmt)
                break
            except ValueError:
                dt = None
        if dt is None:
            return raw

    bulan = [
        "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember",
    ]
    return f"{dt.day} {bulan[dt.month - 1]} {dt.year}"


def kg_ke_satuan(value_kg: Any, satuan: str) -> float:
    nilai = to_float(value_kg)
    return nilai * 1000.0 if satuan == "g" else nilai


def nilai_dengan_satuan_dari_kg(value_kg: Any, satuan: str) -> str:
    nilai = kg_ke_satuan(value_kg, satuan)
    return f"{format_angka_id(nilai)} {satuan}".strip()


def tambah_satuan_jika_belum(text: Any, satuan: str) -> str:
    hasil = safe_str(text).strip()
    if not hasil:
        return ""
    huruf_kecil = hasil.lower()
    if huruf_kecil.endswith(" kg") or huruf_kecil.endswith(" g"):
        return hasil
    return f"{hasil} {satuan}"


def tanda_cek(value: Any) -> str:
    """Gunakan karakter ASCII agar aman pada font bawaan ReportLab."""
    if isinstance(value, str):
        cleaned = value.strip().lower()
        return "V" if cleaned in {"v", "✓", "✅", "true", "sah", "ya"} else "X"
    return "V" if bool(value) else "X"


def hasil_text(item: dict[str, Any]) -> str:
    if item.get("hasil_text"):
        return safe_str(item.get("hasil_text"))
    return "SAH" if item.get("hasil", True) else "TIDAK SAH"


# ============================================================
# STYLE PARAGRAPH DAN TABLE
# ============================================================

_styles = getSampleStyleSheet()

P_LEFT = ParagraphStyle(
    "CellLeft",
    parent=_styles["Normal"],
    fontName="Helvetica",
    fontSize=7.2,
    leading=8.2,
    alignment=TA_LEFT,
    spaceAfter=0,
    spaceBefore=0,
)

P_CENTER = ParagraphStyle(
    "CellCenter",
    parent=P_LEFT,
    alignment=TA_CENTER,
)

P_RIGHT = ParagraphStyle(
    "CellRight",
    parent=P_LEFT,
    alignment=TA_RIGHT,
)

P_HEADER = ParagraphStyle(
    "CellHeader",
    parent=P_CENTER,
    fontName="Helvetica-Bold",
    fontSize=7.0,
    leading=7.8,
)

P_SMALL = ParagraphStyle(
    "CellSmall",
    parent=P_LEFT,
    fontSize=6.3,
    leading=7.0,
)
P_SMALL_BOLD_LEFT = ParagraphStyle(
    "CellSmallBoldLeft",
    parent=P_SMALL,
    fontName="Helvetica-Bold",
    alignment=TA_LEFT,
)
P_SMALL_CENTER = ParagraphStyle(
    "CellSmallCenter",
    parent=P_SMALL,
    alignment=TA_CENTER,
)


def p(text: Any, style: ParagraphStyle = P_LEFT) -> Paragraph:
    value = safe_str(text)
    value = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    value = value.replace("\n", "<br/>")
    return Paragraph(value, style)


def buat_tanda_centang() -> Drawing:
    """Tanda centang vektor agar tidak berubah menjadi kotak hitam."""
    drawing = Drawing(11, 9)
    path = DrawingPath()
    path.moveTo(1.0, 4.5)
    path.lineTo(4.0, 1.5)
    path.lineTo(10.0, 8.0)
    path.strokeColor = colors.black
    path.strokeWidth = 1.4
    path.fillColor = None
    drawing.add(path)
    return drawing


def buat_sel_cek(semua_sah: bool) -> Table:
    """Membuat isi kolom Cek: SAH dan BATAL dengan centang vektor."""
    baris_sah = [
        p("SAH", P_SMALL_CENTER),
        buat_tanda_centang() if semua_sah else "",
    ]
    baris_batal = [
        p("BATAL", P_SMALL_CENTER),
        "" if semua_sah else buat_tanda_centang(),
    ]

    tabel = Table(
        [baris_sah, baris_batal],
        colWidths=[1.05 * cm, 0.40 * cm],
        rowHeights=[0.31 * cm, 0.31 * cm],
    )
    tabel.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("BOX", (0, 0), (-1, -1), 0, colors.white),
        ("INNERGRID", (0, 0), (-1, -1), 0, colors.white),
    ]))
    return tabel


def style_tabel_umum(
    header_rows: Iterable[int] = (0,),
    font_size: float = 7.2,
    padding: float = 2.2,
) -> TableStyle:
    commands: list[tuple] = [
        ("GRID", (0, 0), (-1, -1), 0.55, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), padding),
        ("RIGHTPADDING", (0, 0), (-1, -1), padding),
        ("TOPPADDING", (0, 0), (-1, -1), 2.0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.0),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
    ]
    for row in header_rows:
        commands.extend([
            ("BACKGROUND", (0, row), (-1, row), colors.HexColor("#D9D9D9")),
            ("FONTNAME", (0, row), (-1, row), "Helvetica-Bold"),
            ("ALIGN", (0, row), (-1, row), "CENTER"),
        ])
    return TableStyle(commands)


def gambar_tabel(
    c: canvas.Canvas,
    table: Table,
    x: float,
    y_top: float,
    available_width: float,
) -> tuple[float, float]:
    """Menggambar tabel dari posisi atas dan mengembalikan y baru serta tinggi tabel."""
    table_width, table_height = table.wrapOn(c, available_width, A4[1])
    table.drawOn(c, x, y_top - table_height)
    return y_top - table_height, table_height


def gambar_judul_bagian(
    c: canvas.Canvas,
    y: float,
    nomor: int,
    judul: str,
    catatan: str = "",
    catatan_x: float | None = None,
    margin: float = 1.2 * cm,
    font_catatan: str = "Helvetica-BoldOblique",
) -> float:
    c.setFont("Helvetica-BoldOblique", 9)
    c.drawString(
        margin,
        y,
        f"{nomor}. {judul}"
    )

    if catatan:
        c.setFont(font_catatan, 8)
        c.drawString(
            catatan_x
            if catatan_x is not None
            else margin + 5.8 * cm,
            y,
            catatan
        )

    return y - 0.18 * cm


# ============================================================
# GENERATOR PDF
# ============================================================

def generate_cerapan_pdf(data: dict[str, Any], filename: str) -> str:
    """
    Membuat cerapan Timbangan Elektronik sesuai struktur aplikasi:
    1. Pemeriksaan Visual
    2. Pengujian Kebenaran
    3. Pengujian Eksentrisitas
    4. Pengujian Kemampuan Ulang / Repetability
    """
    output = Path(filename)
    output.parent.mkdir(parents=True, exist_ok=True)

    width, height = A4
    margin = 1.2 * cm
    available_width = width - (2 * margin)
    satuan = safe_str(data.get("satuan", "kg")) or "kg"
    nama_alat = safe_str(data.get("nama_alat", "")).strip().lower()
    is_neraca_obat = nama_alat in {
        "neraca obat",
        "timbangan neraca obat",
    }
    is_timbangan_elektronik = nama_alat == "timbangan elektronik"

    daya_baca_kg = to_float(data.get("daya_baca", 0.0))
    interval_skala_kg = to_float(data.get("interval_skala", 0.0))

    d_tidak_sama_e = (
        is_timbangan_elektronik
        and daya_baca_kg > 0
        and interval_skala_kg > 0
        and not math.isclose(
            daya_baca_kg,
            interval_skala_kg,
            rel_tol=1e-9,
            abs_tol=1e-12,
        )
    )
    if is_neraca_obat:
        keterangan_ed_cerapan = ""
    elif d_tidak_sama_e:
        keterangan_ed_cerapan = "( e ≠ d )"
    else:
        keterangan_ed_cerapan = "( e = d )"
    repetability_sederhana = bool(
        data.get(
            "repetability_sederhana",
            is_neraca_obat or d_tidak_sama_e,
        )
    )
    c = canvas.Canvas(str(output), pagesize=A4)
    y = height - 1.0 * cm
    font_unicode = register_unicode_font()
    # --------------------------------------------------------
    # JUDUL
    # --------------------------------------------------------
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(width / 2, y, "CERAPAN PENERAAN TIMBANGAN")
    y -= 0.58 * cm

    c.setLineWidth(1.6)
    c.line(margin, y, width - margin, y)
    y -= 0.08 * cm
    c.setLineWidth(0.55)
    c.line(margin, y, width - margin, y)
    y -= 0.24 * cm

    # --------------------------------------------------------
    # PEMILIK DAN ALAMAT
    # --------------------------------------------------------
    info_utama = Table(
        [
            [p("Pemilik", P_LEFT), p(f": {safe_str(data.get('pemilik', ''))}", P_LEFT)],
            [p("Alamat", P_LEFT), p(f": {safe_str(data.get('alamat', ''))}", P_LEFT)],
        ],
        colWidths=[1.35 * cm, available_width - 1.35 * cm],
    )
    info_utama.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 1.0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.0),
    ]))
    y, _ = gambar_tabel(c, info_utama, margin, y, available_width)
    y -= 0.10 * cm

    c.setLineWidth(0.55)
    c.line(margin, y, width - margin, y)
    y -= 0.20 * cm

    # --------------------------------------------------------
    # SPESIFIKASI ALAT DAN DATA PENGUJIAN
    # --------------------------------------------------------
    spesifikasi = [
        (
            "Nama Alat",
            safe_str(
                data.get(
                    "nama_alat",
                    "Timbangan Elektronik"
                )
            ),
            True
        ),
        (
            "Merek / Buatan",
            safe_str(data.get("merek", "")),
            False
        ),
        (
            "Model / Tipe",
            safe_str(data.get("model", "")),
            False
        ),
        (
            "No. Seri",
            safe_str(data.get("no_seri", "")),
            False
        ),
        (
            "Kapasitas Maksimum",
            nilai_dengan_satuan_dari_kg(
                data.get("kapasitas_max", 0),
                satuan
            ),
            False
        ),
        (
            "Kapasitas Minimum",
            nilai_dengan_satuan_dari_kg(
                data.get("kapasitas_min", 0),
                satuan
            ),
            False
        ),
        (
            "Daya Baca",
            nilai_dengan_satuan_dari_kg(
                data.get("daya_baca", 0),
                satuan
            ),
            False
        ),
        (
            "Interval Skala Verifikasi",
            nilai_dengan_satuan_dari_kg(
                data.get("interval_skala", 0),
                satuan
            ),
            False
        ),
        (
            "Kelas",
            safe_str(data.get("kelas", "")),
            False
        ),
    ]

    # Model / Tipe hanya untuk Timbangan Elektronik
    if not is_timbangan_elektronik:
        spesifikasi = [
            item for item in spesifikasi
            if item[0] != "Model / Tipe"
        ]

    # Neraca Obat tidak memiliki Daya Baca
    if is_neraca_obat:
        spesifikasi = [
            item for item in spesifikasi
            if item[0] != "Daya Baca"
        ]

    # Neraca Obat tidak memiliki Daya Baca terpisah.
    if is_neraca_obat:
        spesifikasi = [
            item for item in spesifikasi
            if item[0] != "Daya Baca"
        ]

    pengujian = [
        ("Tanggal", format_tanggal_indo(data.get("tanggal_penera", data.get("tanggal", "")))),
        ("Lokasi", safe_str(data.get("lokasi", "Perusahaan"))),
        ("Suhu Ruangan", safe_str(data.get("suhu", "Ambient"))),
        ("Kelembaban", safe_str(data.get("kelembaban", "Ambient"))),
        ("Metode", safe_str(data.get("metode", ""))),
        ("AT Standar", safe_str(data.get("at_standar", ""))),
        ("Keterangan", safe_str(data.get("keterangan", "Tera"))),
    ]

    rows_spec: list[list[Any]] = [
        [
            p("SPESIFIKASI ALAT", P_HEADER),
            "",
            p("DATA PENGUJIAN", P_HEADER),
            ""
        ]
    ]

    # Jumlah baris mengikuti daftar yang paling panjang
    jumlah_baris = max(len(spesifikasi), len(pengujian))

    for idx in range(jumlah_baris):

        # -------------------------
        # Data spesifikasi alat
        # -------------------------
        if idx < len(spesifikasi):
            label_spec, nilai_spec, is_bold = spesifikasi[idx]

            style_spec = (
                P_SMALL_BOLD_LEFT
                if is_bold
                else P_SMALL
            )

            label_spec_pdf = p(label_spec, style_spec)
            nilai_spec_pdf = p(nilai_spec, style_spec)
        else:
            label_spec_pdf = ""
            nilai_spec_pdf = ""

        # -------------------------
        # Data pengujian
        # -------------------------
        if idx < len(pengujian):
            label_uji, nilai_uji = pengujian[idx]

            label_uji_pdf = p(label_uji, P_SMALL)
            nilai_uji_pdf = p(nilai_uji, P_SMALL)
        else:
            label_uji_pdf = ""
            nilai_uji_pdf = ""

        rows_spec.append([
            label_spec_pdf,
            nilai_spec_pdf,
            label_uji_pdf,
            nilai_uji_pdf,
        ])
    spec_table = Table(
        rows_spec,
        colWidths=[
            3.25 * cm,
            5.3 * cm,
            2.8 * cm,
            available_width - 11.35 * cm
        ],
        rowHeights=[
            0.40 * cm
        ] + [
            0.40 * cm
        ] * jumlah_baris,
    )
    spec_style = style_tabel_umum(header_rows=(0,), font_size=6.7, padding=2)
    spec_style.add("SPAN", (0, 0), (1, 0))
    spec_style.add("SPAN", (2, 0), (3, 0))
    # Header tetap di tengah
    spec_style.add("ALIGN", (0, 0), (-1, 0), "CENTER")

    # Isi tabel rata kiri
    spec_style.add("ALIGN", (0, 1), (-1, -1), "LEFT")

    # Vertikal di tengah
    spec_style.add("VALIGN", (0, 0), (-1, -1), "MIDDLE")
    spec_style.add("ALIGN", (0, 0), (-1, 0), "CENTER")
    spec_table.setStyle(spec_style)
    y, _ = gambar_tabel(c, spec_table, margin, y, available_width)
    y -= 0.22 * cm

    # ========================================================
    # 1. PEMERIKSAAN VISUAL
    # ========================================================
    y -= 0.40 * cm
    y = gambar_judul_bagian(c, y, 1, "Pemeriksaan Visual", margin=margin)

    jenis_pengujian = safe_str(data.get("keterangan", "Tera"))
    visual_data = data.get("visual", {}) or {}
    visual_items = [
        "Timbangan bersih, kering dan tidak berkarat",
        "Bahan & Konstruksi Sesuai (Tera)",
        "Posisi timbangan datar",
        "Telah dilakukan pemanasan timbangan",
    ]

    visual_rows: list[list[Any]] = [[
        p("No.", P_HEADER),
        p("Jenis Pemeriksaan", P_HEADER),
        p("Ya", P_HEADER),
        p("Tidak", P_HEADER),
        p("Keterangan", P_HEADER),
    ]]

    for idx, item in enumerate(visual_items, 1):
        khusus_tera = item == "Bahan & Konstruksi Sesuai (Tera)"

        if khusus_tera and jenis_pengujian == "Tera Ulang":
            sel_ya = p("-", P_CENTER)
            sel_tidak = p("-", P_CENTER)
            keterangan_visual = "Tera Ulang"

        else:
            ok = bool(visual_data.get(item, False))

            # Gunakan checklist vektor seperti tabel Eksentrisitas
            sel_ya = buat_tanda_centang() if ok else ""
            sel_tidak = "" if ok else buat_tanda_centang()

            keterangan_visual = ""

        visual_rows.append([
            p(idx, P_CENTER),
            p(item, P_LEFT),
            sel_ya,
            sel_tidak,
            p(keterangan_visual, P_CENTER),
        ])

    visual_table = Table(
        visual_rows,
        colWidths=[0.55 * cm, 8.65 * cm, 1.6 * cm, 1.6 * cm, available_width - 12.4 * cm],
        rowHeights=[0.40 * cm] + [0.38 * cm] * 4,
    )
    visual_style = style_tabel_umum(
        header_rows=(0,),
        font_size=7.0,
        padding=1.8
    )

    # Kolom Ya dan Tidak dibuat rata tengah
    visual_style.add(
        "ALIGN",
        (2, 1),
        (3, -1),
        "CENTER"
    )

    visual_style.add(
        "VALIGN",
        (2, 1),
        (3, -1),
        "MIDDLE"
    )

    visual_table.setStyle(visual_style)
    y, _ = gambar_tabel(c, visual_table, margin, y, available_width)
    y -= 0.23 * cm

    # ========================================================
    # 2. PENGUJIAN KEBENARAN
    # ========================================================
    y -= 0.40 * cm
    y = gambar_judul_bagian(
        c,
        y,
        2,
        "Pengujian Kebenaran",
        keterangan_ed_cerapan,
        margin + 5.6 * cm,
        margin,
        font_catatan=font_unicode,
    )

    benar_rows: list[list[Any]] = [[
        p("No", P_HEADER),
        p("Muatan Uji", P_HEADER),
        p("Penunjukan", P_HEADER),
        p("BKD", P_HEADER),
        p("Pengamatan Penunjukan", P_HEADER),
        p("Hasil", P_HEADER),
        p("Cek", P_HEADER),
    ]]

    hasil_pengujian = list(data.get("hasil_pengujian", []) or [])

    # Neraca Obat hanya menampilkan pengujian aktif pada baris pertama.
    # Baris 2–5 yang disabled di aplikasi tidak dicetak pada cerapan.
    if is_neraca_obat:
        hasil_yang_dicetak = hasil_pengujian[:1]
    else:
        hasil_yang_dicetak = hasil_pengujian[:5]

    for idx, item in enumerate(hasil_yang_dicetak, 1):
        # Prioritas mengikuti nilai yang tampil di aplikasi
        muatan_tampil = item.get("muatan_uji_tampil", None)

        if muatan_tampil not in (None, ""):
            muatan_tampil_text = safe_str(muatan_tampil).strip()

            if (
                muatan_tampil_text.lower().endswith(" kg")
                or muatan_tampil_text.lower().endswith(" g")
            ):
                muatan = muatan_tampil_text
            else:
                muatan = (
                    f"{format_angka_id(muatan_tampil)} "
                    f"{satuan}"
                )

        else:
            muatan_kg = item.get(
                "muatan_uji",
                item.get(
                    "muatan_sb",
                    item.get("standar", 0)
                )
            )

            muatan = nilai_dengan_satuan_dari_kg(
                muatan_kg,
                satuan
            )
        penunjukan = item.get(
            "penunjukan_text",
            item.get("timbangan_text", "")
        )
        if not penunjukan:
            penunjukan = nilai_dengan_satuan_dari_kg(
                item.get("penunjukan", item.get("timbangan", 0)),
                satuan,
            )

        benar_rows.append([
            p(idx, P_CENTER),
            p(muatan, P_CENTER),
            p(penunjukan, P_CENTER),
            p(item.get("bkd_text", ""), P_CENTER),
            p(
                item.get(
                    "pengamatan_penunjukan",
                    "Penunjukan = Massa ATS"
                ),
                P_SMALL,
            ),
            p(item.get("hasil_text", "SAH"), P_CENTER),
            (
                buat_tanda_centang()
                if item.get(
                    "cek_otomatis",
                    item.get("hasil", True)
                )
                else ""
            ),
        ])

    jumlah_baris_benar = 1 if is_neraca_obat else 5

    while len(benar_rows) < jumlah_baris_benar + 1:
        benar_rows.append([p("", P_CENTER) for _ in range(7)])

    benar_table = Table(
        benar_rows,
        colWidths=[
            0.6 * cm,
            2.55 * cm,
            2.75 * cm,
            1.55 * cm,
            6.0 * cm,
            2.1 * cm,
            available_width - 15.55 * cm,
        ],
        rowHeights=[0.42 * cm] + [0.40 * cm] * jumlah_baris_benar,
    )
    benar_style = style_tabel_umum(
        header_rows=(0,),
        font_size=6.6,
        padding=1.3,
    )

    # Kolom Cek dibuat rata tengah
    benar_style.add(
        "ALIGN",
        (6, 1),
        (6, -1),
        "CENTER"
    )

    benar_style.add(
        "VALIGN",
        (6, 1),
        (6, -1),
        "MIDDLE"
    )

    benar_table.setStyle(benar_style)
    y, _ = gambar_tabel(c, benar_table, margin, y, available_width)
    y -= 0.24 * cm

    if not is_neraca_obat:
        # ========================================================
        # 3. PENGUJIAN EKSENTRISITAS
        # ========================================================
        y -= 0.40 * cm
        y = gambar_judul_bagian(c, y, 3, "Pengujian Eksentrisitas", margin=margin)

        eksen_data = data.get("eksentrisitas", []) or []
        muatan_eks_kg = 0.0
        if eksen_data:
            muatan_eks_kg = to_float(eksen_data[0].get("muatan_eks", 0.0))
        if muatan_eks_kg <= 0:
            muatan_eks_kg = to_float(data.get("kapasitas_max", 0.0)) / 3.0

        y -= 0.10 * cm

        # Kotak posisi 1-4 di sebelah kiri
        posisi_table = Table(
            [[p("1", P_CENTER), p("2", P_CENTER)], [p("3", P_CENTER), p("4", P_CENTER)]],
            colWidths=[1.45 * cm, 1.45 * cm],
            rowHeights=[0.72 * cm, 0.72 * cm],
        )
        posisi_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.55, colors.black),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#D9D9D9")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ]))

        eks_rows: list[list[Any]] = [[
            p("Posisi", P_HEADER),
            p("Penunjukan (I)", P_HEADER),
            p("BKD", P_HEADER),
            p("Pengamatan Penunjukan", P_HEADER),
            p("Hasil", P_HEADER),
            p("Cek", P_HEADER),
        ]]

        for idx in range(4):
            item = eksen_data[idx] if idx < len(eksen_data) else {}
            penunjukan = item.get("penunjukan_text", "")
            if not penunjukan and item:
                penunjukan = format_angka_id(item.get("penunjukan_tampil", ""))
            penunjukan = tambah_satuan_jika_belum(penunjukan, satuan) if penunjukan else ""

            eks_rows.append([
                p(item.get("posisi", idx + 1), P_CENTER),
                p(penunjukan, P_CENTER),
                p(item.get("bkd_text", ""), P_CENTER),
                p(item.get("pengamatan_penunjukan", "penunjukan ≤ massa ATS ± BKD "), P_SMALL),
                p(hasil_text(item), P_CENTER),
                buat_tanda_centang(),
            ])

        table_x = margin + 3.25 * cm
        eks_width = available_width - 3.25 * cm
        eks_table = Table(
            eks_rows,
            colWidths=[1.45 * cm, 2.95 * cm, 1.45 * cm, 5.45 * cm, 1.75 * cm, eks_width - 13.05 * cm],
            rowHeights=[0.42 * cm] + [0.40 * cm] * 4,
        )
        eks_style = style_tabel_umum(
            header_rows=(0,),
            font_size=6.6,
            padding=1.3,
        )
        eks_style.add("ALIGN", (5, 1), (5, -1), "CENTER")
        eks_style.add("VALIGN", (5, 1), (5, -1), "MIDDLE")
        eks_table.setStyle(eks_style)

        _, posisi_h = posisi_table.wrapOn(c, 3.0 * cm, A4[1])
        eks_table_w, eks_table_h = eks_table.wrapOn(c, eks_width, A4[1])
        block_h = max(posisi_h, eks_table_h)
        posisi_table.drawOn(c, margin, y - posisi_h)
        eks_table.drawOn(c, table_x, y - eks_table_h)
        y -= block_h
        y -= 0.25 * cm

    # ========================================================
    # PENGUJIAN KEMAMPUAN ULANG / REPETABILITY
    # ========================================================
    if repetability_sederhana:
        y -= 0.40 * cm

        nomor_repetability = 3 if is_neraca_obat else 4
        y = gambar_judul_bagian(
            c,
            y,
            nomor_repetability,
            "Pengujian Kemampuan Ulang",
            keterangan_ed_cerapan,
            margin + 6.8 * cm,
            margin,
            font_catatan=font_unicode,
        )

        repet_data = list(data.get("repetability", []) or [])
        while len(repet_data) < 3:
            repet_data.append({})
        repet_data = repet_data[:3]

        penunjukan_akhir_kg: list[float] = []
        for item in repet_data:
            nilai_akhir = item.get(
                "penunjukan_akhir",
                item.get("penunjukan", 0.0),
            )
            penunjukan_akhir_kg.append(to_float(nilai_akhir))

        if penunjukan_akhir_kg:
            r_kg = max(penunjukan_akhir_kg) - min(penunjukan_akhir_kg)
        else:
            r_kg = 0.0

        r_tampil = kg_ke_satuan(r_kg, satuan)
        r_text = format_angka_id(r_tampil)

        semua_sah = all(
            bool(item.get("hasil", True))
            for item in repet_data
        )

        repet_sederhana_rows: list[list[Any]] = [[
            p("Penunjukan timbangan", P_HEADER),
            "",
            p("Cek", P_HEADER),
        ]]

        for idx, item in enumerate(repet_data, start=1):
            akhir = safe_str(
                item.get("penunjukan_akhir_text", "")
            ).strip()

            if not akhir:
                akhir = nilai_dengan_satuan_dari_kg(
                    item.get(
                        "penunjukan_akhir",
                        item.get("penunjukan", 0.0),
                    ),
                    satuan,
                )

            repet_sederhana_rows.append([
                p(f"P{idx}", P_CENTER),
                p(akhir, P_CENTER),
                buat_sel_cek(semua_sah) if idx == 1 else "",
            ])

        repet_sederhana_rows.append([
            p("R = Pmax - Pmin =", P_RIGHT),
            p(r_text, P_CENTER),
            "",
        ])

        # Kolom Cek diperkecil. Subkolom P1/P2/P3 dibuat sedikit
        # lebih lebar daripada subkolom nilai penunjukan.
        lebar_cek = 2.00 * cm
        lebar_penunjukan_total = available_width - lebar_cek
        lebar_p = lebar_penunjukan_total * 0.52
        lebar_nilai = lebar_penunjukan_total * 0.48

        repet_sederhana_table = Table(
            repet_sederhana_rows,
            colWidths=[
                lebar_p,
                lebar_nilai,
                lebar_cek,
            ],
            rowHeights=[
                0.52 * cm,
                0.46 * cm,
                0.46 * cm,
                0.46 * cm,
                0.42 * cm,
            ],
        )

        repet_sederhana_style = style_tabel_umum(
            header_rows=(0,),
            font_size=6.7,
            padding=1.5,
        )

        # Header Penunjukan timbangan mencakup P dan nilai.
        repet_sederhana_style.add("SPAN", (0, 0), (1, 0))

        # Kolom Cek mencakup tiga pengulangan.
        repet_sederhana_style.add("SPAN", (2, 1), (2, 3))

        repet_sederhana_style.add(
            "ALIGN",
            (0, 0),
            (-1, -1),
            "CENTER",
        )
        repet_sederhana_style.add(
            "VALIGN",
            (0, 0),
            (-1, -1),
            "MIDDLE",
        )
        repet_sederhana_style.add(
            "ALIGN",
            (0, 4),
            (0, 4),
            "RIGHT",
        )
        repet_sederhana_style.add(
            "ALIGN",
            (2, 1),
            (2, 3),
            "CENTER",
        )
        repet_sederhana_style.add(
            "VALIGN",
            (2, 1),
            (2, 3),
            "MIDDLE",
        )

        repet_sederhana_table.setStyle(repet_sederhana_style)

        y, _ = gambar_tabel(
            c,
            repet_sederhana_table,
            margin,
            y,
            available_width,
        )
        y -= 0.24 * cm

    else:
        # ========================================================
        # 4. PENGUJIAN KEMAMPUAN ULANG / REPETABILITY
        # ========================================================
        y -= 0.40 * cm

        y = gambar_judul_bagian(
            c,
            y,
            4,
            "Pengujian Kemampuan Ulang",
            "( e = d )",
            margin + 6.8 * cm,
            margin,
            font_catatan=font_unicode,
        )

        # --------------------------------------------------------
        # AMBIL DATA REPETABILITY
        # --------------------------------------------------------
        repet_data = list(data.get("repetability", []) or [])

        # Pastikan selalu tersedia 3 pengulangan
        while len(repet_data) < 3:
            repet_data.append({})

        repet_data = repet_data[:3]

        # --------------------------------------------------------
        # HITUNG R = PMAX - PMIN
        # Menggunakan Penunjukan kedua
        # --------------------------------------------------------
        penunjukan_akhir_kg: list[float] = []

        for item in repet_data:
            nilai_akhir = item.get(
                "penunjukan_akhir",
                item.get("penunjukan", 0.0)
            )

            penunjukan_akhir_kg.append(
                to_float(nilai_akhir)
            )

        if penunjukan_akhir_kg:
            r_kg = max(penunjukan_akhir_kg) - min(penunjukan_akhir_kg)
        else:
            r_kg = 0.0

        r_tampil = kg_ke_satuan(r_kg, satuan)

        # Tampilan tanpa desimal
        r_text = f"{round(r_tampil):,}".replace(",", ".")

        # --------------------------------------------------------
        # HASIL REPETABILITY
        # --------------------------------------------------------
        semua_sah = all(
            bool(item.get("hasil", True))
            for item in repet_data
        )

        cek_repet = "SAH ✓" if semua_sah else "BATAL"

        # --------------------------------------------------------
        # NILAI NAIKKAN 0,5e
        # --------------------------------------------------------
        naik_text = safe_str(
            repet_data[0].get("naik_05e_text", "")
        )

        if not naik_text:
            naik_text = nilai_dengan_satuan_dari_kg(
                repet_data[0].get(
                    "naik_05e",
                    repet_data[0].get("delta_l", 0.0)
                ),
                satuan
            )

        # --------------------------------------------------------
        # HEADER TABEL
        # Jumlah kolom = 10
        # --------------------------------------------------------
        repet_rows: list[list[Any]] = [
            [
                p("Nolkan timbangan", P_SMALL_CENTER),
                p("Naikkan muatan uji", P_SMALL_CENTER),
                p("Penunjukan", P_SMALL_CENTER),
                p("+0,5e", P_SMALL_CENTER),
                p("Periksa", P_SMALL_CENTER),
                "",
                p("Angkat 0,5e dari muatan", P_SMALL_CENTER),
                p("Penunjukan timbangan", P_SMALL_CENTER),
                "",
                p("Cek", P_SMALL_CENTER),
            ]
        ]

        # --------------------------------------------------------
        # DATA 3 PENGULANGAN
        # --------------------------------------------------------
        for idx, item in enumerate(repet_data, start=1):

            # Penunjukan pertama
            awal = safe_str(
                item.get("penunjukan_text", "")
            )

            if not awal:
                awal = nilai_dengan_satuan_dari_kg(
                    item.get("penunjukan", 0.0),
                    satuan
                )

            # Penunjukan kedua
            akhir = safe_str(
                item.get("penunjukan_akhir_text", "")
            )

            if not akhir:
                akhir = nilai_dengan_satuan_dari_kg(
                    item.get(
                        "penunjukan_akhir",
                        item.get("penunjukan", 0.0)
                    ),
                    satuan
                )

            # ----------------------------------------
            # ISI KOLOM PERIKSA
            # ----------------------------------------
            if idx == 1:
                # Baris pertama:
                # kedua subkolom digabung
                periksa_kiri = p(
                    "Berubah ✓",
                    P_SMALL_CENTER
                )

                periksa_kanan = ""

            elif idx == 2:
                # Baris kedua dan ketiga akan digabung vertikal
                periksa_kiri = p(
                    "Tidak berubah",
                    P_SMALL_CENTER
                )

                periksa_kanan = p(
                    "+0,1e sampai penunjukan berubah",
                    P_SMALL_CENTER
                )

            else:
                # Baris ketiga kosong karena mengikuti merge baris kedua
                periksa_kiri = ""
                periksa_kanan = ""

            repet_rows.append([
                "",
                "",
                p(awal, P_CENTER),
                p(naik_text if idx == 1 else "", P_CENTER),
                periksa_kiri,
                periksa_kanan,
                "",
                p(f"P{idx}", P_CENTER),
                p(akhir, P_CENTER),

                # Kolom Cek
                p(
                    "SAH ✓ BATAL" if idx == 1 else "",
                    P_SMALL_CENTER
                ),
            ])

        # --------------------------------------------------------
        # BARIS R = PMAX - PMIN
        # Tetap harus terdiri dari 10 kolom
        # --------------------------------------------------------
        repet_rows.append([
            p("R = Pmax - Pmin =", P_RIGHT),
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            p(r_text, P_CENTER),
            "",
        ])

        # --------------------------------------------------------
        # LEBAR KOLOM
        # Total proporsi = 1,00
        # --------------------------------------------------------
        repet_col_widths = [
            available_width * 0.10,  # 0 Nolkan timbangan
            available_width * 0.10,  # 1 Naikkan muatan uji
            available_width * 0.11,  # 2 Penunjukan pertama
            available_width * 0.06,  # 3 +0,5e
            available_width * 0.09,  # 4 Periksa kiri
            available_width * 0.16,  # 5 Periksa kanan
            available_width * 0.12,  # 6 Angkat 0,5e
            available_width * 0.05,  # 7 P1/P2/P3
            available_width * 0.13,  # 8 Penunjukan kedua
            available_width * 0.08,  # 9 Cek
        ]

        # --------------------------------------------------------
        # BUAT TABEL
        # Header + 3 baris data + 1 baris R
        # --------------------------------------------------------
        repet_table = Table(
            repet_rows,
            colWidths=repet_col_widths,
            rowHeights=[
                0.55 * cm,  # header
                0.46 * cm,  # pengulangan 1
                0.46 * cm,  # pengulangan 2
                0.46 * cm,  # pengulangan 3
                0.42 * cm,  # R = Pmax - Pmin
            ],
        )

        # --------------------------------------------------------
        # STYLE DASAR
        # --------------------------------------------------------
        repet_style = style_tabel_umum(
            header_rows=(0,),
            font_size=6.5,
            padding=1.5
        )

        # --------------------------------------------------------
        # MERGE KOLOM KEGIATAN
        # Tulisan muncul satu kali dan mencakup header + 3 baris data
        # --------------------------------------------------------
        repet_style.add("SPAN", (0, 0), (0, 3))
        repet_style.add("SPAN", (1, 0), (1, 3))
        repet_style.add("SPAN", (6, 0), (6, 3))

        # --------------------------------------------------------
        # KOLOM CEK
        # Header tetap sendiri.
        # Hanya isi baris 1 sampai 3 yang digabung.
        # --------------------------------------------------------
        repet_style.add(
            "SPAN",
            (9, 1),
            (9, 3)
        )

        # Isi Cek diletakkan pada sel pertama area merge,
        # bukan pada header
        repet_rows[1][9] = p(
            "SAH ✓ BATAL" if semua_sah else "SAH ✓  BATAL",
            P_SMALL_CENTER
        )

        # --------------------------------------------------------
        # NAIKKAN 0,5e
        # Nilainya satu kali untuk 3 baris
        # --------------------------------------------------------
        repet_style.add(
            "SPAN",
            (3, 1),
            (3, 3)
        )

        # --------------------------------------------------------
        # HEADER PERIKSA
        # Mencakup 2 subkolom
        # --------------------------------------------------------
        repet_style.add(
            "SPAN",
            (4, 0),
            (5, 0)
        )

        # Berubah memenuhi kedua subkolom pada baris pertama
        repet_style.add(
            "SPAN",
            (4, 1),
            (5, 1)
        )

        # Tidak berubah mencakup baris kedua dan ketiga
        repet_style.add(
            "SPAN",
            (4, 2),
            (4, 3)
        )

        # +0,1e sampai penunjukan berubah
        # mencakup baris kedua dan ketiga
        repet_style.add(
            "SPAN",
            (5, 2),
            (5, 3)
        )

        # --------------------------------------------------------
        # HEADER PENUNJUKAN TIMBANGAN
        # Mencakup kolom P dan nilai
        # --------------------------------------------------------
        repet_style.add(
            "SPAN",
            (7, 0),
            (8, 0)
        )

        # --------------------------------------------------------
        # BARIS R = PMAX - PMIN
        # Tulisan berada di sel pertama hasil merge
        # --------------------------------------------------------
        repet_style.add(
            "SPAN",
            (0, 4),
            (7, 4)
        )

        # --------------------------------------------------------
        # POSISI TEKS
        # --------------------------------------------------------
        repet_style.add(
            "ALIGN",
            (0, 0),
            (-1, -1),
            "CENTER"
        )

        repet_style.add(
            "VALIGN",
            (0, 0),
            (-1, -1),
            "MIDDLE"
        )

        # Tulisan R rata kanan
        repet_style.add(
            "ALIGN",
            (0, 4),
            (7, 4),
            "RIGHT"
        )

        # Isi kolom Cek rata tengah
        repet_style.add(
            "ALIGN",
            (9, 1),
            (9, 3),
            "CENTER"
        )

        repet_style.add(
            "VALIGN",
            (9, 1),
            (9, 3),
            "MIDDLE"
        )

        repet_table.setStyle(repet_style)

        # --------------------------------------------------------
        # GAMBAR TABEL
        # --------------------------------------------------------
        y, _ = gambar_tabel(
            c,
            repet_table,
            margin,
            y,
            available_width
        )

        y -= 0.24 * cm

    # ========================================================
    # PENERA
    # ========================================================
    nama_penera_1 = safe_str(data.get("nama_penera", ""))
    nama_penera_2 = safe_str(data.get("nama_penera_2", ""))

    metoda_text = "ST TBO No. 240 Tahun 2023"
    standar_text = (
        f"Anak timbangan standar kelas "
        f"{safe_str(data.get('at_standar', 'M2'))}"
    )
    telusuran_text = "Direktorat Metrologi Bandung"

        # Lebar kolom METODA, STANDAR DAN TELUSURAN
    lebar_kolom_metoda = available_width - 10.65 * cm

    # Tabel kecil agar tanda titik dua sejajar
    ket_metoda = Table(
        [
            [
                p("Metoda", P_SMALL),
                p(":", P_SMALL_CENTER),
                p(metoda_text, P_SMALL),
            ],
            [
                p("Standar", P_SMALL),
                p(":", P_SMALL_CENTER),
                p(standar_text, P_SMALL),
            ],
            [
                p("Telusuran", P_SMALL),
                p(":", P_SMALL_CENTER),
                p(telusuran_text, P_SMALL),
            ],
        ],
        colWidths=[
            1.35 * cm,
            0.25 * cm,
            lebar_kolom_metoda - 1.60 * cm,
        ],
        rowHeights=[
            0.30 * cm,
            0.30 * cm,
            0.30 * cm,
        ],
    )

    ket_metoda_style = TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),

        # Label dibuat bold
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (-1, -1), "Helvetica"),

        ("FONTSIZE", (0, 0), (-1, -1), 6.8),

        # Hilangkan garis tabel bagian dalam
        ("BOX", (0, 0), (-1, -1), 0, colors.white),
        ("INNERGRID", (0, 0), (-1, -1), 0, colors.white),

        # Jarak dibuat rapat
        ("LEFTPADDING", (0, 0), (-1, -1), 1),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ])

    ket_metoda.setStyle(ket_metoda_style)

    penera_rows = [
        [
            p("PENERA", P_HEADER),
            "",
            "",
            p("KETERANGAN", P_HEADER),
            p("METODA, STANDAR DAN TELUSURAN", P_HEADER),
        ],
        [
            p("No.", P_HEADER),
            p("Nama", P_HEADER),
            p("Paraf", P_HEADER),
            p("SAH", P_CENTER),
            ket_metoda,
        ],
        [
            p("1.", P_CENTER),
            p(nama_penera_1, P_LEFT),
            p("", P_CENTER),
            "",
            "",
        ],
        [
            p("2.", P_CENTER),
            p(nama_penera_2, P_LEFT),
            p("", P_CENTER),
            "",
            "",
        ],
    ]

    penera_table = Table(
        penera_rows,
        colWidths=[
            0.75 * cm,                         # No
            4.20 * cm,                         # Nama
            1.70 * cm,                         # Paraf
            4.00 * cm,                         # Keterangan
            available_width - 10.65 * cm      # Metoda, Standar dan Telusuran
        ],
        rowHeights=[
            0.42 * cm,   # header utama
            0.42 * cm,   # subheader / awal isi
            0.42 * cm,   # penera 1
            0.42 * cm,   # penera 2
        ],
    )

    penera_style = style_tabel_umum(
        header_rows=(0, 1),
        font_size=7.0,
        padding=1.6
    )

    # Hilangkan warna abu-abu pada header
    penera_style.add(
        "BACKGROUND",
        (0, 0),
        (-1, 1),
        colors.white
    )

    # Header "PENERA" span 3 kolom
    penera_style.add("SPAN", (0, 0), (2, 0))

    # Kolom KETERANGAN -> isi SAH digabung 3 baris ke bawah
    penera_style.add("SPAN", (3, 1), (3, 3))

    # Kolom METODA, STANDAR DAN TELUSURAN -> isi digabung 3 baris ke bawah
    penera_style.add("SPAN", (4, 1), (4, 3))

    # Rata tengah untuk seluruh tabel
    penera_style.add("ALIGN", (0, 0), (-1, -1), "CENTER")
    penera_style.add("VALIGN", (0, 0), (-1, -1), "MIDDLE")

    # Nama penera rata kiri
    penera_style.add("ALIGN", (1, 2), (1, 3), "LEFT")

    # Isi kolom metode rata kiri
    penera_style.add("ALIGN", (4, 1), (4, 3), "LEFT")

    # Isi SAH tetap di tengah
    penera_style.add("ALIGN", (3, 1), (3, 3), "CENTER")
    penera_style.add("VALIGN", (3, 1), (3, 3), "MIDDLE")

    penera_table.setStyle(penera_style)

    gambar_tabel(c, penera_table, margin, y, available_width)

    c.save()
    return str(output)