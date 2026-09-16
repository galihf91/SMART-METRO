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
def simpan_atau_update_spbu_pubbm(
    supabase,
    spbu_id=None,
    nama_spbu="",
    nomor_spbu="",
    alamat="",
    jenis_lokasi="",
    kecamatan="",
    media_bbm="",
):
    """
    Simpan / update master SPBU.

    Aturan:
    1. Jika spbu_id sudah diketahui:
       update row SPBU tersebut.

    2. Jika spbu_id belum ada:
       cari berdasarkan nomor_spbu.

    3. Jika nomor_spbu kosong / tidak ditemukan:
       cari berdasarkan nama_spbu.

    4. Jika masih belum ditemukan:
       buat master SPBU baru.
    """

    # =====================================================
    # NORMALISASI INPUT
    # =====================================================
    nama_spbu = str(
        nama_spbu or ""
    ).strip()

    nomor_spbu = str(
        nomor_spbu or ""
    ).strip()

    alamat = str(
        alamat or ""
    ).strip()

    jenis_lokasi = str(
        jenis_lokasi or ""
    ).strip()

    kecamatan = str(
        kecamatan or ""
    ).strip()

    media_bbm = str(
        media_bbm or ""
    ).strip()

    # =====================================================
    # VALIDASI
    # =====================================================
    if not nama_spbu:
        raise ValueError(
            "Nama SPBU belum diisi."
        )

    # =====================================================
    # 1. JIKA ID SPBU SUDAH DIKENAL
    # =====================================================
    if (
        spbu_id is not None
        and str(spbu_id).strip() != ""
    ):
        try:
            spbu_id = int(
                float(spbu_id)
            )

        except (
            TypeError,
            ValueError
        ):
            raise ValueError(
                "ID SPBU tidak valid."
            )

        response_spbu = (
            supabase
            .table("spbu")
            .select(
                "id, "
                "nama_spbu, "
                "nomor_spbu, "
                "alamat, "
                "jenis_lokasi, "
                "kecamatan, "
                "media_bbm"
            )
            .eq(
                "id",
                spbu_id
            )
            .execute()
        )

        if not response_spbu.data:
            raise ValueError(
                "Master SPBU yang dipilih "
                "tidak ditemukan."
            )

        spbu_lama = (
            response_spbu.data[0]
        )

        # =============================================
        # SUSUN DATA UPDATE
        # =============================================
        data_update = {}

        data_baru = {
            "nama_spbu": nama_spbu,

            "nomor_spbu": (
                nomor_spbu
                if nomor_spbu
                else None
            ),

            "alamat": (
                alamat
                if alamat
                else None
            ),

            "jenis_lokasi": (
                jenis_lokasi
                if jenis_lokasi
                else None
            ),

            "kecamatan": (
                kecamatan
                if kecamatan
                else None
            ),

            "media_bbm": (
                media_bbm
                if media_bbm
                else None
            ),

            "status": "aktif",
        }

        for kolom, nilai_baru in (
            data_baru.items()
        ):
            nilai_lama = (
                spbu_lama.get(
                    kolom
                )
            )

            if nilai_lama is None:
                nilai_lama = ""

            if nilai_baru is None:
                nilai_baru_compare = ""

            else:
                nilai_baru_compare = str(
                    nilai_baru
                ).strip()

            nilai_lama_compare = str(
                nilai_lama
            ).strip()

            if (
                nilai_baru_compare
                != nilai_lama_compare
            ):
                data_update[
                    kolom
                ] = nilai_baru

        if data_update:
            (
                supabase
                .table("spbu")
                .update(
                    data_update
                )
                .eq(
                    "id",
                    spbu_id
                )
                .execute()
            )

        return spbu_id

    # =====================================================
    # 2. CARI BERDASARKAN NOMOR SPBU
    # =====================================================
    if nomor_spbu:

        response_nomor = (
            supabase
            .table("spbu")
            .select(
                "id"
            )
            .eq(
                "nomor_spbu",
                nomor_spbu
            )
            .execute()
        )

        if response_nomor.data:

            spbu_id_ditemukan = (
                response_nomor.data[0][
                    "id"
                ]
            )

            return simpan_atau_update_spbu_pubbm(
                supabase=supabase,
                spbu_id=spbu_id_ditemukan,
                nama_spbu=nama_spbu,
                nomor_spbu=nomor_spbu,
                alamat=alamat,
                jenis_lokasi=jenis_lokasi,
                kecamatan=kecamatan,
                media_bbm=media_bbm,
            )

    # =====================================================
    # 3. CARI BERDASARKAN NAMA SPBU
    # =====================================================
    response_nama = (
        supabase
        .table("spbu")
        .select(
            "id"
        )
        .ilike(
            "nama_spbu",
            nama_spbu
        )
        .execute()
    )

    if response_nama.data:

        spbu_id_ditemukan = (
            response_nama.data[0][
                "id"
            ]
        )

        return simpan_atau_update_spbu_pubbm(
            supabase=supabase,
            spbu_id=spbu_id_ditemukan,
            nama_spbu=nama_spbu,
            nomor_spbu=nomor_spbu,
            alamat=alamat,
            jenis_lokasi=jenis_lokasi,
            kecamatan=kecamatan,
            media_bbm=media_bbm,
        )

    # =====================================================
    # 4. SPBU BARU
    # =====================================================
    payload_spbu = {
        "nama_spbu": nama_spbu,

        "nomor_spbu": (
            nomor_spbu
            if nomor_spbu
            else None
        ),

        "alamat": (
            alamat
            if alamat
            else None
        ),

        "jenis_lokasi": (
            jenis_lokasi
            if jenis_lokasi
            else None
        ),

        "kecamatan": (
            kecamatan
            if kecamatan
            else None
        ),

        "media_bbm": (
            media_bbm
            if media_bbm
            else None
        ),

        "status": "aktif",
    }

    response_insert = (
        supabase
        .table("spbu")
        .insert(
            payload_spbu
        )
        .execute()
    )

    if not response_insert.data:
        raise RuntimeError(
            "Master SPBU gagal disimpan."
        )

    return response_insert.data[0][
        "id"
    ]
# =========================================================
# CARI / BUAT UTTP PUBBM PER NOZZLE
# =========================================================
def get_or_create_nozzle_pubbm(
    supabase,
    spbu_id,
    perusahaan_id,
    merk,
    tipe,
    nomor_seri,
):
    """
    Master UTTP PUBBM.

    Ketentuan:
    - 1 nozzle = 1 UTTP
    - nozzle terikat ke lokasi melalui spbu_id
    - perusahaan_id boleh kosong
    - media dan posisi BUKAN identitas master UTTP
    - media dan posisi disimpan pada pengujian_uttp
    - fungsi ini hanya membuat UTTP baru jika nozzle
      belum mempunyai _uttp_id
    """

    # =====================================================
    # NORMALISASI
    # =====================================================
    merk = str(
        merk or ""
    ).strip()

    tipe = str(
        tipe or ""
    ).strip()

    nomor_seri = str(
        nomor_seri or ""
    ).strip()

    # =====================================================
    # VALIDASI SPBU
    # =====================================================
    if (
        spbu_id is None
        or str(spbu_id).strip() == ""
    ):
        raise ValueError(
            "ID master SPBU belum tersedia."
        )

    try:
        spbu_id = int(
            float(spbu_id)
        )
    except (
        TypeError,
        ValueError
    ):
        raise ValueError(
            "ID master SPBU tidak valid."
        )

    # =====================================================
    # VALIDASI MASTER NOZZLE
    # =====================================================
    if not merk:
        raise ValueError(
            "Merk dispenser belum diisi."
        )

    # =====================================================
    # NORMALISASI PERUSAHAAN
    #
    # perusahaan_id sekarang bersifat opsional.
    # =====================================================
    if (
        perusahaan_id is not None
        and str(perusahaan_id).strip() != ""
    ):
        try:
            perusahaan_id = int(
                float(perusahaan_id)
            )
        except (
            TypeError,
            ValueError
        ):
            perusahaan_id = None

    else:
        perusahaan_id = None

    # =====================================================
    # BUAT UTTP BARU
    #
    # Tidak mencari berdasarkan:
    # - media
    # - posisi
    # - tipe
    # - nomor seri
    #
    # Karena identitas UTTP dipertahankan melalui _uttp_id.
    # =====================================================
    payload_uttp = {
        "spbu_id": spbu_id,

        "perusahaan_id": (
            perusahaan_id
        ),

        "jenis_uttp": (
            "Pompa Ukur BBM"
        ),

        "merk": merk,

        "tipe": (
            tipe
            if tipe
            else None
        ),

        "nomor_seri": (
            nomor_seri
            if nomor_seri
            else None
        ),

        "kapasitas": None,

        "lokasi": "SPBU",

        "status": "aktif",
    }

    response = (
        supabase
        .table("uttp")
        .insert(
            payload_uttp
        )
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
    Struktur PUBBM baru:

    1 KEGIATAN / 1 SERTIFIKAT
        = 1 row tabel pengujian

    1 NOZZLE
        = 1 UTTP

    Relasi nozzle dalam kegiatan
        = tabel pengujian_uttp
    """

    if not data:
        raise ValueError(
            "Data PUBBM belum tersedia."
        )

    # =====================================================
    # 1. DATA UMUM KEGIATAN
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

    # =====================================================
    # 2. VALIDASI DATA UMUM
    # =====================================================
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
    # 3. DATA NOZZLE
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
    # 4. VALIDASI SELURUH NOZZLE
    #
    # Dilakukan sebelum database diubah.
    # =====================================================
    for urutan, nozzle in enumerate(
        dispenser_records,
        start=1
    ):
        merk_cek = str(
            nozzle.get(
                "Merk",
                ""
            )
            or ""
        ).strip()

        tipe_cek = str(
            nozzle.get(
                "Tipe",
                ""
            )
            or ""
        ).strip()

        nomor_seri_cek = str(
            nozzle.get(
                "No. Seri",
                ""
            )
            or ""
        ).strip()

        media_cek = str(
            nozzle.get(
                "Media",
                ""
            )
            or ""
        ).strip()

        posisi_cek = str(
            nozzle.get(
                "Posisi",
                ""
            )
            or ""
        ).strip()

        if not merk_cek:
            raise ValueError(
                f"Nozzle baris {urutan}: "
                "Merk belum diisi."
            )

        if not media_cek:
            raise ValueError(
                f"Nozzle baris {urutan}: "
                "Media belum diisi."
            )

    # =====================================================
    # 5. ALAT STANDAR
    # =====================================================
    alat_standar_records = (
        dataframe_to_records_pubbm(
            data.get(
                "alat_standar"
            )
        )
    )

    # =====================================================
    # 6. SUPABASE
    # =====================================================
    supabase = (
        get_supabase_pubbm()
    )

    # =====================================================
    # 7. MASTER SPBU
    # =====================================================
    spbu_id_input = data.get(
        "_spbu_id"
    )
    
    jenis_lokasi = str(
        data.get(
            "jenis_lokasi",
            ""
        )
        or ""
    ).strip()
    
    kecamatan_spbu = str(
        data.get(
            "kecamatan_spbu",
            ""
        )
        or ""
    ).strip()
    
    media_bbm_master = str(
        data.get(
            "media_bbm_master",
            ""
        )
        or ""
    ).strip()
    
    # =====================================================
    # SIMPAN / UPDATE MASTER SPBU
    #
    # `pemilik` pada struktur form PUBBM saat ini
    # merupakan nama SPBU / nama lokasi yang tampil.
    # =====================================================
    spbu_id = (
        simpan_atau_update_spbu_pubbm(
            supabase=supabase,
    
            spbu_id=(
                spbu_id_input
            ),
    
            nama_spbu=(
                pemilik
            ),
    
            nomor_spbu=(
                nomor_spbu
            ),
    
            alamat=(
                alamat
            ),
    
            jenis_lokasi=(
                jenis_lokasi
            ),
    
            kecamatan=(
                kecamatan_spbu
            ),
    
            media_bbm=(
                media_bbm_master
            ),
        )
    )
    
    # =====================================================
    # SIMPAN KEMBALI ID MASTER KE DATA AKTIF
    # =====================================================
    data[
        "_spbu_id"
    ] = spbu_id
    
    # =====================================================
    # PERUSAHAAN PEMILIK
    #
    # Untuk struktur PUBBM baru, perusahaan_id tidak lagi
    # digunakan sebagai identitas lokasi SPBU.
    #
    # Jika suatu saat badan usaha / pemilik sudah dipetakan,
    # ID tersebut dapat disimpan di _perusahaan_id.
    # =====================================================
    perusahaan_id = data.get(
        "_perusahaan_id"
    )
    
    if (
        perusahaan_id is not None
        and str(
            perusahaan_id
        ).strip() != ""
    ):
        try:
            perusahaan_id = int(
                float(
                    perusahaan_id
                )
            )
    
        except (
            TypeError,
            ValueError
        ):
            perusahaan_id = None
    
    else:
        perusahaan_id = None

    # =====================================================
    # 8. TANGGAL
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
    # 9. SNAPSHOT PENERA
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
    # 10. DATA JSON HEADER KEGIATAN
    #
    # Nozzle, No. Dispenser dan K-Faktor tidak disimpan
    # di sini.
    # =====================================================
    data_pengujian_header = {
        "schema_pubbm": 3,
    
        # =================================================
        # SNAPSHOT IDENTITAS SPBU
        # =================================================
        "_spbu_id": (
            spbu_id
        ),
    
        "pemilik": (
            pemilik
        ),
    
        "nama_spbu": (
            nomor_spbu
        ),
    
        "alamat": (
            alamat
        ),
    
        "jenis_lokasi": (
            jenis_lokasi
        ),
    
        "kecamatan_spbu": (
            kecamatan_spbu
        ),
    
        "media_bbm_master": (
            media_bbm_master
        ),
    
        # =================================================
        # ALAT STANDAR
        # =================================================
        "alat_standar": (
            alat_standar_records
        ),
    
        # =================================================
        # SNAPSHOT PENERA
        # =================================================
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

    # =====================================================
    # 11. PAYLOAD HEADER PENGUJIAN
    #
    # uttp_id = NULL karena UTTP sekarang disimpan melalui
    # tabel relasi pengujian_uttp.
    # =====================================================
    payload_pengujian = {
        # =================================================
        # LOKASI SPBU
        # =================================================
        "spbu_id": (
            spbu_id
        ),
    
        # =================================================
        # BADAN USAHA / PEMILIK
        #
        # Boleh NULL selama belum dipetakan.
        # =================================================
        "perusahaan_id": (
            perusahaan_id
        ),
    
        # =================================================
        # PUBBM = BANYAK UTTP
        # =================================================
        "uttp_id": None,

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
            data_pengujian_header
        ),
    }

    # =====================================================
    # 12. STATUS EDIT
    # =====================================================
    edit_id = st.session_state.get(
        "pubbm_edit_pengujian_id"
    )

    sedang_edit = (
        edit_id is not None
    )
    # =====================================================
    # 12A. CEK NOMOR SERTIFIKAT DUPLIKAT
    #
    # Aturan:
    # - Pengujian baru: nomor sertifikat tidak boleh
    #   sudah digunakan.
    #
    # - Edit: nomor sertifikat milik pengujian yang
    #   sedang diedit sendiri diperbolehkan.
    # =====================================================
    response_sertifikat = (
        supabase
        .table("pengujian")
        .select(
            "id, nomor_sertifikat"
        )
        .eq(
            "nomor_sertifikat",
            nomor_sertifikat
        )
        .execute()
    )

    daftar_sertifikat_sama = (
        response_sertifikat.data
        or []
    )

    sertifikat_duplikat = []

    for row in daftar_sertifikat_sama:

        row_id = row.get(
            "id"
        )

        # =============================================
        # NORMALISASI ID
        # =============================================
        try:
            row_id_int = int(
                row_id
            )
        except (
            TypeError,
            ValueError
        ):
            row_id_int = None

        try:
            edit_id_int = (
                int(edit_id)
                if edit_id is not None
                else None
            )
        except (
            TypeError,
            ValueError
        ):
            edit_id_int = None

        # =============================================
        # SAAT EDIT:
        # ROW MILIK DIRINYA SENDIRI BOLEH
        # =============================================
        if (
            sedang_edit
            and edit_id_int is not None
            and row_id_int == edit_id_int
        ):
            continue

        # =============================================
        # SELAIN ROW SENDIRI = DUPLIKAT
        # =============================================
        sertifikat_duplikat.append(
            row
        )

    if sertifikat_duplikat:
        id_duplikat = [
            row.get("id")
            for row in sertifikat_duplikat
        ]
    
        raise ValueError(
            "Nomor sertifikat sudah pernah digunakan. "
            f"edit_id={edit_id}, "
            f"ID yang memakai nomor ini={id_duplikat}, "
            f"nomor={nomor_sertifikat}"
        )
    # =====================================================
    # 13. CARI / UPDATE MASTER UTTP NOZZLE
    # =====================================================
    daftar_relasi = []

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

        k_faktor = str(
            nozzle.get(
                "K-Faktor",
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
        # MODE EDIT:
        # PERTAHANKAN UTTP ID LAMA
        #
        # Prioritas:
        # 1. _uttp_id yang melekat langsung pada baris nozzle
        # 2. Mapping lama sebagai fallback
        # =============================================
        # =============================================
        # UTTP ID YANG SUDAH DIKENAL
        #
        # Bisa berasal dari:
        # - Edit pengujian
        # - Tambah Pengujian Baru dari Riwayat
        # =============================================
        uttp_id_lama = None
        
        uttp_id_dari_baris = nozzle.get(
            "_uttp_id"
        )
        
        if (
            uttp_id_dari_baris is not None
            and str(
                uttp_id_dari_baris
            ).strip() != ""
        ):
            try:
                uttp_id_lama = int(
                    float(
                        uttp_id_dari_baris
                    )
                )
        
            except (
                TypeError,
                ValueError
            ):
                uttp_id_lama = None

        if uttp_id_lama is not None:

            response_uttp_edit = (
                supabase
                .table("uttp")
                .update({
                    "spbu_id": (
                        spbu_id
                    ),
            
                    "perusahaan_id": (
                        perusahaan_id
                    ),
            
                    "merk": merk,
            
                    "tipe": (
                        tipe
                        if tipe
                        else None
                    ),
            
                    "nomor_seri": (
                        nomor_seri
                        if nomor_seri
                        else None
                    ),
            
                    "lokasi": "SPBU",
            
                    "status": "aktif",
                })
                .eq(
                    "id",
                    uttp_id_lama
                )
                .eq(
                    "spbu_id",
                    spbu_id
                )
                .eq(
                    "jenis_uttp",
                    "Pompa Ukur BBM"
                )
                .execute()
            )

            if not response_uttp_edit.data:
                raise RuntimeError(
                    "UTTP nozzle lama tidak ditemukan "
                    "atau tidak sesuai dengan SPBU "
                    "yang sedang diedit."
                )

            uttp_id = (
                uttp_id_lama
            )

        else:

            # =========================================
            # DATA BARU / NOZZLE BARU
            # =========================================
            uttp_id = (
                get_or_create_nozzle_pubbm(
                    supabase=supabase,
        
                    spbu_id=(
                        spbu_id
                    ),
        
                    perusahaan_id=(
                        perusahaan_id
                    ),
        
                    merk=merk,
                    tipe=tipe,
                    nomor_seri=nomor_seri,
                )
            )
        # =============================================
        # PENGAMAN DUPLIKAT UTTP
        # =============================================
        if (
            uttp_id
            in uttp_id_dalam_form
        ):
            raise ValueError(
                "UTTP nozzle yang sama ditemukan "
                "lebih dari satu kali pada kegiatan."
            )

        uttp_id_dalam_form.add(
            uttp_id
        )

        # =============================================
        # RELASI PENGUJIAN - UTTP
        # =============================================
        daftar_relasi.append({
            "uttp_id": (
                uttp_id
            ),
        
            "no_dispenser": (
                no_dispenser
            ),
        
            "posisi": (
                posisi
                if posisi
                else None
            ),
        
            "media": (
                media
                if media
                else None
            ),
        
            "k_faktor": (
                k_faktor
                if k_faktor
                else None
            ),
        
            "urutan": (
                urutan
            ),
        
            "hasil": "SAH",
        })

    # =====================================================
    # 14. DATA BARU
    # =====================================================
    if not sedang_edit:

        response_pengujian = (
            supabase
            .table(
                "pengujian"
            )
            .insert(
                payload_pengujian
            )
            .execute()
        )

        if not response_pengujian.data:
            raise RuntimeError(
                "Kegiatan pengujian PUBBM "
                "gagal disimpan."
            )

        pengujian_id = (
            response_pengujian.data[0][
                "id"
            ]
        )

        payload_relasi = [
            {
                "pengujian_id": (
                    pengujian_id
                ),
                **relasi,
            }
            for relasi in daftar_relasi
        ]

        try:
            response_relasi = (
                supabase
                .table(
                    "pengujian_uttp"
                )
                .insert(
                    payload_relasi
                )
                .execute()
            )

            if not response_relasi.data:
                raise RuntimeError(
                    "Detail UTTP PUBBM gagal disimpan."
                )

        except Exception:

            # =========================================
            # ROLLBACK HEADER
            #
            # ON DELETE CASCADE juga akan membersihkan
            # relasi yang sempat tersimpan.
            # =========================================
            (
                supabase
                .table(
                    "pengujian"
                )
                .delete()
                .eq(
                    "id",
                    pengujian_id
                )
                .execute()
            )

            raise

        return {
            "pengujian": (
                response_pengujian.data
            ),
            "pengujian_uttp": (
                response_relasi.data
            ),
        }

    # =====================================================
    # 15. MODE EDIT
    # =====================================================
    response_anchor = (
        supabase
        .table(
            "pengujian"
        )
        .select(
            "id, uttp_id"
        )
        .eq(
            "id",
            edit_id
        )
        .execute()
    )

    if not response_anchor.data:
        raise RuntimeError(
            "Data pengujian yang akan diedit "
            "tidak ditemukan."
        )

    pengujian_anchor = (
        response_anchor.data[0]
    )

    # =====================================================
    # 16. EDIT PENGUJIAN PUBBM
    #
    # Struktur resmi:
    # - 1 kegiatan = 1 row pengujian
    # - pengujian.uttp_id = NULL
    # - nozzle berada di pengujian_uttp
    # =====================================================

    # =====================================================
    # PENGAMAN STRUKTUR
    # =====================================================
    if (
        pengujian_anchor.get(
            "uttp_id"
        )
        is not None
    ):
        raise RuntimeError(
            "Data pengujian PUBBM masih menggunakan "
            "struktur lama dan tidak dapat diedit."
        )

    pengujian_id = edit_id

    # =====================================================
    # UPDATE HEADER PENGUJIAN
    # =====================================================
    response_update_header = (
        supabase
        .table(
            "pengujian"
        )
        .update(
            payload_pengujian
        )
        .eq(
            "id",
            pengujian_id
        )
        .execute()
    )

    if not response_update_header.data:
        raise RuntimeError(
            "Header kegiatan PUBBM "
            "gagal diperbarui."
        )

    # =====================================================
    # AMBIL RELASI LAMA
    # =====================================================
    response_relasi_lama = (
        supabase
        .table(
            "pengujian_uttp"
        )
        .select(
            "id, uttp_id"
        )
        .eq(
            "pengujian_id",
            pengujian_id
        )
        .execute()
    )

    relasi_lama = (
        response_relasi_lama.data
        or []
    )

    relasi_lama_per_uttp = {
        row.get(
            "uttp_id"
        ): row
        for row in relasi_lama
    }

    id_uttp_baru = {
        item[
            "uttp_id"
        ]
        for item in daftar_relasi
    }

    hasil_relasi = []

    # =====================================================
    # UPDATE / INSERT RELASI
    # =====================================================
    for relasi in daftar_relasi:

        uttp_id = relasi[
            "uttp_id"
        ]

        relasi_lama_item = (
            relasi_lama_per_uttp.get(
                uttp_id
            )
        )

        # =================================================
        # RELASI SUDAH ADA → UPDATE
        # =================================================
        if relasi_lama_item:

            response_relasi_item = (
                supabase
                .table(
                    "pengujian_uttp"
                )
                .update({
                    "no_dispenser": (
                        relasi[
                            "no_dispenser"
                        ]
                    ),

                    "posisi": (
                        relasi[
                            "posisi"
                        ]
                    ),

                    "media": (
                        relasi[
                            "media"
                        ]
                    ),

                    "k_faktor": (
                        relasi[
                            "k_faktor"
                        ]
                    ),

                    "urutan": (
                        relasi[
                            "urutan"
                        ]
                    ),

                    "hasil": (
                        relasi[
                            "hasil"
                        ]
                    ),
                })
                .eq(
                    "id",
                    relasi_lama_item[
                        "id"
                    ]
                )
                .execute()
            )

        # =================================================
        # RELASI BELUM ADA → INSERT
        # =================================================
        else:

            response_relasi_item = (
                supabase
                .table(
                    "pengujian_uttp"
                )
                .insert({
                    "pengujian_id": (
                        pengujian_id
                    ),
                    **relasi,
                })
                .execute()
            )

        hasil_relasi.extend(
            response_relasi_item.data
            or []
        )

    # =====================================================
    # HAPUS RELASI NOZZLE YANG SUDAH TIDAK ADA
    #
    # Master UTTP TIDAK dihapus.
    # Hanya hubungan dengan pengujian ini.
    # =====================================================
    for relasi_lama_item in relasi_lama:

        uttp_id_lama = (
            relasi_lama_item.get(
                "uttp_id"
            )
        )

        if (
            uttp_id_lama
            not in id_uttp_baru
        ):
            (
                supabase
                .table(
                    "pengujian_uttp"
                )
                .delete()
                .eq(
                    "id",
                    relasi_lama_item[
                        "id"
                    ]
                )
                .execute()
            )

    # =====================================================
    # HASIL SIMPAN EDIT
    #
    # Variabel inilah yang sebelumnya kemungkinan
    # hilang / berada pada indentasi yang salah.
    # =====================================================
    hasil_simpan = {
        "pengujian": (
            response_update_header.data
        ),

        "pengujian_uttp": (
            hasil_relasi
        ),
    }

    # =====================================================
    # 17. KELUAR DARI MODE EDIT
    # =====================================================
    st.session_state.pop(
        "pubbm_edit_pengujian_id",
        None
    )

    st.session_state.pop(
        "pubbm_edit_nomor_sertifikat_asli",
        None
    )

    return hasil_simpan

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
        or ""
    ).strip()

    df_spbu = st.session_state.get(
        "data_spbu"
    )

    # =====================================================
    # JIKA PILIHAN KOSONG
    # =====================================================
    if not selected:

        st.session_state[
            "spbu_id_pubbm"
        ] = None

        st.session_state[
            "nomor_spbu_pubbm"
        ] = ""

        st.session_state[
            "alamat_input_pubbm"
        ] = ""

        st.session_state[
            "jenis_lokasi_pubbm"
        ] = ""

        st.session_state[
            "kecamatan_spbu_pubbm"
        ] = ""

        st.session_state[
            "media_bbm_master_pubbm"
        ] = ""

        return

    if (
        df_spbu is None
        or df_spbu.empty
    ):
        return

    # =====================================================
    # CARI MASTER SPBU
    # =====================================================
    row = df_spbu[
        df_spbu["Nama SPBU"]
        .astype(str)
        .str.strip()
        == selected
    ]

    if row.empty:
        return

    data = row.iloc[0]

    # =====================================================
    # ID MASTER SPBU
    # =====================================================
    spbu_id = data.get(
        "ID SPBU"
    )

    if pd.isna(
        spbu_id
    ):
        spbu_id = None

    elif (
        spbu_id is not None
        and str(spbu_id).strip() != ""
    ):
        try:
            spbu_id = int(
                float(
                    spbu_id
                )
            )
        except (
            TypeError,
            ValueError
        ):
            spbu_id = None

    st.session_state[
        "spbu_id_pubbm"
    ] = spbu_id

    # =====================================================
    # NAMA SPBU
    # =====================================================
    st.session_state[
        "nama_perusahaan"
    ] = selected

    # =====================================================
    # ALAMAT
    # =====================================================
    alamat_spbu = data.get(
        "Alamat",
        ""
    )

    if pd.isna(
        alamat_spbu
    ):
        alamat_spbu = ""

    st.session_state[
        "alamat_input_pubbm"
    ] = str(
        alamat_spbu
        or ""
    ).strip()

    # =====================================================
    # NOMOR SPBU
    # =====================================================
    nomor_spbu = data.get(
        "Nomor SPBU",
        ""
    )

    if pd.isna(
        nomor_spbu
    ):
        nomor_spbu = ""

    nomor_spbu = str(
        nomor_spbu
        or ""
    ).strip()

    # Fallback untuk data lama
    if not nomor_spbu:

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

    # =====================================================
    # JENIS LOKASI
    # =====================================================
    jenis_lokasi = data.get(
        "Jenis Lokasi",
        ""
    )

    if pd.isna(
        jenis_lokasi
    ):
        jenis_lokasi = ""

    st.session_state[
        "jenis_lokasi_pubbm"
    ] = str(
        jenis_lokasi
        or ""
    ).strip()

    # =====================================================
    # KECAMATAN
    # =====================================================
    kecamatan = data.get(
        "Kecamatan",
        ""
    )

    if pd.isna(
        kecamatan
    ):
        kecamatan = ""

    st.session_state[
        "kecamatan_spbu_pubbm"
    ] = str(
        kecamatan
        or ""
    ).strip()

    # =====================================================
    # MEDIA BBM MASTER
    # =====================================================
    media_bbm = data.get(
        "Media BBM",
        ""
    )

    if pd.isna(
        media_bbm
    ):
        media_bbm = ""

    st.session_state[
        "media_bbm_master_pubbm"
    ] = str(
        media_bbm
        or ""
    ).strip()
# =========================================================
# AMBIL RIWAYAT PUBBM PER MASTER SPBU
# =========================================================
def ambil_riwayat_kegiatan_pubbm(
    supabase,
    spbu,
):
    """
    Membaca riwayat PUBBM berdasarkan master SPBU.

    Struktur resmi:
    --------------------------------
    spbu
        ↓
    pengujian.spbu_id
        ↓
    pengujian_uttp
        ↓
    uttp.spbu_id

    1 kegiatan / 1 sertifikat
        = 1 row pengujian

    N nozzle
        = N row pengujian_uttp
    """

    # =====================================================
    # 1. ID MASTER SPBU
    # =====================================================
    spbu_id = spbu.get(
        "id"
    )

    if (
        spbu_id is None
        or str(spbu_id).strip() == ""
    ):
        return []

    try:
        spbu_id = int(
            float(
                spbu_id
            )
        )

    except (
        TypeError,
        ValueError
    ):
        return []

    # =====================================================
    # 2. MASTER UTTP PUBBM MILIK SPBU
    # =====================================================
    response_uttp = (
        supabase
        .table("uttp")
        .select(
            "id, "
            "spbu_id, "
            "perusahaan_id, "
            "jenis_uttp, "
            "merk, "
            "tipe, "
            "nomor_seri"
        )
        .eq(
            "spbu_id",
            spbu_id
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

    uttp_map = {
        row["id"]: row
        for row in daftar_uttp
        if row.get(
            "id"
        ) is not None
    }

    # =====================================================
    # 3. AMBIL PENGUJIAN BERDASARKAN SPBU
    # =====================================================
    response_pengujian = (
        supabase
        .table("pengujian")
        .select("*")
        .eq(
            "spbu_id",
            spbu_id
        )
        .order(
            "tanggal_pengujian",
            desc=True
        )
        .execute()
    )

    semua_pengujian = (
        response_pengujian.data
        or []
    )

    if not semua_pengujian:
        return []

    # =====================================================
    # 4. FILTER HANYA PUBBM STRUKTUR BARU
    # =====================================================
    pengujian_baru = []

    for row in semua_pengujian:

        detail = (
            row.get(
                "data_pengujian"
            )
            or {}
        )

        schema_pubbm = str(
            detail.get(
                "schema_pubbm",
                ""
            )
            or ""
        ).strip()

        if (
            row.get(
                "uttp_id"
            ) is None
            and schema_pubbm == "3"
        ):
            pengujian_baru.append(
                row
            )

    if not pengujian_baru:
        return []

    # =====================================================
    # 5. AMBIL SELURUH RELASI NOZZLE
    # =====================================================
    daftar_header_id = [
        row.get(
            "id"
        )
        for row in pengujian_baru
        if row.get(
            "id"
        ) is not None
    ]

    response_relasi = (
        supabase
        .table(
            "pengujian_uttp"
        )
        .select(
            "id, "
            "pengujian_id, "
            "uttp_id, "
            "no_dispenser, "
            "posisi, "
            "media, "
            "k_faktor, "
            "urutan, "
            "hasil"
        )
        .in_(
            "pengujian_id",
            daftar_header_id
        )
        .execute()
    )

    daftar_relasi = (
        response_relasi.data
        or []
    )

    relasi_per_pengujian = {}

    for relasi in daftar_relasi:

        pengujian_id = relasi.get(
            "pengujian_id"
        )

        relasi_per_pengujian.setdefault(
            pengujian_id,
            []
        ).append(
            relasi
        )

    # =====================================================
    # 6. SUSUN KEGIATAN PUBBM
    # =====================================================
    daftar_kegiatan = []

    for header in pengujian_baru:

        pengujian_id = header.get(
            "id"
        )

        detail_header = (
            header.get(
                "data_pengujian"
            )
            or {}
        )

        relasi_kegiatan = (
            relasi_per_pengujian.get(
                pengujian_id,
                []
            )
            or []
        )

        # =================================================
        # URUTKAN SESUAI URUTAN SERTIFIKAT
        # =================================================
        relasi_kegiatan = sorted(
            relasi_kegiatan,
            key=lambda item: int(
                item.get(
                    "urutan",
                    999999
                )
                or 999999
            )
        )

        dispenser_records = []

        daftar_media = []
        daftar_posisi = []
        nomor_dispenser_set = set()

        for relasi in relasi_kegiatan:

            # =============================================
            # MASTER UTTP
            # =============================================
            uttp_id = relasi.get(
                "uttp_id"
            )

            uttp = uttp_map.get(
                uttp_id,
                {}
            )

            # =============================================
            # NOMOR DISPENSER
            # =============================================
            no_dispenser = relasi.get(
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

            # =============================================
            # MASTER UTTP
            # =============================================
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

            # =============================================
            # DATA PER PENGUJIAN
            # =============================================
            posisi = str(
                relasi.get(
                    "posisi",
                    ""
                )
                or ""
            ).strip()

            media = str(
                relasi.get(
                    "media",
                    ""
                )
                or ""
            ).strip()

            k_faktor = str(
                relasi.get(
                    "k_faktor",
                    ""
                )
                or ""
            ).strip()

            dispenser_records.append({
                "_uttp_id": (
                    uttp_id
                ),

                "No": (
                    no_dispenser
                    if no_dispenser is not None
                    else ""
                ),

                "Posisi": posisi,
                "Merk": merk,
                "Tipe": tipe,
                "No. Seri": no_seri,
                "Media": media,
                "K-Faktor": k_faktor,
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

        # =================================================
        # SNAPSHOT PENERA / ALAT STANDAR
        # =================================================
        alat_standar = list(
            detail_header.get(
                "alat_standar",
                []
            )
            or []
        )

        # =================================================
        # DETAIL VIRTUAL UNTUK FORM
        # =================================================
        detail_gabungan = {
            "schema_pubbm": 3,

            "_spbu_id": (
                spbu_id
            ),

            "nama_alat": (
                "Pompa Ukur BBM (Dispenser)"
            ),

            # =============================================
            # IDENTITAS SPBU DARI MASTER SPBU
            # =============================================
            "pemilik": str(
                spbu.get(
                    "nama_spbu",
                    ""
                )
                or ""
            ).strip(),

            "nama_spbu": str(
                spbu.get(
                    "nomor_spbu",
                    ""
                )
                or ""
            ).strip(),

            "alamat": str(
                spbu.get(
                    "alamat",
                    ""
                )
                or ""
            ).strip(),

            "jenis_lokasi": str(
                spbu.get(
                    "jenis_lokasi",
                    ""
                )
                or ""
            ).strip(),

            "kecamatan_spbu": str(
                spbu.get(
                    "kecamatan",
                    ""
                )
                or ""
            ).strip(),

            "media_bbm_master": str(
                spbu.get(
                    "media_bbm",
                    ""
                )
                or ""
            ).strip(),

            # =============================================
            # DATA DISPENSER
            # =============================================
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

            "dispenser": (
                dispenser_records
            ),

            # =============================================
            # ALAT STANDAR
            # =============================================
            "alat_standar": (
                alat_standar
            ),

            "jumlah_alat_standar": len(
                alat_standar
            ),

            # =============================================
            # PENERA
            # =============================================
            "penera_1": str(
                header.get(
                    "penera_1",
                    ""
                )
                or ""
            ).strip(),

            "nip_penera_1": str(
                detail_header.get(
                    "nip_penera_1",
                    ""
                )
                or ""
            ).strip(),

            "golongan_penera_1": str(
                detail_header.get(
                    "golongan_penera_1",
                    ""
                )
                or ""
            ).strip(),

            "penera_2": str(
                header.get(
                    "penera_2",
                    ""
                )
                or ""
            ).strip(),

            "nip_penera_2": str(
                detail_header.get(
                    "nip_penera_2",
                    ""
                )
                or ""
            ).strip(),

            "golongan_penera_2": str(
                detail_header.get(
                    "golongan_penera_2",
                    ""
                )
                or ""
            ).strip(),

            "jumlah_penera": (
                2
                if str(
                    header.get(
                        "penera_2",
                        ""
                    )
                    or ""
                ).strip()
                else 1
            ),
        }

        kegiatan = dict(
            header
        )

        kegiatan[
            "data_pengujian"
        ] = detail_gabungan

        daftar_kegiatan.append(
            kegiatan
        )

    # =====================================================
    # 7. URUTKAN RIWAYAT
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
            
            
    @st.cache_data(ttl=60)
    def load_data_media_spbu():
        """
        Membaca master kategori media SPBU dari Supabase.
        """
    
        try:
            supabase = get_supabase_pubbm()
    
            response = (
                supabase
                .table("media_spbu")
                .select(
                    "kategori_spbu, media, status"
                )
                .eq(
                    "status",
                    "aktif"
                )
                .order(
                    "kategori_spbu"
                )
                .execute()
            )
    
            rows = (
                response.data
                or []
            )
    
            if not rows:
                return pd.DataFrame(
                    columns=[
                        "KATEGORI SPBU",
                        "MEDIA",
                    ]
                )
    
            df = pd.DataFrame(
                rows
            )
    
            df = df.rename(
                columns={
                    "kategori_spbu": "KATEGORI SPBU",
                    "media": "MEDIA",
                }
            )
    
            df["KATEGORI SPBU"] = (
                df["KATEGORI SPBU"]
                .fillna("")
                .astype(str)
                .str.strip()
            )
    
            df["MEDIA"] = (
                df["MEDIA"]
                .fillna("")
                .astype(str)
                .str.strip()
            )
    
            return df[
                [
                    "KATEGORI SPBU",
                    "MEDIA",
                ]
            ]
    
        except Exception as exc:
            st.warning(
                "Master media SPBU dari Supabase "
                f"tidak dapat dibaca: {exc}"
            )
    
            return pd.DataFrame(
                columns=[
                    "KATEGORI SPBU",
                    "MEDIA",
                ]
            )
    
    
    def get_kategori_spbu(
        nama_spbu="",
        jenis_lokasi="",
    ):
        """
        Menentukan kategori media.
    
        Prioritas:
        1. jenis_lokasi dari master SPBU
        2. fallback dari nama SPBU
        """
    
        jenis = str(
            jenis_lokasi or ""
        ).upper().strip()
    
        nama = str(
            nama_spbu or ""
        ).upper().strip()
    
        if jenis:
            if "SHELL" in jenis:
                return "SHELL"
    
            if "BP" in jenis:
                return "BP AKR"
    
            if "VIVO" in jenis:
                return "VIVO"
    
            if "PERTASHOP" in jenis:
                return "PERTASHOP"
    
            if "SPBU" in jenis:
                return "SPBU"
    
        if "SHELL" in nama:
            return "SHELL"
    
        if "BP AKR" in nama:
            return "BP AKR"
    
        if "VIVO" in nama:
            return "VIVO"
    
        if "PERTASHOP" in nama:
            return "PERTASHOP"
    
        return "SPBU"
    
    
    def get_media_options(
        nama_spbu,
        df_media,
        jenis_lokasi="",
        media_bbm_master="",
    ):
        """
        Pilihan media nozzle.
    
        Prioritas:
        1. media_bbm dari master SPBU
        2. master kategori media_spbu
        """
    
        # =====================================================
        # 1. MEDIA AKTUAL DARI MASTER SPBU
        # =====================================================
        media_master = str(
            media_bbm_master or ""
        ).strip()
    
        if media_master:
            media_list = [
                item.strip()
                for item in media_master.split(",")
                if item.strip()
            ]
    
            if media_list:
                return media_list
    
        # =====================================================
        # 2. FALLBACK BERDASARKAN KATEGORI
        # =====================================================
        kategori = get_kategori_spbu(
            nama_spbu=nama_spbu,
            jenis_lokasi=jenis_lokasi,
        )
    
        if (
            df_media is None
            or df_media.empty
        ):
            return []
    
        row = df_media[
            df_media["KATEGORI SPBU"]
            .astype(str)
            .str.upper()
            .str.strip()
            == kategori.upper()
        ]
    
        if row.empty:
            return []
    
        media_text = str(
            row.iloc[0].get(
                "MEDIA",
                ""
            )
            or ""
        ).strip()
    
        return [
            item.strip()
            for item in media_text.split(",")
            if item.strip()
        ]
    @st.cache_data(ttl=60)
    def load_data_bejana():
        """
        Membaca master Bejana Ukur aktif dari Supabase.
        """
    
        kolom_target = [
            "ID",
            "Standar Volume",
            "Merk",
            "Tipe",
            "Nomor Seri",
            "Kelas",
            "Kapasitas",
            "Satuan Kapasitas",
            "Daya Baca",
            "Satuan Daya Baca",
            "Telusuran",
        ]
    
        try:
            supabase = get_supabase_pubbm()
    
            response = (
                supabase
                .table("bejana")
                .select(
                    "id, "
                    "standar_volume, "
                    "merk, "
                    "tipe, "
                    "nomor_seri, "
                    "kelas, "
                    "kapasitas, "
                    "satuan_kapasitas, "
                    "daya_baca, "
                    "satuan_daya_baca, "
                    "telusuran, "
                    "status"
                )
                .eq(
                    "status",
                    "aktif"
                )
                .order(
                    "merk"
                )
                .execute()
            )
    
            rows = (
                response.data
                or []
            )
    
            if not rows:
                return pd.DataFrame(
                    columns=kolom_target
                )
    
            df = pd.DataFrame(
                rows
            )
    
            # =================================================
            # SAMAKAN NAMA KOLOM DENGAN UI
            # =================================================
            df = df.rename(
                columns={
                    "id": "ID",
                    "standar_volume": "Standar Volume",
                    "merk": "Merk",
                    "tipe": "Tipe",
                    "nomor_seri": "Nomor Seri",
                    "kelas": "Kelas",
                    "kapasitas": "Kapasitas",
                    "satuan_kapasitas": "Satuan Kapasitas",
                    "daya_baca": "Daya Baca",
                    "satuan_daya_baca": "Satuan Daya Baca",
                    "telusuran": "Telusuran",
                }
            )
    
            # =================================================
            # PASTIKAN SEMUA KOLOM ADA
            # =================================================
            for kolom in kolom_target:
                if kolom not in df.columns:
                    df[kolom] = ""
    
            # =================================================
            # BERSIHKAN NILAI
            # =================================================
            for kolom in [
                "Standar Volume",
                "Merk",
                "Tipe",
                "Nomor Seri",
                "Kelas",
                "Satuan Kapasitas",
                "Satuan Daya Baca",
                "Telusuran",
            ]:
                df[kolom] = (
                    df[kolom]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                )
    
            # =================================================
            # NOMOR SERI JANGAN JADI 10.0, 9.0, DST
            # =================================================
            df["Nomor Seri"] = (
                df["Nomor Seri"]
                .apply(
                    lambda nilai: (
                        nilai[:-2]
                        if isinstance(nilai, str)
                        and nilai.endswith(".0")
                        else nilai
                    )
                )
            )
    
            # =================================================
            # URUTKAN
            # =================================================
            df = (
                df[
                    kolom_target
                ]
                .sort_values(
                    [
                        "Merk",
                        "Nomor Seri",
                    ]
                )
                .reset_index(
                    drop=True
                )
            )
    
            return df
    
        except Exception as exc:
            st.warning(
                "Master Bejana Ukur dari Supabase "
                f"tidak dapat dibaca: {exc}"
            )
    
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
        Master SPBU langsung dari tabel Supabase `spbu`.
    
        Output tetap menggunakan kolom:
        - Nama SPBU
        - Nomor SPBU
        - Alamat
        - Jenis Lokasi
        - Kecamatan
        - Media BBM
        """
    
        try:
            supabase = get_supabase_pubbm()
    
            response = (
                supabase
                .table("spbu")
                .select(
                    "id, "
                    "nama_spbu, "
                    "nomor_spbu, "
                    "alamat, "
                    "jenis_lokasi, "
                    "kecamatan, "
                    "media_bbm, "
                    "status"
                )
                .eq(
                    "status",
                    "aktif"
                )
                .order(
                    "nama_spbu"
                )
                .execute()
            )
    
            rows = (
                response.data
                or []
            )
    
            if not rows:
                return pd.DataFrame(
                    columns=[
                        "ID SPBU",
                        "Nama SPBU",
                        "Nomor SPBU",
                        "Alamat",
                        "Jenis Lokasi",
                        "Kecamatan",
                        "Media BBM",
                    ]
                )
    
            data = []
    
            for row in rows:
    
                data.append({
                    "ID SPBU": (
                        row.get(
                            "id"
                        )
                    ),
    
                    "Nama SPBU": str(
                        row.get(
                            "nama_spbu",
                            ""
                        )
                        or ""
                    ).strip(),
    
                    "Nomor SPBU": str(
                        row.get(
                            "nomor_spbu",
                            ""
                        )
                        or ""
                    ).strip(),
    
                    "Alamat": str(
                        row.get(
                            "alamat",
                            ""
                        )
                        or ""
                    ).strip(),
    
                    "Jenis Lokasi": str(
                        row.get(
                            "jenis_lokasi",
                            ""
                        )
                        or ""
                    ).strip(),
    
                    "Kecamatan": str(
                        row.get(
                            "kecamatan",
                            ""
                        )
                        or ""
                    ).strip(),
    
                    "Media BBM": str(
                        row.get(
                            "media_bbm",
                            ""
                        )
                        or ""
                    ).strip(),
                })
    
            df = pd.DataFrame(
                data
            )
    
            # =================================================
            # BERSIHKAN DATA
            # =================================================
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
    
            df["Alamat"] = (
                df["Alamat"]
                .fillna("")
                .astype(str)
                .str.strip()
            )
    
            df["Jenis Lokasi"] = (
                df["Jenis Lokasi"]
                .fillna("")
                .astype(str)
                .str.strip()
            )
    
            df["Kecamatan"] = (
                df["Kecamatan"]
                .fillna("")
                .astype(str)
                .str.strip()
            )
    
            df["Media BBM"] = (
                df["Media BBM"]
                .fillna("")
                .astype(str)
                .str.strip()
            )
    
            # =================================================
            # HAPUS BARIS TANPA NAMA
            # =================================================
            df = df[
                df["Nama SPBU"] != ""
            ]
    
            # =================================================
            # URUTKAN
            # =================================================
            df = (
                df
                .sort_values(
                    "Nama SPBU"
                )
                .reset_index(
                    drop=True
                )
            )
    
            return df
    
        except Exception as exc:
            st.warning(
                "Master SPBU dari Supabase "
                f"tidak dapat dibaca: {exc}"
            )
    
            return pd.DataFrame(
                columns=[
                    "ID SPBU",
                    "Nama SPBU",
                    "Nomor SPBU",
                    "Alamat",
                    "Jenis Lokasi",
                    "Kecamatan",
                    "Media BBM",
                ]
            )
    
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
    if "spbu_id_pubbm" not in st.session_state:
        st.session_state.spbu_id_pubbm = None
    
    if "jenis_lokasi_pubbm" not in st.session_state:
        st.session_state.jenis_lokasi_pubbm = ""
    
    if "kecamatan_spbu_pubbm" not in st.session_state:
        st.session_state.kecamatan_spbu_pubbm = ""
    
    if "media_bbm_master_pubbm" not in st.session_state:
        st.session_state.media_bbm_master_pubbm = ""
        
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
        # IDENTITAS MASTER SPBU
        # =====================================================
        spbu_id_restore = data.get(
            "_spbu_id"
        )
        
        if (
            spbu_id_restore is not None
            and str(spbu_id_restore).strip() != ""
        ):
            try:
                spbu_id_restore = int(
                    float(spbu_id_restore)
                )
            except (
                TypeError,
                ValueError
            ):
                spbu_id_restore = None
        
        else:
            spbu_id_restore = None
        
        st.session_state[
            "spbu_id_pubbm"
        ] = spbu_id_restore
        
        st.session_state[
            "jenis_lokasi_pubbm"
        ] = str(
            data.get(
                "jenis_lokasi",
                ""
            )
            or ""
        ).strip()
        
        st.session_state[
            "kecamatan_spbu_pubbm"
        ] = str(
            data.get(
                "kecamatan_spbu",
                ""
            )
            or ""
        ).strip()
        
        st.session_state[
            "media_bbm_master_pubbm"
        ] = str(
            data.get(
                "media_bbm_master",
                ""
            )
            or ""
        ).strip()
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
        #
        # Prioritas:
        # 1. _spbu_id
        # 2. Nama SPBU sebagai fallback
        # =====================================================
        df_spbu = st.session_state.get(
            "data_spbu"
        )
        
        spbu_ditemukan = False
        
        spbu_id_restore = data.get(
            "_spbu_id"
        )
        
        if (
            spbu_id_restore is not None
            and str(
                spbu_id_restore
            ).strip() != ""
        ):
            try:
                spbu_id_restore = int(
                    float(
                        spbu_id_restore
                    )
                )
        
            except (
                TypeError,
                ValueError
            ):
                spbu_id_restore = None
        
        else:
            spbu_id_restore = None
        
        
        # =====================================================
        # 1. CARI BERDASARKAN ID MASTER
        # =====================================================
        if (
            df_spbu is not None
            and not df_spbu.empty
            and spbu_id_restore is not None
            and "ID SPBU" in df_spbu.columns
        ):
            row_spbu = df_spbu[
                pd.to_numeric(
                    df_spbu["ID SPBU"],
                    errors="coerce"
                )
                == spbu_id_restore
            ]
        
            if not row_spbu.empty:
                data_spbu_restore = (
                    row_spbu.iloc[0]
                )
        
                nama_master = str(
                    data_spbu_restore.get(
                        "Nama SPBU",
                        ""
                    )
                    or ""
                ).strip()
        
                nomor_master = str(
                    data_spbu_restore.get(
                        "Nomor SPBU",
                        ""
                    )
                    or ""
                ).strip()
        
                alamat_master = str(
                    data_spbu_restore.get(
                        "Alamat",
                        ""
                    )
                    or ""
                ).strip()
        
                jenis_lokasi_master = str(
                    data_spbu_restore.get(
                        "Jenis Lokasi",
                        ""
                    )
                    or ""
                ).strip()
        
                kecamatan_master = str(
                    data_spbu_restore.get(
                        "Kecamatan",
                        ""
                    )
                    or ""
                ).strip()
        
                media_master = str(
                    data_spbu_restore.get(
                        "Media BBM",
                        ""
                    )
                    or ""
                ).strip()
        
                st.session_state[
                    "spbu_id_pubbm"
                ] = spbu_id_restore
        
                st.session_state[
                    "spbu_select"
                ] = nama_master
        
                st.session_state[
                    "nama_perusahaan"
                ] = nama_master
        
                st.session_state[
                    "nomor_spbu_pubbm"
                ] = nomor_master
        
                st.session_state[
                    "alamat_input_pubbm"
                ] = alamat_master
        
                st.session_state[
                    "jenis_lokasi_pubbm"
                ] = jenis_lokasi_master
        
                st.session_state[
                    "kecamatan_spbu_pubbm"
                ] = kecamatan_master
        
                st.session_state[
                    "media_bbm_master_pubbm"
                ] = media_master
        
                st.session_state[
                    "input_manual_spbu"
                ] = False
        
                spbu_ditemukan = True
        
        
        # =====================================================
        # 2. FALLBACK BERDASARKAN NAMA
        # =====================================================
        if (
            not spbu_ditemukan
            and df_spbu is not None
            and not df_spbu.empty
            and nama_spbu_restore
        ):
            row_spbu = df_spbu[
                df_spbu["Nama SPBU"]
                .astype(str)
                .str.strip()
                == nama_spbu_restore
            ]
        
            if not row_spbu.empty:
                data_spbu_restore = (
                    row_spbu.iloc[0]
                )
        
                st.session_state[
                    "spbu_select"
                ] = nama_spbu_restore
        
                st.session_state[
                    "input_manual_spbu"
                ] = False
        
                # Ambil ID master jika tersedia
                spbu_id_fallback = (
                    data_spbu_restore.get(
                        "ID SPBU"
                    )
                )
        
                if pd.isna(
                    spbu_id_fallback
                ):
                    spbu_id_fallback = None
        
                elif (
                    spbu_id_fallback is not None
                    and str(
                        spbu_id_fallback
                    ).strip() != ""
                ):
                    try:
                        spbu_id_fallback = int(
                            float(
                                spbu_id_fallback
                            )
                        )
                    except (
                        TypeError,
                        ValueError
                    ):
                        spbu_id_fallback = None
        
                st.session_state[
                    "spbu_id_pubbm"
                ] = spbu_id_fallback
        
                spbu_ditemukan = True
        
        
        # =====================================================
        # 3. TIDAK ADA DI MASTER → INPUT MANUAL
        # =====================================================
        if (
            nama_spbu_restore
            and not spbu_ditemukan
        ):
            st.session_state[
                "spbu_select"
            ] = ""
        
            st.session_state[
                "spbu_id_pubbm"
            ] = None
        
            st.session_state[
                "input_manual_spbu"
            ] = True
        
        
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
        dispenser_data = data.get(
            "dispenser"
        )
        
        # =====================================================
        # NORMALISASI MENJADI DATAFRAME
        # =====================================================
        if isinstance(
            dispenser_data,
            pd.DataFrame
        ):
            dispenser_df = (
                dispenser_data.copy()
            )
        
        elif isinstance(
            dispenser_data,
            list
        ):
            dispenser_df = pd.DataFrame(
                dispenser_data
            )
        
        else:
            dispenser_df = pd.DataFrame()
        
        # =====================================================
        # PASTIKAN KOLOM DISPENSER LENGKAP
        # =====================================================
        kolom_dispenser = [
            "_uttp_id",
            "No",
            "Posisi",
            "Merk",
            "Tipe",
            "No. Seri",
            "Media",
            "K-Faktor",
        ]
        
        for kolom in kolom_dispenser:
            if kolom not in dispenser_df.columns:
                dispenser_df[
                    kolom
                ] = None if kolom == "_uttp_id" else ""
        
        dispenser_df = (
            dispenser_df[
                kolom_dispenser
            ]
            .copy()
        )
        
        # =====================================================
        # NORMALISASI NOMOR DISPENSER
        # =====================================================
        if (
            not dispenser_df.empty
            and "No" in dispenser_df.columns
        ):
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
        
        # =====================================================
        # NORMALISASI _uttp_id
        # =====================================================
        if (
            not dispenser_df.empty
            and "_uttp_id" in dispenser_df.columns
        ):
            dispenser_df[
                "_uttp_id"
            ] = pd.to_numeric(
                dispenser_df[
                    "_uttp_id"
                ],
                errors="coerce"
            )
        
            dispenser_df[
                "_uttp_id"
            ] = dispenser_df[
                "_uttp_id"
            ].where(
                dispenser_df[
                    "_uttp_id"
                ].notna(),
                None
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
                    # =============================================
                    # ID UTTP ASLI NOZZLE
                    # Hanya digunakan secara internal saat Edit.
                    # =============================================
                    uttp_id_restore = row.get(
                        "_uttp_id",
                        None
                    )
                    
                    if pd.isna(
                        uttp_id_restore
                    ):
                        uttp_id_restore = None
                    
                    st.session_state[
                        f"uttp_id_{nomor_dispenser}_{nomor_posisi}"
                    ] = uttp_id_restore

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
            "uttp_id_",
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
            "pubbm_edit_nomor_sertifikat_asli",
            "spbu_id_pubbm",
            "jenis_lokasi_pubbm",
            "kecamatan_spbu_pubbm",
            "media_bbm_master_pubbm",
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
        spbu,
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
        # ID PENGUJIAN YANG SEDANG DIEDIT
        #
        # Struktur resmi PUBBM:
        # 1 kegiatan = 1 row pengujian
        # =====================================================
        edit_id = (
            pengujian.get(
                "id"
            )
        )

        if edit_id is None:
            raise ValueError(
                "ID pengujian PUBBM tidak ditemukan."
            )

        st.session_state[
            "pubbm_edit_pengujian_id"
        ] = edit_id
        # =====================================================
        # NOMOR SERTIFIKAT ASLI SAAT MASUK MODE EDIT
        #
        # Dipakai agar sertifikat milik pengujian ini sendiri
        # tidak dianggap sebagai duplikat.
        # =====================================================
        st.session_state[
            "pubbm_edit_nomor_sertifikat_asli"
        ] = str(
            pengujian.get(
                "nomor_sertifikat",
                ""
            )
            or ""
        ).strip()
        # =====================================================
        # HAPUS DRAFT INPUT LAMA
        #
        # Saat Edit dipilih dari Riwayat, data kegiatan yang
        # dipilih harus menjadi prioritas utama.
        # Draft form lama tidak boleh menimpa data Edit.
        # =====================================================
        st.session_state.pop(
            "pubbm_draft_widget",
            None
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
                "_uttp_id",
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
        
            # =============================================
            # IDENTITAS MASTER SPBU
            # =============================================
            "_spbu_id": (
                pengujian.get(
                    "spbu_id"
                )
                or spbu.get(
                    "id"
                )
                or detail.get(
                    "_spbu_id"
                )
            ),
        
            "pemilik": str(
                spbu.get(
                    "nama_spbu",
                    ""
                )
                or detail.get(
                    "pemilik",
                    ""
                )
                or ""
            ).strip(),
        
            "nama_spbu": str(
                spbu.get(
                    "nomor_spbu",
                    ""
                )
                or detail.get(
                    "nama_spbu",
                    ""
                )
                or ""
            ).strip(),
        
            "alamat": str(
                spbu.get(
                    "alamat",
                    ""
                )
                or detail.get(
                    "alamat",
                    ""
                )
                or ""
            ).strip(),
        
            "jenis_lokasi": str(
                spbu.get(
                    "jenis_lokasi",
                    ""
                )
                or detail.get(
                    "jenis_lokasi",
                    ""
                )
                or ""
            ).strip(),
        
            "kecamatan_spbu": str(
                spbu.get(
                    "kecamatan",
                    ""
                )
                or detail.get(
                    "kecamatan_spbu",
                    ""
                )
                or ""
            ).strip(),
        
            "media_bbm_master": str(
                spbu.get(
                    "media_bbm",
                    ""
                )
                or detail.get(
                    "media_bbm_master",
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
        
            "jumlah_alat_standar": (
                len(alat_standar_df)
                if not alat_standar_df.empty
                else 1
            ),
        
            "alat_standar": alat_standar_df,
        
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
            "uttp_id_",
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
        spbu,
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
        # PASTIKAN BENAR-BENAR BUKAN MODE EDIT
        #
        # Pengujian baru boleh memakai data nozzle lama
        # sebagai acuan, tetapi tidak boleh membawa ID
        # pengujian lama.
        # =====================================================
        st.session_state.pop(
            "pubbm_edit_pengujian_id",
            None
        )
        
        st.session_state.pop(
            "pubbm_edit_nomor_sertifikat_asli",
            None
        )
        
        # =====================================================
        # HAPUS DRAFT FORM LAMA
        #
        # Draft lama dapat menimpa kembali data pengujian
        # acuan ketika aplikasi berpindah dari Riwayat
        # ke menu Input.
        # =====================================================
        st.session_state.pop(
            "pubbm_draft_widget",
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
                "_uttp_id",
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
            
            "_spbu_id": (
                pengujian.get(
                    "spbu_id"
                )
                or spbu.get(
                    "id"
                )
                or detail.get(
                    "_spbu_id"
                )
            ),
            
            "pemilik": str(
                spbu.get(
                    "nama_spbu",
                    ""
                )
                or detail.get(
                    "pemilik",
                    ""
                )
                or ""
            ).strip(),
            
            "nama_spbu": str(
                spbu.get(
                    "nomor_spbu",
                    ""
                )
                or detail.get(
                    "nama_spbu",
                    ""
                )
                or ""
            ).strip(),
            
            "alamat": str(
                spbu.get(
                    "alamat",
                    ""
                )
                or detail.get(
                    "alamat",
                    ""
                )
                or ""
            ).strip(),
            
            "jenis_lokasi": str(
                spbu.get(
                    "jenis_lokasi",
                    ""
                )
                or detail.get(
                    "jenis_lokasi",
                    ""
                )
                or ""
            ).strip(),
            
            "kecamatan_spbu": str(
                spbu.get(
                    "kecamatan",
                    ""
                )
                or detail.get(
                    "kecamatan_spbu",
                    ""
                )
                or ""
            ).strip(),
            
            "media_bbm_master": str(
                spbu.get(
                    "media_bbm",
                    ""
                )
                or detail.get(
                    "media_bbm_master",
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
            "spbu_id_pubbm",
            "jenis_lokasi_pubbm",
            "kecamatan_spbu_pubbm",
            "media_bbm_master_pubbm",
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
                    "Master SPBU belum tersedia di Supabase. "
                    "Silakan input SPBU secara manual."
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
            spbu_id = st.session_state.get(
                "spbu_id_pubbm"
            )
            
            jenis_lokasi = str(
                st.session_state.get(
                    "jenis_lokasi_pubbm",
                    ""
                )
                or ""
            ).strip()
            
            kecamatan_spbu = str(
                st.session_state.get(
                    "kecamatan_spbu_pubbm",
                    ""
                )
                or ""
            ).strip()
            
            media_bbm_master = str(
                st.session_state.get(
                    "media_bbm_master_pubbm",
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

        df_media = st.session_state.get(
            "data_media_spbu"
        )
        
        media_options = get_media_options(
            nama_spbu=pemilik,
            df_media=df_media,
            jenis_lokasi=jenis_lokasi,
            media_bbm_master=media_bbm_master,
        )
        if media_options:
            st.success(
                "Pilihan media tersedia: "
                + ", ".join(media_options)
            )
        else:
            st.warning(
                "Pilihan media belum tersedia pada "
                "master SPBU maupun master media SPBU."
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
                                "_uttp_id": st.session_state.get(
                                    f"uttp_id_{i}_{idx}"
                                ),
                    
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
            "_uttp_id",
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
        
            # =====================================================
            # IDENTITAS MASTER SPBU
            # =====================================================
            "_spbu_id": spbu_id,
        
            "pemilik": pemilik,
        
            "nama_spbu": nomor_spbu,
        
            "alamat": alamat,
        
            "jenis_lokasi": jenis_lokasi,
        
            "kecamatan_spbu": kecamatan_spbu,
        
            "media_bbm_master": media_bbm_master,
        
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
                        "_uttp_id",
                        "K-Faktor",
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
                                        "_uttp_id",
                                        "K-Faktor",
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
                        # REFRESH MASTER SPBU
                        #
                        # Nomor SPBU / alamat mungkin baru saja diperbarui
                        # pada tabel perusahaan.
                        # =================================================
                        load_data_spbu.clear()
                        
                        st.session_state[
                            "data_spbu"
                        ] = load_data_spbu()
                
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
                            or "pengujian_nomor_sertifikat_header_unique"
                            in pesan_error
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
            # 1. AMBIL MASTER SPBU AKTIF
            # =====================================================
            response_spbu = (
                supabase
                .table("spbu")
                .select(
                    "id, "
                    "nama_spbu, "
                    "nomor_spbu, "
                    "alamat, "
                    "jenis_lokasi, "
                    "kecamatan, "
                    "media_bbm, "
                    "status"
                )
                .eq(
                    "status",
                    "aktif"
                )
                .order(
                    "nama_spbu"
                )
                .execute()
            )
            
            daftar_spbu = (
                response_spbu.data
                or []
            )
            
            if not daftar_spbu:
                st.info(
                    "Belum ada master SPBU "
                    "yang tersimpan di Supabase."
                )
                st.stop()
            
            # =====================================================
            # 2. SUSUN PILIHAN SPBU
            # =====================================================
            opsi_spbu = {}
            
            for spbu in daftar_spbu:
            
                spbu_id = spbu.get(
                    "id"
                )
            
                nama_spbu = str(
                    spbu.get(
                        "nama_spbu",
                        ""
                    )
                    or ""
                ).strip()
            
                nomor_spbu = str(
                    spbu.get(
                        "nomor_spbu",
                        ""
                    )
                    or ""
                ).strip()
            
                if not nama_spbu:
                    continue
            
                # =================================================
                # LABEL DROPDOWN
                # =================================================
                if nomor_spbu:
                    label = (
                        f"{nama_spbu} | "
                        f"{nomor_spbu}"
                    )
                else:
                    label = nama_spbu
            
                # Pengaman apabila label sama
                if label in opsi_spbu:
                    label = (
                        f"{label} | "
                        f"ID {spbu_id}"
                    )
            
                opsi_spbu[
                    label
                ] = spbu
    
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
    
            # =====================================================
            # MASTER SPBU TERPILIH
            # =====================================================
            spbu = opsi_spbu[
                pilihan_spbu
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
            
            # =====================================================
            # FALLBACK DATA LAMA
            # Jika SPBU lama hanya mempunyai satu UTTP
            # =====================================================
            if not uttp_ids:
                uttp_id_lama = alat.get(
                    "id"
                )
            
                if uttp_id_lama is not None:
                    uttp_ids = [
                        uttp_id_lama
                    ]
    
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
                    spbu=spbu,
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
                    gunakan_data_lama_untuk_pengujian_baru_pubbm(
                        spbu=spbu,
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
                        perusahaan=spbu,
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
            
