import math
import re
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from supabase import create_client
try:
    from modules.timbangan.cerapan_timbangan_generator import generate_cerapan_pdf
    from modules.timbangan.sertifikat_timbangan_generator import generate_sertifikat_pdf
    from modules.timbangan.form_peminjaman_standar_timbangan_generator import (
        generate_form_peminjaman_standar_timbangan_pdf
    )
    from modules.timbangan.form_peminjaman_ctt_timbangan_generator import (
        generate_form_peminjaman_ctt_timbangan_pdf
    )
except ModuleNotFoundError:
    # Fallback agar file tetap bisa diuji secara mandiri.
    from cerapan_generator import generate_cerapan_pdf
    from sertifikat_generator import generate_sertifikat_pdf
    from form_peminjaman_standar_timbangan_generator import (
        generate_form_peminjaman_standar_timbangan_pdf
    )
    from form_peminjaman_ctt_timbangan_generator import (
        generate_form_peminjaman_ctt_timbangan_pdf
    )


def find_project_root():
    current = Path(__file__).resolve()

    for parent in [current.parent] + list(current.parents):
        if (parent / "modules").exists() or (parent / "app.py").exists():
            return parent

    return current.parent


PROJECT_ROOT = find_project_root()
ASSETS_DIR = PROJECT_ROOT / "assets"
OUTPUT_DIR = PROJECT_ROOT / "output" / "timbangan"
# =========================================================
# KONEKSI SUPABASE
# =========================================================
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]

    return create_client(url, key)

def simpan_atau_update_perusahaan(
    supabase,
    nama_perusahaan,
    alamat,
):
    """
    Cari perusahaan berdasarkan nama.
    Jika sudah ada, update alamat bila berbeda.
    Jika belum ada, insert perusahaan baru.
    """

    nama_perusahaan = str(
        nama_perusahaan or ""
    ).strip()

    alamat = str(
        alamat or ""
    ).strip()

    if not nama_perusahaan:
        raise ValueError(
            "Nama perusahaan belum diisi."
        )

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

    # Perusahaan sudah ada
    if response.data:
        row = response.data[0]

        perusahaan_id = row["id"]

        alamat_lama = str(
            row.get(
                "alamat",
                ""
            ) or ""
        ).strip()

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

    # Perusahaan baru
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
            "Perusahaan gagal disimpan."
        )

    return response.data[0]["id"]

def get_or_create_uttp_timbangan(
    supabase,
    perusahaan_id,
    nama_alat,
    merek,
    model,
    no_seri,
    kapasitas_max,
    lokasi="Perusahaan",
):
    """
    Cari atau buat UTTP Timbangan.
    """

    nama_alat = str(
        nama_alat or "Timbangan"
    ).strip()

    merek = str(
        merek or ""
    ).strip()

    model = str(
        model or ""
    ).strip()

    no_seri = str(
        no_seri or ""
    ).strip()

    lokasi = str(
        lokasi or "Perusahaan"
    ).strip()

    if not no_seri:
        raise ValueError(
            "No. Seri / No. Alat wajib diisi."
        )

    # =====================================================
    # CARI UTTP BERDASARKAN JENIS ALAT + NOMOR SERI
    # perusahaan_id TIDAK digunakan sebagai identitas alat,
    # karena pemilik/perusahaan dapat berubah.
    # =====================================================
    response = (
        supabase
        .table("uttp")
        .select("*")
        .eq(
            "jenis_uttp",
            nama_alat
        )
        .eq(
            "nomor_seri",
            no_seri
        )
        .execute()
    )

    # Jika sudah ada, update identitas alat
    if response.data:
        uttp = response.data[0]
        uttp_id = uttp["id"]

        (
            supabase
            .table("uttp")
            .update({
                "perusahaan_id": perusahaan_id,
                "merk": merek,
                "tipe": model,
                "kapasitas": str(
                    kapasitas_max
                ),
                "lokasi": lokasi,
                "status": "aktif",
            })
            .eq(
                "id",
                uttp_id
            )
            .execute()
        )

        return uttp_id

    # Jika belum ada, buat baru
    response = (
        supabase
        .table("uttp")
        .insert({
            "perusahaan_id": perusahaan_id,
            "jenis_uttp": nama_alat,
            "merk": merek,
            "tipe": model,
            "nomor_seri": no_seri,
            "kapasitas": str(
                kapasitas_max
            ),
            "lokasi": lokasi,
            "status": "aktif",
        })
        .execute()
    )

    return response.data[0]["id"]

def build_data_pengujian_timbangan(data):
    """
    Menyusun detail teknis pengujian Timbangan
    untuk disimpan ke kolom JSONB data_pengujian.

    Fungsi ini dibuat fleksibel untuk:
    - Timbangan Elektronik
    - Timbangan Bobot Ingsut
    - Timbangan Sentisimal
    - Timbangan Pegas
    - Timbangan Meja
    - Timbangan Neraca Obat
    """

    nama_alat = str(
        data.get("nama_alat", "")
    ).strip()

    # =====================================================
    # HASIL PENGUJIAN KEBENARAN
    # =====================================================
    hasil_kebenaran_raw = list(
        data.get("hasil_pengujian", []) or []
    )

    # Hanya simpan baris yang benar-benar aktif.
    hasil_kebenaran = [
        item
        for item in hasil_kebenaran_raw
        if item.get("aktif", True)
    ]

    # Fallback untuk kompatibilitas data versi lama.
    if (
        not hasil_kebenaran
        and hasil_kebenaran_raw
    ):
        hasil_kebenaran = hasil_kebenaran_raw

    # =====================================================
    # EKSENTRISITAS
    # =====================================================
    eksentrisitas = list(
        data.get("eksentrisitas", []) or []
    )

    # =====================================================
    # REPETABILITY
    # =====================================================
    repetability = list(
        data.get("repetability", []) or []
    )

    # =====================================================
    # PEMERIKSAAN VISUAL
    # =====================================================
    visual = dict(
        data.get("visual", {}) or {}
    )

    # =====================================================
    # ALAT STANDAR PEMINJAMAN
    # =====================================================
    alat_standar_peminjaman = list(
        data.get(
            "daftar_alat_standar_peminjaman",
            []
        ) or []
    )

    # =====================================================
    # JUMLAH TITIK UJI
    # =====================================================
    jumlah_titik_uji = data.get(
        "jumlah_titik_uji"
    )

    if jumlah_titik_uji is None:
        jumlah_titik_uji = len(
            hasil_kebenaran
        )

    try:
        jumlah_titik_uji = int(
            jumlah_titik_uji
        )
    except (TypeError, ValueError):
        jumlah_titik_uji = len(
            hasil_kebenaran
        )

    # =====================================================
    # SUSUN JSON
    # =====================================================
    detail_pengujian = {
        "nama_alat": nama_alat,

        "model": str(
            data.get(
                "model",
                ""
            ) or ""
        ).strip(),

        "kapasitas_max": data.get(
            "kapasitas_max",
            0
        ),

        "kapasitas_min": data.get(
            "kapasitas_min",
            0
        ),

        "daya_baca": data.get(
            "daya_baca",
            0
        ),

        "interval_skala": data.get(
            "interval_skala",
            0
        ),

        "satuan": str(
            data.get(
                "satuan",
                "kg"
            ) or "kg"
        ).strip(),

        "kelas": str(
            data.get(
                "kelas",
                ""
            ) or ""
        ).strip(),

        "suhu": str(
            data.get(
                "suhu",
                "Ambient"
            ) or "Ambient"
        ).strip(),

        "kelembaban": str(
            data.get(
                "kelembaban",
                "Ambient"
            ) or "Ambient"
        ).strip(),

        "metode": str(
            data.get(
                "metode",
                ""
            ) or ""
        ).strip(),

        "at_standar": str(
            data.get(
                "at_standar",
                ""
            ) or ""
        ).strip(),

        "lokasi": str(
            data.get(
                "lokasi",
                "Perusahaan"
            ) or "Perusahaan"
        ).strip(),

        "jumlah_titik_uji": jumlah_titik_uji,

        "hasil_kebenaran": hasil_kebenaran,

        "eksentrisitas": eksentrisitas,

        "repetability": repetability,

        "repetability_sederhana": bool(
            data.get(
                "repetability_sederhana",
                False
            )
        ),

        "penyetelan_nol": data.get(
            "penyetelan_nol",
            []
        ),

        "visual": visual,

        "daftar_alat_standar_peminjaman": (
            alat_standar_peminjaman
        ),
    }

    return detail_pengujian

def simpan_pengujian_timbangan_ke_supabase(data):
    """
    Menyimpan satu pengujian Timbangan ke Supabase.

    Alur:
    1. Ambil perusahaan
    2. Cari / buat UTTP
    3. Susun data_pengujian JSON
    4. Insert / update ke tabel pengujian
    """

    supabase = get_supabase()

    # =====================================================
    # 1. VALIDASI DASAR
    # =====================================================
    pemilik = str(
        data.get("pemilik", "")
    ).strip()

    alamat = str(
        data.get("alamat", "")
    ).strip()

    nama_alat = str(
        data.get("nama_alat", "")
    ).strip()

    no_seri = str(
        data.get("no_seri", "")
    ).strip()

    nomor_order = str(
        data.get("nomor_order", "")
    ).strip()

    nomor_sertifikat = str(
        data.get("nomor_sertifikat", "")
    ).strip()

    if not pemilik:
        raise ValueError(
            "Nama pemilik / perusahaan belum diisi."
        )

    if not nama_alat:
        raise ValueError(
            "Nama alat belum diisi."
        )

    if not no_seri:
        raise ValueError(
            "No. Seri / No. Alat belum diisi."
        )

    if not nomor_order:
        raise ValueError(
            "Nomor order belum diisi."
        )

    if not nomor_sertifikat:
        raise ValueError(
            "Nomor sertifikat belum diisi."
        )

    # =====================================================
    # 2. TENTUKAN PERUSAHAAN
    # =====================================================
    
    sedang_edit = bool(
        st.session_state.get(
            "tb_edit_pengujian_id"
        )
    )
    
    aksi_perusahaan = st.session_state.get(
        "tb_aksi_perusahaan_edit",
        "Gunakan perusahaan saat ini"
    )
    
    
    # -----------------------------------------------------
    # A. INPUT DATA BARU
    # -----------------------------------------------------
    if not sedang_edit:
    
        perusahaan_id = simpan_atau_update_perusahaan(
            supabase,
            pemilik,
            alamat,
        )
    
    
    # -----------------------------------------------------
    # B. EDIT - GUNAKAN PERUSAHAAN SAAT INI
    # -----------------------------------------------------
    elif aksi_perusahaan == "Gunakan perusahaan saat ini":
    
        perusahaan_id = st.session_state.get(
            "tb_perusahaan_id_lama"
        )
    
        if not perusahaan_id:
            raise ValueError(
                "ID perusahaan lama tidak ditemukan."
            )
    
    
    # -----------------------------------------------------
    # C. EDIT DATA PERUSAHAAN SAAT INI
    # -----------------------------------------------------
    elif aksi_perusahaan == "Edit data perusahaan saat ini":
    
        perusahaan_id = st.session_state.get(
            "tb_perusahaan_id_lama"
        )
    
        if not perusahaan_id:
            raise ValueError(
                "ID perusahaan lama tidak ditemukan."
            )
    
        (
            supabase
            .table("perusahaan")
            .update({
                "nama_perusahaan": pemilik,
                "alamat": alamat,
            })
            .eq(
                "id",
                perusahaan_id
            )
            .execute()
        )
    
    
    # -----------------------------------------------------
    # D. GANTI / TAMBAH PERUSAHAAN BARU
    # -----------------------------------------------------
    elif aksi_perusahaan == "Ganti / tambah perusahaan baru":
    
        perusahaan_id = simpan_atau_update_perusahaan(
            supabase,
            pemilik,
            alamat,
        )
    
    
    # -----------------------------------------------------
    # FALLBACK
    # -----------------------------------------------------
    else:
    
        perusahaan_id = simpan_atau_update_perusahaan(
            supabase,
            pemilik,
            alamat,
        )

    # =====================================================
    # 3. CARI / BUAT UTTP
    # =====================================================
    uttp_id = get_or_create_uttp_timbangan(
        supabase=supabase,
        perusahaan_id=perusahaan_id,
        nama_alat=nama_alat,
        merek=data.get(
            "merek",
            ""
        ),
        model=data.get(
            "model",
            ""
        ),
        no_seri=no_seri,
        kapasitas_max=data.get(
            "kapasitas_max",
            ""
        ),
        lokasi=data.get(
            "lokasi",
            "Perusahaan"
        ),
    )

    # =====================================================
    # 4. SUSUN JSON DATA PENGUJIAN
    # =====================================================
    detail_pengujian = (
        build_data_pengujian_timbangan(
            data
        )
    )

    # =====================================================
    # 5. TANGGAL
    # =====================================================
    tanggal_pengujian = data.get(
        "tanggal"
    )

    tanggal_sertifikat = data.get(
        "tanggal_tanda_tangan"
    )

    berlaku_sampai = data.get(
        "berlaku_sampai"
    )

    if hasattr(
        tanggal_pengujian,
        "strftime"
    ):
        tanggal_pengujian = (
            tanggal_pengujian.strftime(
                "%Y-%m-%d"
            )
        )

    if hasattr(
        tanggal_sertifikat,
        "strftime"
    ):
        tanggal_sertifikat = (
            tanggal_sertifikat.strftime(
                "%Y-%m-%d"
            )
        )

    if hasattr(
        berlaku_sampai,
        "strftime"
    ):
        berlaku_sampai = (
            berlaku_sampai.strftime(
                "%Y-%m-%d"
            )
        )

    # =====================================================
    # 6. PAYLOAD PENGUJIAN
    # =====================================================
    payload = {
        "uttp_id": uttp_id,

        "tanggal_pengujian": (
            tanggal_pengujian
        ),

        "tanggal_sertifikat": (
            tanggal_sertifikat
        ),

        "jenis_pengujian": str(
            data.get(
                "keterangan",
                "Tera Ulang"
            )
        ).strip(),

        "hasil": "SAH",

        "nomor_order": nomor_order,

        "nomor_sertifikat": (
            nomor_sertifikat
        ),

        "penera_1": str(
            data.get(
                "nama_penera",
                ""
            )
        ).strip(),

        "penera_2": str(
            data.get(
                "nama_penera_2",
                ""
            )
        ).strip(),

        "berlaku_sampai": (
            berlaku_sampai
        ),

        "data_pengujian": (
            detail_pengujian
        ),
    }

    # =====================================================
    # 7. INSERT / UPDATE
    # =====================================================
    edit_id = st.session_state.get(
        "tb_edit_pengujian_id"
    )

    if edit_id:
        response = (
            supabase
            .table("pengujian")
            .update(payload)
            .eq(
                "id",
                edit_id
            )
            .execute()
        )
    
    else:
        response = (
            supabase
            .table("pengujian")
            .insert(payload)
            .execute()
        )
    
    
    # =====================================================
    # PASTIKAN PENYIMPANAN BERHASIL
    # =====================================================
    if not response.data:
        raise RuntimeError(
            "Data pengujian gagal disimpan ke Supabase."
        )
    
    
    # =====================================================
    # BERSIHKAN MODE EDIT SETELAH UPDATE BERHASIL
    # =====================================================
    if edit_id:
    
        keys_edit_perusahaan = [
            "tb_edit_pengujian_id",
            "tb_perusahaan_id_lama",
            "tb_uttp_id_lama",
            "tb_nama_perusahaan_lama",
            "tb_alamat_perusahaan_lama",
            "tb_aksi_perusahaan_edit",
            "tb_aksi_perusahaan_edit_sebelumnya",
        ]
    
        for key in keys_edit_perusahaan:
            st.session_state.pop(
                key,
                None
            )
    
    
    return response.data
def gunakan_data_lama_untuk_pengujian_baru_timbangan(
    alat,
    perusahaan,
    pengujian
):
    """
    Menggunakan identitas alat lama sebagai dasar
    pengujian baru, tanpa membawa hasil pengujian lama.
    """

    detail = (
        pengujian.get("data_pengujian")
        or {}
    )

    # Pastikan bukan mode edit
    st.session_state.pop(
        "tb_edit_pengujian_id",
        None
    )

    nama_perusahaan = str(
        perusahaan.get(
            "nama_perusahaan",
            ""
        )
        or ""
    ).strip()

    alamat = str(
        perusahaan.get(
            "alamat",
            ""
        )
        or ""
    ).strip()

    st.session_state.tb_saved_data = {

        "pemilik": nama_perusahaan,
        "alamat": alamat,

        "nama_alat": (
            alat.get("jenis_uttp")
            or detail.get("nama_alat")
            or ""
        ),

        "merek": (
            alat.get("merk")
            or ""
        ),

        "model": (
            alat.get("tipe")
            or detail.get("model")
            or ""
        ),

        "no_seri": (
            alat.get("nomor_seri")
            or ""
        ),

        "kapasitas_max": detail.get(
            "kapasitas_max",
            0
        ),

        "kapasitas_min": detail.get(
            "kapasitas_min",
            0
        ),

        "daya_baca": detail.get(
            "daya_baca",
            0
        ),

        "interval_skala": detail.get(
            "interval_skala",
            0
        ),

        "satuan": detail.get(
            "satuan",
            "kg"
        ),

        "kelas": detail.get(
            "kelas",
            "III"
        ),

        "suhu": "Ambient",
        "kelembaban": "Ambient",

        "metode": detail.get(
            "metode",
            ""
        ),

        "at_standar": detail.get(
            "at_standar",
            ""
        ),

        "lokasi": detail.get(
            "lokasi",
            "Perusahaan"
        ),

        # Hasil pengujian dibuat baru
        "hasil_pengujian": [],
        "eksentrisitas": [],
        "repetability": [],
        "penyetelan_nol": [],

        "jumlah_titik_uji": detail.get(
            "jumlah_titik_uji",
            5
        ),
        
        "visual": {},

        "daftar_alat_standar_peminjaman": (
            detail.get(
                "daftar_alat_standar_peminjaman",
                []
            )
        ),

        # Nomor dokumen baru
        "nomor_order": "",
        "nomor_sertifikat": "",

        # Tanggal baru
        "tanggal": datetime.now().strftime(
            "%Y-%m-%d"
        ),

        "tanggal_tanda_tangan": (
            datetime.now().strftime(
                "%Y-%m-%d"
            )
        ),

        "keterangan": "Tera Ulang",
    }
    # =====================================================
    # SINKRONKAN ALAT STANDAR
    # =====================================================
    daftar_alat_standar = (
        st.session_state.tb_saved_data.get(
            "daftar_alat_standar_peminjaman",
            []
        )
        or []
    )
    
    st.session_state[
        "tb_jumlah_baris_alat_standar"
    ] = max(
        1,
        len(daftar_alat_standar)
    )
    
    for key in list(st.session_state.keys()):
        if (
            key.startswith("tb_jenis_alat_standar_")
            or key.startswith("tb_jumlah_alat_standar_")
        ):
            st.session_state.pop(
                key,
                None
            )
    # =====================================================
    # BERSIHKAN WIDGET HASIL PENGUJIAN LAMA
    # =====================================================
    prefixes = [
        "tb_muatan_uji_",
        "tb_penunjukan_kebenaran_",
        "tb_pengamatan_penunjukan_",
        "tb_hasil_kebenaran_",
        "tb_cek_kebenaran_",
        "tb_neraca_",
        "tb_eksen_",
        "tb_repet_",
    ]

    for key in list(
        st.session_state.keys()
    ):
        if any(
            key.startswith(prefix)
            for prefix in prefixes
        ):
            st.session_state.pop(
                key,
                None
            )

    # =====================================================
    # IDENTITAS KE WIDGET
    # =====================================================
    st.session_state[
        "tb_nama_perusahaan"
    ] = nama_perusahaan

    st.session_state[
        "tb_alamat_input"
    ] = alamat

    st.session_state[
        "tb_perusahaan_select"
    ] = nama_perusahaan

    st.session_state[
        "tb_manual_perusahaan"
    ] = False

    st.session_state[
        "tb_nama_alat"
    ] = st.session_state.tb_saved_data[
        "nama_alat"
    ]

    st.session_state[
        "tb_merek"
    ] = st.session_state.tb_saved_data[
        "merek"
    ]

    st.session_state[
        "tb_model"
    ] = st.session_state.tb_saved_data[
        "model"
    ]

    st.session_state[
        "tb_no_seri"
    ] = st.session_state.tb_saved_data[
        "no_seri"
    ]
    # =====================================================
    # SINKRONKAN SPESIFIKASI KE WIDGET
    # =====================================================
    satuan = str(
        st.session_state.tb_saved_data.get(
            "satuan",
            "kg"
        )
        or "kg"
    ).strip()
    
    if satuan not in ["kg", "g"]:
        satuan = "kg"
    
    nama_alat = str(
        st.session_state.tb_saved_data.get(
            "nama_alat",
            "Timbangan Elektronik"
        )
    ).strip()
    
    kapasitas_max_kg = float(
        st.session_state.tb_saved_data.get(
            "kapasitas_max",
            0
        )
        or 0
    )
    
    kapasitas_min_kg = float(
        st.session_state.tb_saved_data.get(
            "kapasitas_min",
            0
        )
        or 0
    )
    
    daya_baca_kg = float(
        st.session_state.tb_saved_data.get(
            "daya_baca",
            0
        )
        or 0
    )
    
    interval_skala_kg = float(
        st.session_state.tb_saved_data.get(
            "interval_skala",
            0
        )
        or 0
    )
    
    st.session_state[
        "tb_satuan_kapasitas_max"
    ] = satuan
    
    if is_neraca_name(nama_alat):
    
        st.session_state[
            "tb_kapasitas_max_neraca_input"
        ] = _format_input_from_kg(
            kapasitas_max_kg,
            satuan
        )
    
        st.session_state[
            "tb_kapasitas_min_neraca_input"
        ] = _format_input_from_kg(
            kapasitas_min_kg,
            satuan
        )
    
        st.session_state[
            "tb_interval_skala_neraca_kg"
        ] = interval_skala_kg
    
        st.session_state[
            "tb_kelas"
        ] = "III"
    
    else:
    
        st.session_state[
            "tb_kapasitas_max_input"
        ] = _format_input_from_kg(
            kapasitas_max_kg,
            satuan
        )
    
        st.session_state[
            "tb_daya_baca_input"
        ] = _format_input_from_kg(
            daya_baca_kg,
            satuan
        )
    
        st.session_state[
            "tb_interval_skala_input"
        ] = _format_input_from_kg(
            interval_skala_kg,
            satuan
        )
    
        st.session_state[
            "tb_kapasitas_min_kg"
        ] = kapasitas_min_kg
    
    if is_timbangan_meja_name(nama_alat):
    
        kelas_meja = str(
            st.session_state.tb_saved_data.get(
                "kelas",
                "III"
            )
            or "III"
        ).strip()
    
        if kelas_meja not in ["III", "IIII"]:
            kelas_meja = "III"
    
        st.session_state[
            "tb_kelas_meja"
        ] = kelas_meja
    
    st.session_state[
        "tb_kelas"
    ] = str(
        st.session_state.tb_saved_data.get(
            "kelas",
            "III"
        )
        or "III"
    ).strip()
    
    st.session_state[
        "tb_metode_pengujian"
    ] = str(
        st.session_state.tb_saved_data.get(
            "metode",
            "Perbandingan Langsung"
        )
        or "Perbandingan Langsung"
    ).strip()
    
    st.session_state[
        "tb_at_standar"
    ] = str(
        st.session_state.tb_saved_data.get(
            "at_standar",
            "M2"
        )
        or "M2"
    ).strip()
    
    st.session_state[
        "tb_lokasi_pengujian"
    ] = str(
        st.session_state.tb_saved_data.get(
            "lokasi",
            "Perusahaan"
        )
        or "Perusahaan"
    ).strip()
    
    jumlah_titik = (
        st.session_state.tb_saved_data.get(
            "jumlah_titik_uji"
        )
    )
    
    if jumlah_titik in [3, 5]:
        st.session_state[
            "tb_jumlah_titik_kebenaran"
        ] = int(jumlah_titik)
    # =====================================================
    # TANGGAL BARU
    # =====================================================
    hari_ini = datetime.now().date()

    st.session_state[
        "tb_tanggal_pengujian"
    ] = hari_ini

    st.session_state[
        "tb_tanggal_tanda_tangan"
    ] = hari_ini

    # =====================================================
    # NOMOR DOKUMEN BARU
    # =====================================================
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

    st.session_state[
        "tb_nomor_sertifikat"
    ] = nomor_sertifikat_baru

    st.session_state[
        "tb_nomor_order"
    ] = nomor_order_baru

    st.session_state.tb_saved_data[
        "nomor_sertifikat"
    ] = nomor_sertifikat_baru

    st.session_state.tb_saved_data[
        "nomor_order"
    ] = nomor_order_baru

    # Hapus file generated lama
    st.session_state.tb_generated_files = {}

    # Kembali ke input data
    st.session_state[
        "tb_next_mode"
    ] = "📝 Input Data Pengujian"

def gunakan_data_lama_untuk_edit_timbangan(
    alat,
    perusahaan,
    pengujian
):
    """
    Memuat data pengujian lama ke form Timbangan
    dan mengaktifkan mode edit.
    """

    detail = (
        pengujian.get("data_pengujian")
        or {}
    )

    # =====================================================
    # BERSIHKAN WIDGET HASIL PENGUJIAN LAMA
    # =====================================================
    prefixes_widget_hasil = [
        "tb_muatan_uji_",
        "tb_penunjukan_kebenaran_",
        "tb_pengamatan_penunjukan_",
        "tb_hasil_kebenaran_",
        "tb_cek_kebenaran_",
        "tb_neraca_muatan_disabled_",
        "tb_neraca_penunjukan_disabled_",
        "tb_neraca_bkd_disabled_",
        "tb_neraca_pengamatan_disabled_",
        "tb_neraca_hasil_disabled_",
        "tb_neraca_cek_disabled_",
        "tb_eksen_",
        "tb_repet_",
    ]

    for key in list(
        st.session_state.keys()
    ):
        if any(
            key.startswith(prefix)
            for prefix in prefixes_widget_hasil
        ):
            st.session_state.pop(
                key,
                None
            )

    # =====================================================
    # AKTIFKAN MODE EDIT
    # =====================================================
    st.session_state[
        "tb_edit_pengujian_id"
    ] = pengujian["id"]

    # =====================================================
    # IDENTITAS PERUSAHAAN
    # =====================================================
    nama_perusahaan = str(
        perusahaan.get(
            "nama_perusahaan",
            ""
        )
        or ""
    ).strip()

    alamat = str(
        perusahaan.get(
            "alamat",
            ""
        )
        or ""
    ).strip()
    # =====================================================
    # SIMPAN IDENTITAS ASLI UNTUK MODE EDIT PERUSAHAAN
    # =====================================================
    
    st.session_state[
        "tb_perusahaan_id_lama"
    ] = perusahaan.get("id")
    
    st.session_state[
        "tb_uttp_id_lama"
    ] = alat.get("id")
    
    st.session_state[
        "tb_nama_perusahaan_lama"
    ] = nama_perusahaan
    
    st.session_state[
        "tb_alamat_perusahaan_lama"
    ] = alamat
    
    # Saat pertama masuk mode Edit,
    # default tidak mengubah perusahaan.
    st.session_state[
        "tb_aksi_perusahaan_edit"
    ] = "Gunakan perusahaan saat ini"
    # =====================================================
    # DATA PENERA
    # =====================================================
    nama_penera = str(
        pengujian.get(
            "penera_1",
            ""
        )
        or ""
    ).strip()
    nama_penera_2 = str(
        pengujian.get(
            "penera_2",
            ""
        )
        or ""
    ).strip()
    nip_penera = ""
    golongan_penera = ""

    df_penera = st.session_state.get(
        "tb_data_penera"
    )

    if (
        df_penera is not None
        and not df_penera.empty
        and nama_penera
    ):
        row_penera = df_penera[
            df_penera["Nama"]
            .astype(str)
            .str.strip()
            == nama_penera
        ]

        if not row_penera.empty:
            penera_data = row_penera.iloc[0]

            nip_penera = str(
                penera_data.get(
                    "NIP",
                    ""
                )
                or ""
            ).strip()

            golongan_penera = str(
                penera_data.get(
                    "Golongan",
                    ""
                )
                or ""
            ).strip()

    # =====================================================
    # SAVED DATA
    # =====================================================
    st.session_state.tb_saved_data = {

        "pemilik": nama_perusahaan,
        "alamat": alamat,

        "nama_alat": (
            alat.get("jenis_uttp")
            or detail.get("nama_alat")
            or ""
        ),

        "merek": (
            alat.get("merk")
            or ""
        ),

        "model": (
            alat.get("tipe")
            or detail.get("model")
            or ""
        ),

        "no_seri": (
            alat.get("nomor_seri")
            or ""
        ),

        "kapasitas_max": detail.get(
            "kapasitas_max",
            0
        ),

        "kapasitas_min": detail.get(
            "kapasitas_min",
            0
        ),

        "daya_baca": detail.get(
            "daya_baca",
            0
        ),

        "interval_skala": detail.get(
            "interval_skala",
            0
        ),

        "satuan": detail.get(
            "satuan",
            "kg"
        ),

        "kelas": detail.get(
            "kelas",
            "III"
        ),

        "suhu": detail.get(
            "suhu",
            "Ambient"
        ),

        "kelembaban": detail.get(
            "kelembaban",
            "Ambient"
        ),

        "metode": detail.get(
            "metode",
            ""
        ),

        "at_standar": detail.get(
            "at_standar",
            ""
        ),

        "lokasi": detail.get(
            "lokasi",
            "Perusahaan"
        ),

        "nama_penera": nama_penera,
        "nip_penera": nip_penera,
        "golongan_penera": golongan_penera,
        "nama_penera_2": nama_penera_2,
        "jumlah_titik_uji": detail.get(
            "jumlah_titik_uji"
        ),

        "hasil_pengujian": detail.get(
            "hasil_kebenaran",
            []
        ),

        "repetability": detail.get(
            "repetability",
            []
        ),

        "repetability_sederhana": detail.get(
            "repetability_sederhana",
            False
        ),

        "eksentrisitas": detail.get(
            "eksentrisitas",
            []
        ),

        "penyetelan_nol": detail.get(
            "penyetelan_nol",
            []
        ),

        "visual": detail.get(
            "visual",
            {}
        ),

        "daftar_alat_standar_peminjaman": (
            detail.get(
                "daftar_alat_standar_peminjaman",
                []
            )
        ),

        "tanggal": pengujian.get(
            "tanggal_pengujian"
        ),

        "tanggal_tanda_tangan": (
            pengujian.get(
                "tanggal_sertifikat"
            )
        ),

        "keterangan": pengujian.get(
            "jenis_pengujian",
            "Tera Ulang"
        ),

        "nomor_order": pengujian.get(
            "nomor_order",
            ""
        ),

        "nomor_sertifikat": (
            pengujian.get(
                "nomor_sertifikat",
                ""
            )
        ),

        "berlaku_sampai": (
            pengujian.get(
                "berlaku_sampai"
            )
        ),
    }

    # =====================================================
    # SINKRONKAN WIDGET FORM
    # =====================================================
    satuan = str(
        detail.get(
            "satuan",
            "kg"
        )
        or "kg"
    ).strip()

    if satuan not in ["kg", "g"]:
        satuan = "kg"

    nama_alat = str(
        alat.get("jenis_uttp")
        or detail.get("nama_alat")
        or "Timbangan Elektronik"
    ).strip()

    st.session_state[
        "tb_nama_alat"
    ] = nama_alat
    st.session_state[
        "tb_merek"
    ] = str(
        alat.get("merk")
        or ""
    ).strip()
    
    st.session_state[
        "tb_model"
    ] = str(
        alat.get("tipe")
        or detail.get("model")
        or ""
    ).strip()
    
    st.session_state[
        "tb_no_seri"
    ] = str(
        alat.get("nomor_seri")
        or ""
    ).strip()
    st.session_state[
        "tb_nama_perusahaan"
    ] = nama_perusahaan

    st.session_state[
        "tb_alamat_input"
    ] = alamat

    st.session_state[
        "tb_perusahaan_select"
    ] = nama_perusahaan

    st.session_state[
        "tb_manual_perusahaan"
    ] = False

    st.session_state[
        "tb_satuan_kapasitas_max"
    ] = satuan

    kapasitas_max_kg = float(
        detail.get(
            "kapasitas_max",
            0
        )
        or 0
    )
    # =====================================================
    # SIMPAN KAPASITAS ASLI SAAT MASUK MODE EDIT
    # =====================================================
    st.session_state[
        "tb_kapasitas_max_edit_asli_kg"
    ] = kapasitas_max_kg
    
    st.session_state[
        "tb_paksa_hitung_ulang_uji"
    ] = False
    kapasitas_min_kg = float(
        detail.get(
            "kapasitas_min",
            0
        )
        or 0
    )

    daya_baca_kg = float(
        detail.get(
            "daya_baca",
            0
        )
        or 0
    )

    interval_skala_kg = float(
        detail.get(
            "interval_skala",
            0
        )
        or 0
    )

    # =====================================================
    # NERACA OBAT
    # =====================================================
    if is_neraca_name(
        nama_alat
    ):
        st.session_state[
            "tb_kapasitas_max_neraca_input"
        ] = _format_input_from_kg(
            kapasitas_max_kg,
            satuan
        )

        st.session_state[
            "tb_kapasitas_min_neraca_input"
        ] = _format_input_from_kg(
            kapasitas_min_kg,
            satuan
        )

        st.session_state[
            "tb_interval_skala_neraca_kg"
        ] = interval_skala_kg

        st.session_state[
            "tb_kelas"
        ] = "III"

    # =====================================================
    # SELAIN NERACA
    # =====================================================
    else:
        st.session_state[
            "tb_kapasitas_max_input"
        ] = _format_input_from_kg(
            kapasitas_max_kg,
            satuan
        )

        st.session_state[
            "tb_daya_baca_input"
        ] = _format_input_from_kg(
            daya_baca_kg,
            satuan
        )

        st.session_state[
            "tb_interval_skala_input"
        ] = _format_input_from_kg(
            interval_skala_kg,
            satuan
        )

        st.session_state[
            "tb_kapasitas_min_kg"
        ] = kapasitas_min_kg

    # =====================================================
    # TIMBANGAN MEJA
    # =====================================================
    if is_timbangan_meja_name(
        nama_alat
    ):
        kelas_meja = str(
            detail.get(
                "kelas",
                "III"
            )
            or "III"
        ).strip()

        if kelas_meja not in [
            "III",
            "IIII"
        ]:
            kelas_meja = "III"

        st.session_state[
            "tb_kelas_meja"
        ] = kelas_meja

    # =====================================================
    # KELAS
    # =====================================================
    st.session_state[
        "tb_kelas"
    ] = str(
        detail.get(
            "kelas",
            "III"
        )
        or "III"
    ).strip()

    # =====================================================
    # JENIS PENGUJIAN
    # =====================================================
    st.session_state[
        "tb_keterangan"
    ] = str(
        pengujian.get(
            "jenis_pengujian",
            "Tera Ulang"
        )
        or "Tera Ulang"
    ).strip()

    # =====================================================
    # METODE & AT STANDAR
    # =====================================================
    st.session_state[
        "tb_metode_pengujian"
    ] = str(
        detail.get(
            "metode",
            "Perbandingan Langsung"
        )
        or "Perbandingan Langsung"
    ).strip()

    st.session_state[
        "tb_at_standar"
    ] = str(
        detail.get(
            "at_standar",
            "M2"
        )
        or "M2"
    ).strip()

    # =====================================================
    # LOKASI
    # =====================================================
    st.session_state[
        "tb_lokasi_pengujian"
    ] = str(
        detail.get(
            "lokasi",
            "Perusahaan"
        )
        or "Perusahaan"
    ).strip()

    # =====================================================
    # PENERA
    # =====================================================
    st.session_state[
        "tb_penera_select"
    ] = nama_penera

    st.session_state[
        "tb_nama_penera"
    ] = nama_penera

    st.session_state[
        "tb_nip_penera"
    ] = nip_penera

    st.session_state[
        "tb_golongan_penera"
    ] = golongan_penera

    st.session_state[
        "tb_manual_penera"
    ] = False
    st.session_state[
        "tb_penera_2_select"
    ] = nama_penera_2
    # =====================================================
    # TANGGAL
    # =====================================================
    st.session_state[
        "tb_tanggal_pengujian"
    ] = _parse_date_safe(
        pengujian.get(
            "tanggal_pengujian"
        )
    )

    st.session_state[
        "tb_tanggal_tanda_tangan"
    ] = _parse_date_safe(
        pengujian.get(
            "tanggal_sertifikat"
        )
    )

    # =====================================================
    # JUMLAH TITIK UJI
    # =====================================================
    jumlah_titik = detail.get(
        "jumlah_titik_uji"
    )

    if jumlah_titik in [
        3,
        5
    ]:
        st.session_state[
            "tb_jumlah_titik_kebenaran"
        ] = int(
            jumlah_titik
        )

    # =====================================================
    # NOMOR DOKUMEN
    # =====================================================
    st.session_state[
        "tb_nomor_sertifikat"
    ] = str(
        pengujian.get(
            "nomor_sertifikat",
            ""
        )
        or ""
    )

    st.session_state[
        "tb_nomor_order"
    ] = str(
        pengujian.get(
            "nomor_order",
            ""
        )
        or ""
    )
    daftar_alat_standar = (
        detail.get(
            "daftar_alat_standar_peminjaman",
            []
        )
        or []
    )
    
    st.session_state[
        "tb_jumlah_baris_alat_standar"
    ] = max(
        1,
        len(daftar_alat_standar)
    )
    # Bersihkan state widget alat standar lama
    for key in list(st.session_state.keys()):
        if (
            key.startswith("tb_jenis_alat_standar_")
            or key.startswith("tb_jumlah_alat_standar_")
        ):
            st.session_state.pop(key, None)
    # Bersihkan file lama
    st.session_state.tb_generated_files = {}

    # Kembali ke input
    st.session_state[
        "tb_next_mode"
    ] = "📝 Input Data Pengujian"
def find_asset_file(filename):
    """Mencari aset pada folder standar proyek dan lokasi modul."""
    candidates = [
        ASSETS_DIR / filename,
        Path(__file__).resolve().parent / filename,
        PROJECT_ROOT / "modules" / "timbangan" / filename,
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    # Lokasi standar untuk pesan kesalahan jika file belum tersedia.
    return ASSETS_DIR / filename


TABEL_BKD_PATH = find_asset_file("tabel_bkd.png")

def bersihkan_nama_file(value):
    text = str(value or "").strip()

    # Hapus karakter yang tidak diperbolehkan pada nama file
    text = re.sub(r'[\\/:*?"<>|]', "", text)

    # Rapikan spasi
    text = re.sub(r"\s+", " ", text)

    return text


def format_nama_file_dokumen(data, jenis_dokumen):
    pemilik = bersihkan_nama_file(
        data.get("pemilik", "Tanpa Pemilik")
    )
    singkatan_alat = {
        "Timbangan Elektronik": "TE",
        "Timbangan Pegas": "TP",
        "Timbangan Bobot Ingsut": "TBI",
        "Timbangan Centisimal": "CS",
        "Timbangan Sentisimal": "CS",
        "Timbangan Neraca": "TN",
        "Timbangan Neraca Obat": "TN",
        "Timbangan Meja": "TM",
    }
    nama_alat_asli = str(
        data.get("nama_alat", "Timbangan")
    ).strip()

    nama_alat = singkatan_alat.get(
        nama_alat_asli,
        bersihkan_nama_file(nama_alat_asli)
    )

    nama_penera = bersihkan_nama_file(
        data.get("nama_penera", "Tanpa Penera")
    )

    tanggal_raw = (
        data.get("tanggal")
        or data.get("tanggal_penera")
        or datetime.now().strftime("%Y-%m-%d")
    )

    try:
        tanggal_obj = datetime.strptime(
            str(tanggal_raw),
            "%Y-%m-%d"
        )

        bulan = [
            "JANUARI", "FEBRUARI", "MARET", "APRIL",
            "MEI", "JUNI", "JULI", "AGUSTUS",
            "SEPTEMBER", "OKTOBER", "NOVEMBER", "DESEMBER"
        ]

        tanggal_text = (
            f"{tanggal_obj.day} "
            f"{bulan[tanggal_obj.month - 1]} "
            f"{tanggal_obj.year}"
        )

    except (TypeError, ValueError):
        tanggal_text = bersihkan_nama_file(
            tanggal_raw
        )

    return (
        f"{jenis_dokumen}_"
        f"{pemilik}_"
        f"{nama_alat}_"
        f"{nama_penera}_"
        f"{tanggal_text}.pdf"
    )
def determine_class(max_kg, e):
    """
    Menentukan kelas timbangan berdasarkan:
    n = Max / e

    Aturan:
    - n < 1000              → Kelas IIII
    - 1000 s.d. 10000       → Kelas III
    - >10000 s.d. 100000    → Kelas II
      khusus Max > 75 kg    → Kelas III
    - >100000               → Kelas I
    """

    if max_kg <= 0 or e <= 0:
        return (
            "",
            0,
            "Masukkan nilai Kapasitas Maksimum "
            "dan Interval Skala terlebih dahulu"
        )

    n = max_kg / e

    # Kelas IIII
    if n < 1000:
        return (
            "IIII",
            10 * e,
            f"OK (n = {n:.0f} → Kelas IIII)"
        )

    # Kelas III
    if 1000 <= n <= 10000:
        return (
            "III",
            20 * e,
            f"OK (n = {n:.0f} → Kelas III)"
        )

    # Kelas II
    if 10000 < n <= 100000:
        if max_kg > 75:
            return (
                "III",
                20 * e,
                f"OK (n = {n:.0f}, "
                f"Max > 75 kg → Kelas III)"
            )

        return (
            "II",
            50 * e,
            f"OK (n = {n:.0f} → Kelas II)"
        )

    # Kelas I
    if n > 100000:
        return (
            "I",
            100 * e,
            f"OK (n = {n:.0f} → Kelas I)"
        )

    return (
        "",
        0,
        f"Tidak terdefinisi (n = {n:.0f})"
    )

from decimal import Decimal, InvalidOperation
def convert_to_kg(value_str, satuan):
    """Konversi nilai string/angka dengan satuan ke kg."""
    if value_str is None:
        return 0.0

    if isinstance(value_str, (int, float)):
        val = float(value_str)
    else:
        value_str = str(value_str).strip()
        if not value_str:
            return 0.0
        try:
            val = float(value_str.replace(',', '.'))
        except ValueError:
            return 0.0

    if satuan == "g":
        val /= 1000.0
    return val
def kg_to_satuan(value_kg, satuan=None):
    """
    Mengubah nilai dari kg ke satuan tampilan.
    Jika satuan = g, maka kg dikali 1000.
    Jika satuan = kg, tetap.
    """
    try:
        value_kg = float(value_kg)
    except (TypeError, ValueError):
        value_kg = 0.0

    if satuan is None:
        satuan = st.session_state.get("tb_satuan_kapasitas_max", "kg")

    if satuan == "g":
        return value_kg * 1000

    return value_kg


def satuan_to_kg(value, satuan=None):
    """
    Mengubah nilai dari satuan tampilan ke kg.
    Jika satuan = g, maka dibagi 1000.
    Jika satuan = kg, tetap.
    """
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0.0

    if satuan is None:
        satuan = st.session_state.get("tb_satuan_kapasitas_max", "kg")

    if satuan == "g":
        return value / 1000

    return value
def get_decimal_places_from_daya_baca():
    """
    Menentukan jumlah angka desimal berdasarkan daya baca dalam satuan kg.
    Contoh:
    daya baca 0.001 kg -> 3 desimal
    daya baca 0.02 kg  -> 2 desimal
    daya baca 1 g      -> 0.001 kg -> 3 desimal
    daya baca 20 g     -> 0.02 kg  -> 2 desimal
    """
    raw = str(st.session_state.get("tb_daya_baca_input", "")).strip().replace(",", ".")
    satuan = st.session_state.get("tb_satuan_kapasitas_max", "kg")

    if not raw:
        return 0

    try:
        d = Decimal(raw)
    except InvalidOperation:
        return 0

    if d <= 0:
        return 0

    if satuan == "g":
        d = d / Decimal("1000")

    d = d.normalize()
    return max(0, -d.as_tuple().exponent)


def format_angka_id(value, decimals=0):
    """
    Format angka Indonesia.
    Contoh:
    50.0 dengan 3 desimal -> 50,000
    0.5 dengan 2 desimal  -> 0,50
    """
    return f"{value:.{decimals}f}".replace(".", ",")


def get_decimal_places_from_number(value):
    """
    Menentukan jumlah angka desimal dari nilai numerik.
    Dipakai untuk format tampilan sesuai daya baca pada satuan aktif.
    Contoh:
    0.001 -> 3
    0.02  -> 2
    1     -> 0
    """
    try:
        d = Decimal(str(value)).normalize()
        return max(0, -d.as_tuple().exponent)
    except (InvalidOperation, ValueError, TypeError):
        return 0
def get_input_kg(field_name, default=0.0):
    """Ambil input modul timbangan lalu konversi ke kg."""
    state_key = (
        field_name
        if str(field_name).startswith("tb_")
        else f"tb_{field_name}"
    )
    satuan = st.session_state.get(
        "tb_satuan_kapasitas_max",
        "kg",
    )
    nilai = convert_to_kg(
        st.session_state.get(state_key, ""),
        satuan,
    )
    return nilai if nilai > 0 else default


def tampilkan_dalam_satuan_aktif(nilai_kg):
    """Tampilkan nilai kg dalam satuan aktif user."""
    satuan = st.session_state.get('tb_satuan_kapasitas_max', 'kg')
    nilai = nilai_kg * 1000 if satuan == "g" else nilai_kg
    return f"{nilai:g}".replace('.', ',')


def add_one_year_safe(tanggal_obj):
    """Tambah 1 tahun dengan aman, termasuk untuk 29 Februari."""
    try:
        return tanggal_obj.replace(year=tanggal_obj.year + 1)
    except ValueError:
        return tanggal_obj.replace(year=tanggal_obj.year + 1, month=2, day=28)
    
def is_neraca_name(value):
    """True jika nama alat adalah Neraca."""
    return str(value or "").strip().lower() in {
        "neraca obat",
        "timbangan neraca obat",
    }

def is_timbangan_meja_name(value):
    return (
        str(value or "")
        .strip()
        .lower()
        == "timbangan meja"
    )
    
def nilai_berbeda(a, b, toleransi=1e-12):
    """Membandingkan dua nilai float dengan toleransi kecil."""
    try:
        return abs(float(a) - float(b)) > toleransi
    except (TypeError, ValueError):
        return False

# ============================================================
# RESET HASIL UJI JIKA KAPASITAS MAKSIMUM BERUBAH SAAT EDIT
# ============================================================
def reset_hasil_uji_jika_kapasitas_berubah():

    # Hanya berlaku saat Edit Pengujian
    if not st.session_state.get(
        "tb_edit_pengujian_id"
    ):
        return

    saved_data = st.session_state.get(
        "tb_saved_data",
        {}
    )

    if not saved_data:
        return

    nama_alat = str(
        st.session_state.get(
            "tb_nama_alat",
            saved_data.get(
                "nama_alat",
                ""
            )
        )
        or ""
    ).strip()

    satuan = st.session_state.get(
        "tb_satuan_kapasitas_max",
        "kg"
    )

    # ========================================================
    # AMBIL KAPASITAS YANG SEDANG DIINPUT USER
    # ========================================================
    if is_neraca_name(nama_alat):

        kapasitas_raw = (
            st.session_state.get(
                "tb_kapasitas_max_neraca_input",
                ""
            )
        )

    else:

        kapasitas_raw = (
            st.session_state.get(
                "tb_kapasitas_max_input",
                ""
            )
        )

    kapasitas_baru_kg = convert_to_kg(
        kapasitas_raw,
        satuan
    )

    try:
        kapasitas_lama_kg = float(
            saved_data.get(
                "kapasitas_max",
                0
            )
            or 0
        )
    except (TypeError, ValueError):
        kapasitas_lama_kg = 0.0

    # Belum ada nilai yang valid
    if kapasitas_baru_kg <= 0:
        return

    # Tidak berubah
    if not nilai_berbeda(
        kapasitas_baru_kg,
        kapasitas_lama_kg
    ):
        return

    # ========================================================
    # KAPASITAS BERUBAH
    # DATA PENGUJIAN LAMA TIDAK BOLEH DIPAKAI LAGI
    # ========================================================
    saved_data[
        "kapasitas_max"
    ] = kapasitas_baru_kg

    saved_data[
        "hasil_pengujian"
    ] = []

    saved_data[
        "eksentrisitas"
    ] = []

    saved_data[
        "repetability"
    ] = []

    # ========================================================
    # HAPUS WIDGET HASIL UJI LAMA
    # ========================================================
    prefixes_hasil = [
        "tb_muatan_uji_",
        "tb_penunjukan_kebenaran_",
        "tb_pengamatan_penunjukan_",
        "tb_hasil_kebenaran_",
        "tb_cek_kebenaran_",
        "tb_neraca_muatan_disabled_",
        "tb_neraca_penunjukan_disabled_",
        "tb_neraca_bkd_disabled_",
        "tb_neraca_pengamatan_disabled_",
        "tb_neraca_hasil_disabled_",
        "tb_neraca_cek_disabled_",
        "tb_eksen_",
        "tb_repet_",
    ]

    for key in list(
        st.session_state.keys()
    ):
        if any(
            key.startswith(prefix)
            for prefix in prefixes_hasil
        ):
            st.session_state.pop(
                key,
                None
            )
def update_class():
    """
    Memperbarui kelas dan minimum menimbang.

    Khusus Neraca Obat:
    - kelas selalu III;
    - minimum menimbang diinput manual;
    - daya baca dan interval skala verifikasi tidak digunakan.
    """
    nama_alat_aktif = (
        st.session_state.get("tb_nama_alat")
        or st.session_state.get("tb_saved_data", {}).get(
            "nama_alat",
            "Timbangan Elektronik"
        )
    )

    satuan = st.session_state.get(
        "tb_satuan_kapasitas_max",
        "kg"
    )
    
    # Jika sedang Edit Pengujian dan kapasitas berubah,
    # jangan gunakan hasil pengujian lama.
    reset_hasil_uji_jika_kapasitas_berubah()

    if is_neraca_name(nama_alat_aktif):
        max_raw = st.session_state.get(
            "tb_kapasitas_max_neraca_input",
            ""
        )
        min_raw = st.session_state.get(
            "tb_kapasitas_min_neraca_input",
            ""
        )
        max_kg = convert_to_kg(max_raw, satuan)
        min_kg = convert_to_kg(min_raw, satuan)
        interval_kg = max_kg / 10000.0 if max_kg > 0 else 0.0

        st.session_state["tb_kelas"] = "III"
        st.session_state["tb_kelas_status"] = (
            "Neraca Obat otomatis Kelas III"
        )
        st.session_state["tb_kapasitas_min_kg"] = (
            min_kg if min_kg > 0 else 0.0
        )
        st.session_state["tb_interval_skala_neraca_kg"] = interval_kg
        return
    
    # ============================================================
    # KHUSUS TIMBANGAN MEJA
    # ============================================================
    if is_timbangan_meja_name(nama_alat_aktif):

        satuan = st.session_state.get(
            "tb_satuan_kapasitas_max",
            "kg"
        )

        max_raw = str(
            st.session_state.get(
                "tb_kapasitas_max_input",
                ""
            )
        ).strip()

        max_kg = convert_to_kg(
            max_raw,
            satuan
        )

        # e = Maksimum / 1000
        e_kg = (
            max_kg / 1000.0
            if max_kg > 0
            else 0.0
        )

        kelas = st.session_state.get(
            "tb_kelas_meja",
            "III"
        )

        if kelas not in ["III", "IIII"]:
            kelas = "III"

        # Minimum menimbang
        if kelas == "III":
            min_kg = 20 * e_kg
        else:
            min_kg = 10 * e_kg

        # Simpan e sesuai satuan aktif
        if satuan == "g":
            e_input = e_kg * 1000.0
        else:
            e_input = e_kg

        st.session_state[
            "tb_interval_skala_input"
        ] = e_input

        st.session_state[
            "tb_kapasitas_min_kg"
        ] = min_kg

        st.session_state[
            "tb_kelas"
        ] = kelas

        st.session_state[
            "tb_metode_pengujian"
        ] = "Perbandingan Langsung"

        st.session_state[
            "tb_at_standar"
        ] = "M2"

        st.session_state[
            "tb_kelas_status"
        ] = f"Timbangan Meja Kelas {kelas}"

        return
        
    max_raw = str(
        st.session_state.get("tb_kapasitas_max_input", "")
    ).strip()
    e_raw = str(
        st.session_state.get("tb_interval_skala_input", "")
    ).strip()

    max_kg = convert_to_kg(max_raw, satuan)
    e_kg = convert_to_kg(e_raw, satuan)

    cls, min_kg, status = determine_class(max_kg, e_kg)

    if min_kg == 0 and cls and e_kg > 0:
        faktor = {
            "I": 100,
            "II": 50,
            "III": 20,
            "IIII": 10,
        }
        min_kg = faktor.get(cls, 20) * e_kg

    st.session_state["tb_kelas"] = cls if cls else "III"
    st.session_state["tb_kelas_status"] = status
    st.session_state["tb_kapasitas_min_kg"] = (
        min_kg if min_kg > 0 else 0.0
    )


def bulan_ke_romawi(bulan):
    romawi = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
    return romawi[bulan-1]

def generate_nomor_sertifikat(tanggal):
    if isinstance(tanggal, str):
        t = datetime.strptime(tanggal, '%Y-%m-%d')
    else:
        t = tanggal
    return f"500.2.3.15/0000/BID-K/{bulan_ke_romawi(t.month)}/{t.year}"

def generate_nomor_order(tanggal):
    if isinstance(tanggal, str):
        t = datetime.strptime(tanggal, '%Y-%m-%d')
    else:
        t = tanggal
    return f"0000/SCD/{bulan_ke_romawi(t.month)}/{t.year}"

# ===== BACA DATA PERUSAHAAN =====
def format_tanggal_indonesia(tanggal_str):
    """Mengubah format YYYY-MM-DD menjadi 'DD Month YYYY' (contoh: 8 Juni 2026)"""
    if not tanggal_str:
        return ""
    try:
        if isinstance(tanggal_str, str):
            t = datetime.strptime(tanggal_str, '%Y-%m-%d')
        else:
            t = tanggal_str
        bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
                 "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
        return f"{t.day} {bulan[t.month-1]} {t.year}"
    except:
        return tanggal_str

def _find_data_file(*filenames):
    """Mencari file data pada folder data, root proyek, lalu folder halaman."""
    search_dirs = [
        PROJECT_ROOT / "data",
        PROJECT_ROOT,
        Path(__file__).resolve().parent,
    ]

    for directory in search_dirs:
        for filename in filenames:
            candidate = directory / filename
            if candidate.exists():
                return candidate

    return None


def _read_excel_compatible(path):
    """Membaca xlsx/xls tanpa memaksa engine yang salah."""
    if path.suffix.lower() == ".xlsx":
        return pd.read_excel(path, engine="openpyxl")

    return pd.read_excel(path)


def _normalize_excel_identifier(value):
    """Mencegah NIP numerik berubah menjadi teks berakhiran .0."""
    if pd.isna(value):
        return ""

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return str(value).strip()

@st.cache_data(ttl=60)
def load_data_perusahaan():
    """
    Membaca master perusahaan langsung dari Supabase.
    """

    try:
        supabase = get_supabase()

        response = (
            supabase
            .table("perusahaan")
            .select(
                "id, nama_perusahaan, alamat, "
                "kecamatan, telepon, email"
            )
            .order("nama_perusahaan")
            .execute()
        )

        data = response.data or []

        if not data:
            return pd.DataFrame(
                columns=[
                    "ID",
                    "Nama Perusahaan",
                    "Alamat",
                    "Kecamatan",
                    "Telepon",
                    "Email",
                ]
            )

        df = pd.DataFrame(data)

        df = df.rename(
            columns={
                "id": "ID",
                "nama_perusahaan": "Nama Perusahaan",
                "alamat": "Alamat",
                "kecamatan": "Kecamatan",
                "telepon": "Telepon",
                "email": "Email",
            }
        )

        for col in [
            "Nama Perusahaan",
            "Alamat",
            "Kecamatan",
            "Telepon",
            "Email",
        ]:
            if col not in df.columns:
                df[col] = ""

            df[col] = (
                df[col]
                .fillna("")
                .astype(str)
                .str.strip()
            )

        df = df[
            df["Nama Perusahaan"] != ""
        ].copy()

        df = (
            df
            .sort_values("Nama Perusahaan")
            .reset_index(drop=True)
        )

        return df

    except Exception as exc:
        st.warning(
            "Data perusahaan dari Supabase "
            f"tidak dapat dibaca: {exc}"
        )

        return pd.DataFrame(
            columns=[
                "ID",
                "Nama Perusahaan",
                "Alamat",
                "Kecamatan",
                "Telepon",
                "Email",
            ]
        )
@st.cache_data(ttl=60)
def load_data_penera():
    """
    Membaca data penera aktif langsung dari Supabase.
    """

    try:
        supabase = get_supabase()

        response = (
            supabase
            .table("penera")
            .select(
                "id, nama, nip, golongan, status"
            )
            .eq("status", "aktif")
            .order("nama")
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

        df = pd.DataFrame(data)

        df = df.rename(
            columns={
                "id": "ID",
                "nama": "Nama",
                "nip": "NIP",
                "golongan": "Golongan",
                "status": "Status",
            }
        )

        for col in [
            "Nama",
            "NIP",
            "Golongan",
            "Status",
        ]:
            if col not in df.columns:
                df[col] = ""

            df[col] = (
                df[col]
                .fillna("")
                .astype(str)
                .str.strip()
            )

        df = df[
            df["Nama"] != ""
        ].copy()

        df = (
            df
            .drop_duplicates(
                subset=["Nama", "NIP"]
            )
            .sort_values("Nama")
            .reset_index(drop=True)
        )

        return df

    except Exception as exc:
        st.warning(
            "Data penera dari Supabase "
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

def update_perusahaan_terpilih_tb():
    selected = str(
        st.session_state.get(
            "tb_perusahaan_select",
            ""
        )
    ).strip()

    df_perusahaan = st.session_state.get(
        "tb_data_perusahaan"
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

    alamat_perusahaan = data_perusahaan.get(
        "Alamat",
        ""
    )

    if pd.isna(alamat_perusahaan):
        alamat_perusahaan = ""

    st.session_state["tb_nama_perusahaan"] = selected
    st.session_state["tb_alamat_input"] = str(
        alamat_perusahaan
    ).strip()

    st.session_state["tb_manual_perusahaan"] = False
    
def update_penera_terpilih_tb():
    selected = str(
        st.session_state.get(
            "tb_penera_select",
            ""
        )
    ).strip()

    df_penera = st.session_state.get(
        "tb_data_penera"
    )

    if (
        not selected
        or df_penera is None
        or df_penera.empty
    ):
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

    st.session_state["tb_nama_penera"] = selected
    st.session_state["tb_nip_penera"] = str(
        data_penera.get(
            "NIP",
            ""
        )
    ).strip()

    st.session_state["tb_golongan_penera"] = str(
        data_penera.get(
            "Golongan",
            ""
        )
    ).strip()

    st.session_state["tb_manual_penera"] = False
    
def copy_standar():
    """Salin nilai standar baris ke-2 (indeks 1) ke baris 4, 6, 8 (indeks 3,5,7)."""
    e = st.session_state.get('tb_interval_skala_input', 20)
    key_src = f"tb_standar_1_{e}"
    if key_src in st.session_state:
        val = st.session_state[key_src]
        st.session_state[f"tb_standar_3_{e}"] = val
        st.session_state[f"tb_standar_5_{e}"] = val
        st.session_state[f"tb_standar_7_{e}"] = val

def sync_balas(prev_key, next_key):
    """Salin nilai dari prev_key ke next_key di session state."""
    if prev_key in st.session_state:
        st.session_state[next_key] = st.session_state[prev_key]
        
def get_default_muatan_uji(kelas, e_kg, kapasitas_max_kg):
    """
    Menghasilkan tepat lima titik muatan uji dalam kg.

    Urutan:
    1. Minimum menimbang
    2-4. Titik transisi/fallback
    5. Kapasitas maksimum
    """
    if e_kg <= 0 or kapasitas_max_kg <= 0:
        return [0.0] * 5

    batas_e_01g_kg = 0.0001

    faktor_minimum = {
        "I": 100,
        "III": 20,
        "IIII": 10,
    }

    if kelas == "II":
        faktor_min = (
            50
            if e_kg >= batas_e_01g_kg
            else 20
        )
    else:
        faktor_min = faktor_minimum.get(kelas, 20)

    minimum_kg = min(
        faktor_min * e_kg,
        kapasitas_max_kg,
    )

    if math.isclose(
        minimum_kg,
        kapasitas_max_kg,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        return [kapasitas_max_kg] * 5

    def valid_middle(value):
        return minimum_kg < value < kapasitas_max_kg

    def finalize(middle_candidates):
        """Menjamin tiga titik tengah dan total lima baris."""
        middle = []

        for value in middle_candidates:
            value = round(float(value), 12)
            if valid_middle(value) and value not in middle:
                middle.append(value)

        # Tambahan proporsional hanya jika titik aturan belum cukup.
        if len(middle) < 3:
            for fraction in (0.25, 0.50, 0.75):
                value = round(kapasitas_max_kg * fraction, 12)
                if valid_middle(value) and value not in middle:
                    middle.append(value)
                if len(middle) >= 3:
                    break

        # Grid tambahan untuk kombinasi ekstrem.
        if len(middle) < 3:
            rentang = kapasitas_max_kg - minimum_kg
            for fraction in (0.20, 0.40, 0.60, 0.80):
                value = round(
                    minimum_kg + rentang * fraction,
                    12,
                )
                if valid_middle(value) and value not in middle:
                    middle.append(value)
                if len(middle) >= 3:
                    break

        middle = sorted(middle)

        # Ambil tiga titik yang mempertahankan sebaran.
        if len(middle) > 3:
            selected = [
                middle[0],
                middle[len(middle) // 2],
                middle[-1],
            ]
            middle = sorted(set(selected))

        while len(middle) < 3:
            # Kondisi ini hanya mungkin bila rentang sangat sempit.
            middle.append(middle[-1] if middle else minimum_kg)

        return [
            minimum_kg,
            middle[0],
            middle[1],
            middle[2],
            kapasitas_max_kg,
        ]

    # Kelas II memakai susunan khusus yang sudah disepakati.
    if kelas == "II":
        titik_5000e = 5000 * e_kg
        titik_20000e = 20000 * e_kg
        titik_100000e = 100000 * e_kg

        # Semua titik aturan masih berada di bawah maksimum.
        if valid_middle(titik_100000e):
            return finalize([
                titik_5000e,
                titik_20000e,
                titik_100000e,
            ])

        # 20000e masih dapat digunakan, sedangkan 100000e tidak.
        # Contoh: Max 3000 g, e 0,1 g -> 5; 500; 1000; 2000; 3000 g.
        if valid_middle(titik_20000e):
            titik_sebelum_20000e = titik_20000e * 0.5

            if not (
                titik_5000e
                < titik_sebelum_20000e
                < titik_20000e
            ):
                titik_sebelum_20000e = (
                    titik_5000e + titik_20000e
                ) / 2.0

            return finalize([
                titik_5000e,
                titik_sebelum_20000e,
                titik_20000e,
            ])

        # Jika 20000e dan 100000e melebihi maksimum,
        # baris 3 dan 4 memakai 50% dan 75% maksimum.
        if valid_middle(titik_5000e):
            return finalize([
                titik_5000e,
                0.50 * kapasitas_max_kg,
                0.75 * kapasitas_max_kg,
            ])

        return finalize([
            0.25 * kapasitas_max_kg,
            0.50 * kapasitas_max_kg,
            0.75 * kapasitas_max_kg,
        ])

    faktor_tengah = {
        "I": [50000, 200000, 1000000],
        "III": [500, 1000, 2000],
        "IIII": [50, 200, 1000],
    }.get(kelas, [500, 1000, 2000])

    candidates = [
        faktor * e_kg
        for faktor in faktor_tengah
        if valid_middle(faktor * e_kg)
    ]

    return finalize(candidates)


def hitung_bkd(muatan, interval_skala, kelas, keterangan):
    if interval_skala == 0:
        return 0, 0

    m = muatan / interval_skala

    # Tabel 4.7: BKD dasar untuk Kelas III
    batas = {
        'I'   : [(50000, 0.5), (200000, 1.0), (float('inf'), 1.5)],
        'II'  : [(5000,  0.5), (20000,  1.0), (100000, 1.5)],
        'III' : [(500,   0.5), (2000,   1.0), (10000,  1.5)],
        'IIII': [(50,    0.5), (200,    1.0), (1000,   1.5)],
    }

    koef_dasar = 1.5
    for batas_m, koef in batas.get(kelas, batas['III']):
        if m <= batas_m:
            koef_dasar = koef
            break

    # Tabel 4.8: Multiplier untuk Tera Ulang
    multiplier = 2.0 if keterangan == "Tera Ulang" else 1.0

    koef_final = koef_dasar * multiplier
    bkd_kg     = koef_final * interval_skala

    return koef_final, bkd_kg
def sinkronkan_daya_baca_interval():
    """
    Untuk alat selain Timbangan Elektronik,
    interval skala verifikasi (e) selalu sama dengan daya baca (d).
    """
    nama_alat_aktif = (
        st.session_state.get("tb_nama_alat", "")
    )

    is_elektronik = (
        str(nama_alat_aktif).strip().lower()
        == "timbangan elektronik"
    )

    is_neraca_aktif = is_neraca_name(
        nama_alat_aktif
    )

    if not is_elektronik and not is_neraca_aktif:
        st.session_state["tb_interval_skala_input"] = (
            st.session_state.get(
                "tb_daya_baca_input",
                ""
            )
        )

    update_class()
def _parse_date_safe(value, default=None):
    default = default or datetime.now().date()

    if not value:
        return default

    if isinstance(value, datetime):
        return value.date()

    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return value

    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return default


def _format_input_from_kg(value_kg, unit):
    try:
        value = kg_to_satuan(float(value_kg), unit)
    except (TypeError, ValueError):
        return ""

    if value == 0:
        return ""

    return f"{value:g}".replace(".", ",")


def init_timbangan_state():
    """Inisialisasi state khusus modul timbangan."""
    if "tb_saved_data" not in st.session_state:
        st.session_state.tb_saved_data = {}

    saved = st.session_state.tb_saved_data
    saved_unit = saved.get("satuan", "kg")
    saved_name = saved.get("nama_alat", "Timbangan Elektronik")
    saved_is_neraca = is_neraca_name(
        saved_name
    )

    saved_is_timbangan_meja = is_timbangan_meja_name(
        saved_name
    )
    defaults = {
        "tb_test_results": [],
        "tb_generated_files": {},
        "tb_satuan_kapasitas_max": saved_unit,
        "tb_kelas": saved.get("kelas", "III"),
        "tb_keterangan": saved.get("keterangan", "Tera Ulang"),
        "tb_metode_pengujian": saved.get(
            "metode",
            "Perbandingan Langsung",
        ),
        "tb_at_standar": saved.get("at_standar", "M2"),
        "tb_lokasi_pengujian": saved.get("lokasi", "Perusahaan"),
        "tb_kelas_status": "",
        "tb_min_otomatis": 0,
        "tb_kapasitas_min_kg": saved.get("kapasitas_min", 0.0),
        "tb_interval_skala_neraca_kg": (
            saved.get("interval_skala", 0.0)
            if saved_is_neraca
            else 0.0
        ),
        "tb_nama_perusahaan": saved.get("pemilik", ""),
        "tb_alamat_input": saved.get("alamat", ""),
        "tb_manual_perusahaan": False,
        "tb_nama_penera": saved.get("nama_penera", ""),
        "tb_nip_penera": saved.get("nip_penera", ""),
        "tb_golongan_penera": saved.get("golongan_penera", ""),
        "tb_tampilkan_tabel_bkd": False,
        "tb_mode": "📝 Input Data Pengujian",
        "tb_tanggal_pengujian": _parse_date_safe(
            saved.get("tanggal")
        ),
        "tb_tanggal_tanda_tangan": _parse_date_safe(
            saved.get("tanggal_tanda_tangan")
        ),
        "tb_tambahkan_alat_standar": saved.get(
            "tambahkan_alat_standar",
            False
        ),
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if "tb_data_perusahaan" not in st.session_state:
        st.session_state.tb_data_perusahaan = load_data_perusahaan()

    if "tb_data_penera" not in st.session_state:
        st.session_state.tb_data_penera = load_data_penera()

    if "tb_kapasitas_max_input" not in st.session_state:
        st.session_state.tb_kapasitas_max_input = (
            ""
            if saved_is_neraca
            else _format_input_from_kg(
                saved.get("kapasitas_max", 0),
                saved_unit,
            )
        )

    if "tb_daya_baca_input" not in st.session_state:
        st.session_state.tb_daya_baca_input = (
            ""
            if (
                saved_is_neraca
                or saved_is_timbangan_meja
            )
            else _format_input_from_kg(
                saved.get("daya_baca", 0),
                saved_unit,
            )
        )

    if "tb_kelas_meja" not in st.session_state:
        st.session_state.tb_kelas_meja = (
            saved.get("kelas", "III")
            if saved_is_timbangan_meja
            else "III"
        )
        
    if "tb_interval_skala_input" not in st.session_state:
        st.session_state.tb_interval_skala_input = (
            ""
            if saved_is_neraca
            else _format_input_from_kg(
                saved.get("interval_skala", 0),
                saved_unit,
            )
        )

    if "tb_kapasitas_max_neraca_input" not in st.session_state:
        st.session_state.tb_kapasitas_max_neraca_input = (
            _format_input_from_kg(
                saved.get("kapasitas_max", 0),
                saved_unit,
            )
            if saved_is_neraca
            else ""
        )

    if "tb_kapasitas_min_neraca_input" not in st.session_state:
        st.session_state.tb_kapasitas_min_neraca_input = (
            _format_input_from_kg(
                saved.get("kapasitas_min", 0),
                saved_unit,
            )
            if saved_is_neraca
            else ""
        )

    if "tb_state_initialized" not in st.session_state:
        st.session_state.tb_state_initialized = True

        # Data tersimpan mempertahankan kelas/minimum yang sudah dipilih.
        if not saved:
            update_class()


def reset_form_timbangan():
    """Menghapus state khusus timbangan tanpa mengganggu modul lain."""
    for key in list(st.session_state.keys()):
        if key.startswith("tb_"):
            del st.session_state[key]


def run():
    init_timbangan_state()

    st.caption(
        f"Modul aktif: {Path(__file__).resolve()}"
    )
    st.title("⚖️ Pengujian Timbangan")

    col_nav1, col_nav2 = st.columns(2)

    with col_nav1:
        if st.button(
            "← Kembali ke Home",
            use_container_width=True,
            key="tb_nav_home"
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
    
    # CSS styling
    st.markdown(
        """
        <style>
            .main {
                padding-top: 2rem;
            }
        </style>
        """,
        unsafe_allow_html=True
    )
    # =========================================================
    # PINDAH MODE DARI AKSI RIWAYAT
    # Harus sebelum widget radio dibuat
    # =========================================================
    if "tb_next_mode" in st.session_state:
        st.session_state["tb_mode"] = (
            st.session_state.pop(
                "tb_next_mode"
            )
        )
    # Sidebar navigasi
    with st.sidebar:
        st.header("📋 Menu Navigasi")

        mode = st.radio(
            "Pilih Mode:",
            [
                "📝 Input Data Pengujian",
                "📄 Generate Dokumen",
                "📚 Riwayat Timbangan"
            ],
            key="tb_mode",
            help="Pilih mode yang ingin digunakan."
        )
    if mode == "📝 Input Data Pengujian":
        st.header("Masukkan Data Pengujian")

        # =====================================================
        # MODE EDIT PENGUJIAN
        # =====================================================
        edit_id = st.session_state.get(
            "tb_edit_pengujian_id"
        )
        
        if edit_id:
            st.warning(
                f"✏️ Mode Edit Pengujian Aktif — "
                f"ID Pengujian: {edit_id}"
            )
        
            if st.button(
                "❌ Batal Edit",
                use_container_width=True,
                key="tb_btn_batal_edit"
            ):
                reset_form_timbangan()
                st.rerun()
        # Ambil nilai dari session state untuk digunakan di seluruh blok
        satuan_aktif = st.session_state.get('tb_satuan_kapasitas_max', 'kg')
        e = get_input_kg('interval_skala_input', 0.0)
        kapasitas_max_kg = get_input_kg('kapasitas_max_input', 0.0)
        cls = st.session_state.get('tb_kelas', 'III')
        jns_uji = st.session_state.get('tb_keterangan', 'Tera Ulang')

        # ======================== KOLOM 1-3 ========================
        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("Identitas Pemilik")
        
            # =====================================================
            # MODE PERUSAHAAN SAAT EDIT RIWAYAT
            # =====================================================
            sedang_edit_perusahaan = bool(
                st.session_state.get(
                    "tb_edit_pengujian_id"
                )
            )
            
            # =====================================================
            # DEFAULT MODE PERUSAHAAN
            # Aman juga saat input pengujian baru
            # =====================================================
            aksi_perusahaan_edit = ""
            kunci_perusahaan_lama = False
            edit_perusahaan_lama = False
            ganti_perusahaan_baru = False
            
            
            if sedang_edit_perusahaan:
        
                opsi_aksi_perusahaan = [
                    "Gunakan perusahaan saat ini",
                    "Edit data perusahaan saat ini",
                    "Ganti / tambah perusahaan baru",
                ]
        
                if (
                    st.session_state.get(
                        "tb_aksi_perusahaan_edit"
                    )
                    not in opsi_aksi_perusahaan
                ):
                    st.session_state[
                        "tb_aksi_perusahaan_edit"
                    ] = "Gunakan perusahaan saat ini"
        
                nama_perusahaan_lama = str(
                    st.session_state.get(
                        "tb_nama_perusahaan_lama",
                        ""
                    )
                    or ""
                ).strip()
        
                if nama_perusahaan_lama:
                    st.caption(
                        f"Perusahaan saat ini: "
                        f"**{nama_perusahaan_lama}**"
                    )
        
                st.radio(
                    "Tindakan terhadap perusahaan",
                    options=opsi_aksi_perusahaan,
                    key="tb_aksi_perusahaan_edit",
                )
                aksi_perusahaan_edit = (
                    st.session_state.get(
                        "tb_aksi_perusahaan_edit",
                        "Gunakan perusahaan saat ini"
                    )
                )
        
                kunci_perusahaan_lama = (
                    sedang_edit_perusahaan
                    and aksi_perusahaan_edit
                    == "Gunakan perusahaan saat ini"
                )
                edit_perusahaan_lama = (
                    sedang_edit_perusahaan
                    and aksi_perusahaan_edit
                    == "Edit data perusahaan saat ini"
                )
                
                ganti_perusahaan_baru = (
                    sedang_edit_perusahaan
                    and aksi_perusahaan_edit
                    == "Ganti / tambah perusahaan baru"
                )
                # =====================================================
                # SINKRONISASI SAAT USER MENGGANTI AKSI PERUSAHAAN
                # =====================================================
                
                aksi_sebelumnya = st.session_state.get(
                    "tb_aksi_perusahaan_edit_sebelumnya"
                )
                
                if aksi_sebelumnya != aksi_perusahaan_edit:
                
                    # -------------------------------------------------
                    # GUNAKAN / EDIT PERUSAHAAN LAMA
                    # -------------------------------------------------
                    if aksi_perusahaan_edit in [
                        "Gunakan perusahaan saat ini",
                        "Edit data perusahaan saat ini",
                    ]:
                        st.session_state[
                            "tb_nama_perusahaan"
                        ] = st.session_state.get(
                            "tb_nama_perusahaan_lama",
                            ""
                        )
                
                        st.session_state[
                            "tb_alamat_input"
                        ] = st.session_state.get(
                            "tb_alamat_perusahaan_lama",
                            ""
                        )
                
                        st.session_state[
                            "tb_perusahaan_select"
                        ] = st.session_state.get(
                            "tb_nama_perusahaan_lama",
                            ""
                        )
                
                        st.session_state[
                            "tb_manual_perusahaan"
                        ] = False
                
                    # -------------------------------------------------
                    # GANTI / TAMBAH PERUSAHAAN BARU
                    # -------------------------------------------------
                    elif aksi_perusahaan_edit == (
                        "Ganti / tambah perusahaan baru"
                    ):
                        st.session_state[
                            "tb_nama_perusahaan"
                        ] = ""
                
                        st.session_state[
                            "tb_alamat_input"
                        ] = ""
                
                        st.session_state[
                            "tb_perusahaan_select"
                        ] = ""
                
                        st.session_state[
                            "tb_manual_perusahaan"
                        ] = False
                
                    st.session_state[
                        "tb_aksi_perusahaan_edit_sebelumnya"
                    ] = aksi_perusahaan_edit
            df_perusahaan = st.session_state.get(
                "tb_data_perusahaan"
            )

            if "tb_nama_perusahaan" not in st.session_state:
                st.session_state.tb_nama_perusahaan = str(
                    st.session_state.tb_saved_data.get(
                        "pemilik",
                        ""
                    )
                ).strip()

            if "tb_alamat_input" not in st.session_state:
                st.session_state.tb_alamat_input = str(
                    st.session_state.tb_saved_data.get(
                        "alamat",
                        ""
                    )
                ).strip()

            if "tb_manual_perusahaan" not in st.session_state:
                st.session_state.tb_manual_perusahaan = False

            # =====================================================
            # EDIT DATA PERUSAHAAN SAAT INI
            # =====================================================
            if edit_perusahaan_lama:
            
                st.info(
                    "✏️ Nama dan alamat di bawah ini akan "
                    "memperbarui data perusahaan yang saat ini "
                    "terhubung dengan alat."
                )
            
                st.text_input(
                    "Nama Pemilik / Perusahaan",
                    key="tb_nama_perusahaan",
                    placeholder="Contoh: PT. ABC",
                )
            
                st.text_area(
                    "Alamat",
                    height=90,
                    key="tb_alamat_input",
                    help=(
                        "Ubah alamat jika terdapat koreksi "
                        "pada data perusahaan."
                    ),
                )
            
            
            # =====================================================
            # MODE NORMAL / GANTI PERUSAHAAN
            # =====================================================
            elif (
                df_perusahaan is not None
                and not df_perusahaan.empty
            ):
                all_names = (
                    df_perusahaan["Nama Perusahaan"]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .tolist()
                )

                nama_tersimpan = str(
                    st.session_state.get(
                        "tb_nama_perusahaan",
                        ""
                    )
                ).strip()

                if "tb_perusahaan_select" not in st.session_state:
                    if nama_tersimpan in all_names:
                        st.session_state.tb_perusahaan_select = (
                            nama_tersimpan
                        )
                    else:
                        st.session_state.tb_perusahaan_select = ""

                        if nama_tersimpan:
                            st.session_state.tb_manual_perusahaan = True

                st.selectbox(
                    "Cari & Pilih Nama Perusahaan",
                    options=[""] + all_names,
                    placeholder="Ketik nama perusahaan...",
                    key="tb_perusahaan_select",
                    on_change=update_perusahaan_terpilih_tb,
                    disabled=kunci_perusahaan_lama,
                )

                st.text_area(
                    "Alamat",
                    height=90,
                    key="tb_alamat_input",
                    help=(
                        "Alamat otomatis muncul setelah perusahaan "
                        "dipilih dan tetap dapat diedit."
                    ),
                    disabled=kunci_perusahaan_lama,
                )

                st.checkbox(
                    "Input manual nama perusahaan",
                    key="tb_manual_perusahaan",
                    disabled=kunci_perusahaan_lama,
                )

                if st.session_state.tb_manual_perusahaan:
                    st.text_input(
                        "Nama Pemilik / Perusahaan",
                        key="tb_nama_perusahaan",
                        placeholder="Contoh: PT. ABC",
                        disabled=kunci_perusahaan_lama,
                    )

            else:
                st.info(
                    "📂 File data perusahaan tidak ditemukan. "
                    "Silakan input manual."
                )

                st.text_input(
                    "Nama Pemilik / Perusahaan",
                    key="tb_nama_perusahaan",
                )

                st.text_area(
                    "Alamat",
                    height=90,
                    key="tb_alamat_input",
                )

            pemilik = str(
                st.session_state.get(
                    "tb_nama_perusahaan",
                    ""
                )
            ).strip()

            alamat = str(
                st.session_state.get(
                    "tb_alamat_input",
                    ""
                )
            ).strip()

        with col2:
            st.subheader("Spesifikasi Alat")

            nama_alat_options = [
                "Timbangan Elektronik",
                "Timbangan Bobot Ingsut",
                "Timbangan Neraca Obat",
                "Timbangan Sentisimal",
                "Timbangan Pegas",
                "Timbangan Meja",
            ]

            nama_alat_tersimpan = st.session_state.tb_saved_data.get(
                "nama_alat",
                "Timbangan Elektronik"
            )

            if nama_alat_tersimpan not in nama_alat_options:
                nama_alat_tersimpan = "Timbangan Elektronik"

            nama_alat = st.selectbox(
                "Nama Alat",
                options=nama_alat_options,
                index=nama_alat_options.index(
                    nama_alat_tersimpan
                ),
                key="tb_nama_alat",
                on_change=update_class
            )

            is_neraca = is_neraca_name(
                nama_alat
            )
            
            is_timbangan_meja = is_timbangan_meja_name(
                nama_alat
            )
            
            is_timbangan_elektronik = (
                str(nama_alat).strip().lower()
                == "timbangan elektronik"
            )

            merek = st.text_input(
                "Merek/Buatan",
                value=st.session_state.tb_saved_data.get(
                    "merek",
                    ""
                ),
                placeholder="",
                key="tb_merek",
            )

            # Model / Tipe ditampilkan untuk semua jenis timbangan
            model = st.text_input(
                "Model / Tipe",
                value=st.session_state.tb_saved_data.get(
                    "model",
                    ""
                ),
                key="tb_model"
            )

            no_seri = st.text_input(
                "No. Seri/No. Alat",
                value=st.session_state.tb_saved_data.get(
                    "no_seri",
                    ""
                ),
                placeholder="",
                key="tb_no_seri",
            )

        with col3:
            st.subheader("Kapasitas & Skala")

            if is_neraca:
                # Saat pertama kali beralih ke Neraca Obat, satuan default menjadi gram.
                if st.session_state.get("tb_last_nama_alat_unit") != nama_alat:
                    st.session_state["tb_satuan_kapasitas_max"] = "g"
                    st.session_state["tb_last_nama_alat_unit"] = nama_alat

                st.info(
                    "Neraca Obat otomatis Kelas III. "
                    "Interval skala verifikasi dihitung otomatis: Maksimum / 10.000."
                )

                st.selectbox(
                    "Satuan",
                    options=["g", "kg"],
                    key="tb_satuan_kapasitas_max",
                    on_change=update_class,
                )

                st.text_input(
                    "Maksimum Menimbang",
                    placeholder="Masukkan maksimum menimbang",
                    key="tb_kapasitas_max_neraca_input",
                    on_change=update_class,
                )

                st.text_input(
                    "Minimum Menimbang",
                    placeholder="Masukkan minimum menimbang",
                    key="tb_kapasitas_min_neraca_input",
                    on_change=update_class,
                )

                satuan = st.session_state.get(
                    "tb_satuan_kapasitas_max",
                    "g"
                )

                kapasitas_max_kg = convert_to_kg(
                    st.session_state.get(
                        "tb_kapasitas_max_neraca_input",
                        ""
                    ),
                    satuan
                )
                kapasitas_min_final = convert_to_kg(
                    st.session_state.get(
                        "tb_kapasitas_min_neraca_input",
                        ""
                    ),
                    satuan
                )

                # Interval skala verifikasi Neraca Obat = Maksimum / 10.000.
                interval_skala_kg = (
                    kapasitas_max_kg / 10000.0
                    if kapasitas_max_kg > 0
                    else 0.0
                )
                daya_baca_kg = 0.0
                kelas_final = "III"

                interval_skala_tampil = kg_to_satuan(
                    interval_skala_kg,
                    satuan
                )
                decimal_interval = max(
                    0,
                    get_decimal_places_from_number(interval_skala_tampil)
                )
                st.text_input(
                    "Interval Skala Verifikasi (otomatis)",
                    value=(
                        format_angka_id(interval_skala_tampil, decimal_interval)
                        if interval_skala_kg > 0
                        else ""
                    ),
                    disabled=True,
                    help="Dihitung otomatis dari Maksimum Menimbang / 10.000.",
                    key="tb_interval_skala_neraca_tampil",
                )
                st.caption(
                    f"e = Maksimum / 10.000 = "
                    f"{format_angka_id(interval_skala_tampil, decimal_interval) if interval_skala_kg > 0 else '-'} {satuan}"
                )
                status_kelas = "Neraca Obat otomatis Kelas III"

                st.session_state["tb_kelas"] = "III"
                st.session_state["tb_kelas_status"] = status_kelas
                st.session_state["tb_kapasitas_min_kg"] = (
                    kapasitas_min_final
                )

                if (
                    kapasitas_max_kg > 0
                    and kapasitas_min_final > kapasitas_max_kg
                ):
                    st.warning(
                        "Minimum menimbang tidak boleh lebih besar "
                        "dari maksimum menimbang."
                    )
            elif is_timbangan_meja:
                st.info(
                    "Timbangan Meja hanya Kelas III atau IIII. "
                    "Interval skala verifikasi dihitung otomatis: "
                    "e = Maksimum / 1000."
                )

                st.selectbox(
                    "Satuan",
                    options=["kg", "g"],
                    key="tb_satuan_kapasitas_max",
                    on_change=update_class
                )

                satuan = st.session_state.get(
                    "tb_satuan_kapasitas_max",
                    "kg"
                )

                st.text_input(
                    "Maksimum Menimbang",
                    placeholder="Masukkan maksimum menimbang",
                    key="tb_kapasitas_max_input",
                    on_change=update_class
                )

                kapasitas_max_kg = convert_to_kg(
                    st.session_state.get(
                        "tb_kapasitas_max_input",
                        ""
                    ),
                    satuan
                )

                interval_skala_kg = (
                    kapasitas_max_kg / 1000.0
                    if kapasitas_max_kg > 0
                    else 0.0
                )

                if satuan == "g":
                    e_tampil = interval_skala_kg * 1000
                else:
                    e_tampil = interval_skala_kg

                st.session_state["tb_e_meja_display"] = float(
                    e_tampil
                )

                st.number_input(
                    "Interval Skala Verifikasi (e)",
                    disabled=True,
                    key="tb_e_meja_display"
                )

                kelas_final = st.selectbox(
                    "Kelas",
                    options=["III", "IIII"],
                    key="tb_kelas_meja",
                    on_change=update_class
                )

                if kelas_final == "III":
                    kapasitas_min_final = (
                        20 * interval_skala_kg
                    )
                else:
                    kapasitas_min_final = (
                        10 * interval_skala_kg
                    )

                if satuan == "g":
                    min_tampil = (
                        kapasitas_min_final * 1000
                    )
                else:
                    min_tampil = kapasitas_min_final

                st.session_state["tb_min_meja_display"] = float(
                    min_tampil
                )

                st.number_input(
                    "Minimum Menimbang",
                    disabled=True,
                    key="tb_min_meja_display"
                )

                daya_baca_kg = 0.0

                st.session_state[
                    "tb_interval_skala_input"
                ] = e_tampil

                st.session_state[
                    "tb_kapasitas_min_kg"
                ] = kapasitas_min_final

                st.session_state[
                    "tb_kelas"
                ] = kelas_final
            
            else:
                # === Kapasitas Maksimum ===
                col_val, col_unit = st.columns([3, 1])
                with col_val:
                    st.text_input(
                        "Kapasitas Maksimum",
                        placeholder="Masukkan kapasitas maksimum",
                        key="tb_kapasitas_max_input",
                        on_change=update_class,
                        label_visibility="collapsed",
                    )
                with col_unit:
                    st.selectbox(
                        "Satuan",
                        options=["kg", "g"],
                        key="tb_satuan_kapasitas_max",
                        on_change=update_class,
                        label_visibility="collapsed",
                    )

                # === Daya Baca ===
                col_val, col_unit = st.columns([3, 1])

                with col_val:
                    st.text_input(
                        "Daya Baca",
                        placeholder="Masukkan daya baca",
                        key="tb_daya_baca_input",
                        on_change=(
                            update_class
                            if is_timbangan_elektronik
                            else sinkronkan_daya_baca_interval
                        ),
                        label_visibility="collapsed"
                    )

                with col_unit:
                    st.markdown(
                        f"**{st.session_state.tb_satuan_kapasitas_max}**"
                    )


                # Untuk alat selain Timbangan Elektronik,
                # interval skala selalu sama dengan daya baca.
                if not is_timbangan_elektronik:
                    st.session_state["tb_interval_skala_input"] = (
                        st.session_state.get(
                            "tb_daya_baca_input",
                            ""
                        )
                    )


                # === Interval Skala Verifikasi ===
                col_val, col_unit = st.columns([3, 1])

                with col_val:
                    if is_timbangan_elektronik:
                        st.text_input(
                            "Interval Skala Verifikasi",
                            placeholder=(
                                "Masukkan interval skala verifikasi (e)"
                            ),
                            key="tb_interval_skala_input",
                            on_change=update_class,
                            help="Interval Skala Verifikasi (e).",
                            label_visibility="collapsed"
                        )

                    else:
                        st.text_input(
                            "Interval Skala Verifikasi",
                            key="tb_interval_skala_input",
                            disabled=True,
                            help=(
                                "Interval Skala Verifikasi otomatis "
                                "sama dengan Daya Baca."
                            ),
                            label_visibility="collapsed"
                        )

                with col_unit:
                    st.markdown(
                        f"**{st.session_state.tb_satuan_kapasitas_max}**"
                    )


                # =========================================================
                # KAPASITAS MINIMUM OTOMATIS
                # =========================================================

                # Hitung kelas dan kapasitas minimum terlebih dahulu
                update_class()

                min_kg = st.session_state.get(
                    "tb_kapasitas_min_kg",
                    0.0
                )

                satuan = st.session_state.get(
                    "tb_satuan_kapasitas_max",
                    "kg"
                )

                formatted = (
                    tampilkan_dalam_satuan_aktif(min_kg)
                    if min_kg > 0
                    else ""
                )

                # Sinkronkan nilai widget dengan hasil perhitungan terbaru
                st.session_state["tb_kapasitas_min_tampil"] = formatted

                col_val, col_unit = st.columns([3, 1])

                with col_val:
                    st.text_input(
                        "Kapasitas Minimum",
                        disabled=True,
                        help=(
                            "Kapasitas minimum dihitung berdasarkan "
                            "kelas: faktor × interval skala (e)."
                        ),
                        key="tb_kapasitas_min_tampil",
                        label_visibility="collapsed",
                    )

                with col_unit:
                    st.markdown(f"**{satuan}**")

                kapasitas_max_kg = get_input_kg(
                    "kapasitas_max_input",
                    0.0
                )

                daya_baca_kg = get_input_kg(
                    "daya_baca_input",
                    0.0
                )

                if is_timbangan_elektronik:
                    interval_skala_kg = get_input_kg(
                        "interval_skala_input",
                        0.0
                    )
                else:
                    # Alat selain Timbangan Elektronik: e = d
                    interval_skala_kg = daya_baca_kg
                kelas_final = st.session_state.get(
                    "tb_kelas",
                    "III"
                )
                kapasitas_min_final = st.session_state.get(
                    "tb_kapasitas_min_kg",
                    0.0
                )
                status_kelas = st.session_state.get(
                    "tb_kelas_status",
                    ""
                )
        st.markdown("---")

        # ======================== KELAS & JENIS PENGUJIAN ========================
        col_extra1, col_extra2 = st.columns(2)

        with col_extra1:
            st.subheader("Kelas Timbangan")

            if is_timbangan_meja:
                st.caption(
                    f"💡 Kelas Timbangan Meja dipilih pada bagian "
                    f"Kapasitas & Skala: Kelas "
                    f"{st.session_state.get('tb_kelas_meja', 'III')}."
                )

            elif is_neraca:
                st.session_state["tb_kelas"] = "III"

                kelas = st.text_input(
                    "Kelas",
                    value="III",
                    disabled=True,
                    help="Neraca otomatis ditetapkan sebagai Kelas III.",
                    key="tb_kelas_neraca_tampil",
                )

                st.caption(
                    "💡 Neraca otomatis masuk Kelas III."
                )

            else:
                options = ["I", "II", "III", "IIII"]

                if st.session_state.get("tb_kelas") not in options:
                    st.session_state.tb_kelas = "III"

                kelas = st.selectbox(
                    "Pilih Kelas",
                    options=options,
                    key="tb_kelas",
                    help=(
                        "Kelas diupdate otomatis saat Kapasitas "
                        "Maksimum atau Interval Skala berubah, "
                        "namun bisa diubah manual."
                    ),
                )

                status = st.session_state.get(
                    "tb_kelas_status",
                    ""
                )

                if status and not str(status).startswith("OK"):
                    st.warning(f"⚠️ {status}")
                else:
                    st.caption(
                        "💡 Kelas diupdate otomatis saat Kapasitas "
                        "Maksimum atau Interval Skala berubah."
                    )
        with col_extra2:
            st.subheader("Jenis Pengujian")
        
            keterangan = st.selectbox(
                "Pilih Jenis Pengujian",
                options=[
                    "Tera",
                    "Tera Ulang",
                ],
                key="tb_keterangan",
                help=(
                    "Pilih Tera untuk pengujian pertama "
                    "atau Tera Ulang untuk pengujian berkala."
                ),
            )
        st.markdown("---")

        # ======================== DATA PENGUJIAN LAINNYA ========================
        col4, col5, col6 = st.columns(3)

        with col4:
            st.subheader("Data Pengujian")
        
            tanggal = st.date_input(
                "Tanggal Pengujian",
                key="tb_tanggal_pengujian",
            )

            tanggal_tanda_tangan = st.date_input(
                "Tanggal Sertifikat",
                key="tb_tanggal_tanda_tangan",
            )

            lokasi_options = ["Perusahaan", "Dalam Kantor"]
            if (
                st.session_state.get("tb_lokasi_pengujian")
                not in lokasi_options
            ):
                st.session_state.tb_lokasi_pengujian = "Perusahaan"

            lokasi = st.selectbox(
                "Lokasi Pengujian",
                options=lokasi_options,
                key="tb_lokasi_pengujian",
                help="Pilih lokasi pelaksanaan pengujian.",
            )

        with col5:
            st.subheader("Data Penera")

            df_penera = st.session_state.get(
                "tb_data_penera"
            )

            if "tb_manual_penera" not in st.session_state:
                st.session_state.tb_manual_penera = False

            if (
                df_penera is not None
                and not df_penera.empty
            ):
                daftar_nama_penera = (
                    df_penera["Nama"]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .tolist()
                )

                nama_penera_tersimpan = str(
                    st.session_state.get(
                        "tb_nama_penera",
                        ""
                    )
                ).strip()

                if "tb_penera_select" not in st.session_state:
                    if nama_penera_tersimpan in daftar_nama_penera:
                        st.session_state.tb_penera_select = (
                            nama_penera_tersimpan
                        )
                    else:
                        st.session_state.tb_penera_select = ""

                        if nama_penera_tersimpan:
                            st.session_state.tb_manual_penera = True

                st.selectbox(
                    "Pilih Nama Penera",
                    options=[""] + daftar_nama_penera,
                    placeholder="Ketik atau pilih nama...",
                    key="tb_penera_select",
                    on_change=update_penera_terpilih_tb,
                )

                st.checkbox(
                    "Input manual",
                    key="tb_manual_penera",
                )

                if st.session_state.tb_manual_penera:
                    st.text_input(
                        "Nama Penera",
                        key="tb_nama_penera",
                    )

                    st.text_input(
                        "NIP Penera",
                        key="tb_nip_penera",
                    )

                    st.text_input(
                        "Golongan Penera",
                        key="tb_golongan_penera",
                    )

                else:
                    nama_aktif = str(
                        st.session_state.get(
                            "tb_nama_penera",
                            ""
                        )
                    ).strip()

                    nip_aktif = str(
                        st.session_state.get(
                            "tb_nip_penera",
                            ""
                        )
                    ).strip()

                    golongan_aktif = str(
                        st.session_state.get(
                            "tb_golongan_penera",
                            ""
                        )
                    ).strip()

                    if nama_aktif:
                        st.caption(
                            f"**NIP:** {nip_aktif or '-'}"
                        )

                        st.caption(
                            f"**Golongan:** {golongan_aktif or '-'}"
                        )

            else:
                st.info(
                    "📂 File data penera tidak ditemukan. "
                    "Silakan input manual."
                )

                st.text_input(
                    "Nama Penera",
                    key="tb_nama_penera",
                )

                st.text_input(
                    "NIP Penera",
                    key="tb_nip_penera",
                )

                st.text_input(
                    "Golongan Penera",
                    key="tb_golongan_penera",
                )

            nama_penera = str(
                st.session_state.get(
                    "tb_nama_penera",
                    ""
                )
            ).strip()

            nip_penera = str(
                st.session_state.get(
                    "tb_nip_penera",
                    ""
                )
            ).strip()
            st.markdown("##### Penera 2 (Opsional)")

            daftar_nama_penera_2 = [""]
            
            if (
                df_penera is not None
                and not df_penera.empty
            ):
                daftar_nama_penera_2 += (
                    df_penera["Nama"]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .tolist()
                )
            
            nama_penera_2 = st.selectbox(
                "Pilih Penera 2",
                options=daftar_nama_penera_2,
                key="tb_penera_2_select",
            )
        with col6:
            st.subheader("Informasi Tambahan")
        
            # Suhu ruangan selalu "Ambient" (tidak bisa diubah)
            suhu = st.text_input(
                "Suhu Ruangan",
                value="Ambient",
                disabled=True,
                help="Nilai tetap Ambient sesuai standar pengujian.",
                key="tb_suhu",
            )
        
            # Kelembaban selalu "Ambient" (tidak bisa diubah)
            kelembaban = st.text_input(
                "Kelembaban",
                value="Ambient",
                disabled=True,
                help="Nilai tetap Ambient sesuai standar pengujian.",
                key="tb_kelembaban",
            )
        
            # ===== METODE PENGUJIAN =====
            kelas_saat_ini = st.session_state.get(
                "tb_kelas",
                "III"
            )

            if is_timbangan_meja:

                st.session_state[
                    "tb_metode_pengujian"
                ] = "Perbandingan Langsung"

                metode = st.selectbox(
                    "Metode Pengujian",
                    options=[
                        "Perbandingan Langsung"
                    ],
                    key="tb_metode_pengujian",
                    disabled=True,
                    help=(
                        "Timbangan Meja menggunakan "
                        "metode Perbandingan Langsung."
                    ),
                )

            elif kelas_saat_ini in ["I", "II"]:

                st.session_state[
                    "tb_metode_pengujian"
                ] = "Perbandingan Langsung"

                metode = st.selectbox(
                    "Metode Pengujian",
                    options=[
                        "Perbandingan Langsung"
                    ],
                    key="tb_metode_pengujian",
                    help=(
                        "Kelas I dan II wajib menggunakan "
                        "metode Perbandingan Langsung."
                    ),
                )

            else:

                metode_options = [
                    "Beban Substitusi Tunggal",
                    "Perbandingan Langsung"
                ]

                if (
                    st.session_state.get(
                        "tb_metode_pengujian"
                    )
                    not in metode_options
                ):
                    st.session_state[
                        "tb_metode_pengujian"
                    ] = metode_options[0]

                metode = st.selectbox(
                    "Metode Pengujian",
                    options=metode_options,
                    key="tb_metode_pengujian",
                    help="Pilih metode pengujian yang digunakan.",
                )
        
            # ===== AT STANDAR =====
            kelas_saat_ini = st.session_state.get(
                "tb_kelas",
                "III"
            )

            if is_timbangan_meja:

                st.session_state[
                    "tb_at_standar"
                ] = "M2"

                at_standar = st.selectbox(
                    "AT Standar",
                    options=["M2"],
                    key="tb_at_standar",
                    disabled=True,
                    help=(
                        "Timbangan Meja menggunakan "
                        "anak timbangan standar kelas M2."
                    ),
                )

            else:

                if kelas_saat_ini in ["III", "IIII"]:
                    at_options = ["M2"]

                elif kelas_saat_ini == "II":
                    at_options = [
                        "M1",
                        "F2",
                        "F1"
                    ]

                elif kelas_saat_ini == "I":
                    at_options = [
                        "F2",
                        "F1"
                    ]

                else:
                    at_options = ["M2"]

                if (
                    st.session_state.get(
                        "tb_at_standar"
                    )
                    not in at_options
                ):
                    st.session_state[
                        "tb_at_standar"
                    ] = at_options[0]

                at_standar = st.selectbox(
                    "AT Standar",
                    options=at_options,
                    key="tb_at_standar",
                    help=(
                        "Kelas ketelitian anak timbangan standar "
                        "yang digunakan sesuai kelas timbangan."
                    ),
                )
    
        # ======================== PEMERIKSAAN VISUAL ========================
        st.markdown("---")
        st.subheader("Pemeriksaan Visual")

        jenis_pengujian = st.session_state.get("tb_keterangan", "Tera Ulang")

        visual_items = [
            "Timbangan bersih, kering dan tidak berkarat",
            "Bahan & Konstruksi Sesuai (Tera)",
            "Posisi timbangan datar",
            "Telah dilakukan pemanasan timbangan"
        ]

        visual_results = {}

        cols_vis = st.columns(4)

        for idx, item in enumerate(visual_items):
            with cols_vis[idx % 4]:

                # Khusus item ini: tetap tampil, tapi disable saat Tera Ulang
                is_bahan_konstruksi = item == "Bahan & Konstruksi Sesuai (Tera)"
                is_disabled = is_bahan_konstruksi and jenis_pengujian == "Tera Ulang"

                visual_results[item] = st.checkbox(
                    item,
                    value=True if not is_disabled else False,
                    disabled=is_disabled,
                    key=f"tb_vis_{item}_{jenis_pengujian}"
                )

        # Tabel BKD dibaca dari folder assets proyek.

        if "tb_tampilkan_tabel_bkd" not in st.session_state:
            st.session_state.tb_tampilkan_tabel_bkd = False

        col_judul_bkd, col_link_bkd = st.columns([4, 1.4])

        with col_judul_bkd:
            st.subheader("Pengujian Kebenaran")
            # ============================================================
            # PILIHAN JUMLAH TITIK UJI
            # ============================================================
            if not is_neraca and not is_timbangan_meja:
                jumlah_titik_uji = st.radio(
                    "Jumlah Titik Uji",
                    options=[5, 3],
                    horizontal=True,
                    key="tb_jumlah_titik_kebenaran",
                    format_func=lambda x: f"{x} Titik Uji",
                    help=(
                        "5 titik menggunakan susunan muatan uji standar. "
                        "3 titik menggunakan Minimum Menimbang, "
                        "50% Maksimum, dan Maksimum."
                    ),
                )
            else:
                jumlah_titik_uji = 1
            if is_neraca or is_timbangan_meja:
                keterangan_ed = ""
            else:
                e_sama_d = math.isclose(
                    float(e),
                    float(daya_baca_kg),
                    rel_tol=1e-9,
                    abs_tol=1e-12
                )

                keterangan_ed = "e = d" if e_sama_d else "e ≠ d"
                st.caption(keterangan_ed)

        with col_link_bkd:
            label_bkd = (
                "Tutup Tabel BKD"
                if st.session_state.tb_tampilkan_tabel_bkd
                else "Lihat Tabel BKD"
            )

            if st.button(
                label_bkd,
                key="tb_btn_tabel_bkd",
                use_container_width=True
            ):
                st.session_state.tb_tampilkan_tabel_bkd = (
                    not st.session_state.tb_tampilkan_tabel_bkd
                )
                st.rerun()

        if st.session_state.tb_tampilkan_tabel_bkd:
            if TABEL_BKD_PATH.exists():
                st.image(
                    str(TABEL_BKD_PATH),
                    caption="Tabel Batas Kesalahan yang Diizinkan (BKD)",
                    use_container_width=True
                )
            else:
                st.error(
                    f"File tabel_bkd.png tidak ditemukan di: {TABEL_BKD_PATH}"
                )

        # ======================== TABEL PENGUJIAN KEBENARAN ========================
        satuan_tampilan = st.session_state.get(
            "tb_satuan_kapasitas_max",
            "kg"
        )
        cls = "III" if is_neraca else st.session_state.get(
            "tb_kelas",
            "III"
        )
        jns_uji = st.session_state.get(
            "tb_keterangan",
            "Tera Ulang"
        )

        if is_neraca:
            # Neraca Obat: e dihitung otomatis dari Maksimum / 10.000.
            daya_baca_kg = 0.0
            kapasitas_max_kg = convert_to_kg(
                st.session_state.get(
                    "tb_kapasitas_max_neraca_input",
                    ""
                ),
                satuan_tampilan
            )
            kapasitas_min_kg = convert_to_kg(
                st.session_state.get(
                    "tb_kapasitas_min_neraca_input",
                    ""
                ),
                satuan_tampilan
            )
            e = kapasitas_max_kg / 10000.0 if kapasitas_max_kg > 0 else 0.0

            if kapasitas_max_kg <= 0:
                st.warning(
                    "⚠️ Isi Maksimum Menimbang Neraca terlebih dahulu."
                )
                st.stop()

            if kapasitas_min_kg <= 0:
                st.warning(
                    "⚠️ Isi Minimum Menimbang Neraca terlebih dahulu."
                )
                st.stop()

            if kapasitas_min_kg > kapasitas_max_kg:
                st.warning(
                    "⚠️ Minimum menimbang tidak boleh lebih besar "
                    "dari maksimum menimbang."
                )
                st.stop()

            max_tampil = kg_to_satuan(
                kapasitas_max_kg,
                satuan_tampilan
            )
            e_tampil = kg_to_satuan(e, satuan_tampilan)

            # Neraca Obat: penunjukan ditampilkan tanpa angka desimal
            # dan nilainya selalu sama dengan muatan uji.
            decimal_penunjukan = 0
            format_penunjukan = "%.0f"

            step_muatan_tampil = e_tampil if e_tampil > 0 else 0.001
            step_penunjukan_tampil = 1.0

            # Baris 1 adalah maksimum menimbang; baris 2–5 kosong.
            default_muatan_list = [
                kapasitas_max_kg,
                0.0,
                0.0,
                0.0,
                0.0,
            ]
        
        elif is_timbangan_meja:
            # ============================================================
            # TIMBANGAN MEJA
            # Pengujian Kebenaran hanya pada Maksimum
            # ============================================================

            kapasitas_max_kg = get_input_kg(
                "kapasitas_max_input",
                0.0
            )

            e = get_input_kg(
                "interval_skala_input",
                0.0
            )

            # Timbangan Meja tidak menggunakan daya baca.
            # Untuk format tampilan, gunakan e.
            daya_baca_kg = e

            if kapasitas_max_kg <= 0:
                st.warning(
                    "⚠️ Isi Maksimum Menimbang Timbangan Meja terlebih dahulu."
                )
                st.stop()

            if e <= 0:
                st.warning(
                    "⚠️ Interval Skala Verifikasi (e) belum terbentuk."
                )
                st.stop()

            e_tampil = kg_to_satuan(
                e,
                satuan_tampilan
            )

            # Timbangan Meja: penunjukan selalu bilangan bulat
            decimal_penunjukan = 0
            format_penunjukan = "%.0f"

            step_muatan_tampil = (
                e_tampil
                if e_tampil > 0
                else 0.001
            )

            step_penunjukan_tampil = step_muatan_tampil

            # Hanya baris pertama aktif = Maksimum
            default_muatan_list = [
                kapasitas_max_kg,
                0.0,
                0.0,
                0.0,
                0.0,
            ]
                
        else:
            e = get_input_kg(
                "interval_skala_input",
                0.0
            )
            daya_baca_kg = get_input_kg(
                "daya_baca_input",
                e
            )
            kapasitas_max_kg = get_input_kg(
                "kapasitas_max_input",
                0.0
            )

            if e <= 0:
                st.warning(
                    "⚠️ Isi Interval Skala Verifikasi (e) "
                    "terlebih dahulu agar tabel pengujian dapat dihitung."
                )
                st.stop()

            if kapasitas_max_kg <= 0:
                st.warning(
                    "⚠️ Isi Kapasitas Maksimum terlebih dahulu "
                    "agar tabel pengujian dapat dihitung."
                )
                st.stop()

            if daya_baca_kg <= 0:
                daya_baca_kg = e

            step_muatan_tampil = kg_to_satuan(
                e,
                satuan_tampilan
            )
            if step_muatan_tampil <= 0:
                step_muatan_tampil = 1.0

            step_penunjukan_tampil = kg_to_satuan(
                daya_baca_kg,
                satuan_tampilan
            )
            if step_penunjukan_tampil <= 0:
                step_penunjukan_tampil = step_muatan_tampil

            daya_baca_tampil = kg_to_satuan(
                daya_baca_kg,
                satuan_tampilan
            )

            if is_timbangan_meja:
                # Timbangan Meja: penunjukan tanpa desimal
                decimal_penunjukan = 0
                format_penunjukan = "%.0f"
            else:
                decimal_penunjukan = get_decimal_places_from_number(
                    daya_baca_tampil
                )
                format_penunjukan = f"%.{decimal_penunjukan}f"

            kapasitas_min_kg = st.session_state.get(
                "tb_kapasitas_min_kg",
                0.0
            )

            if kapasitas_min_kg <= 0:
                faktor_min = {
                    "I": 100,
                    "II": 50,
                    "III": 20,
                    "IIII": 10,
                }
                kapasitas_min_kg = (
                    faktor_min.get(cls, 20) * e
                )

            if jumlah_titik_uji == 3:
                default_muatan_list = [
                    kapasitas_min_kg,
                    kapasitas_max_kg * 0.5,
                    kapasitas_max_kg,
                ]
            
            else:
                default_muatan_list = get_default_muatan_uji(
                    cls,
                    e,
                    kapasitas_max_kg
                )
        # ==================================================
        # KETERANGAN PERBANDINGAN e DAN d
        # Tempel tepat di sini
        # ==================================================
        if is_neraca:
            # Neraca Obat tidak memiliki nilai d terpisah
            keterangan_ed = ""
        else:
            e_sama_d = math.isclose(
                float(e),
                float(daya_baca_kg),
                rel_tol=1e-9,
                abs_tol=1e-12
            )

            keterangan_ed = (
                "e = d"
                if e_sama_d
                else "e ≠ d"
            )

        num_results = len(
            default_muatan_list
        )
        test_results = []

        # =====================================================
        # DATA KEBENARAN LAMA
        # Digunakan ketika Mode Edit
        # =====================================================
        hasil_kebenaran_lama = (
            st.session_state
            .get(
                "tb_saved_data",
                {}
            )
            .get(
                "hasil_pengujian",
                []
            )
            or []
        )
        st.write("**Masukkan Hasil Pengujian**")

        cols_header = st.columns(
            [0.5, 2.1, 2.3, 1.4, 3.6, 1.2, 1.4]
        )

        for col, label in zip(
            cols_header,
            [
                "**No**",
                "**Muatan Uji**",
                "**Penunjukan**",
                "**BKD**",
                "**Pengamatan Penunjukan**",
                "**Hasil**",
                "**Cek**",
            ]
        ):
            col.write(label)

        for i in range(num_results):
            cols = st.columns(
                [0.5, 2.1, 2.3, 1.4, 3.6, 1.2, 1.4]
            )

            nomor_baris = i + 1
            # =====================================================
            # DATA LAMA BARIS INI
            # =====================================================
            row_lama = {}
            
            if i < len(
                hasil_kebenaran_lama
            ):
                calon_row = (
                    hasil_kebenaran_lama[i]
                    or {}
                )
            
                if calon_row.get(
                    "aktif",
                    True
                ):
                    row_lama = calon_row
            baris_kebenaran_disabled = (
                (is_neraca or is_timbangan_meja)
                and i > 0
            )

            with cols[0]:
                st.write(str(nomor_baris))

            # Neraca Obat: hanya baris 1 aktif; baris 2–5 kosong dan disabled.
            if baris_kebenaran_disabled:
                with cols[1]:
                    st.text_input(
                        f"Muatan Uji Neraca {nomor_baris}",
                        value="",
                        disabled=True,
                        key=f"tb_neraca_muatan_disabled_{i}",
                        label_visibility="collapsed"
                    )

                with cols[2]:
                    st.text_input(
                        f"Penunjukan Neraca {nomor_baris}",
                        value="",
                        disabled=True,
                        key=f"tb_neraca_penunjukan_disabled_{i}",
                        label_visibility="collapsed"
                    )

                with cols[3]:
                    st.text_input(
                        f"BKD Neraca {nomor_baris}",
                        value="",
                        disabled=True,
                        key=f"tb_neraca_bkd_disabled_{i}",
                        label_visibility="collapsed"
                    )

                with cols[4]:
                    st.text_input(
                        f"Pengamatan Neraca {nomor_baris}",
                        value="",
                        disabled=True,
                        key=f"tb_neraca_pengamatan_disabled_{i}",
                        label_visibility="collapsed"
                    )

                with cols[5]:
                    st.text_input(
                        f"Hasil Neraca {nomor_baris}",
                        value="",
                        disabled=True,
                        key=f"tb_neraca_hasil_disabled_{i}",
                        label_visibility="collapsed"
                    )

                with cols[6]:
                    st.text_input(
                        f"Cek Neraca {nomor_baris}",
                        value="",
                        disabled=True,
                        key=f"tb_neraca_cek_disabled_{i}",
                        label_visibility="collapsed"
                    )

                test_results.append({
                    "nomor": nomor_baris,
                    "aktif": False,
                    "muatan_uji": 0.0,
                    "penunjukan": 0.0,
                    "tb_muatan_uji_text": "",
                    "penunjukan_text": "",
                    "pengamatan_penunjukan": "",
                    "hasil_perhitungan": 0.0,
                    "cek_otomatis": False,
                    "hasil_text": "",
                    "standar": "",
                    "balas": "",
                    "muatan_sb": "",
                    "timbangan": "",
                    "timbangan_text": "",
                    "imbuh": "",
                    "p_aktual": "",
                    "kesalahan": "",
                    "bkd_koef": 0.0,
                    "bkd_kg": 0.0,
                    "bkd_text": "",
                    "hasil": False,
                })
                continue

            if row_lama:
                muatan_lama_kg = row_lama.get(
                    "muatan_uji",
                    row_lama.get(
                        "muatan_sb",
                        row_lama.get(
                            "standar",
                            default_muatan_list[i]
                        )
                    )
                )
            
                try:
                    muatan_lama_kg = float(
                        muatan_lama_kg
                    )
                except (
                    TypeError,
                    ValueError
                ):
                    muatan_lama_kg = (
                        default_muatan_list[i]
                    )
            
                default_muatan_tampil = (
                    kg_to_satuan(
                        muatan_lama_kg,
                        satuan_tampilan
                    )
                )
            
            else:
                default_muatan_tampil = (
                    kg_to_satuan(
                        default_muatan_list[i],
                        satuan_tampilan
                    )
                )

            # --- Muatan Uji ---
            with cols[1]:
                sub_muatan1, sub_muatan2 = st.columns([4, 1])

                with sub_muatan1:
                    muatan_uji_tampil = st.number_input(
                        f"Muatan Uji {nomor_baris}",
                        value=float(default_muatan_tampil),
                        step=float(step_muatan_tampil),
                        format="%g",
                        disabled=(
                            is_neraca
                            or is_timbangan_meja
                        ),
                        key=(
                            f"tb_muatan_uji_{jumlah_titik_uji}_{i}_{nama_alat}_"
                            f"{kapasitas_max_kg}_{e}_"
                            f"{satuan_tampilan}"
                        ),
                        label_visibility="collapsed"
                    )

                with sub_muatan2:
                    st.markdown(f"**{satuan_tampilan}**")

            muatan_uji = satuan_to_kg(
                muatan_uji_tampil,
                satuan_tampilan
            )

            # --- Penunjukan ---
            if row_lama:
                penunjukan_lama_kg = (
                    row_lama.get(
                        "penunjukan",
                        row_lama.get(
                            "timbangan",
                            muatan_uji
                        )
                    )
                )
            
                try:
                    penunjukan_lama_kg = float(
                        penunjukan_lama_kg
                    )
                except (
                    TypeError,
                    ValueError
                ):
                    penunjukan_lama_kg = (
                        muatan_uji
                    )
            
                default_penunjukan_tampil = (
                    kg_to_satuan(
                        penunjukan_lama_kg,
                        satuan_tampilan
                    )
                )
            
            else:
                default_penunjukan_tampil = (
                    kg_to_satuan(
                        muatan_uji,
                        satuan_tampilan
                    )
                )

            with cols[2]:
                sub_penunjukan1, sub_penunjukan2 = st.columns(
                    [4, 1]
                )

                with sub_penunjukan1:
                    penunjukan_tampil = st.number_input(
                        f"Penunjukan {nomor_baris}",
                        value=float(default_penunjukan_tampil),
                        step=float(step_penunjukan_tampil),
                        format=format_penunjukan,
                        disabled=True,
                        key=(
                            f"tb_penunjukan_kebenaran_{i}_{nama_alat}_"
                            f"{e}_{daya_baca_kg}_{muatan_uji}_"
                            f"{satuan_tampilan}"
                        ),
                        label_visibility="collapsed"
                    )

                with sub_penunjukan2:
                    st.markdown(f"**{satuan_tampilan}**")

            penunjukan_val = satuan_to_kg(
                penunjukan_tampil,
                satuan_tampilan
            )

            # --- BKD ---
            with cols[3]:
                if is_neraca:
                    # BKD Neraca Obat = muatan uji / 5.000
                    # Contoh: 50 g / 5.000 = 0,01 g
                    bkd_kg = muatan_uji / 5000.0
                    koef = 2.0  # ekuivalen 2e karena e = Maks / 10.000

                    bkd_tampil = kg_to_satuan(
                        bkd_kg,
                        satuan_tampilan
                    )
                    desimal_bkd = get_decimal_places_from_number(
                        bkd_tampil
                    )
                    bkd_text = (
                        "± "
                        + format_angka_id(bkd_tampil, desimal_bkd)
                        + f" {satuan_tampilan}"
                    )
                else:
                    koef, bkd_kg = hitung_bkd(
                        muatan_uji,
                        e,
                        cls,
                        jns_uji
                    )

                    if koef == 0.5:
                        bkd_text = "±0.5e"
                    elif koef == 1.0:
                        bkd_text = "±1e"
                    elif koef == 1.5:
                        bkd_text = "±1.5e"
                    elif koef == 2.0:
                        bkd_text = "±2e"
                    elif koef == 3.0:
                        bkd_text = "±3e"
                    else:
                        bkd_text = f"±{koef:.1f}e"

                st.write(f"**{bkd_text}**")

            # --- Pengamatan Penunjukan ---
            with cols[4]:
                st.text_input(
                    f"Pengamatan Penunjukan {nomor_baris}",
                    value="Penunjukan = Massa ATS",
                    disabled=True,
                    key=(
                        f"tb_pengamatan_penunjukan_{nama_alat}_{i}"
                    ),
                    label_visibility="collapsed"
                )

            delta_l_val = 0.0
            p_aktual = penunjukan_val
            kesalahan_val = penunjukan_val - muatan_uji

            if is_neraca or is_timbangan_meja:
                cek_sah = True
            else:
                cek_sah = abs(kesalahan_val) <= bkd_kg

            # --- Hasil ---
            with cols[5]:
                hasil_val = st.text_input(
                    f"Hasil {nomor_baris}",
                    value="SAH",
                    disabled=True,
                    key=(
                        f"tb_hasil_kebenaran_{nama_alat}_{i}_"
                        f"{e}_{muatan_uji}_{penunjukan_val}"
                    ),
                    label_visibility="collapsed"
                )

            # --- Cek ---
            with cols[6]:
                cek_icon = "✅" if cek_sah else "❌"

                st.text_input(
                    f"Cek {nomor_baris}",
                    value=cek_icon,
                    disabled=True,
                    key=(
                        f"tb_cek_kebenaran_{nama_alat}_{i}_"
                        f"{e}_{muatan_uji}_{penunjukan_val}"
                    ),
                    label_visibility="collapsed"
                )

            desimal_muatan = (
                0
                if is_neraca
                else get_decimal_places_from_number(step_muatan_tampil)
            )

            test_results.append({
                "nomor": nomor_baris,
                "aktif": True,
                "muatan_uji": muatan_uji,
                "penunjukan": penunjukan_val,
                "tb_muatan_uji_text": (
                    format_angka_id(
                        muatan_uji_tampil,
                        desimal_muatan
                    )
                    + f" {satuan_tampilan}"
                ),
                "penunjukan_text": (
                    format_angka_id(
                        penunjukan_tampil,
                        decimal_penunjukan
                    )
                    + f" {satuan_tampilan}"
                ),
                "pengamatan_penunjukan": (
                    "Penunjukan = Massa ATS"
                ),
                "hasil_perhitungan": p_aktual,
                "cek_otomatis": cek_sah,
                "hasil_text": hasil_val,

                # Kompatibilitas generator PDF lama
                "standar": muatan_uji,
                "balas": 0,
                "muatan_sb": muatan_uji,
                "timbangan": penunjukan_val,
                "timbangan_text": (
                    format_angka_id(
                        penunjukan_tampil,
                        decimal_penunjukan
                    )
                    + f" {satuan_tampilan}"
                ),
                "imbuh": delta_l_val,
                "p_aktual": p_aktual,
                "kesalahan": kesalahan_val,
                "bkd_koef": koef,
                "bkd_kg": bkd_kg,
                "bkd_text": bkd_text,
                "hasil": hasil_val == "SAH",
            })

        st.markdown("---")
        # Neraca Obat tidak menggunakan pengujian eksentrisitas.
        # Repetability tetap ditampilkan dalam format sederhana.
        eksen_data = []
        repet_data = []

        if is_neraca:
            st.info(
                "Pengujian Eksentrisitas tidak diterapkan untuk Neraca Obat."
            )
        else:
        # ======================== EKSENTRISITAS ========================
            st.markdown("---")
            st.subheader("Eksentrisitas (1/3 Maks)")

            kapasitas_max = get_input_kg(
                "kapasitas_max_input",
                0.0
            )

            interval_skala = get_input_kg(
                "interval_skala_input",
                0.0
            )

            if is_timbangan_meja:
                # Timbangan Meja tidak mempunyai daya baca terpisah.
                # Untuk format penunjukan gunakan interval skala (e).
                daya_baca_kg = interval_skala
            else:
                daya_baca_kg = get_input_kg(
                    "daya_baca_input",
                    interval_skala
                )

            kelas = st.session_state.get('tb_kelas', 'III')
            keterangan = st.session_state.get('tb_keterangan', 'Tera Ulang')
            satuan_tampilan = st.session_state.get("tb_satuan_kapasitas_max", "kg")

            if kapasitas_max <= 0 or interval_skala <= 0:
                st.warning(
                    "Isi Kapasitas Maksimum dan Interval Skala Verifikasi."
                )
                st.stop()

            if daya_baca_kg <= 0:
                daya_baca_kg = interval_skala

            # Format desimal mengikuti daya baca dalam satuan tampilan
            daya_baca_tampil = kg_to_satuan(
                daya_baca_kg,
                satuan_tampilan
            )

            if is_timbangan_meja:
                # Timbangan Meja: penunjukan selalu bilangan bulat
                decimal_penunjukan = 0
                format_penunjukan = "%.0f"
            else:
                decimal_penunjukan = get_decimal_places_from_number(
                    daya_baca_tampil
                )
                format_penunjukan = f"%.{decimal_penunjukan}f"

            step_penunjukan_tampil = daya_baca_tampil

            # Beban eksentrisitas = 1/3 Maks
            muatan_eks_kg = kapasitas_max / 3.0
            muatan_eks_tampil = kg_to_satuan(muatan_eks_kg, satuan_tampilan)

            # Header 6 kolom
            cols_header_eks = st.columns([0.8, 2.2, 1.4, 3.4, 1.4, 1.2])

            for col, label in zip(cols_header_eks, [
                "**Posisi**",
                "**Penunjukan (I)**",
                "**BKD**",
                "**Pengamatan Penunjukan**",
                "**Hasil**",
                "**Cek**"
            ]):
                col.write(label)

            eksen_data = []
            # =====================================================
            # DATA EKSENTRISITAS LAMA
            # Digunakan saat Mode Edit
            # =====================================================
            eksentrisitas_lama = (
                st.session_state
                .get(
                    "tb_saved_data",
                    {}
                )
                .get(
                    "eksentrisitas",
                    []
                )
                or []
            )
            
            penunjukan_eks_lama_kg = None
            
            if eksentrisitas_lama:
                try:
                    penunjukan_eks_lama_kg = float(
                        eksentrisitas_lama[0].get(
                            "penunjukan",
                            0
                        )
                        or 0
                    )
                except (TypeError, ValueError):
                    penunjukan_eks_lama_kg = None
            for i in range(1, 5):
                cols_eksen = st.columns([0.8, 2.2, 1.4, 3.4, 1.4, 1.2])

                # --- Posisi ---
                with cols_eksen[0]:
                    st.text_input(
                        f"Posisi {i}",
                        value=str(i),
                        disabled=True,
                        key=f"tb_eksen_posisi_{i}",
                        label_visibility="collapsed"
                    )

                # --- Penunjukan (I) ---
                with cols_eksen[1]:
                    sub_penunjukan1, sub_penunjukan2 = st.columns([4, 1])

                    with sub_penunjukan1:
                        if i == 1:

                            if penunjukan_eks_lama_kg is not None:
                                default_penunjukan_eks_tampil = (
                                    kg_to_satuan(
                                        penunjukan_eks_lama_kg,
                                        satuan_tampilan
                                    )
                                )
                            else:
                                default_penunjukan_eks_tampil = (
                                    muatan_eks_tampil
                                )
                        
                            penunjukan_tampil = st.number_input(
                                f"Penunjukan Eksentrisitas {i}",
                                value=float(
                                    default_penunjukan_eks_tampil
                                ),
                                step=float(
                                    step_penunjukan_tampil
                                ),
                                format=format_penunjukan,
                                key=(
                                    f"tb_eksen_penunjukan_1_"
                                    f"{daya_baca_kg}_"
                                    f"{satuan_tampilan}"
                                ),
                                label_visibility="collapsed"
                            )
                        
                            st.session_state[
                                "tb_eksen_penunjukan_acuan"
                            ] = penunjukan_tampil

                        else:
                            penunjukan_acuan = st.session_state.get(
                                "tb_eksen_penunjukan_acuan",
                                muatan_eks_tampil
                            )

                            penunjukan_tampil = st.number_input(
                                f"Penunjukan Eksentrisitas {i}",
                                value=float(penunjukan_acuan),
                                step=float(step_penunjukan_tampil),
                                format=format_penunjukan,
                                disabled=True,
                                key=f"tb_eksen_penunjukan_{i}_{penunjukan_acuan}_{daya_baca_kg}_{satuan_tampilan}",
                                label_visibility="collapsed"
                            )

                    with sub_penunjukan2:
                        st.markdown(f"**{satuan_tampilan}**")

                # WAJIB: konversi penunjukan dari satuan tampilan ke kg
                I = satuan_to_kg(penunjukan_tampil, satuan_tampilan)

                # --- BKD ---
                with cols_eksen[2]:
                    koef, bkd_kg = hitung_bkd(I, interval_skala, kelas, keterangan)

                    if koef == 0.5:
                        bkd_text = "±0.5e"
                    elif koef == 1.0:
                        bkd_text = "±1e"
                    elif koef == 1.5:
                        bkd_text = "±1.5e"
                    elif koef == 2.0:
                        bkd_text = "±2e"
                    elif koef == 3.0:
                        bkd_text = "±3e"
                    else:
                        bkd_text = f"±{koef:.1f}e"

                    st.write(f"**{bkd_text}**")

                # --- Pengamatan Penunjukan ---
                with cols_eksen[3]:
                    st.text_input(
                        f"Pengamatan Eksentrisitas {i}",
                        value="penunjukan ≤ massa ATS ± BKD ",
                        disabled=True,
                        key=f"tb_eksen_pengamatan_{i}",
                        label_visibility="collapsed"
                    )

                # Hitung kesalahan eksentrisitas
                kesalahan_eks = (
                    I - muatan_eks_kg
                )

                # SAH jika kesalahan masih berada dalam BKD
                if is_timbangan_meja:
                    cek_sah = True
                else:
                    cek_sah = (
                        abs(kesalahan_eks)
                        <= bkd_kg
                    )

                # --- Hasil ---
                with cols_eksen[4]:
                    hasil_otomatis_eks = (
                        "SAH"
                        if cek_sah
                        else "TIDAK SAH"
                    )

                    hasil = st.text_input(
                        f"Hasil Eksentrisitas {i}",
                        value=hasil_otomatis_eks,
                        disabled=True,
                        key=(
                            f"tb_eksen_hasil_{i}_{I}_"
                            f"{bkd_kg}_{cek_sah}"
                        ),
                        label_visibility="collapsed"
                    )

                # --- Cek ---
                with cols_eksen[5]:
                    cek_icon = (
                        "✅"
                        if cek_sah
                        else "❌"
                    )

                    st.text_input(
                        f"Cek Eksentrisitas {i}",
                        value=cek_icon,
                        disabled=True,
                        key=(
                            f"tb_eksen_cek_{i}_{I}_{bkd_kg}_"
                            f"{interval_skala}_{keterangan}"
                        ),
                        label_visibility="collapsed"
                    )

                eksen_data.append({
                    "posisi": i,
                    "penunjukan": I,
                    "penunjukan_tampil": penunjukan_tampil,
                    "penunjukan_text": format_angka_id(
                        penunjukan_tampil,
                        decimal_penunjukan
                    ),
                    "satuan_tampilan": satuan_tampilan,
                    "muatan_eks": muatan_eks_kg,
                    "muatan_eks_tampil": muatan_eks_tampil,
                    "pengamatan_penunjukan": (
                        "penunjukan ≤ massa ATS ± BKD"
                    ),
                    "kesalahan": kesalahan_eks,

                    # Selalu checklist
                    "cek_otomatis": cek_sah,
                    "cek_icon": cek_icon,

                    "hasil_text": hasil,
                    "hasil": hasil == "SAH",
                    "bkd_koef": koef,
                    "bkd_kg": bkd_kg,
                    "bkd_text": bkd_text,

                    "delta_l": 0.0,
                    "p_value": I,
                    "selisih": str(i),
                })

        # ======================== REPETABILITY ========================
        # =====================================================
        # DATA REPETABILITY LAMA
        # Digunakan saat Mode Edit
        # =====================================================
        repetability_lama = (
            st.session_state
            .get(
                "tb_saved_data",
                {}
            )
            .get(
                "repetability",
                []
            )
            or []
        )
        nama_alat_repet = (
            st.session_state.get("tb_nama_alat")
            or st.session_state.get("tb_saved_data", {}).get(
                "nama_alat",
                "Timbangan Elektronik"
            )
        )

        is_neraca_repet = is_neraca_name(
            nama_alat_repet
        )

        is_timbangan_elektronik_repet = (
            str(nama_alat_repet).strip().lower()
            == "timbangan elektronik"
        )

        is_timbangan_meja_repet = (
            str(nama_alat_repet).strip().lower()
            == "timbangan meja"
        )

        repet_sederhana = (
            is_neraca_repet
            or is_timbangan_meja_repet
            or (
                is_timbangan_elektronik_repet
                and nilai_berbeda(
                    daya_baca_kg,
                    interval_skala_kg
                )
            )
        )

        # ============================================================
        # A. REPETABILITY SEDERHANA
        # Neraca Obat dan Timbangan Elektronik dengan e != d
        # ============================================================
        if repet_sederhana:
            st.markdown("---")
            st.subheader("Repetability")

            # Neraca Obat tidak menampilkan keterangan e dan d.
            if (
                not is_neraca
                and not is_timbangan_meja_repet
                and keterangan_ed
            ):
                st.caption(keterangan_ed)

            satuan_tampilan = st.session_state.get(
                "tb_satuan_kapasitas_max",
                "g" if is_neraca else "kg"
            )

            if is_neraca:
                kapasitas_max_repet_kg = convert_to_kg(
                    st.session_state.get(
                        "tb_kapasitas_max_neraca_input",
                        ""
                    ),
                    satuan_tampilan
                )

                # Neraca Obat menggunakan Maksimum
                muatan_repet_kg = kapasitas_max_repet_kg

            elif is_timbangan_meja_repet:
                kapasitas_max_repet_kg = get_input_kg(
                    "kapasitas_max_input",
                    0.0
                )

                # Timbangan Meja menggunakan Maksimum
                muatan_repet_kg = kapasitas_max_repet_kg

            else:
                kapasitas_max_repet_kg = get_input_kg(
                    "kapasitas_max_input",
                    0.0
                )

                # Timbangan Elektronik e != d menggunakan 50% Maksimum
                muatan_repet_kg = kapasitas_max_repet_kg * 0.5

            muatan_repet_tampil = kg_to_satuan(
                muatan_repet_kg,
                satuan_tampilan
            )

            if is_neraca:
                decimal_repet = 0
                format_repet = "%.0f"
                step_repet = 1.0

            elif is_timbangan_meja_repet:
                e_repet_tampil = kg_to_satuan(
                    interval_skala_kg,
                    satuan_tampilan
                )

                # Timbangan Meja: penunjukan selalu bilangan bulat
                decimal_repet = 0
                format_repet = "%.0f"

                step_repet = (
                    e_repet_tampil
                    if e_repet_tampil > 0
                    else 1.0
                )

            else:
                daya_baca_repet_tampil = kg_to_satuan(
                    daya_baca_kg,
                    satuan_tampilan
                )

                decimal_repet = get_decimal_places_from_number(
                    daya_baca_repet_tampil
                )

                format_repet = f"%.{decimal_repet}f"

                step_repet = (
                    daya_baca_repet_tampil
                    if daya_baca_repet_tampil > 0
                    else 1.0
                )

            col_header = st.columns([3.5, 1.5])

            with col_header[0]:
                st.write("**Penunjukan Akhir**")

            with col_header[1]:
                st.write("**Hasil**")

            repet_data = []
            penunjukan_repet_list = []

            # =====================================================
            # DEFAULT REPETABILITY LAMA
            # =====================================================
            penunjukan_repet_lama_kg = None
            
            if repetability_lama:
                try:
                    penunjukan_repet_lama_kg = float(
                        repetability_lama[0].get(
                            "penunjukan_akhir",
                            repetability_lama[0].get(
                                "penunjukan",
                                0
                            )
                        )
                        or 0
                    )
                except (TypeError, ValueError):
                    penunjukan_repet_lama_kg = None
            
            if penunjukan_repet_lama_kg is not None:
                penunjukan_acuan_tampil = float(
                    kg_to_satuan(
                        penunjukan_repet_lama_kg,
                        satuan_tampilan
                    )
                )
            else:
                penunjukan_acuan_tampil = float(
                    muatan_repet_tampil
                )

            for i in range(1, 4):
                cols_repet = st.columns([3.5, 1.5])

                with cols_repet[0]:
                    col_nilai, col_satuan = st.columns([4, 1])

                    with col_nilai:
                        if i == 1:
                            penunjukan_akhir_tampil = st.number_input(
                                f"Penunjukan Akhir Repetability {i}",
                                min_value=0.0,
                                value=float(
                                    penunjukan_acuan_tampil
                                ),
                                step=float(step_repet),
                                format=format_repet,
                                key=(
                                    "tb_repet_sederhana_penunjukan_akhir_1_"
                                    f"{nama_alat_repet}_{muatan_repet_tampil}_"
                                    f"{daya_baca_kg}_{e}_{satuan_tampilan}"
                                ),
                                label_visibility="collapsed"
                            )

                            penunjukan_acuan_tampil = float(
                                penunjukan_akhir_tampil
                            )

                        else:
                            penunjukan_akhir_tampil = st.number_input(
                                f"Penunjukan Akhir Repetability {i}",
                                min_value=0.0,
                                value=float(penunjukan_acuan_tampil),
                                step=float(step_repet),
                                format=format_repet,
                                disabled=True,
                                key=(
                                    f"tb_repet_sederhana_penunjukan_akhir_{i}_"
                                    f"{nama_alat_repet}_{penunjukan_acuan_tampil}_"
                                    f"{daya_baca_kg}_{e}_{satuan_tampilan}"
                                ),
                                label_visibility="collapsed"
                            )

                    with col_satuan:
                        st.markdown(
                            f"<div style='padding-top:8px;'>"
                            f"{satuan_tampilan}</div>",
                            unsafe_allow_html=True
                        )

                with cols_repet[1]:
                    hasil = st.text_input(
                        f"Hasil Repetability {i}",
                        value="SAH",
                        disabled=True,
                        key=(
                            f"tb_repet_sederhana_hasil_{i}_"
                            f"{nama_alat_repet}_{daya_baca_kg}_{e}"
                        ),
                        label_visibility="collapsed"
                    )

                penunjukan_akhir_kg = satuan_to_kg(
                    penunjukan_akhir_tampil,
                    satuan_tampilan
                )

                penunjukan_repet_list.append(
                    penunjukan_akhir_kg
                )

                repet_data.append({
                    "penunjukan": penunjukan_akhir_kg,
                    "penunjukan_tampil": penunjukan_akhir_tampil,
                    "penunjukan_text": (
                        format_angka_id(
                            penunjukan_akhir_tampil,
                            decimal_repet
                        )
                        + f" {satuan_tampilan}"
                    ),

                    "penunjukan_akhir": penunjukan_akhir_kg,
                    "penunjukan_akhir_tampil": penunjukan_akhir_tampil,
                    "penunjukan_akhir_text": (
                        format_angka_id(
                            penunjukan_akhir_tampil,
                            decimal_repet
                        )
                        + f" {satuan_tampilan}"
                    ),

                    "naik_05e": 0.0,
                    "naik_05e_tampil": 0.0,
                    "naik_05e_text": "",

                    "periksa": "",
                    "angkat_05e": "",

                    "hasil": hasil == "SAH",
                    "hasil_text": hasil,

                    "delta_l": 0.0,
                    "delta_l_tampil": 0.0,
                    "delta_l_text": "",

                    "p_value": penunjukan_akhir_kg,
                    "bkd_koef": None,
                    "bkd_kg": None,
                    "bkd_text": "",
                })

            if penunjukan_repet_list:
                pmax_kg = max(penunjukan_repet_list)
                pmin_kg = min(penunjukan_repet_list)
                r_kg = pmax_kg - pmin_kg
            else:
                r_kg = 0.0

            r_tampil = kg_to_satuan(
                r_kg,
                satuan_tampilan
            )

            r_text = format_angka_id(
                r_tampil,
                decimal_repet
            )

            row_r = st.columns([3.5, 1.5])

            with row_r[0]:
                st.markdown(
                    f"**R = Pmax - Pmin = {r_text}**"
                )

        # ============================================================
        # B. REPETABILITY LENGKAP
        # Timbangan Elektronik dengan e = d
        # ============================================================
        else:
            st.markdown("---")
            st.subheader("Repetability (50% Maks)")

            if keterangan_ed:
                st.caption(keterangan_ed)

            satuan_tampilan = st.session_state.get(
                "tb_satuan_kapasitas_max",
                "kg"
            )

            kapasitas_max = get_input_kg(
                "kapasitas_max_input",
                0.0
            )

            interval_skala = get_input_kg(
                "interval_skala_input",
                0.0
            )

            daya_baca_kg = get_input_kg(
                "daya_baca_input",
                interval_skala
            )

            kelas = st.session_state.get(
                "tb_kelas",
                "III"
            )

            keterangan = st.session_state.get(
                "tb_keterangan",
                "Tera Ulang"
            )

            if kapasitas_max <= 0:
                st.warning(
                    "Isi Maksimum Menimbang terlebih dahulu."
                )
                st.stop()

            if interval_skala <= 0:
                st.warning(
                    "Interval Skala Verifikasi belum tersedia."
                )
                st.stop()

            if daya_baca_kg <= 0:
                daya_baca_kg = interval_skala

            daya_baca_tampil = kg_to_satuan(
                daya_baca_kg,
                satuan_tampilan
            )

            decimal_penunjukan = get_decimal_places_from_number(
                daya_baca_tampil
            )

            format_penunjukan = (
                f"%.{decimal_penunjukan}f"
            )

            step_penunjukan_tampil = daya_baca_tampil

            if step_penunjukan_tampil <= 0:
                step_penunjukan_tampil = kg_to_satuan(
                    interval_skala,
                    satuan_tampilan
                )

            # Beban Repetability = 50% maksimum.
            half_max_kg = kapasitas_max * 0.5

            half_max_tampil = kg_to_satuan(
                half_max_kg,
                satuan_tampilan
            )

            repet_signature = (
                f"{kapasitas_max:.10f}_"
                f"{satuan_tampilan}_"
                f"{daya_baca_kg:.10f}_"
                f"{interval_skala:.10f}"
            )

            # Nilai 0,5e.
            nilai_naik_kg = interval_skala * 0.5

            nilai_naik_tampil = kg_to_satuan(
                nilai_naik_kg,
                satuan_tampilan
            )

            decimal_naik = max(
                1,
                get_decimal_places_from_number(
                    nilai_naik_tampil
                )
            )

            format_naik = f"%.{decimal_naik}f"

            signature_naik = (
                f"{interval_skala:.10f}_"
                f"{satuan_tampilan}"
            )

            # Header enam kolom.
            col_header = st.columns([
                2.2,
                1.4,
                1.3,
                1.4,
                2.2,
                1.2,
            ])

            with col_header[0]:
                st.write("**Penunjukan (I)**")

            with col_header[1]:
                st.write("**Naikkan 0,5e**")

            with col_header[2]:
                st.write("**Periksa**")

            with col_header[3]:
                st.write("")

            with col_header[4]:
                st.write("**Penunjukan**")

            with col_header[5]:
                st.write("**Hasil**")

            repet_data = []
            penunjukan_repet_list = []

            for i in range(1, 4):
                # =====================================================
                # DATA REPETABILITY LAMA BARIS INI
                # =====================================================
                row_repet_lama = {}
                
                if (i - 1) < len(
                    repetability_lama
                ):
                    row_repet_lama = (
                        repetability_lama[i - 1]
                        or {}
                    )
                # Harus enam kolom karena kode memakai indeks 0 sampai 5.
                cols_repet = st.columns([
                    2.2,
                    1.4,
                    1.3,
                    1.4,
                    2.2,
                    1.2,
                ])

                # --------------------------------------------
                # Penunjukan awal
                # --------------------------------------------
                with cols_repet[0]:
                    col_pen_nilai, col_pen_satuan = st.columns(
                        [4, 1]
                    )

                    with col_pen_nilai:
                        if row_repet_lama:
                            try:
                                penunjukan_awal_lama_kg = float(
                                    row_repet_lama.get(
                                        "penunjukan",
                                        half_max_kg
                                    )
                                    or half_max_kg
                                )
                            except (TypeError, ValueError):
                                penunjukan_awal_lama_kg = half_max_kg
                        
                            default_penunjukan_repet_tampil = kg_to_satuan(
                                penunjukan_awal_lama_kg,
                                satuan_tampilan
                            )
                        
                        else:
                            default_penunjukan_repet_tampil = half_max_tampil
                        penunjukan_tampil = st.number_input(
                            f"Penunjukan Repetability {i}",
                            min_value=0.0,
                            value=float(
                                default_penunjukan_repet_tampil
                            ),
                            step=float(step_penunjukan_tampil),
                            format=format_penunjukan,
                            key=(
                                f"tb_repet_penunjukan_awal_{i}_"
                                f"{repet_signature}"
                            ),
                            label_visibility="collapsed"
                        )

                    with col_pen_satuan:
                        st.markdown(
                            f"<div style='padding-top:8px;'>"
                            f"{satuan_tampilan}</div>",
                            unsafe_allow_html=True
                        )

                I_kg = satuan_to_kg(
                    penunjukan_tampil,
                    satuan_tampilan
                )

                # --------------------------------------------
                # Naikkan 0,5e
                # --------------------------------------------
                with cols_repet[1]:
                    col_naik_nilai, col_naik_satuan = st.columns(
                        [4, 1]
                    )

                    with col_naik_nilai:
                        st.number_input(
                            f"Naikkan 0,5e Repetability {i}",
                            min_value=0.0,
                            value=float(nilai_naik_tampil),
                            step=(
                                float(nilai_naik_tampil)
                                if nilai_naik_tampil > 0
                                else 0.0001
                            ),
                            format=format_naik,
                            disabled=True,
                            key=(
                                f"tb_repet_naik_05e_{i}_"
                                f"{signature_naik}"
                            ),
                            label_visibility="collapsed"
                        )

                    with col_naik_satuan:
                        st.markdown(
                            f"<div style='padding-top:8px;'>"
                            f"{satuan_tampilan}</div>",
                            unsafe_allow_html=True
                        )

                # --------------------------------------------
                # Periksa
                # --------------------------------------------
                with cols_repet[2]:
                    periksa = st.text_input(
                        f"Periksa Repetability {i}",
                        value="Berubah",
                        disabled=True,
                        key=(
                            f"tb_repet_periksa_{i}_"
                            f"{repet_signature}"
                        ),
                        label_visibility="collapsed"
                    )

                # --------------------------------------------
                # Angkat 0,5e
                # --------------------------------------------
                with cols_repet[3]:
                    if i == 2:
                        st.text_input(
                            "Angkat 0,5e",
                            value="Angkat 0,5e",
                            disabled=True,
                            key=(
                                "tb_repet_angkat_05e_merged_"
                                f"{repet_signature}"
                            ),
                            label_visibility="collapsed"
                        )
                    else:
                        st.write("")

                # --------------------------------------------
                # Penunjukan akhir
                # --------------------------------------------
                with cols_repet[4]:
                    col_pen2_nilai, col_pen2_satuan = st.columns(
                        [4, 1]
                    )

                    with col_pen2_nilai:
                        penunjukan_akhir_tampil = st.number_input(
                            f"Penunjukan Akhir Repetability {i}",
                            min_value=0.0,
                            value=float(penunjukan_tampil),
                            step=float(step_penunjukan_tampil),
                            format=format_penunjukan,
                            disabled=True,
                            key=(
                                f"tb_repet_penunjukan_akhir_{i}_"
                                f"{repet_signature}_"
                                f"{penunjukan_tampil}"
                            ),
                            label_visibility="collapsed"
                        )

                    with col_pen2_satuan:
                        st.markdown(
                            f"<div style='padding-top:8px;'>"
                            f"{satuan_tampilan}</div>",
                            unsafe_allow_html=True
                        )

                penunjukan_akhir_kg = satuan_to_kg(
                    penunjukan_akhir_tampil,
                    satuan_tampilan
                )

                penunjukan_repet_list.append(
                    penunjukan_akhir_kg
                )

                # --------------------------------------------
                # Hasil
                # --------------------------------------------
                with cols_repet[5]:
                    if i == 2:
                        hasil = st.text_input(
                            "Hasil Repetability",
                            value="SAH",
                            disabled=True,
                            key=(
                                "tb_repet_hasil_merged_"
                                f"{repet_signature}"
                            ),
                            label_visibility="collapsed"
                        )
                    else:
                        hasil = "SAH"
                        st.write("")

                repet_data.append({
                    "penunjukan": I_kg,
                    "penunjukan_tampil": penunjukan_tampil,
                    "penunjukan_text": (
                        format_angka_id(
                            penunjukan_tampil,
                            decimal_penunjukan
                        )
                        + f" {satuan_tampilan}"
                    ),

                    "naik_05e": nilai_naik_kg,
                    "naik_05e_tampil": nilai_naik_tampil,
                    "naik_05e_text": (
                        format_angka_id(
                            nilai_naik_tampil,
                            decimal_naik
                        )
                        + f" {satuan_tampilan}"
                    ),

                    "periksa": periksa,
                    "angkat_05e": "Angkat 0,5e",

                    "penunjukan_akhir": penunjukan_akhir_kg,
                    "penunjukan_akhir_tampil": penunjukan_akhir_tampil,
                    "penunjukan_akhir_text": (
                        format_angka_id(
                            penunjukan_akhir_tampil,
                            decimal_penunjukan
                        )
                        + f" {satuan_tampilan}"
                    ),

                    "hasil": hasil == "SAH",
                    "hasil_text": hasil,

                    # Kompatibilitas generator cerapan lama.
                    "delta_l": nilai_naik_kg,
                    "delta_l_tampil": nilai_naik_tampil,
                    "delta_l_text": (
                        format_angka_id(
                            nilai_naik_tampil,
                            decimal_naik
                        )
                        + f" {satuan_tampilan}"
                    ),

                    "p_value": I_kg,
                    "bkd_koef": None,
                    "bkd_kg": None,
                    "bkd_text": "",
                })

            if penunjukan_repet_list:
                pmax_kg = max(penunjukan_repet_list)
                pmin_kg = min(penunjukan_repet_list)
                r_kg = pmax_kg - pmin_kg
            else:
                r_kg = 0.0

            r_tampil = kg_to_satuan(
                r_kg,
                satuan_tampilan
            )

            r_text = format_angka_id(
                r_tampil,
                decimal_penunjukan
            )

            row_r = st.columns([
                2.2,
                1.4,
                1.3,
                1.4,
                2.2,
                1.2,
            ])

            with row_r[4]:
                st.markdown(
                    f"**R = Pmax - Pmin = {r_text}**"
                )            



        # =========================================================
        # ALAT STANDAR UNTUK FORM PEMINJAMAN
        # =========================================================
        st.markdown("---")
        st.subheader("⚖️ Alat Standar untuk Peminjaman")

        st.caption(
            "Pilih alat standar dan jumlahnya. Gunakan tombol "
            "Tambah Alat Standar untuk menambahkan baris berikutnya."
        )

        opsi_alat_peminjaman = [
            "AT 20 kg",
            "AT 10 kg",
            "AT 5 kg",
            "AT 2 kg",
            "AT 1 kg",
            "AT M1",
            "AT F2",
        ]

        daftar_tersimpan = (
            st.session_state.tb_saved_data.get(
                "daftar_alat_standar_peminjaman",
                []
            )
        )

        if not isinstance(daftar_tersimpan, list):
            daftar_tersimpan = []

        # Minimal selalu tersedia satu baris.
        if "tb_jumlah_baris_alat_standar" not in st.session_state:
            st.session_state.tb_jumlah_baris_alat_standar = max(
                1,
                len(daftar_tersimpan)
            )

        jumlah_baris_alat = int(
            st.session_state.tb_jumlah_baris_alat_standar
        )

        daftar_alat_standar_peminjaman = []

        for indeks in range(jumlah_baris_alat):
            data_lama = (
                daftar_tersimpan[indeks]
                if indeks < len(daftar_tersimpan)
                and isinstance(daftar_tersimpan[indeks], dict)
                else {}
            )

            alat_lama = str(
                data_lama.get(
                    "jenis_alat",
                    opsi_alat_peminjaman[0]
                )
            )

            if alat_lama not in opsi_alat_peminjaman:
                alat_lama = opsi_alat_peminjaman[0]

            col_alat, col_jumlah = st.columns([3, 1])

            with col_alat:
                alat_dipilih = st.selectbox(
                    f"Alat Standar {indeks + 1}",
                    options=opsi_alat_peminjaman,
                    index=opsi_alat_peminjaman.index(
                        alat_lama
                    ),
                    key=f"tb_jenis_alat_standar_{indeks}",
                )

            jumlah_tetap_satu = alat_dipilih in {
                "AT M1",
                "AT F2",
            }

            with col_jumlah:
                if jumlah_tetap_satu:
                    jumlah_dipilih = st.number_input(
                        f"Jumlah {indeks + 1} (set)",
                        min_value=1,
                        max_value=1,
                        value=1,
                        step=1,
                        disabled=True,
                        key=f"tb_jumlah_alat_standar_{indeks}_tetap",
                        help=(
                            f"{alat_dipilih} selalu dipinjam "
                            "sebanyak 1 set."
                        ),
                    )
                else:
                    jumlah_awal = data_lama.get(
                        "jumlah_angka",
                        data_lama.get("jumlah", 1)
                    )

                    try:
                        jumlah_awal = int(jumlah_awal)
                    except (TypeError, ValueError):
                        jumlah_awal = 1

                    jumlah_dipilih = st.number_input(
                        f"Jumlah {indeks + 1} (buah)",
                        min_value=1,
                        value=max(1, jumlah_awal),
                        step=1,
                        key=f"tb_jumlah_alat_standar_{indeks}",
                    )

            satuan_jumlah = (
                "Set"
                if jumlah_tetap_satu
                else "Buah"
            )

            daftar_alat_standar_peminjaman.append(
                {
                    "jenis_alat": alat_dipilih,
                    "nomor_seri": "",
                    "jumlah_angka": int(jumlah_dipilih),
                    "jumlah": (
                        f"{int(jumlah_dipilih)} "
                        f"{satuan_jumlah}"
                    ),
                    "lama_peminjaman": "1 Hari",
                }
            )

        col_tambah, col_hapus, col_kosong = st.columns(
            [1.4, 1.4, 3]
        )

        with col_tambah:
            if st.button(
                "➕ Tambah Alat Standar",
                key="tb_tambah_baris_alat_standar",
                use_container_width=True,
            ):
                st.session_state.tb_jumlah_baris_alat_standar += 1
                st.rerun()

        with col_hapus:
            if st.button(
                "➖ Hapus Baris Terakhir",
                key="tb_hapus_baris_alat_standar",
                use_container_width=True,
                disabled=jumlah_baris_alat <= 1,
            ):
                indeks_terakhir = (
                    st.session_state.tb_jumlah_baris_alat_standar
                    - 1
                )

                for key in [
                    f"tb_jenis_alat_standar_{indeks_terakhir}",
                    f"tb_jumlah_alat_standar_{indeks_terakhir}",
                    (
                        f"tb_jumlah_alat_standar_"
                        f"{indeks_terakhir}_tetap"
                    ),
                ]:
                    st.session_state.pop(key, None)

                st.session_state.tb_jumlah_baris_alat_standar -= 1
                st.rerun()

        tambahkan_alat_standar = bool(
            daftar_alat_standar_peminjaman
        )

        # ======================== TOMBOL SIMPAN ========================
        col_submit1, col_submit2 = st.columns(2)
        with col_submit1:
            submit_btn = st.button("💾 Simpan Data", key="tb_simpan", use_container_width=True, type="primary")
        with col_submit2:
            st.button("🔄 Reset Form", key="tb_reset", use_container_width=True, on_click=reset_form_timbangan)

        if submit_btn:
            satuan = st.session_state.get(
                "tb_satuan_kapasitas_max",
                "kg"
            )

            if is_neraca:
                kapasitas_max_kg = convert_to_kg(
                    st.session_state.get(
                        "tb_kapasitas_max_neraca_input",
                        ""
                    ),
                    satuan
                )
                kapasitas_min_final = convert_to_kg(
                    st.session_state.get(
                        "tb_kapasitas_min_neraca_input",
                        ""
                    ),
                    satuan
                )
                daya_baca_kg = 0.0
                interval_skala_kg = (
                    kapasitas_max_kg / 10000.0
                    if kapasitas_max_kg > 0
                    else 0.0
                )
                kelas_final = "III"

                if kapasitas_max_kg <= 0:
                    st.error(
                        "Maksimum Menimbang Neraca belum diisi."
                    )
                    st.stop()

                if kapasitas_min_final <= 0:
                    st.error(
                        "Minimum Menimbang Neraca belum diisi."
                    )
                    st.stop()

                if kapasitas_min_final > kapasitas_max_kg:
                    st.error(
                        "Minimum menimbang tidak boleh lebih besar "
                        "dari maksimum menimbang."
                    )
                    st.stop()
            elif is_timbangan_meja:
                kapasitas_max_kg = convert_to_kg(
                    st.session_state.get(
                        "tb_kapasitas_max_input",
                        ""
                    ),
                    satuan
                )

                daya_baca_kg = 0.0

                interval_skala_kg = (
                    kapasitas_max_kg / 1000.0
                    if kapasitas_max_kg > 0
                    else 0.0
                )

                kelas_final = st.session_state.get(
                    "tb_kelas",
                    "III"
                )

                kapasitas_min_final = st.session_state.get(
                    "tb_kapasitas_min_kg",
                    0.0
                )

                if kapasitas_max_kg <= 0:
                    st.error(
                        "Maksimum Menimbang Timbangan Meja belum diisi."
                    )
                    st.stop()

                if kelas_final not in ["III", "IIII"]:
                    st.error(
                        "Kelas Timbangan Meja harus III atau IIII."
                    )
                    st.stop()

                if interval_skala_kg <= 0:
                    st.error(
                        "Interval Skala Verifikasi Timbangan Meja belum terbentuk."
                    )
                    st.stop()

                if kapasitas_min_final <= 0:
                    st.error(
                        "Minimum Menimbang Timbangan Meja belum terbentuk."
                    )
                    st.stop()
            
            else:
                kapasitas_max_kg = convert_to_kg(
                    st.session_state.get(
                        "tb_kapasitas_max_input",
                        ""
                    ),
                    satuan
                )

                daya_baca_kg = convert_to_kg(
                    st.session_state.get(
                        "tb_daya_baca_input",
                        ""
                    ),
                    satuan
                )

                if is_timbangan_elektronik:
                    interval_skala_kg = convert_to_kg(
                        st.session_state.get(
                            "tb_interval_skala_input",
                            ""
                        ),
                        satuan
                    )
                else:
                    interval_skala_kg = daya_baca_kg

                kelas_final = st.session_state.get(
                    "tb_kelas",
                    "III"
                )

                kapasitas_min_final = st.session_state.get(
                    "tb_kapasitas_min_kg",
                    0.0
                )

                if kapasitas_max_kg <= 0:
                    st.error(
                        "Kapasitas maksimum belum diisi."
                    )
                    st.stop()

                if daya_baca_kg <= 0:
                    st.error(
                        "Daya baca belum diisi."
                    )
                    st.stop()

                if interval_skala_kg <= 0:
                    st.error(
                        "Interval skala verifikasi belum diisi."
                    )
                    st.stop()

                if kapasitas_min_final > kapasitas_max_kg:
                    st.error(
                        "Kapasitas minimum tidak boleh lebih besar "
                        "dari kapasitas maksimum."
                    )
                    st.stop()

            keterangan_final = st.session_state.get(
                "tb_keterangan",
                "Tera Ulang"
            )

            metode = st.session_state.get(
                "tb_metode_pengujian",
                "Beban Substitusi Tunggal"
            )
            at_standar = st.session_state.get(
                "tb_at_standar",
                "M2"
            )
            # =====================================================
            # SIMPAN NOMOR DOKUMEN LAMA JIKA SEDANG MODE EDIT
            # =====================================================
            sedang_edit = bool(
                st.session_state.get(
                    "tb_edit_pengujian_id"
                )
            )
            
            nomor_sertifikat_lama = (
                st.session_state
                .get(
                    "tb_saved_data",
                    {}
                )
                .get(
                    "nomor_sertifikat",
                    ""
                )
            )
            
            nomor_order_lama = (
                st.session_state
                .get(
                    "tb_saved_data",
                    {}
                )
                .get(
                    "nomor_order",
                    ""
                )
            )
            st.session_state.tb_saved_data = {
                'pemilik': pemilik,
                'alamat': alamat,
                'nama_alat': nama_alat,
                'is_neraca': is_neraca,
                'is_timbangan_meja': is_timbangan_meja,
                'merek': merek,
                'model': model,
                'no_seri': no_seri,
                'kapasitas_max': kapasitas_max_kg,
                'kapasitas_min': kapasitas_min_final,
                'daya_baca': daya_baca_kg,
                'interval_skala': interval_skala_kg,
                'satuan': satuan,
                'kelas': kelas_final,
                'suhu': suhu,
                'kelembaban': kelembaban,
                'metode': metode,
                'at_standar': at_standar,
                'tambahkan_alat_standar': bool(
                    tambahkan_alat_standar
                ),
                'daftar_alat_standar_peminjaman': (
                    list(daftar_alat_standar_peminjaman)
                ),
                # Kompatibilitas dengan generator/versi lama.
                'alat_standar_peminjaman': [
                    item.get("jenis_alat", "")
                    for item in daftar_alat_standar_peminjaman
                ],
                'jumlah_alat_standar_peminjaman': {
                    item.get("jenis_alat", ""): item.get(
                        "jumlah_angka",
                        1
                    )
                    for item in daftar_alat_standar_peminjaman
                },
                'lokasi': st.session_state.get('tb_lokasi_pengujian', 'Perusahaan'),
                'nama_penera': nama_penera,
                'nip_penera': nip_penera,
                'golongan_penera': st.session_state.get('tb_golongan_penera', ''),
                'nama_penera_2': nama_penera_2,
                'hasil_pengujian': test_results,
                'jumlah_titik_uji': jumlah_titik_uji,
                'tanggal': tanggal.strftime('%Y-%m-%d'),
                'tanggal_penera': format_tanggal_indonesia(tanggal.strftime('%Y-%m-%d')),
                'tanggal_tanda_tangan': (
                    tanggal_tanda_tangan.strftime("%Y-%m-%d")
                ),
                'keterangan': keterangan_final,
                'nomor_sertifikat': (
                    nomor_sertifikat_lama
                    if sedang_edit
                    else ""
                ),
                
                'nomor_order': (
                    nomor_order_lama
                    if sedang_edit
                    else ""
                ),
                'berlaku_sampai': add_one_year_safe(tanggal).strftime('%Y-%m-%d'),
                'repetability': repet_data,
                'repetability_sederhana': repet_sederhana,
                'eksentrisitas': eksen_data,
                'penyetelan_nol': [],
                'visual': visual_results,
            }
            st.session_state.tb_test_results = test_results

            # Dokumen lama tidak boleh tetap tersedia setelah data berubah.
            st.session_state.tb_generated_files = {}
            if sedang_edit:
                st.session_state[
                    "tb_nomor_sertifikat"
                ] = nomor_sertifikat_lama
            
                st.session_state[
                    "tb_nomor_order"
                ] = nomor_order_lama
            
            else:
                st.session_state.pop(
                    "tb_nomor_sertifikat",
                    None
                )
            
                st.session_state.pop(
                    "tb_nomor_order",
                    None
                )
            st.success("✅ Data berhasil disimpan!")
            st.balloons()


    # ===== MODE 2: GENERATE DOKUMEN =====
    elif mode == "📄 Generate Dokumen":
        st.header("Generate Dokumen Cerapan & Sertifikat")
    
        if not st.session_state.tb_saved_data:
            st.warning("⚠️ Silakan input data pengujian terlebih dahulu di menu 'Input Data Pengujian'")
        else:
            data = st.session_state.tb_saved_data
        
            col1, col2 = st.columns(2)
        
            with col1:
                st.subheader("📋 Preview Data")
                preview_cols = st.columns(2)
            
                with preview_cols[0]:
                    st.write(f"**Pemilik:** {data.get('pemilik', '-')}")
                    st.write(f"**Nama Alat:** {data.get('nama_alat', '-')}")
                    st.write(f"**Merek:** {data.get('merek', '-')}")
                    st.write(
                        f"**Model / Tipe:** "
                        f"{data.get('model', '-')}"
                    )
                    st.write(f"**No. Seri:** {data.get('no_seri', '-')}")
            
                with preview_cols[1]:
                    st.write(f"**Penera:** {data.get('nama_penera', '-')}")
                    st.write(f"**Tanggal:** {data.get('tanggal_penera', '-')}")
                    st.write(
                        f"**Tanggal Sertifikat:** "
                        f"{format_tanggal_indonesia(data.get('tanggal_tanda_tangan', ''))}"
                    )
                    st.write(f"**Kelas:** {data.get('kelas', '-')}")
                    st.write(f"**Hasil Pengujian:** {len(data.get('hasil_pengujian', []))} data")
        
            with col2:
                st.subheader("📊 Nomor Dokumen")
            
                tanggal_data = _parse_date_safe(
                    data.get(
                        "tanggal"
                    ),
                    datetime.now().date()
                )

                default_sertifikat = generate_nomor_sertifikat(
                    tanggal_data
                )

                default_order = generate_nomor_order(
                    tanggal_data
                )
            
                nomor_sertifikat = st.text_input(
                    "Nomor Sertifikat",
                    value=(
                        data.get("nomor_sertifikat")
                        or default_sertifikat
                    ),
                    placeholder=(
                        "Format: "
                        "XXX.X.X.XX/XXXX/XXX-X/X/XXXX"
                    ),
                    key="tb_nomor_sertifikat",
                )
            
                nomor_order = st.text_input(
                    "Nomor Order",
                    value=(
                        data.get("nomor_order")
                        or default_order
                    ),
                    placeholder="Format nomor order",
                    key="tb_nomor_order",
                )
            
            st.session_state.tb_saved_data[
                "nomor_sertifikat"
            ] = nomor_sertifikat

            st.session_state.tb_saved_data[
                "nomor_order"
            ] = nomor_order

            data = st.session_state.tb_saved_data
        
            st.markdown("---")
        
            # Button untuk generate
            col_btn1, col_btn2, col_btn3 = st.columns(3)
        
            # --- Tombol Generate Cerapan ---
            with col_btn1:
                if st.button(
                    "📝 Generate Cerapan",
                    key="tb_generate_cerapan",
                    use_container_width=True,
                ):
                    try:
                        output_path = OUTPUT_DIR
                        output_path.mkdir(parents=True, exist_ok=True)

                        nama_file_cerapan = format_nama_file_dokumen(
                            data,
                            "CERAPAN",
                        )
                        filename = output_path / nama_file_cerapan

                        generate_cerapan_pdf(
                            st.session_state.tb_saved_data,
                            str(filename),
                        )
                        st.session_state.tb_generated_files["cerapan"] = (
                            str(filename)
                        )
                        st.success("✅ Cerapan berhasil dibuat!")

                    except Exception as exc:
                        st.error(f"❌ Error: {exc}")
                        st.code(traceback.format_exc())

            # --- Tombol Generate Sertifikat ---
            with col_btn2:
                if st.button(
                    "🎫 Generate Sertifikat",
                    key="tb_generate_sertifikat",
                    use_container_width=True,
                ):
                    try:
                        output_path = OUTPUT_DIR
                        output_path.mkdir(parents=True, exist_ok=True)

                        nama_file_sertifikat = format_nama_file_dokumen(
                            data,
                            "SERTIFIKAT",
                        )
                        filename = output_path / nama_file_sertifikat

                        generate_sertifikat_pdf(
                            st.session_state.tb_saved_data,
                            str(filename),
                            nomor_sertifikat,
                        )
                        st.session_state.tb_generated_files["sertifikat"] = (
                            str(filename)
                        )
                        st.session_state.tb_saved_data[
                            "nomor_sertifikat"
                        ] = nomor_sertifikat
                        
                        st.session_state.tb_saved_data[
                            "nomor_order"
                        ] = nomor_order
                        
                        try:
                            simpan_pengujian_timbangan_ke_supabase(
                                st.session_state.tb_saved_data
                            )
                        
                            st.success(
                                "✅ Sertifikat berhasil dibuat dan "
                                "data pengujian berhasil disimpan ke database."
                            )
                        
                        except Exception as db_error:
                            error_text = str(db_error)
                        
                            if (
                                "duplicate key value violates unique constraint"
                                in error_text
                                and "pengujian_nomor_sertifikat_unique"
                                in error_text
                            ):
                                st.error(
                                    "❌ Nomor sertifikat sudah pernah digunakan. "
                                    "Silakan gunakan nomor sertifikat yang berbeda."
                                )
                        
                            else:
                                st.warning(
                                    "⚠️ Sertifikat berhasil dibuat, "
                                    "tetapi data gagal disimpan ke database."
                                )
                        
                                st.exception(db_error)
                    except Exception as exc:
                        st.error(f"❌ Error: {exc}")
                        st.code(traceback.format_exc())

            # --- Tombol Generate Kedua Dokumen ---
            with col_btn3:
                if st.button(
                    "📦 Generate Kedua Dokumen",
                    key="tb_generate_keduanya",
                    use_container_width=True,
                ):
                    try:
                        output_path = OUTPUT_DIR
                        output_path.mkdir(parents=True, exist_ok=True)

                        nama_file_cerapan = format_nama_file_dokumen(
                            data,
                            "CERAPAN",
                        )
                        cerapan_file = output_path / nama_file_cerapan

                        generate_cerapan_pdf(
                            st.session_state.tb_saved_data,
                            str(cerapan_file),
                        )
                        st.session_state.tb_generated_files["cerapan"] = (
                            str(cerapan_file)
                        )

                        nama_file_sertifikat = format_nama_file_dokumen(
                            data,
                            "SERTIFIKAT",
                        )
                        sertifikat_file = (
                            output_path / nama_file_sertifikat
                        )

                        generate_sertifikat_pdf(
                            st.session_state.tb_saved_data,
                            str(sertifikat_file),
                            nomor_sertifikat,
                        )
                        st.session_state.tb_generated_files["sertifikat"] = (
                            str(sertifikat_file)
                        )
                        st.session_state.tb_saved_data[
                            "nomor_sertifikat"
                        ] = nomor_sertifikat
                        
                        st.session_state.tb_saved_data[
                            "nomor_order"
                        ] = nomor_order
                        
                        try:
                            simpan_pengujian_timbangan_ke_supabase(
                                st.session_state.tb_saved_data
                            )
                        
                            st.success(
                                "✅ Cerapan dan sertifikat berhasil dibuat "
                                "serta data pengujian berhasil disimpan "
                                "ke database."
                            )
                        
                        except Exception as db_error:
                            error_text = str(db_error)
                        
                            if (
                                "duplicate key value violates unique constraint"
                                in error_text
                                and "pengujian_nomor_sertifikat_unique"
                                in error_text
                            ):
                                st.error(
                                    "❌ Nomor sertifikat sudah pernah digunakan. "
                                    "Silakan gunakan nomor sertifikat yang berbeda."
                                )
                        
                            else:
                                st.warning(
                                    "⚠️ Cerapan dan sertifikat berhasil dibuat, "
                                    "tetapi data gagal disimpan ke database."
                                )
                        
                                st.exception(db_error)

                    except Exception as exc:
                        st.error(f"❌ Error: {exc}")
                        st.code(traceback.format_exc())

            st.markdown("---")
        
            # =====================================================
            # GENERATE FORM PEMINJAMAN
            # =====================================================
            st.subheader("📄 Formulir Peminjaman")

            col_form1, col_form2 = st.columns(2)

            with col_form1:
                if st.button(
                    "⚖️ Generate Form Peminjaman Alat Standar",
                    key="tb_generate_form_standar",
                    use_container_width=True,
                ):
                    try:
                        output_path = OUTPUT_DIR
                        output_path.mkdir(
                            parents=True,
                            exist_ok=True
                        )

                        nama_file = format_nama_file_dokumen(
                            data,
                            "FORM_PEMINJAMAN_ALAT_STANDAR",
                        )
                        filename = output_path / nama_file

                        generate_form_peminjaman_standar_timbangan_pdf(
                            st.session_state.tb_saved_data,
                            str(filename),
                            nomor_surat_perintah="",
                        )

                        st.session_state.tb_generated_files[
                            "form_peminjaman_standar"
                        ] = str(filename)

                        st.success(
                            "✅ Form peminjaman alat standar "
                            "berhasil dibuat!"
                        )

                    except Exception as exc:
                        st.error(f"❌ Error: {exc}")
                        st.code(traceback.format_exc())

            with col_form2:
                if st.button(
                    "🔏 Generate Form Peminjaman CTT",
                    key="tb_generate_form_ctt",
                    use_container_width=True,
                ):
                    try:
                        output_path = OUTPUT_DIR
                        output_path.mkdir(
                            parents=True,
                            exist_ok=True
                        )

                        nama_file = format_nama_file_dokumen(
                            data,
                            "FORM_PEMINJAMAN_CTT",
                        )
                        filename = output_path / nama_file

                        generate_form_peminjaman_ctt_timbangan_pdf(
                            st.session_state.tb_saved_data,
                            str(filename),
                            nomor_surat_perintah="",
                        )

                        st.session_state.tb_generated_files[
                            "form_peminjaman_ctt"
                        ] = str(filename)

                        st.success(
                            "✅ Form peminjaman CTT berhasil dibuat!"
                        )

                    except Exception as exc:
                        st.error(f"❌ Error: {exc}")
                        st.code(traceback.format_exc())

            st.markdown("---")

            # ===== TOMBOL DOWNLOAD BERDASARKAN SESSION STATE =====
            st.subheader("📥 Download Dokumen")
        
            cerapan_path = (
                st.session_state.tb_generated_files.get(
                    "cerapan"
                )
            )
            sertifikat_path = (
                st.session_state.tb_generated_files.get(
                    "sertifikat"
                )
            )
            form_standar_path = (
                st.session_state.tb_generated_files.get(
                    "form_peminjaman_standar"
                )
            )
            form_ctt_path = (
                st.session_state.tb_generated_files.get(
                    "form_peminjaman_ctt"
                )
            )

            col_dl1, col_dl2, col_dl3, col_dl4 = st.columns(4)

            with col_dl1:
                if cerapan_path and Path(cerapan_path).exists():
                    with open(cerapan_path, "rb") as f:
                        st.download_button(
                            label="⬇️ Download Cerapan",
                            data=f.read(),
                            file_name=Path(cerapan_path).name,
                            mime="application/pdf",
                            use_container_width=True,
                            key="tb_download_cerapan",
                        )
                else:
                    st.caption("Cerapan belum digenerate.")
        
            with col_dl2:
                if sertifikat_path and Path(sertifikat_path).exists():
                    with open(sertifikat_path, "rb") as f:
                        st.download_button(
                            label="⬇️ Download Sertifikat",
                            data=f.read(),
                            file_name=Path(sertifikat_path).name,
                            mime="application/pdf",
                            use_container_width=True,
                            key="tb_download_sertifikat",
                        )
                else:
                    st.caption("Sertifikat belum digenerate.")

            with col_dl3:
                if (
                    form_standar_path
                    and Path(form_standar_path).exists()
                ):
                    with open(form_standar_path, "rb") as f:
                        st.download_button(
                            label=(
                                "⬇️ Download Form "
                                "Alat Standar"
                            ),
                            data=f.read(),
                            file_name=Path(
                                form_standar_path
                            ).name,
                            mime="application/pdf",
                            use_container_width=True,
                            key="tb_download_form_standar",
                        )
                else:
                    st.caption(
                        "Form alat standar belum digenerate."
                    )

            with col_dl4:
                if (
                    form_ctt_path
                    and Path(form_ctt_path).exists()
                ):
                    with open(form_ctt_path, "rb") as f:
                        st.download_button(
                            label="⬇️ Download Form CTT",
                            data=f.read(),
                            file_name=Path(
                                form_ctt_path
                            ).name,
                            mime="application/pdf",
                            use_container_width=True,
                            key="tb_download_form_ctt",
                        )
                else:
                    st.caption(
                        "Form CTT belum digenerate."
                    )
        
            st.markdown("---")
        
    # =========================================================
    # MODE 3: RIWAYAT TIMBANGAN
    # =========================================================
    elif mode == "📚 Riwayat Timbangan":
    
        st.header("📚 Riwayat Timbangan")
    
        try:
            supabase = get_supabase()
    
            # =====================================================
            # 1. AMBIL SEMUA UTTP JENIS TIMBANGAN
            # =====================================================
            response_uttp = (
                supabase
                .table("uttp")
                .select(
                    "id, perusahaan_id, jenis_uttp, merk, tipe, "
                    "nomor_seri, kapasitas, lokasi, status"
                )
                .order(
                    "jenis_uttp"
                )
                .execute()
            )
    
            semua_uttp = (
                response_uttp.data
                or []
            )
    
            # =====================================================
            # FILTER HANYA MODUL TIMBANGAN
            # =====================================================
            jenis_timbangan = {
                "Timbangan Elektronik",
                "Timbangan Pegas",
                "Timbangan Bobot Ingsut",
                "Timbangan Sentisimal",
                "Timbangan Meja",
                "Neraca Obat",
                "Timbangan Neraca Obat",
            }
    
            daftar_uttp = [
                item
                for item in semua_uttp
                if str(
                    item.get(
                        "jenis_uttp",
                        ""
                    )
                ).strip()
                in jenis_timbangan
            ]
    
            if not daftar_uttp:
                st.info(
                    "Belum ada data Timbangan "
                    "yang tersimpan di database."
                )
                st.stop()
    
            # =====================================================
            # 2. AMBIL PERUSAHAAN TERKAIT
            # =====================================================
            daftar_perusahaan_id = list({
                item.get("perusahaan_id")
                for item in daftar_uttp
                if item.get(
                    "perusahaan_id"
                ) is not None
            })
    
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
    
                daftar_perusahaan = (
                    response_perusahaan.data
                    or []
                )
    
            else:
                daftar_perusahaan = []
    
            perusahaan_by_id = {
                item["id"]: item
                for item in daftar_perusahaan
            }
    
            # =====================================================
            # 3. PILIH PERUSAHAAN
            # =====================================================
            perusahaan_map = {}
    
            for alat_item in daftar_uttp:
    
                perusahaan_id = (
                    alat_item.get(
                        "perusahaan_id"
                    )
                )
    
                perusahaan_item = (
                    perusahaan_by_id.get(
                        perusahaan_id,
                        {}
                    )
                )
    
                nama_perusahaan = str(
                    perusahaan_item.get(
                        "nama_perusahaan",
                        ""
                    )
                    or ""
                ).strip()
    
                if nama_perusahaan:
                    perusahaan_map[
                        nama_perusahaan
                    ] = perusahaan_item
    
            st.subheader(
                "Cari Perusahaan"
            )
    
            nama_perusahaan_terpilih = (
                st.selectbox(
                    "Nama Perusahaan",
                    options=sorted(
                        perusahaan_map.keys()
                    ),
                    index=None,
                    placeholder=(
                        "Ketik atau pilih "
                        "nama perusahaan..."
                    ),
                    key="tb_riwayat_perusahaan"
                )
            )
    
            if not nama_perusahaan_terpilih:
                st.info(
                    "Silakan pilih perusahaan "
                    "untuk melihat Timbangan "
                    "yang terdaftar."
                )
                st.stop()
    
            perusahaan = perusahaan_map[
                nama_perusahaan_terpilih
            ]
    
            perusahaan_id = (
                perusahaan["id"]
            )
    
            # =====================================================
            # 4. FILTER ALAT MILIK PERUSAHAAN
            # =====================================================
            daftar_alat = [
                item
                for item in daftar_uttp
                if item.get(
                    "perusahaan_id"
                ) == perusahaan_id
            ]
    
            if not daftar_alat:
                st.info(
                    "Belum ada Timbangan "
                    "untuk perusahaan ini."
                )
                st.stop()
    
            # =====================================================
            # 5. PILIH ALAT
            # =====================================================
            alat_map = {}
    
            for alat_item in daftar_alat:
    
                label = (
                    f"{alat_item.get('jenis_uttp') or '-'} | "
                    f"{alat_item.get('merk') or '-'} | "
                    f"{alat_item.get('tipe') or '-'} | "
                    f"No. Seri/Alat: "
                    f"{alat_item.get('nomor_seri') or '-'}"
                )
    
                alat_map[
                    label
                ] = alat_item
    
            alat_terpilih_label = (
                st.selectbox(
                    "Pilih Timbangan",
                    options=list(
                        alat_map.keys()
                    ),
                    index=None,
                    placeholder=(
                        "Pilih Timbangan..."
                    ),
                    key="tb_riwayat_alat"
                )
            )
    
            if not alat_terpilih_label:
                st.info(
                    "Silakan pilih Timbangan "
                    "untuk melihat riwayat "
                    "pengujiannya."
                )
                st.stop()
    
            alat = alat_map[
                alat_terpilih_label
            ]
    
            # =====================================================
            # 6. RINGKASAN ALAT
            # =====================================================
            st.markdown("---")
            st.subheader(
                "Ringkasan Timbangan"
            )
    
            col1, col2, col3 = (
                st.columns(3)
            )
    
            with col1:
                st.write(
                    "**Jenis Timbangan:**",
                    alat.get(
                        "jenis_uttp"
                    ) or "-"
                )
    
                st.write(
                    "**Perusahaan:**",
                    perusahaan.get(
                        "nama_perusahaan"
                    ) or "-"
                )
    
            with col2:
                st.write(
                    "**Merek:**",
                    alat.get(
                        "merk"
                    ) or "-"
                )
    
                st.write(
                    "**Model/Tipe:**",
                    alat.get(
                        "tipe"
                    ) or "-"
                )
    
            with col3:
                st.write(
                    "**No. Seri / No. Alat:**",
                    alat.get(
                        "nomor_seri"
                    ) or "-"
                )
    
                st.write(
                    "**Kapasitas:**",
                    alat.get(
                        "kapasitas"
                    ) or "-"
                )
    
            # =====================================================
            # 7. AMBIL RIWAYAT PENGUJIAN
            # =====================================================
            response_riwayat = (
                supabase
                .table("pengujian")
                .select("*")
                .eq(
                    "uttp_id",
                    alat["id"]
                )
                .order(
                    "tanggal_pengujian",
                    desc=True
                )
                .execute()
            )
    
            riwayat = (
                response_riwayat.data
                or []
            )
    
            st.markdown("---")
            st.subheader(
                "Riwayat Tera / Tera Ulang"
            )
    
            if not riwayat:
                st.info(
                    "Belum ada riwayat "
                    "pengujian untuk Timbangan ini."
                )
                st.stop()
    
            # =====================================================
            # 8. TABEL RIWAYAT
            # =====================================================
            data_tabel = []
    
            for r in riwayat:
                data_tabel.append({
                    "Tanggal": (
                        r.get(
                            "tanggal_pengujian"
                        )
                    ),
                    "Jenis": (
                        r.get(
                            "jenis_pengujian"
                        )
                    ),
                    "Hasil": (
                        r.get(
                            "hasil"
                        )
                    ),
                    "Nomor Order": (
                        r.get(
                            "nomor_order"
                        )
                    ),
                    "Nomor Sertifikat": (
                        r.get(
                            "nomor_sertifikat"
                        )
                    ),
                    "Penera": (
                        r.get(
                            "penera_1"
                        )
                    ),
                    "Berlaku Sampai": (
                        r.get(
                            "berlaku_sampai"
                        )
                    ),
                })
    
            st.dataframe(
                pd.DataFrame(
                    data_tabel
                ),
                use_container_width=True,
                hide_index=True,
            )
    
            # =====================================================
            # 9. PILIH RIWAYAT
            # =====================================================
            pilihan_riwayat = {}
    
            for r in riwayat:
    
                label = (
                    f"{r.get('tanggal_pengujian', '-')} | "
                    f"{r.get('jenis_pengujian', '-')} | "
                    f"{r.get('nomor_sertifikat', '-')} | "
                    f"{r.get('penera_1', '-')}"
                )
    
                pilihan_riwayat[
                    label
                ] = r
    
            st.markdown(
                "#### Pilih Data Pengujian"
            )
    
            riwayat_label = (
                st.selectbox(
                    "Pilih riwayat yang akan digunakan",
                    options=list(
                        pilihan_riwayat.keys()
                    ),
                    key=(
                        f"tb_pilih_riwayat_"
                        f"{alat['id']}"
                    )
                )
            )
    
            riwayat_terpilih = (
                pilihan_riwayat[
                    riwayat_label
                ]
            )
    
            with st.container(
                border=True
            ):
                st.write(
                    "**Tanggal:**",
                    riwayat_terpilih.get(
                        "tanggal_pengujian"
                    ) or "-"
                )
    
                st.write(
                    "**Jenis:**",
                    riwayat_terpilih.get(
                        "jenis_pengujian"
                    ) or "-"
                )
    
                st.write(
                    "**Nomor Sertifikat:**",
                    riwayat_terpilih.get(
                        "nomor_sertifikat"
                    ) or "-"
                )
    
                st.write(
                    "**Penera:**",
                    riwayat_terpilih.get(
                        "penera_1"
                    ) or "-"
                )
    
            # =====================================================
            # 10. AKSI RIWAYAT
            # =====================================================
            col_edit, col_baru = st.columns(2)
    
            with col_edit:
                if st.button(
                    "✏️ Edit Pengujian",
                    use_container_width=True,
                    key=(
                        f"tb_edit_riwayat_"
                        f"{riwayat_terpilih['id']}"
                    )
                ):
                    gunakan_data_lama_untuk_edit_timbangan(
                        alat,
                        perusahaan,
                        riwayat_terpilih
                    )
    
                    st.rerun()
    
            with col_baru:
                if st.button(
                    "➕ Tambah Pengujian Baru",
                    use_container_width=True,
                    key=(
                        f"tb_baru_riwayat_"
                        f"{riwayat_terpilih['id']}"
                    )
                ):
                    gunakan_data_lama_untuk_pengujian_baru_timbangan(
                        alat,
                        perusahaan,
                        riwayat_terpilih
                    )
    
                    st.rerun()
    
        except Exception as exc:
            st.error(
                "Gagal mengambil riwayat "
                "Timbangan dari Supabase."
            )
    
            st.exception(exc)
    st.markdown("---")
    st.markdown("""
        <div style='text-align: center; color: #888; font-size: 12px;'>
        <p>Aplikasi Automasi Sertifikat Tera © 2026</p>
        <p>Match dengan Template Excel & Word</p>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    run()
