from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import ImageReader
from datetime import datetime, date
from pathlib import Path


# =========================================================
# PATH PROYEK
# =========================================================
BASE_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = BASE_DIR / "assets"

LOGO_PATH = ASSETS_DIR / "logo.png"


# =========================================================
# FORMAT TANGGAL INDONESIA
# =========================================================

def format_tanggal_indonesia(tanggal):
    if not tanggal:
        return ""

    bulan = [
        "Januari", "Februari", "Maret", "April",
        "Mei", "Juni", "Juli", "Agustus",
        "September", "Oktober", "November", "Desember"
    ]

    if isinstance(tanggal, datetime):
        tanggal = tanggal.date()

    if isinstance(tanggal, date):
        return f"{tanggal.day} {bulan[tanggal.month - 1]} {tanggal.year}"

    tanggal_str = str(tanggal).strip()

    # Format YYYY-MM-DD
    try:
        nilai_tanggal = datetime.strptime(
            tanggal_str,
            "%Y-%m-%d"
        )

        return (
            f"{nilai_tanggal.day} "
            f"{bulan[nilai_tanggal.month - 1]} "
            f"{nilai_tanggal.year}"
        )
    except (ValueError, TypeError):
        pass

    # Sudah berbentuk tanggal Indonesia
    return tanggal_str


def format_tanggal_huruf_besar(tanggal):
    return format_tanggal_indonesia(tanggal).upper()


# =========================================================
# FORMAT NAMA DAN NIP
# =========================================================
def format_nama_tanda_tangan(nama):
    if not nama:
        return ""

    return str(nama).upper()


def format_nip(nip):
    if not nip:
        return ""

    nip_text = str(nip).strip()

    # Menghindari hasil Excel seperti 199102112020121012.0
    if nip_text.endswith(".0"):
        nip_text = nip_text[:-2]

    return nip_text


# =========================================================
# GENERATOR FORM PEMINJAMAN ALAT STANDAR
# =========================================================
def generate_form_peminjaman_standar_timbangan_pdf(
    data,
    filename,
    nomor_surat_perintah="",
    daftar_alat=None
):
    width, height = A4
    c = canvas.Canvas(str(filename), pagesize=A4)

    # =====================================================
    # MARGIN
    # =====================================================
    margin_old = 1.5 * cm
    margin_left_content = 2.0 * cm
    right_limit = width - margin_old

    y = height - 1.2 * cm

    # =====================================================
    # LOGO KOP SURAT
    # =====================================================
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
            print(f"Error logo kop surat: {e}")

    # =====================================================
    # TEKS KOP SURAT
    # =====================================================
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
    c.drawCentredString(
        center_x,
        y,
        (
            "Jl. Atik Soewardi, Gedung Usaha-Usaha Daerah Lt. 3 "
            "Tigaraksa, Tangerang, Banten 15720"
        )
    )
    y -= 0.45 * cm

    c.drawCentredString(
        center_x,
        y,
        (
            "Laman: disperindag.tangerangkab.go.id  "
            "Pos-el: disperindag@tangerangkab.go.id"
        )
    )
    y -= 0.35 * cm

    # =====================================================
    # GARIS GANDA KOP
    # =====================================================
    c.setLineWidth(2)
    c.line(margin_old, y, right_limit, y)

    y -= 0.1 * cm

    c.setLineWidth(0.8)
    c.line(margin_old, y, right_limit, y)

    y -= 0.7 * cm

    # =====================================================
    # JUDUL
    # =====================================================
    c.setFont("Helvetica-Bold", 12)

    judul = "FORMULIR PEMINJAMAN ALAT STANDAR"
    c.drawCentredString(width / 2, y, judul)

    judul_width = c.stringWidth(
        judul,
        "Helvetica-Bold",
        12
    )

    c.line(
        width / 2 - judul_width / 2,
        y - 0.08 * cm,
        width / 2 + judul_width / 2,
        y - 0.08 * cm
    )

    y -= 1.1 * cm

    # =====================================================
    # DATA UTAMA
    # =====================================================
    nama_penera = data.get("nama_penera", "")
    nip_penera = format_nip(data.get("nip_penera", ""))

    nama_perusahaan = (
        data.get("pemilik")
        or data.get("nama_perusahaan")
        or ""
    )

    jenis_pengujian = data.get(
        "keterangan",
        "Tera Ulang"
    )

    tanggal_pengujian = (
        data.get("tanggal")
        or data.get("tanggal_pengujian")
        or data.get("tanggal_penera")
        or datetime.now().strftime("%Y-%m-%d")
    )

    tanggal_teks = format_tanggal_huruf_besar(
        tanggal_pengujian
    )

    # =====================================================
    # IDENTITAS PEMINJAM
    # =====================================================
    x_label = margin_left_content + 0.5 * cm
    x_colon = margin_left_content + 2.8 * cm
    x_value = x_colon + 0.3 * cm

    c.setFont("Helvetica", 11)
    c.drawString(
        x_label,
        y,
        "Yang bertandatangan di bawah ini:"
    )
    y -= 0.65 * cm

    c.drawString(x_label, y, "Nama")
    c.drawString(x_colon, y, ":")
    c.drawString(x_value, y, nama_penera)
    y -= 0.55 * cm

    c.drawString(x_label, y, "NIP")
    c.drawString(x_colon, y, ":")
    c.drawString(x_value, y, nip_penera)
    y -= 0.7 * cm

    # =====================================================
    # PARAGRAF PERMOHONAN
    # =====================================================
    paragraf_permohonan = (
        "Mengajukan permohonan peminjaman Alat Standar untuk "
        f"melaksanakan kegiatan {jenis_pengujian} UTTP di "
        f"{nama_perusahaan} pada tanggal {tanggal_teks} "
        "berdasarkan Surat Perintah Nomor "
        f"{nomor_surat_perintah or '................................'} "
        "dengan rincian sebagai berikut:"
    )

    max_width_paragraf = right_limit - x_label


    def draw_wrapped_text(teks, posisi_y):
        words = str(teks).split()
        current_line = ""
        line_height = 0.5 * cm

        c.setFont("Helvetica", 11)

        for word in words:
            test_line = f"{current_line} {word}".strip()

            if c.stringWidth(
                test_line,
                "Helvetica",
                11
            ) <= max_width_paragraf:
                current_line = test_line

            else:
                if current_line:
                    c.drawString(
                        x_label,
                        posisi_y,
                        current_line
                    )
                    posisi_y -= line_height

                current_line = word

        if current_line:
            c.drawString(
                x_label,
                posisi_y,
                current_line
            )
            posisi_y -= line_height

        return posisi_y


    y = draw_wrapped_text(
        paragraf_permohonan,
        y
    )

    y -= 0.2 * cm

    # =====================================================
    # DATA ALAT STANDAR DARI PILIHAN USER
    # =====================================================
    if daftar_alat is None:
        daftar_alat = data.get(
            "daftar_alat_standar_peminjaman",
            []
        )

        if not isinstance(daftar_alat, list):
            daftar_alat = []

        daftar_alat_valid = []

        for item in daftar_alat:
            if not isinstance(item, dict):
                continue

            jenis_alat = str(
                item.get("jenis_alat", "")
            ).strip()

            if not jenis_alat:
                continue

            jumlah = item.get("jumlah", "")

            if not jumlah:
                try:
                    jumlah_angka = int(
                        item.get("jumlah_angka", 1)
                    )
                except (TypeError, ValueError):
                    jumlah_angka = 1

                satuan = (
                    "Set"
                    if jenis_alat in {"AT M1", "AT F2"}
                    else "Buah"
                )

                jumlah = f"{jumlah_angka} {satuan}"

            daftar_alat_valid.append(
                {
                    "jenis_alat": jenis_alat,
                    "nomor_seri": str(
                        item.get("nomor_seri", "")
                    ),
                    "jumlah": str(jumlah),
                    "lama_peminjaman": str(
                        item.get(
                            "lama_peminjaman",
                            "1 Hari"
                        )
                    ),
                }
            )

        daftar_alat = daftar_alat_valid

        # Fallback untuk data lama.
        if not daftar_alat:
            pilihan_lama = data.get(
                "alat_standar_peminjaman",
                []
            )
            jumlah_lama = data.get(
                "jumlah_alat_standar_peminjaman",
                {}
            )

            if isinstance(pilihan_lama, list):
                for alat in pilihan_lama:
                    alat = str(alat).strip()
                    if not alat:
                        continue

                    try:
                        jumlah_angka = int(
                            jumlah_lama.get(alat, 1)
                        )
                    except (AttributeError, TypeError, ValueError):
                        jumlah_angka = 1

                    satuan = (
                        "Set"
                        if alat in {"AT M1", "AT F2"}
                        else "Buah"
                    )

                    daftar_alat.append(
                        {
                            "jenis_alat": alat,
                            "nomor_seri": "",
                            "jumlah": (
                                f"{jumlah_angka} {satuan}"
                            ),
                            "lama_peminjaman": "1 Hari",
                        }
                    )

        # Fallback terakhir menggunakan AT utama pengujian.
        if not daftar_alat:
            at_standar = str(
                data.get("at_standar", "M2")
            ).strip()

            daftar_alat = [
                {
                    "jenis_alat": f"AT {at_standar}",
                    "nomor_seri": "",
                    "jumlah": "1 Set",
                    "lama_peminjaman": "1 Hari",
                }
            ]

    # =====================================================
    # TABEL
    # =====================================================
    table_data = [
        [
            "No.",
            "Jenis Alat\nStandar",
            "Nomor\nSeri",
            "Jumlah",
            "Lama\nPeminjaman",
            "Paraf\nPeminjaman",
            "Tanggal\nPengembalian",
            "Paraf\nPengembalian"
        ]
    ]

    for nomor in range(1, 16):
        if nomor <= len(daftar_alat):
            alat = daftar_alat[nomor - 1]

            table_data.append([
                str(nomor),
                str(alat.get("jenis_alat", "")),
                str(alat.get("nomor_seri", "")),
                str(alat.get("jumlah", "")),
                str(alat.get("lama_peminjaman", "")),
                "",
                "",
                ""
            ])
        else:
            table_data.append([
                str(nomor),
                "",
                "",
                "",
                "",
                "",
                "",
                ""
            ])

    col_widths = [
        0.75 * cm,
        2.6 * cm,
        1.5 * cm,
        1.45 * cm,
        2.2 * cm,
        2.2 * cm,
        2.35 * cm,
        2.35 * cm
    ]

    tabel = Table(
        table_data,
        colWidths=col_widths,
        rowHeights=[1.15 * cm] + [0.43 * cm] * 15
    )

    tabel.setStyle(
        TableStyle([
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.7,
                colors.black
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica"
            ),
            (
                "FONTNAME",
                (0, 1),
                (-1, -1),
                "Helvetica"
            ),
            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                8.5
            ),
            (
                "ALIGN",
                (0, 0),
                (-1, 0),
                "CENTER"
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),
            (
                "ALIGN",
                (0, 1),
                (0, -1),
                "CENTER"
            ),
            (
                "ALIGN",
                (2, 1),
                (-1, -1),
                "CENTER"
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                3
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                3
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                1
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                1
            )
        ])
    )

    table_width, table_height = tabel.wrapOn(
        c,
        width,
        height
    )

    table_x = (width - table_width) / 2
    table_y = y - table_height

    tabel.drawOn(
        c,
        table_x,
        table_y
    )

    y = table_y - 0.9 * cm

    # =====================================================
    # TANDA TANGAN
    # =====================================================
    penanggung_jawab_nama = data.get(
        "penanggung_jawab_standar_nama",
        "FITRI WAHYUNINGSIH, ST"
    )

    penanggung_jawab_nip = format_nip(
        data.get(
            "penanggung_jawab_standar_nip",
            "198507062010012011"
        )
    )

    x_ttd_kiri = width * 0.29
    x_ttd_kanan = width * 0.74

    c.setFont("Helvetica", 10)

    c.drawCentredString(
        x_ttd_kiri,
        y,
        "Mengetahui,"
    )
    c.drawCentredString(
        x_ttd_kanan,
        y,
        "Pegawai Berhak,"
    )

    y -= 0.45 * cm

    c.drawCentredString(
        x_ttd_kiri,
        y,
        "Penanggung Jawab Alat Standar"
    )

    y_nama = y - 2.2 * cm

    nama_kiri = format_nama_tanda_tangan(
        penanggung_jawab_nama
    )

    nama_kanan = format_nama_tanda_tangan(
        nama_penera
    )

    c.setFont("Helvetica", 10)

    c.drawCentredString(
        x_ttd_kiri,
        y_nama,
        nama_kiri
    )

    c.drawCentredString(
        x_ttd_kanan,
        y_nama,
        nama_kanan
    )

    # Garis bawah nama
    width_nama_kiri = c.stringWidth(
        nama_kiri,
        "Helvetica",
        10
    )

    width_nama_kanan = c.stringWidth(
        nama_kanan,
        "Helvetica",
        10
    )

    c.line(
        x_ttd_kiri - width_nama_kiri / 2,
        y_nama - 0.07 * cm,
        x_ttd_kiri + width_nama_kiri / 2,
        y_nama - 0.07 * cm
    )

    c.line(
        x_ttd_kanan - width_nama_kanan / 2,
        y_nama - 0.07 * cm,
        x_ttd_kanan + width_nama_kanan / 2,
        y_nama - 0.07 * cm
    )

    c.drawCentredString(
        x_ttd_kiri,
        y_nama - 0.4 * cm,
        f"NIP. {penanggung_jawab_nip}"
    )

    c.drawCentredString(
        x_ttd_kanan,
        y_nama - 0.4 * cm,
        f"NIP. {nip_penera}"
    )

    # =====================================================
    # SIMPAN PDF
    # =====================================================
    c.save()

    return str(filename)