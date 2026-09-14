import re
import traceback
from datetime import date
from pathlib import Path
from supabase import create_client

import pandas as pd
import streamlit as st

from modules.uttp.sertifikat_uttp_generator import (
    generate_sertifikat_uttp_pdf,
)


def find_project_root():
    current = Path(__file__).resolve()

    for parent in [current.parent] + list(current.parents):
        if (parent / "modules").exists() or (parent / "app.py").exists():
            return parent

    return current.parent


PROJECT_ROOT = find_project_root()
OUTPUT_DIR = PROJECT_ROOT / "output" / "uttp"
# =========================================================
# SUPABASE UTTP UMUM
# =========================================================
def get_supabase_uttp():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]

    return create_client(
        url,
        key
    )


# =========================================================
# KONVERSI NILAI NUMERIK
# =========================================================
def angka_numeric_uttp(value):
    """
    Mengubah:
    0,005 -> 0.005
    0.005 -> 0.005

    Nilai kosong / "-" -> None
    """

    if value is None:
        return None

    text = str(
        value
    ).strip()

    if (
        not text
        or text == "-"
    ):
        return None

    text = text.replace(
        ",",
        "."
    )

    try:
        return float(
            text
        )

    except (
        TypeError,
        ValueError
    ):
        return None


# =========================================================
# BERLAKU SAMPAI
# =========================================================
def berlaku_sampai_uttp(
    tanggal_pengujian
):
    tanggal_obj = parse_tanggal_uttp(
        tanggal_pengujian
    )

    try:
        tanggal_berlaku = (
            tanggal_obj.replace(
                year=(
                    tanggal_obj.year
                    + 1
                )
            )
        )

    except ValueError:
        # Kasus 29 Februari
        tanggal_berlaku = (
            tanggal_obj.replace(
                year=(
                    tanggal_obj.year
                    + 1
                ),
                month=2,
                day=28,
            )
        )

    return tanggal_berlaku.isoformat()


# =========================================================
# SIMPAN / UPDATE MASTER PERUSAHAAN
# =========================================================
def simpan_atau_update_perusahaan_uttp(
    supabase,
    nama_perusahaan,
    alamat,
):
    nama_perusahaan = str(
        nama_perusahaan
        or ""
    ).strip()

    alamat = str(
        alamat
        or ""
    ).strip()

    if not nama_perusahaan:
        raise ValueError(
            "Nama pemilik / perusahaan belum diisi."
        )

    # =====================================================
    # CARI PERUSAHAAN
    # =====================================================
    response = (
        supabase
        .table(
            "perusahaan"
        )
        .select(
            "id, nama_perusahaan, alamat"
        )
        .eq(
            "nama_perusahaan",
            nama_perusahaan
        )
        .limit(1)
        .execute()
    )

    # =====================================================
    # SUDAH ADA
    # =====================================================
    if response.data:
        perusahaan = (
            response.data[0]
        )

        perusahaan_id = (
            perusahaan["id"]
        )

        alamat_lama = str(
            perusahaan.get(
                "alamat",
                ""
            )
            or ""
        ).strip()

        if (
            alamat
            and alamat != alamat_lama
        ):
            (
                supabase
                .table(
                    "perusahaan"
                )
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
        .table(
            "perusahaan"
        )
        .insert({
            "nama_perusahaan": (
                nama_perusahaan
            ),
            "alamat": alamat,
        })
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Master perusahaan gagal disimpan."
        )

    return response.data[0][
        "id"
    ]


# =========================================================
# CARI / BUAT MASTER UTTP UMUM
# =========================================================
def get_or_create_master_uttp_umum(
    supabase,
    perusahaan_id,
    rincian,
):
    """
    1 rincian UTTP = 1 master UTTP.

    Prioritas identitas:
    perusahaan_id + jenis_uttp + nomor_seri

    Jika sudah ada:
    master diperbarui dan ID lama digunakan kembali.

    Jika belum:
    dibuat master UTTP baru.
    """

    jenis_uttp = str(
        rincian.get(
            "nama_alat",
            ""
        )
        or ""
    ).strip()

    merk = str(
        rincian.get(
            "merek",
            ""
        )
        or ""
    ).strip()

    tipe = str(
        rincian.get(
            "model_tipe",
            ""
        )
        or ""
    ).strip()

    nomor_seri = str(
        rincian.get(
            "nomor_seri",
            ""
        )
        or ""
    ).strip()

    kapasitas = str(
        rincian.get(
            "kapasitas",
            ""
        )
        or ""
    ).strip()

    satuan = str(
        rincian.get(
            "satuan",
            ""
        )
        or ""
    ).strip()

    kelas = str(
        rincian.get(
            "kelas",
            ""
        )
        or ""
    ).strip()

    tanpa_daya_baca = bool(
        rincian.get(
            "tanpa_daya_baca",
            False
        )
    )

    if tanpa_daya_baca:
        daya_baca = None
        satuan_daya_baca = None

    else:
        daya_baca = angka_numeric_uttp(
            rincian.get(
                "daya_baca"
            )
        )

        satuan_daya_baca = (
            satuan
            if satuan
            else None
        )

    # =====================================================
    # VALIDASI IDENTITAS MASTER
    # =====================================================
    if not jenis_uttp:
        raise ValueError(
            "Jenis UTTP belum diisi."
        )

    if not merk:
        raise ValueError(
            "Merek UTTP belum diisi."
        )

    if not nomor_seri:
        raise ValueError(
            "Nomor seri UTTP belum diisi."
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

        "merk": merk,

        "tipe": (
            tipe
            if tipe
            else None
        ),

        "nomor_seri": (
            nomor_seri
        ),

        "kapasitas": (
            kapasitas
            if kapasitas
            else None
        ),

        "satuan_kapasitas": (
            satuan
            if satuan
            else None
        ),

        "daya_baca": (
            daya_baca
        ),

        "satuan_daya_baca": (
            satuan_daya_baca
        ),

        # Belum ada input e pada form.
        "interval_skala_verifikasi": None,

        "kelas": (
            kelas
            if kelas
            else None
        ),

        "status": "aktif",
    }
    # =====================================================
    # PRIORITAS UTTP ID YANG SUDAH DIKENAL
    #
    # Berasal dari Edit atau penggunaan riwayat.
    # =====================================================
    uttp_id_lama = (
        rincian.get(
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
                "Master UTTP lama tidak ditemukan "
                "atau tidak sesuai dengan perusahaan."
            )

        return (
            uttp_id_lama,
            False
        )
    # =====================================================
    # CARI MASTER YANG SUDAH ADA
    # =====================================================
    response_existing = (
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
            .table(
                "uttp"
            )
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
                "Master UTTP lama gagal diperbarui."
            )

        return (
            uttp_id,
            False
        )

    # =====================================================
    # BELUM ADA → BUAT MASTER BARU
    # =====================================================
    response_insert = (
        supabase
        .table(
            "uttp"
        )
        .insert(
            payload_uttp
        )
        .execute()
    )

    if not response_insert.data:
        raise RuntimeError(
            "Master UTTP gagal disimpan."
        )

    return (
        response_insert.data[0]["id"],
        True
    )


# =========================================================
# SIMPAN PENGUJIAN UTTP UMUM
# =========================================================
def simpan_pengujian_uttp_umum_ke_supabase(
    data
):
    """
    Struktur:

    1 sertifikat / kegiatan
        = 1 row pengujian

    1 rincian alat
        = 1 row master uttp

    hubungan kegiatan dengan alat
        = pengujian_uttp
    """

    if not data:
        raise ValueError(
            "Data pengujian UTTP belum tersedia."
        )

    supabase = get_supabase_uttp()
    # =====================================================
    # STATUS EDIT
    # =====================================================
    edit_id = st.session_state.get(
        "uttp_edit_pengujian_id"
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
    # DATA HEADER
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

    lokasi_pengujian = str(
        data.get(
            "lokasi_pengujian",
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

    daftar_rincian = (
        data.get(
            "daftar_rincian_uttp",
            []
        )
        or []
    )

    if not nomor_sertifikat:
        raise ValueError(
            "Nomor sertifikat belum diisi."
        )

    if not nomor_order:
        raise ValueError(
            "Nomor order belum diisi."
        )

    if not daftar_rincian:
        raise ValueError(
            "Daftar rincian UTTP belum tersedia."
        )

    # =====================================================
    # CEK NOMOR SERTIFIKAT
    # Dilakukan sebelum database lain diubah.
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
    # PERUSAHAAN
    # =====================================================
    perusahaan_id = (
        simpan_atau_update_perusahaan_uttp(
            supabase=supabase,
            nama_perusahaan=pemilik,
            alamat=alamat,
        )
    )

    # =====================================================
    # TANGGAL
    # =====================================================
    tanggal_pengujian = (
        parse_tanggal_uttp(
            data.get(
                "tanggal_pengujian"
            )
        )
    )

    tanggal_sertifikat = (
        parse_tanggal_uttp(
            data.get(
                "tanggal_sertifikat"
            )
        )
    )

    # =====================================================
    # DATA HEADER JSON
    # =====================================================
    data_pengujian_header = {
        "schema_uttp_umum": 1,

        "lokasi_pengujian": (
            lokasi_pengujian
        ),

        "alat_standar": (
            data.get(
                "alat_standar",
                []
            )
            or []
        ),

        "nip_penera_1": str(
            data.get(
                "nip_penera_1",
                ""
            )
            or ""
        ).strip(),

        "golongan_penera_1": str(
            data.get(
                "golongan_penera_1",
                ""
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
    # =====================================================
    # MASTER UTTP + RELASI
    # =====================================================
    daftar_relasi = []
    uttp_baru_dibuat = []
    uttp_id_dalam_form = set()

    try:

        # =================================================
        # 1. SIAPKAN MASTER UTTP
        # =================================================
        for urutan, rincian in enumerate(
            daftar_rincian,
            start=1
        ):
            (
                uttp_id,
                dibuat_baru
            ) = (
                get_or_create_master_uttp_umum(
                    supabase=supabase,
                    perusahaan_id=perusahaan_id,
                    rincian=rincian,
                )
            )

            # =============================================
            # PENGAMAN:
            # UTTP YANG SAMA TIDAK BOLEH MUNCUL 2 KALI
            # DALAM SATU KEGIATAN
            # =============================================
            if (
                uttp_id
                in uttp_id_dalam_form
            ):
                raise ValueError(
                    "UTTP yang sama ditemukan "
                    "lebih dari satu kali dalam "
                    "satu pengujian."
                )

            uttp_id_dalam_form.add(
                uttp_id
            )

            if dibuat_baru:
                uttp_baru_dibuat.append(
                    uttp_id
                )

            daftar_relasi.append({
                "uttp_id": (
                    uttp_id
                ),

                "urutan": (
                    urutan
                ),

                "hasil": "SAH",

                "data_detail": {},
            })

        # =================================================
        # 2. PAYLOAD HEADER PENGUJIAN
        # =================================================
        payload_pengujian = {
            "perusahaan_id": (
                perusahaan_id
            ),

            # Relasi alat berada pada pengujian_uttp
            "uttp_id": None,

            "tanggal_pengujian": (
                tanggal_pengujian.isoformat()
            ),

            "tanggal_sertifikat": (
                tanggal_sertifikat.isoformat()
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
                if penera_2
                else None
            ),

            "berlaku_sampai": (
                berlaku_sampai_uttp(
                    tanggal_pengujian
                )
            ),

            "data_pengujian": (
                data_pengujian_header
            ),
        }

        # =================================================
        # 3. DATA BARU
        # =================================================
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
                    "Header pengujian UTTP "
                    "gagal disimpan."
                )

            pengujian_id = (
                response_pengujian
                .data[0]["id"]
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
                    "Relasi pengujian dan UTTP "
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

                "uttp_ids": [
                    item["uttp_id"]
                    for item in daftar_relasi
                ],
            }

        # =================================================
        # 4. MODE EDIT
        # =================================================

        # =================================================
        # PASTIKAN HEADER LAMA ADA
        # =================================================
        response_anchor = (
            supabase
            .table(
                "pengujian"
            )
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
                "Pengujian UTTP yang akan diedit "
                "tidak ditemukan."
            )

        pengujian_anchor = (
            response_anchor.data[0]
        )

        # =================================================
        # PENGAMAN STRUKTUR BARU
        # =================================================
        detail_anchor = (
            pengujian_anchor.get(
                "data_pengujian"
            )
            or {}
        )

        schema_anchor = str(
            detail_anchor.get(
                "schema_uttp_umum",
                ""
            )
            or ""
        ).strip()

        if schema_anchor != "1":
            raise RuntimeError(
                "Data yang dipilih bukan pengujian "
                "UTTP Umum struktur baru."
            )

        if (
            pengujian_anchor.get(
                "uttp_id"
            )
            is not None
        ):
            raise RuntimeError(
                "Pengujian masih menggunakan "
                "struktur lama dan belum dapat diedit."
            )

        pengujian_id = (
            edit_id
        )

        # =================================================
        # 5. UPDATE HEADER PENGUJIAN
        # =================================================
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
                "Header pengujian UTTP "
                "gagal diperbarui."
            )

        # =================================================
        # 6. AMBIL RELASI LAMA
        # =================================================
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

        id_uttp_sekarang = {
            item[
                "uttp_id"
            ]
            for item in daftar_relasi
        }

        hasil_relasi = []

        # =================================================
        # 7. UPDATE / INSERT RELASI
        # =================================================
        for relasi in daftar_relasi:

            uttp_id = relasi[
                "uttp_id"
            ]

            relasi_lama_item = (
                relasi_lama_per_uttp.get(
                    uttp_id
                )
            )

            # =============================================
            # RELASI SUDAH ADA
            # =============================================
            if relasi_lama_item:

                response_relasi_item = (
                    supabase
                    .table(
                        "pengujian_uttp"
                    )
                    .update({
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

                        "data_detail": (
                            relasi[
                                "data_detail"
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

            # =============================================
            # UTTP BARU DITAMBAHKAN SAAT EDIT
            # =============================================
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

        # =================================================
        # 8. HAPUS RELASI UTTP YANG DIHAPUS DARI FORM
        #
        # Master UTTP tidak dihapus.
        # Hanya relasinya terhadap kegiatan ini.
        # =================================================
        for relasi_lama_item in relasi_lama:

            uttp_id_lama = (
                relasi_lama_item.get(
                    "uttp_id"
                )
            )

            if (
                uttp_id_lama
                not in id_uttp_sekarang
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

        # =================================================
        # 9. SELESAI EDIT
        # =================================================
        hasil_simpan = {
            "mode": "edit",

            "pengujian": (
                response_update_header.data
            ),

            "pengujian_uttp": (
                hasil_relasi
            ),

            "uttp_ids": [
                item["uttp_id"]
                for item in daftar_relasi
            ],
        }

        st.session_state.pop(
            "uttp_edit_pengujian_id",
            None
        )

        return hasil_simpan

    except Exception:

        # =================================================
        # ROLLBACK HEADER BARU
        #
        # Hanya untuk mode DATA BARU.
        # Jangan hapus header lama saat Edit.
        # =================================================
        if (
            not sedang_edit
            and "pengujian_id" in locals()
        ):
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

        # =================================================
        # HAPUS UTTP YANG BENAR-BENAR BARU DIBUAT
        #
        # UTTP lama tidak dihapus.
        # =================================================
        for uttp_id_baru in (
            uttp_baru_dibuat
        ):
            try:
                (
                    supabase
                    .table(
                        "uttp"
                    )
                    .delete()
                    .eq(
                        "id",
                        uttp_id_baru
                    )
                    .execute()
                )

            except Exception:
                pass

        raise
# =========================================================
# AMBIL RIWAYAT PENGUJIAN UTTP UMUM
# =========================================================
def ambil_riwayat_uttp_umum():
    supabase = get_supabase_uttp()

    # =====================================================
    # 1. AMBIL HEADER PENGUJIAN
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
    # HANYA PENGUJIAN UTTP UMUM
    # =====================================================
    daftar_pengujian = []

    for row in semua_pengujian:

        detail = (
            row.get(
                "data_pengujian"
            )
            or {}
        )

        schema_uttp_umum = str(
            detail.get(
                "schema_uttp_umum",
                ""
            )
            or ""
        ).strip()

        if schema_uttp_umum == "1":
            daftar_pengujian.append(
                row
            )

    if not daftar_pengujian:
        return []

    # =====================================================
    # 2. AMBIL SELURUH RELASI PENGUJIAN - UTTP
    # =====================================================
    daftar_pengujian_id = [
        row.get("id")
        for row in daftar_pengujian
        if row.get("id") is not None
    ]

    response_relasi = (
        supabase
        .table("pengujian_uttp")
        .select(
            "id, pengujian_id, "
            "uttp_id, urutan, hasil"
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

    relasi_per_pengujian = {}

    for relasi in semua_relasi:

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
    # 3. MASTER UTTP
    # =====================================================
    daftar_uttp_id = list({
        relasi.get("uttp_id")
        for relasi in semua_relasi
        if relasi.get("uttp_id") is not None
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
                "daya_baca, satuan_daya_baca, "
                "interval_skala_verifikasi, "
                "kelas, lokasi, status"
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
    # 4. MASTER PERUSAHAAN
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
    # 5. BANGUN RIWAYAT PER KEGIATAN
    # =====================================================
    hasil = []

    for header in daftar_pengujian:

        pengujian_id = header.get(
            "id"
        )

        perusahaan = perusahaan_map.get(
            header.get(
                "perusahaan_id"
            ),
            {}
        )

        detail_header = dict(
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

        daftar_rincian_uttp = []

        for nomor, relasi in enumerate(
            relasi_kegiatan,
            start=1
        ):

            uttp_id = relasi.get(
                "uttp_id"
            )

            alat = uttp_map.get(
                uttp_id,
                {}
            )

            daya_baca = alat.get(
                "daya_baca"
            )

            tanpa_daya_baca = (
                daya_baca is None
            )

            satuan = str(
                alat.get(
                    "satuan_kapasitas",
                    ""
                )
                or alat.get(
                    "satuan_daya_baca",
                    ""
                )
                or ""
            ).strip()

            daftar_rincian_uttp.append({
                "_uttp_id": uttp_id,

                "no": nomor,

                "nama_alat": str(
                    alat.get(
                        "jenis_uttp",
                        ""
                    )
                    or ""
                ).strip(),

                "merek": str(
                    alat.get(
                        "merk",
                        ""
                    )
                    or ""
                ).strip(),

                "model_tipe": str(
                    alat.get(
                        "tipe",
                        ""
                    )
                    or ""
                ).strip(),

                "nomor_seri": str(
                    alat.get(
                        "nomor_seri",
                        ""
                    )
                    or ""
                ).strip(),

                "kapasitas": str(
                    alat.get(
                        "kapasitas",
                        ""
                    )
                    or ""
                ).strip(),

                "daya_baca": (
                    "-"
                    if tanpa_daya_baca
                    else str(
                        daya_baca
                    )
                ),

                "tanpa_daya_baca": (
                    tanpa_daya_baca
                ),

                "satuan": satuan,

                "kelas": str(
                    alat.get(
                        "kelas",
                        ""
                    )
                    or ""
                ).strip(),

                "nilai_n": None,
            })

        # =================================================
        # GABUNGKAN HEADER + MASTER
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

        detail_header[
            "daftar_rincian_uttp"
        ] = daftar_rincian_uttp

        detail_header[
            "jumlah_alat"
        ] = len(
            daftar_rincian_uttp
        )

        kegiatan = dict(
            header
        )

        kegiatan[
            "data_pengujian"
        ] = detail_header

        hasil.append(
            kegiatan
        )

    return hasil

def bulan_ke_romawi(bulan):
    romawi = [
        "I", "II", "III", "IV", "V", "VI",
        "VII", "VIII", "IX", "X", "XI", "XII",
    ]
    return romawi[bulan - 1]


def generate_nomor_sertifikat(tanggal):
    return (
        f"500.2.3.15/0000/BID-K/"
        f"{bulan_ke_romawi(tanggal.month)}/{tanggal.year}"
    )


def generate_nomor_order(tanggal):
    return (
        f"0000/SCD/"
        f"{bulan_ke_romawi(tanggal.month)}/{tanggal.year}"
    )

def bersihkan_nama_file_uttp(value):
    text = str(value or "").strip()

    text = re.sub(
        r'[\\/:*?"<>|]',
        "",
        text
    )

    text = re.sub(
        r"\s+",
        "_",
        text
    )

    return text.strip("_")


def bulan_singkat_uttp(tanggal):
    bulan = {
        1: "JAN",
        2: "FEB",
        3: "MAR",
        4: "APR",
        5: "MEI",
        6: "JUN",
        7: "JUL",
        8: "AGS",
        9: "SEP",
        10: "OKT",
        11: "NOV",
        12: "DES",
    }

    return bulan.get(
        tanggal.month,
        ""
    )


def format_nama_file_uttp(
    data,
    jenis_dokumen="Sertifikat"
):
    pemilik = bersihkan_nama_file_uttp(
        data.get(
            "pemilik",
            "PEMILIK"
        )
    )

    penera = bersihkan_nama_file_uttp(
        data.get(
            "penera_1",
            "PENERA"
        )
    )

    tanggal = parse_tanggal_uttp(
        data.get(
            "tanggal_pengujian"
        )
    )

    tanggal_text = (
        f"{tanggal.day:02d}_"
        f"{bulan_singkat_uttp(tanggal)}"
    )

    return (
        f"{pemilik}_"
        f"UTTP_"
        f"{jenis_dokumen}_"
        f"{penera}_"
        f"{tanggal_text}.pdf"
    )
def konversi_ke_gram(nilai, satuan):
    try:
        # Mendukung penulisan 0,005 maupun 0.005
        nilai_text = str(nilai).strip().replace(",", ".")
        nilai_angka = float(nilai_text)

    except (TypeError, ValueError):
        return None

    if satuan == "kg":
        return nilai_angka * 1000

    if satuan == "g":
        return nilai_angka

    return None

def tentukan_kelas_timbangan(
    kapasitas,
    daya_baca,
    satuan
):
    max_gram = konversi_ke_gram(
        kapasitas,
        satuan
    )

    e_gram = konversi_ke_gram(
        daya_baca,
        satuan
    )

    if (
        max_gram is None
        or e_gram is None
        or max_gram <= 0
        or e_gram <= 0
    ):
        return "", None

    max_kg = max_gram / 1000
    e_kg = e_gram / 1000

    n = max_kg / e_kg

    # Kelas IIII
    if n < 1000:
        return "IIII", n

    # Kelas III
    if 1000 <= n <= 10000:
        return "III", n

    # Kelas II
    if 10000 < n <= 100000:
        if max_kg > 75:
            return "III", n

        return "II", n

    # Kelas I
    if n > 100000:
        return "I", n

    return "", n

def _read_excel(path):
    if not path.exists():
        return None

    return pd.read_excel(path, engine="openpyxl")


def load_data_penera():
    path = PROJECT_ROOT / "data" / "data_penera.xlsx"

    try:
        df = _read_excel(path)

        if df is None:
            return pd.DataFrame(
                columns=["Nama", "NIP", "Golongan"]
            )

        for column in ["Nama", "NIP", "Golongan"]:
            if column not in df.columns:
                df[column] = ""

        df["Nama"] = df["Nama"].fillna("").astype(str).str.strip()
        df["Golongan"] = (
            df["Golongan"].fillna("").astype(str).str.strip()
        )

        def format_nip(value):
            if pd.isna(value):
                return ""
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            return str(value).strip()

        df["NIP"] = df["NIP"].apply(format_nip)

        return df[df["Nama"] != ""].reset_index(drop=True)

    except Exception as exc:
        st.warning(f"Data penera tidak dapat dibaca: {exc}")
        return pd.DataFrame(
            columns=["Nama", "NIP", "Golongan"]
        )


def load_data_perusahaan():
    path = PROJECT_ROOT / "data" / "data_perusahaan.xlsx"

    try:
        df = _read_excel(path)

        if df is None:
            return pd.DataFrame(
                columns=["Nama Perusahaan", "Alamat"]
            )

        for column in ["Nama Perusahaan", "Alamat"]:
            if column not in df.columns:
                df[column] = ""

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
        df["_panjang_alamat"] = (
            df["Alamat"]
            .str.len()
        )

        df = (
            df.sort_values(
                "_panjang_alamat",
                ascending=False
            )
            .drop_duplicates(
                subset=[
                    "Nama Perusahaan"
                ],
                keep="first"
            )
            .drop(
                columns=[
                    "_panjang_alamat"
                ]
            )
            .sort_values(
                "Nama Perusahaan"
            )
            .reset_index(
                drop=True
            )
        )
        return df[
            df["Nama Perusahaan"] != ""
        ].reset_index(
            drop=True
        )

    except Exception as exc:
        st.warning(f"Data perusahaan tidak dapat dibaca: {exc}")
        return pd.DataFrame(
            columns=["Nama Perusahaan", "Alamat"]
        )
def update_perusahaan_terpilih_uttp():
    selected = str(
        st.session_state.get(
            "uttp_perusahaan_select",
            ""
        )
    ).strip()

    df_perusahaan = st.session_state.get(
        "uttp_data_perusahaan"
    )

    if (
        not selected
        or df_perusahaan is None
        or df_perusahaan.empty
    ):
        return

    row = df_perusahaan[
        df_perusahaan["Nama Perusahaan"]
        .astype(str)
        .str.strip()
        == selected
    ]

    if row.empty:
        return

    data_perusahaan = row.iloc[0]

    alamat = data_perusahaan.get(
        "Alamat",
        ""
    )

    if pd.isna(alamat):
        alamat = ""

    st.session_state[
        "uttp_nama_perusahaan"
    ] = selected

    st.session_state[
        "uttp_alamat_input"
    ] = str(alamat).strip()

    st.session_state[
        "uttp_manual_perusahaan"
    ] = False
def update_nomor_dokumen_uttp():
    tanggal = st.session_state.get(
        "uttp_tanggal_pengujian",
        date.today()
    )

    st.session_state[
        "uttp_nomor_sertifikat"
    ] = generate_nomor_sertifikat(
        tanggal
    )

    st.session_state[
        "uttp_nomor_order"
    ] = generate_nomor_order(
        tanggal
    )
    
def parse_tanggal_uttp(value, default=None):
    if default is None:
        default = date.today()

    if isinstance(value, date):
        return value

    if value:
        try:
            return date.fromisoformat(
                str(value)
            )
        except ValueError:
            pass

    return default
    
def update_penera_1_uttp():
    selected = str(
        st.session_state.get(
            "uttp_penera_1",
            ""
        )
    ).strip()

    df_penera = st.session_state.get(
        "uttp_data_penera"
    )

    if (
        not selected
        or df_penera is None
        or df_penera.empty
    ):
        st.session_state[
            "uttp_nip_penera_1"
        ] = ""

        st.session_state[
            "uttp_golongan_penera_1"
        ] = ""

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

    st.session_state[
        "uttp_nip_penera_1"
    ] = str(
        data_penera.get(
            "NIP",
            ""
        )
    ).strip()

    st.session_state[
        "uttp_golongan_penera_1"
    ] = str(
        data_penera.get(
            "Golongan",
            ""
        )
    ).strip()


def update_penera_2_uttp():
    selected = str(
        st.session_state.get(
            "uttp_penera_2",
            ""
        )
    ).strip()

    df_penera = st.session_state.get(
        "uttp_data_penera"
    )

    if (
        not selected
        or df_penera is None
        or df_penera.empty
    ):
        st.session_state[
            "uttp_nip_penera_2"
        ] = ""

        st.session_state[
            "uttp_golongan_penera_2"
        ] = ""

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

    st.session_state[
        "uttp_nip_penera_2"
    ] = str(
        data_penera.get(
            "NIP",
            ""
        )
    ).strip()

    st.session_state[
        "uttp_golongan_penera_2"
    ] = str(
        data_penera.get(
            "Golongan",
            ""
        )
    ).strip()
def init_uttp_state():
    if "uttp_saved_data" not in st.session_state:
        st.session_state.uttp_saved_data = {}

    saved = st.session_state.uttp_saved_data

    tanggal_pengujian_saved = parse_tanggal_uttp(
        saved.get(
            "tanggal_pengujian"
        )
    )

    tanggal_sertifikat_saved = parse_tanggal_uttp(
        saved.get(
            "tanggal_sertifikat"
        )
    )

    rincian_saved = saved.get(
        "daftar_rincian_uttp",
        []
    )

    if not isinstance(rincian_saved, list):
        rincian_saved = []

    defaults = {
        # =================================================
        # FILE / STATUS DATABASE
        # =================================================
        "uttp_generated_files": {},

        "uttp_sudah_disimpan_db": False,

        "uttp_last_pengujian_id": None,

        # =================================================
        # MASTER DATA
        # =================================================
        "uttp_data_penera": (
            load_data_penera()
        ),

        "uttp_data_perusahaan": (
            load_data_perusahaan()
        ),

        # =================================================
        # PEMILIK
        # =================================================
        "uttp_nama_perusahaan": (
            saved.get(
                "pemilik",
                ""
            )
        ),

        "uttp_alamat_input": (
            saved.get(
                "alamat",
                ""
            )
        ),

        "uttp_manual_perusahaan": False,

        # =================================================
        # NAVIGASI
        # =================================================
        "uttp_mode": (
            "📝 Input Data Pengujian"
        ),

        # =================================================
        # JUMLAH RINCIAN
        # =================================================
        "uttp_jumlah_rincian_alat": max(
            1,
            len(rincian_saved)
        ),

        # =================================================
        # DATA PENGUJIAN
        # =================================================
        "uttp_jenis_pengujian": (
            saved.get(
                "jenis_pengujian",
                "Tera Ulang"
            )
        ),

        "uttp_lokasi_pengujian": (
            saved.get(
                "lokasi_pengujian",
                "Perusahaan"
            )
        ),

        "uttp_tanggal_pengujian": (
            tanggal_pengujian_saved
        ),

        "uttp_tanggal_sertifikat": (
            tanggal_sertifikat_saved
        ),

        "uttp_nomor_sertifikat": (
            saved.get(
                "nomor_sertifikat",
                generate_nomor_sertifikat(
                    tanggal_pengujian_saved
                )
            )
        ),

        "uttp_nomor_order": (
            saved.get(
                "nomor_order",
                generate_nomor_order(
                    tanggal_pengujian_saved
                )
            )
        ),

        # =================================================
        # ALAT STANDAR
        # =================================================
        "uttp_alat_standar": (
            saved.get(
                "alat_standar",
                []
            )
        ),

        # =================================================
        # PENERA
        # =================================================
        "uttp_jumlah_penera": (
            saved.get(
                "jumlah_penera",
                1
            )
        ),

        "uttp_penera_1": (
            saved.get(
                "penera_1",
                ""
            )
        ),

        "uttp_penera_2": (
            saved.get(
                "penera_2",
                ""
            )
        ),

        "uttp_nip_penera_1": (
            saved.get(
                "nip_penera_1",
                ""
            )
        ),

        "uttp_golongan_penera_1": (
            saved.get(
                "golongan_penera_1",
                ""
            )
        ),

        "uttp_nip_penera_2": (
            saved.get(
                "nip_penera_2",
                ""
            )
        ),

        "uttp_golongan_penera_2": (
            saved.get(
                "golongan_penera_2",
                ""
            )
        ),
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_form_uttp():
    for key in list(st.session_state.keys()):
        if key.startswith("uttp_"):
            del st.session_state[key]
def kembali_ke_input_uttp():
    st.session_state[
        "uttp_mode"
    ] = "📝 Input Data Pengujian"
def validasi_data_uttp(
    pemilik,
    alamat,
    daftar_rincian,
    alat_standar,
    penera_1,
    jumlah_penera,
    penera_2,
):
    errors = []

    if not str(
        pemilik
    ).strip():
        errors.append(
            "Nama pemilik/perusahaan belum diisi."
        )

    if not str(
        alamat
    ).strip():
        errors.append(
            "Alamat pemilik/perusahaan belum diisi."
        )

    if not alat_standar:
        errors.append(
            "Pilih minimal satu alat standar."
        )

    if not str(
        penera_1
    ).strip():
        errors.append(
            "Penera 1 belum dipilih."
        )

    if (
        jumlah_penera == 2
        and not str(
            penera_2
        ).strip()
    ):
        errors.append(
            "Penera 2 belum dipilih."
        )

    if not daftar_rincian:
        errors.append(
            "Daftar rincian UTTP belum tersedia."
        )

    for index, item in enumerate(
        daftar_rincian,
        start=1
    ):
        nama_alat = str(
            item.get(
                "nama_alat",
                ""
            )
        ).strip()

        merek = str(
            item.get(
                "merek",
                ""
            )
        ).strip()

        model_tipe = str(
            item.get(
                "model_tipe",
                ""
            )
        ).strip()

        nomor_seri = str(
            item.get(
                "nomor_seri",
                ""
            )
        ).strip()

        kapasitas = str(
            item.get(
                "kapasitas",
                ""
            )
        ).strip()

        daya_baca = str(
            item.get(
                "daya_baca",
                ""
            )
        ).strip()

        kelas = str(
            item.get(
                "kelas",
                ""
            )
        ).strip()

        if not nama_alat:
            errors.append(
                f"Rincian {index}: nama alat belum diisi."
            )

        if not merek:
            errors.append(
                f"Rincian {index}: merek belum diisi."
            )

        if not model_tipe:
            errors.append(
                f"Rincian {index}: model/tipe belum diisi."
            )

        if not nomor_seri:
            errors.append(
                f"Rincian {index}: nomor seri belum diisi."
            )

        if not kapasitas:
            errors.append(
                f"Rincian {index}: kapasitas belum diisi."
            )

        tanpa_daya_baca = bool(
            item.get(
                "tanpa_daya_baca",
                False
            )
        )
        
        if (
            not tanpa_daya_baca
            and not daya_baca
        ):
            errors.append(
                f"Rincian {index}: daya baca belum diisi."
            )

        if not kelas:
            errors.append(
                f"Rincian {index}: kelas timbangan tidak valid."
            )

    return errors
    
# =========================================================
# GUNAKAN RIWAYAT UNTUK EDIT UTTP UMUM
# =========================================================
def gunakan_data_lama_untuk_edit_uttp(
    pengujian
):
    detail = (
        pengujian.get(
            "data_pengujian"
        )
        or {}
    )

    pengujian_id = (
        pengujian.get(
            "id"
        )
    )

    if pengujian_id is None:
        raise ValueError(
            "ID pengujian tidak ditemukan."
        )

    daftar_rincian = (
        detail.get(
            "daftar_rincian_uttp",
            []
        )
        or []
    )

    # =====================================================
    # TENTUKAN JENIS ALAT UTAMA
    # =====================================================
    daftar_jenis = {
        str(
            item.get(
                "nama_alat",
                ""
            )
            or ""
        ).strip()
        for item in daftar_rincian
        if str(
            item.get(
                "nama_alat",
                ""
            )
            or ""
        ).strip()
    }

    if len(daftar_jenis) == 1:
        nama_alat = next(
            iter(
                daftar_jenis
            )
        )

    else:
        nama_alat = "Timbangan"

    data_edit = {
        "_edit_pengujian_id": (
            pengujian_id
        ),

        "pemilik": (
            detail.get(
                "pemilik",
                ""
            )
        ),

        "alamat": (
            detail.get(
                "alamat",
                ""
            )
        ),

        "nama_alat": (
            nama_alat
        ),

        "jumlah_alat": len(
            daftar_rincian
        ),

        "daftar_alat_uttp": [
            {
                "nama_alat": (
                    nama_alat
                ),
                "jumlah": len(
                    daftar_rincian
                ),
                "keterangan": "Terlampir",
            }
        ],

        "daftar_rincian_uttp": (
            daftar_rincian
        ),

        "alat_standar": (
            detail.get(
                "alat_standar",
                []
            )
            or []
        ),

        "jenis_pengujian": (
            pengujian.get(
                "jenis_pengujian",
                "Tera Ulang"
            )
        ),

        "lokasi_pengujian": (
            detail.get(
                "lokasi_pengujian",
                "Perusahaan"
            )
        ),

        "tanggal_pengujian": (
            pengujian.get(
                "tanggal_pengujian"
            )
        ),

        "tanggal_sertifikat": (
            pengujian.get(
                "tanggal_sertifikat"
            )
        ),

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

        "jumlah_penera": (
            2
            if str(
                pengujian.get(
                    "penera_2",
                    ""
                )
                or ""
            ).strip()
            else 1
        ),

        "penera_1": (
            pengujian.get(
                "penera_1",
                ""
            )
        ),

        "nip_penera_1": (
            detail.get(
                "nip_penera_1",
                ""
            )
        ),

        "golongan_penera_1": (
            detail.get(
                "golongan_penera_1",
                ""
            )
        ),

        "penera_2": (
            pengujian.get(
                "penera_2",
                ""
            )
            or ""
        ),

        "nip_penera_2": (
            detail.get(
                "nip_penera_2",
                ""
            )
        ),

        "golongan_penera_2": (
            detail.get(
                "golongan_penera_2",
                ""
            )
        ),
    }

    # =====================================================
    # HAPUS STATE FORM LAMA
    # =====================================================
    for key in list(
        st.session_state.keys()
    ):
        if key.startswith(
            "uttp_"
        ):
            st.session_state.pop(
                key,
                None
            )

    # =====================================================
    # AKTIFKAN DATA EDIT
    # =====================================================
    st.session_state[
        "uttp_saved_data"
    ] = data_edit

    st.session_state[
        "uttp_edit_pengujian_id"
    ] = pengujian_id

    # Pengujian lama akan diedit,
    # jadi hasil Generate sebelumnya tidak berlaku.
    st.session_state[
        "uttp_sudah_disimpan_db"
    ] = False

    st.session_state[
        "uttp_last_pengujian_id"
    ] = None

    st.session_state[
        "uttp_generated_files"
    ] = {}

    st.session_state[
        "uttp_mode"
    ] = "📝 Input Data Pengujian"
# =========================================================
# GUNAKAN RIWAYAT UNTUK PENGUJIAN BARU
# =========================================================
def gunakan_riwayat_untuk_pengujian_baru_uttp(
    pengujian
):
    detail = (
        pengujian.get(
            "data_pengujian"
        )
        or {}
    )

    daftar_rincian = (
        detail.get(
            "daftar_rincian_uttp",
            []
        )
        or []
    )

    if not daftar_rincian:
        raise ValueError(
            "Riwayat tidak memiliki rincian UTTP."
        )

    # =====================================================
    # TENTUKAN JENIS ALAT UTAMA
    # =====================================================
    daftar_jenis = {
        str(
            item.get(
                "nama_alat",
                ""
            )
            or ""
        ).strip()
        for item in daftar_rincian
        if str(
            item.get(
                "nama_alat",
                ""
            )
            or ""
        ).strip()
    }

    if len(daftar_jenis) == 1:
        nama_alat = next(
            iter(
                daftar_jenis
            )
        )
    else:
        nama_alat = "Timbangan"

    # =====================================================
    # TANGGAL PENGUJIAN BARU
    # =====================================================
    tanggal_baru = date.today()

    # =====================================================
    # COPY RINCIAN
    #
    # _uttp_id TETAP DIPERTAHANKAN
    # supaya menggunakan master alat yang sama.
    # =====================================================
    rincian_baru = []

    for nomor, item in enumerate(
        daftar_rincian,
        start=1
    ):
        item_baru = dict(
            item
        )

        item_baru[
            "no"
        ] = nomor

        rincian_baru.append(
            item_baru
        )

    # =====================================================
    # DATA BARU
    # =====================================================
    data_baru = {
        # PENTING:
        # Tidak ada _edit_pengujian_id.
        # Ini kegiatan baru.
        "_edit_pengujian_id": None,

        "pemilik": (
            detail.get(
                "pemilik",
                ""
            )
        ),

        "alamat": (
            detail.get(
                "alamat",
                ""
            )
        ),

        "nama_alat": (
            nama_alat
        ),

        "jumlah_alat": len(
            rincian_baru
        ),

        "daftar_alat_uttp": [
            {
                "nama_alat": (
                    nama_alat
                ),
                "jumlah": len(
                    rincian_baru
                ),
                "keterangan": "Terlampir",
            }
        ],

        "daftar_rincian_uttp": (
            rincian_baru
        ),

        "alat_standar": (
            detail.get(
                "alat_standar",
                []
            )
            or []
        ),

        # Pengujian berikutnya umumnya Tera Ulang.
        "jenis_pengujian": "Tera Ulang",

        "lokasi_pengujian": (
            detail.get(
                "lokasi_pengujian",
                "Perusahaan"
            )
        ),

        "tanggal_pengujian": (
            tanggal_baru.isoformat()
        ),

        "tanggal_sertifikat": (
            tanggal_baru.isoformat()
        ),

        # Nomor dibuat baru.
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

        # Penera boleh memakai data sebelumnya,
        # nanti tetap dapat diubah di form.
        "jumlah_penera": (
            2
            if str(
                pengujian.get(
                    "penera_2",
                    ""
                )
                or ""
            ).strip()
            else 1
        ),

        "penera_1": (
            pengujian.get(
                "penera_1",
                ""
            )
        ),

        "nip_penera_1": (
            detail.get(
                "nip_penera_1",
                ""
            )
        ),

        "golongan_penera_1": (
            detail.get(
                "golongan_penera_1",
                ""
            )
        ),

        "penera_2": (
            pengujian.get(
                "penera_2",
                ""
            )
            or ""
        ),

        "nip_penera_2": (
            detail.get(
                "nip_penera_2",
                ""
            )
        ),

        "golongan_penera_2": (
            detail.get(
                "golongan_penera_2",
                ""
            )
        ),
    }

    # =====================================================
    # BERSIHKAN STATE FORM
    # =====================================================
    for key in list(
        st.session_state.keys()
    ):
        if key.startswith(
            "uttp_"
        ):
            st.session_state.pop(
                key,
                None
            )

    # =====================================================
    # PASTIKAN BUKAN MODE EDIT
    # =====================================================
    st.session_state.pop(
        "uttp_edit_pengujian_id",
        None
    )

    st.session_state[
        "uttp_saved_data"
    ] = data_baru

    st.session_state[
        "uttp_sudah_disimpan_db"
    ] = False

    st.session_state[
        "uttp_last_pengujian_id"
    ] = None

    st.session_state[
        "uttp_generated_files"
    ] = {}

    st.session_state[
        "uttp_mode"
    ] = "📝 Input Data Pengujian"
def run():
    init_uttp_state()

    st.title("📋 Aplikasi Automasi Sertifikat Tera UTTP")

    col_nav1, col_nav2 = st.columns(2)

    with col_nav1:
        if st.button(
            "← Kembali ke Home",
            use_container_width=True,
            key="uttp_nav_home",
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

    st.markdown("---")

    with st.sidebar:
        mode = st.radio(
            "Menu",
            [
                "📝 Input Data Pengujian",
                "📄 Preview & Generate Data",
                "📚 Riwayat UTTP",
            ],
            key="uttp_mode",
        )

    if mode == "📝 Input Data Pengujian":
        st.header("Masukkan Data Pengujian UTTP")

        if st.session_state.get(
            "uttp_edit_pengujian_id"
        ):
            st.warning(
                "✏️ Anda sedang mengedit pengujian "
                "yang sudah tersimpan."
            )

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Identitas Pemilik")

            df_perusahaan = st.session_state.get(
                "uttp_data_perusahaan"
            )

            if (
                df_perusahaan is not None
                and not df_perusahaan.empty
            ):
                daftar_perusahaan = (
                    df_perusahaan["Nama Perusahaan"]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .tolist()
                )

                nama_tersimpan = str(
                    st.session_state.get(
                        "uttp_nama_perusahaan",
                        ""
                    )
                ).strip()

                if (
                    "uttp_perusahaan_select"
                    not in st.session_state
                ):
                    if nama_tersimpan in daftar_perusahaan:
                        st.session_state[
                            "uttp_perusahaan_select"
                        ] = nama_tersimpan
                    else:
                        st.session_state[
                            "uttp_perusahaan_select"
                        ] = ""

                        if nama_tersimpan:
                            st.session_state[
                                "uttp_manual_perusahaan"
                            ] = True

                st.selectbox(
                    "Cari & Pilih Nama Perusahaan",
                    options=[""] + daftar_perusahaan,
                    placeholder="Ketik atau pilih perusahaan...",
                    key="uttp_perusahaan_select",
                    on_change=update_perusahaan_terpilih_uttp,
                )

                st.text_area(
                    "Alamat",
                    height=90,
                    key="uttp_alamat_input",
                    help=(
                        "Alamat otomatis muncul setelah perusahaan "
                        "dipilih dan tetap dapat diedit."
                    ),
                )

                st.checkbox(
                    "Input manual nama perusahaan",
                    key="uttp_manual_perusahaan",
                )

                if st.session_state.uttp_manual_perusahaan:
                    st.text_input(
                        "Nama Pemilik / Perusahaan",
                        key="uttp_nama_perusahaan",
                    )

            else:
                st.info(
                    "Data perusahaan tidak ditemukan. "
                    "Silakan input manual."
                )

                st.text_input(
                    "Nama Pemilik / Perusahaan",
                    key="uttp_nama_perusahaan",
                )

                st.text_area(
                    "Alamat",
                    height=90,
                    key="uttp_alamat_input",
                )

            pemilik = str(
                st.session_state.get(
                    "uttp_nama_perusahaan",
                    ""
                )
            ).strip()

            alamat = str(
                st.session_state.get(
                    "uttp_alamat_input",
                    ""
                )
            ).strip()

        with col2:
            st.subheader("Data Sertifikat")

            jenis_pengujian = st.selectbox(
                "Jenis Pengujian",
                options=[
                    "Tera",
                    "Tera Ulang"
                ],
                key="uttp_jenis_pengujian",
            )
            lokasi_options = [
                "Dalam Kantor",
                "Perusahaan",
            ]

            if (
                st.session_state.get(
                    "uttp_lokasi_pengujian"
                )
                not in lokasi_options
            ):
                st.session_state[
                    "uttp_lokasi_pengujian"
                ] = "Perusahaan"

            lokasi_pengujian = st.selectbox(
                "Lokasi Pengujian",
                options=lokasi_options,
                key="uttp_lokasi_pengujian",
            )
            tanggal_pengujian = st.date_input(
                "Tanggal Pengujian",
                key="uttp_tanggal_pengujian",
                on_change=update_nomor_dokumen_uttp,
            )

            tanggal_sertifikat = st.date_input(
                "Tanggal Sertifikat",
                key="uttp_tanggal_sertifikat",
            )

            nomor_sertifikat = st.text_input(
                "Nomor Sertifikat",
                key="uttp_nomor_sertifikat",
            )

            nomor_order = st.text_input(
                "Nomor Order",
                key="uttp_nomor_order",
            )

        st.markdown("---")
        st.subheader("⚖️ Data Alat UTTP")

        opsi_nama_alat = [
            "Timbangan Elektronik",
            "Timbangan Mekanik",
            "Timbangan",
        ]

        daftar_tersimpan = (
            st.session_state.uttp_saved_data.get(
                "daftar_alat_uttp",
                []
            )
        )

        data_alat_tersimpan = (
            daftar_tersimpan[0]
            if isinstance(daftar_tersimpan, list)
            and daftar_tersimpan
            and isinstance(daftar_tersimpan[0], dict)
            else {}
        )

        nama_alat_tersimpan = str(
            data_alat_tersimpan.get(
                "nama_alat",
                opsi_nama_alat[0],
            )
        )

        if nama_alat_tersimpan not in opsi_nama_alat:
            nama_alat_tersimpan = opsi_nama_alat[0]

        with st.container(border=True):
            col_alat, col_jumlah = st.columns([3, 1])

            with col_alat:
                nama_alat = st.selectbox(
                    "Nama Alat",
                    options=opsi_nama_alat,
                    index=opsi_nama_alat.index(
                        nama_alat_tersimpan
                    ),
                    key="uttp_nama_alat",
                )

            with col_jumlah:
                jumlah_alat = int(
                    st.session_state.get(
                        "uttp_jumlah_rincian_alat",
                        1
                    )
                )

                st.text_input(
                    "Jumlah Unit",
                    value=str(jumlah_alat),
                    disabled=True,
                    key="uttp_jumlah_alat_tampil",
                )

        daftar_alat_uttp = [
            {
                "nama_alat": nama_alat,
                "jumlah": int(jumlah_alat),
                "keterangan": "Terlampir",
            }
        ]
        # =====================================================
        # ALAT STANDAR YANG DIGUNAKAN
        # =====================================================
        st.markdown("---")
        st.subheader("⚖️ Alat Standar yang Digunakan")

        alat_standar_tersimpan = (
            st.session_state.uttp_saved_data.get(
                "alat_standar",
                []
            )
        )

        if not isinstance(alat_standar_tersimpan, list):
            alat_standar_tersimpan = []

        opsi_alat_standar = [
            "M2",
            "M1",
            "F2",
            "F1",
        ]

        alat_standar = st.multiselect(
            "Pilih Kelas Anak Timbangan Standar",
            options=opsi_alat_standar,
            default=[
                item
                for item in alat_standar_tersimpan
                if item in opsi_alat_standar
            ],
            placeholder="Pilih satu atau lebih kelas standar",
            key="uttp_alat_standar",
        )

        if alat_standar:
            st.info(
                "Standar yang digunakan: "
                + ", ".join(alat_standar)
            )
        else:
            st.warning(
                "Pilih minimal satu kelas alat standar."
            )
        # =====================================================
        # DAFTAR RINCIAN UTTP
        # =====================================================
        st.markdown("---")
        st.subheader("📋 Daftar Rincian UTTP")

        st.caption(
            "Tambahkan rincian UTTP yang akan dicantumkan "
            "pada lampiran sertifikat."
        )

        rincian_tersimpan = (
            st.session_state.uttp_saved_data.get(
                "daftar_rincian_uttp",
                []
            )
        )

        if not isinstance(rincian_tersimpan, list):
            rincian_tersimpan = []

        daftar_rincian_uttp = []
        jumlah_rincian = int(
            st.session_state.uttp_jumlah_rincian_alat
        )

        for index in range(jumlah_rincian):
            data_lama = (
                rincian_tersimpan[index]
                if index < len(rincian_tersimpan)
                and isinstance(rincian_tersimpan[index], dict)
                else {}
            )

            with st.container(border=True):
                st.markdown(f"### Rincian UTTP {index + 1}")

                col_r1, col_r2 = st.columns(2)

                with col_r1:
                    # ==========================================
                    # NAMA ALAT PER RINCIAN
                    # ==========================================
                    opsi_nama_alat_rincian = [
                        "Timbangan Elektronik",
                        "Timbangan Mekanik",
                    ]

                    if nama_alat == "Timbangan":
                        nama_alat_rincian_lama = str(
                            data_lama.get(
                                "nama_alat",
                                "Timbangan Elektronik"
                            )
                        ).strip()

                        if (
                            nama_alat_rincian_lama
                            not in opsi_nama_alat_rincian
                        ):
                            nama_alat_rincian_lama = (
                                "Timbangan Elektronik"
                            )

                        nama_alat_rincian = st.selectbox(
                            "Nama Alat",
                            options=opsi_nama_alat_rincian,
                            index=opsi_nama_alat_rincian.index(
                                nama_alat_rincian_lama
                            ),
                            key=f"uttp_rincian_nama_alat_{index}",
                        )

                    else:
                        # Otomatis mengikuti pilihan alat utama
                        nama_alat_rincian = nama_alat

                        st.text_input(
                            "Nama Alat",
                            value=nama_alat_rincian,
                            disabled=True,
                            key=(
                                f"uttp_rincian_nama_alat_"
                                f"tampil_{index}"
                            ),
                        )

                    # ==========================================
                    # MEREK
                    # Harus di luar blok if/else
                    # ==========================================
                    merek_rincian = st.text_input(
                        "Merek",
                        value=str(
                            data_lama.get(
                                "merek",
                                ""
                            )
                        ),
                        key=f"uttp_rincian_merek_{index}",
                    )

                    # ==========================================
                    # TIPE / NOMOR SERI
                    # Harus di luar blok if/else
                    # ==========================================
                    model_tipe_rincian = st.text_input(
                        "Model / Tipe",
                        value=str(
                            data_lama.get(
                                "model_tipe",
                                data_lama.get("tipe_no_seri", "")
                            )
                        ),
                        placeholder="Contoh: ACS-30",
                        key=f"uttp_rincian_model_tipe_{index}",
                    )

                    nomor_seri_rincian = st.text_input(
                        "Nomor Seri",
                        value=str(
                            data_lama.get(
                                "nomor_seri",
                                ""
                            )
                        ),
                        placeholder="Contoh: SN123456",
                        key=f"uttp_rincian_nomor_seri_{index}",
                    )

                with col_r2:
                    # ==============================
                    # KAPASITAS DAN SATUAN
                    # ==============================
                    col_kap_nilai, col_kap_satuan = st.columns([3, 1])

                    with col_kap_nilai:
                        kapasitas_rincian = st.text_input(
                            "Kapasitas",
                            value=str(
                                data_lama.get(
                                    "kapasitas",
                                    ""
                                )
                            ),
                            placeholder="Contoh: 60",
                            key=f"uttp_rincian_kapasitas_{index}",
                        )

                    with col_kap_satuan:
                        opsi_satuan = ["kg", "g"]

                        satuan_lama = str(
                            data_lama.get(
                                "satuan",
                                "kg"
                            )
                        )

                        if satuan_lama not in opsi_satuan:
                            satuan_lama = "kg"

                        satuan_rincian = st.selectbox(
                            "Satuan",
                            options=opsi_satuan,
                            index=opsi_satuan.index(
                                satuan_lama
                            ),
                            key=f"uttp_rincian_satuan_{index}",
                        )

                    # ==============================
                    # DAYA BACA
                    # ==============================
                    tanpa_daya_baca = st.checkbox(
                        "Tidak ada daya baca",
                        value=bool(
                            data_lama.get(
                                "tanpa_daya_baca",
                                False
                            )
                        ),
                        key=f"uttp_tanpa_daya_baca_{index}",
                    )
                    
                    daya_baca_input = st.text_input(
                        f"Daya Baca ({satuan_rincian})",
                        value=(
                            ""
                            if tanpa_daya_baca
                            else str(
                                data_lama.get(
                                    "daya_baca",
                                    ""
                                )
                            )
                        ),
                        placeholder="Contoh: 0,005",
                        disabled=tanpa_daya_baca,
                        key=f"uttp_rincian_daya_baca_{index}",
                    )
                    
                    daya_baca_rincian = (
                        "-"
                        if tanpa_daya_baca
                        else daya_baca_input
                    )

                    # ==============================
                    # KELAS
                    # ==============================
                    if tanpa_daya_baca:
                        kelas_otomatis = "III"
                        nilai_n = None
                    else:
                        kelas_otomatis, nilai_n = tentukan_kelas_timbangan(
                            kapasitas_rincian,
                            daya_baca_rincian,
                            satuan_rincian
                        )
                    kelas_key = f"uttp_rincian_kelas_{index}"
                    kelas_signature_key = (
                        f"uttp_rincian_kelas_signature_{index}"
                    )
                    
                    signature_baru = (
                        str(kapasitas_rincian),
                        str(daya_baca_rincian),
                        str(satuan_rincian),
                    )
                    
                    # Jika Max/e/satuan berubah, gunakan kelas hasil
                    # perhitungan sebagai rekomendasi awal.
                    if (
                        st.session_state.get(
                            kelas_signature_key
                        ) != signature_baru
                    ):
                        st.session_state[
                            kelas_key
                        ] = (
                            kelas_otomatis
                            if kelas_otomatis
                            else "III"
                        )
                    
                        st.session_state[
                            kelas_signature_key
                        ] = signature_baru
                    
                    kelas_rincian = st.selectbox(
                        "Kelas Timbangan",
                        options=[
                            "I",
                            "II",
                            "III",
                            "IIII",
                        ],
                        key=kelas_key,
                    )
                    if nilai_n is not None:
                        st.caption(
                            f"Jumlah skala verifikasi (n): "
                            f"{nilai_n:,.0f}".replace(",", ".")
                        )
                        
                    if (
                        kapasitas_rincian
                        and daya_baca_rincian
                        and not kelas_otomatis
                    ):
                        st.warning(
                            "Kombinasi kapasitas dan daya baca "
                            "tidak sesuai klasifikasi kelas timbangan."
                        )
                daftar_rincian_uttp.append({
                    "_uttp_id": data_lama.get(
                        "_uttp_id"
                    ),
                
                    "no": index + 1,
                    "nama_alat": nama_alat_rincian,
                    "merek": merek_rincian,
                    "model_tipe": model_tipe_rincian,
                    "nomor_seri": nomor_seri_rincian,
                    "kapasitas": kapasitas_rincian,
                    "daya_baca": daya_baca_rincian,
                    "tanpa_daya_baca": tanpa_daya_baca,
                    "satuan": satuan_rincian,
                    "kelas": kelas_rincian,
                    "nilai_n": nilai_n,
                })

        col_tambah, col_copy, col_hapus, _ = st.columns(
            [1.5, 1.8, 1.7, 2]
        )

        # =====================================================
        # TAMBAH RINCIAN KOSONG
        # =====================================================
        with col_tambah:
            if st.button(
                "➕ Tambah Rincian",
                use_container_width=True,
                key="uttp_tambah_rincian",
            ):
                st.session_state.uttp_jumlah_rincian_alat += 1
                st.rerun()


        # =====================================================
        # TAMBAH DAN COPY DATA SEBELUMNYA
        # =====================================================
        with col_copy:
            if st.button(
                "📋 Tambah & Copy Sebelumnya",
                use_container_width=True,
                key="uttp_copy_rincian",
            ):
                index_sebelumnya = jumlah_rincian - 1
                index_baru = jumlah_rincian

                # Ambil data dari rincian terakhir
                nama_alat_copy = st.session_state.get(
                    f"uttp_rincian_nama_alat_{index_sebelumnya}",
                    "Timbangan Elektronik"
                )
                
                merek_copy = st.session_state.get(
                    f"uttp_rincian_merek_{index_sebelumnya}",
                    ""
                )

                model_tipe_copy = st.session_state.get(
                    f"uttp_rincian_model_tipe_{index_sebelumnya}",
                    ""
                )

                nomor_seri_copy = st.session_state.get(
                    f"uttp_rincian_nomor_seri_{index_sebelumnya}",
                    ""
                )

                kapasitas_copy = st.session_state.get(
                    f"uttp_rincian_kapasitas_{index_sebelumnya}",
                    ""
                )

                satuan_copy = st.session_state.get(
                    f"uttp_rincian_satuan_{index_sebelumnya}",
                    "kg"
                )

                daya_baca_copy = st.session_state.get(
                    f"uttp_rincian_daya_baca_{index_sebelumnya}",
                    ""
                )

                # Isi data pada rincian baru
                st.session_state[
                    f"uttp_rincian_nama_alat_{index_baru}"
                ] = nama_alat_copy
                
                st.session_state[
                    f"uttp_rincian_merek_{index_baru}"
                ] = merek_copy

                st.session_state[
                    f"uttp_rincian_model_tipe_{index_baru}"
                ] = model_tipe_copy

                st.session_state[
                    f"uttp_rincian_nomor_seri_{index_baru}"
                ] = nomor_seri_copy

                st.session_state[
                    f"uttp_rincian_kapasitas_{index_baru}"
                ] = kapasitas_copy

                st.session_state[
                    f"uttp_rincian_satuan_{index_baru}"
                ] = satuan_copy

                st.session_state[
                    f"uttp_rincian_daya_baca_{index_baru}"
                ] = daya_baca_copy

                # Tambah jumlah kartu
                st.session_state.uttp_jumlah_rincian_alat += 1

                st.rerun()


        # =====================================================
        # HAPUS RINCIAN TERAKHIR
        # =====================================================
        with col_hapus:
            if st.button(
                "➖ Hapus Rincian Terakhir",
                use_container_width=True,
                disabled=jumlah_rincian <= 1,
                key="uttp_hapus_rincian",
            ):
                index_terakhir = jumlah_rincian - 1

                for key in [
                    f"uttp_rincian_nama_alat_{index_terakhir}",
                    f"uttp_rincian_nama_alat_tampil_{index_terakhir}",
                    f"uttp_rincian_merek_{index_terakhir}",
                    f"uttp_rincian_model_tipe_{index_terakhir}",
                    f"uttp_rincian_nomor_seri_{index_terakhir}",
                    f"uttp_rincian_kapasitas_{index_terakhir}",
                    f"uttp_rincian_satuan_{index_terakhir}",
                    f"uttp_rincian_daya_baca_{index_terakhir}",
                    f"uttp_rincian_kelas_{index_terakhir}",
                ]:
                    st.session_state.pop(key, None)

                st.session_state.uttp_jumlah_rincian_alat -= 1
                st.rerun()

        st.markdown("---")
        st.subheader("Penera / Pegawai Berhak")

        df_penera = st.session_state.uttp_data_penera

        jumlah_penera = st.radio(
            "Jumlah Penera",
            [1, 2],
            horizontal=True,
            key="uttp_jumlah_penera",
        )

        col_penera1, col_penera2 = st.columns(2)

        # =====================================================
        # PENERA 1
        # =====================================================
        with col_penera1:
            penera_1 = st.selectbox(
                "Penera 1",
                options=[""] + df_penera["Nama"].tolist(),
                key="uttp_penera_1",
                on_change=update_penera_1_uttp,
            )

            nip_penera_1 = str(
                st.session_state.get(
                    "uttp_nip_penera_1",
                    ""
                )
            ).strip()

            golongan_penera_1 = str(
                st.session_state.get(
                    "uttp_golongan_penera_1",
                    ""
                )
            ).strip()

            st.text_input(
                "NIP Penera 1",
                disabled=True,
                key="uttp_nip_penera_1",
            )

            st.text_input(
                "Golongan Penera 1",
                disabled=True,
                key="uttp_golongan_penera_1",
            )


        # =====================================================
        # PENERA 2
        # =====================================================
        if jumlah_penera == 2:
            with col_penera2:
                penera_2 = st.selectbox(
                    "Penera 2",
                    options=[""] + df_penera["Nama"].tolist(),
                    key="uttp_penera_2",
                    on_change=update_penera_2_uttp,
                )

                nip_penera_2 = str(
                    st.session_state.get(
                        "uttp_nip_penera_2",
                        ""
                    )
                ).strip()

                golongan_penera_2 = str(
                    st.session_state.get(
                        "uttp_golongan_penera_2",
                        ""
                    )
                ).strip()

                st.text_input(
                    "NIP Penera 2",
                    disabled=True,
                    key="uttp_nip_penera_2",
                )

                st.text_input(
                    "Golongan Penera 2",
                    disabled=True,
                    key="uttp_golongan_penera_2",
                )
        else:
            penera_2 = ""
            nip_penera_2 = ""
            golongan_penera_2 = ""

        st.markdown("---")

        col_simpan, col_reset = st.columns(2)

        with col_simpan:
            simpan = st.button(
                "💾 Simpan Data",
                type="primary",
                use_container_width=True,
                key="uttp_simpan",
            )

        with col_reset:
            st.button(
                "🔄 Reset Form",
                use_container_width=True,
                key="uttp_reset",
                on_click=reset_form_uttp,
            )

        if simpan:
            # =================================================
            # VALIDASI
            # =================================================
            daftar_error = validasi_data_uttp(
                pemilik=pemilik,
                alamat=alamat,
                daftar_rincian=daftar_rincian_uttp,
                alat_standar=alat_standar,
                penera_1=penera_1,
                jumlah_penera=jumlah_penera,
                penera_2=penera_2,
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

            # =================================================
            # SIMPAN DATA FORM KE SESSION STATE
            # =================================================
            st.session_state.uttp_saved_data = {
                "_edit_pengujian_id": (
                    st.session_state.get(
                        "uttp_edit_pengujian_id"
                    )
                ),

                "pemilik": pemilik,
                "alamat": alamat,

                "daftar_alat_uttp": (
                    daftar_alat_uttp
                ),

                "daftar_rincian_uttp": (
                    daftar_rincian_uttp
                ),

                "alat_standar": (
                    alat_standar
                ),

                "nama_alat": (
                    daftar_alat_uttp[0][
                        "nama_alat"
                    ]
                ),

                "jumlah_alat": (
                    daftar_alat_uttp[0][
                        "jumlah"
                    ]
                ),

                "jenis_pengujian": (
                    jenis_pengujian
                ),

                "lokasi_pengujian": (
                    lokasi_pengujian
                ),

                "tanggal_pengujian": (
                    tanggal_pengujian.strftime(
                        "%Y-%m-%d"
                    )
                ),

                "tanggal_sertifikat": (
                    tanggal_sertifikat.strftime(
                        "%Y-%m-%d"
                    )
                ),

                "nomor_sertifikat": (
                    nomor_sertifikat
                ),

                "nomor_order": (
                    nomor_order
                ),

                "jumlah_penera": (
                    jumlah_penera
                ),

                "penera_1": (
                    penera_1
                ),

                "nip_penera_1": (
                    nip_penera_1
                ),

                "golongan_penera_1": (
                    golongan_penera_1
                ),

                "penera_2": (
                    penera_2
                ),

                "nip_penera_2": (
                    nip_penera_2
                ),

                "golongan_penera_2": (
                    golongan_penera_2
                ),
            }

            # =================================================
            # DATA BERUBAH → DOKUMEN LAMA TIDAK BERLAKU
            # =================================================
            st.session_state[
                "uttp_generated_files"
            ] = {}

            # =================================================
            # DATA BARU / HASIL EDIT BELUM DIKIRIM KE DATABASE
            # =================================================
            st.session_state[
                "uttp_sudah_disimpan_db"
            ] = False

            st.session_state[
                "uttp_last_pengujian_id"
            ] = None

            st.success(
                "✅ Data berhasil disimpan! "
                "Silakan buka Preview & Generate Data."
            )

            st.balloons()
            st.session_state.uttp_saved_data = {
                "_edit_pengujian_id": (
                    st.session_state.get(
                        "uttp_edit_pengujian_id"
                    )
                ),
                "pemilik": pemilik,
                "alamat": alamat,
                "daftar_alat_uttp": daftar_alat_uttp,
                "daftar_rincian_uttp": daftar_rincian_uttp,
                "alat_standar": alat_standar,
                "nama_alat": daftar_alat_uttp[0]["nama_alat"],
                "jumlah_alat": daftar_alat_uttp[0]["jumlah"],
                "jenis_pengujian": jenis_pengujian,
                "lokasi_pengujian": lokasi_pengujian,
                "tanggal_pengujian": (
                    tanggal_pengujian.strftime("%Y-%m-%d")
                ),
                "tanggal_sertifikat": (
                    tanggal_sertifikat.strftime("%Y-%m-%d")
                ),
                "nomor_sertifikat": nomor_sertifikat,
                "nomor_order": nomor_order,
                "jumlah_penera": jumlah_penera,
                "penera_1": penera_1,
                "nip_penera_1": nip_penera_1,
                "golongan_penera_1": golongan_penera_1,
                "penera_2": penera_2,
                "nip_penera_2": nip_penera_2,
                "golongan_penera_2": golongan_penera_2,
            }

            st.session_state.uttp_generated_files = {}

            # Data form baru / hasil edit belum dikirim ke database
            st.session_state[
                "uttp_sudah_disimpan_db"
            ] = False
            
            st.session_state[
                "uttp_last_pengujian_id"
            ] = None
            
            st.success(
                "✅ Data berhasil disimpan!"
            )
            st.balloons()

    elif mode == "📄 Preview & Generate Data":
        st.header("Preview dan Generate Sertifikat")
        col_kembali, col_kosong = st.columns(
            [1.5, 4]
        )

        with col_kembali:
            st.button(
                "← Kembali dan Edit Data",
                use_container_width=True,
                key="uttp_kembali_edit",
                on_click=kembali_ke_input_uttp,
            )
        data = st.session_state.uttp_saved_data

        if not data:
            st.warning(
                "Silakan simpan data pengujian terlebih dahulu."
            )
            return

        col_preview1, col_preview2 = st.columns(2)

        with col_preview1:
            st.subheader("📋 Preview Data")
            st.write(f"**Pemilik:** {data.get('pemilik', '-')}")
            st.write(f"**Alamat:** {data.get('alamat', '-')}")

            st.write("**Daftar Alat:**")
            for item in data.get("daftar_alat_uttp", []):
                st.write(
                    f"- {item.get('jumlah', 0)} Unit "
                    f"{item.get('nama_alat', '')}"
                )

            st.write("**Rincian UTTP:**")

            daftar_rincian_preview = data.get(
                "daftar_rincian_uttp",
                []
            )

            if not daftar_rincian_preview:
                st.caption(
                    "Belum ada rincian UTTP."
                )

            for nomor, item in enumerate(
                daftar_rincian_preview,
                start=1
            ):
                nama_alat_preview = item.get(
                    "nama_alat",
                    "-"
                )

                merek_preview = item.get(
                    "merek",
                    "-"
                )

                model_tipe_preview = item.get(
                    "model_tipe",
                    item.get("tipe_no_seri", "-")
                )

                nomor_seri_preview = item.get(
                    "nomor_seri",
                    "-"
                )

                kapasitas_preview = item.get(
                    "kapasitas",
                    "-"
                )

                daya_baca_preview = item.get(
                    "daya_baca",
                    "-"
                )

                satuan_preview = item.get(
                    "satuan",
                    ""
                )

                kelas_preview = item.get(
                    "kelas",
                    "-"
                )

                with st.container(
                    border=True
                ):
                    st.markdown(
                        f"**{nomor}. {nama_alat_preview}**"
                    )

                    col_rinci1, col_rinci2 = (
                        st.columns(2)
                    )

                    with col_rinci1:
                        st.write(
                            f"**Merek:** "
                            f"{merek_preview}"
                        )

                        st.write(
                            f"**Model / Tipe:** "
                            f"{model_tipe_preview}"
                        )

                        st.write(
                            f"**Nomor Seri:** "
                            f"{nomor_seri_preview}"
                        )

                    with col_rinci2:
                        st.write(
                            f"**Kapasitas:** "
                            f"{kapasitas_preview} "
                            f"{satuan_preview}"
                        )

                        if not item.get(
                            "tanpa_daya_baca",
                            False
                        ):
                            st.write(
                                f"**Daya Baca:** "
                                f"{daya_baca_preview} "
                                f"{satuan_preview}"
                            )

                        st.write(
                            f"**Kelas:** "
                            f"{kelas_preview}"
                        )
            alat_standar_preview = data.get(
                "alat_standar",
                []
            )

            if isinstance(alat_standar_preview, list):
                alat_standar_text = ", ".join(
                    alat_standar_preview
                )
            else:
                alat_standar_text = str(
                    alat_standar_preview or "-"
                )

            st.write(
                f"**Alat Standar:** "
                f"{alat_standar_text or '-'}"
            )
        with col_preview2:
            st.subheader("📄 Data Sertifikat")
            st.write(
                f"**Nomor Sertifikat:** "
                f"{data.get('nomor_sertifikat', '-')}"
            )
            st.write(
                f"**Nomor Order:** "
                f"{data.get('nomor_order', '-')}"
            )
            st.write(
                f"**Jenis Pengujian:** "
                f"{data.get('jenis_pengujian', '-')}"
            )
            st.write(
                f"**Lokasi Pengujian:** "
                f"{data.get('lokasi_pengujian', '-')}"
            )
            st.write(
                f"**Penera 1:** "
                f"{data.get('penera_1', '-')}"
            )

            st.write(
                f"**NIP Penera 1:** "
                f"{data.get('nip_penera_1', '-')}"
            )

            if data.get(
                "jumlah_penera",
                1
            ) == 2:
                st.write(
                    f"**Penera 2:** "
                    f"{data.get('penera_2', '-')}"
                )

                st.write(
                    f"**NIP Penera 2:** "
                    f"{data.get('nip_penera_2', '-')}"
                )

        st.markdown("---")

        sudah_disimpan_db = bool(
            st.session_state.get(
                "uttp_sudah_disimpan_db",
                False
            )
        )
        
        if st.button(
            (
                "✅ Sudah Disimpan ke Database"
                if sudah_disimpan_db
                else "🎫 Generate Sertifikat"
            ),
            type="primary",
            use_container_width=True,
            disabled=sudah_disimpan_db,
            key="uttp_generate_sertifikat",
        ):
            try:
                OUTPUT_DIR.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                nama_file = format_nama_file_uttp(
                    data,
                    "Sertifikat"
                )

                output_file = OUTPUT_DIR / nama_file

                generate_sertifikat_uttp_pdf(
                    data,
                    str(output_file),
                )

                # =====================================================
                # SIMPAN PENGUJIAN KE SUPABASE
                # =====================================================
                hasil_simpan = (
                    simpan_pengujian_uttp_umum_ke_supabase(
                        data
                    )
                )
                
                # =====================================================
                # AMBIL ID PENGUJIAN HASIL SIMPAN
                # =====================================================
                pengujian_rows = (
                    hasil_simpan.get(
                        "pengujian",
                        []
                    )
                    or []
                )
                
                pengujian_id_hasil = None
                
                if pengujian_rows:
                    pengujian_id_hasil = (
                        pengujian_rows[0].get(
                            "id"
                        )
                    )
                
                # =====================================================
                # TANDAI SUDAH MASUK DATABASE
                # =====================================================
                st.session_state[
                    "uttp_sudah_disimpan_db"
                ] = True
                
                st.session_state[
                    "uttp_last_pengujian_id"
                ] = pengujian_id_hasil
                
                st.session_state.uttp_generated_files[
                    "sertifikat"
                ] = str(
                    output_file
                )
                
                if (
                    hasil_simpan.get("mode")
                    == "edit"
                ):
                    st.success(
                        "✅ Pengujian berhasil diperbarui "
                        "dan sertifikat berhasil dibuat!"
                    )
                else:
                    st.success(
                        "✅ Pengujian berhasil disimpan ke "
                        "Supabase dan sertifikat berhasil dibuat!"
                    )
            except Exception as exc:
                st.error(f"❌ Error: {exc}")
                st.code(traceback.format_exc())

        sertifikat_path = (
            st.session_state.uttp_generated_files.get(
                "sertifikat"
            )
        )

        if (
            sertifikat_path
            and Path(sertifikat_path).exists()
        ):
            with open(sertifikat_path, "rb") as file_pdf:
                st.download_button(
                    "⬇️ Download Sertifikat",
                    data=file_pdf.read(),
                    file_name=Path(
                        sertifikat_path
                    ).name,
                    mime="application/pdf",
                    use_container_width=True,
                    key="uttp_download_sertifikat",
                )
            if st.session_state.get(
                "uttp_sudah_disimpan_db",
                False
            ):
                st.markdown("---")
            
                if st.button(
                    "➕ Buat Pengujian Baru",
                    use_container_width=True,
                    key="uttp_pengujian_baru",
                ):
                    reset_form_uttp()
                    st.rerun()

    # =========================================================
    # MODE RIWAYAT UTTP UMUM
    # =========================================================
    elif mode == "📚 Riwayat UTTP":

        st.header(
            "📚 Riwayat Pengujian UTTP"
        )

        try:
            daftar_riwayat = (
                ambil_riwayat_uttp_umum()
            )

            if not daftar_riwayat:
                st.info(
                    "Belum ada riwayat pengujian "
                    "UTTP Umum."
                )
                return

            # =================================================
            # PILIH DETAIL PENGUJIAN
            # =================================================
            opsi_pengujian = {}

            for pengujian in daftar_riwayat:

                detail = (
                    pengujian.get(
                        "data_pengujian"
                    )
                    or {}
                )

                label = (
                    f"{pengujian.get('tanggal_pengujian', '')}"
                    f" | "
                    f"{detail.get('pemilik', '')}"
                    f" | "
                    f"{pengujian.get('nomor_sertifikat', '')}"
                )

                opsi_pengujian[
                    label
                ] = pengujian

            pilihan = st.selectbox(
                "Lihat Detail Pengujian",
                options=[
                    ""
                ] + list(
                    opsi_pengujian.keys()
                ),
                key="uttp_riwayat_pilih",
            )

            if pilihan:

                pengujian = (
                    opsi_pengujian[
                        pilihan
                    ]
                )

                detail = (
                    pengujian.get(
                        "data_pengujian"
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
                        detail.get(
                            "pemilik",
                            "-"
                        )
                    )

                    st.write(
                        "**Alamat:**",
                        detail.get(
                            "alamat",
                            "-"
                        )
                    )

                    st.write(
                        "**Tanggal Pengujian:**",
                        pengujian.get(
                            "tanggal_pengujian",
                            "-"
                        )
                    )

                    st.write(
                        "**Jenis Pengujian:**",
                        pengujian.get(
                            "jenis_pengujian",
                            "-"
                        )
                    )

                with col2:
                    st.write(
                        "**Nomor Sertifikat:**",
                        pengujian.get(
                            "nomor_sertifikat",
                            "-"
                        )
                    )

                    st.write(
                        "**Nomor Order:**",
                        pengujian.get(
                            "nomor_order",
                            "-"
                        )
                    )

                    st.write(
                        "**Penera:**",
                        pengujian.get(
                            "penera_1",
                            "-"
                        )
                    )

                    st.write(
                        "**Hasil:**",
                        pengujian.get(
                            "hasil",
                            "-"
                        )
                    )

                st.markdown(
                    "### Daftar Rincian UTTP"
                )

                daftar_rincian = (
                    detail.get(
                        "daftar_rincian_uttp",
                        []
                    )
                    or []
                )

                if daftar_rincian:

                    df_rincian = pd.DataFrame(
                        daftar_rincian
                    )

                    df_rincian = df_rincian.drop(
                        columns=[
                            "_uttp_id",
                            "tanpa_daya_baca",
                            "nilai_n",
                        ],
                        errors="ignore",
                    )

                    st.dataframe(
                        df_rincian,
                        use_container_width=True,
                        hide_index=True,
                    )

                st.markdown("---")
    
                if st.button(
                    "✏️ Edit Pengujian",
                    type="primary",
                    use_container_width=True,
                    key=(
                        "uttp_edit_riwayat_"
                        f"{pengujian.get('id')}"
                    ),
                ):
                    gunakan_data_lama_untuk_edit_uttp(
                        pengujian
                    )
                
                    st.rerun()
        except Exception as exc:
            st.error(
                "Gagal membaca riwayat UTTP: "
                f"{exc}"
            )

            st.code(
                traceback.format_exc()
            )
if __name__ == "__main__":
    run()
