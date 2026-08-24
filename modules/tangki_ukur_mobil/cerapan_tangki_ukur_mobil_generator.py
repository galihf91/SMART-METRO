from pathlib import Path
from datetime import datetime, date
import textwrap

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle


# =========================================================
# PATH
# =========================================================
def find_project_root():
    current = Path(__file__).resolve()

    for parent in [current.parent] + list(current.parents):
        if (parent / "assets").exists():
            return parent

    return current.parents[2]


BASE_DIR = find_project_root()
ASSETS_DIR = BASE_DIR / "assets"
GAMBAR_TUM_PATH = ASSETS_DIR / "gambar_pengukuran_tum.png"


# =========================================================
# HELPER
# =========================================================
BULAN_ID = [
    "Januari", "Februari", "Maret", "April",
    "Mei", "Juni", "Juli", "Agustus",
    "September", "Oktober", "November", "Desember",
]
TERBILANG_KOMPARTEMEN = {
    1: "Satu",
    2: "Dua",
    3: "Tiga",
    4: "Empat",
}
def _bulan_tahun_plus_2(value):
    t = _parse_date(value)

    if not t:
        return ""

    return (
        f"{BULAN_ID[t.month - 1]} "
        f"{t.year + 2}"
    )
def _parse_date(value):
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    text = str(value or "").strip()

    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass

    return None


def _tanggal_indonesia(value):
    tanggal = _parse_date(value)

    if not tanggal:
        return str(value or "")

    return (
        f"{tanggal.day} "
        f"{BULAN_ID[tanggal.month - 1]} "
        f"{tanggal.year}"
    )


def _fmt_number(value, decimals=0):
    if value in ("", None):
        return ""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)

    if decimals == 0:
        if number.is_integer():
            return str(int(number))
        return f"{number:.2f}".rstrip("0").rstrip(".")

    return f"{number:.{decimals}f}".rstrip("0").rstrip(".")


def _draw_wrapped_text(
    c,
    text,
    x,
    y,
    max_width,
    font="Helvetica",
    size=10,
    leading=13,
):
    c.setFont(font, size)

    lines = []

    for paragraph in str(text or "").splitlines() or [""]:
        words = paragraph.split()
        current = ""

        if not words:
            lines.append("")
            continue

        for word in words:
            test = word if not current else f"{current} {word}"

            if c.stringWidth(test, font, size) <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word

        if current:
            lines.append(current)

    if not lines:
        lines = [""]

    yy = y

    for line in lines:
        c.drawString(x, yy, line)
        yy -= leading

    return yy


def _draw_field(
    c,
    label,
    value,
    y,
    label_x=1.7 * cm,
    colon_x=6.0 * cm,
    value_x=6.35 * cm,
    right_x=19.3 * cm,
    font_size=10,
):
    c.setFont("Helvetica", font_size)
    c.drawString(label_x, y, label)
    c.drawString(colon_x, y, ":")

    max_width = right_x - value_x

    new_y = _draw_wrapped_text(
        c,
        value,
        value_x,
        y,
        max_width,
        size=font_size,
        leading=0.42 * cm,
    )

    used_height = max(
        0.48 * cm,
        y - new_y + 0.08 * cm,
    )

    return y - used_height


def _draw_page_title(c, width, title):
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(
        width / 2,
        28.5 * cm,
        title,
    )

    c.setLineWidth(1.2)
    c.line(
        1.5 * cm,
        28.15 * cm,
        width - 1.5 * cm,
        28.15 * cm,
    )

def _get_compartments(data):
    items = data.get(
        "data_kompartemen",
        []
    )

    if not isinstance(items, list):
        items = []

    try:
        jumlah = int(
            data.get(
                "jumlah_kompartemen",
                len(items) or 1
            )
        )
    except (TypeError, ValueError):
        jumlah = 1

    jumlah = max(
        1,
        min(jumlah, 4)
    )

    hasil = []

    for i in range(4):
        aktif = i < jumlah

        if (
            aktif
            and i < len(items)
            and isinstance(
                items[i],
                dict
            )
        ):
            item = dict(
                items[i]
            )
        else:
            item = {}

        item["kompartemen"] = (
            ["I", "II", "III", "IV"][i]
        )

        item["_aktif"] = aktif

        if (
            aktif
            and item.get("T")
            in ("", None)
        ):
            try:
                item["T"] = (
                    float(
                        item.get(
                            "t3",
                            0
                        ) or 0
                    )
                    +
                    float(
                        item.get(
                            "t4",
                            0
                        ) or 0
                    )
                )
            except (
                TypeError,
                ValueError
            ):
                item["T"] = ""

        hasil.append(
            item
        )

    return hasil, jumlah


# =========================================================
# GENERATOR
# =========================================================
def generate_cerapan_tangki_ukur_mobil_pdf(data, filename):
    """
    Membuat Cerapan Pengujian Tangki Ukur Mobil (TUM).

    Data utama yang dibaca dari aplikasi:
    - jenis_cairan
    - isi_nominal
    - merek_tangki
    - tipe_no_seri_tangki
    - merek_kendaraan
    - nomor_chasis_no_mesin / nomor_rangka_no_mesin
    - pemilik
    - alamat
    - metode
    - suhu_dasar
    - nama_penera_1, nip_penera_1
    - nama_penera_2, nip_penera_2 (opsional)
    - tanggal_pengujian
    - masa_berlaku
    - jumlah_kompartemen
    - data_kompartemen
    """

    output_path = Path(filename)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    width, height = A4

    c = canvas.Canvas(
        str(output_path),
        pagesize=A4,
    )

    compartments, jumlah = _get_compartments(data)

    jenis_cairan = str(
        data.get("jenis_cairan", "")
    ).strip()

    nama_alat = str(
        data.get("nama_alat", "")
    ).strip()

    if not nama_alat:
        nama_alat = (
            f'Tangki Ukur untuk cairan "{jenis_cairan}"'
            if jenis_cairan
            else "Tangki Ukur"
        )

    isi_nominal = _fmt_number(
        data.get("isi_nominal", "")
    )

    if isi_nominal:
        isi_nominal = f"{isi_nominal} L"

    tipe_no_seri = str(
        data.get("tipe_no_seri_tangki", "")
    ).strip()

    nomor_chasis_mesin = str(
        data.get(
            "nomor_chasis_no_mesin",
            data.get("nomor_rangka_no_mesin", "")
        )
    ).strip()

    metode = str(
        data.get("metode", "")
    ).strip()

    suhu_dasar = _fmt_number(
        data.get("suhu_dasar", ""),
        1
    )

    metode_suhu = metode

    if suhu_dasar:
        metode_suhu = (
            f"{metode} / {suhu_dasar}°C"
            if metode
            else f"{suhu_dasar}°C"
        )

    tanggal_uji = _tanggal_indonesia(
        data.get(
            "tanggal_pengujian",
            data.get("tanggal", "")
        )
    )

    bulan_tahun_ulang = _bulan_tahun_plus_2(
        data.get(
            "tanggal_pengujian",
            data.get("tanggal", "")
        )
    )

    # =====================================================
    # HALAMAN 1 - IDENTITAS + GAMBAR PENGUKURAN
    # =====================================================
    _draw_page_title(
        c,
        width,
        "PENGUJIAN TANGKI UKUR MOBIL"
    )

    y = 27.5 * cm

    y = _draw_field(
        c,
        "Alat Ukur yang ditera",
        nama_alat,
        y
    )

    y = _draw_field(
        c,
        "Isi Nominal",
        isi_nominal,
        y
    )

    y = _draw_field(
        c,
        "Merek Tangki",
        data.get("merek_tangki", ""),
        y
    )

    y = _draw_field(
        c,
        "Tipe / No Seri Tangki",
        tipe_no_seri,
        y
    )

    y = _draw_field(
        c,
        "Merek Kendaraan",
        data.get("merek_kendaraan", ""),
        y
    )

    y = _draw_field(
        c,
        "Nomor Chasis / No Mesin",
        nomor_chasis_mesin,
        y
    )
    y = _draw_field(
        c,
        "Nomor Polisi",
        data.get("nomor_polisi", ""),
        y
    )
    y = _draw_field(
        c,
        "Pemilik",
        data.get("pemilik", ""),
        y
    )

    y = _draw_field(
        c,
        "Alamat",
        data.get("alamat", ""),
        y
    )

    y = _draw_field(
        c,
        "Metode / Suhu dasar",
        metode_suhu,
        y
    )

    # Penera
    penera_lines = []

    nama_1 = str(
        data.get("nama_penera_1", "")
    ).strip()
    nip_1 = str(
        data.get("nip_penera_1", "")
    ).strip()

    if nama_1:
        teks = f"1. {nama_1}"
        if nip_1:
            teks += f" / NIP. {nip_1}"
        penera_lines.append(teks)

    nama_2 = str(
        data.get("nama_penera_2", "")
    ).strip()
    nip_2 = str(
        data.get("nip_penera_2", "")
    ).strip()

    if nama_2:
        teks = f"2. {nama_2}"
        if nip_2:
            teks += f" / NIP. {nip_2}"
        penera_lines.append(teks)

    y = _draw_field(
        c,
        "Diuji Oleh",
        "\n".join(penera_lines),
        y
    )

    jenis_pengujian = str(
        data.get(
            "jenis_pengujian",
            "Tera"
        )
    ).strip()
    tanggal_uji_obj = _parse_date(
        data.get(
            "tanggal_pengujian",
            data.get("tanggal", "")
        )
    )

    tahun_uji = (
        tanggal_uji_obj.year
        if tanggal_uji_obj
        else date.today().year
    )
    if jenis_pengujian == "Lainnya":
        hasil_teks = (
            f"Telah dilakukan Pengujian Tahun {tahun_uji}"
        )
    else:
        hasil_teks = (
            f"Disahkan untuk {jenis_pengujian} Tahun {tahun_uji}"
        )

    y = _draw_field(
        c,
        "Hasil",
        hasil_teks,
        y
    )
    # Karena _draw_field tidak memproses newline secara khusus,
    # tampilkan ulang penera dengan layout yang lebih rapi jika dua orang.
    if len(penera_lines) > 1:
        # Tutup area penera tadi dengan putih lalu gambar ulang.
        # Posisi dihitung secara aman dari titik sebelum area gambar.
        pass

    y -= 0.10 * cm

    image_top = y
    image_left = 2.0 * cm
    image_right = width - 2.0 * cm

    image_w = image_right - image_left

    # Tinggi maksimum gambar
    max_image_h = 5.0 * cm

    if GAMBAR_TUM_PATH.exists():
        try:
            img = ImageReader(
                str(GAMBAR_TUM_PATH)
            )

            iw, ih = img.getSize()

            ratio = min(
                image_w / iw,
                max_image_h / ih
            )

            draw_w = iw * ratio
            draw_h = ih * ratio

            x = image_left + (
                image_w - draw_w
            ) / 2

            yy = image_top - draw_h

            c.drawImage(
                img,
                x,
                yy,
                width=draw_w,
                height=draw_h,
                preserveAspectRatio=True,
                mask="auto",
            )

            y = yy - 0.60 * cm

        except Exception:
            c.setFont(
                "Helvetica-Oblique",
                9
            )

            c.drawCentredString(
                width / 2,
                y,
                "Gambar pengukuran TUM tidak dapat dibaca."
            )

            y -= 0.8 * cm

    else:
        c.setFont(
            "Helvetica-Oblique",
            9
        )

        c.drawCentredString(
            width / 2,
            y,
            "Gambar pengukuran TUM belum tersedia."
        )

        y -= 0.8 * cm

    teknis_rows = [
        [
            "DATA\nTEKNIS",
            "KOMPARTEMEN (mm)",
            "",
            "",
            "",
        ],
        [
            "",
            "I",
            "II",
            "III",
            "IV",
        ],
    ]

    for field in [
        "t1",
        "t2",
        "t3",
        "t4",
        "T",
        "D",
        "P",
        "Q",
        "S",
    ]:
        row = [field]

        for item in compartments:
            if item.get(
                "_aktif",
                False
            ):
                row.append(
                    _fmt_number(
                        item.get(
                            field,
                            ""
                        )
                    )
                )
            else:
                row.append("")

        teknis_rows.append(
            row
        )

    available_w = 10.5 * cm

    first_col = 2.5 * cm

    other_col = (
        (available_w - first_col)
        / 4
    )

    teknis_table = Table(
        teknis_rows,
        colWidths=[
            first_col,
            other_col,
            other_col,
            other_col,
            other_col,
        ],
        rowHeights=[
            0.42 * cm,  # baris KOMPARTEMEN (mm)
            0.42 * cm,  # baris I II III IV
        ] + [
            0.43 * cm
        ] * 9,
    )

    teknis_table.setStyle(
        TableStyle([
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.7,
                colors.black
            ),

            # Gabungkan DATA TEKNIS secara vertikal
            (
                "SPAN",
                (0, 0),
                (0, 1)
            ),

            # Gabungkan KOMPARTEMEN (mm) di atas I-IV
            (
                "SPAN",
                (1, 0),
                (4, 0)
            ),

            # Header 2 baris
            (
                "BACKGROUND",
                (0, 0),
                (-1, 1),
                colors.HexColor("#E6E6E6")
            ),

            # Kolom nama parameter t1-S
            (
                "BACKGROUND",
                (0, 2),
                (0, -1),
                colors.HexColor("#F2F2F2")
            ),

            # Header bold
            (
                "FONTNAME",
                (0, 0),
                (-1, 1),
                "Helvetica-Bold"
            ),

            # t1, t2, dst bold
            (
                "FONTNAME",
                (0, 2),
                (0, -1),
                "Helvetica-Bold"
            ),

            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                9
            ),

            (
                "ALIGN",
                (0, 0),
                (-1, -1),
                "CENTER"
            ),

            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),

            # Blok kompartemen yang tidak digunakan
            *[
                command
                for i, item in enumerate(compartments)
                if not item.get("_aktif", False)
                for command in [
                    (
                        "BACKGROUND",
                        (i + 1, 2),
                        (i + 1, 10),
                        colors.HexColor("#777777")
                    ),
                    (
                        "TEXTCOLOR",
                        (i + 1, 2),
                        (i + 1, 10),
                        colors.HexColor("#777777")
                    ),
                ]
            ],
        ])
    )

    tw, th = teknis_table.wrap(
        available_w,
        10 * cm
    )

    x_teknis = 1.4 * cm

    teknis_table.drawOn(
        c,
        x_teknis,
        y - th
    )

    y_top_tabel = y

    # =====================================================
    # KEPEKAAN
    # =====================================================
    x_samping = 12.2 * cm

    side_w = width - x_samping - 1.4 * cm

    side_comp = side_w / 4
    side_w = width - x_samping - 1.4 * cm

    side_first = 2.0 * cm

    side_comp = (
        side_w - side_first
    ) / 4
    
    kepekaan_rows = [
        [
            "KEPEKAAN\n(mm/L)",
            "",
            "",
            "",
        ],
        [
            "I",
            "II",
            "III",
            "IV",
        ],
        [
            *[
                (
                    _fmt_number(
                        item.get(
                            "kepekaan",
                            ""
                        ),
                        3
                    )
                    if item.get("_aktif", False)
                    else ""
                )
                for item in compartments
            ]
        ],
    ]

    kepekaan_table = Table(
        kepekaan_rows,
        colWidths=[
            side_comp,
            side_comp,
            side_comp,
            side_comp,
        ],
        rowHeights=[
            0.90 * cm,
            0.45 * cm,
            0.45 * cm,
        ]
    )

    kepekaan_table.setStyle(
        TableStyle([
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.6,
                colors.black
            ),
            (
                "SPAN",
                (0, 0),
                (3, 0)
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, 0),
                4
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, 0),
                4
            ),
            (
                "BACKGROUND",
                (0, 0),
                (-1, 1),
                colors.HexColor("#E6E6E6")
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, 1),
                "Helvetica-Bold"
            ),
            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                8
            ),
            (
                "ALIGN",
                (0, 0),
                (-1, -1),
                "CENTER"
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),

            # blok kompartemen yang tidak digunakan
            *[
                command
                for i, item in enumerate(compartments)
                if not item.get("_aktif", False)
                for command in [
                    (
                        "BACKGROUND",
                        (i, 2),
                        (i, 2),
                        colors.HexColor("#777777")
                    ),
                    (
                        "TEXTCOLOR",
                        (i, 2),
                        (i, 2),
                        colors.HexColor("#777777")
                    ),
                ]
            ],
        ])
    )

    kw, kh = kepekaan_table.wrap(
        available_w,
        3 * cm
    )

    x_samping = 12.2 * cm

    kepekaan_table.drawOn(
        c,
        x_samping,
        y_top_tabel - kh
    )

    # =====================================================
    # RUANG KOSONG
    # =====================================================
    ruang_rows = [
        [
            "RUANG KOSONG\n(L)",
            "",
            "",
            "",
        ],
        [
            "I",
            "II",
            "III",
            "IV",
        ],
        [
            *[
                (
                    _fmt_number(
                        item.get(
                            "ruang_kosong",
                            ""
                        )
                    )
                    if item.get("_aktif", False)
                    else ""
                )
                for item in compartments
            ]
        ],
    ]

    ruang_table = Table(
        ruang_rows,
        colWidths=[
            side_comp,
            side_comp,
            side_comp,
            side_comp,
        ],
        rowHeights=[
            0.90 * cm,
            0.45 * cm,
            0.45 * cm,
        ]
    )

    ruang_table.setStyle(
        TableStyle([
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.6,
                colors.black
            ),
            (
                "SPAN",
                (0, 0),
                (3, 0)
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, 0),
                4
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, 0),
                4
            ),
            (
                "BACKGROUND",
                (0, 0),
                (-1, 1),
                colors.HexColor("#E6E6E6")
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, 1),
                "Helvetica-Bold"
            ),
            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                8
            ),
            (
                "ALIGN",
                (0, 0),
                (-1, -1),
                "CENTER"
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),

            # blok kompartemen yang tidak digunakan
            *[
                command
                for i, item in enumerate(compartments)
                if not item.get("_aktif", False)
                for command in [
                    (
                        "BACKGROUND",
                        (i, 2),
                        (i, 2),
                        colors.HexColor("#777777")
                    ),
                    (
                        "TEXTCOLOR",
                        (i, 2),
                        (i, 2),
                        colors.HexColor("#777777")
                    ),
                ]
            ],
        ])
    )

    rw, rh = ruang_table.wrap(
        available_w,
        3 * cm
    )

    jarak_antar_tabel = 0.35 * cm

    ruang_table.drawOn(
        c,
        x_samping,
        y_top_tabel - kh - jarak_antar_tabel - rh
    )
    y = y_top_tabel - th - 0.55 * cm
    # =====================================================
    # CATATAN
    # =====================================================
    terbilang = TERBILANG_KOMPARTEMEN.get(
        jumlah,
        str(jumlah)
    )
    c.setFont(
        "Helvetica-Bold",
        10
    )
    c.drawString(
        1.7 * cm,
        y,
        "Catatan:"
    )

    y -= 0.5 * cm

    c.setFont(
        "Helvetica",
        9.5
    )

    note_1 = (
        "1. Tangki Ukur Mobil tersebut di atas agar diuji ulang"
    )

    c.drawString(
        2.0 * cm,
        y,
        note_1
    )

    y -= 0.45 * cm

    c.drawString(
        2.6 * cm,
        y,
        f"pada bulan : {bulan_tahun_ulang}"
    )

    y -= 0.5 * cm

    c.drawString(
        2.0 * cm,
        y,
        f"2. Tangki terdiri dari {jumlah} ({terbilang}) kompartemen"
    )

    # =====================================================
    # TANDA TANGAN
    # =====================================================
    y_ttd = max(
        3.0 * cm,
        y - 1.2 * cm
    )

    c.setFont(
        "Helvetica",
        10
    )

    c.drawString(
        12.1 * cm,
        y_ttd,
        f"Tangerang, {tanggal_uji}"
    )

    y_ttd -= 0.5 * cm

    c.drawString(
        12.1 * cm,
        y_ttd,
        "Petugas Metrologi"
    )

    nama_ttd = nama_1

    y_ttd -= 1.7 * cm

    c.setFont(
        "Helvetica-Bold",
        10
    )

    c.drawString(
        12.1 * cm,
        y_ttd,
        nama_ttd
    )

    y_ttd -= 0.42 * cm

    c.setFont(
        "Helvetica",
        9.5
    )

    if nip_1:
        c.drawString(
            12.1 * cm,
            y_ttd,
            f"NIP. {nip_1}"
        )

    c.save()

    return str(output_path)