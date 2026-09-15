import traceback
from datetime import date, datetime
from pathlib import Path
from supabase import create_client
import pandas as pd
import streamlit as st
from modules.tangki_ukur_mobil.cerapan_tangki_ukur_mobil_generator import (
    generate_cerapan_tangki_ukur_mobil_pdf
)
from modules.tangki_ukur_mobil.sertifikat_tangki_ukur_mobil_generator import (
    generate_sertifikat_tangki_ukur_mobil_pdf
)


# =========================================================
# KONFIGURASI
# =========================================================
MODE_INPUT = "📝 Input Data Pengujian"
MODE_PREVIEW = "📄 Preview Data"
MODE_HISTORY = "📚 Riwayat TUM"

OUTPUT_DIR = Path("output/tangki_ukur_mobil")

JENIS_PENGUJIAN_OPTIONS = [
    "Tera",
    "Tera Ulang",
    "Lainnya"
]
LOKASI_OPTIONS = ["Dalam Kantor", "Perusahaan"]

NAMA_KOMPARTEMEN = ["I", "II", "III", "IV"]
# =========================================================
# SUPABASE TANGKI UKUR MOBIL
# =========================================================
def get_supabase_tum():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]

    return create_client(
        url,
        key
    )

# =========================================================
# SIMPAN / UPDATE MASTER PERUSAHAAN TUM
# =========================================================
def simpan_atau_update_perusahaan_tum(
    supabase,
    nama_perusahaan,
    alamat,
):
    """
    Aturan standar SMART METRO:

    1. Perusahaan belum ada
       → INSERT perusahaan baru.

    2. Perusahaan sudah ada dan alamat berubah
       → UPDATE alamat.

    3. Perusahaan sudah ada dan alamat sama
       → gunakan perusahaan_id lama.

    Berlaku untuk:
    - perusahaan dari daftar;
    - perusahaan input manual.
    """

    nama_perusahaan = str(
        nama_perusahaan
        or ""
    ).strip()

    alamat = str(
        alamat
        or ""
    ).strip()

    # =====================================================
    # VALIDASI
    # =====================================================
    if not nama_perusahaan:
        raise ValueError(
            "Nama pemilik / perusahaan belum diisi."
        )

    if not alamat:
        raise ValueError(
            "Alamat pemilik / perusahaan belum diisi."
        )

    # =====================================================
    # CARI PERUSAHAAN BERDASARKAN NAMA
    # =====================================================
    response_cari = (
        supabase
        .table("perusahaan")
        .select(
            "id, nama_perusahaan, alamat"
        )
        .ilike(
            "nama_perusahaan",
            nama_perusahaan
        )
        .limit(1)
        .execute()
    )

    # =====================================================
    # PERUSAHAAN SUDAH ADA
    # =====================================================
    if response_cari.data:

        perusahaan_lama = (
            response_cari.data[0]
        )

        perusahaan_id = (
            perusahaan_lama["id"]
        )

        nama_lama = str(
            perusahaan_lama.get(
                "nama_perusahaan",
                ""
            )
            or ""
        ).strip()

        alamat_lama = str(
            perusahaan_lama.get(
                "alamat",
                ""
            )
            or ""
        ).strip()

        payload_update = {}

        # =================================================
        # NAMA BERUBAH
        # =================================================
        if nama_perusahaan != nama_lama:
            payload_update[
                "nama_perusahaan"
            ] = nama_perusahaan

        # =================================================
        # ALAMAT BERUBAH
        # =================================================
        if alamat != alamat_lama:
            payload_update[
                "alamat"
            ] = alamat

        # =================================================
        # ADA PERUBAHAN → UPDATE
        # =================================================
        if payload_update:

            response_update = (
                supabase
                .table("perusahaan")
                .update(
                    payload_update
                )
                .eq(
                    "id",
                    perusahaan_id
                )
                .execute()
            )

            if not response_update.data:
                raise RuntimeError(
                    "Data perusahaan gagal diperbarui."
                )

        return perusahaan_id

    # =====================================================
    # PERUSAHAAN BARU → INSERT
    # =====================================================
    response_insert = (
        supabase
        .table("perusahaan")
        .insert({
            "nama_perusahaan": (
                nama_perusahaan
            ),
            "alamat": (
                alamat
            ),
        })
        .execute()
    )

    if not response_insert.data:
        raise RuntimeError(
            "Perusahaan baru gagal disimpan "
            "ke Supabase."
        )

    return (
        response_insert
        .data[0]["id"]
    )
# =========================================================
# PECAH TIPE / NOMOR SERI TANGKI
# =========================================================
def pecah_tipe_nomor_seri_tum(
    value
):
    text = str(
        value
        or ""
    ).strip()

    if not text:
        return "", ""

    parts = [
        part.strip()
        for part in text.split("/")
        if part.strip()
    ]

    if len(parts) >= 2:
        tipe = parts[0]

        nomor_seri = " / ".join(
            parts[1:]
        )

        return (
            tipe,
            nomor_seri
        )

    # Jika user tidak memakai tanda "/"
    # simpan teks yang sama agar identitas
    # master tetap tidak kosong.
    return (
        text,
        text
    )


# =========================================================
# CARI / BUAT MASTER TANGKI UKUR MOBIL
# =========================================================
def get_or_create_master_tum(
    supabase,
    perusahaan_id,
    data,
):
    """
    1 Tangki Ukur Mobil = 1 master UTTP.

    Identitas utama:
    perusahaan_id
    + jenis_uttp
    + nomor_seri

    Jika master sudah dikenal dari riwayat/edit,
    prioritaskan _uttp_id.
    """

    jenis_uttp = (
        "Tangki Ukur Mobil"
    )

    merek = str(
        data.get(
            "merek_tangki",
            ""
        )
        or ""
    ).strip()

    tipe_no_seri = str(
        data.get(
            "tipe_no_seri_tangki",
            ""
        )
        or ""
    ).strip()

    (
        tipe,
        nomor_seri
    ) = pecah_tipe_nomor_seri_tum(
        tipe_no_seri
    )

    kapasitas = safe_float(
        data.get(
            "isi_nominal",
            0
        )
    )
    jumlah_kompartemen = int(
        data.get(
            "jumlah_kompartemen",
            1
        )
        or 1
    )
    
    if jumlah_kompartemen < 1:
        jumlah_kompartemen = 1
    
    if jumlah_kompartemen > 4:
        jumlah_kompartemen = 4
    # =====================================================
    # VALIDASI MASTER
    # =====================================================
    if not merek:
        raise ValueError(
            "Merek Tangki belum diisi."
        )

    if not tipe_no_seri:
        raise ValueError(
            "Tipe / Nomor Seri Tangki belum diisi."
        )

    if not nomor_seri:
        raise ValueError(
            "Nomor seri Tangki tidak ditemukan."
        )

    if kapasitas <= 0:
        raise ValueError(
            "Isi nominal Tangki harus lebih besar dari 0."
        )

    # =====================================================
    # PAYLOAD MASTER UTTP
    # =====================================================
    payload_uttp = {
        "perusahaan_id": (
            perusahaan_id
        ),

        "jenis_uttp": (
            jenis_uttp
        ),

        "merk": (
            merek
        ),

        "tipe": (
            tipe
        ),

        "nomor_seri": (
            nomor_seri
        ),

        "kapasitas": (
            kapasitas
        ),

        "satuan_kapasitas": (
            "L"
        ),
        "jumlah_kompartemen": (
            jumlah_kompartemen
        ),

        # Lokasi master alat,
        # bukan lokasi kegiatan pengujian.
        "lokasi": (
            "Perusahaan"
        ),

        "status": (
            "aktif"
        ),
    }

    # =====================================================
    # PRIORITAS MASTER YANG SUDAH DIKENAL
    # Untuk Edit / Pengujian Baru dari Riwayat
    # =====================================================
    uttp_id_lama = (
        data.get(
            "_uttp_id"
        )
    )

    if (
        uttp_id_lama is not None
        and str(
            uttp_id_lama
        ).strip() != ""
    ):
        try:
            uttp_id_lama = int(
                float(
                    uttp_id_lama
                )
            )

        except (
            TypeError,
            ValueError
        ):
            uttp_id_lama = None

    if uttp_id_lama is not None:

        response_update = (
            supabase
            .table("uttp")
            .update(
                payload_uttp
            )
            .eq(
                "id",
                uttp_id_lama
            )
            .eq(
                "perusahaan_id",
                perusahaan_id
            )
            .execute()
        )

        if not response_update.data:
            raise RuntimeError(
                "Master Tangki Ukur Mobil lama "
                "tidak ditemukan atau tidak sesuai "
                "dengan perusahaan."
            )

        return (
            uttp_id_lama,
            False
        )

    # =====================================================
    # CARI MASTER BERDASARKAN IDENTITAS
    # =====================================================
    response_existing = (
        supabase
        .table("uttp")
        .select(
            "id"
        )
        .eq(
            "perusahaan_id",
            perusahaan_id
        )
        .eq(
            "jenis_uttp",
            jenis_uttp
        )
        .eq(
            "nomor_seri",
            nomor_seri
        )
        .limit(1)
        .execute()
    )

    # =====================================================
    # SUDAH ADA → UPDATE MASTER
    # =====================================================
    if response_existing.data:

        uttp_id = (
            response_existing
            .data[0]["id"]
        )

        response_update = (
            supabase
            .table("uttp")
            .update(
                payload_uttp
            )
            .eq(
                "id",
                uttp_id
            )
            .execute()
        )

        if not response_update.data:
            raise RuntimeError(
                "Master Tangki Ukur Mobil "
                "gagal diperbarui."
            )

        return (
            uttp_id,
            False
        )

    # =====================================================
    # BELUM ADA → INSERT MASTER BARU
    # =====================================================
    response_insert = (
        supabase
        .table("uttp")
        .insert(
            payload_uttp
        )
        .execute()
    )

    if not response_insert.data:
        raise RuntimeError(
            "Master Tangki Ukur Mobil "
            "gagal disimpan."
        )

    return (
        response_insert
        .data[0]["id"],
        True
    )
# =========================================================
# SIMPAN / UPDATE PENGUJIAN TUM KE SUPABASE
# =========================================================
def simpan_pengujian_tum_ke_supabase(
    data
):
    """
    DATA BARU
    ---------
    perusahaan      → INSERT / UPDATE
    uttp             → INSERT / UPDATE master TUM
    pengujian        → INSERT
    pengujian_uttp   → INSERT

    EDIT
    ----
    perusahaan      → UPDATE bila berubah
    uttp             → UPDATE master lama
    pengujian        → UPDATE
    pengujian_uttp   → UPDATE
    """

    if not data:
        raise ValueError(
            "Data Tangki Ukur Mobil belum tersedia."
        )

    supabase = get_supabase_tum()

    # =====================================================
    # STATUS EDIT
    # =====================================================
    edit_id = st.session_state.get(
        "tum_edit_pengujian_id"
    )

    if edit_id is None:
        edit_id = data.get(
            "_edit_pengujian_id"
        )

    if edit_id is not None:
        try:
            edit_id = int(
                float(
                    edit_id
                )
            )

        except (
            TypeError,
            ValueError
        ):
            edit_id = None

    sedang_edit = (
        edit_id is not None
    )

    # =====================================================
    # DATA UTAMA
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

    nomor_sertifikat = str(
        data.get(
            "nomor_sertifikat",
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

    jenis_pengujian = str(
        data.get(
            "jenis_pengujian",
            "Tera Ulang"
        )
        or "Tera Ulang"
    ).strip()

    nama_penera_1 = str(
        data.get(
            "nama_penera_1",
            data.get(
                "nama_penera",
                ""
            )
        )
        or ""
    ).strip()

    nama_penera_2 = str(
        data.get(
            "nama_penera_2",
            ""
        )
        or ""
    ).strip()

    # Untuk dokumen TUM yang disimpan/final,
    # default hasil = SAH.
    hasil_akhir = str(
        data.get(
            "hasil_akhir",
            data.get(
                "hasil",
                "SAH"
            )
        )
        or "SAH"
    ).strip()

    data_kompartemen = (
        data.get(
            "data_kompartemen",
            []
        )
        or []
    )

    # =====================================================
    # VALIDASI
    # =====================================================
    if not pemilik:
        raise ValueError(
            "Nama pemilik / perusahaan belum diisi."
        )

    if not alamat:
        raise ValueError(
            "Alamat perusahaan belum diisi."
        )

    if not nomor_sertifikat:
        raise ValueError(
            "Nomor sertifikat belum diisi."
        )

    if not nomor_order:
        raise ValueError(
            "Nomor order belum diisi."
        )

    if not nama_penera_1:
        raise ValueError(
            "Penera 1 belum dipilih."
        )

    if not data_kompartemen:
        raise ValueError(
            "Data kompartemen belum tersedia."
        )

    # =====================================================
    # CEK DUPLIKAT NOMOR SERTIFIKAT
    #
    # Saat Edit:
    # nomor sertifikat milik dirinya sendiri
    # tidak dianggap duplikat.
    # =====================================================
    query_sertifikat = (
        supabase
        .table("pengujian")
        .select("id")
        .eq(
            "nomor_sertifikat",
            nomor_sertifikat
        )
    )

    if sedang_edit:
        query_sertifikat = (
            query_sertifikat
            .neq(
                "id",
                edit_id
            )
        )

    response_sertifikat = (
        query_sertifikat
        .limit(1)
        .execute()
    )

    if response_sertifikat.data:
        raise ValueError(
            "Nomor sertifikat sudah pernah digunakan. "
            "Silakan gunakan nomor sertifikat yang berbeda."
        )

    # =====================================================
    # JIKA EDIT → PASTIKAN DATA LAMA BENAR-BENAR TUM
    # =====================================================
    if sedang_edit:

        response_anchor = (
            supabase
            .table("pengujian")
            .select(
                "id, uttp_id, data_pengujian"
            )
            .eq(
                "id",
                edit_id
            )
            .limit(1)
            .execute()
        )

        if not response_anchor.data:
            raise RuntimeError(
                "Pengujian Tangki Ukur Mobil "
                "yang akan diedit tidak ditemukan."
            )

        anchor = (
            response_anchor.data[0]
        )

        detail_anchor = (
            anchor.get(
                "data_pengujian"
            )
            or {}
        )

        schema_anchor = str(
            detail_anchor.get(
                "schema_tum",
                ""
            )
            or ""
        ).strip()

        if schema_anchor != "1":
            raise RuntimeError(
                "Data yang dipilih bukan pengujian "
                "Tangki Ukur Mobil struktur baru."
            )

    # =====================================================
    # MASTER PERUSAHAAN
    # =====================================================
    perusahaan_id = (
        simpan_atau_update_perusahaan_tum(
            supabase=supabase,
            nama_perusahaan=pemilik,
            alamat=alamat,
        )
    )

    uttp_id = None
    uttp_dibuat_baru = False
    pengujian_id = None

    try:

        # =================================================
        # MASTER TANGKI UKUR MOBIL
        # =================================================
        (
            uttp_id,
            uttp_dibuat_baru
        ) = (
            get_or_create_master_tum(
                supabase=supabase,
                perusahaan_id=perusahaan_id,
                data=data,
            )
        )

        # =================================================
        # TANGGAL
        # =================================================
        tanggal_pengujian = (
            parse_date_value(
                data.get(
                    "tanggal_pengujian"
                )
            )
        )

        tanggal_tanda_tangan = (
            parse_date_value(
                data.get(
                    "tanggal_tanda_tangan"
                ),
                tanggal_pengujian
            )
        )

        masa_berlaku = (
            parse_date_value(
                data.get(
                    "masa_berlaku"
                ),
                tambah_2_tahun(
                    tanggal_pengujian
                )
            )
        )

        # =================================================
        # HEADER / SNAPSHOT PENGUJIAN
        # =================================================
        data_pengujian_header = {
            "schema_tum": 1,

            # =============================================
            # IDENTITAS / KONTEKS TUM
            # =============================================
            "nama_alat": (
                data.get(
                    "nama_alat",
                    "Tangki Ukur Mobil"
                )
            ),

            "jenis_cairan": (
                data.get(
                    "jenis_cairan",
                    ""
                )
            ),

            "nomor_polisi": (
                data.get(
                    "nomor_polisi",
                    ""
                )
            ),

            "merek_kendaraan": (
                data.get(
                    "merek_kendaraan",
                    ""
                )
            ),

            "nomor_chasis_no_mesin": (
                data.get(
                    "nomor_chasis_no_mesin",
                    data.get(
                        "nomor_rangka_no_mesin",
                        ""
                    )
                )
            ),

            # =============================================
            # KEGIATAN
            # =============================================
            "lokasi_pengujian": (
                data.get(
                    "lokasi_pengujian",
                    ""
                )
            ),

            "lokasi_kegiatan": (
                data.get(
                    "lokasi_kegiatan",
                    ""
                )
            ),

            "metode": (
                data.get(
                    "metode",
                    ""
                )
            ),

            "suhu_dasar": (
                safe_float(
                    data.get(
                        "suhu_dasar",
                        0
                    )
                )
            ),

            # =============================================
            # DATA PENERA
            # =============================================
            "nip_penera_1": str(
                data.get(
                    "nip_penera_1",
                    data.get(
                        "nip_penera",
                        ""
                    )
                )
                or ""
            ).strip(),

            "golongan_penera_1": str(
                data.get(
                    "golongan_penera_1",
                    data.get(
                        "golongan_penera",
                        ""
                    )
                )
                or ""
            ).strip(),

            "nip_penera_2": str(
                data.get(
                    "nip_penera_2",
                    ""
                )
                or ""
            ).strip(),

            "golongan_penera_2": str(
                data.get(
                    "golongan_penera_2",
                    ""
                )
                or ""
            ).strip(),
        }

        # =================================================
        # PAYLOAD PENGUJIAN
        # =================================================
        payload_pengujian = {
            "perusahaan_id": (
                perusahaan_id
            ),

            # TUM = 1 pengujian : 1 UTTP
            "uttp_id": (
                uttp_id
            ),

            "tanggal_pengujian": (
                tanggal_pengujian.isoformat()
            ),

            "tanggal_sertifikat": (
                tanggal_tanda_tangan.isoformat()
            ),

            "jenis_pengujian": (
                jenis_pengujian
            ),

            "hasil": (
                hasil_akhir
            ),

            "nomor_order": (
                nomor_order
            ),

            "nomor_sertifikat": (
                nomor_sertifikat
            ),

            "penera_1": (
                nama_penera_1
            ),

            "penera_2": (
                nama_penera_2
                if nama_penera_2
                else None
            ),

            "berlaku_sampai": (
                masa_berlaku.isoformat()
            ),

            "data_pengujian": (
                data_pengujian_header
            ),
        }

        # =================================================
        # DATA DETAIL TEKNIS TUM
        # =================================================
        data_detail = {
            "schema_tum_detail": 1,
        
            "data_kompartemen": (
                data_kompartemen
            ),
        }

        # =================================================
        # RELASI PENGUJIAN - UTTP
        # =================================================
        payload_relasi = {
            "uttp_id": (
                uttp_id
            ),

            "urutan": 1,

            "hasil": (
                hasil_akhir
            ),

            "data_detail": (
                data_detail
            ),

            # Kolom khusus PUBBM
            "no_dispenser": None,
            "posisi": None,
            "media": None,
            "k_faktor": None,
        }

        # =================================================
        # DATA BARU
        # =================================================
        if not sedang_edit:

            response_pengujian = (
                supabase
                .table("pengujian")
                .insert(
                    payload_pengujian
                )
                .execute()
            )

            if not response_pengujian.data:
                raise RuntimeError(
                    "Pengujian Tangki Ukur Mobil "
                    "gagal disimpan."
                )

            pengujian_id = (
                response_pengujian
                .data[0]["id"]
            )

            # =============================================
            # RELASI PENGUJIAN - UTTP
            # =============================================
            response_relasi = (
                supabase
                .table("pengujian_uttp")
                .insert({
                    "pengujian_id": (
                        pengujian_id
                    ),
                    **payload_relasi,
                })
                .execute()
            )

            if not response_relasi.data:
                raise RuntimeError(
                    "Relasi pengujian Tangki Ukur Mobil "
                    "gagal disimpan."
                )

            return {
                "mode": "baru",

                "pengujian": (
                    response_pengujian.data
                ),

                "pengujian_uttp": (
                    response_relasi.data
                ),

                "uttp_id": (
                    uttp_id
                ),

                "perusahaan_id": (
                    perusahaan_id
                ),
            }

        # =================================================
        # MODE EDIT
        # =================================================
        pengujian_id = (
            edit_id
        )

        # =================================================
        # UPDATE HEADER PENGUJIAN
        # =================================================
        response_pengujian = (
            supabase
            .table("pengujian")
            .update(
                payload_pengujian
            )
            .eq(
                "id",
                pengujian_id
            )
            .execute()
        )

        if not response_pengujian.data:
            raise RuntimeError(
                "Pengujian Tangki Ukur Mobil "
                "gagal diperbarui."
            )

        # =================================================
        # AMBIL RELASI LAMA
        # =================================================
        response_relasi_lama = (
            supabase
            .table("pengujian_uttp")
            .select(
                "id, uttp_id"
            )
            .eq(
                "pengujian_id",
                pengujian_id
            )
            .order(
                "id"
            )
            .execute()
        )

        relasi_lama = (
            response_relasi_lama.data
            or []
        )

        # =================================================
        # RELASI SUDAH ADA
        # =================================================
        if relasi_lama:

            relasi_utama = (
                relasi_lama[0]
            )

            response_relasi = (
                supabase
                .table("pengujian_uttp")
                .update(
                    payload_relasi
                )
                .eq(
                    "id",
                    relasi_utama["id"]
                )
                .execute()
            )

            # TUM hanya 1 UTTP per pengujian.
            # Jika ada relasi tambahan tidak sengaja,
            # hapus dan sisakan relasi utama.
            for relasi_tambahan in (
                relasi_lama[1:]
            ):

                (
                    supabase
                    .table("pengujian_uttp")
                    .delete()
                    .eq(
                        "id",
                        relasi_tambahan["id"]
                    )
                    .execute()
                )

        # =================================================
        # RELASI BELUM ADA
        # =================================================
        else:

            response_relasi = (
                supabase
                .table("pengujian_uttp")
                .insert({
                    "pengujian_id": (
                        pengujian_id
                    ),
                    **payload_relasi,
                })
                .execute()
            )

        if not response_relasi.data:
            raise RuntimeError(
                "Relasi pengujian Tangki Ukur Mobil "
                "gagal diperbarui."
            )

        # =================================================
        # SELESAI EDIT
        # =================================================
        return {
            "mode": "edit",

            "pengujian": (
                response_pengujian.data
            ),

            "pengujian_uttp": (
                response_relasi.data
            ),

            "uttp_id": (
                uttp_id
            ),

            "perusahaan_id": (
                perusahaan_id
            ),
        }

    except Exception:

        # =================================================
        # ROLLBACK PENGUJIAN BARU
        # =================================================
        if (
            not sedang_edit
            and pengujian_id is not None
        ):
            try:
                (
                    supabase
                    .table("pengujian")
                    .delete()
                    .eq(
                        "id",
                        pengujian_id
                    )
                    .execute()
                )

            except Exception:
                pass

        # =================================================
        # MASTER TUM BARU YANG GAGAL DIGUNAKAN
        # =================================================
        if (
            uttp_dibuat_baru
            and uttp_id is not None
        ):
            try:
                (
                    supabase
                    .table("uttp")
                    .delete()
                    .eq(
                        "id",
                        uttp_id
                    )
                    .execute()
                )

            except Exception:
                pass

        raise
# =========================================================
# SIMPAN TUM DENGAN PENGAMAN DUPLIKASI
# =========================================================
def pastikan_tum_tersimpan_db(
    data
):
    # =====================================================
    # CEK MODE EDIT
    # =====================================================
    edit_id = (
        st.session_state.get(
            "tum_edit_pengujian_id"
        )
        or data.get(
            "_edit_pengujian_id"
        )
    )

    sedang_edit = (
        edit_id is not None
        and str(
            edit_id
        ).strip() != ""
    )

    # =====================================================
    # MODE EDIT
    #
    # Generate boleh berkali-kali.
    # Setiap Generate = UPDATE ID yang sama.
    # =====================================================
    if sedang_edit:

        hasil_simpan = (
            simpan_pengujian_tum_ke_supabase(
                data
            )
        )

        pengujian_rows = (
            hasil_simpan.get(
                "pengujian",
                []
            )
            or []
        )

        if pengujian_rows:
            st.session_state[
                "tum_last_pengujian_id"
            ] = (
                pengujian_rows[0].get(
                    "id"
                )
            )

        return hasil_simpan

    # =====================================================
    # MODE DATA BARU
    #
    # Sudah pernah INSERT pada form ini
    # → jangan INSERT kedua kali.
    # =====================================================
    if st.session_state.get(
        "tum_sudah_disimpan_db",
        False
    ):
        return {
            "mode": "sudah_tersimpan",

            "pengujian_id": (
                st.session_state.get(
                    "tum_last_pengujian_id"
                )
            ),
        }

    # =====================================================
    # INSERT DATA BARU
    # =====================================================
    hasil_simpan = (
        simpan_pengujian_tum_ke_supabase(
            data
        )
    )

    pengujian_rows = (
        hasil_simpan.get(
            "pengujian",
            []
        )
        or []
    )

    pengujian_id = None

    if pengujian_rows:
        pengujian_id = (
            pengujian_rows[0].get(
                "id"
            )
        )

    st.session_state[
        "tum_sudah_disimpan_db"
    ] = True

    st.session_state[
        "tum_last_pengujian_id"
    ] = pengujian_id

    return hasil_simpan
# =========================================================
# AMBIL RIWAYAT PENGUJIAN TUM
# =========================================================
def ambil_riwayat_tum():
    supabase = get_supabase_tum()

    # =====================================================
    # 1. AMBIL SEMUA PENGUJIAN
    # =====================================================
    response_pengujian = (
        supabase
        .table("pengujian")
        .select("*")
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

    # =====================================================
    # HANYA DATA TUM
    # =====================================================
    daftar_pengujian = []

    for row in semua_pengujian:

        detail = (
            row.get(
                "data_pengujian"
            )
            or {}
        )

        schema_tum = str(
            detail.get(
                "schema_tum",
                ""
            )
            or ""
        ).strip()

        if schema_tum == "1":
            daftar_pengujian.append(
                row
            )

    if not daftar_pengujian:
        return []

    # =====================================================
    # 2. AMBIL RELASI PENGUJIAN - UTTP
    # =====================================================
    daftar_pengujian_id = [
        row["id"]
        for row in daftar_pengujian
        if row.get("id") is not None
    ]

    response_relasi = (
        supabase
        .table("pengujian_uttp")
        .select(
            "id, pengujian_id, uttp_id, "
            "urutan, hasil, data_detail"
        )
        .in_(
            "pengujian_id",
            daftar_pengujian_id
        )
        .execute()
    )

    semua_relasi = (
        response_relasi.data
        or []
    )

    relasi_map = {}

    for relasi in semua_relasi:
        relasi_map[
            relasi.get(
                "pengujian_id"
            )
        ] = relasi

    # =====================================================
    # 3. AMBIL MASTER UTTP
    # =====================================================
    daftar_uttp_id = list({
        row.get("uttp_id")
        for row in semua_relasi
        if row.get("uttp_id") is not None
    })

    uttp_map = {}

    if daftar_uttp_id:

        response_uttp = (
            supabase
            .table("uttp")
            .select(
                "id, perusahaan_id, jenis_uttp, "
                "merk, tipe, nomor_seri, "
                "kapasitas, satuan_kapasitas, "
                "jumlah_kompartemen, "
                "lokasi, status"
            )
            .in_(
                "id",
                daftar_uttp_id
            )
            .execute()
        )

        uttp_map = {
            row["id"]: row
            for row in (
                response_uttp.data
                or []
            )
        }

    # =====================================================
    # 4. AMBIL MASTER PERUSAHAAN
    # =====================================================
    daftar_perusahaan_id = list({
        row.get("perusahaan_id")
        for row in daftar_pengujian
        if row.get("perusahaan_id") is not None
    })

    perusahaan_map = {}

    if daftar_perusahaan_id:

        response_perusahaan = (
            supabase
            .table("perusahaan")
            .select(
                "id, nama_perusahaan, alamat"
            )
            .in_(
                "id",
                daftar_perusahaan_id
            )
            .execute()
        )

        perusahaan_map = {
            row["id"]: row
            for row in (
                response_perusahaan.data
                or []
            )
        }

    # =====================================================
    # 5. BANGUN DATA RIWAYAT
    # =====================================================
    hasil = []

    for header in daftar_pengujian:

        pengujian_id = (
            header.get("id")
        )

        perusahaan = (
            perusahaan_map.get(
                header.get(
                    "perusahaan_id"
                ),
                {}
            )
        )

        relasi = (
            relasi_map.get(
                pengujian_id,
                {}
            )
            or {}
        )

        uttp_id = (
            relasi.get(
                "uttp_id"
            )
            or header.get(
                "uttp_id"
            )
        )

        alat = (
            uttp_map.get(
                uttp_id,
                {}
            )
        )

        data_detail = (
            relasi.get(
                "data_detail"
            )
            or {}
        )

        detail_header = dict(
            header.get(
                "data_pengujian"
            )
            or {}
        )

        # =================================================
        # IDENTITAS INTERNAL
        # =================================================
        detail_header[
            "_uttp_id"
        ] = uttp_id

        # =================================================
        # PERUSAHAAN
        # =================================================
        detail_header[
            "pemilik"
        ] = str(
            perusahaan.get(
                "nama_perusahaan",
                ""
            )
            or ""
        ).strip()

        detail_header[
            "alamat"
        ] = str(
            perusahaan.get(
                "alamat",
                ""
            )
            or ""
        ).strip()

        # =================================================
        # MASTER TANGKI
        # =================================================
        detail_header[
            "merek_tangki"
        ] = str(
            alat.get(
                "merk",
                ""
            )
            or ""
        ).strip()

        tipe = str(
            alat.get(
                "tipe",
                ""
            )
            or ""
        ).strip()

        nomor_seri = str(
            alat.get(
                "nomor_seri",
                ""
            )
            or ""
        ).strip()

        if tipe and nomor_seri:
            tipe_no_seri = (
                f"{tipe} / {nomor_seri}"
            )

        else:
            tipe_no_seri = (
                tipe
                or nomor_seri
            )

        detail_header[
            "tipe_no_seri_tangki"
        ] = tipe_no_seri

        detail_header[
            "isi_nominal"
        ] = (
            alat.get(
                "kapasitas",
                0
            )
        )

        detail_header[
            "satuan_isi_nominal"
        ] = (
            alat.get(
                "satuan_kapasitas",
                "L"
            )
            or "L"
        )

        # Jumlah kompartemen berasal dari MASTER UTTP
        detail_header[
            "jumlah_kompartemen"
        ] = int(
            alat.get(
                "jumlah_kompartemen",
                1
            )
            or 1
        )

        # =================================================
        # DATA TEKNIS PER KEGIATAN
        # =================================================
        detail_header[
            "data_kompartemen"
        ] = (
            data_detail.get(
                "data_kompartemen",
                []
            )
            or []
        )

        # =================================================
        # HEADER PENGUJIAN
        # =================================================
        detail_header[
            "jenis_pengujian"
        ] = header.get(
            "jenis_pengujian",
            ""
        )

        detail_header[
            "tanggal_pengujian"
        ] = header.get(
            "tanggal_pengujian"
        )

        detail_header[
            "tanggal_tanda_tangan"
        ] = header.get(
            "tanggal_sertifikat"
        )

        detail_header[
            "masa_berlaku"
        ] = header.get(
            "berlaku_sampai"
        )

        detail_header[
            "nomor_order"
        ] = header.get(
            "nomor_order",
            ""
        )

        detail_header[
            "nomor_sertifikat"
        ] = header.get(
            "nomor_sertifikat",
            ""
        )

        detail_header[
            "nama_penera_1"
        ] = header.get(
            "penera_1",
            ""
        )

        detail_header[
            "nama_penera_2"
        ] = header.get(
            "penera_2",
            ""
        ) or ""

        detail_header[
            "nama_penera"
        ] = header.get(
            "penera_1",
            ""
        )

        detail_header[
            "hasil"
        ] = header.get(
            "hasil",
            "SAH"
        )

        detail_header[
            "hasil_akhir"
        ] = header.get(
            "hasil",
            "SAH"
        )

        hasil.append({
            "id": (
                pengujian_id
            ),

            "data": (
                detail_header
            ),
        })

    return hasil
# =========================================================
# HELPER TANGGAL
# =========================================================
def bulan_ke_romawi(bulan):
    return [
        "I", "II", "III", "IV", "V", "VI",
        "VII", "VIII", "IX", "X", "XI", "XII"
    ][bulan - 1]


def parse_date_value(value, default_value=None):
    if default_value is None:
        default_value = date.today()

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str) and value.strip():
        try:
            return datetime.strptime(
                value.strip(),
                "%Y-%m-%d"
            ).date()
        except ValueError:
            pass

    return default_value


def format_tanggal_indonesia(value):
    t = parse_date_value(value)

    bulan = [
        "Januari", "Februari", "Maret", "April",
        "Mei", "Juni", "Juli", "Agustus",
        "September", "Oktober", "November", "Desember",
    ]

    return f"{t.day} {bulan[t.month - 1]} {t.year}"


def tambah_2_tahun(tanggal):
    """
    Contoh cerapan TUM yang digunakan sebagai acuan menunjukkan
    jadwal pengujian ulang 2 tahun setelah tanggal pengujian.
    """
    tanggal = parse_date_value(tanggal)

    try:
        return date(
            tanggal.year + 2,
            tanggal.month,
            tanggal.day,
        )
    except ValueError:
        return date(
            tanggal.year + 2,
            tanggal.month,
            28,
        )


def generate_nomor_sertifikat(tanggal):
    t = parse_date_value(tanggal)

    return (
        f"500.2.3.15/0000/BID-K/"
        f"{bulan_ke_romawi(t.month)}/{t.year}"
    )


def generate_nomor_order(tanggal):
    t = parse_date_value(tanggal)

    return (
        f"0000/SCD/"
        f"{bulan_ke_romawi(t.month)}/{t.year}"
    )


# =========================================================
# DATA MASTER
# =========================================================
@st.cache_data
def load_data_perusahaan():
    path = Path("data/data_perusahaan.xlsx")

    if not path.exists():
        return pd.DataFrame(
            columns=[
                "Nama Perusahaan",
                "Alamat",
            ]
        )

    try:
        df = pd.read_excel(
            path,
            engine="openpyxl"
        )

        for col in [
            "Nama Perusahaan",
            "Alamat",
        ]:
            if col not in df.columns:
                df[col] = ""

        df["Nama Perusahaan"] = (
            df["Nama Perusahaan"]
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

        df = df[
            df["Nama Perusahaan"] != ""
        ].copy()

        # Jika ada perusahaan duplikat,
        # pilih alamat yang paling lengkap/panjang.
        df["_panjang"] = df["Alamat"].str.len()

        df = (
            df.sort_values(
                "_panjang",
                ascending=False
            )
            .drop_duplicates(
                "Nama Perusahaan",
                keep="first"
            )
            .drop(
                columns=["_panjang"]
            )
            .sort_values(
                "Nama Perusahaan"
            )
            .reset_index(drop=True)
        )

        return df

    except Exception as exc:
        st.warning(
            f"Data perusahaan tidak dapat dibaca: {exc}"
        )

        return pd.DataFrame(
            columns=[
                "Nama Perusahaan",
                "Alamat",
            ]
        )


@st.cache_data
def load_data_penera():
    path = Path("data/data_penera.xlsx")

    if not path.exists():
        return pd.DataFrame(
            columns=[
                "Nama",
                "NIP",
                "Golongan",
            ]
        )

    try:
        df = pd.read_excel(
            path,
            engine="openpyxl"
        )

        for col in [
            "Nama",
            "NIP",
            "Golongan",
        ]:
            if col not in df.columns:
                df[col] = ""

        df["Nama"] = (
            df["Nama"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        df["Golongan"] = (
            df["Golongan"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        def fmt_nip(value):
            if pd.isna(value):
                return ""

            if (
                isinstance(value, float)
                and value.is_integer()
            ):
                return str(int(value))

            text = str(value).strip()

            if text.endswith(".0"):
                text = text[:-2]

            return text

        df["NIP"] = df["NIP"].apply(
            fmt_nip
        )

        return (
            df[
                df["Nama"] != ""
            ]
            .reset_index(drop=True)
        )

    except Exception as exc:
        st.warning(
            f"Data penera tidak dapat dibaca: {exc}"
        )

        return pd.DataFrame(
            columns=[
                "Nama",
                "NIP",
                "Golongan",
            ]
        )


# =========================================================
# SESSION STATE
# =========================================================
def init_tum_state():
    if "tum_generated_files" not in st.session_state:
        st.session_state.tum_generated_files = {}
    if "tum_saved_data" not in st.session_state:
        st.session_state.tum_saved_data = {}

    saved = st.session_state.tum_saved_data

    tanggal_uji = parse_date_value(
        saved.get(
            "tanggal_pengujian",
            date.today()
        )
    )

    masa_berlaku = parse_date_value(
        saved.get(
            "masa_berlaku",
            tambah_2_tahun(
                tanggal_uji
            )
        ),
        tambah_2_tahun(
            tanggal_uji
        )
    )
    saved_jenis_pengujian = str(
        saved.get(
            "jenis_pengujian",
            "Tera"
        )
    ).strip()

    if saved_jenis_pengujian in [
        "Tera",
        "Tera Ulang"
    ]:
        jenis_pengujian_default = (
            saved_jenis_pengujian
        )
        jenis_pengujian_lainnya_default = ""
    else:
        jenis_pengujian_default = "Lainnya"
        jenis_pengujian_lainnya_default = (
            saved_jenis_pengujian
        )
    defaults = {
        "tum_mode": MODE_INPUT,
        "tum_data_perusahaan": load_data_perusahaan(),
        "tum_data_penera": load_data_penera(),

        "tum_nama_perusahaan": saved.get(
            "pemilik",
            ""
        ),
        "tum_alamat": saved.get(
            "alamat",
            ""
        ),
        "tum_input_manual_perusahaan": False,

        "tum_jenis_cairan": saved.get(
            "jenis_cairan",
            ""
        ),

        "tum_nomor_polisi": saved.get(
            "nomor_polisi",
            ""
        ),
        
        "tum_jenis_pengujian":
            jenis_pengujian_default,

        "tum_jenis_pengujian_lainnya":
            jenis_pengujian_lainnya_default,

        "tum_lokasi_pengujian": saved.get(
            "lokasi_pengujian",
            "Perusahaan"
        ),

        "tum_tanggal_pengujian": tanggal_uji,
        "tum_masa_berlaku": masa_berlaku,

        "tum_metode": saved.get(
            "metode",
            "Penakaran masuk"
        ),

        "tum_suhu_dasar": float(
            saved.get(
                "suhu_dasar",
                28.0
            )
        ),

        "tum_nomor_sertifikat": (
            saved.get(
                "nomor_sertifikat"
            )
            or generate_nomor_sertifikat(
                tanggal_uji
            )
        ),
        
        "tum_nomor_order": (
            saved.get(
                "nomor_order"
            )
            or generate_nomor_order(
                tanggal_uji
            )
        ),

        "tum_penera_1_select": saved.get(
            "nama_penera_1",
            ""
        ),

        "tum_nama_penera_1": saved.get(
            "nama_penera_1",
            ""
        ),

        "tum_nip_penera_1": saved.get(
            "nip_penera_1",
            ""
        ),

        "tum_golongan_penera_1": saved.get(
            "golongan_penera_1",
            ""
        ),

        "tum_penera_2_select": saved.get(
            "nama_penera_2",
            ""
        ),

        "tum_nama_penera_2": saved.get(
            "nama_penera_2",
            ""
        ),

        "tum_nip_penera_2": saved.get(
            "nip_penera_2",
            ""
        ),

        "tum_golongan_penera_2": saved.get(
            "golongan_penera_2",
            ""
        ),
        # =====================================================
        # STATUS DATABASE
        # =====================================================
        "tum_sudah_disimpan_db": False,
        "tum_last_pengujian_id": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_form_tum():
    for key in list(
        st.session_state.keys()
    ):
        if key.startswith("tum_"):
            st.session_state.pop(
                key,
                None
            )


# =========================================================
# CALLBACK
# =========================================================
def update_perusahaan_tum():
    selected = str(
        st.session_state.get(
            "tum_perusahaan_select",
            ""
        )
    ).strip()

    df = st.session_state.get(
        "tum_data_perusahaan"
    )

    if (
        not selected
        or df is None
        or df.empty
    ):
        return

    row = df[
        df[
            "Nama Perusahaan"
        ].astype(str).str.strip()
        == selected
    ]

    if row.empty:
        return

    st.session_state.tum_nama_perusahaan = (
        selected
    )

    st.session_state.tum_alamat = str(
        row.iloc[0].get(
            "Alamat",
            ""
        )
        or ""
    ).strip()

    st.session_state.tum_input_manual_perusahaan = (
        False
    )


def update_penera_tum(
    nomor
):
    select_key = (
        f"tum_penera_{nomor}_select"
    )

    selected = str(
        st.session_state.get(
            select_key,
            ""
        )
    ).strip()

    df = st.session_state.get(
        "tum_data_penera"
    )

    nama_key = (
        f"tum_nama_penera_{nomor}"
    )
    nip_key = (
        f"tum_nip_penera_{nomor}"
    )
    golongan_key = (
        f"tum_golongan_penera_{nomor}"
    )

    if (
        not selected
        or df is None
        or df.empty
    ):
        st.session_state[
            nama_key
        ] = ""

        st.session_state[
            nip_key
        ] = ""

        st.session_state[
            golongan_key
        ] = ""

        return

    row = df[
        df["Nama"]
        .astype(str)
        .str.strip()
        == selected
    ]

    if row.empty:
        return

    data_penera = row.iloc[0]

    st.session_state[
        nama_key
    ] = selected

    st.session_state[
        nip_key
    ] = str(
        data_penera.get(
            "NIP",
            ""
        )
    ).strip()

    st.session_state[
        golongan_key
    ] = str(
        data_penera.get(
            "Golongan",
            ""
        )
    ).strip()


def update_tanggal_tum():
    tanggal = st.session_state.get(
        "tum_tanggal_pengujian",
        date.today()
    )

    st.session_state.tum_masa_berlaku = (
        tambah_2_tahun(
            tanggal
        )
    )

    st.session_state.tum_nomor_sertifikat = (
        generate_nomor_sertifikat(
            tanggal
        )
    )

    st.session_state.tum_nomor_order = (
        generate_nomor_order(
            tanggal
        )
    )


def kembali_ke_input_tum():
    st.session_state.tum_mode = (
        MODE_INPUT
    )


# =========================================================
# VALIDASI
# =========================================================
def validasi_data_tum(
    data
):
    errors = []

    wajib = {
        "pemilik":
            "Nama pemilik/perusahaan belum diisi.",

        "alamat":
            "Alamat belum diisi.",

        "isi_nominal":
            "Isi nominal belum diisi.",

        "merek_tangki":
            "Merek tangki belum diisi.",

        "tipe_no_seri_tangki":
            "Tipe / Nomor Seri Tangki belum diisi.",

        "merek_kendaraan":
            "Merek kendaraan belum diisi.",

        "nomor_chasis_no_mesin":
            "Nomor Chasis / Nomor Mesin belum diisi.",

        "nama_penera_1":
            "Penera 1 belum dipilih.",
    }

    for key, pesan in wajib.items():
        value = data.get(
            key,
            ""
        )

        if not str(value).strip():
            errors.append(
                pesan
            )

    if (
        float(
            data.get(
                "isi_nominal",
                0
            )
            or 0
        )
        <= 0
    ):
        errors.append(
            "Isi nominal harus lebih besar dari 0."
        )

    jumlah_kompartemen = int(
        data.get(
            "jumlah_kompartemen",
            1
        )
    )

    data_kompartemen = data.get(
        "data_kompartemen",
        []
    )

    if (
        len(data_kompartemen)
        < jumlah_kompartemen
    ):
        errors.append(
            "Data kompartemen belum lengkap."
        )

    return errors


# =========================================================
# HELPER DATA TEKNIS
# =========================================================
def get_saved_kompartemen(
    saved,
    index
):
    items = saved.get(
        "data_kompartemen",
        []
    )

    if (
        isinstance(items, list)
        and len(items) > index
        and isinstance(
            items[index],
            dict
        )
    ):
        return items[index]

    return {}


def safe_float(
    value,
    default=0.0
):
    if value is None:
        return float(default)

    if isinstance(
        value,
        (int, float)
    ):
        return float(value)

    text = str(value).strip()

    if not text:
        return float(default)

    # Hilangkan spasi
    text = text.replace(" ", "")

    try:
        # Jika ada titik dan koma sekaligus
        # separator terakhir dianggap desimal.
        #
        # Contoh:
        # 1.234,56 -> 1234.56
        # 1,234.56 -> 1234.56
        if "," in text and "." in text:

            if text.rfind(",") > text.rfind("."):
                # Format Indonesia
                # 1.234,56
                text = (
                    text
                    .replace(".", "")
                    .replace(",", ".")
                )

            else:
                # Format internasional
                # 1,234.56
                text = text.replace(",", "")

        # Hanya koma:
        # 12,5 -> 12.5
        elif "," in text:
            text = text.replace(",", ".")

        return float(text)

    except (
        TypeError,
        ValueError
    ):
        return float(default)


# =========================================================
# NAVIGASI
# =========================================================
def render_navigation():
    col_nav1, col_nav2 = st.columns(2)

    with col_nav1:
        if st.button(
            "← Kembali ke Home",
            use_container_width=True,
            key="tum_nav_home"
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


# =========================================================
# UI PENERA
# =========================================================
def render_penera(
    nomor
):
    df = st.session_state.get(
        "tum_data_penera"
    )

    select_key = (
        f"tum_penera_{nomor}_select"
    )
    nama_key = (
        f"tum_nama_penera_{nomor}"
    )
    nip_key = (
        f"tum_nip_penera_{nomor}"
    )
    golongan_key = (
        f"tum_golongan_penera_{nomor}"
    )

    label = (
        f"Penera {nomor}"
        + (
            ""
            if nomor == 1
            else " (Opsional)"
        )
    )

    if (
        df is not None
        and not df.empty
    ):
        options = (
            df["Nama"]
            .dropna()
            .astype(str)
            .tolist()
        )

        st.selectbox(
            label,
            options=[""] + options,
            key=select_key,
            on_change=update_penera_tum,
            args=(nomor,),
        )

        st.text_input(
            "Nama",
            key=nama_key,
            disabled=True,
        )

        st.text_input(
            "NIP",
            key=nip_key,
            disabled=True,
        )

        st.text_input(
            "Golongan",
            key=golongan_key,
            disabled=True,
        )

    else:
        st.info(
            "Data penera tidak ditemukan. "
            "Silakan input manual."
        )

        st.text_input(
            label,
            key=nama_key,
        )

        st.text_input(
            "NIP",
            key=nip_key,
        )

        st.text_input(
            "Golongan",
            key=golongan_key,
        )


# =========================================================
# UI DATA TEKNIS KOMPARTEMEN
# =========================================================
def render_data_teknis(saved):
    
    st.subheader(
        "📐 Data Teknis Kompartemen"
    )
    # =========================================================
    # KONTROL JUMLAH KOMPARTEMEN
    # =========================================================
    if (
        "tum_jumlah_kompartemen"
        not in st.session_state
    ):
        st.session_state.tum_jumlah_kompartemen = int(
            saved.get(
                "jumlah_kompartemen",
                1
            )
        )

    jumlah_kompartemen = int(
        st.session_state.tum_jumlah_kompartemen
    )

    col_jumlah, col_tambah, col_copy, col_hapus = st.columns(
        [2, 2, 2, 2]
    )

    with col_jumlah:
        st.number_input(
            "Jumlah Kompartemen",
            min_value=1,
            max_value=4,
            value=jumlah_kompartemen,
            disabled=True,
            key="tum_jumlah_kompartemen_display"
        )

    with col_tambah:
        st.write("")

        st.button(
            "➕ Tambah Kompartemen",
            use_container_width=True,
            disabled=jumlah_kompartemen >= 4,
            on_click=tambah_kompartemen_tum,
            key="tum_tambah_kompartemen"
        )

    with col_copy:
        st.write("")

        st.button(
            "📋 Tambah + Copy",
            use_container_width=True,
            disabled=jumlah_kompartemen >= 4,
            on_click=tambah_copy_kompartemen_tum,
            key="tum_tambah_copy_kompartemen"
        )

    with col_hapus:
        st.write("")

        st.button(
            "➖ Hapus Terakhir",
            use_container_width=True,
            disabled=jumlah_kompartemen <= 1,
            on_click=hapus_kompartemen_tum,
            key="tum_hapus_kompartemen"
        )

    st.markdown("---")
    with st.expander(
        "🖼️ Lihat Gambar Pengukuran Tangki Ukur Mobil"
    ):
        gambar_tum = Path(
            "assets/gambar_pengukuran_tum.png"
        )

        if gambar_tum.exists():
            st.image(
                str(gambar_tum),
                use_container_width=True
            )

            st.caption(
                "Referensi posisi pengukuran t1, t2, t3, t4, "
                "T, D, P, Q, dan S."
            )
        else:
            st.info(
                "Gambar pengukuran TUM belum tersedia."
            )
    st.caption(
        "Satuan data teknis t1, t2, t3, t4, T, D, P, Q, dan S adalah mm. "
        "Nilai T dihitung otomatis dari t3 + t4."
    )

    nama_aktif = (
        NAMA_KOMPARTEMEN[
            :jumlah_kompartemen
        ]
    )

    widths = (
        [2.3]
        + [1.5] * jumlah_kompartemen
    )

    header = st.columns(
        widths
    )

    header[0].markdown(
        "**DATA TEKNIS**"
    )

    for i, nama in enumerate(
        nama_aktif
    ):
        header[
            i + 1
        ].markdown(
            f"**{nama}**"
        )

    saved_kompartemen = [
        get_saved_kompartemen(
            saved,
            i
        )
        for i in range(
            jumlah_kompartemen
        )
    ]

    hasil = [
        {
            "kompartemen":
                nama_aktif[i]
        }
        for i in range(
            jumlah_kompartemen
        )
    ]

    def input_row(
        label,
        field,
        step=1.0,
        fmt="%.0f"
    ):
        row = st.columns(
            widths
        )

        row[0].write(
            f"{label} (mm)"
        )

        values = []

        for i in range(
            jumlah_kompartemen
        ):
            default = safe_float(
                saved_kompartemen[
                    i
                ].get(
                    field,
                    0
                )
            )

            with row[
                i + 1
            ]:
                value = st.number_input(
                    f"{label} Kompartemen "
                    f"{nama_aktif[i]}",
                    min_value=0.0,
                    value=float(
                        default
                    ),
                    step=step,
                    format=fmt,
                    key=(
                        f"tum_{field}_"
                        f"{i + 1}"
                    ),
                    label_visibility=(
                        "collapsed"
                    ),
                )

            values.append(
                value
            )

        return values

    t1 = input_row(
        "t1",
        "t1"
    )

    t2 = input_row(
        "t2",
        "t2"
    )

    t3 = input_row(
        "t3",
        "t3"
    )

    t4 = input_row(
        "t4",
        "t4"
    )

    # T = t3 + t4
    t_value = [
        t3[i] + t4[i]
        for i in range(
            jumlah_kompartemen
        )
    ]

    row_t = st.columns(
        widths
    )

    row_t[0].write(
        "**T (mm)**"
    )

    for i in range(
        jumlah_kompartemen
    ):
        with row_t[
            i + 1
        ]:
            st.number_input(
                f"T Kompartemen "
                f"{nama_aktif[i]}",
                value=float(
                    t_value[i]
                ),
                format="%.0f",
                disabled=True,
                key=(
                    f"tum_T_preview_"
                    f"{i + 1}_"
                    f"{t_value[i]:.3f}"
                ),
                label_visibility=(
                    "collapsed"
                ),
            )

    d = input_row(
        "D",
        "D"
    )

    p = input_row(
        "P",
        "P"
    )

    q = input_row(
        "Q",
        "Q"
    )

    s = input_row(
        "S",
        "S"
    )

    st.markdown("---")

    # =====================================================
    # KEPEKAAN
    # =====================================================
    st.markdown(
        "### Kepekaan"
    )

    st.caption(
        "Satuan: mm/L"
    )

    row_k = st.columns(
        widths
    )

    row_k[0].write(
        "Kepekaan"
    )

    kepekaan = []

    for i in range(
        jumlah_kompartemen
    ):
        default = safe_float(
            saved_kompartemen[
                i
            ].get(
                "kepekaan",
                0
            )
        )

        with row_k[
            i + 1
        ]:
            value = st.number_input(
                f"Kepekaan Kompartemen "
                f"{nama_aktif[i]}",
                min_value=0.0,
                value=float(
                    default
                ),
                step=0.001,
                format="%.3f",
                key=(
                    f"tum_kepekaan_"
                    f"{i + 1}"
                ),
                label_visibility=(
                    "collapsed"
                ),
            )

        kepekaan.append(
            value
        )

    st.markdown(
        "### Ruang Kosong"
    )

    st.caption(
        "Satuan: L"
    )

    row_r = st.columns(
        widths
    )

    row_r[0].write(
        "Ruang Kosong"
    )

    ruang_kosong = []

    for i in range(
        jumlah_kompartemen
    ):
        default = safe_float(
            saved_kompartemen[
                i
            ].get(
                "ruang_kosong",
                0
            )
        )

        with row_r[
            i + 1
        ]:
            value = st.number_input(
                f"Ruang Kosong Kompartemen "
                f"{nama_aktif[i]}",
                min_value=0.0,
                value=float(
                    default
                ),
                step=1.0,
                format="%.0f",
                key=(
                    f"tum_ruang_kosong_"
                    f"{i + 1}"
                ),
                label_visibility=(
                    "collapsed"
                ),
            )

        ruang_kosong.append(
            value
        )

    for i in range(
        jumlah_kompartemen
    ):
        hasil[i].update(
            {
                "t1": t1[i],
                "t2": t2[i],
                "t3": t3[i],
                "t4": t4[i],
                "T": t_value[i],
                "D": d[i],
                "P": p[i],
                "Q": q[i],
                "S": s[i],
                "kepekaan":
                    kepekaan[i],
                "ruang_kosong":
                    ruang_kosong[i],
            }
        )

    return hasil, jumlah_kompartemen

# =========================================================
# TAMBAH / COPY KOMPARTEMEN
# =========================================================
def tambah_kompartemen_tum():
    jumlah = int(
        st.session_state.get(
            "tum_jumlah_kompartemen",
            1
        )
    )

    if jumlah < 4:
        st.session_state.tum_jumlah_kompartemen = (
            jumlah + 1
        )


def tambah_copy_kompartemen_tum():
    jumlah = int(
        st.session_state.get(
            "tum_jumlah_kompartemen",
            1
        )
    )

    if jumlah >= 4:
        return

    sumber = jumlah
    tujuan = jumlah + 1

    # Semua field yang dicopy
    fields = [
        "t1",
        "t2",
        "t3",
        "t4",
        "D",
        "P",
        "Q",
        "S",
        "kepekaan",
        "ruang_kosong",
    ]

    for field in fields:
        key_sumber = (
            f"tum_{field}_{sumber}"
        )

        key_tujuan = (
            f"tum_{field}_{tujuan}"
        )

        nilai = st.session_state.get(
            key_sumber,
            0.0
        )

        st.session_state[
            key_tujuan
        ] = nilai

    st.session_state.tum_jumlah_kompartemen = (
        tujuan
    )
def hapus_kompartemen_tum():
    jumlah = int(
        st.session_state.get(
            "tum_jumlah_kompartemen",
            1
        )
    )

    if jumlah <= 1:
        return

    fields = [
        "t1",
        "t2",
        "t3",
        "t4",
        "D",
        "P",
        "Q",
        "S",
        "kepekaan",
        "ruang_kosong",
    ]

    for field in fields:
        st.session_state.pop(
            f"tum_{field}_{jumlah}",
            None
        )

    st.session_state.tum_jumlah_kompartemen = (
        jumlah - 1
    )
# =========================================================
# GUNAKAN RIWAYAT UNTUK EDIT TUM
# =========================================================
def gunakan_data_lama_untuk_edit_tum(
    riwayat
):
    pengujian_id = (
        riwayat.get(
            "id"
        )
    )

    data_riwayat = dict(
        riwayat.get(
            "data",
            {}
        )
        or {}
    )

    if pengujian_id is None:
        raise ValueError(
            "ID pengujian Tangki Ukur Mobil "
            "tidak ditemukan."
        )

    # =====================================================
    # TANDAI SEBAGAI EDIT
    # =====================================================
    data_riwayat[
        "_edit_pengujian_id"
    ] = pengujian_id

    # =====================================================
    # BERSIHKAN STATE TUM LAMA
    # =====================================================
    for key in list(
        st.session_state.keys()
    ):
        if key.startswith(
            "tum_"
        ):
            st.session_state.pop(
                key,
                None
            )

    # =====================================================
    # MASUKKAN DATA RIWAYAT KE FORM
    # =====================================================
    st.session_state[
        "tum_saved_data"
    ] = data_riwayat

    st.session_state[
        "tum_edit_pengujian_id"
    ] = pengujian_id

    st.session_state[
        "tum_sudah_disimpan_db"
    ] = False

    st.session_state[
        "tum_last_pengujian_id"
    ] = None

    st.session_state[
        "tum_generated_files"
    ] = {}

    st.session_state[
        "tum_mode"
    ] = MODE_INPUT


# =========================================================
# GUNAKAN RIWAYAT UNTUK PENGUJIAN BARU TUM
# =========================================================
def gunakan_riwayat_untuk_pengujian_baru_tum(
    riwayat
):
    data_lama = dict(
        riwayat.get(
            "data",
            {}
        )
        or {}
    )

    uttp_id = (
        data_lama.get(
            "_uttp_id"
        )
    )

    if uttp_id is None:
        raise ValueError(
            "Master Tangki Ukur Mobil "
            "pada riwayat tidak ditemukan."
        )

    tanggal_baru = (
        date.today()
    )

    masa_baru = (
        tambah_2_tahun(
            tanggal_baru
        )
    )

    # =====================================================
    # DATA KEGIATAN BARU
    #
    # Identitas tangki tetap.
    # Data teknis pengujian lama TIDAK dibawa.
    # =====================================================
    data_baru = {
        "_edit_pengujian_id": None,

        # Master UTTP lama tetap dipakai
        "_uttp_id": (
            uttp_id
        ),

        # =================================================
        # PERUSAHAAN
        # =================================================
        "pemilik": (
            data_lama.get(
                "pemilik",
                ""
            )
        ),

        "alamat": (
            data_lama.get(
                "alamat",
                ""
            )
        ),

        # =================================================
        # IDENTITAS TANGKI
        # =================================================
        "nama_alat": (
            data_lama.get(
                "nama_alat",
                "Tangki Ukur Mobil"
            )
        ),

        "jenis_cairan": (
            data_lama.get(
                "jenis_cairan",
                ""
            )
        ),

        "isi_nominal": (
            data_lama.get(
                "isi_nominal",
                0
            )
        ),

        "satuan_isi_nominal": "L",

        "merek_tangki": (
            data_lama.get(
                "merek_tangki",
                ""
            )
        ),

        "tipe_no_seri_tangki": (
            data_lama.get(
                "tipe_no_seri_tangki",
                ""
            )
        ),

        # =================================================
        # KENDARAAN
        # =================================================
        "merek_kendaraan": (
            data_lama.get(
                "merek_kendaraan",
                ""
            )
        ),

        "nomor_chasis_no_mesin": (
            data_lama.get(
                "nomor_chasis_no_mesin",
                data_lama.get(
                    "nomor_rangka_no_mesin",
                    ""
                )
            )
        ),

        "nomor_rangka_no_mesin": (
            data_lama.get(
                "nomor_chasis_no_mesin",
                data_lama.get(
                    "nomor_rangka_no_mesin",
                    ""
                )
            )
        ),

        "nomor_polisi": (
            data_lama.get(
                "nomor_polisi",
                ""
            )
        ),

        # =================================================
        # KEGIATAN BARU
        # =================================================
        "jenis_pengujian": (
            "Tera Ulang"
        ),

        "keterangan": (
            "Tera Ulang"
        ),

        "lokasi_pengujian": (
            data_lama.get(
                "lokasi_pengujian",
                "Perusahaan"
            )
        ),

        "tanggal_pengujian": (
            tanggal_baru.isoformat()
        ),

        "tanggal": (
            tanggal_baru.isoformat()
        ),

        "tanggal_penera": (
            format_tanggal_indonesia(
                tanggal_baru
            )
        ),

        "tanggal_tanda_tangan": (
            tanggal_baru.isoformat()
        ),

        "masa_berlaku": (
            masa_baru.isoformat()
        ),

        "masa_berlaku_indonesia": (
            format_tanggal_indonesia(
                masa_baru
            )
        ),

        "metode": (
            data_lama.get(
                "metode",
                "Penakaran masuk"
            )
        ),

        "suhu_dasar": (
            data_lama.get(
                "suhu_dasar",
                28.0
            )
        ),

        "nomor_sertifikat": (
            generate_nomor_sertifikat(
                tanggal_baru
            )
        ),

        "nomor_order": (
            generate_nomor_order(
                tanggal_baru
            )
        ),

        # =================================================
        # PENERA
        # Boleh dipakai sebagai default.
        # =================================================
        "nama_penera_1": (
            data_lama.get(
                "nama_penera_1",
                ""
            )
        ),

        "nip_penera_1": (
            data_lama.get(
                "nip_penera_1",
                ""
            )
        ),

        "golongan_penera_1": (
            data_lama.get(
                "golongan_penera_1",
                ""
            )
        ),

        "nama_penera_2": (
            data_lama.get(
                "nama_penera_2",
                ""
            )
        ),

        "nip_penera_2": (
            data_lama.get(
                "nip_penera_2",
                ""
            )
        ),

        "golongan_penera_2": (
            data_lama.get(
                "golongan_penera_2",
                ""
            )
        ),

        # =================================================
        # JUMLAH KOMPARTEMEN
        # Berasal dari master UTTP.
        # =================================================
        "jumlah_kompartemen": int(
            data_lama.get(
                "jumlah_kompartemen",
                1
            )
            or 1
        ),

        # =================================================
        # PENTING:
        # HASIL TEKNIS LAMA TIDAK DIBAWA
        # =================================================
        "data_kompartemen": [],
    }

    # =====================================================
    # BERSIHKAN STATE
    # =====================================================
    for key in list(
        st.session_state.keys()
    ):
        if key.startswith(
            "tum_"
        ):
            st.session_state.pop(
                key,
                None
            )

    # Ini kegiatan BARU, bukan Edit
    st.session_state.pop(
        "tum_edit_pengujian_id",
        None
    )

    st.session_state[
        "tum_saved_data"
    ] = data_baru

    st.session_state[
        "tum_sudah_disimpan_db"
    ] = False

    st.session_state[
        "tum_last_pengujian_id"
    ] = None

    st.session_state[
        "tum_generated_files"
    ] = {}

    st.session_state[
        "tum_mode"
    ] = MODE_INPUT
# =========================================================
# MAIN APP
# =========================================================
def run():
    init_tum_state()

    st.title(
        "🚛 Pengujian Tangki Ukur Mobil"
    )

    render_navigation()

    st.markdown("---")

    with st.sidebar:
        st.header(
            "📋 Menu Navigasi"
        )

        mode = st.radio(
            "Pilih Mode:",
            [
                MODE_INPUT,
                MODE_PREVIEW
                MODE_HISTORY,
            ],
            key="tum_mode"
        )

    # =====================================================
    # INPUT
    # =====================================================
    if mode == MODE_INPUT:
        st.header(
            "Masukkan Data Pengujian Tangki Ukur Mobil"
        )
        if st.session_state.get(
            "tum_edit_pengujian_id"
        ):
            st.warning(
                "✏️ Anda sedang mengedit pengujian "
                "Tangki Ukur Mobil yang sudah tersimpan."
            )
        saved = (
            st.session_state
            .tum_saved_data
        )

        col1, col2, col3 = (
            st.columns(3)
        )

        # =================================================
        # IDENTITAS PEMILIK
        # =================================================
        with col1:
            st.subheader(
                "Identitas Pemilik"
            )

            df_perusahaan = (
                st.session_state.get(
                    "tum_data_perusahaan"
                )
            )

            if (
                df_perusahaan
                is not None
                and not df_perusahaan.empty
            ):
                options = (
                    df_perusahaan[
                        "Nama Perusahaan"
                    ]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .tolist()
                )

                if (
                    "tum_perusahaan_select"
                    not in st.session_state
                ):
                    nama_lama = str(
                        st.session_state.get(
                            "tum_nama_perusahaan",
                            ""
                        )
                    ).strip()

                    st.session_state[
                        "tum_perusahaan_select"
                    ] = (
                        nama_lama
                        if nama_lama in options
                        else ""
                    )

                    if (
                        nama_lama
                        and nama_lama
                        not in options
                    ):
                        st.session_state[
                            "tum_input_manual_perusahaan"
                        ] = True

                st.selectbox(
                    "Cari & Pilih Nama Perusahaan",
                    options=[""] + options,
                    placeholder=(
                        "Ketik atau pilih perusahaan..."
                    ),
                    key=(
                        "tum_perusahaan_select"
                    ),
                    on_change=(
                        update_perusahaan_tum
                    ),
                )

                st.text_area(
                    "Alamat",
                    height=110,
                    key="tum_alamat"
                )

                st.checkbox(
                    "Input manual nama perusahaan",
                    key=(
                        "tum_input_manual_perusahaan"
                    )
                )

                if st.session_state.get(
                    "tum_input_manual_perusahaan",
                    False
                ):
                    st.text_input(
                        "Nama Pemilik / Perusahaan",
                        key=(
                            "tum_nama_perusahaan"
                        )
                    )

            else:
                st.info(
                    "Data perusahaan tidak ditemukan. "
                    "Silakan input manual."
                )

                st.text_input(
                    "Nama Pemilik / Perusahaan",
                    key=(
                        "tum_nama_perusahaan"
                    )
                )

                st.text_area(
                    "Alamat",
                    height=110,
                    key="tum_alamat"
                )

            pemilik = str(
                st.session_state.get(
                    "tum_nama_perusahaan",
                    ""
                )
            ).strip()

            alamat = str(
                st.session_state.get(
                    "tum_alamat",
                    ""
                )
            ).strip()

        # =================================================
        # DATA TANGKI DAN KENDARAAN
        # =================================================
        with col2:
            st.subheader(
                "Data Tangki & Kendaraan"
            )

            jenis_cairan = st.text_input(
                "Jenis Cairan",
                value=str(
                    saved.get(
                        "jenis_cairan",
                        ""
                    )
                ),
                placeholder="Contoh: BBM atau KIMIA",
                key="tum_jenis_cairan"
            )

            nama_alat = (
                f'Tangki Ukur untuk cairan '
                f'"{jenis_cairan}"'
            )

            st.text_input(
                "Alat Ukur yang Ditera",
                value=nama_alat,
                disabled=True,
                key=(
                    f"tum_nama_alat_preview_"
                    f"{jenis_cairan}"
                ),
            )

            c_nominal, c_satuan = (
                st.columns([3, 1])
            )

            with c_nominal:
                isi_nominal_input = st.text_input(
                    "Isi Nominal",
                    value=str(
                        saved.get(
                            "isi_nominal",
                            ""
                        )
                    ),
                    placeholder="Contoh: 16000",
                    key="tum_isi_nominal"
                )

                isi_nominal = safe_float(
                    isi_nominal_input
                )

            with c_satuan:
                st.text_input(
                    "Satuan",
                    value="L",
                    disabled=True,
                    key=(
                        "tum_satuan_isi_nominal"
                    )
                )

            merek_tangki = st.text_input(
                "Merek Tangki",
                value=str(
                    saved.get(
                        "merek_tangki",
                        ""
                    )
                ),
                key="tum_merek_tangki"
            )

            tipe_no_seri_tangki = st.text_input(
                "Tipe / Nomor Seri Tangki",
                value=str(
                    saved.get(
                        "tipe_no_seri_tangki",
                        ""
                    )
                ),
                placeholder="Contoh: Square / ABC123",
                key="tum_tipe_no_seri_tangki"
            )

            merek_kendaraan = st.text_input(
                "Merek Kendaraan",
                value=str(
                    saved.get(
                        "merek_kendaraan",
                        ""
                    )
                ),
                placeholder="Contoh: HINO / FL8JW1A-BGJ TRONTON (6X2)",
                key="tum_merek_kendaraan"
            )

            nomor_chasis_no_mesin = st.text_input(
                "Nomor Chasis / Nomor Mesin",
                value=str(
                    saved.get(
                        "nomor_chasis_no_mesin",
                        ""
                    )
                ),
                placeholder="Contoh: MJEFL8JW1GJB11778 / J08EUGJ54459",
                key="tum_nomor_chasis_no_mesin"
            )
            nomor_polisi = st.text_input(
                "Nomor Polisi",
                value=str(
                    saved.get(
                        "nomor_polisi",
                        ""
                    )
                ),
                placeholder="Contoh: B 9364 CFU",
                key="tum_nomor_polisi"
            )
        # =================================================
        # DATA PENGUJIAN
        # =================================================
        with col3:
            st.subheader(
                "Data Pengujian"
            )

            jenis_pengujian = (
                st.selectbox(
                    "Jenis Pengujian",
                    options=(
                        JENIS_PENGUJIAN_OPTIONS
                    ),
                    key=(
                        "tum_jenis_pengujian"
                    )
                )
            )

            lokasi_pengujian = (
                st.selectbox(
                    "Lokasi Pengujian",
                    options=(
                        LOKASI_OPTIONS
                    ),
                    key=(
                        "tum_lokasi_pengujian"
                    )
                )
            )

            tanggal_pengujian = (
                st.date_input(
                    "Tanggal Pengujian",
                    key=(
                        "tum_tanggal_pengujian"
                    ),
                    on_change=(
                        update_tanggal_tum
                    )
                )
            )
            tanggal_tanda_tangan = st.date_input(
                "Tanggal Tanda Tangan",
                value=parse_date_value(
                    saved.get(
                        "tanggal_tanda_tangan",
                        tanggal_pengujian
                    )
                ),
                key="tum_tanggal_tanda_tangan"
            )
            masa_berlaku = (
                st.date_input(
                    "Pengujian Ulang / Masa Berlaku",
                    key="tum_masa_berlaku",
                    disabled=True,
                    help=(
                        "Otomatis 2 tahun setelah "
                        "tanggal pengujian mengikuti "
                        "contoh cerapan TUM."
                    ),
                )
            )

            metode = st.selectbox(
                "Metode",
                options=[
                    "Penakaran masuk",
                    "Penakaran keluar",
                ],
                key="tum_metode"
            )

            c_suhu, c_suhu_unit = (
                st.columns([3, 1])
            )

            with c_suhu:
                suhu_dasar = (
                    st.number_input(
                        "Suhu Dasar",
                        value=float(
                            st.session_state.get(
                                "tum_suhu_dasar",
                                28.0
                            )
                        ),
                        step=1.0,
                        format="%.0f",
                        key="tum_suhu_dasar"
                    )
                )

            with c_suhu_unit:
                st.text_input(
                    "Satuan ",
                    value="°C",
                    disabled=True,
                    key="tum_satuan_suhu"
                )

            nomor_sertifikat = (
                st.text_input(
                    "Nomor Sertifikat",
                    key=(
                        "tum_nomor_sertifikat"
                    )
                )
            )

            nomor_order = (
                st.text_input(
                    "Nomor Order",
                    key=(
                        "tum_nomor_order"
                    )
                )
            )

        # =================================================
        # PENERA
        # =================================================
        st.markdown("---")

        st.subheader("👤 Data Penera")

        render_penera(1)

        tambah_penera_2 = st.checkbox(
            "Tambah Penera 2",
            value=bool(
                saved.get(
                    "nama_penera_2",
                    ""
                )
            ),
            key="tum_tambah_penera_2"
        )

        if tambah_penera_2:
            st.markdown("#### Penera 2")
            render_penera(2)

        # =========================================================
        # JUMLAH KOMPARTEMEN
        # =========================================================
        if (
            "tum_jumlah_kompartemen"
            not in st.session_state
        ):
            st.session_state.tum_jumlah_kompartemen = int(
                saved.get(
                    "jumlah_kompartemen",
                    1
                )
            )

        data_kompartemen, jumlah_kompartemen = (
            render_data_teknis(saved)
        )
        # =================================================
        # SIMPAN / RESET
        # =================================================
        col_simpan, col_reset = (
            st.columns(2)
        )

        with col_simpan:
            simpan_btn = st.button(
                "💾 Simpan Data",
                type="primary",
                use_container_width=True,
                key=(
                    "tum_simpan_data"
                )
            )

        with col_reset:
            st.button(
                "🔄 Reset Form",
                use_container_width=True,
                key=(
                    "tum_reset_form"
                ),
                on_click=(
                    reset_form_tum
                ),
            )

        if simpan_btn:
            nama_penera_1 = str(
                st.session_state.get(
                    "tum_nama_penera_1",
                    ""
                )
            ).strip()

            nip_penera_1 = str(
                st.session_state.get(
                    "tum_nip_penera_1",
                    ""
                )
            ).strip()

            golongan_penera_1 = str(
                st.session_state.get(
                    "tum_golongan_penera_1",
                    ""
                )
            ).strip()

            if tambah_penera_2:
                nama_penera_2 = str(
                    st.session_state.get(
                        "tum_nama_penera_2",
                        ""
                    )
                ).strip()

                nip_penera_2 = str(
                    st.session_state.get(
                        "tum_nip_penera_2",
                        ""
                    )
                ).strip()

                golongan_penera_2 = str(
                    st.session_state.get(
                        "tum_golongan_penera_2",
                        ""
                    )
                ).strip()

            else:
                nama_penera_2 = ""
                nip_penera_2 = ""
                golongan_penera_2 = ""

            lokasi_kegiatan = (
                "Dalam Kantor"
                if lokasi_pengujian == "Dalam Kantor"
                else pemilik
            )
            data_tum = {
                # =====================================================
                # ID INTERNAL DATABASE
                # =====================================================
                "_edit_pengujian_id": (
                    st.session_state.get(
                        "tum_edit_pengujian_id"
                    )
                    or saved.get(
                        "_edit_pengujian_id"
                    )
                ),
                
                "_uttp_id": (
                    saved.get(
                        "_uttp_id"
                    )
                ),
                "nama_alat":
                    nama_alat,

                "jenis_cairan":
                    jenis_cairan,

                "isi_nominal":
                    float(
                        isi_nominal
                    ),

                "satuan_isi_nominal":
                    "L",

                "merek_tangki":
                    merek_tangki,

                "tipe_no_seri_tangki":
                    tipe_no_seri_tangki,

                "merek_kendaraan":
                    merek_kendaraan,

                "nomor_chasis_no_mesin":
                    nomor_chasis_no_mesin,
                
                "nomor_polisi":
                    nomor_polisi,
                # Alias untuk generator nanti
                "nomor_rangka_no_mesin":
                    nomor_chasis_no_mesin,

                "pemilik":
                    pemilik,

                "alamat":
                    alamat,

                "jenis_pengujian":
                    jenis_pengujian,

                "keterangan":
                    jenis_pengujian,

                "lokasi_pengujian":
                    lokasi_pengujian,

                "lokasi_kegiatan":
                    lokasi_kegiatan,

                "tanggal_pengujian":
                    tanggal_pengujian.strftime(
                        "%Y-%m-%d"
                    ),
                "tanggal_tanda_tangan":
                    tanggal_tanda_tangan.strftime(
                        "%Y-%m-%d"
                    ),
                "tanggal":
                    tanggal_pengujian.strftime(
                        "%Y-%m-%d"
                    ),

                "tanggal_penera":
                    format_tanggal_indonesia(
                        tanggal_pengujian
                    ),

                "masa_berlaku":
                    masa_berlaku.strftime(
                        "%Y-%m-%d"
                    ),

                "masa_berlaku_indonesia":
                    format_tanggal_indonesia(
                        masa_berlaku
                    ),

                "metode":
                    metode,

                "suhu_dasar":
                    float(
                        suhu_dasar
                    ),

                "metode_suhu":
                    (
                        f"{metode} / "
                        f"{int(suhu_dasar)}°"
                    ),

                "nomor_sertifikat":
                    nomor_sertifikat,

                "nomor_order":
                    nomor_order,

                "nama_penera_1":
                    nama_penera_1,

                "nip_penera_1":
                    nip_penera_1,

                "golongan_penera_1":
                    golongan_penera_1,

                "nama_penera_2":
                    nama_penera_2,

                "nip_penera_2":
                    nip_penera_2,

                "golongan_penera_2":
                    golongan_penera_2,

                # Alias agar generator nantinya
                # mudah memakai pola aplikasi lama.
                "nama_penera":
                    nama_penera_1,

                "nip_penera":
                    nip_penera_1,

                "golongan_penera":
                    golongan_penera_1,

                "jumlah_kompartemen":
                    jumlah_kompartemen,

                "data_kompartemen":
                    data_kompartemen,

            }

            errors = (
                validasi_data_tum(
                    data_tum
                )
            )

            if errors:
                st.error(
                    "Data belum dapat disimpan. "
                    "Periksa bagian berikut:"
                )

                for pesan in errors:
                    st.write(
                        f"- {pesan}"
                    )

                st.stop()

            st.session_state[
                "tum_saved_data"
            ] = data_tum

            # =====================================================
            # DATA FORM BERUBAH / BARU
            # Belum disimpan ke database.
            # =====================================================
            st.session_state[
                "tum_sudah_disimpan_db"
            ] = False
            
            st.session_state[
                "tum_last_pengujian_id"
            ] = None
            
            st.session_state[
                "tum_generated_files"
            ] = {}

            st.success(
                "✅ Data Tangki Ukur Mobil berhasil disimpan."
            )

            st.balloons()

    # =====================================================
    # PREVIEW
    # =====================================================
    elif mode == MODE_PREVIEW:
        st.header(
            "Preview Data Tangki Ukur Mobil"
        )

        data = st.session_state.get(
            "tum_saved_data",
            {}
        )

        if not data:
            st.warning(
                "⚠️ Silakan input dan simpan "
                "data pengujian terlebih dahulu."
            )
            return

        st.button(
            "✏️ Kembali dan Edit Data",
            use_container_width=True,
            key="tum_kembali_edit",
            on_click=kembali_ke_input_tum,
        )

        st.markdown("---")

        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader(
                "🚛 Identitas Tangki"
            )

            st.write(
                f"**Alat Ukur:** "
                f"{data.get('nama_alat', '-')}"
            )

            st.write(
                f"**Isi Nominal:** "
                f"{data.get('isi_nominal', '-')} L"
            )

            st.write(
                f"**Merek Tangki:** "
                f"{data.get('merek_tangki', '-')}"
            )

            st.write(
                f"**Tipe / No. Seri:** "
                f"{data.get('tipe_no_seri_tangki', '-')}"
            )

            st.write(
                f"**Merek / Tipe Kendaraan:** "
                f"{data.get('merek_kendaraan', '-')}"
            )

            st.write(
                f"**Nomor Rangka / No. Mesin:** "
                f"{data.get('nomor_rangka_no_mesin', '-')}"
            )
            
            st.write(
                f"**Nomor Polisi:** "
                f"{data.get('nomor_polisi', '-')}"
            )

            st.write(
                f"**Pemilik:** "
                f"{data.get('pemilik', '-')}"
            )

            st.write(
                f"**Alamat:** "
                f"{data.get('alamat', '-')}"
            )

        with col_b:
            st.subheader(
                "📋 Data Pengujian"
            )

            st.write(
                f"**Jenis Pengujian:** "
                f"{data.get('jenis_pengujian', '-')}"
            )

            st.write(
                f"**Lokasi:** "
                f"{data.get('lokasi_kegiatan', '-')}"
            )

            st.write(
                f"**Tanggal:** "
                f"{data.get('tanggal_penera', '-')}"
            )

            st.write(
                f"**Pengujian Ulang:** "
                f"{data.get('masa_berlaku_indonesia', '-')}"
            )

            st.write(
                f"**Metode / Suhu Dasar:** "
                f"{data.get('metode_suhu', '-')}"
            )

            st.write(
                f"**Penera 1:** "
                f"{data.get('nama_penera_1', '-')}"
            )

            st.write(
                f"**Penera 2:** "
                f"{data.get('nama_penera_2') or '-'}"
            )

            st.write(
                f"**Jumlah Kompartemen:** "
                f"{data.get('jumlah_kompartemen', '-')}"
            )

        st.markdown("---")

        st.subheader(
            "📐 Data Teknis"
        )

        komp_df = pd.DataFrame(
            data.get(
                "data_kompartemen",
                []
            )
        )

        if not komp_df.empty:
            urutan = [
                "kompartemen",
                "t1",
                "t2",
                "t3",
                "t4",
                "T",
                "D",
                "P",
                "Q",
                "S",
                "kepekaan",
                "ruang_kosong",
            ]

            kolom_tersedia = [
                col
                for col in urutan
                if col in komp_df.columns
            ]

            komp_df = komp_df[
                kolom_tersedia
            ]

            st.dataframe(
                komp_df,
                use_container_width=True,
                hide_index=True
            )

        st.info(
            "Tahap berikutnya: generator Cerapan, "
            "Sertifikat, dan form tambahan untuk Tangki Ukur Mobil "
            "akan menggunakan data yang sudah tersimpan di halaman ini."
        )

        st.markdown("---")
        st.subheader("📄 Generate Dokumen")

        col_doc1, col_doc2 = st.columns(2)

        with col_doc1:
            with st.container(border=True):
                st.markdown("### 📝 Cerapan Tangki Ukur Mobil")

                if st.button(
                    "Generate Cerapan",
                    type="primary",
                    use_container_width=True,
                    key="tum_generate_cerapan"
                ):
                    try:
                        OUTPUT_DIR.mkdir(
                            parents=True,
                            exist_ok=True
                        )

                        nama_perusahaan = str(
                            data.get(
                                "pemilik",
                                "TUM"
                            )
                        ).strip()

                        tanggal = str(
                            data.get(
                                "tanggal_pengujian",
                                ""
                            )
                        ).replace("-", "")

                        nama_file_aman = (
                            nama_perusahaan
                            .replace("/", "_")
                            .replace("\\", "_")
                            .replace(" ", "_")
                        )

                        filename = (
                            OUTPUT_DIR
                            / f"Cerapan_TUM_{nama_file_aman}_{tanggal}.pdf"
                        )

                        generate_cerapan_tangki_ukur_mobil_pdf(
                            data,
                            str(filename)
                        )

                        st.session_state.tum_generated_files[
                            "cerapan"
                        ] = str(filename)

                        st.success(
                            "✅ Cerapan Tangki Ukur Mobil berhasil dibuat."
                        )

                    except Exception as exc:
                        st.error(
                            f"❌ Gagal membuat Cerapan: {exc}"
                        )

                        st.code(
                            traceback.format_exc()
                        )


                path_cerapan = (
                    st.session_state
                    .tum_generated_files
                    .get("cerapan")
                )

                if (
                    path_cerapan
                    and Path(path_cerapan).exists()
                ):
                    with open(
                        path_cerapan,
                        "rb"
                    ) as pdf:
                        st.download_button(
                            "⬇️ Download Cerapan",
                            data=pdf.read(),
                            file_name=Path(
                                path_cerapan
                            ).name,
                            mime="application/pdf",
                            use_container_width=True,
                            key="tum_download_cerapan"
                        )
                else:
                    st.caption(
                        "Cerapan belum digenerate."
                    )
        with col_doc2:
            with st.container(border=True):
                st.markdown("### 📜 Sertifikat Tangki Ukur Mobil")

                if st.button(
                    "Generate Sertifikat",
                    type="primary",
                    use_container_width=True,
                    key="tum_generate_sertifikat"
                ):
                    try:
                        OUTPUT_DIR.mkdir(
                            parents=True,
                            exist_ok=True
                        )

                        nama_perusahaan = str(
                            data.get(
                                "pemilik",
                                "TUM"
                            )
                        ).strip()

                        tanggal = str(
                            data.get(
                                "tanggal_pengujian",
                                ""
                            )
                        ).replace("-", "")

                        nama_file_aman = (
                            nama_perusahaan
                            .replace("/", "_")
                            .replace("\\", "_")
                            .replace(" ", "_")
                        )

                        filename = (
                            OUTPUT_DIR
                            / f"Sertifikat_TUM_{nama_file_aman}_{tanggal}.pdf"
                        )

                        generate_sertifikat_tangki_ukur_mobil_pdf(
                            data,
                            str(filename),
                            data.get(
                                "nomor_sertifikat",
                                ""
                            )
                        )
                        
                        st.session_state.tum_generated_files[
                            "sertifikat"
                        ] = str(
                            filename
                        )
                        
                        # =====================================================
                        # SIMPAN PENGUJIAN KE SUPABASE
                        #
                        # Sertifikat dianggap sebagai dokumen final,
                        # sehingga pada tahap ini data pengujian disimpan.
                        # =====================================================
                        hasil_simpan = (
                            pastikan_tum_tersimpan_db(
                                data
                            )
                        )
                        
                        st.success(
                            "✅ Sertifikat Tangki Ukur Mobil berhasil dibuat "
                            "dan pengujian berhasil disimpan."
                        )

                    except Exception as exc:
                        st.error(
                            f"❌ Gagal membuat Sertifikat: {exc}"
                        )

                        st.code(
                            traceback.format_exc()
                        )

                path_sertifikat = (
                    st.session_state
                    .tum_generated_files
                    .get("sertifikat")
                )

                if (
                    path_sertifikat
                    and Path(path_sertifikat).exists()
                ):
                    with open(
                        path_sertifikat,
                        "rb"
                    ) as pdf:
                        st.download_button(
                            "⬇️ Download Sertifikat",
                            data=pdf.read(),
                            file_name=Path(
                                path_sertifikat
                            ).name,
                            mime="application/pdf",
                            use_container_width=True,
                            key="tum_download_sertifikat"
                        )
                else:
                    st.caption(
                        "Sertifikat belum digenerate."
                    )
    
    # =====================================================
    # RIWAYAT TANGKI UKUR MOBIL
    # =====================================================
    elif mode == MODE_HISTORY:
    
        st.header(
            "📚 Riwayat Pengujian Tangki Ukur Mobil"
        )
    
        try:
            daftar_riwayat = (
                ambil_riwayat_tum()
            )
    
            if not daftar_riwayat:
                st.info(
                    "Belum ada riwayat pengujian "
                    "Tangki Ukur Mobil."
                )
                return
    
            opsi_riwayat = {}
    
            for item in daftar_riwayat:
    
                data_riwayat = (
                    item.get(
                        "data",
                        {}
                    )
                    or {}
                )
    
                label = (
                    f"{data_riwayat.get('tanggal_pengujian', '')}"
                    f" | "
                    f"{data_riwayat.get('pemilik', '')}"
                    f" | "
                    f"{data_riwayat.get('nomor_sertifikat', '')}"
                )
    
                opsi_riwayat[
                    label
                ] = item
    
            pilihan = st.selectbox(
                "Pilih Riwayat Pengujian",
                options=[
                    ""
                ] + list(
                    opsi_riwayat.keys()
                ),
                key="tum_riwayat_pilih",
            )
    
            if pilihan:
    
                riwayat = (
                    opsi_riwayat[
                        pilihan
                    ]
                )
    
                data_riwayat = (
                    riwayat.get(
                        "data",
                        {}
                    )
                    or {}
                )
    
                st.subheader(
                    "Detail Pengujian"
                )
    
                col1, col2 = (
                    st.columns(2)
                )
    
                with col1:
                    st.write(
                        "**Pemilik:**",
                        data_riwayat.get(
                            "pemilik",
                            "-"
                        )
                    )
    
                    st.write(
                        "**Merek Tangki:**",
                        data_riwayat.get(
                            "merek_tangki",
                            "-"
                        )
                    )
    
                    st.write(
                        "**Tipe / No. Seri:**",
                        data_riwayat.get(
                            "tipe_no_seri_tangki",
                            "-"
                        )
                    )
    
                    st.write(
                        "**Isi Nominal:**",
                        (
                            f"{data_riwayat.get('isi_nominal', '-')} L"
                        )
                    )
    
                    st.write(
                        "**Jumlah Kompartemen:**",
                        data_riwayat.get(
                            "jumlah_kompartemen",
                            "-"
                        )
                    )
    
                    st.write(
                        "**Nomor Polisi:**",
                        data_riwayat.get(
                            "nomor_polisi",
                            "-"
                        )
                    )
    
                with col2:
                    st.write(
                        "**Tanggal Pengujian:**",
                        data_riwayat.get(
                            "tanggal_pengujian",
                            "-"
                        )
                    )
    
                    st.write(
                        "**Jenis Pengujian:**",
                        data_riwayat.get(
                            "jenis_pengujian",
                            "-"
                        )
                    )
    
                    st.write(
                        "**Nomor Order:**",
                        data_riwayat.get(
                            "nomor_order",
                            "-"
                        )
                    )
    
                    st.write(
                        "**Nomor Sertifikat:**",
                        data_riwayat.get(
                            "nomor_sertifikat",
                            "-"
                        )
                    )
    
                    st.write(
                        "**Penera 1:**",
                        data_riwayat.get(
                            "nama_penera_1",
                            "-"
                        )
                    )
    
                    st.write(
                        "**Penera 2:**",
                        data_riwayat.get(
                            "nama_penera_2",
                            ""
                        )
                        or "-"
                    )
    
                data_kompartemen = (
                    data_riwayat.get(
                        "data_kompartemen",
                        []
                    )
                    or []
                )
    
                if data_kompartemen:
    
                    st.markdown(
                        "### Data Teknis Kompartemen"
                    )
    
                    st.dataframe(
                        pd.DataFrame(
                            data_kompartemen
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )
                st.markdown("---")

                col_edit, col_baru = (
                    st.columns(2)
                )
                
                # =================================================
                # EDIT PENGUJIAN
                # =================================================
                with col_edit:
                
                    if st.button(
                        "✏️ Edit Pengujian",
                        type="primary",
                        use_container_width=True,
                        key=(
                            "tum_edit_riwayat_"
                            f"{riwayat.get('id')}"
                        ),
                    ):
                
                        gunakan_data_lama_untuk_edit_tum(
                            riwayat
                        )
                
                        st.rerun()
                
                
                # =================================================
                # PENGUJIAN BARU
                # =================================================
                with col_baru:
                
                    if st.button(
                        "➕ Pengujian Baru",
                        use_container_width=True,
                        key=(
                            "tum_baru_riwayat_"
                            f"{riwayat.get('id')}"
                        ),
                    ):
                
                        gunakan_riwayat_untuk_pengujian_baru_tum(
                            riwayat
                        )
                
                        st.rerun()
    
        except Exception as exc:
            st.error(
                "Gagal membaca riwayat "
                f"Tangki Ukur Mobil: {exc}"
            )
    
            st.code(
                traceback.format_exc()
            )
    st.markdown(
        """
        <div style='text-align:center; color:#888; font-size:12px;'>
            <p>Aplikasi Pengujian Tangki Ukur Mobil © 2026</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    run()
