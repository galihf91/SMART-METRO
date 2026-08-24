from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Table, TableStyle
from datetime import datetime, date
from pathlib import Path


# =========================================================
# PATH
# =========================================================
BASE_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = BASE_DIR / "assets"

WATERMARK_PATH = ASSETS_DIR / "logo_metrologi.png"
LOGO_PATH = ASSETS_DIR / "logo.png"
GAMBAR_TUM_PATH = ASSETS_DIR / "gambar_pengukuran_tum.png"


# =========================================================
# KONSTANTA
# =========================================================
BULAN_ID = [
    "Januari", "Februari", "Maret", "April",
    "Mei", "Juni", "Juli", "Agustus",
    "September", "Oktober", "November", "Desember",
]

NAMA_KOMPARTEMEN = ["I", "II", "III", "IV"]

TERBILANG_KOMPARTEMEN = {
    1: "Satu",
    2: "Dua",
    3: "Tiga",
    4: "Empat",
}


# =========================================================
# HELPER
# =========================================================
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


def _format_tanggal_indonesia(value):
    t = _parse_date(value)

    if not t:
        return str(value or "")

    return f"{t.day} {BULAN_ID[t.month - 1]} {t.year}"


def _bulan_tahun_plus_2(value):
    t = _parse_date(value)

    if not t:
        return ""

    return f"{BULAN_ID[t.month - 1]} {t.year + 2}"


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
    leading=0.42 * cm,
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
            candidate = (
                word
                if not current
                else f"{current} {word}"
            )

            if (
                c.stringWidth(
                    candidate,
                    font,
                    size
                )
                <= max_width
            ):
                current = candidate

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
        c.drawString(
            x,
            yy,
            line
        )

        yy -= leading

    return yy


def _draw_field(
    c,
    label,
    value,
    y,
    label_x=3.0 * cm,
    colon_x=7.4 * cm,
    value_x=7.7 * cm,
    right_x=19.5 * cm,
    font_size=10,
):
    c.setFont(
        "Helvetica",
        font_size
    )

    c.drawString(
        label_x,
        y,
        label
    )

    c.drawString(
        colon_x,
        y,
        ":"
    )

    new_y = _draw_wrapped_text(
        c,
        value,
        value_x,
        y,
        right_x - value_x,
        font="Helvetica",
        size=font_size,
        leading=0.42 * cm,
    )

    # Jarak antar field
    used_height = max(
        0.46 * cm,
        y - new_y + 0.05 * cm,
    )

    return y - used_height


def _get_compartments(data):
    items = data.get("data_kompartemen", [])

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

    jumlah = max(1, min(jumlah, 4))
    hasil = []

    for i in range(4):
        aktif = i < jumlah

        if (
            aktif
            and i < len(items)
            and isinstance(items[i], dict)
        ):
            item = dict(items[i])
        else:
            item = {}

        item["kompartemen"] = NAMA_KOMPARTEMEN[i]
        item["_aktif"] = aktif

        if aktif and item.get("T") in ("", None):
            try:
                item["T"] = (
                    float(item.get("t3", 0) or 0)
                    + float(item.get("t4", 0) or 0)
                )
            except (TypeError, ValueError):
                item["T"] = ""

        hasil.append(item)

    return hasil, jumlah


def _inactive_dash(item, key, decimals=0):
    if not item.get("_aktif", False):
        return "-"

    value = item.get(key, "")

    if value in ("", None):
        return "-"

    return _fmt_number(value, decimals)


def _draw_header(c, width, height):
    margin = 1.5 * cm
    y = height - 1.2 * cm

    # =====================================================
    # WATERMARK
    # =====================================================
    if WATERMARK_PATH.exists():
        try:
            wm = ImageReader(
                str(WATERMARK_PATH)
            )

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

        except Exception:
            pass

    # =====================================================
    # LOGO KOP
    # =====================================================
    if LOGO_PATH.exists():
        try:
            logo = ImageReader(
                str(LOGO_PATH)
            )

            logo_width = 1.9 * cm
            logo_height = 2.2 * cm

            logo_y = (
                y
                - logo_height
                + 0.45 * cm
            )

            c.drawImage(
                logo,
                margin,
                logo_y,
                width=logo_width,
                height=logo_height,
                mask="auto"
            )

        except Exception:
            pass

    # =====================================================
    # TEKS KOP
    # =====================================================
    offset = 0.4 * cm
    center_x = width / 2 + offset

    c.setFont(
        "Helvetica",
        14
    )

    c.drawCentredString(
        center_x,
        y,
        "PEMERINTAH KABUPATEN TANGERANG"
    )

    y -= 0.8 * cm

    c.setFont(
        "Helvetica-Bold",
        18
    )

    c.drawCentredString(
        center_x,
        y,
        "DINAS PERINDUSTRIAN DAN PERDAGANGAN"
    )

    y -= 0.45 * cm

    c.setFont(
        "Helvetica",
        10
    )

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

    # =====================================================
    # GARIS GANDA
    # =====================================================
    c.setLineWidth(2)

    c.line(
        margin,
        y,
        width - margin,
        y
    )

    y -= 0.1 * cm

    c.setLineWidth(0.8)

    c.line(
        margin,
        y,
        width - margin,
        y
    )

    return y - 0.8 * cm


def _draw_footer(c, width):
    margin = 1.5 * cm
    right_limit = width - margin

    # Garis footer
    c.setLineWidth(0.5)

    c.line(
        margin,
        1.8 * cm,
        right_limit,
        1.8 * cm
    )

    # Teks footer
    c.setFillGray(0)

    c.setFont(
        "Helvetica-Oblique",
        10
    )

    c.drawString(
        margin,
        1.5 * cm,
        "Dilarang menggandakan sebagian dan atau seluruh isi Surat Keterangan Hasil Pengujian ini tanpa seizin dari"
    )

    c.drawString(
        margin,
        1.2 * cm,
        "Bidang Kemetrologian Kabupaten Tangerang"
    )


def _draw_tum_image(c, width, y_top, max_h=6.0 * cm):
    left = 1.6 * cm
    right = width - 1.6 * cm
    available_w = right - left

    if not GAMBAR_TUM_PATH.exists():
        return y_top

    try:
        img = ImageReader(str(GAMBAR_TUM_PATH))
        iw, ih = img.getSize()

        ratio = min(
            available_w / iw,
            max_h / ih
        )

        draw_w = iw * ratio
        draw_h = ih * ratio

        x = left + (available_w - draw_w) / 2
        y = y_top - draw_h

        c.drawImage(
            img,
            x,
            y,
            width=draw_w,
            height=draw_h,
            preserveAspectRatio=True,
            mask="auto",
        )

        return y - 0.25 * cm

    except Exception:
        return y_top


# =========================================================
# GENERATOR SERTIFIKAT TUM
# =========================================================
def generate_sertifikat_tangki_ukur_mobil_pdf(
    data,
    filename,
    nomor_sertifikat=None,
):
    width, height = A4

    output_path = Path(filename)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    c = canvas.Canvas(
        str(output_path),
        pagesize=A4
    )

    compartments, jumlah = _get_compartments(data)

    # =====================================================
    # HEADER
    # =====================================================
    y = _draw_header(
        c,
        width,
        height
    )

    # =====================================================
    # JUDUL SKHP
    # =====================================================
    c.setFont(
        "Helvetica-Bold",
        12.5
    )

    c.drawCentredString(
        width / 2,
        y,
        "SURAT KETERANGAN HASIL PENGUJIAN"
    )

    y -= 0.35 * cm

    nomor_sertifikat = (
        nomor_sertifikat
        or data.get("nomor_sertifikat", "")
    )

    c.setFont(
        "Helvetica",
        10
    )

    c.drawCentredString(
        width / 2,
        y,
        f"Nomor : {nomor_sertifikat}"
    )

    y -= 0.38 * cm

    c.setFont(
        "Helvetica-Bold",
        9.5
    )

    c.drawRightString(
        width - 2.75 * cm,
        y,
        f"No Order : {data.get('nomor_order', '')}"
    )

    y -= 0.90 * cm

    # =====================================================
    # DATA IDENTITAS
    # =====================================================
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

    nomor_chasis_mesin = str(
        data.get(
            "nomor_chasis_no_mesin",
            data.get("nomor_rangka_no_mesin", "")
        )
    ).strip()

    metode = str(
        data.get("metode", "")
    ).strip()

    suhu = _fmt_number(
        data.get("suhu_dasar", ""),
        1
    )

    metode_suhu = metode

    if suhu:
        metode_suhu = (
            f"{metode} / {suhu}°C"
            if metode
            else f"{suhu}°C"
        )

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
        data.get("tipe_no_seri_tangki", ""),
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
        data.get(
            "nama_penera_1",
            data.get("nama_penera", "")
        )
    ).strip()

    nip_1 = str(
        data.get(
            "nip_penera_1",
            data.get("nip_penera", "")
        )
    ).strip()

    if nama_1:
        text = f"1. {nama_1}"

        if nip_1:
            text += f" / NIP. {nip_1}"

        penera_lines.append(text)

    nama_2 = str(
        data.get("nama_penera_2", "")
    ).strip()

    nip_2 = str(
        data.get("nip_penera_2", "")
    ).strip()

    if nama_2:
        text = f"2. {nama_2}"

        if nip_2:
            text += f" / NIP. {nip_2}"

        penera_lines.append(text)

    y = _draw_field(
        c,
        "Diuji oleh",
        "\n".join(penera_lines),
        y
    )

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

    jenis_pengujian = str(
        data.get(
            "jenis_pengujian",
            data.get("keterangan", "Tera")
        )
    ).strip() or "Tera"

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

    # =====================================================
    # GAMBAR TUM
    # =====================================================
    y -= 0.05 * cm

    y = _draw_tum_image(
        c,
        width,
        y,
        max_h=6.0 * cm
    )

    # =====================================================
    # TABEL DATA TEKNIS
    # =====================================================
    table_top = y

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
        "t1", "t2", "t3", "t4",
        "T", "D", "P", "Q", "S",
    ]:
        teknis_rows.append(
            [
                field,
                *[
                    _inactive_dash(
                        item,
                        field,
                        0
                    )
                    for item in compartments
                ]
            ]
        )

    teknis_w = 8.5 * cm
    first_col = 1.9 * cm
    other_col = (
        teknis_w - first_col
    ) / 4

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
            0.60 * cm,
            0.45 * cm,
        ] + [
            0.38 * cm
        ] * 9,
    )

    teknis_table.setStyle(
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
                (0, 1)
            ),
            (
                "SPAN",
                (1, 0),
                (4, 0)
            ),
            (
                "BACKGROUND",
                (0, 0),
                (-1, 1),
                colors.HexColor("#E6E6E6")
            ),
            (
                "BACKGROUND",
                (0, 2),
                (0, -1),
                colors.HexColor("#F2F2F2")
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, 1),
                "Helvetica-Bold"
            ),
            (
                "FONTNAME",
                (0, 2),
                (0, -1),
                "Helvetica-Bold"
            ),
            # NILAI & TANDA "-" TIDAK BOLD
            (
                "FONTNAME",
                (1, 2),
                (-1, -1),
                "Helvetica"
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
        ])
    )

    tw, th = teknis_table.wrap(
        teknis_w,
        10 * cm
    )

    x_teknis = 2.3 * cm

    teknis_table.drawOn(
        c,
        x_teknis,
        table_top - th
    )

    # =====================================================
    # TABEL KEPEKAAN & RUANG KOSONG
    # =====================================================
    x_samping = 11.8 * cm
    side_w = 6.2 * cm
    side_comp = side_w / 4

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
                _inactive_dash(
                    item,
                    "kepekaan",
                    3
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
            1.05 * cm,
            0.42 * cm,
            0.42 * cm,
        ],
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
            # BARIS NILAI, TERMASUK "-" = NORMAL
            (
                "FONTNAME",
                (0, 2),
                (-1, 2),
                "Helvetica"
            ),
            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                7.6
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
        ])
    )

    kw, kh = kepekaan_table.wrap(
        side_w,
        3 * cm
    )

    kepekaan_table.drawOn(
        c,
        x_samping,
        table_top - kh
    )

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
                _inactive_dash(
                    item,
                    "ruang_kosong",
                    0
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
            1.05 * cm,
            0.42 * cm,
            0.42 * cm,
        ],
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
            # BARIS NILAI, TERMASUK "-" = NORMAL
            (
                "FONTNAME",
                (0, 2),
                (-1, 2),
                "Helvetica"
            ),
            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                7.6
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
        ])
    )

    rw, rh = ruang_table.wrap(
        side_w,
        3 * cm
    )

    gap = 0.30 * cm

    ruang_table.drawOn(
        c,
        x_samping,
        table_top - kh - gap - rh
    )

    # =====================================================
    # CATATAN
    # =====================================================
    y = table_top - th - 0.40 * cm

    c.setFont(
        "Helvetica-Bold",
        9
    )

    c.drawString(
        3.0 * cm,
        y,
        "Catatan:"
    )

    y -= 0.42 * cm

    c.setFont(
        "Helvetica",
        9
    )

    bulan_tahun_ulang = _bulan_tahun_plus_2(
        data.get(
            "tanggal_pengujian",
            data.get("tanggal", "")
        )
    )

    c.drawString(
        3.2 * cm,
        y,
        "1. Tangki Ukur Mobil tersebut di atas agar diuji"
    )

    y -= 0.40 * cm

    c.drawString(
        3.65 * cm,
        y,
        f"ulang pada bulan : {bulan_tahun_ulang}"
    )

    y -= 0.45 * cm

    terbilang = TERBILANG_KOMPARTEMEN.get(
        jumlah,
        str(jumlah)
    )

    c.drawString(
        3.2 * cm,
        y,
        f"2. Tangki terdiri dari {jumlah} ({terbilang}) kompartemen"
    )

    # =====================================================
    # TANDA TANGAN KEPALA BIDANG
    # =====================================================
    tanggal_sertifikat = _format_tanggal_indonesia(
        data.get(
            "tanggal_tanda_tangan",
            data.get(
                "tanggal_pengujian",
                data.get("tanggal", "")
            )
        )
    )

    x_ttd = 11.8 * cm

    # Posisi tanda tangan dibuat sedikit lebih turun
    y_ttd = y - 0.15 * cm

    c.setFont(
        "Helvetica",
        10
    )

    c.drawString(
        x_ttd,
        y_ttd,
        f"Tangerang, {tanggal_sertifikat}"
    )

    y_ttd -= 0.45 * cm

    c.drawString(
        x_ttd,
        y_ttd,
        "KEPALA BIDANG KEMETROLOGIAN"
    )

    y_ttd -= 0.42 * cm

    c.drawString(
        x_ttd,
        y_ttd,
        "KABUPATEN TANGERANG"
    )

    # Ruang tanda tangan
    y_ttd -= 1.80 * cm

    c.setFont(
        "Helvetica",
        10
    )

    c.drawString(
        x_ttd,
        y_ttd,
        "Priatin Saputra, S.Kom.,M.Si"
    )

    y_ttd -= 0.42 * cm

    c.setFont(
        "Helvetica",
        10
    )

    c.drawString(
        x_ttd,
        y_ttd,
        "Penata Tk. I (III/d)"
    )

    y_ttd -= 0.42 * cm

    c.drawString(
        x_ttd,
        y_ttd,
        "NIP. 198505152011011004"
    )

    # =====================================================
    # FOOTER
    # =====================================================
    _draw_footer(
        c,
        width
    )

    c.save()

    return str(output_path)
