
from pathlib import Path
from datetime import datetime, date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)


def _format_tanggal_indonesia(value):
    if not value:
        return ""

    if isinstance(value, datetime):
        value = value.date()

    if isinstance(value, str):
        try:
            value = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return value

    if not isinstance(value, date):
        return str(value)

    bulan = [
        "Januari", "Februari", "Maret", "April",
        "Mei", "Juni", "Juli", "Agustus",
        "September", "Oktober", "November", "Desember",
    ]

    return f"{value.day} {bulan[value.month - 1]} {value.year}"


def _fmt_number(value, decimals=3, strip_zero=True):
    if value in (None, ""):
        return ""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)

    text = f"{number:.{decimals}f}"

    # Hapus nol desimal hanya jika memang ada angka desimal
    if strip_zero and decimals > 0:
        text = text.rstrip("0").rstrip(".")

    return text


def _p(text, style):
    return Paragraph(str(text or ""), style)


def generate_cerapan_meter_air_pdf(data, output_path):
    """
    Membuat PDF Cerapan Pengujian Meter Air berdasarkan template
    'Cerapan Meter Air.xlsx'.

    Struktur data utama yang dibaca:
    - pemilik, alamat
    - tanggal_pengujian / tanggal
    - nomor_order
    - merek
    - model_tipe / model
    - nomor_seri / no_seri
    - kapasitas
    - diameter
    - kelas
    - masa_berlaku / masa_berlaku_indonesia
    - bejana_merek
    - bejana_tipe
    - bejana_nomor_seri
    - bejana_volume_nominal
    - bejana_koefisien_muai
    - bejana_sb
    - bejana_waktu_tetesan
    - jenis_cairan
    - hasil_pengujian: list 3 dict
    - hasil_akhir / hasil
    - nama_penera / penera_1
    """

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    page_width, page_height = A4

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=1.0 * cm,
        rightMargin=1.0 * cm,
        topMargin=0.8 * cm,
        bottomMargin=0.8 * cm,
    )

    styles = {
        "title": ParagraphStyle(
            "title",
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=15,
            alignment=TA_CENTER,
        ),
        "label": ParagraphStyle(
            "label",
            fontName="Helvetica",
            fontSize=9,
            leading=10.5,
            alignment=TA_LEFT,
        ),
        "label_bold": ParagraphStyle(
            "label_bold",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=10.5,
            alignment=TA_LEFT,
        ),
        "small": ParagraphStyle(
            "small",
            fontName="Helvetica",
            fontSize=8,
            leading=9,
            alignment=TA_LEFT,
        ),
        "small_center": ParagraphStyle(
            "small_center",
            fontName="Helvetica",
            fontSize=8,
            leading=9,
            alignment=TA_CENTER,
        ),
        "small_bold": ParagraphStyle(
            "small_bold",
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=9,
            alignment=TA_LEFT,
        ),
        "small_bold_center": ParagraphStyle(
            "small_bold_center",
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=9,
            alignment=TA_CENTER,
        ),
        "result": ParagraphStyle(
            "result",
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=11,
            alignment=TA_CENTER,
        ),
    }

    story = []

    # =====================================================
    # HEADER / JUDUL
    # =====================================================
    header = Table(
        [
            [
                _p(
                    "CERAPAN PENGUJIAN METER AIR",
                    styles["title"]
                )
            ]
        ],
        colWidths=[19.0 * cm],
        rowHeights=[0.7 * cm],
    )

    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    story.append(header)

    # =====================================================
    # GARIS PEMISAH JUDUL DAN ISI
    # =====================================================
    garis_judul = Table(
        [[""]],
        colWidths=[19.0 * cm],
        rowHeights=[0.12 * cm],
    )

    garis_judul.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, 0), (-1, 0), 1.6, colors.black),
                ("LINEBELOW", (0, 0), (-1, 0), 0.55, colors.black),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    story.append(garis_judul)
    story.append(Spacer(1, 0.18 * cm))

    # =====================================================
    # IDENTITAS
    # =====================================================
    tanggal_pengujian = (
        data.get("tanggal_penera")
        or _format_tanggal_indonesia(
            data.get("tanggal_pengujian")
            or data.get("tanggal")
        )
    )

    identitas = Table(
        [
            [
                _p("Pemilik", styles["label"]),
                _p(":", styles["label"]),
                _p(data.get("pemilik", ""), styles["label"]),
            ],
            [
                _p("Alamat", styles["label"]),
                _p(":", styles["label"]),
                _p(data.get("alamat", ""), styles["label"]),
            ],
            [
                _p("Tanggal Pengujian", styles["label"]),
                _p(":", styles["label"]),
                _p(tanggal_pengujian, styles["label"]),
            ],
        ],
        colWidths=[
            3.7 * cm,
            0.35 * cm,
            14.95 * cm,
        ],
        rowHeights=[
            0.48 * cm,
            0.62 * cm,
            0.48 * cm,
        ],
    )

    identitas.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )

    story.append(identitas)
    story.append(Spacer(1, 0.12 * cm))

    # =====================================================
    # DATA METER AIR + DATA BEJANA UKUR
    # =====================================================
    masa_berlaku = (
        data.get("masa_berlaku_indonesia")
        or _format_tanggal_indonesia(
            data.get("masa_berlaku")
        )
    )

    bejana_tipe_no_seri = (
        data.get("bejana_tipe_no_seri")
        or " / ".join(
            value
            for value in [
                str(data.get("bejana_tipe", "")).strip(),
                str(data.get("bejana_nomor_seri", "")).strip(),
            ]
            if value
        )
    )

    info_data = [
        [
            _p("DATA METER AIR", styles["label_bold"]),
            "",
            "",
            _p("DATA BEJANA UKUR", styles["label_bold"]),
            "",
            "",
        ],
        [
            _p("Merek", styles["label"]),
            _p(":", styles["label"]),
            _p(data.get("merek", ""), styles["label"]),
            _p("Merek", styles["label"]),
            _p(":", styles["label"]),
            _p(data.get("bejana_merek", ""), styles["label"]),
        ],
        [
            _p("Model/ tipe", styles["label"]),
            _p(":", styles["label"]),
            _p(
                data.get("model_tipe")
                or data.get("model", ""),
                styles["label"],
            ),
            _p("Tipe/No. Seri", styles["label"]),
            _p(":", styles["label"]),
            _p(bejana_tipe_no_seri, styles["label"]),
        ],
        [
            _p("No. Seri", styles["label"]),
            _p(":", styles["label"]),
            _p(
                data.get("nomor_seri")
                or data.get("no_seri", ""),
                styles["label"],
            ),
            _p("Volume Nominal", styles["label"]),
            _p(":", styles["label"]),
            _p(data.get("bejana_volume_nominal", ""), styles["label"]),
        ],
        [
            _p("Kapasitas", styles["label"]),
            _p(":", styles["label"]),
            _p(
                f"{data.get('kapasitas', '')} m³/h"
                if str(data.get("kapasitas", "")).strip()
                else "",
                styles["label"],
            ),
            _p("Koefisien Muai Bahan (α)", styles["label"]),
            _p(":", styles["label"]),
            _p(data.get("bejana_koefisien_muai", ""), styles["label"]),
        ],
        [
            _p("Diameter", styles["label"]),
            _p(":", styles["label"]),
            _p(
                f"{data.get('diameter', '')} mm"
                if str(data.get("diameter", "")).strip()
                else "",
                styles["label"],
            ),
            _p("Kesalahan Penunjukan (SB)", styles["label"]),
            _p(":", styles["label"]),
            _p(
                _fmt_number(data.get("bejana_sb", ""), 3),
                styles["label"],
            ),
        ],
        [
            _p("Kelas", styles["label"]),
            _p(":", styles["label"]),
            _p(data.get("kelas", ""), styles["label"]),
            _p("Waktu Tetesan", styles["label"]),
            _p(":", styles["label"]),
            _p(data.get("bejana_waktu_tetesan", ""), styles["label"]),
        ],
        [
            _p("Masa Berlaku", styles["label"]),
            _p(":", styles["label"]),
            _p(masa_berlaku, styles["label"]),
            "",
            "",
            "",
        ],
    ]

    info = Table(
        info_data,
        colWidths=[
            3.55 * cm,
            0.28 * cm,
            5.65 * cm,
            4.9 * cm,
            0.28 * cm,
            4.35 * cm,
        ],
        rowHeights=[
            0.48 * cm,
            0.45 * cm,
            0.48 * cm,
            0.45 * cm,
            0.48 * cm,
            0.48 * cm,
            0.45 * cm,
            0.45 * cm,
        ],
    )

    info.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (2, 0)),
                ("SPAN", (3, 0), (5, 0)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    story.append(info)
    story.append(Spacer(1, 0.08 * cm))

    # =====================================================
    # CAIRAN UJI
    # =====================================================
    cairan = Table(
        [
            [
                _p("CAIRAN UJI", styles["label_bold"]),
                "",
                "",
            ],
            [
                _p("Jenis Cairan", styles["label"]),
                _p(":", styles["label"]),
                _p(data.get("jenis_cairan", "Air"), styles["label"]),
            ],
        ],
        colWidths=[
            3.7 * cm,
            0.35 * cm,
            14.95 * cm,
        ],
        rowHeights=[
            0.45 * cm,
            0.45 * cm,
        ],
    )

    cairan.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (2, 0)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    story.append(cairan)
    story.append(Spacer(1, 0.10 * cm))

    # =====================================================
    # TABEL HASIL PENGUJIAN
    # =====================================================
    hasil = data.get("hasil_pengujian", [])

    while len(hasil) < 3:
        hasil.append({})

    uji1, uji2, uji3 = hasil[:3]

    def gv(item, key, decimals=3):
        return _fmt_number(item.get(key, ""), decimals)
    
    def gv_blank_zero(item, key, decimals=3):
        value = item.get(key, "")

        if value in ("", None):
            return ""

        try:
            if float(value) == 0:
                return ""
        except (TypeError, ValueError):
            pass

        return _fmt_number(
            value,
            decimals
        )

    table_data = [
        [
            _p("No.", styles["small_bold_center"]),
            _p("URAIAN", styles["small_bold_center"]),
            _p("SATUAN", styles["small_bold_center"]),
            _p("Pengujian ke :", styles["small_bold_center"]),
            "",
            "",
        ],
        [
            "",
            "",
            "",
            _p("1", styles["small_bold_center"]),
            _p("2", styles["small_bold_center"]),
            _p("3", styles["small_bold_center"]),
        ],
        [
            "",
            _p("Kecepatan Alir", styles["small_bold"]),
            _p("L/h", styles["small_center"]),
            _p(gv(uji1, "kecepatan_alir", 0), styles["small_center"]),
            _p(gv(uji2, "kecepatan_alir", 0), styles["small_center"]),
            _p(gv(uji3, "kecepatan_alir", 0), styles["small_center"]),
        ],
        [
            "",
            _p("Bejana Ukur", styles["small_bold"]),
            "",
            "",
            "",
            "",
        ],
        [
            "1",
            _p("Pembacaan Akhir (Vb2)", styles["small"]),
            _p("L", styles["small_center"]),
            _p(gv(uji1, "vb2"), styles["small_center"]),
            _p(gv(uji2, "vb2"), styles["small_center"]),
            _p(gv(uji3, "vb2"), styles["small_center"]),
        ],
        [
            "2",
            _p("Pembacaan Awal (Vb1)", styles["small"]),
            _p("L", styles["small_center"]),
            _p(gv(uji1, "vb1"), styles["small_center"]),
            _p(gv(uji2, "vb1"), styles["small_center"]),
            _p(gv(uji3, "vb1"), styles["small_center"]),
        ],
        [
            "3",
            _p("Volume yang diukur Vb=(1) - (2)", styles["small"]),
            _p("L", styles["small_center"]),
            _p(gv(uji1, "vb"), styles["small_center"]),
            _p(gv(uji2, "vb"), styles["small_center"]),
            _p(gv(uji3, "vb"), styles["small_center"]),
        ],
        [
            "",
            _p("Meter Air", styles["small_bold"]),
            "",
            "",
            "",
            "",
        ],
        [
            "4",
            _p("Pembacaan Akhir", styles["small"]),
            _p("L", styles["small_center"]),
            _p(gv(uji1, "pembacaan_akhir_meter"), styles["small_center"]),
            _p(gv(uji2, "pembacaan_akhir_meter"), styles["small_center"]),
            _p(gv(uji3, "pembacaan_akhir_meter"), styles["small_center"]),
        ],
        [
            "5",
            _p("Vm2 = 4 - SB", styles["small"]),
            _p("L", styles["small_center"]),
            _p(gv(uji1, "vm2"), styles["small_center"]),
            _p(gv(uji2, "vm2"), styles["small_center"]),
            _p(gv(uji3, "vm2"), styles["small_center"]),
        ],
        [
            "6",
            _p("Pembacaan Awal = Vm1", styles["small"]),
            _p("L", styles["small_center"]),
            _p(gv(uji1, "vm1"), styles["small_center"]),
            _p(gv(uji2, "vm1"), styles["small_center"]),
            _p(gv(uji3, "vm1"), styles["small_center"]),
        ],
        [
            "7",
            _p(
                "Volume yang diukur<br/>Vm = 5 - 6 (Vm2 - Vm1)",
                styles["small"],
            ),
            _p("L", styles["small_center"]),
            _p(gv(uji1, "vm"), styles["small_center"]),
            _p(gv(uji2, "vm"), styles["small_center"]),
            _p(gv(uji3, "vm"), styles["small_center"]),
        ],
        [
            "8",
            _p("Suhu (Tm)", styles["small"]),
            _p("°C", styles["small_center"]),
            _p(gv(uji1, "suhu", 1), styles["small_center"]),
            _p(gv(uji2, "suhu", 1), styles["small_center"]),
            _p(gv(uji3, "suhu", 1), styles["small_center"]),
        ],
        [
            "9",
            _p("Tekanan (Pm)", styles["small"]),
            _p("kPa (kg/cm²)", styles["small_center"]),
            _p(gv(uji1, "tekanan", 2), styles["small_center"]),
            _p(gv(uji2, "tekanan", 2), styles["small_center"]),
            _p(gv(uji3, "tekanan", 2), styles["small_center"]),
        ],
        [
            "10",
            _p("Kesalahan Meter Air", styles["small"]),
            _p("%", styles["small_center"]),
            _p(gv(uji1, "kesalahan_meter_air", 2), styles["small_center"]),
            _p(gv(uji2, "kesalahan_meter_air", 2), styles["small_center"]),
            _p(gv(uji3, "kesalahan_meter_air", 2), styles["small_center"]),
        ],
        [
            "11",
            _p("BKD", styles["small"]),
            _p("%", styles["small_center"]),
            _p(gv(uji1, "bkd", 2), styles["small_center"]),
            _p(gv(uji2, "bkd", 2), styles["small_center"]),
            _p(gv(uji3, "bkd", 2), styles["small_center"]),
        ],
        [
            "12",
            _p("Ketidaktetapan", styles["small"]),
            _p("%", styles["small_center"]),
            _p(
                gv_blank_zero(
                    uji1,
                    "ketidaktetapan",
                    3
                ),
                styles["small_center"],
            ),
            _p(
                gv_blank_zero(
                    uji2,
                    "ketidaktetapan",
                    3
                ),
                styles["small_center"],
            ),
            _p(
                gv_blank_zero(
                    uji3,
                    "ketidaktetapan",
                    3
                ),
                styles["small_center"],
            ),
        ],
        [
            "13",
            _p(
                "Kepekaan (khusus Dn=15mm)",
                styles["small"]
            ),
            _p(
                "L/min",
                styles["small_center"]
            ),
            _p(
                gv_blank_zero(
                    uji1,
                    "kepekaan",
                    3
                ),
                styles["small_center"],
            ),
            _p(
                gv_blank_zero(
                    uji2,
                    "kepekaan",
                    3
                ),
                styles["small_center"],
            ),
            _p(
                gv_blank_zero(
                    uji3,
                    "kepekaan",
                    3
                ),
                styles["small_center"],
            ),
        ],
    ]

    hasil_table = Table(
        table_data,
        colWidths=[
            1.0 * cm,
            8.3 * cm,
            2.15 * cm,
            2.55 * cm,
            2.55 * cm,
            2.55 * cm,
        ],
        rowHeights=[
            0.55 * cm,
            0.45 * cm,
            0.48 * cm,
            0.46 * cm,
            0.45 * cm,
            0.45 * cm,
            0.45 * cm,
            0.46 * cm,
            0.45 * cm,
            0.45 * cm,
            0.45 * cm,
            0.65 * cm,
            0.45 * cm,
            0.50 * cm,
            0.45 * cm,
            0.45 * cm,
            0.45 * cm,
            0.45 * cm,
        ],
        repeatRows=2,
    )

    hasil_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.7, colors.black),
                ("SPAN", (0, 0), (0, 1)),
                ("SPAN", (1, 0), (1, 1)),
                ("SPAN", (2, 0), (2, 1)),
                ("SPAN", (3, 0), (5, 0)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (2, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                # Highlight baris hasil utama
                ("BACKGROUND", (0, 6), (-1, 6), colors.lightgrey),
                ("BACKGROUND", (0, 11), (-1, 11), colors.lightgrey),
                ("BACKGROUND", (0, 14), (-1, 14), colors.lightgrey),

                # Bold agar lebih jelas
                ("FONTNAME", (0, 6), (-1, 6), "Helvetica-Bold"),
                ("FONTNAME", (0, 11), (-1, 11), "Helvetica-Bold"),
                ("FONTNAME", (0, 14), (-1, 14), "Helvetica-Bold"),
            ]
        )
    )

    story.append(hasil_table)

    # =====================================================
    # KETERANGAN + HASIL
    # =====================================================
    hasil_akhir = (
        data.get("hasil_akhir")
        or data.get("hasil")
        or ""
    )

    ket_table = Table(
        [
            [
                _p("Keterangan :", styles["label"]),
            ],
            [
                _p(hasil_akhir, styles["result"]),
            ],
        ],
        colWidths=[19.1 * cm],
        rowHeights=[
            0.65 * cm,
            0.85 * cm,
        ],
    )

    ket_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.7, colors.black),
                ("LINEBELOW", (0, 0), (-1, 0), 0.7, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )

    story.append(ket_table)
    story.append(Spacer(1, 0.18 * cm))

    # =====================================================
    # PENERA
    # =====================================================
    nama_penera = (
        data.get("nama_penera")
        or data.get("penera_1")
        or ""
    )

    penera_table = Table(
        [
            [
                _p("PENERA", styles["label_bold"]),
                "",
                "",
            ],
            [
                _p("No.", styles["label"]),
                _p("Nama", styles["label"]),
                _p("Paraf", styles["label"]),
            ],
            [
                _p("1.", styles["label"]),
                _p(nama_penera, styles["label"]),
                "",
            ],
        ],
        colWidths=[
            1.6 * cm,
            6.5 * cm,
            4.2 * cm,
        ],
        rowHeights=[
            0.45 * cm,
            0.45 * cm,
            0.55 * cm,
        ],
    )

    penera_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.7, colors.black),
                ("SPAN", (0, 0), (2, 0)),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )

    story.append(penera_table)

    doc.build(story)

    return str(output_path)


# Alias opsional agar mudah dipakai bila suatu modul lama memakai nama generik.
generate_cerapan_pdf = generate_cerapan_meter_air_pdf
