import streamlit as st
import pandas as pd
from supabase import create_client
from modules.pubbm.sertifikat_pubbm_generator import generate_sertifikat_pubbm
from modules.timbangan_jembatan.form_peminjaman_standar_generator import (
    generate_form_peminjaman_standar_pdf,
)
from modules.timbangan_jembatan.form_peminjaman_ctt_generator import (
    generate_form_peminjaman_ctt_pdf,
)
from datetime import date, datetime
import re
from pathlib import Path

OPSI_MEDIA_MANUAL = "✍️ Input Media Manual"
# =========================================================
# SUPABASE PUBBM
# =========================================================
def get_supabase_pubbm():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]

    return create_client(
        url,
        key
    )
def simpan_atau_update_perusahaan_pubbm(
    supabase,
    nama_perusahaan,
    alamat,
):
    nama_perusahaan = str(
        nama_perusahaan or ""
    ).strip()

    alamat = str(
        alamat or ""
    ).strip()

    if not nama_perusahaan:
        raise ValueError(
            "Nama SPBU / perusahaan belum diisi."
        )

    # =====================================================
    # CARI PERUSAHAAN BERDASARKAN NAMA
    # =====================================================
    response = (
        supabase
        .table("perusahaan")
        .select(
            "id, nama_perusahaan, alamat"
        )
        .eq(
            "nama_perusahaan",
            nama_perusahaan
        )
        .execute()
    )

    # =====================================================
    # PERUSAHAAN SUDAH ADA
    # =====================================================
    if response.data:
        perusahaan = response.data[0]

        perusahaan_id = perusahaan[
            "id"
        ]

        alamat_lama = str(
            perusahaan.get(
                "alamat",
                ""
            )
            or ""
        ).strip()

        # Update alamat jika berubah
        if (
            alamat
            and alamat != alamat_lama
        ):
            (
                supabase
                .table("perusahaan")
                .update({
                    "alamat": alamat
                })
                .eq(
                    "id",
                    perusahaan_id
                )
                .execute()
            )

        return perusahaan_id

    # =====================================================
    # PERUSAHAAN BARU
    # =====================================================
    response = (
        supabase
        .table("perusahaan")
        .insert({
            "nama_perusahaan": nama_perusahaan,
            "alamat": alamat,
        })
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Data SPBU / perusahaan gagal disimpan."
        )

    return response.data[0]["id"]
def get_or_create_uttp_pubbm(
    supabase,
    perusahaan_id,
    nomor_spbu,
    pemilik,
):
    """
    Konsep PUBBM:
    1 UTTP = 1 SPBU.

    Prioritas identitas:
    1. Nomor SPBU jika tersedia
    2. Nama pemilik/SPBU jika nomor tidak tersedia
    """

    nomor_spbu = str(
        nomor_spbu or ""
    ).strip()

    pemilik = str(
        pemilik or ""
    ).strip()

    # =====================================================
    # IDENTITAS UTAMA
    # =====================================================
    identifier = (
        nomor_spbu
        if nomor_spbu
        else pemilik
    )

    if not identifier:
        raise ValueError(
            "Identitas SPBU belum tersedia."
        )

    identifier_normal = (
        normalisasi_identitas_spbu(
            identifier
        )
    )

    # =====================================================
    # CARI SEMUA UTTP PUBBM MILIK PERUSAHAAN INI
    # =====================================================
    response = (
        supabase
        .table("uttp")
        .select("*")
        .eq(
            "perusahaan_id",
            perusahaan_id
        )
        .eq(
            "jenis_uttp",
            "Pompa Ukur BBM"
        )
        .execute()
    )

    daftar_uttp = (
        response.data
        or []
    )

    # =====================================================
    # BANDINGKAN SETELAH NORMALISASI
    # =====================================================
    for uttp in daftar_uttp:

        nomor_seri_lama = str(
            uttp.get(
                "nomor_seri",
                ""
            )
            or ""
        ).strip()

        nomor_seri_normal = (
            normalisasi_identitas_spbu(
                nomor_seri_lama
            )
        )

        if (
            nomor_seri_normal
            == identifier_normal
        ):
            uttp_id = uttp[
                "id"
            ]

            # Pastikan data master tetap aktif
            (
                supabase
                .table("uttp")
                .update({
                    "lokasi": "SPBU",
                    "status": "aktif",
                })
                .eq(
                    "id",
                    uttp_id
                )
                .execute()
            )

            return uttp_id

    # =====================================================
    # BELUM ADA → BUAT UTTP BARU
    # =====================================================
    response = (
        supabase
        .table("uttp")
        .insert({
            "perusahaan_id": (
                perusahaan_id
            ),

            "jenis_uttp": (
                "Pompa Ukur BBM"
            ),

            # Tetap simpan bentuk aslinya agar enak dibaca
            "nomor_seri": identifier,

            "merk": "",
            "tipe": "",
            "kapasitas": None,

            "lokasi": "SPBU",
            "status": "aktif",
        })
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "UTTP SPBU gagal disimpan."
        )

    return response.data[0][
        "id"
    ]
# =========================================================
# CARI / BUAT UTTP PUBBM PER NOZZLE
# =========================================================
def get_or_create_nozzle_pubbm(
    supabase,
    perusahaan_id,
    merk,
    tipe,
    nomor_seri,
    media,
    posisi,
):
    """
    Konsep baru PUBBM:

    1 NOZZLE = 1 UTTP

    Identitas nozzle ditentukan oleh:
    - perusahaan
    - jenis UTTP
    - tipe
    - nomor seri
    - media
    - posisi

    Merk tetap disimpan sebagai identitas alat,
    tetapi tidak digunakan sebagai pembeda utama.
    """

    merk = str(
        merk or ""
    ).strip()

    tipe = str(
        tipe or ""
    ).strip()

    nomor_seri = str(
        nomor_seri or ""
    ).strip()

    media = str(
        media or ""
    ).strip()

    posisi = str(
        posisi or ""
    ).strip()

    # =====================================================
    # VALIDASI DATA NOZZLE
    # =====================================================
    if not merk:
        raise ValueError(
            "Merk dispenser belum diisi."
        )

    if not tipe:
        raise ValueError(
            "Tipe dispenser belum diisi."
        )

    if not nomor_seri:
        raise ValueError(
            "No. Seri dispenser belum diisi."
        )

    if not media:
        raise ValueError(
            "Media nozzle belum diisi."
        )

    if not posisi:
        raise ValueError(
            "Posisi nozzle belum diisi."
        )

    # =====================================================
    # NORMALISASI UNTUK PENCARIAN
    # =====================================================
    tipe_normal = (
        tipe
        .upper()
        .strip()
    )

    nomor_seri_normal = (
        nomor_seri
        .upper()
        .strip()
    )

    media_normal = (
        media
        .upper()
        .strip()
    )

    posisi_normal = (
        posisi
        .upper()
        .strip()
    )

    # =====================================================
    # AMBIL SEMUA UTTP PUBBM PERUSAHAAN INI
    # =====================================================
    response = (
        supabase
        .table("uttp")
        .select(
            "id, perusahaan_id, jenis_uttp, "
            "merk, tipe, nomor_seri, media, posisi"
        )
        .eq(
            "perusahaan_id",
            perusahaan_id
        )
        .eq(
            "jenis_uttp",
            "Pompa Ukur BBM"
        )
        .execute()
    )

    daftar_uttp = (
        response.data
        or []
    )

    # =====================================================
    # CARI NOZZLE YANG SAMA
    # =====================================================
    for uttp in daftar_uttp:

        tipe_lama = str(
            uttp.get(
                "tipe",
                ""
            )
            or ""
        ).upper().strip()

        seri_lama = str(
            uttp.get(
                "nomor_seri",
                ""
            )
            or ""
        ).upper().strip()

        media_lama = str(
            uttp.get(
                "media",
                ""
            )
            or ""
        ).upper().strip()

        posisi_lama = str(
            uttp.get(
                "posisi",
                ""
            )
            or ""
        ).upper().strip()

        if (
            tipe_lama == tipe_normal
            and seri_lama == nomor_seri_normal
            and media_lama == media_normal
            and posisi_lama == posisi_normal
        ):
            uttp_id = uttp[
                "id"
            ]

            # =============================================
            # UPDATE IDENTITAS MASTER TERBARU
            # =============================================
            (
                supabase
                .table("uttp")
                .update({
                    "merk": merk,
                    "tipe": tipe,
                    "nomor_seri": nomor_seri,
                    "media": media,
                    "posisi": posisi,
                    "lokasi": "SPBU",
                    "status": "aktif",
                })
                .eq(
                    "id",
                    uttp_id
                )
                .execute()
            )

            return uttp_id

    # =====================================================
    # NOZZLE BELUM ADA → BUAT UTTP BARU
    # =====================================================
    response = (
        supabase
        .table("uttp")
        .insert({
            "perusahaan_id": perusahaan_id,

            "jenis_uttp": (
                "Pompa Ukur BBM"
            ),

            "merk": merk,
            "tipe": tipe,
            "nomor_seri": nomor_seri,

            "media": media,
            "posisi": posisi,

            "kapasitas": None,

            "lokasi": "SPBU",
            "status": "aktif",
        })
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "UTTP nozzle PUBBM gagal disimpan."
        )

    return response.data[0][
        "id"
    ]
# =========================================================
# KONVERSI DATAFRAME PUBBM KE JSON
# =========================================================
def dataframe_to_records_pubbm(df):
    """
    Mengubah DataFrame menjadi list of dict
    agar aman disimpan ke JSONB Supabase.
    """

    if (
        df is None
        or not isinstance(df, pd.DataFrame)
        or df.empty
    ):
        return []

    df_clean = df.copy()

    # Ubah NaN / NaT menjadi None
    df_clean = df_clean.where(
        pd.notna(df_clean),
        None
    )

    return df_clean.to_dict(
        orient="records"
    )
# =========================================================
# BUILD DATA PENGUJIAN PUBBM
# =========================================================
def build_data_pengujian_pubbm(data):
    """
    Menyusun detail pengujian PUBBM
    untuk disimpan ke kolom data_pengujian JSONB.

    Konsep:
    1 UTTP = 1 SPBU
    Detail dispenser/nozzle disimpan per pengujian.
    """

    if not data:
        return {}

    # =====================================================
    # DISPENSER / NOZZLE
    # =====================================================
    dispenser_records = (
        dataframe_to_records_pubbm(
            data.get("dispenser")
        )
    )

    # =====================================================
    # BEJANA UKUR STANDAR
    # =====================================================
    alat_standar_records = (
        dataframe_to_records_pubbm(
            data.get("alat_standar")
        )
    )

    # =====================================================
    # JUMLAH NOZZLE YANG DIUJI
    # =====================================================
    jumlah_nozzle = len(
        dispenser_records
    )

    # =====================================================
    # DAFTAR POSISI NOZZLE
    # =====================================================
    posisi_nozzle = []

    for item in dispenser_records:
        posisi = str(
            item.get(
                "Posisi",
                ""
            )
            or ""
        ).strip()

        if posisi:
            posisi_nozzle.append(
                posisi
            )

    # =====================================================
    # DAFTAR MEDIA
    # =====================================================
    daftar_media = []

    for item in dispenser_records:
        media = str(
            item.get(
                "Media",
                ""
            )
            or ""
        ).strip()

        if (
            media
            and media not in daftar_media
        ):
            daftar_media.append(
                media
            )

    # =====================================================
    # HASIL JSONB
    # =====================================================
    return {

        # -------------------------------------------------
        # IDENTITAS SPBU
        # -------------------------------------------------
        "nama_alat": data.get(
            "nama_alat",
            "Pompa Ukur BBM (Dispenser)"
        ),

        "nama_spbu": data.get(
            "nama_spbu",
            ""
        ),

        "pemilik": data.get(
            "pemilik",
            ""
        ),

        "alamat": data.get(
            "alamat",
            ""
        ),

        # -------------------------------------------------
        # RINGKASAN PENGUJIAN
        # -------------------------------------------------
        "jumlah_dispenser": int(
            data.get(
                "jumlah_dispenser",
                0
            )
            or 0
        ),

        "jumlah_nozzle": jumlah_nozzle,

        "posisi_nozzle": posisi_nozzle,

        "media": daftar_media,

        # -------------------------------------------------
        # DETAIL DISPENSER / NOZZLE
        # -------------------------------------------------
        "dispenser": dispenser_records,

        # -------------------------------------------------
        # ALAT STANDAR
        # -------------------------------------------------
        "jumlah_alat_standar": int(
            data.get(
                "jumlah_alat_standar",
                0
            )
            or 0
        ),

        "alat_standar": alat_standar_records,

        # -------------------------------------------------
        # DATA PENERA
        # -------------------------------------------------
        "jumlah_penera": int(
            data.get(
                "jumlah_penera",
                1
            )
            or 1
        ),

        "penera_1": data.get(
            "penera_1",
            ""
        ),

        "nip_penera_1": data.get(
            "nip_penera_1",
            ""
        ),

        "golongan_penera_1": data.get(
            "golongan_penera_1",
            ""
        ),

        "penera_2": data.get(
            "penera_2",
            ""
        ),

        "nip_penera_2": data.get(
            "nip_penera_2",
            ""
        ),

        "golongan_penera_2": data.get(
            "golongan_penera_2",
            ""
        ),
    }
# =========================================================
# NORMALISASI TANGGAL PUBBM
# =========================================================
def tanggal_iso_pubbm(nilai):
    """
    Mengubah date/datetime/string menjadi YYYY-MM-DD.
    """

    if not nilai:
        return None

    if isinstance(nilai, datetime):
        return nilai.date().isoformat()

    if isinstance(nilai, date):
        return nilai.isoformat()

    nilai = str(nilai).strip()

    try:
        return datetime.strptime(
            nilai,
            "%Y-%m-%d"
        ).date().isoformat()

    except ValueError:
        return nilai
# =========================================================
# BERLAKU SAMPAI PUBBM
# =========================================================
def berlaku_sampai_pubbm(tanggal_pengujian):
    if not tanggal_pengujian:
        return None

    if isinstance(
        tanggal_pengujian,
        datetime
    ):
        tanggal_obj = (
            tanggal_pengujian.date()
        )

    elif isinstance(
        tanggal_pengujian,
        date
    ):
        tanggal_obj = (
            tanggal_pengujian
        )

    else:
        tanggal_obj = datetime.strptime(
            str(tanggal_pengujian),
            "%Y-%m-%d"
        ).date()

    try:
        tanggal_berlaku = (
            tanggal_obj.replace(
                year=tanggal_obj.year + 1
            )
        )

    except ValueError:
        # Kasus 29 Februari
        tanggal_berlaku = (
            tanggal_obj.replace(
                year=tanggal_obj.year + 1,
                month=2,
                day=28
            )
        )

    return tanggal_berlaku.isoformat()
# =========================================================
# SIMPAN PENGUJIAN PUBBM KE SUPABASE
# =========================================================
def simpan_pengujian_pubbm_ke_supabase(
    data
):
    """
    Menyimpan pengujian PUBBM dengan konsep:

    1 NOZZLE = 1 UTTP
    1 NOZZLE = 1 ROW PENGUJIAN

    Semua nozzle dalam satu kegiatan tetap memakai:
    - nomor order yang sama;
    - nomor sertifikat yang sama;
    - tanggal yang sama;
    - penera yang sama.
    """

    if not data:
        raise ValueError(
            "Data PUBBM belum tersedia."
        )

    # =====================================================
    # 1. VALIDASI DATA UMUM
    # =====================================================
    pemilik = str(
        data.get(
            "pemilik",
            ""
        )
        or ""
    ).strip()

    alamat = str(
        data.get(
            "alamat",
            ""
        )
        or ""
    ).strip()

    nomor_spbu = str(
        data.get(
            "nama_spbu",
            ""
        )
        or ""
    ).strip()

    nomor_order = str(
        data.get(
            "nomor_order",
            ""
        )
        or ""
    ).strip()

    nomor_sertifikat = str(
        data.get(
            "nomor_sertifikat",
            ""
        )
        or ""
    ).strip()

    penera_1 = str(
        data.get(
            "penera_1",
            ""
        )
        or ""
    ).strip()

    penera_2 = str(
        data.get(
            "penera_2",
            ""
        )
        or ""
    ).strip()

    jenis_pengujian = str(
        data.get(
            "jenis_pengujian",
            "Tera Ulang"
        )
        or "Tera Ulang"
    ).strip()

    if not pemilik:
        raise ValueError(
            "Nama SPBU / perusahaan belum diisi."
        )

    if not nomor_order:
        raise ValueError(
            "Nomor order belum diisi."
        )

    if not nomor_sertifikat:
        raise ValueError(
            "Nomor sertifikat belum diisi."
        )

    if not penera_1:
        raise ValueError(
            "Penera 1 belum dipilih."
        )

    # =====================================================
    # 2. AMBIL DATA NOZZLE
    # =====================================================
    dispenser_records = (
        dataframe_to_records_pubbm(
            data.get(
                "dispenser"
            )
        )
    )

    if not dispenser_records:
        raise ValueError(
            "Data nozzle / dispenser belum tersedia."
        )

    # =====================================================
    # 3. ALAT STANDAR
    # =====================================================
    alat_standar_records = (
        dataframe_to_records_pubbm(
            data.get(
                "alat_standar"
            )
        )
    )

    # =====================================================
    # 4. KONEKSI SUPABASE
    # =====================================================
    supabase = (
        get_supabase_pubbm()
    )

    # =====================================================
    # 5. PERUSAHAAN / SPBU
    # =====================================================
    perusahaan_id = (
        simpan_atau_update_perusahaan_pubbm(
            supabase=supabase,
            nama_perusahaan=pemilik,
            alamat=alamat,
        )
    )

    # =====================================================
    # 6. TANGGAL
    # =====================================================
    tanggal_pengujian = (
        tanggal_iso_pubbm(
            data.get(
                "tanggal_pengujian"
            )
        )
    )

    tanggal_sertifikat = (
        tanggal_iso_pubbm(
            data.get(
                "tanggal_cetak"
            )
        )
    )

    berlaku_sampai = (
        berlaku_sampai_pubbm(
            data.get(
                "tanggal_pengujian"
            )
        )
    )

    # =====================================================
    # 7. DATA PENERA TAMBAHAN
    # Disimpan sebagai snapshot teknis karena tabel
    # pengujian hanya menyimpan nama penera.
    # =====================================================
    nip_penera_1 = str(
        data.get(
            "nip_penera_1",
            ""
        )
        or ""
    ).strip()

    golongan_penera_1 = str(
        data.get(
            "golongan_penera_1",
            ""
        )
        or ""
    ).strip()

    nip_penera_2 = str(
        data.get(
            "nip_penera_2",
            ""
        )
        or ""
    ).strip()

    golongan_penera_2 = str(
        data.get(
            "golongan_penera_2",
            ""
        )
        or ""
    ).strip()

    # =====================================================
    # 8. SUSUN PAYLOAD PER NOZZLE
    # =====================================================
    daftar_payload = []

    uttp_id_dalam_form = set()

    for urutan, nozzle in enumerate(
        dispenser_records,
        start=1
    ):

        merk = str(
            nozzle.get(
                "Merk",
                ""
            )
            or ""
        ).strip()

        tipe = str(
            nozzle.get(
                "Tipe",
                ""
            )
            or ""
        ).strip()

        nomor_seri = str(
            nozzle.get(
                "No. Seri",
                ""
            )
            or ""
        ).strip()

        media = str(
            nozzle.get(
                "Media",
                ""
            )
            or ""
        ).strip()

        posisi = str(
            nozzle.get(
                "Posisi",
                ""
            )
            or ""
        ).strip()

        # =============================================
        # NOMOR DISPENSER
        # =============================================
        no_dispenser_raw = nozzle.get(
            "No",
            ""
        )

        try:
            no_dispenser = int(
                float(
                    no_dispenser_raw
                )
            )
        except (
            TypeError,
            ValueError
        ):
            no_dispenser = None

        # =============================================
        # VALIDASI PER NOZZLE
        # =============================================
        if not merk:
            raise ValueError(
                f"Nozzle baris {urutan}: "
                "Merk belum diisi."
            )

        if not tipe:
            raise ValueError(
                f"Nozzle baris {urutan}: "
                "Tipe belum diisi."
            )

        if not nomor_seri:
            raise ValueError(
                f"Nozzle baris {urutan}: "
                "No. Seri belum diisi."
            )

        if not media:
            raise ValueError(
                f"Nozzle baris {urutan}: "
                "Media belum diisi."
            )

        if not posisi:
            raise ValueError(
                f"Nozzle baris {urutan}: "
                "Posisi belum diisi."
            )

        # =============================================
        # CARI / BUAT 1 UTTP UNTUK 1 NOZZLE
        # =============================================
        uttp_id = (
            get_or_create_nozzle_pubbm(
                supabase=supabase,
                perusahaan_id=perusahaan_id,
                merk=merk,
                tipe=tipe,
                nomor_seri=nomor_seri,
                media=media,
                posisi=posisi,
            )
        )

        # =============================================
        # CEGAH NOZZLE YANG SAMA MASUK 2 KALI
        # =============================================
        if uttp_id in uttp_id_dalam_form:
            raise ValueError(
                "Nozzle yang sama ditemukan lebih "
                "dari satu kali pada form:\n\n"
                f"{tipe} | {nomor_seri} | "
                f"{media} | {posisi}"
            )

        uttp_id_dalam_form.add(
            uttp_id
        )

        # =============================================
        # JSONB BARU YANG LEBIH SEDERHANA
        #
        # Merk, Tipe, No Seri, Media, Posisi
        # TIDAK disimpan lagi di sini karena sudah
        # menjadi master pada tabel UTTP.
        # =============================================
        detail_nozzle = {
            "schema_pubbm": 2,

            # Nomor SPBU tetap disimpan sebagai
            # snapshot administratif.
            "nomor_spbu": nomor_spbu,

            # Dibutuhkan untuk mengelompokkan nozzle
            # dalam dispenser yang sama.
            "no_dispenser": (
                no_dispenser
            ),

            # Alat standar merupakan kondisi kegiatan
            # pengujian sehingga tetap disimpan.
            "alat_standar": (
                alat_standar_records
            ),

            # Snapshot identitas penera
            "nip_penera_1": (
                nip_penera_1
            ),

            "golongan_penera_1": (
                golongan_penera_1
            ),

            "nip_penera_2": (
                nip_penera_2
            ),

            "golongan_penera_2": (
                golongan_penera_2
            ),
        }

        # =============================================
        # PAYLOAD PENGUJIAN NOZZLE
        # =============================================
        payload = {
            "uttp_id": (
                uttp_id
            ),

            "tanggal_pengujian": (
                tanggal_pengujian
            ),

            "tanggal_sertifikat": (
                tanggal_sertifikat
            ),

            "jenis_pengujian": (
                jenis_pengujian
            ),

            "hasil": "SAH",

            "nomor_order": (
                nomor_order
            ),

            "nomor_sertifikat": (
                nomor_sertifikat
            ),

            "penera_1": (
                penera_1
            ),

            "penera_2": (
                penera_2
            ),

            "berlaku_sampai": (
                berlaku_sampai
            ),

            "data_pengujian": (
                detail_nozzle
            ),
        }

        daftar_payload.append(
            payload
        )

    # =====================================================
    # 9. MODE EDIT ATAU DATA BARU
    # =====================================================
    edit_id = st.session_state.get(
        "pubbm_edit_pengujian_id"
    )

    # =====================================================
    # A. DATA BARU
    # =====================================================
    if not edit_id:

        response = (
            supabase
            .table(
                "pengujian"
            )
            .insert(
                daftar_payload
            )
            .execute()
        )

        if not response.data:
            raise RuntimeError(
                "Data pengujian PUBBM "
                "gagal disimpan."
            )

        return response.data

    # =====================================================
    # B. MODE EDIT
    #
    # Cari sertifikat kegiatan lama.
    # Satu sertifikat dapat mempunyai banyak row nozzle.
    # =====================================================
    response_edit = (
        supabase
        .table(
            "pengujian"
        )
        .select(
            "id, uttp_id, nomor_sertifikat"
        )
        .eq(
            "id",
            edit_id
        )
        .execute()
    )

    if not response_edit.data:
        raise RuntimeError(
            "Data pengujian lama tidak ditemukan."
        )

    row_edit = (
        response_edit.data[0]
    )

    nomor_sertifikat_lama = str(
        row_edit.get(
            "nomor_sertifikat",
            ""
        )
        or ""
    ).strip()

    # =====================================================
    # AMBIL SEMUA UTTP PUBBM PERUSAHAAN INI
    # =====================================================
    response_uttp_perusahaan = (
        supabase
        .table(
            "uttp"
        )
        .select(
            "id"
        )
        .eq(
            "perusahaan_id",
            perusahaan_id
        )
        .eq(
            "jenis_uttp",
            "Pompa Ukur BBM"
        )
        .execute()
    )

    id_uttp_perusahaan = {
        row.get("id")
        for row in (
            response_uttp_perusahaan.data
            or []
        )
        if row.get("id") is not None
    }

    # =====================================================
    # AMBIL SEMUA ROW DALAM SERTIFIKAT LAMA
    # =====================================================
    response_lama = (
        supabase
        .table(
            "pengujian"
        )
        .select(
            "id, uttp_id, nomor_sertifikat"
        )
        .eq(
            "nomor_sertifikat",
            nomor_sertifikat_lama
        )
        .execute()
    )

    daftar_lama = [
        row
        for row in (
            response_lama.data
            or []
        )
        if row.get(
            "uttp_id"
        ) in id_uttp_perusahaan
    ]

    lama_per_uttp = {
        row.get("uttp_id"): row
        for row in daftar_lama
    }

    hasil_simpan = []

    id_uttp_baru = {
        payload["uttp_id"]
        for payload in daftar_payload
    }

    # =====================================================
    # UPDATE ROW YANG SUDAH ADA
    # INSERT ROW NOZZLE BARU
    # =====================================================
    for payload in daftar_payload:

        uttp_id = payload[
            "uttp_id"
        ]

        row_lama = lama_per_uttp.get(
            uttp_id
        )

        if row_lama:

            response = (
                supabase
                .table(
                    "pengujian"
                )
                .update(
                    payload
                )
                .eq(
                    "id",
                    row_lama[
                        "id"
                    ]
                )
                .execute()
            )

        else:

            response = (
                supabase
                .table(
                    "pengujian"
                )
                .insert(
                    payload
                )
                .execute()
            )

        if not response.data:
            raise RuntimeError(
                "Data pengujian nozzle PUBBM "
                "gagal diperbarui."
            )

        hasil_simpan.extend(
            response.data
        )

    # =====================================================
    # HAPUS ROW NOZZLE YANG SUDAH TIDAK ADA
    #
    # Dilakukan paling akhir agar data lama tidak hilang
    # jika proses update/insert sebelumnya gagal.
    # =====================================================
    for row_lama in daftar_lama:

        uttp_id_lama = row_lama.get(
            "uttp_id"
        )

        if (
            uttp_id_lama
            not in id_uttp_baru
        ):
            (
                supabase
                .table(
                    "pengujian"
                )
                .delete()
                .eq(
                    "id",
                    row_lama[
                        "id"
                    ]
                )
                .execute()
            )

    # =====================================================
    # KELUAR DARI MODE EDIT
    # =====================================================
    st.session_state.pop(
        "pubbm_edit_pengujian_id",
        None
    )

    return hasil_simpan
# =========================================================
# NORMALISASI IDENTITAS SPBU
# =========================================================
def normalisasi_identitas_spbu(
    text
):
    """
    Menyamakan berbagai format penulisan
    identitas SPBU.

    Contoh:
    SPBU 34-15717
    SPBU 34.15717
    34-15717
    34.15717

    semuanya menjadi:
    3415717
    """

    text = str(
        text or ""
    ).upper().strip()

    if not text:
        return ""

    # =====================================================
    # JIKA ADA NOMOR SPBU, GUNAKAN ANGKANYA SAJA
    # =====================================================
    match_spbu = re.search(
        r"SPBU\s*([0-9][0-9.\-\s]*)",
        text,
        re.IGNORECASE,
    )

    if match_spbu:
        return re.sub(
            r"\D",
            "",
            match_spbu.group(1)
        )

    # =====================================================
    # JIKA ISINYA MEMANG NOMOR SPBU TANPA KATA "SPBU"
    # =====================================================
    hanya_angka = re.sub(
        r"\D",
        "",
        text
    )

    if (
        hanya_angka
        and not re.search(
            r"[A-Z]",
            text
        )
    ):
        return hanya_angka

    # =====================================================
    # FALLBACK UNTUK NAMA SPBU / PERUSAHAAN
    # =====================================================
    hasil = re.sub(
        r"[^A-Z0-9]",
        "",
        text
    )

    if hasil.startswith(
        "SPBU"
    ):
        hasil = hasil[4:]

    return hasil
def bulan_singkat_id(tanggal):
    bulan = {
        1: "JAN", 2: "FEB", 3: "MAR", 4: "APR",
        5: "MEI", 6: "JUN", 7: "JUL", 8: "AGS",
        9: "SEP", 10: "OKT", 11: "NOV", 12: "DES"
    }
    return bulan.get(tanggal.month, "")


def slug_filename(text):
    text = str(text).replace("/", "_").replace("\\", "_").replace(" ", "_")
    return "".join(ch for ch in text if ch.isalnum() or ch in ["_", "-", "."])

def parse_tanggal_file_pubbm(data):
    tanggal = (
        data.get("tanggal_pengujian")
        or data.get("tanggal")
        or data.get("tanggal_tera")
        or data.get("tanggal_penera")
    )

    if tanggal:
        if isinstance(tanggal, str):
            try:
                return datetime.strptime(tanggal, "%Y-%m-%d")
            except Exception:
                pass

        return tanggal

    return datetime.now()


def format_nama_file_pubbm(data):
    nama_spbu = (
        data.get("nama_spbu")
        or data.get("nomor_spbu")
        or data.get("nama_perusahaan")
        or data.get("pemilik")
        or "SPBU"
    )

    nama_penera = (
        data.get("penera_1")
        or data.get("nama_penera")
        or data.get("penera")
        or "PENERA"
    )

    tanggal = parse_tanggal_file_pubbm(data)
    tanggal_file = f"{tanggal.day:02d} {bulan_singkat_id(tanggal)}"

    nama_file = f"{nama_spbu}_{nama_penera}_{tanggal_file}"
    return slug_filename(nama_file)

def update_spbu_terpilih():
    selected = str(
        st.session_state.get(
            "spbu_select",
            ""
        )
    ).strip()

    df_spbu = st.session_state.get(
        "data_spbu"
    )

    if (
        not selected
        or df_spbu is None
        or df_spbu.empty
    ):
        return

    row = df_spbu[
        df_spbu["Nama SPBU"]
        .astype(str)
        .str.strip()
        == selected
    ]

    if row.empty:
        return

    data = row.iloc[0]

    st.session_state["nama_perusahaan"] = selected

    alamat_spbu = data.get(
        "Alamat",
        ""
    )

    if pd.isna(alamat_spbu):
        alamat_spbu = ""

    st.session_state[
        "alamat_input_pubbm"
    ] = str(alamat_spbu).strip()
    # =====================================================
    # PERBARUI NOMOR SPBU SESUAI MASTER
    # =====================================================
    nomor_spbu = str(
        data.get(
            "Nomor SPBU",
            ""
        )
        or ""
    ).strip()
    
    # Fallback khusus data lama
    if (
        not nomor_spbu
        or nomor_spbu.lower() == "nan"
    ):
        match_spbu = re.search(
            r"SPBU\s*[\d\.-]+",
            selected,
            re.IGNORECASE,
        )
    
        nomor_spbu = (
            match_spbu.group(0).upper()
            if match_spbu
            else ""
        )
    
    st.session_state[
        "nomor_spbu_pubbm"
    ] = nomor_spbu
# =========================================================
# AMBIL RIWAYAT PUBBM PER KEGIATAN / SERTIFIKAT
# =========================================================
def ambil_riwayat_kegiatan_pubbm(
    supabase,
    perusahaan,
):
    """
    Membaca struktur PUBBM baru:

        1 nozzle = 1 UTTP
        1 nozzle = 1 row pengujian

    lalu menggabungkannya kembali menjadi:

        1 sertifikat = 1 kegiatan PUBBM

    agar form Riwayat / Edit / Tambah Pengujian
    tetap dapat bekerja seperti sebelumnya.

    Fungsi juga mempertahankan kompatibilitas
    dengan data PUBBM lama yang masih menyimpan
    array 'dispenser' di JSONB.
    """

    perusahaan_id = perusahaan.get(
        "id"
    )

    if not perusahaan_id:
        return []

    # =====================================================
    # 1. AMBIL SELURUH UTTP PUBBM MILIK PERUSAHAAN
    # =====================================================
    response_uttp = (
        supabase
        .table("uttp")
        .select(
            "id, perusahaan_id, jenis_uttp, "
            "merk, tipe, nomor_seri, "
            "media, posisi"
        )
        .eq(
            "perusahaan_id",
            perusahaan_id
        )
        .eq(
            "jenis_uttp",
            "Pompa Ukur BBM"
        )
        .execute()
    )

    daftar_uttp = (
        response_uttp.data
        or []
    )

    if not daftar_uttp:
        return []

    uttp_map = {
        row["id"]: row
        for row in daftar_uttp
        if row.get("id") is not None
    }

    daftar_uttp_id = list(
        uttp_map.keys()
    )

    if not daftar_uttp_id:
        return []

    # =====================================================
    # 2. AMBIL SELURUH PENGUJIAN DARI UTTP TERSEBUT
    # =====================================================
    response_pengujian = (
        supabase
        .table("pengujian")
        .select("*")
        .in_(
            "uttp_id",
            daftar_uttp_id
        )
        .order(
            "tanggal_pengujian",
            desc=True
        )
        .execute()
    )

    daftar_pengujian = (
        response_pengujian.data
        or []
    )

    if not daftar_pengujian:
        return []

    # =====================================================
    # 3. KELOMPOKKAN BERDASARKAN SATU KEGIATAN
    #
    # Sertifikat + Order + Tanggal digunakan bersama-sama
    # agar pengelompokan lebih aman.
    # =====================================================
    kelompok = {}

    for row in daftar_pengujian:

        nomor_sertifikat = str(
            row.get(
                "nomor_sertifikat",
                ""
            )
            or ""
        ).strip()

        nomor_order = str(
            row.get(
                "nomor_order",
                ""
            )
            or ""
        ).strip()

        tanggal = str(
            row.get(
                "tanggal_pengujian",
                ""
            )
            or ""
        ).strip()

        # Data sangat lama mungkin belum memiliki nomor.
        if nomor_sertifikat:
            kunci = (
                nomor_sertifikat,
                nomor_order,
                tanggal,
            )
        else:
            kunci = (
                f"ID-{row.get('id')}",
                nomor_order,
                tanggal,
            )

        kelompok.setdefault(
            kunci,
            []
        ).append(
            row
        )

    # =====================================================
    # 4. BANGUN KEMBALI SATU KEGIATAN PUBBM
    # =====================================================
    daftar_kegiatan = []

    for _, rows in kelompok.items():

        # Urutkan agar hasil stabil
        rows = sorted(
            rows,
            key=lambda item: int(
                item.get("id", 0)
                or 0
            )
        )

        pengujian_utama = dict(
            rows[0]
        )

        detail_utama = (
            pengujian_utama.get(
                "data_pengujian"
            )
            or {}
        )

        # =================================================
        # KOMPATIBILITAS DATA LAMA
        #
        # Data lama memang sudah punya array dispenser.
        # Tidak perlu direkonstruksi dari tabel UTTP.
        # =================================================
        dispenser_lama = (
            detail_utama.get(
                "dispenser",
                []
            )
            or []
        )

        if dispenser_lama:

            detail_gabungan = dict(
                detail_utama
            )

            # Simpan semua ID terkait agar nanti mudah
            # digunakan pada proses Edit.
            pengujian_utama[
                "_pubbm_pengujian_ids"
            ] = [
                row.get("id")
                for row in rows
            ]

            pengujian_utama[
                "data_pengujian"
            ] = detail_gabungan

            daftar_kegiatan.append(
                pengujian_utama
            )

            continue

        # =================================================
        # FORMAT BARU
        # REKONSTRUKSI DISPENSER DARI TABEL UTTP
        # =================================================
        dispenser_records = []

        daftar_media = []
        daftar_posisi = []
        nomor_dispenser_set = set()

        alat_standar = []
        nomor_spbu = ""

        nip_penera_1 = ""
        golongan_penera_1 = ""
        nip_penera_2 = ""
        golongan_penera_2 = ""

        for row in rows:

            uttp = uttp_map.get(
                row.get(
                    "uttp_id"
                ),
                {}
            )

            detail = (
                row.get(
                    "data_pengujian"
                )
                or {}
            )

            # ---------------------------------------------
            # NOMOR DISPENSER
            # ---------------------------------------------
            no_dispenser = detail.get(
                "no_dispenser"
            )

            if no_dispenser not in (
                None,
                ""
            ):
                try:
                    no_dispenser = int(
                        no_dispenser
                    )
                except (
                    TypeError,
                    ValueError
                ):
                    pass

                nomor_dispenser_set.add(
                    no_dispenser
                )

            # ---------------------------------------------
            # DATA NOZZLE DARI MASTER UTTP
            # ---------------------------------------------
            merk = str(
                uttp.get(
                    "merk",
                    ""
                )
                or ""
            ).strip()

            tipe = str(
                uttp.get(
                    "tipe",
                    ""
                )
                or ""
            ).strip()

            no_seri = str(
                uttp.get(
                    "nomor_seri",
                    ""
                )
                or ""
            ).strip()

            media = str(
                uttp.get(
                    "media",
                    ""
                )
                or ""
            ).strip()

            posisi = str(
                uttp.get(
                    "posisi",
                    ""
                )
                or ""
            ).strip()

            dispenser_records.append({
                "No": (
                    no_dispenser
                    if no_dispenser is not None
                    else ""
                ),
                "Merk": merk,
                "Tipe": tipe,
                "No. Seri": no_seri,
                "Media": media,
                "Posisi": posisi,
            })

            if (
                media
                and media not in daftar_media
            ):
                daftar_media.append(
                    media
                )

            if (
                posisi
                and posisi not in daftar_posisi
            ):
                daftar_posisi.append(
                    posisi
                )

            # ---------------------------------------------
            # DATA KEGIATAN CUKUP DIAMBIL SEKALI
            # ---------------------------------------------
            if not alat_standar:
                alat_standar = list(
                    detail.get(
                        "alat_standar",
                        []
                    )
                    or []
                )

            if not nomor_spbu:
                nomor_spbu = str(
                    detail.get(
                        "nomor_spbu",
                        ""
                    )
                    or ""
                ).strip()

            if not nip_penera_1:
                nip_penera_1 = str(
                    detail.get(
                        "nip_penera_1",
                        ""
                    )
                    or ""
                ).strip()

            if not golongan_penera_1:
                golongan_penera_1 = str(
                    detail.get(
                        "golongan_penera_1",
                        ""
                    )
                    or ""
                ).strip()

            if not nip_penera_2:
                nip_penera_2 = str(
                    detail.get(
                        "nip_penera_2",
                        ""
                    )
                    or ""
                ).strip()

            if not golongan_penera_2:
                golongan_penera_2 = str(
                    detail.get(
                        "golongan_penera_2",
                        ""
                    )
                    or ""
                ).strip()

        # =================================================
        # URUTKAN BERDASARKAN NOMOR DISPENSER + POSISI
        # =================================================
        def kunci_dispenser(item):

            no = item.get(
                "No",
                ""
            )

            try:
                no_sort = int(
                    no
                )
            except (
                TypeError,
                ValueError
            ):
                no_sort = 999999

            posisi_sort = str(
                item.get(
                    "Posisi",
                    ""
                )
                or ""
            ).strip()

            return (
                no_sort,
                posisi_sort
            )

        dispenser_records = sorted(
            dispenser_records,
            key=kunci_dispenser
        )

        # =================================================
        # SUSUN DETAIL VIRTUAL KOMPATIBEL DENGAN FORM LAMA
        # =================================================
        detail_gabungan = {
            "schema_pubbm": 2,

            "nama_alat": (
                "Pompa Ukur BBM (Dispenser)"
            ),

            "nama_spbu": (
                nomor_spbu
                or str(
                    perusahaan.get(
                        "nama_perusahaan",
                        ""
                    )
                    or ""
                ).strip()
            ),

            "pemilik": str(
                perusahaan.get(
                    "nama_perusahaan",
                    ""
                )
                or ""
            ).strip(),

            "alamat": str(
                perusahaan.get(
                    "alamat",
                    ""
                )
                or ""
            ).strip(),

            "jumlah_dispenser": len(
                nomor_dispenser_set
            ),

            "jumlah_nozzle": len(
                dispenser_records
            ),

            "posisi_nozzle": (
                daftar_posisi
            ),

            "media": (
                daftar_media
            ),

            # Inilah yang membuat form lama tetap bekerja
            "dispenser": (
                dispenser_records
            ),

            "alat_standar": (
                alat_standar
            ),

            "jumlah_alat_standar": len(
                alat_standar
            ),

            "penera_1": str(
                pengujian_utama.get(
                    "penera_1",
                    ""
                )
                or ""
            ).strip(),

            "nip_penera_1": (
                nip_penera_1
            ),

            "golongan_penera_1": (
                golongan_penera_1
            ),

            "penera_2": str(
                pengujian_utama.get(
                    "penera_2",
                    ""
                )
                or ""
            ).strip(),

            "nip_penera_2": (
                nip_penera_2
            ),

            "golongan_penera_2": (
                golongan_penera_2
            ),

            "jumlah_penera": (
                2
                if str(
                    pengujian_utama.get(
                        "penera_2",
                        ""
                    )
                    or ""
                ).strip()
                else 1
            ),
        }

        pengujian_utama[
            "data_pengujian"
        ] = detail_gabungan

        # ID pertama tetap dipakai sebagai jangkar mode Edit.
        # Fungsi simpan baru kemudian mencari seluruh row
        # dengan nomor sertifikat yang sama.
        pengujian_utama[
            "_pubbm_pengujian_ids"
        ] = [
            row.get("id")
            for row in rows
        ]

        daftar_kegiatan.append(
            pengujian_utama
        )

    # =====================================================
    # 5. URUTKAN KEGIATAN TERBARU
    # =====================================================
    daftar_kegiatan = sorted(
        daftar_kegiatan,
        key=lambda item: (
            str(
                item.get(
                    "tanggal_pengujian",
                    ""
                )
                or ""
            ),
            int(
                item.get(
                    "id",
                    0
                )
                or 0
            ),
        ),
        reverse=True
    )

    return daftar_kegiatan
def run():
    col_nav1, col_nav2 = st.columns(2)

    with col_nav1:
        if st.button(
            "← Kembali ke Home",
            use_container_width=True,
            key="pubbm_nav_home",
        ):
            st.session_state.halaman = "home"
            st.rerun()

    with col_nav2:
        if st.button(
            "📋 Ke Pengujian UTTP",
            use_container_width=True,
            key="tb_nav_uttp"
        ):
            st.session_state.halaman_uttp = "home_uttp"
            st.rerun()
            
            
    @st.cache_data
    def load_data_media_spbu():
        try:
            df = pd.read_excel("data/data_media_spbu.xlsx")
            df.columns = df.columns.str.strip()
            return df
        except FileNotFoundError:
            return pd.DataFrame(
                {
                    "NAMA SPBU": [
                        "SPBU",
                        "SPBU BP AKR",
                        "SPBU SHELL",
                        "SPBU VIVO",
                        "PERTASHOP"
                    ],
                    "MEDIA": [
                        "Pertalite, Pertamax, Pertamax GREEN, Pertamax Turbo, Bio Solar, Pertamina Dex",
                        "BP 92, BP Ultimate, BP Ultimate Diesel",
                        "Super, V-Power, V-Power Diesel, V-Power Nitro+",
                        "Revvo 90, Revvo 92, Revvo 95",
                        "Pertamax"
                    ]
                }
            )
    
    
    def get_kategori_spbu(nama_spbu):
        nama = str(nama_spbu).upper()
    
        if "SHELL" in nama:
            return "SPBU SHELL"
    
        elif "BP AKR" in nama or "BP" in nama:
            return "SPBU BP AKR"
    
        elif "VIVO" in nama:
            return "SPBU VIVO"
    
        elif "PERTASHOP" in nama:
            return "PERTASHOP"
    
        else:
            return "SPBU"
    
    
    def get_media_options(nama_spbu, df_media):
        kategori = get_kategori_spbu(nama_spbu)
    
        if df_media is None or df_media.empty:
            return []
    
        row = df_media[
            df_media["NAMA SPBU"].astype(str).str.upper().str.strip()
            == kategori.upper()
        ]
    
        if row.empty:
            return []
    
        media_text = row.iloc[0]["MEDIA"]
    
        media_list = [
            m.strip()
            for m in str(media_text).split(",")
            if m.strip()
        ]
    
        return media_list
    @st.cache_data(ttl=60)
    def load_data_bejana():
        """
        Prioritas data:
        1. Supabase table 'bejana'
        2. data/data_bejana.xlsx sebagai fallback
        """
    
        kolom_target = [
            "Standar Volume",
            "Merk",
            "Tipe",
            "Nomor Seri",
            "Kelas",
            "Kapasitas",
            "Daya Baca",
            "Telusuran",
        ]
    
        # =====================================================
        # 1. COBA BACA DARI SUPABASE
        # =====================================================
        try:
            supabase = get_supabase_pubbm()
    
            response = (
                supabase
                .table("bejana")
                .select("*")
                .execute()
            )
    
            data = response.data or []
    
            if data:
                df = pd.DataFrame(
                    data
                )
    
                # =============================================
                # SAMAKAN NAMA KOLOM SUPABASE DENGAN UI
                # =============================================
                rename_map = {
                    "standar_volume": "Standar Volume",
                    "merk": "Merk",
                    "tipe": "Tipe",
                    "nomor_seri": "Nomor Seri",
                    "kelas": "Kelas",
                    "kapasitas": "Kapasitas",
                    "daya_baca": "Daya Baca",
                    "telusuran": "Telusuran",
                }
    
                df = df.rename(
                    columns=rename_map
                )
    
                # =============================================
                # PASTIKAN SEMUA KOLOM TERSEDIA
                # =============================================
                for kolom in kolom_target:
                    if kolom not in df.columns:
                        df[kolom] = ""
    
                df = df[
                    kolom_target
                ].copy()
    
                # =============================================
                # BERSIHKAN NILAI
                # =============================================
                for kolom in kolom_target:
                    df[kolom] = (
                        df[kolom]
                        .fillna("")
                    )
    
                return df
    
        except Exception:
            # Kalau tabel belum ada / koneksi gagal,
            # lanjut baca Excel.
            pass
    
        # =====================================================
        # 2. FALLBACK KE EXCEL
        # =====================================================
        try:
            df = pd.read_excel(
                "data/data_bejana.xlsx"
            )
    
            df.columns = (
                df.columns
                .str.strip()
            )
    
            for kolom in kolom_target:
                if kolom not in df.columns:
                    df[kolom] = ""
    
            return df[
                kolom_target
            ]
    
        except FileNotFoundError:
            return pd.DataFrame(
                columns=kolom_target
            )
    
    def bulan_ke_romawi(bulan):
        romawi = {
            1: "I",
            2: "II",
            3: "III",
            4: "IV",
            5: "V",
            6: "VI",
            7: "VII",
            8: "VIII",
            9: "IX",
            10: "X",
            11: "XI",
            12: "XII"
        }
        return romawi.get(bulan, "")
    def generate_nomor_sertifikat(tanggal):
        if isinstance(tanggal, str):
            t = datetime.strptime(tanggal, "%Y-%m-%d")
        else:
            t = tanggal
    
        return f"500.2.3.15/0000/BID-K/{bulan_ke_romawi(t.month)}/{t.year}"
    
    
    def generate_nomor_order(tanggal):
        if isinstance(tanggal, str):
            t = datetime.strptime(tanggal, "%Y-%m-%d")
        else:
            t = tanggal
    
        return f"0000/SCD/{bulan_ke_romawi(t.month)}/{t.year}"
    
    def update_nomor_dokumen_pubbm():
        tanggal = st.session_state.get(
            "tanggal_pengujian_pubbm",
            date.today()
        )

        if isinstance(tanggal, str):
            try:
                tanggal = datetime.strptime(
                    tanggal,
                    "%Y-%m-%d"
                ).date()
            except ValueError:
                tanggal = date.today()

        st.session_state[
            "nomor_sertifikat_pubbm"
        ] = generate_nomor_sertifikat(
            tanggal
        )

        st.session_state[
            "nomor_order_pubbm"
        ] = generate_nomor_order(
            tanggal
        )
        
    def update_penera_1_pubbm():
        selected = str(
            st.session_state.get(
                "penera_1_select",
                ""
            )
        ).strip()

        df_penera = st.session_state.get(
            "data_penera"
        )

        if (
            not selected
            or df_penera is None
            or df_penera.empty
        ):
            st.session_state["nip_penera_1_pubbm"] = ""
            st.session_state["golongan_penera_1_pubbm"] = ""
            return

        row = df_penera[
            df_penera["Nama"]
            .astype(str)
            .str.strip()
            == selected
        ]

        if row.empty:
            return

        data_penera = row.iloc[0]

        nip = str(
            data_penera.get("NIP", "")
        ).strip()

        if nip.endswith(".0"):
            nip = nip[:-2]

        st.session_state[
            "nip_penera_1_pubbm"
        ] = nip

        st.session_state[
            "golongan_penera_1_pubbm"
        ] = str(
            data_penera.get("Golongan", "")
        ).strip()


    def update_penera_2_pubbm():
        selected = str(
            st.session_state.get(
                "penera_2_select",
                ""
            )
        ).strip()

        df_penera = st.session_state.get(
            "data_penera"
        )

        if (
            not selected
            or df_penera is None
            or df_penera.empty
        ):
            st.session_state["nip_penera_2_pubbm"] = ""
            st.session_state["golongan_penera_2_pubbm"] = ""
            return

        row = df_penera[
            df_penera["Nama"]
            .astype(str)
            .str.strip()
            == selected
        ]

        if row.empty:
            return

        data_penera = row.iloc[0]

        nip = str(
            data_penera.get("NIP", "")
        ).strip()

        if nip.endswith(".0"):
            nip = nip[:-2]

        st.session_state[
            "nip_penera_2_pubbm"
        ] = nip

        st.session_state[
            "golongan_penera_2_pubbm"
        ] = str(
            data_penera.get("Golongan", "")
        ).strip()
    @st.cache_data(ttl=60)
    def load_data_penera():
        """
        Membaca master Penera aktif dari Supabase.
        """
    
        try:
            supabase = get_supabase_pubbm()
    
            response = (
                supabase
                .table("penera")
                .select(
                    "id, nama, nip, golongan, status"
                )
                .eq(
                    "status",
                    "aktif"
                )
                .order(
                    "nama"
                )
                .execute()
            )
    
            data = response.data or []
    
            if not data:
                return pd.DataFrame(
                    columns=[
                        "ID",
                        "Nama",
                        "NIP",
                        "Golongan",
                        "Status",
                    ]
                )
    
            df = pd.DataFrame(
                data
            )
    
            # =================================================
            # SAMAKAN NAMA KOLOM DENGAN UI PUBBM
            # =================================================
            df = df.rename(
                columns={
                    "id": "ID",
                    "nama": "Nama",
                    "nip": "NIP",
                    "golongan": "Golongan",
                    "status": "Status",
                }
            )
    
            # =================================================
            # BERSIHKAN DATA
            # =================================================
            for kolom in [
                "Nama",
                "NIP",
                "Golongan",
                "Status",
            ]:
                if kolom not in df.columns:
                    df[kolom] = ""
    
                df[kolom] = (
                    df[kolom]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                )
    
            # Jangan tampilkan penera tanpa nama
            df = df[
                df["Nama"] != ""
            ].copy()
    
            # Hindari duplikat
            df = (
                df
                .drop_duplicates(
                    subset=[
                        "Nama",
                        "NIP",
                    ]
                )
                .sort_values(
                    "Nama"
                )
                .reset_index(
                    drop=True
                )
            )
    
            return df
    
        except Exception as exc:
            st.warning(
                "Data Penera dari Supabase "
                f"tidak dapat dibaca: {exc}"
            )
    
            return pd.DataFrame(
                columns=[
                    "ID",
                    "Nama",
                    "NIP",
                    "Golongan",
                    "Status",
                ]
            )
    
    @st.cache_data(ttl=60)
    def load_data_spbu():
        """
        Prioritas:
        1. Master perusahaan dari Supabase
           yang teridentifikasi sebagai SPBU/PUBBM.
        2. data_spbu.csv sebagai data fallback/legacy.
    
        Hasil akhir tetap menggunakan kolom:
        - Nama SPBU
        - Alamat
        """
    
        daftar_data = []
    
        # =====================================================
        # 1. AMBIL DATA DARI SUPABASE
        # =====================================================
        try:
            supabase = get_supabase_pubbm()
    
            # Ambil UTTP PUBBM yang sudah dikenal
            response_uttp = (
                supabase
                .table("uttp")
                .select(
                    "perusahaan_id, nomor_seri"
                )
                .eq(
                    "jenis_uttp",
                    "Pompa Ukur BBM"
                )
                .execute()
            )
            # =====================================================
            # PETA NOMOR SPBU BERDASARKAN PERUSAHAAN
            # =====================================================
            nomor_spbu_map = {}
            
            for row in (
                response_uttp.data
                or []
            ):
                perusahaan_id = row.get(
                    "perusahaan_id"
                )
            
                nomor_spbu = str(
                    row.get(
                        "nomor_seri",
                        ""
                    )
                    or ""
                ).strip()
            
                if (
                    perusahaan_id is not None
                    and nomor_spbu
                ):
                    nomor_spbu_map[
                        perusahaan_id
                    ] = nomor_spbu
            perusahaan_ids_pubbm = {
                row.get("perusahaan_id")
                for row in (
                    response_uttp.data
                    or []
                )
                if row.get(
                    "perusahaan_id"
                ) is not None
            }
    
            # Ambil master perusahaan
            response_perusahaan = (
                supabase
                .table("perusahaan")
                .select(
                    "id, nama_perusahaan, alamat"
                )
                .execute()
            )
    
            for row in (
                response_perusahaan.data
                or []
            ):
                perusahaan_id = row.get(
                    "id"
                )
    
                nama = str(
                    row.get(
                        "nama_perusahaan",
                        ""
                    )
                    or ""
                ).strip()
    
                alamat = str(
                    row.get(
                        "alamat",
                        ""
                    )
                    or ""
                ).strip()
    
                nama_upper = nama.upper()
    
                # =============================================
                # PERUSAHAAN DIANGGAP SPBU JIKA:
                # 1. Sudah punya UTTP Pompa Ukur BBM
                # ATAU
                # 2. Nama menunjukkan SPBU/Pertashop/Shell/BP/Vivo
                # =============================================
                merupakan_pubbm = (
                    perusahaan_id
                    in perusahaan_ids_pubbm
                    or "SPBU" in nama_upper
                    or "PERTASHOP" in nama_upper
                    or "SHELL" in nama_upper
                    or "BP AKR" in nama_upper
                    or "VIVO" in nama_upper
                )
    
                if (
                    merupakan_pubbm
                    and nama
                ):
                    daftar_data.append({
                        "Nama SPBU": nama,
                        "Nomor SPBU": str(
                            nomor_spbu_map.get(
                                perusahaan_id,
                                ""
                            )
                            or ""
                        ).strip(),
                        "Alamat": alamat,
                    })
    
        except Exception:
            # Jika Supabase bermasalah,
            # aplikasi tetap bisa memakai CSV.
            pass
    
        # =====================================================
        # 2. TAMBAHKAN DATA LEGACY DARI CSV
        # =====================================================
        try:
            df_csv = pd.read_csv(
                "data/data_spbu.csv",
                sep=";",
                encoding="utf-8-sig"
            )
    
            df_csv.columns = (
                df_csv.columns
                .str.strip()
            )
    
            if (
                "Nama SPBU"
                in df_csv.columns
            ):
                for _, row in (
                    df_csv.iterrows()
                ):
                    nama = str(
                        row.get(
                            "Nama SPBU",
                            ""
                        )
                        or ""
                    ).strip()
    
                    alamat = str(
                        row.get(
                            "Alamat",
                            ""
                        )
                        or ""
                    ).strip()
    
                    if (
                        nama
                        and nama.lower()
                        != "nan"
                    ):
                        match_nomor = re.search(
                            r"SPBU\s*[\d\.-]+",
                            nama,
                            re.IGNORECASE,
                        )
                        
                        nomor_spbu_csv = (
                            match_nomor.group(0).upper()
                            if match_nomor
                            else ""
                        )
                        
                        daftar_data.append({
                            "Nama SPBU": nama,
                            "Nomor SPBU": nomor_spbu_csv,
                            "Alamat": (
                                ""
                                if alamat.lower()
                                == "nan"
                                else alamat
                            ),
                        })
    
        except FileNotFoundError:
            pass
    
        # =====================================================
        # 3. SUSUN DATAFRAME
        # =====================================================
        if not daftar_data:
            return pd.DataFrame(
                columns=[
                    "Nama SPBU",
                    "Nomor SPBU",
                    "Alamat"
                ]
            )
    
        df = pd.DataFrame(
            daftar_data
        )
    
        # =====================================================
        # 4. HAPUS DUPLIKAT
        # =====================================================
        df["Nama SPBU"] = (
            df["Nama SPBU"]
            .fillna("")
            .astype(str)
            .str.strip()
        )
        df["Nomor SPBU"] = (
            df["Nomor SPBU"]
            .fillna("")
            .astype(str)
            .str.strip()
        )
        
        df.loc[
            df["Nomor SPBU"].str.lower() == "nan",
            "Nomor SPBU"
        ] = ""
        df["Alamat"] = (
            df["Alamat"]
            .fillna("")
            .astype(str)
            .str.strip()
        )
    
        df = df[
            df["Nama SPBU"] != ""
        ]
    
        df = (
            df
            .drop_duplicates(
                subset=[
                    "Nama SPBU"
                ],
                keep="first"
            )
            .sort_values(
                "Nama SPBU"
            )
            .reset_index(
                drop=True
            )
        )
    
        return df
    
    # =========================
    # SESSION STATE AWAL
    # =========================
    if "data_penera" not in st.session_state:
        st.session_state.data_penera = load_data_penera()
    
    if "saved_data" not in st.session_state:
        st.session_state.saved_data = {}
    if "pubbm_dispenser" not in st.session_state:
        st.session_state.pubbm_dispenser = pd.DataFrame(
            columns=[
                "No",
                "Posisi",
                "Merk",
                "Tipe",
                "No. Seri",
                "Media",
                "K-Faktor",
            ]
        )
    if "data_spbu" not in st.session_state:
        st.session_state.data_spbu = load_data_spbu()
    if "data_bejana" not in st.session_state:
        st.session_state.data_bejana = load_data_bejana()
    if "data_media_spbu" not in st.session_state:
        st.session_state.data_media_spbu = load_data_media_spbu()
    if "data_pubbm" not in st.session_state:
        st.session_state.data_pubbm = {}
    if "nip_penera_1_pubbm" not in st.session_state:
        st.session_state.nip_penera_1_pubbm = ""

    if "golongan_penera_1_pubbm" not in st.session_state:
        st.session_state.golongan_penera_1_pubbm = ""

    if "nip_penera_2_pubbm" not in st.session_state:
        st.session_state.nip_penera_2_pubbm = ""

    if "golongan_penera_2_pubbm" not in st.session_state:
        st.session_state.golongan_penera_2_pubbm = ""
    if "pubbm_generated_files" not in st.session_state:
        st.session_state.pubbm_generated_files = {}
        
    def pulihkan_data_pubbm():
        data = st.session_state.get("data_pubbm", {})
    
        if not data:
            return
    
        # =====================================================
        # IDENTITAS SPBU
        # =====================================================
        nama_spbu_restore = str(
            data.get(
                "pemilik",
                ""
            )
            or ""
        ).strip()
        
        alamat_spbu_restore = str(
            data.get(
                "alamat",
                ""
            )
            or ""
        ).strip()
        
        st.session_state[
            "nama_perusahaan"
        ] = nama_spbu_restore
        
        st.session_state[
            "alamat_input_pubbm"
        ] = alamat_spbu_restore
        # =====================================================
        # NOMOR SPBU
        # =====================================================
        st.session_state[
            "nomor_spbu_pubbm"
        ] = str(
            data.get(
                "nama_spbu",
                ""
            )
            or ""
        ).strip()

        # =====================================================
        # PULIHKAN PILIHAN SPBU
        # =====================================================
        df_spbu = st.session_state.get(
            "data_spbu"
        )
        
        spbu_ditemukan = False
        
        if (
            df_spbu is not None
            and not df_spbu.empty
            and nama_spbu_restore
        ):
            daftar_spbu = (
                df_spbu["Nama SPBU"]
                .dropna()
                .astype(str)
                .str.strip()
                .tolist()
            )
        
            if nama_spbu_restore in daftar_spbu:
                st.session_state[
                    "spbu_select"
                ] = nama_spbu_restore
        
                st.session_state[
                    "input_manual_spbu"
                ] = False
        
                spbu_ditemukan = True
        
        
        # Jika nama SPBU tidak ada pada master,
        # tampilkan sebagai input manual
        if (
            nama_spbu_restore
            and not spbu_ditemukan
        ):
            st.session_state[
                "spbu_select"
            ] = ""
        
            st.session_state[
                "input_manual_spbu"
            ] = True
    
        # Sertifikat
        st.session_state["jenis_pengujian_pubbm"] = data.get(
            "jenis_pengujian",
            "Tera Ulang"
        )
    
        tanggal_pengujian_restore = data.get(
            "tanggal_pengujian",
            date.today()
        )

        if isinstance(
            tanggal_pengujian_restore,
            str
        ):
            try:
                tanggal_pengujian_restore = (
                    datetime.strptime(
                        tanggal_pengujian_restore,
                        "%Y-%m-%d"
                    ).date()
                )
            except ValueError:
                tanggal_pengujian_restore = date.today()

        st.session_state[
            "tanggal_pengujian_pubbm"
        ] = tanggal_pengujian_restore


        tanggal_cetak_restore = data.get(
            "tanggal_cetak",
            date.today()
        )

        if isinstance(
            tanggal_cetak_restore,
            str
        ):
            try:
                tanggal_cetak_restore = (
                    datetime.strptime(
                        tanggal_cetak_restore,
                        "%Y-%m-%d"
                    ).date()
                )
            except ValueError:
                tanggal_cetak_restore = date.today()

        st.session_state[
            "tanggal_cetak_pubbm"
        ] = tanggal_cetak_restore
    
        st.session_state["nomor_sertifikat_pubbm"] = data.get(
            "nomor_sertifikat",
            ""
        )
    
        st.session_state["nomor_order_pubbm"] = data.get(
            "nomor_order",
            ""
        )
    
        # Penera
        st.session_state["jumlah_penera"] = data.get(
            "jumlah_penera",
            1
        )
    
        st.session_state["penera_1_select"] = data.get(
            "penera_1",
            ""
        )
    
        st.session_state["penera_2_select"] = data.get(
            "penera_2",
            ""
        )
    
        # Pulihkan NIP dan Golongan Penera 1
        st.session_state[
            "nip_penera_1_pubbm"
        ] = str(
            data.get(
                "nip_penera_1",
                ""
            )
        ).strip()

        st.session_state[
            "golongan_penera_1_pubbm"
        ] = str(
            data.get(
                "golongan_penera_1",
                ""
            )
        ).strip()

        # Pulihkan NIP dan Golongan Penera 2
        st.session_state[
            "nip_penera_2_pubbm"
        ] = str(
            data.get(
                "nip_penera_2",
                ""
            )
        ).strip()

        st.session_state[
            "golongan_penera_2_pubbm"
        ] = str(
            data.get(
                "golongan_penera_2",
                ""
            )
        ).strip()
        # =====================================================
        # ALAT STANDAR
        # =====================================================
        alat_standar = data.get(
            "alat_standar"
        )
        # =====================================================
        # NORMALISASI NOMOR ALAT STANDAR
        # =====================================================
        if (
            isinstance(
                alat_standar,
                pd.DataFrame
            )
            and not alat_standar.empty
            and "No" in alat_standar.columns
        ):
            alat_standar = (
                alat_standar.copy()
            )
        
            alat_standar["No"] = (
                pd.to_numeric(
                    alat_standar["No"],
                    errors="coerce"
                )
            )
        
            alat_standar = (
                alat_standar[
                    alat_standar["No"].notna()
                ]
                .copy()
            )
        
            alat_standar["No"] = (
                alat_standar["No"]
                .astype(int)
            )
            # =====================================================
            # SINKRONKAN ALAT STANDAR HASIL NORMALISASI
            # =====================================================
            jumlah_alat_standar_normal = (
                len(alat_standar)
                if not alat_standar.empty
                else 1
            )
            
            data[
                "alat_standar"
            ] = alat_standar.copy()
            
            data[
                "jumlah_alat_standar"
            ] = jumlah_alat_standar_normal
            
            st.session_state[
                "data_pubbm"
            ] = data
            
            
            # Sinkronkan juga saved_data jika tersedia
            if isinstance(
                st.session_state.get(
                    "saved_data"
                ),
                dict
            ):
                st.session_state[
                    "saved_data"
                ][
                    "alat_standar"
                ] = alat_standar.copy()
            
                st.session_state[
                    "saved_data"
                ][
                    "jumlah_alat_standar"
                ] = jumlah_alat_standar_normal
        if (
            isinstance(
                alat_standar,
                pd.DataFrame
            )
            and not alat_standar.empty
        ):
            jumlah_alat_standar = len(
                alat_standar
            )
        
        else:
            jumlah_alat_standar = int(
                data.get(
                    "jumlah_alat_standar",
                    1
                )
                or 1
            )
        
        st.session_state[
            "jumlah_alat_standar_pubbm"
        ] = max(
            1,
            jumlah_alat_standar
        )
        
        
        # =====================================================
        # PULIHKAN PILIHAN BEJANA
        # =====================================================
        if (
            isinstance(
                alat_standar,
                pd.DataFrame
            )
            and not alat_standar.empty
        ):
            for _, row in alat_standar.iterrows():
        
                nomor = int(
                    row.get(
                        "No",
                        1
                    )
                )
        
                merk = str(
                    row.get(
                        "Merk",
                        ""
                    )
                ).strip()
        
                nomor_seri = str(
                    row.get(
                        "Nomor Seri",
                        ""
                    )
                ).strip()
        
                if nomor_seri.endswith(
                    ".0"
                ):
                    nomor_seri = (
                        nomor_seri[:-2]
                    )
        
                st.session_state[
                    f"bejana_select_{nomor}"
                ] = (
                    f"{merk} | "
                    f"No Seri : {nomor_seri}"
                )
        
        
        # =====================================================
        # DISPENSER
        # =====================================================
        dispenser_df = data.get(
            "dispenser"
        )
        
        if (
            isinstance(
                dispenser_df,
                pd.DataFrame
            )
            and not dispenser_df.empty
            and "No" in dispenser_df.columns
        ):
            jumlah_dispenser = (
                dispenser_df[
                    "No"
                ]
                .dropna()
                .nunique()
            )
        
        else:
            jumlah_dispenser = int(
                data.get(
                    "jumlah_dispenser",
                    1
                )
                or 1
            )
        
        st.session_state[
            "jumlah_dispenser_pubbm"
        ] = max(
            1,
            int(
                jumlah_dispenser
            )
        )
    
        # =====================================================
        # PULIHKAN DATA DISPENSER
        # =====================================================
        dispenser_df = data.get(
            "dispenser"
        )

        # =====================================================
        # NORMALISASI NOMOR DISPENSER
        # =====================================================
        if (
            isinstance(
                dispenser_df,
                pd.DataFrame
            )
            and not dispenser_df.empty
            and "No" in dispenser_df.columns
        ):
            dispenser_df = (
                dispenser_df.copy()
            )

            dispenser_df["No"] = (
                pd.to_numeric(
                    dispenser_df["No"],
                    errors="coerce"
                )
            )

            dispenser_df = (
                dispenser_df[
                    dispenser_df["No"].notna()
                ]
                .copy()
            )

            dispenser_df["No"] = (
                dispenser_df["No"]
                .astype(int)
            )

        else:
            dispenser_df = pd.DataFrame(
                columns=[
                    "No",
                    "Posisi",
                    "Merk",
                    "Tipe",
                    "No. Seri",
                    "Media",
                    "K-Faktor",
                ]
            )

        # =====================================================
        # SINKRONKAN DISPENSER HASIL NORMALISASI
        # =====================================================
        st.session_state[
            "pubbm_dispenser"
        ] = dispenser_df.copy()

        data[
            "dispenser"
        ] = dispenser_df.copy()

        data[
            "jumlah_dispenser"
        ] = (
            int(
                dispenser_df["No"]
                .nunique()
            )
            if not dispenser_df.empty
            else int(
                data.get(
                    "jumlah_dispenser",
                    1
                )
                or 1
            )
        )

        st.session_state[
            "jumlah_dispenser_pubbm"
        ] = max(
            1,
            int(
                data[
                    "jumlah_dispenser"
                ]
            )
        )

        st.session_state[
            "data_pubbm"
        ] = data

        # =====================================================
        # SINKRONKAN SAVED DATA
        # =====================================================
        if isinstance(
            st.session_state.get(
                "saved_data"
            ),
            dict
        ):
            st.session_state[
                "saved_data"
            ][
                "dispenser"
            ] = dispenser_df.copy()

            st.session_state[
                "saved_data"
            ][
                "jumlah_dispenser"
            ] = data[
                "jumlah_dispenser"
            ]

        # =====================================================
        # PULIHKAN WIDGET SETIAP DISPENSER
        # =====================================================
        if not dispenser_df.empty:

            for nomor_dispenser in sorted(
                dispenser_df["No"]
                .dropna()
                .unique()
            ):
                nomor_dispenser = int(
                    nomor_dispenser
                )

                data_dispenser = (
                    dispenser_df[
                        dispenser_df["No"]
                        == nomor_dispenser
                    ]
                    .reset_index(
                        drop=True
                    )
                )

                if data_dispenser.empty:
                    continue

                # =============================================
                # IDENTITAS DISPENSER
                # =============================================
                baris_pertama = (
                    data_dispenser.iloc[0]
                )

                merk_restore = str(
                    baris_pertama.get(
                        "Merk",
                        ""
                    )
                    or ""
                ).strip()

                tipe_restore = str(
                    baris_pertama.get(
                        "Tipe",
                        ""
                    )
                    or ""
                ).strip()

                no_seri_restore = str(
                    baris_pertama.get(
                        "No. Seri",
                        ""
                    )
                    or ""
                ).strip()

                if merk_restore.lower() == "nan":
                    merk_restore = ""

                if tipe_restore.lower() == "nan":
                    tipe_restore = ""

                if no_seri_restore.lower() == "nan":
                    no_seri_restore = ""

                if no_seri_restore.endswith(
                    ".0"
                ):
                    no_seri_restore = (
                        no_seri_restore[:-2]
                    )

                st.session_state[
                    f"merk_{nomor_dispenser}"
                ] = merk_restore

                st.session_state[
                    f"tipe_{nomor_dispenser}"
                ] = tipe_restore

                st.session_state[
                    f"no_seri_{nomor_dispenser}"
                ] = no_seri_restore

                # =============================================
                # JUMLAH POSISI / NOZZLE
                # =============================================
                jumlah_posisi = len(
                    data_dispenser
                )

                st.session_state[
                    f"jumlah_posisi_{nomor_dispenser}"
                ] = max(
                    1,
                    jumlah_posisi
                )

                # =============================================
                # POSISI & MEDIA
                # =============================================
                for idx, row in (
                    data_dispenser.iterrows()
                ):
                    nomor_posisi = (
                        idx + 1
                    )

                    posisi_restore = str(
                        row.get(
                            "Posisi",
                            ""
                        )
                        or ""
                    ).strip()

                    if (
                        posisi_restore.lower()
                        == "nan"
                    ):
                        posisi_restore = ""

                    media_tersimpan = str(
                        row.get(
                            "Media",
                            ""
                        )
                        or ""
                    ).strip()
                    
                    if (
                        media_tersimpan.lower()
                        == "nan"
                    ):
                        media_tersimpan = ""
                    
                    
                    # =============================================
                    # K-FAKTOR
                    # =============================================
                    k_faktor_restore = str(
                        row.get(
                            "K-Faktor",
                            ""
                        )
                        or ""
                    ).strip()
                    
                    if (
                        k_faktor_restore.lower()
                        == "nan"
                    ):
                        k_faktor_restore = ""
                    
                    
                    st.session_state[
                        f"posisi_{nomor_dispenser}_{nomor_posisi}"
                    ] = posisi_restore
                    
                    st.session_state[
                        f"media_restore_{nomor_dispenser}_{nomor_posisi}"
                    ] = media_tersimpan
                    
                    st.session_state[
                        f"k_faktor_{nomor_dispenser}_{nomor_posisi}"
                    ] = k_faktor_restore
                    
    def kembali_ke_input_pubbm():
        pulihkan_data_pubbm()

        st.session_state["mode_pubbm"] = (
            "📝 Input Data Pengujian"
        )
        
    def reset_form_pubbm():
        key_tetap = {
            "data_penera",
            "data_spbu",
            "data_bejana",
            "data_media_spbu",
        }

        prefix_hapus = (
            "merk_",
            "tipe_",
            "no_seri_",
            "posisi_",
            "media_",
            "media_manual_",
            "media_restore_",
            "jumlah_posisi_",
            "bejana_select_",
            "k_faktor_",
        )

        key_hapus_langsung = {
            "saved_data",
            "data_pubbm",
            "pubbm_dispenser",
            "pubbm_generated_files",
            "nama_perusahaan",
            "alamat_input_pubbm",
            "input_manual_spbu",
            "spbu_select",
            "jenis_pengujian_pubbm",
            "tanggal_pengujian_pubbm",
            "tanggal_cetak_pubbm",
            "nomor_sertifikat_pubbm",
            "nomor_order_pubbm",
            "jumlah_penera",
            "penera_1_select",
            "penera_2_select",
            "nip_penera_1_pubbm",
            "nip_penera_2_pubbm",
            "golongan_penera_1_pubbm",
            "golongan_penera_2_pubbm",
            "jumlah_alat_standar_pubbm",
            "jumlah_dispenser_pubbm",
            "mode_pubbm",
            "pubbm_edit_pengujian_id",
            "pubbm_next_mode",
            "pubbm_filter_tahun",
            "pubbm_filter_jenis_pengujian",
            "pubbm_filter_nozzle",
            "pubbm_detail_riwayat",
            "pubbm_riwayat_spbu",
            "nomor_spbu_pubbm",
            "pubbm_draft_widget",
            "pubbm_mode_sebelumnya",
        }

        for key in list(st.session_state.keys()):
            if key in key_tetap:
                continue

            if (
                key in key_hapus_langsung
                or key.startswith(prefix_hapus)
            ):
                st.session_state.pop(
                    key,
                    None
                )
    def gunakan_data_lama_untuk_edit_pubbm(
        alat,
        perusahaan,
        pengujian
    ):
        """
        Memuat satu riwayat PUBBM kembali ke form
        untuk diedit.
    
        Data JSONB dari Supabase dikembalikan
        menjadi DataFrame karena form PUBBM
        masih menggunakan DataFrame.
        """
    
        detail = (
            pengujian.get(
                "data_pengujian"
            )
            or {}
        )
    
        # =====================================================
        # ID PENGUJIAN YANG AKAN DI-UPDATE
        # =====================================================
        st.session_state[
            "pubbm_edit_pengujian_id"
        ] = pengujian.get(
            "id"
        )
    
        # =====================================================
        # DISPENSER DARI JSON -> DATAFRAME
        # =====================================================
        dispenser_records = (
            detail.get(
                "dispenser",
                []
            )
            or []
        )
    
        dispenser_df = pd.DataFrame(
            dispenser_records,
            columns=[
                "No",
                "Posisi",
                "Merk",
                "Tipe",
                "No. Seri",
                "Media",
                "K-Faktor",
            ]
        )
    
        # =====================================================
        # ALAT STANDAR DARI JSON -> DATAFRAME
        # =====================================================
        alat_standar_records = (
            detail.get(
                "alat_standar",
                []
            )
            or []
        )
    
        alat_standar_df = pd.DataFrame(
            alat_standar_records,
            columns=[
                "No",
                "Merk",
                "Nomor Seri",
                "Telusuran",
            ]
        )
    
        # =====================================================
        # SUSUN DATA UNTUK FORM
        # =====================================================
        data_edit = {
            "nomor_sertifikat": (
                pengujian.get(
                    "nomor_sertifikat",
                    ""
                )
            ),
    
            "nomor_order": (
                pengujian.get(
                    "nomor_order",
                    ""
                )
            ),
    
            "tanggal_pengujian": (
                pengujian.get(
                    "tanggal_pengujian",
                    ""
                )
            ),
    
            "tanggal_cetak": (
                pengujian.get(
                    "tanggal_sertifikat",
                    ""
                )
            ),
    
            "nama_alat": detail.get(
                "nama_alat",
                "Pompa Ukur BBM (Dispenser)"
            ),
    
            "pemilik": str(
                perusahaan.get(
                    "nama_perusahaan",
                    ""
                )
                or detail.get(
                    "pemilik",
                    ""
                )
                or ""
            ).strip(),
            
            "nama_spbu": str(
                detail.get(
                    "nama_spbu",
                    ""
                )
                or alat.get(
                    "nomor_seri",
                    ""
                )
                or ""
            ).strip(),
            
            "alamat": str(
                perusahaan.get(
                    "alamat",
                    ""
                )
                or detail.get(
                    "alamat",
                    ""
                )
                or ""
            ).strip(),
    
            "jenis_pengujian": (
                pengujian.get(
                    "jenis_pengujian",
                    "Tera Ulang"
                )
            ),
    
            # =============================================
            # PENERA
            # =============================================
            "penera_1": pengujian.get(
                "penera_1",
                detail.get(
                    "penera_1",
                    ""
                )
            ),
    
            "nip_penera_1": detail.get(
                "nip_penera_1",
                ""
            ),
    
            "golongan_penera_1": detail.get(
                "golongan_penera_1",
                ""
            ),
    
            "penera_2": pengujian.get(
                "penera_2",
                detail.get(
                    "penera_2",
                    ""
                )
            ),
    
            "nip_penera_2": detail.get(
                "nip_penera_2",
                ""
            ),
    
            "golongan_penera_2": detail.get(
                "golongan_penera_2",
                ""
            ),
    
            "jumlah_penera": int(
                detail.get(
                    "jumlah_penera",
                    1
                )
                or 1
            ),
    
            # =============================================
            # ALAT STANDAR
            # =============================================
            "jumlah_alat_standar": (
                len(alat_standar_df)
                if not alat_standar_df.empty
                else 1
            ),
            
            "alat_standar": alat_standar_df,
    
            # =============================================
            # DISPENSER
            # =============================================
            "jumlah_dispenser": (
                int(
                    dispenser_df["No"].nunique()
                )
                if not dispenser_df.empty
                else 1
            ),
            
            "dispenser": dispenser_df,
        }
    
        # =====================================================
        # SIMPAN SEBAGAI DATA AKTIF
        # =====================================================
        st.session_state[
            "data_pubbm"
        ] = data_edit
    
        st.session_state[
            "saved_data"
        ] = dict(
            data_edit
        )
        # =====================================================
        # SINKRONKAN DATA DISPENSER AKTIF
        # =====================================================
        st.session_state[
            "pubbm_dispenser"
        ] = dispenser_df.copy()
        # =====================================================
        # BERSIHKAN WIDGET DINAMIS DARI PENGUJIAN SEBELUMNYA
        # =====================================================
        prefix_hapus = (
            "merk_",
            "tipe_",
            "no_seri_",
            "posisi_",
            "media_",
            "media_manual_",
            "media_restore_",
            "jumlah_posisi_",
            "bejana_select_",
            "k_faktor_",
        )
        
        for key in list(
            st.session_state.keys()
        ):
            if key.startswith(
                prefix_hapus
            ):
                st.session_state.pop(
                    key,
                    None
                )
        # =====================================================
        # PULIHKAN SELURUH WIDGET FORM
        # =====================================================
        pulihkan_data_pubbm()
    
        # =====================================================
        # HAPUS FILE HASIL GENERATE LAMA
        # =====================================================
        st.session_state[
            "pubbm_generated_files"
        ] = {}
    
        # =====================================================
        # PINDAH KE INPUT DATA
        # =====================================================
        st.session_state[
            "pubbm_next_mode"
        ] = "📝 Input Data Pengujian"
    def gunakan_data_lama_untuk_pengujian_baru_pubbm(
        alat,
        perusahaan,
        pengujian
    ):
        """
        Menggunakan riwayat PUBBM sebagai dasar
        pengujian baru.
    
        Identitas SPBU, dispenser/nozzle,
        alat standar, dan penera dapat digunakan kembali.
    
        Nomor dokumen dan tanggal dibuat baru.
        """
    
        detail = (
            pengujian.get(
                "data_pengujian"
            )
            or {}
        )
    
        # =====================================================
        # PASTIKAN BUKAN MODE EDIT
        # =====================================================
        st.session_state.pop(
            "pubbm_edit_pengujian_id",
            None
        )
    
        # =====================================================
        # DATA DISPENSER JSON -> DATAFRAME
        # =====================================================
        dispenser_records = (
            detail.get(
                "dispenser",
                []
            )
            or []
        )
    
        dispenser_df = pd.DataFrame(
            dispenser_records,
            columns=[
                "No",
                "Posisi",
                "Merk",
                "Tipe",
                "No. Seri",
                "Media",
                "K-Faktor",
            ]
        )
    
        # =====================================================
        # ALAT STANDAR JSON -> DATAFRAME
        # =====================================================
        alat_standar_records = (
            detail.get(
                "alat_standar",
                []
            )
            or []
        )
    
        alat_standar_df = pd.DataFrame(
            alat_standar_records,
            columns=[
                "No",
                "Merk",
                "Nomor Seri",
                "Telusuran",
            ]
        )
    
        # =====================================================
        # TANGGAL BARU
        # =====================================================
        hari_ini = date.today()
    
        nomor_sertifikat_baru = (
            generate_nomor_sertifikat(
                hari_ini
            )
        )
    
        nomor_order_baru = (
            generate_nomor_order(
                hari_ini
            )
        )
    
        # =====================================================
        # SUSUN DATA PENGUJIAN BARU
        # =====================================================
        data_baru = {
    
            # =============================================
            # NOMOR DOKUMEN BARU
            # =============================================
            "nomor_sertifikat": (
                nomor_sertifikat_baru
            ),
    
            "nomor_order": (
                nomor_order_baru
            ),
    
            # =============================================
            # TANGGAL BARU
            # =============================================
            "tanggal_pengujian": (
                hari_ini
            ),
    
            "tanggal_cetak": (
                hari_ini
            ),
    
            # =============================================
            # IDENTITAS SPBU
            # =============================================
            "nama_alat": detail.get(
                "nama_alat",
                "Pompa Ukur BBM (Dispenser)"
            ),
    
            "pemilik": str(
                perusahaan.get(
                    "nama_perusahaan",
                    ""
                )
                or detail.get(
                    "pemilik",
                    ""
                )
                or ""
            ).strip(),
    
            "nama_spbu": (
                str(
                    detail.get(
                        "nama_spbu",
                        ""
                    )
                    or alat.get(
                        "nomor_seri",
                        ""
                    )
                    or ""
                ).strip()
            ),
    
            "alamat": str(
                perusahaan.get(
                    "alamat",
                    ""
                )
                or detail.get(
                    "alamat",
                    ""
                )
                or ""
            ).strip(),
    
            # =============================================
            # DEFAULT PENGUJIAN BARU
            # =============================================
            "jenis_pengujian": (
                "Tera Ulang"
            ),
    
            # =============================================
            # PENERA
            # =============================================
            "penera_1": detail.get(
                "penera_1",
                pengujian.get(
                    "penera_1",
                    ""
                )
            ),
    
            "nip_penera_1": detail.get(
                "nip_penera_1",
                ""
            ),
    
            "golongan_penera_1": detail.get(
                "golongan_penera_1",
                ""
            ),
    
            "penera_2": detail.get(
                "penera_2",
                pengujian.get(
                    "penera_2",
                    ""
                )
            ),
    
            "nip_penera_2": detail.get(
                "nip_penera_2",
                ""
            ),
    
            "golongan_penera_2": detail.get(
                "golongan_penera_2",
                ""
            ),
    
            "jumlah_penera": int(
                detail.get(
                    "jumlah_penera",
                    1
                )
                or 1
            ),
    
            # =============================================
            # ALAT STANDAR
            # =============================================
            "jumlah_alat_standar": (
                len(alat_standar_df)
                if not alat_standar_df.empty
                else 1
            ),
            
            "alat_standar": (
                alat_standar_df
            ),
    
            # =============================================
            # DISPENSER / NOZZLE
            # =============================================
            "jumlah_dispenser": (
                int(
                    dispenser_df["No"].nunique()
                )
                if not dispenser_df.empty
                else 1
            ),
            
            "dispenser": (
                dispenser_df
            ),
        }
    
        # =====================================================
        # DATA AKTIF
        # =====================================================
        st.session_state[
            "data_pubbm"
        ] = data_baru
    
        st.session_state[
            "saved_data"
        ] = dict(
            data_baru
        )
        # =====================================================
        # SINKRONKAN DATA DISPENSER AKTIF
        # =====================================================
        st.session_state[
            "pubbm_dispenser"
        ] = dispenser_df.copy()
        # =====================================================
        # BERSIHKAN WIDGET DINAMIS LAMA
        # =====================================================
        prefix_hapus = (
            "merk_",
            "tipe_",
            "no_seri_",
            "posisi_",
            "media_",
            "k_faktor_",
            "media_manual_",
            "media_restore_",
            "jumlah_posisi_",
            "bejana_select_",
        )
    
        for key in list(
            st.session_state.keys()
        ):
            if key.startswith(
                prefix_hapus
            ):
                st.session_state.pop(
                    key,
                    None
                )
    
        # =====================================================
        # BERSIHKAN NOMOR / TANGGAL WIDGET LAMA
        # =====================================================
        for key in [
            "nomor_sertifikat_pubbm",
            "nomor_order_pubbm",
            "tanggal_pengujian_pubbm",
            "tanggal_cetak_pubbm",
        ]:
            st.session_state.pop(
                key,
                None
            )
    
        # =====================================================
        # PULIHKAN DATA KE FORM
        # =====================================================
        pulihkan_data_pubbm()
    
        # =====================================================
        # FILE GENERATED LAMA DIHAPUS
        # =====================================================
        st.session_state[
            "pubbm_generated_files"
        ] = {}
    
        # =====================================================
        # MASUK KE INPUT
        # =====================================================
        st.session_state[
            "pubbm_next_mode"
        ] = "📝 Input Data Pengujian"
    def validasi_data_pubbm(
        pemilik,
        alamat,
        penera_1,
        jumlah_penera,
        penera_2,
        alat_standar_df,
        dispenser_df,
        jumlah_dispenser,
    ):
        errors = []

        if not str(pemilik).strip():
            errors.append(
                "Nama SPBU atau perusahaan belum diisi."
            )

        if not str(alamat).strip():
            errors.append(
                "Alamat SPBU atau perusahaan belum diisi."
            )

        if not str(penera_1).strip():
            errors.append(
                "Penera 1 belum dipilih."
            )

        if (
            int(jumlah_penera) == 2
            and not str(penera_2).strip()
        ):
            errors.append(
                "Penera 2 belum dipilih."
            )

        if (
            alat_standar_df is None
            or not isinstance(
                alat_standar_df,
                pd.DataFrame
            )
            or alat_standar_df.empty
        ):
            errors.append(
                "Minimal satu Bejana Ukur Standar belum dipilih."
            )

        if (
            dispenser_df is None
            or not isinstance(
                dispenser_df,
                pd.DataFrame
            )
            or dispenser_df.empty
        ):
            errors.append(
                "Data pompa ukur BBM belum diisi."
            )

            return errors

        for nomor_dispenser in range(
            1,
            int(jumlah_dispenser) + 1
        ):
            merk = str(
                st.session_state.get(
                    f"merk_{nomor_dispenser}",
                    ""
                )
            ).strip()

            tipe = str(
                st.session_state.get(
                    f"tipe_{nomor_dispenser}",
                    ""
                )
            ).strip()

            no_seri = str(
                st.session_state.get(
                    f"no_seri_{nomor_dispenser}",
                    ""
                )
            ).strip()

            if not merk:
                errors.append(
                    f"Dispenser {nomor_dispenser}: merk belum diisi."
                )

            if not tipe:
                errors.append(
                    f"Dispenser {nomor_dispenser}: tipe belum diisi."
                )

            if not no_seri:
                errors.append(
                    f"Dispenser {nomor_dispenser}: nomor seri belum diisi."
                )

            jumlah_posisi = int(
                st.session_state.get(
                    f"jumlah_posisi_{nomor_dispenser}",
                    1
                )
            )

            for posisi_index in range(
                1,
                jumlah_posisi + 1
            ):
                posisi = str(
                    st.session_state.get(
                        f"posisi_{nomor_dispenser}_{posisi_index}",
                        ""
                    )
                ).strip()

                pilihan_media = str(
                    st.session_state.get(
                        f"media_{nomor_dispenser}_{posisi_index}",
                        ""
                    )
                ).strip()

                if not posisi:
                    errors.append(
                        f"Dispenser {nomor_dispenser}, "
                        f"posisi {posisi_index}: "
                        "posisi/nozzle belum diisi."
                    )

                if not pilihan_media:
                    errors.append(
                        f"Dispenser {nomor_dispenser}, "
                        f"posisi {posisi_index}: "
                        "media belum dipilih."
                    )

                if pilihan_media == OPSI_MEDIA_MANUAL:
                    media_manual = str(
                        st.session_state.get(
                            (
                                f"media_manual_"
                                f"{nomor_dispenser}_"
                                f"{posisi_index}"
                            ),
                            ""
                        )
                    ).strip()

                    if not media_manual:
                        errors.append(
                            f"Dispenser {nomor_dispenser}, "
                            f"posisi {posisi_index}: "
                            "nama media manual belum diisi."
                        )

        return errors
    # =========================================================
    # PINDAH MODE PUBBM SETELAH RERUN
    # =========================================================
    if "pubbm_next_mode" in st.session_state:
        st.session_state[
            "mode_pubbm"
        ] = st.session_state.pop(
            "pubbm_next_mode"
        )
    # =========================================================
    # SIMPAN DRAFT FORM SEBELUM MENINGGALKAN MENU INPUT
    # =========================================================
    def simpan_draft_widget_pubbm():
    
        mode_lama = st.session_state.get(
            "pubbm_mode_sebelumnya"
        )
    
        # Hanya simpan draft ketika user
        # sedang meninggalkan menu Input
        if (
            mode_lama
            != "📝 Input Data Pengujian"
        ):
            return
    
        key_form = {
            "nama_perusahaan",
            "alamat_input_pubbm",
            "input_manual_spbu",
            "spbu_select",
            "nomor_spbu_pubbm",
    
            "jenis_pengujian_pubbm",
            "tanggal_pengujian_pubbm",
            "tanggal_cetak_pubbm",
            "nomor_sertifikat_pubbm",
            "nomor_order_pubbm",
    
            "jumlah_penera",
            "penera_1_select",
            "penera_2_select",
            "nip_penera_1_pubbm",
            "nip_penera_2_pubbm",
            "golongan_penera_1_pubbm",
            "golongan_penera_2_pubbm",
    
            "jumlah_alat_standar_pubbm",
            "jumlah_dispenser_pubbm",
        }
    
        prefix_form = (
            "merk_",
            "tipe_",
            "no_seri_",
            "posisi_",
            "media_",
            "media_manual_",
            "media_restore_",
            "k_faktor_",
            "jumlah_posisi_",
            "bejana_select_",
        )
    
        draft = {}
    
        for key, value in list(
            st.session_state.items()
        ):
            if (
                key in key_form
                or key.startswith(
                    prefix_form
                )
            ):
                draft[key] = value
    
        st.session_state[
            "pubbm_draft_widget"
        ] = draft
    
    
    # =========================
    # SIDEBAR
    # =========================
    mode = st.sidebar.radio(
        "Menu",
        [
            "📝 Input Data Pengujian",
            "📄 Preview & Generate Data",
            "📚 Riwayat PU BBM",
        ],
        key="mode_pubbm",
        on_change=simpan_draft_widget_pubbm,
    )
    
    
    # =========================================================
    # PULIHKAN DATA SETIAP KEMBALI KE INPUT
    # =========================================================
    mode_sebelumnya = st.session_state.get(
        "pubbm_mode_sebelumnya"
    )
    
    if (
        mode == "📝 Input Data Pengujian"
        and mode_sebelumnya
        and mode_sebelumnya
        != "📝 Input Data Pengujian"
    ):
    
        draft = st.session_state.get(
            "pubbm_draft_widget",
            {}
        )
    
        # =============================================
        # PRIORITAS 1: DRAFT YANG BELUM DISIMPAN
        # =============================================
        if draft:
            for key, value in draft.items():
                st.session_state[
                    key
                ] = value
    
        # =============================================
        # PRIORITAS 2: DATA YANG SUDAH DISIMPAN
        # =============================================
        elif st.session_state.get(
            "data_pubbm"
        ):
            pulihkan_data_pubbm()
    
    
    st.session_state[
        "pubbm_mode_sebelumnya"
    ] = mode
    # =========================
    # TITLE
    # =========================
    st.title("⛽ Aplikasi Automasi Sertifikat Tera PU BBM")
    st.markdown("---")
    
    
    # =========================
    # MODE INPUT
    # =========================
    if mode == "📝 Input Data Pengujian":
    
        st.header("Masukkan Data Pengujian PU BBM")
        # =========================================================
        # INFORMASI MODE EDIT
        # =========================================================
        if st.session_state.get(
            "pubbm_edit_pengujian_id"
        ):
            st.warning(
                "✏️ Anda sedang mengedit pengujian yang sudah "
                "tersimpan. Generate Sertifikat akan memperbarui "
                "data pengujian lama."
            )
        
            if st.button(
                "❌ Batal Edit",
                use_container_width=True,
                key="pubbm_batal_edit"
            ):
                reset_form_pubbm()
        
                st.session_state[
                    "pubbm_next_mode"
                ] = "📝 Input Data Pengujian"
        
                st.rerun()
        # ======================== KOLOM 1-2 ========================
        col1, col2= st.columns(2)
    
        # ======================== KOLOM 1 ========================
        with col1:
            st.subheader("Identitas Pemilik / SPBU")

            df_spbu = st.session_state.get("data_spbu")

            if "nama_perusahaan" not in st.session_state:
                st.session_state.nama_perusahaan = (
                    st.session_state.saved_data.get(
                        "pemilik",
                        ""
                    )
                )

            if "alamat_input_pubbm" not in st.session_state:
                st.session_state.alamat_input_pubbm = (
                    st.session_state.saved_data.get(
                        "alamat",
                        ""
                    )
                )

            if "input_manual_spbu" not in st.session_state:
                st.session_state.input_manual_spbu = False

            if df_spbu is not None and not df_spbu.empty:
                all_names = (
                    df_spbu["Nama SPBU"]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .tolist()
                )

                st.selectbox(
                    "Cari & Pilih Nama SPBU",
                    options=[""] + all_names,
                    placeholder="Ketik nama SPBU...",
                    key="spbu_select",
                    on_change=update_spbu_terpilih,
                )

                st.text_area(
                    "Alamat",
                    height=90,
                    key="alamat_input_pubbm",
                    help="Alamat otomatis muncul dan tetap dapat diedit.",
                )

                st.checkbox(
                    "Input manual nama SPBU / perusahaan",
                    key="input_manual_spbu",
                )

                if st.session_state.input_manual_spbu:
                    st.text_input(
                        "Nama Pemilik / SPBU / Perusahaan",
                        key="nama_perusahaan",
                    )

            else:
                st.info(
                    "📂 File data perusahaan tidak ditemukan. "
                    "Silakan input manual."
                )

                st.text_input(
                    "Nama Pemilik / SPBU / Perusahaan",
                    key="nama_perusahaan",
                    placeholder=(
                        "Contoh: SPBU 34-15717 "
                        "PT. YASINCO INDO PRATAMA"
                    ),
                )

                st.text_area(
                    "Alamat",
                    height=90,
                    key="alamat_input_pubbm",
                    placeholder=(
                        "Contoh: Jalan Aria Wasangkara Desa Tapos "
                        "Kecamatan Tigaraksa Kabupaten Tangerang"
                    ),
                )
            # =====================================================
            # NOMOR SPBU
            # =====================================================
            if "nomor_spbu_pubbm" not in st.session_state:
            
                pemilik_awal = str(
                    st.session_state.get(
                        "nama_perusahaan",
                        ""
                    )
                    or ""
                ).strip()
            
                match_spbu_awal = re.search(
                    r"SPBU\s*[\d\.-]+",
                    pemilik_awal,
                    re.IGNORECASE,
                )
            
                if match_spbu_awal:
                    st.session_state[
                        "nomor_spbu_pubbm"
                    ] = (
                        match_spbu_awal
                        .group(0)
                        .upper()
                    )
            
                else:
                    st.session_state[
                        "nomor_spbu_pubbm"
                    ] = ""
            
            
            st.text_input(
                "Nomor SPBU",
                key="nomor_spbu_pubbm",
                placeholder="Contoh: 34-15717",
                help="Nomor SPBU tetap dapat diedit.",
            )
            pemilik = str(
                st.session_state.get(
                    "nama_perusahaan",
                    ""
                )
            ).strip()

            alamat = str(
                st.session_state.get(
                    "alamat_input_pubbm",
                    ""
                )
            ).strip()

            nomor_spbu = str(
                st.session_state.get(
                    "nomor_spbu_pubbm",
                    ""
                )
                or ""
            ).strip()
    
        # ======================== KOLOM 2 ========================
        with col2:
            st.subheader("Data Sertifikat")

            # ==========================================
            # NILAI AWAL DARI DATA TERSIMPAN
            # ==========================================
            if "jenis_pengujian_pubbm" not in st.session_state:
                st.session_state.jenis_pengujian_pubbm = (
                    st.session_state.saved_data.get(
                        "jenis_pengujian",
                        "Tera Ulang"
                    )
                )

            if "tanggal_pengujian_pubbm" not in st.session_state:
                tanggal_awal = st.session_state.saved_data.get(
                    "tanggal_pengujian",
                    date.today()
                )

                if isinstance(tanggal_awal, str):
                    try:
                        tanggal_awal = datetime.strptime(
                            tanggal_awal,
                            "%Y-%m-%d"
                        ).date()
                    except ValueError:
                        tanggal_awal = date.today()

                st.session_state.tanggal_pengujian_pubbm = (
                    tanggal_awal
                )

            if "tanggal_cetak_pubbm" not in st.session_state:
                tanggal_cetak_awal = st.session_state.saved_data.get(
                    "tanggal_cetak",
                    date.today()
                )

                if isinstance(tanggal_cetak_awal, str):
                    try:
                        tanggal_cetak_awal = datetime.strptime(
                            tanggal_cetak_awal,
                            "%Y-%m-%d"
                        ).date()
                    except ValueError:
                        tanggal_cetak_awal = date.today()

                st.session_state.tanggal_cetak_pubbm = (
                    tanggal_cetak_awal
                )

            # ==========================================
            # INPUT JENIS PENGUJIAN
            # ==========================================
            jenis_pengujian = st.selectbox(
                "Jenis Pengujian",
                ["Tera", "Tera Ulang"],
                key="jenis_pengujian_pubbm"
            )

            # ==========================================
            # INPUT TANGGAL PENGUJIAN
            # ==========================================
            tanggal_pengujian = st.date_input(
                "Tanggal Pengujian",
                key="tanggal_pengujian_pubbm",
                on_change=update_nomor_dokumen_pubbm,
            )

            # ==========================================
            # INPUT TANGGAL TANDA TANGAN
            # ==========================================
            tanggal_tanda_tangan = st.date_input(
                "Tanggal Tanda Tangan",
                key="tanggal_cetak_pubbm"
            )

            # ==========================================
            # NOMOR SERTIFIKAT & ORDER
            # ==========================================
            default_sertifikat = generate_nomor_sertifikat(
                tanggal_pengujian
            )

            default_order = generate_nomor_order(
                tanggal_pengujian
            )

            if "nomor_sertifikat_pubbm" not in st.session_state:
                st.session_state.nomor_sertifikat_pubbm = (
                    st.session_state.saved_data.get(
                        "nomor_sertifikat",
                        default_sertifikat
                    )
                )

            if "nomor_order_pubbm" not in st.session_state:
                st.session_state.nomor_order_pubbm = (
                    st.session_state.saved_data.get(
                        "nomor_order",
                        default_order
                    )
                )

            nomor_sertifikat = st.text_input(
                "Nomor Sertifikat",
                key="nomor_sertifikat_pubbm",
                placeholder=(
                    "Format: XXX.X.X.XX/XXXX/XXX-X/X/XXXX"
                )
            )

            nomor_order = st.text_input(
                "Nomor Order",
                key="nomor_order_pubbm",
                placeholder="Format nomor order"
            )

            # ==========================================
            # SIMPAN SEMENTARA
            # ==========================================
            st.session_state.saved_data[
                "jenis_pengujian"
            ] = jenis_pengujian

            st.session_state.saved_data[
                "tanggal_pengujian"
            ] = tanggal_pengujian

            st.session_state.saved_data[
                "tanggal_cetak"
            ] = tanggal_tanda_tangan

            st.session_state.saved_data[
                "nomor_sertifikat"
            ] = nomor_sertifikat

            st.session_state.saved_data[
                "nomor_order"
            ] = nomor_order
    
        st.markdown("---")
    
        # =========================
        # PENERA
        # =========================
        st.subheader("Penera / Pegawai Berhak")
    
        df_penera = st.session_state.get("data_penera")
    
        jumlah_penera = st.radio(
            "Jumlah Penera",
            [1, 2],
            horizontal=True,
            key="jumlah_penera"
        )
    
        col4, col5 = st.columns(2)
    
        # =========================
        # PENERA 1
        # =========================
        with col4:
    
            nama_penera_1 = st.selectbox(
                "Penera 1",
                options=(
                    [""]
                    + df_penera["Nama"]
                    .dropna()
                    .astype(str)
                    .tolist()
                ),
                key="penera_1_select",
                on_change=update_penera_1_pubbm,
            )

            penera_1 = nama_penera_1

            nip_penera_1 = str(
                st.session_state.get(
                    "nip_penera_1_pubbm",
                    ""
                )
            ).strip()

            golongan_penera_1 = str(
                st.session_state.get(
                    "golongan_penera_1_pubbm",
                    ""
                )
            ).strip()

            st.text_input(
                "NIP Penera 1",
                key="nip_penera_1_pubbm",
                disabled=True,
            )

            st.text_input(
                "Golongan Penera 1",
                key="golongan_penera_1_pubbm",
                disabled=True,
            )
    
    
        # =========================
        # PENERA 2
        # =========================
        if jumlah_penera == 2:
            with col5:
                nama_penera_2 = st.selectbox(
                    "Penera 2",
                    options=(
                        [""]
                        + df_penera["Nama"]
                        .dropna()
                        .astype(str)
                        .tolist()
                    ),
                    key="penera_2_select",
                    on_change=update_penera_2_pubbm,
                )

                penera_2 = nama_penera_2

                nip_penera_2 = str(
                    st.session_state.get(
                        "nip_penera_2_pubbm",
                        ""
                    )
                ).strip()

                golongan_penera_2 = str(
                    st.session_state.get(
                        "golongan_penera_2_pubbm",
                        ""
                    )
                ).strip()

                st.text_input(
                    "NIP Penera 2",
                    key="nip_penera_2_pubbm",
                    disabled=True,
                )

                st.text_input(
                    "Golongan Penera 2",
                    key="golongan_penera_2_pubbm",
                    disabled=True,
                )

        else:
            penera_2 = ""
            nip_penera_2 = ""
            golongan_penera_2 = ""
    
        st.markdown("---")
    
        # =========================
        # BEJANA UKUR STANDAR
        # =========================
        st.subheader("Perangkat Bejana Ukur Standar 20L")

        df_bejana = st.session_state.get("data_bejana")

        jumlah_alat_standar = st.number_input(
            "Jumlah Alat Standar",
            min_value=1,
            max_value=10,
            value=int(
                st.session_state.saved_data.get(
                    "jumlah_alat_standar",
                    1
                )
            ),
            step=1,
            key="jumlah_alat_standar_pubbm"
        )

        st.session_state.saved_data[
            "jumlah_alat_standar"
        ] = jumlah_alat_standar

        data_alat_standar = []

        if df_bejana is not None and not df_bejana.empty:

            df_bejana_tampil = df_bejana.copy()

            df_bejana_tampil["Merk"] = (
                df_bejana_tampil["Merk"]
                .fillna("")
                .astype(str)
                .str.strip()
            )

            df_bejana_tampil["Nomor Seri"] = (
                df_bejana_tampil["Nomor Seri"]
                .fillna("")
                .apply(
                    lambda nilai: (
                        str(int(nilai))
                        if isinstance(nilai, float)
                        and nilai.is_integer()
                        else str(nilai).strip()
                    )
                )
            )

            pilihan_bejana = (
                df_bejana_tampil["Merk"]
                + " | No Seri : "
                + df_bejana_tampil["Nomor Seri"]
            )
        
            jumlah_kolom = 2
        
            for awal in range(
                1,
                jumlah_alat_standar + 1,
                jumlah_kolom
            ):
        
                kolom_standar = st.columns(jumlah_kolom)
        
                for posisi_kolom in range(jumlah_kolom):
                    i = awal + posisi_kolom
        
                    if i > jumlah_alat_standar:
                        break
        
                    with kolom_standar[posisi_kolom]:
        
                        st.markdown(
                            f"**⚖️ Alat Standar {i}**"
                        )
        
                        selected_bejana = st.selectbox(
                            f"Pilih Bejana Ukur Standar {i}",
                            options=[""] + pilihan_bejana.tolist(),
                            index=0,
                            key=f"bejana_select_{i}",
                            label_visibility="collapsed"
                        )
        
                        if selected_bejana:
                            idx = pilihan_bejana[
                                pilihan_bejana == selected_bejana
                            ].index[0]
        
                            row_bejana = df_bejana_tampil.loc[idx]
        
                            merk_bus_item = str(
                                row_bejana.get("Merk", "")
                            )
        
                            nomor_seri_bus_item = str(
                                row_bejana.get("Nomor Seri", "")
                            )
        
                            telusuran_bus_item = str(
                                row_bejana.get("Telusuran", "")
                            )
        
                            data_alat_standar.append(
                                {
                                    "No": i,
                                    "Merk": merk_bus_item,
                                    "Nomor Seri": nomor_seri_bus_item,
                                    "Telusuran": telusuran_bus_item
                                }
                            )

        alat_standar_df = pd.DataFrame(
            data_alat_standar,
            columns=[
                "No",
                "Merk",
                "Nomor Seri",
                "Telusuran"
            ]
        )

        # Tetap siapkan variabel lama agar generator lama tidak error
        if not alat_standar_df.empty:
            alat_pertama = alat_standar_df.iloc[0]

            merk_bus = str(alat_pertama.get("Merk", ""))
            nomor_seri_bus = str(
                alat_pertama.get("Nomor Seri", "")
            )
            telusuran_bus = str(
                alat_pertama.get("Telusuran", "")
            )

        else:
            merk_bus = ""
            nomor_seri_bus = ""
            telusuran_bus = ""

        st.markdown("---")
    
        # =========================
        # DATA POMPA UKUR BBM
        # =========================
        st.subheader("Data Pompa Ukur BBM")

        df_media = st.session_state.get("data_media_spbu")
        media_options = get_media_options(pemilik, df_media)

        if media_options:
            st.success(
                "Pilihan media tersedia: "
                + ", ".join(media_options)
            )
        else:
            st.warning(
                "Pilihan media belum tersedia. "
                "Periksa nama SPBU atau data_media_spbu.xlsx."
            )

            media_options = [
                "Pertalite",
                "Pertamax",
                "Bio Solar"
            ]

        # =========================
        # STYLE TAMPILAN
        # =========================
        st.markdown(
            """
            <style>
            .pubbm-title {
                font-size: 18px;
                font-weight: 700;
                margin-bottom: 8px;
            }

            .pubbm-help {
                font-size: 13px;
                color: #6b7280;
                margin-bottom: 12px;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        # =========================
        # SESSION STATE DISPENSER
        # =========================
        if "jumlah_dispenser_pubbm" not in st.session_state:
            jumlah_awal = int(
                st.session_state.saved_data.get(
                    "jumlah_dispenser",
                    1
                )
            )

            st.session_state.jumlah_dispenser_pubbm = max(
                1,
                jumlah_awal
            )

        # =========================
        # FUNGSI TAMBAH DISPENSER
        # =========================
        def tambah_dispenser():
            jumlah_sekarang = int(
                st.session_state.get(
                    "jumlah_dispenser_pubbm",
                    1
                )
            )

            if jumlah_sekarang >= 50:
                return

            dispenser_baru = jumlah_sekarang + 1

            # Pastikan dispenser baru kosong
            st.session_state.pop(
                f"merk_{dispenser_baru}",
                None
            )
            st.session_state.pop(
                f"tipe_{dispenser_baru}",
                None
            )
            st.session_state.pop(
                f"no_seri_{dispenser_baru}",
                None
            )

            st.session_state[
                f"jumlah_posisi_{dispenser_baru}"
            ] = 4

            for idx_baru in range(1, 21):
                st.session_state.pop(
                    f"posisi_{dispenser_baru}_{idx_baru}",
                    None
                )
            
                st.session_state.pop(
                    f"media_{dispenser_baru}_{idx_baru}",
                    None
                )
            
                st.session_state.pop(
                    f"media_manual_{dispenser_baru}_{idx_baru}",
                    None
                )
            
                st.session_state.pop(
                    f"media_restore_{dispenser_baru}_{idx_baru}",
                    None
                )
                st.session_state.pop(
                    f"k_faktor_{dispenser_baru}_{idx_baru}",
                    None
                )

            st.session_state.jumlah_dispenser_pubbm = (
                dispenser_baru
            )

        # =========================
        # FUNGSI TAMBAH DAN COPY
        # =========================
        def tambah_copy_dispenser():
            jumlah_lama = int(
                st.session_state.get(
                    "jumlah_dispenser_pubbm",
                    1
                )
            )

            if jumlah_lama >= 50:
                return

            dispenser_asal = jumlah_lama
            dispenser_baru = jumlah_lama + 1

            # Salin identitas dispenser
            st.session_state[
                f"merk_{dispenser_baru}"
            ] = st.session_state.get(
                f"merk_{dispenser_asal}",
                ""
            )

            st.session_state[
                f"tipe_{dispenser_baru}"
            ] = st.session_state.get(
                f"tipe_{dispenser_asal}",
                ""
            )

            st.session_state[
                f"no_seri_{dispenser_baru}"
            ] = st.session_state.get(
                f"no_seri_{dispenser_asal}",
                ""
            )

            jumlah_posisi_asal = int(
                st.session_state.get(
                    f"jumlah_posisi_{dispenser_asal}",
                    4
                )
            )

            st.session_state[
                f"jumlah_posisi_{dispenser_baru}"
            ] = jumlah_posisi_asal

            # Salin posisi dan media
            for idx_copy in range(
                1,
                jumlah_posisi_asal + 1
            ):
                st.session_state[
                    f"posisi_{dispenser_baru}_{idx_copy}"
                ] = st.session_state.get(
                    f"posisi_{dispenser_asal}_{idx_copy}",
                    ""
                )

                key_media_asal = (
                    f"media_{dispenser_asal}_{idx_copy}"
                )
                
                key_manual_asal = (
                    f"media_manual_{dispenser_asal}_{idx_copy}"
                )
                
                key_media_baru = (
                    f"media_{dispenser_baru}_{idx_copy}"
                )
                
                key_manual_baru = (
                    f"media_manual_{dispenser_baru}_{idx_copy}"
                )
                key_k_faktor_asal = (
                    f"k_faktor_{dispenser_asal}_{idx_copy}"
                )
                
                key_k_faktor_baru = (
                    f"k_faktor_{dispenser_baru}_{idx_copy}"
                )
                pilihan_media_asal = st.session_state.get(
                    key_media_asal,
                    ""
                )
                
                media_manual_asal = st.session_state.get(
                    key_manual_asal,
                    ""
                )
                
                # Salin pilihan media
                st.session_state[
                    key_media_baru
                ] = pilihan_media_asal
                
                # Salin isi manual apabila menggunakan media manual
                if pilihan_media_asal == OPSI_MEDIA_MANUAL:
                    st.session_state[
                        key_manual_baru
                    ] = media_manual_asal
                else:
                    st.session_state[
                        key_manual_baru
                    ] = ""
                # =============================================
                # SALIN K-FAKTOR
                # =============================================
                st.session_state[
                    key_k_faktor_baru
                ] = st.session_state.get(
                    key_k_faktor_asal,
                    ""
                )
            st.session_state.jumlah_dispenser_pubbm = (
                dispenser_baru
            )

        # =========================
        # FUNGSI HAPUS DISPENSER
        # =========================
        def hapus_dispenser_terakhir():
            jumlah_sekarang = int(
                st.session_state.get(
                    "jumlah_dispenser_pubbm",
                    1
                )
            )

            if jumlah_sekarang <= 1:
                return

            dispenser_hapus = jumlah_sekarang

            jumlah_posisi_hapus = int(
                st.session_state.get(
                    f"jumlah_posisi_{dispenser_hapus}",
                    4
                )
            )

            # Hapus identitas dispenser
            for key_hapus in [
                f"merk_{dispenser_hapus}",
                f"tipe_{dispenser_hapus}",
                f"no_seri_{dispenser_hapus}",
                f"jumlah_posisi_{dispenser_hapus}",
            ]:
                st.session_state.pop(
                    key_hapus,
                    None
                )

            # Hapus posisi dan media
            for idx_hapus in range(
                1,
                jumlah_posisi_hapus + 1
            ):
                st.session_state.pop(
                    f"posisi_{dispenser_hapus}_{idx_hapus}",
                    None
                )
            
                st.session_state.pop(
                    f"media_{dispenser_hapus}_{idx_hapus}",
                    None
                )
            
                st.session_state.pop(
                    f"media_manual_{dispenser_hapus}_{idx_hapus}",
                    None
                )
            
                st.session_state.pop(
                    f"media_restore_{dispenser_hapus}_{idx_hapus}",
                    None
                )
                st.session_state.pop(
                    f"k_faktor_{dispenser_hapus}_{idx_hapus}",
                    None
                )
            st.session_state.jumlah_dispenser_pubbm = (
                jumlah_sekarang - 1
            )

        # Ambil jumlah dispenser terbaru
        jumlah_dispenser = int(
            st.session_state.get(
                "jumlah_dispenser_pubbm",
                1
            )
        )

        st.session_state.saved_data[
            "jumlah_dispenser"
        ] = jumlah_dispenser

        # =========================
        # DATA DISPENSER
        # =========================
        data_rows = []

        for i in range(1, jumlah_dispenser + 1):

            with st.expander(
                f"⛽ Dispenser / Pompa Nomor {i}",
                expanded=(i == jumlah_dispenser)
            ):

                st.markdown(
                    f"""
                    <div class="pubbm-title">
                        Dispenser {i}
                    </div>

                    <div class="pubbm-help">
                        Isi spesifikasi dispenser, kemudian pilih
                        media untuk setiap posisi/nozzle.
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                # =========================
                # IDENTITAS DISPENSER
                # =========================
                col_merk, col_tipe, col_seri = st.columns(3)

                with col_merk:
                    merk = st.text_input(
                        "Merk",
                        key=f"merk_{i}"
                    )

                with col_tipe:
                    tipe = st.text_input(
                        "Tipe",
                        key=f"tipe_{i}"
                    )

                with col_seri:
                    no_seri = st.text_input(
                        "No. Seri",
                        key=f"no_seri_{i}"
                    )

                st.markdown(
                    "**Posisi / Nozzle dan Media**"
                )

                # =========================
                # JUMLAH POSISI
                # =========================
                key_jumlah_posisi = (
                    f"jumlah_posisi_{i}"
                )

                if key_jumlah_posisi not in st.session_state:
                    st.session_state[
                        key_jumlah_posisi
                    ] = 4

                jumlah_posisi = int(
                    st.number_input(
                        "Jumlah Posisi / Nozzle",
                        min_value=1,
                        max_value=20,
                        step=1,
                        key=key_jumlah_posisi
                    )
                )

                # =========================
                # =========================
                # POSISI DAN MEDIA
                # =========================
                for idx in range(
                    1,
                    jumlah_posisi + 1
                ):
                    col_posisi, col_media, col_kfaktor = st.columns(
                        [1, 2, 1]
                    )
                
                    key_posisi = f"posisi_{i}_{idx}"
                    key_media_pilihan = f"media_{i}_{idx}"
                    key_media_manual = f"media_manual_{i}_{idx}"
                    key_media_restore = f"media_restore_{i}_{idx}"
                    key_k_faktor = (
                        f"k_faktor_{i}_{idx}"
                    )
                
                    # =================================================
                    # PULIHKAN MEDIA SAAT USER KEMBALI DARI PREVIEW
                    # =================================================
                    if key_media_restore in st.session_state:
                        media_tersimpan = str(
                            st.session_state.pop(
                                key_media_restore,
                                ""
                            )
                        ).strip()
                
                        if media_tersimpan in media_options:
                            st.session_state[
                                key_media_pilihan
                            ] = media_tersimpan
                
                            st.session_state[
                                key_media_manual
                            ] = ""
                
                        elif media_tersimpan:
                            st.session_state[
                                key_media_pilihan
                            ] = OPSI_MEDIA_MANUAL
                
                            st.session_state[
                                key_media_manual
                            ] = media_tersimpan
                
                    with col_posisi:
                        posisi = st.text_input(
                            f"Posisi {idx}",
                            placeholder=(
                                "Contoh: 1, 1.1, 1.2, 3.4"
                            ),
                            key=key_posisi
                        )
                
                    with col_media:
                        pilihan_media = st.selectbox(
                            f"Media {idx}",
                            options=(
                                [""]
                                + media_options
                                + [OPSI_MEDIA_MANUAL]
                            ),
                            key=key_media_pilihan
                        )
                
                        if pilihan_media == OPSI_MEDIA_MANUAL:
                            media_manual = st.text_input(
                                f"Nama Media Manual {idx}",
                                placeholder=(
                                    "Contoh: Dexlite, BBM Khusus, "
                                    "Produk lainnya"
                                ),
                                key=key_media_manual
                            )
                
                            media = media_manual.strip()
                
                            if media:
                                st.caption(
                                    f"Media sertifikat: **{media}**"
                                )
                
                        else:
                            media = str(
                                pilihan_media
                            ).strip()
                
                    with col_kfaktor:
                        k_faktor = st.text_input(
                            f"K-Faktor {idx}",
                            key=key_k_faktor,
                            placeholder="Opsional",
                        ) 
                    if media:
                        data_rows.append(
                            {
                                "No": i,
                                "Posisi": posisi.strip(),
                                "Merk": merk.strip(),
                                "Tipe": tipe.strip(),
                                "No. Seri": no_seri.strip(),
                                "Media": media,
                                "K-Faktor": k_faktor.strip(),
                            }
                        )

                # =========================
                # TOMBOL DI DISPENSER TERAKHIR
                # =========================
                if i == jumlah_dispenser:
                    st.markdown("---")
                    st.markdown(
                        "**Kelola Dispenser**"
                    )

                    col_tambah, col_copy, col_hapus = (
                        st.columns(3)
                    )

                    with col_tambah:
                        st.button(
                            "➕ Tambah Dispenser",
                            use_container_width=True,
                            key=(
                                f"tambah_dispenser_"
                                f"setelah_{i}"
                            ),
                            on_click=tambah_dispenser,
                            disabled=(
                                jumlah_dispenser >= 50
                            )
                        )

                    with col_copy:
                        st.button(
                            "📋 Tambah & Copy",
                            use_container_width=True,
                            key=(
                                f"copy_dispenser_"
                                f"setelah_{i}"
                            ),
                            on_click=tambah_copy_dispenser,
                            disabled=(
                                jumlah_dispenser >= 50
                            )
                        )

                    with col_hapus:
                        st.button(
                            "🗑️ Hapus Dispenser",
                            use_container_width=True,
                            key=f"hapus_dispenser_{i}",
                            on_click=(
                                hapus_dispenser_terakhir
                            ),
                            disabled=(
                                jumlah_dispenser <= 1
                            )
                        )

        # =========================
        # DATAFRAME DISPENSER
        # =========================
        kolom_dispenser = [
            "No",
            "Posisi",
            "Merk",
            "Tipe",
            "No. Seri",
            "Media",
            "K-Faktor",
        ]

        dispenser_df = pd.DataFrame(
            data_rows,
            columns=kolom_dispenser
        )

        if not dispenser_df.empty:
            dispenser_df = dispenser_df[
                dispenser_df["Media"]
                .astype(str)
                .str.strip()
                .ne("")
            ]

        st.session_state.pubbm_dispenser = (
            dispenser_df
        )

        st.markdown("---")

    
            # =========================
        # SIMPAN DATA KE SESSION STATE
        # =========================
        data_pubbm = {
            "nomor_sertifikat": nomor_sertifikat,
            "nomor_order": nomor_order,
            "tanggal_pengujian": tanggal_pengujian,
            "tanggal_cetak": tanggal_tanda_tangan,
    
            "nama_alat": "Pompa Ukur BBM (Dispenser)",
    
            "pemilik": pemilik,
            "nama_spbu": nomor_spbu,
            "alamat": alamat,
    
            "jenis_pengujian": jenis_pengujian,
    
            "penera_1": penera_1,
            "nip_penera_1": nip_penera_1,
            "golongan_penera_1": golongan_penera_1,
    
            "penera_2": penera_2,
            "nip_penera_2": nip_penera_2,
            "golongan_penera_2": golongan_penera_2,
    
            "jumlah_penera": jumlah_penera,

            "jumlah_alat_standar": jumlah_alat_standar,
            "alat_standar": alat_standar_df,

            # Tetap disimpan untuk kompatibilitas generator lama
            "merk_bus": merk_bus,
            "nomor_seri_bus": nomor_seri_bus,
            "telusuran_bus": telusuran_bus,

            "jumlah_dispenser": jumlah_dispenser,
            "dispenser": dispenser_df,
                    }
    
        col_simpan, col_reset = st.columns(2)

        with col_simpan:
            simpan_pubbm = st.button(
                "💾 Simpan Data",
                type="primary",
                use_container_width=True,
                key="simpan_data_pubbm",
            )

        with col_reset:
            st.button(
                "🔄 Reset Form",
                use_container_width=True,
                key="reset_form_pubbm",
                on_click=reset_form_pubbm,
            )

        if simpan_pubbm:
            daftar_error = validasi_data_pubbm(
                pemilik=pemilik,
                alamat=alamat,
                penera_1=penera_1,
                jumlah_penera=jumlah_penera,
                penera_2=penera_2,
                alat_standar_df=alat_standar_df,
                dispenser_df=dispenser_df,
                jumlah_dispenser=jumlah_dispenser,
            )

            if daftar_error:
                st.error(
                    "Data belum dapat disimpan. "
                    "Periksa bagian berikut:"
                )

                for pesan in daftar_error:
                    st.write(
                        f"- {pesan}"
                    )

                st.stop()

            st.session_state.data_pubbm = (
                data_pubbm
            )

            # =====================================================
            # SIMPAN SNAPSHOT LENGKAP DATA PUBBM
            # =====================================================
            st.session_state[
                "saved_data"
            ] = dict(
                data_pubbm
            )
            
            # DataFrame dibuat copy agar tidak ikut berubah
            # karena perubahan widget pada rerun berikutnya
            st.session_state[
                "saved_data"
            ][
                "alat_standar"
            ] = alat_standar_df.copy()
            
            st.session_state[
                "saved_data"
            ][
                "dispenser"
            ] = dispenser_df.copy()
            
            st.session_state[
                "pubbm_dispenser"
            ] = dispenser_df.copy()

            st.balloons()

            st.success(
                "Data PU BBM berhasil disimpan. "
                "Silakan buka menu Preview & Generate Data."
            )
    
    # =========================
    # MODE PREVIEW
    # =========================
    elif mode == "📄 Preview & Generate Data":

        st.header("Preview Data PU BBM")

        st.button(
            "✏️ Kembali dan Edit Data",
            use_container_width=True,
            key="pubbm_kembali_edit",
            on_click=kembali_ke_input_pubbm,
        )
    
        data_pubbm = st.session_state.get("data_pubbm")
    
        if not data_pubbm:
            st.warning("Belum ada data. Silakan isi data terlebih dahulu di menu Input Data Pengujian.")
            st.stop()
        # =====================================================
        # DATA FORMULIR PEMINJAMAN ALAT STANDAR PUBBM
        # =====================================================
        data_form_peminjaman_pubbm = dict(data_pubbm)

        data_form_peminjaman_pubbm.update(
            {
                # Generator formulir membaca key ini
                "nama_penera": data_pubbm.get(
                    "penera_1",
                    ""
                ),
                "nip_penera": data_pubbm.get(
                    "nip_penera_1",
                    ""
                ),
                "keterangan": data_pubbm.get(
                    "jenis_pengujian",
                    "Tera Ulang"
                ),
                "tanggal": data_pubbm.get(
                    "tanggal_pengujian",
                    ""
                ),
                "nama_perusahaan": data_pubbm.get(
                    "pemilik",
                    ""
                ),
            }
        )
        # =====================================================
        # DAFTAR BEJANA UKUR STANDAR UNTUK ISI TABEL FORMULIR
        # =====================================================
        daftar_alat_form_pubbm = []

        alat_standar_df = data_pubbm.get(
            "alat_standar"
        )

        if (
            isinstance(alat_standar_df, pd.DataFrame)
            and not alat_standar_df.empty
        ):
            for _, row_alat in alat_standar_df.iterrows():
                merk_alat = str(
                    row_alat.get(
                        "Merk",
                        ""
                    )
                ).strip()

                nomor_seri_alat = str(
                    row_alat.get(
                        "Nomor Seri",
                        ""
                    )
                ).strip()

                # Hindari nilai nan dari pandas
                if merk_alat.lower() == "nan":
                    merk_alat = ""

                if nomor_seri_alat.lower() == "nan":
                    nomor_seri_alat = ""

                jenis_alat = "Bejana 20 L"

                nomor_seri_form = " ".join(
                    bagian
                    for bagian in [
                        merk_alat,
                        nomor_seri_alat,
                    ]
                    if bagian
                )

                daftar_alat_form_pubbm.append(
                    {
                        "jenis_alat": jenis_alat,
                        "nomor_seri": nomor_seri_form,
                        "jumlah": "1 Unit",
                        "lama_peminjaman": "1 Hari",
                    }
                )
        # =====================================================
        # FALLBACK DATA LAMA YANG HANYA MENYIMPAN SATU BEJANA
        # =====================================================
        if not daftar_alat_form_pubbm:
            merk_bus_lama = str(
                data_pubbm.get(
                    "merk_bus",
                    ""
                )
            ).strip()

            nomor_seri_bus_lama = str(
                data_pubbm.get(
                    "nomor_seri_bus",
                    ""
                )
            ).strip()

            if merk_bus_lama.lower() == "nan":
                merk_bus_lama = ""

            if nomor_seri_bus_lama.lower() == "nan":
                nomor_seri_bus_lama = ""

            if merk_bus_lama or nomor_seri_bus_lama:
                jenis_alat_lama = (
                    "Bejana 20 L"
                )

                if merk_bus_lama:
                    jenis_alat_lama += (
                        f" - {merk_bus_lama}"
                    )

                daftar_alat_form_pubbm.append(
                    {
                        "jenis_alat": jenis_alat_lama,
                        "nomor_seri": nomor_seri_bus_lama,
                        "jumlah": "1 Unit",
                        "lama_peminjaman": "1 Hari",
                    }
                )
        st.subheader("Identitas Sertifikat")
    
        col1, col2, col3 = st.columns(3)
    
        with col1:
            st.write("**Nomor Sertifikat:**")
            st.write(data_pubbm.get("nomor_sertifikat", ""))
    
            st.write("**Nomor Order:**")
            st.write(data_pubbm.get("nomor_order", ""))
    
        with col2:
            st.write("**Tanggal Pengujian:**")
            st.write(
                data_pubbm.get(
                    "tanggal_pengujian",
                    ""
                )
            )

            st.write("**Tanggal Tanda Tangan:**")
            st.write(
                data_pubbm.get(
                    "tanggal_cetak",
                    ""
                )
            )

            st.write("**Jenis Pengujian:**")
            st.write(
                data_pubbm.get(
                    "jenis_pengujian",
                    ""
                )
            )
    
        with col3:
            st.write("**Nama Alat:**")
            st.write(data_pubbm.get("nama_alat", ""))
    
        st.markdown("---")
    
        st.subheader("Identitas Pemilik / SPBU")
    
        st.write("**Pemilik:**")
        st.write(data_pubbm.get("pemilik", ""))
    
        st.write("**Alamat:**")
        st.write(data_pubbm.get("alamat", ""))
    
        st.markdown("---")
    
        st.subheader("Penera / Pegawai Berhak")
    
        st.write("**Penera 1:**")
        st.write(
            f"{data_pubbm.get('penera_1', '')} / "
            f"NIP. {data_pubbm.get('nip_penera_1', '')} / "
            f"{data_pubbm.get('golongan_penera_1', '')}"
        )
    
        if data_pubbm.get("jumlah_penera") == 2:
            st.write("**Penera 2:**")
            st.write(
                f"{data_pubbm.get('penera_2', '')} / "
                f"NIP. {data_pubbm.get('nip_penera_2', '')} / "
                f"{data_pubbm.get('golongan_penera_2', '')}"
            )
    
        st.markdown("---")
    
        st.subheader("Perangkat Bejana Ukur Standar")

        alat_standar_df = data_pubbm.get("alat_standar")

        if (
            isinstance(alat_standar_df, pd.DataFrame)
            and not alat_standar_df.empty
        ):
            st.dataframe(
                alat_standar_df,
                use_container_width=True,
                hide_index=True,
            )
        else:
            col4, col5, col6 = st.columns(3)

            with col4:
                st.write("**Merk / Buatan:**")
                st.write(data_pubbm.get("merk_bus", ""))

            with col5:
                st.write("**Nomor Seri:**")
                st.write(data_pubbm.get("nomor_seri_bus", ""))

            with col6:
                st.write("**Telusuran:**")
                st.write(data_pubbm.get("telusuran_bus", ""))
    
        st.markdown("---")
    
        st.subheader("Data Pompa Ukur BBM")
    
        dispenser_df = data_pubbm.get(
            "dispenser"
        )
        
        if (
            dispenser_df is None
            or dispenser_df.empty
        ):
            st.warning(
                "Data pompa ukur BBM belum diisi."
            )
        
        else:
            # K-Faktor tetap disimpan dalam data,
            # tetapi tidak ditampilkan di Preview
            dispenser_preview_df = (
                dispenser_df.drop(
                    columns=[
                        "K-Faktor"
                    ],
                    errors="ignore"
                )
                .copy()
            )
        
            st.dataframe(
                dispenser_preview_df,
                use_container_width=True,
                hide_index=True
            )
    
        st.markdown("---")
    
        # =====================================================
        # GENERATE DAN DOWNLOAD DOKUMEN
        # =====================================================
        st.markdown("---")
        st.subheader("📄 Generate Dokumen")

        if "pubbm_generated_files" not in st.session_state:
            st.session_state.pubbm_generated_files = {}

        col_sertifikat, col_form_standar, col_form_ctt = st.columns(3)


        # =====================================================
        # SERTIFIKAT PU BBM
        # =====================================================
        with col_sertifikat:
            with st.container(border=True):
                st.markdown("### 🎫 Sertifikat PU BBM")

                st.caption(
                    "Generate dan download Sertifikat "
                    "Pengujian PU BBM."
                )

                if st.button(
                    "📄 Generate Sertifikat",
                    type="primary",
                    use_container_width=True,
                    key="pubbm_generate_sertifikat",
                ):
                    try:
                        # =================================================
                        # 1. SIAPKAN FOLDER OUTPUT
                        # =================================================
                        output_dir_sertifikat = Path(
                            "output/pubbm/sertifikat"
                        )
                
                        output_dir_sertifikat.mkdir(
                            parents=True,
                            exist_ok=True,
                        )
                
                        # =================================================
                        # 2. NAMA FILE
                        # =================================================
                        nama_file = format_nama_file_pubbm(
                            data_pubbm
                        )
                
                        output_file = (
                            output_dir_sertifikat
                            / f"{nama_file}.pdf"
                        )
                
                        # =================================================
                        # 3. GENERATE PDF
                        # =================================================
                        # =================================================
                        # DATA KHUSUS UNTUK SERTIFIKAT
                        # K-Faktor tidak dicetak ke sertifikat
                        # =================================================
                        data_sertifikat_pubbm = dict(
                            data_pubbm
                        )
                        
                        dispenser_sertifikat = (
                            data_pubbm.get(
                                "dispenser"
                            )
                        )
                        
                        if (
                            isinstance(
                                dispenser_sertifikat,
                                pd.DataFrame
                            )
                        ):
                            data_sertifikat_pubbm[
                                "dispenser"
                            ] = (
                                dispenser_sertifikat.drop(
                                    columns=[
                                        "K-Faktor"
                                    ],
                                    errors="ignore"
                                )
                                .copy()
                            )
                        
                        
                        generate_sertifikat_pubbm(
                            data_sertifikat_pubbm,
                            str(output_file),
                        )
                
                        # =================================================
                        # 4. SIMPAN KE SUPABASE
                        # =================================================
                        sedang_edit = bool(
                            st.session_state.get(
                                "pubbm_edit_pengujian_id"
                            )
                        )
                        hasil_simpan = (
                            simpan_pengujian_pubbm_ke_supabase(
                                data_pubbm
                            )
                        )
                
                        # =================================================
                        # 5. SIMPAN FILE KE SESSION STATE
                        # Hanya dilakukan jika Supabase berhasil
                        # =================================================
                        st.session_state.pubbm_generated_files[
                            "sertifikat"
                        ] = str(
                            output_file
                        )
                
                        if sedang_edit:
                            st.success(
                                "✅ Sertifikat berhasil dibuat dan "
                                "data pengujian lama berhasil diperbarui."
                            )
                        else:
                            st.success(
                                "✅ Sertifikat berhasil dibuat dan "
                                "pengujian baru berhasil disimpan."
                            )
                
                    except Exception as exc:
                        pesan_error = str(exc)
                
                        # =================================================
                        # NOMOR SERTIFIKAT DUPLIKAT
                        # =================================================
                        if (
                            "pengujian_nomor_sertifikat_unique"
                            in pesan_error
                            or "duplicate key"
                            in pesan_error.lower()
                            or "23505" in pesan_error
                        ):
                            st.error(
                                "❌ Nomor sertifikat sudah pernah "
                                "digunakan.\n\n"
                                "Silakan gunakan nomor sertifikat "
                                "yang berbeda."
                            )
                
                        else:
                            st.error(
                                "Gagal membuat atau menyimpan "
                                f"sertifikat: {exc}"
                            )
                
                            import traceback
                
                            st.code(
                                traceback.format_exc()
                            )
                sertifikat_path = (
                    st.session_state.pubbm_generated_files.get(
                        "sertifikat"
                    )
                )

                if (
                    sertifikat_path
                    and Path(sertifikat_path).exists()
                ):
                    with open(
                        sertifikat_path,
                        "rb",
                    ) as file_sertifikat:
                        st.download_button(
                            label="⬇️ Download Sertifikat",
                            data=file_sertifikat.read(),
                            file_name=Path(
                                sertifikat_path
                            ).name,
                            mime="application/pdf",
                            use_container_width=True,
                            key="pubbm_download_sertifikat",
                        )
                else:
                    st.caption(
                        "Sertifikat belum digenerate."
                    )


        # =====================================================
        # FORM PEMINJAMAN ALAT STANDAR
        # =====================================================
        with col_form_standar:
            with st.container(border=True):
                st.markdown(
                    "### ⚖️ Peminjaman Alat Standar"
                )

                st.caption(
                    "Generate dan download formulir "
                    "peminjaman Bejana Ukur Standar."
                )

                if st.button(
                    "⚖️ Generate Form Standar",
                    type="primary",
                    use_container_width=True,
                    key="pubbm_generate_form_peminjaman_standar",
                ):
                    try:
                        if not daftar_alat_form_pubbm:
                            st.error(
                                "Belum ada Bejana Ukur Standar "
                                "yang dipilih."
                            )

                        else:
                            output_dir_form = Path(
                                "output/pubbm/form_peminjaman"
                            )

                            output_dir_form.mkdir(
                                parents=True,
                                exist_ok=True,
                            )

                            nama_file_dasar = (
                                format_nama_file_pubbm(
                                    data_pubbm
                                )
                            )

                            output_form_peminjaman = (
                                output_dir_form
                                / (
                                    "FORM_PEMINJAMAN_ALAT_STANDAR_"
                                    f"{nama_file_dasar}.pdf"
                                )
                            )

                            generate_form_peminjaman_standar_pdf(
                                data=data_form_peminjaman_pubbm,
                                filename=str(
                                    output_form_peminjaman
                                ),
                                nomor_surat_perintah="",
                                daftar_alat=daftar_alat_form_pubbm,
                            )

                            st.session_state.pubbm_generated_files[
                                "form_peminjaman_standar"
                            ] = str(
                                output_form_peminjaman
                            )

                            st.success(
                                "✅ Form alat standar berhasil dibuat."
                            )

                    except Exception as exc:
                        st.error(
                            "Gagal membuat form alat standar: "
                            f"{exc}"
                        )

                        import traceback
                        st.code(traceback.format_exc())

                form_standar_path = (
                    st.session_state.pubbm_generated_files.get(
                        "form_peminjaman_standar"
                    )
                )

                if (
                    form_standar_path
                    and Path(form_standar_path).exists()
                ):
                    with open(
                        form_standar_path,
                        "rb",
                    ) as file_form_standar:
                        st.download_button(
                            label="⬇️ Download Form Standar",
                            data=file_form_standar.read(),
                            file_name=Path(
                                form_standar_path
                            ).name,
                            mime="application/pdf",
                            use_container_width=True,
                            key="pubbm_download_form_standar",
                        )
                else:
                    st.caption(
                        "Form alat standar belum digenerate."
                    )


        # =====================================================
        # FORM PEMINJAMAN CTT
        # =====================================================
        with col_form_ctt:
            with st.container(border=True):
                st.markdown(
                    "### 🔏 Peminjaman CTT"
                )

                st.caption(
                    "Generate dan download formulir "
                    "peminjaman Cap Tanda Tera."
                )

                if st.button(
                    "🔏 Generate Form CTT",
                    type="primary",
                    use_container_width=True,
                    key="pubbm_generate_form_ctt",
                ):
                    try:
                        output_dir_ctt = Path(
                            "output/pubbm/form_peminjaman"
                        )

                        output_dir_ctt.mkdir(
                            parents=True,
                            exist_ok=True,
                        )

                        nama_file_dasar = (
                            format_nama_file_pubbm(
                                data_pubbm
                            )
                        )

                        output_form_ctt = (
                            output_dir_ctt
                            / (
                                "FORM_PEMINJAMAN_CTT_"
                                f"{nama_file_dasar}.pdf"
                            )
                        )

                        generate_form_peminjaman_ctt_pdf(
                            data=data_form_peminjaman_pubbm,
                            filename=str(
                                output_form_ctt
                            ),
                            nomor_surat_perintah="",
                        )

                        st.session_state.pubbm_generated_files[
                            "form_peminjaman_ctt"
                        ] = str(output_form_ctt)

                        st.success(
                            "✅ Form peminjaman CTT "
                            "berhasil dibuat."
                        )

                    except Exception as exc:
                        st.error(
                            f"Gagal membuat form CTT: {exc}"
                        )

                        import traceback
                        st.code(traceback.format_exc())

                form_ctt_path = (
                    st.session_state.pubbm_generated_files.get(
                        "form_peminjaman_ctt"
                    )
                )

                if (
                    form_ctt_path
                    and Path(form_ctt_path).exists()
                ):
                    with open(
                        form_ctt_path,
                        "rb",
                    ) as file_form_ctt:
                        st.download_button(
                            label="⬇️ Download Form CTT",
                            data=file_form_ctt.read(),
                            file_name=Path(
                                form_ctt_path
                            ).name,
                            mime="application/pdf",
                            use_container_width=True,
                            key="pubbm_download_form_ctt",
                        )
                else:
                    st.caption(
                        "Form CTT belum digenerate."
                    )
    # =========================================================
    # MODE RIWAYAT PUBBM
    # =========================================================
    elif mode == "📚 Riwayat PU BBM":
    
        st.header("📚 Riwayat Pengujian PU BBM")
    
        try:
            supabase = get_supabase_pubbm()
    
            # =====================================================
            # 1. AMBIL MASTER UTTP PUBBM
            # =====================================================
            response_uttp = (
                supabase
                .table("uttp")
                .select("*")
                .eq(
                    "jenis_uttp",
                    "Pompa Ukur BBM"
                )
                .order(
                    "id",
                    desc=True
                )
                .execute()
            )
    
            daftar_uttp = (
                response_uttp.data
                or []
            )
    
            if not daftar_uttp:
                st.info(
                    "Belum ada data PU BBM "
                    "yang tersimpan di Supabase."
                )
                st.stop()
    
            # =====================================================
            # 2. AMBIL DATA PERUSAHAAN
            # =====================================================
            perusahaan_ids = list({
                row.get("perusahaan_id")
                for row in daftar_uttp
                if row.get("perusahaan_id") is not None
            })
    
            daftar_perusahaan = []
    
            if perusahaan_ids:
                response_perusahaan = (
                    supabase
                    .table("perusahaan")
                    .select(
                        "id, nama_perusahaan, alamat"
                    )
                    .in_(
                        "id",
                        perusahaan_ids
                    )
                    .execute()
                )
    
                daftar_perusahaan = (
                    response_perusahaan.data
                    or []
                )
    
            perusahaan_map = {
                row["id"]: row
                for row in daftar_perusahaan
            }
    
            # =====================================================
            # 3. SUSUN PILIHAN SPBU
            # Hindari SPBU yang sama muncul lebih dari sekali
            # =====================================================
            grup_spbu = {}
            
            for alat in daftar_uttp:
            
                perusahaan = perusahaan_map.get(
                    alat.get("perusahaan_id"),
                    {}
                )
            
                perusahaan_id = alat.get(
                    "perusahaan_id"
                )
            
                nama_perusahaan = str(
                    perusahaan.get(
                        "nama_perusahaan",
                        ""
                    )
                    or ""
                ).strip()
            
                identitas_spbu = str(
                    alat.get(
                        "nomor_seri",
                        ""
                    )
                    or ""
                ).strip()
            
                # =================================================
                # NORMALISASI IDENTITAS SPBU UNTUK PENGELOMPOKAN
                # =================================================
                sumber_identitas = (
                    identitas_spbu
                    or nama_perusahaan
                )
                
                sumber_identitas = str(
                    sumber_identitas
                    or ""
                ).strip()
                
                # Jika terdapat tulisan SPBU,
                # ambil nomor SPBU-nya saja.
                match_nomor_spbu = re.search(
                    r"SPBU\s*([0-9][0-9.\-\s]*)",
                    sumber_identitas,
                    re.IGNORECASE,
                )
                
                if match_nomor_spbu:
                    identitas_normal = re.sub(
                        r"\D",
                        "",
                        match_nomor_spbu.group(1)
                    )
                
                else:
                    identitas_normal = (
                        normalisasi_identitas_spbu(
                            sumber_identitas
                        )
                    )
                
                    # Samakan:
                    # SPBU3415717
                    # dengan
                    # 3415717
                    if identitas_normal.startswith(
                        "SPBU"
                    ):
                        identitas_normal = (
                            identitas_normal[4:]
                        )
                
                # =================================================
                # JANGAN GABUNGKAN DATA YANG IDENTITAS SPBU-NYA KOSONG
                # =================================================
                if not identitas_normal:
                    identitas_normal = (
                        f"UTTP_{alat.get('id')}"
                    )
                key_spbu = (
                    perusahaan_id,
                    identitas_normal,
                )
            
                # =================================================
                # SPBU BELUM MASUK DAFTAR
                # =================================================
                if key_spbu not in grup_spbu:
            
                    grup_spbu[key_spbu] = {
                        "uttp": alat,
                        "uttp_ids": [],
                        "perusahaan": perusahaan,
                        "nama_perusahaan": nama_perusahaan,
                        "identitas_spbu": identitas_spbu,
                    }
            
                # Simpan seluruh UTTP ID yang ternyata
                # mengarah ke SPBU yang sama
                uttp_id_item = alat.get(
                    "id"
                )
            
                if (
                    uttp_id_item is not None
                    and uttp_id_item
                    not in grup_spbu[
                        key_spbu
                    ]["uttp_ids"]
                ):
                    grup_spbu[
                        key_spbu
                    ]["uttp_ids"].append(
                        uttp_id_item
                    )
            
            
            # =====================================================
            # SUSUN LABEL DROPDOWN
            # =====================================================
            opsi_spbu = {}
            
            for data_spbu_item in sorted(
                grup_spbu.values(),
                key=lambda item: (
                    item.get(
                        "nama_perusahaan",
                        ""
                    )
                    or ""
                ).lower()
            ):
            
                nama_perusahaan = (
                    data_spbu_item[
                        "nama_perusahaan"
                    ]
                )
            
                identitas_spbu = (
                    data_spbu_item[
                        "identitas_spbu"
                    ]
                )
            
                if (
                    identitas_spbu
                    and identitas_spbu.lower()
                    not in nama_perusahaan.lower()
                ):
                    label = (
                        f"{nama_perusahaan}"
                        f" | {identitas_spbu}"
                    )
                else:
                    label = (
                        nama_perusahaan
                        or identitas_spbu
                    )
            
                opsi_spbu[
                    label
                ] = data_spbu_item
    
            pilihan_spbu = st.selectbox(
                "Pilih SPBU",
                options=[""] + list(
                    opsi_spbu.keys()
                ),
                key="pubbm_riwayat_spbu",
            )
    
            if not pilihan_spbu:
                st.info(
                    "Pilih SPBU untuk melihat "
                    "riwayat tera / tera ulang."
                )
                st.stop()
    
            data_pilihan = opsi_spbu[
                pilihan_spbu
            ]
            
            alat = data_pilihan[
                "uttp"
            ]
            
            perusahaan = data_pilihan[
                "perusahaan"
            ]
            
            # =====================================================
            # SELURUH UTTP ID MILIK SPBU YANG SAMA
            # =====================================================
            uttp_ids = (
                data_pilihan.get(
                    "uttp_ids",
                    []
                )
                or []
            )
            
            # Fallback jika data lama hanya punya satu UTTP
            if not uttp_ids:
                uttp_id_lama = alat.get(
                    "id"
                )
            
                if uttp_id_lama is not None:
                    uttp_ids = [
                        uttp_id_lama
                    ]
          
                # Hanya tampilkan identitas SPBU
                # jika belum tercantum pada nama perusahaan
                if (
                    identitas_spbu_tampil
                    and identitas_spbu_tampil.lower()
                    not in nama_spbu_tampil.lower()
                ):
                    st.write(
                        "**Identitas SPBU:**",
                        identitas_spbu_tampil
                    )
            
                st.write(
                    "**Alamat:**",
                    alamat_spbu_tampil or "-"
                )
    
            # =====================================================
            # 5. AMBIL RIWAYAT PUBBM PER KEGIATAN
            #
            # Struktur database:
            # 1 nozzle = 1 UTTP
            # 1 nozzle = 1 row pengujian
            #
            # Tetapi pada UI Riwayat:
            # 1 sertifikat = 1 kegiatan PUBBM
            # =====================================================
            daftar_pengujian = (
                ambil_riwayat_kegiatan_pubbm(
                    supabase=supabase,
                    perusahaan=perusahaan,
                )
            )
            
            if not daftar_pengujian:
                st.info(
                    "Belum ada riwayat pengujian "
                    "untuk SPBU ini."
                )
                st.stop()
            # =====================================================
            # PILIH OTOMATIS PENGUJIAN ACUAN
            # Prioritas:
            # 1. Jumlah nozzle terbanyak
            # 2. Jika sama, tanggal pengujian terbaru
            # 3. Jika tanggal sama, ID pengujian terbesar
            # =====================================================
            
            def hitung_jumlah_nozzle_pubbm(
                pengujian
            ):
                detail = (
                    pengujian.get(
                        "data_pengujian"
                    )
                    or {}
                )
            
                # =================================================
                # PRIORITAS: HITUNG LANGSUNG DARI DATA DISPENSER
                # 1 baris dispenser = 1 nozzle
                # =================================================
                dispenser_records = (
                    detail.get(
                        "dispenser",
                        []
                    )
                    or []
                )
            
                if isinstance(
                    dispenser_records,
                    list
                ) and dispenser_records:
                    return len(
                        dispenser_records
                    )
            
                # =================================================
                # FALLBACK DATA LAMA
                # =================================================
                try:
                    return int(
                        detail.get(
                            "jumlah_nozzle",
                            0
                        )
                        or 0
                    )
            
                except (
                    TypeError,
                    ValueError
                ):
                    return 0
            
            
            def kunci_pengujian_acuan_pubbm(
                pengujian
            ):
                tanggal = str(
                    pengujian.get(
                        "tanggal_pengujian",
                        ""
                    )
                    or ""
                ).strip()
            
                try:
                    pengujian_id = int(
                        pengujian.get(
                            "id",
                            0
                        )
                        or 0
                    )
                except (TypeError, ValueError):
                    pengujian_id = 0
            
                return (
                    hitung_jumlah_nozzle_pubbm(
                        pengujian
                    ),
                    tanggal,
                    pengujian_id,
                )
            
            
            pengujian_terpilih = max(
                daftar_pengujian,
                key=kunci_pengujian_acuan_pubbm
            )
            
            detail_pengujian_terpilih = (
                pengujian_terpilih.get(
                    "data_pengujian"
                )
                or {}
            )
            
            jumlah_nozzle_terpilih = (
                hitung_jumlah_nozzle_pubbm(
                    pengujian_terpilih
                )
            )
            # =====================================================
            # UTTP YANG BENAR-BENAR MILIK PENGUJIAN ACUAN
            # =====================================================
            uttp_id_pengujian_terpilih = (
                pengujian_terpilih.get(
                    "uttp_id"
                )
            )
            
            alat_pengujian_terpilih = next(
                (
                    item
                    for item in daftar_uttp
                    if item.get("id")
                    == uttp_id_pengujian_terpilih
                ),
                alat
            )
            # =====================================================
            # 6. PENGUJIAN ACUAN
            # =====================================================
            st.markdown("---")
            
            st.subheader(
                "Pengujian Acuan"
            )
            
            with st.container(
                border=True
            ):
                col1, col2 = st.columns(2)
            
                with col1:
                    st.write(
                        "**Tanggal:**",
                        pengujian_terpilih.get(
                            "tanggal_pengujian",
                            ""
                        )
                        or "-"
                    )
            
                    st.write(
                        "**Jenis Pengujian:**",
                        pengujian_terpilih.get(
                            "jenis_pengujian",
                            ""
                        )
                        or "-"
                    )
            
                    st.write(
                        "**Jumlah Nozzle:**",
                        jumlah_nozzle_terpilih
                    )
            
                with col2:
                    st.write(
                        "**Nomor Sertifikat:**",
                        pengujian_terpilih.get(
                            "nomor_sertifikat",
                            ""
                        )
                        or "-"
                    )
            
                    st.write(
                        "**Nomor Order:**",
                        pengujian_terpilih.get(
                            "nomor_order",
                            ""
                        )
                        or "-"
                    )
            
                    st.write(
                        "**Penera:**",
                        pengujian_terpilih.get(
                            "penera_1",
                            ""
                        )
                        or "-"
                    )
            
            
            # =====================================================
            # 7. AKSI PENGUJIAN ACUAN
            # =====================================================
            st.markdown("---")
            
            col_edit, col_baru = (
                st.columns(2)
            )
            
            with col_edit:
                if st.button(
                    "✏️ Edit Pengujian",
                    type="primary",
                    use_container_width=True,
                    key=(
                        "pubbm_edit_riwayat_"
                        f"{pengujian_terpilih.get('id')}"
                    )
                ):
                    gunakan_data_lama_untuk_edit_pubbm(
                        alat=alat_pengujian_terpilih,
                        perusahaan=perusahaan,
                        pengujian=pengujian_terpilih,
                    )
            
                    st.rerun()
            
            
            with col_baru:
                if st.button(
                    "➕ Tambah Pengujian Baru",
                    use_container_width=True,
                    key=(
                        "pubbm_baru_riwayat_"
                        f"{pengujian_terpilih.get('id')}"
                    )
                ):
                    gunakan_data_lama_untuk_pengujian_baru_pubbm(
                        alat=alat_pengujian_terpilih,
                        perusahaan=perusahaan,
                        pengujian=pengujian_terpilih,
                    )
            
                    st.rerun()

        except Exception as exc:
            st.error(
                "Gagal membaca riwayat PUBBM: "
                f"{exc}"
            )
    
            import traceback
    
            st.code(
                traceback.format_exc()
            )
            
