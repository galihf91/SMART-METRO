import streamlit as st
import pandas as pd
from datetime import datetime, date
from supabase import create_client
from modules.timbangan_jembatan.cerapan_tj_generator import generate_cerapan_pdf
from modules.timbangan_jembatan.sertifikat_tj_generator import generate_sertifikat_pdf
from modules.timbangan_jembatan.form_peminjaman_standar_generator import (
    generate_form_peminjaman_standar_pdf
)
from modules.timbangan_jembatan.form_peminjaman_ctt_generator import (
    generate_form_peminjaman_ctt_pdf
)
import os
from pathlib import Path

# =========================================================
# KONEKSI SUPABASE
# =========================================================
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]

    return create_client(
        url,
        key
    )
def simpan_atau_update_perusahaan(
    supabase,
    nama_perusahaan,
    alamat
):
    nama_perusahaan = str(
        nama_perusahaan
    ).strip()

    alamat = str(
        alamat
    ).strip()

    if not nama_perusahaan:
        return None

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

    if response.data:
        perusahaan = response.data[0]

        perusahaan_id = perusahaan["id"]

        alamat_lama = (
            perusahaan.get("alamat")
            or ""
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

    response = (
        supabase
        .table("perusahaan")
        .insert({
            "nama_perusahaan": nama_perusahaan,
            "alamat": alamat
        })
        .execute()
    )

    return response.data[0]["id"]


def bulan_singkat_id(tanggal):
    bulan = {
        1: "JAN", 2: "FEB", 3: "MAR", 4: "APR",
        5: "MEI", 6: "JUN", 7: "JUL", 8: "AGS",
        9: "SEP", 10: "OKT", 11: "NOV", 12: "DES"
    }
    return bulan.get(tanggal.month, "")

def get_or_create_uttp_tj(
    supabase,
    perusahaan_id,
    merek,
    model,
    no_seri,
    kapasitas_max
):
    no_seri = str(no_seri).strip()

    if not no_seri:
        raise ValueError(
            "Nomor seri Timbangan Jembatan wajib diisi."
        )

    # Cari berdasarkan jenis UTTP + nomor seri
    response = (
        supabase
        .table("uttp")
        .select("*")
        .eq(
            "jenis_uttp",
            "Timbangan Jembatan"
        )
        .eq(
            "nomor_seri",
            no_seri
        )
        .execute()
    )

    # =====================================================
    # UTTP SUDAH ADA
    # =====================================================
    if response.data:
        uttp = response.data[0]

        (
            supabase
            .table("uttp")
            .update({
                "perusahaan_id": perusahaan_id,
                "merk": str(merek).strip(),
                "tipe": str(model).strip(),
                "kapasitas": str(
                    kapasitas_max
                ),
                "status": "aktif"
            })
            .eq(
                "id",
                uttp["id"]
            )
            .execute()
        )

        return uttp["id"]

    # =====================================================
    # UTTP BELUM ADA
    # =====================================================
    response = (
        supabase
        .table("uttp")
        .insert({
            "perusahaan_id": perusahaan_id,
            "jenis_uttp": "Timbangan Jembatan",
            "merk": str(merek).strip(),
            "tipe": str(model).strip(),
            "nomor_seri": no_seri,
            "kapasitas": str(
                kapasitas_max
            ),
            "lokasi": "Perusahaan",
            "status": "aktif"
        })
        .execute()
    )

    return response.data[0]["id"]

def simpan_pengujian_tj_ke_supabase(data):
    supabase = get_supabase()

    # =========================================
    # 1. PERUSAHAAN
    # =========================================
    perusahaan_id = simpan_atau_update_perusahaan(
        supabase,
        data.get("pemilik", ""),
        data.get("alamat", "")
    )

    # =========================================
    # 2. UTTP
    # =========================================
    uttp_id = get_or_create_uttp_tj(
        supabase,
        perusahaan_id,
        data.get("merek", ""),
        data.get("model", ""),
        data.get("no_seri", ""),
        data.get("kapasitas_max", "")
    )

    # =========================================
    # 3. DETAIL PENGUJIAN
    # =========================================
    detail_pengujian = {
        "kapasitas_max": data.get("kapasitas_max"),
        "kapasitas_min": data.get("kapasitas_min"),
        "daya_baca": data.get("daya_baca"),
        "interval_skala": data.get("interval_skala"),
        "kelas": data.get("kelas"),
        "suhu": data.get("suhu"),
        "kelembaban": data.get("kelembaban"),
        "metode": data.get("metode"),

        "hasil_kebenaran": data.get(
            "hasil_pengujian",
            []
        ),

        "repetability": data.get(
            "repetability",
            []
        ),

        "eksentrisitas": data.get(
            "eksentrisitas",
            []
        ),

        "penyetelan_nol": data.get(
            "penyetelan_nol",
            {}
        ),

        "visual": data.get(
            "visual",
            {}
        ),

        "alat_standar": {
            "jumlah_bidur": data.get(
                "jumlah_bidur",
                0
            ),
            "jumlah_at_10kg": data.get(
                "jumlah_at_10kg",
                0
            ),
            "jumlah_at_5kg": data.get(
                "jumlah_at_5kg",
                0
            ),
            "jumlah_at_2kg": data.get(
                "jumlah_at_2kg",
                0
            ),
            "jumlah_at_1kg": data.get(
                "jumlah_at_1kg",
                0
            ),
            "tambahkan_alat_standar": data.get(
                "tambahkan_alat_standar",
                False
            ),
            "pilihan_alat_tambahan": data.get(
                "pilihan_alat_tambahan",
                ""
            ),
            "jumlah_alat_tambahan": data.get(
                "jumlah_alat_tambahan",
                0
            )
        }
    }

    # =========================================
    # 4. TANGGAL
    # =========================================
    tanggal = data.get("tanggal")

    if isinstance(
        tanggal,
        (datetime, date)
    ):
        tanggal = tanggal.strftime(
            "%Y-%m-%d"
        )
    tanggal_sertifikat = data.get(
        "tanggal_sertifikat"
    )
    
    if isinstance(
        tanggal_sertifikat,
        (datetime, date)
    ):
        tanggal_sertifikat = (
            tanggal_sertifikat.strftime(
                "%Y-%m-%d"
            )
        )
    berlaku_sampai = data.get(
        "berlaku_sampai"
    )

    if isinstance(
        berlaku_sampai,
        (datetime, date)
    ):
        berlaku_sampai = (
            berlaku_sampai.strftime(
                "%Y-%m-%d"
            )
        )

    # =========================================
    # 5. NOMOR SERTIFIKAT
    # =========================================
    nomor_sertifikat = str(
        data.get(
            "nomor_sertifikat",
            ""
        )
    ).strip()

    if not nomor_sertifikat:
        raise ValueError(
            "Nomor sertifikat belum diisi."
        )

    # =========================================
    # 6. PAYLOAD PENGUJIAN
    # =========================================
    payload = {
        "uttp_id": uttp_id,
        "tanggal_pengujian": tanggal,
        "tanggal_sertifikat": tanggal_sertifikat,
        "jenis_pengujian": data.get(
            "keterangan",
            ""
        ),
        "hasil": "SAH",
        "nomor_order": data.get(
            "nomor_order",
            ""
        ),
        "nomor_sertifikat": nomor_sertifikat,
        "penera_1": data.get(
            "nama_penera",
            ""
        ),
        "berlaku_sampai": berlaku_sampai,
        "data_pengujian": detail_pengujian
    }

    # =========================================
    # 7. EDIT ATAU INSERT BARU
    # =========================================
    edit_id = st.session_state.get(
        "edit_pengujian_id"
    )

    if edit_id:
        response = (
            supabase
            .table("pengujian")
            .update(
                payload
            )
            .eq(
                "id",
                edit_id
            )
            .execute()
        )

        st.session_state.pop(
            "edit_pengujian_id",
            None
        )

    else:
        response = (
            supabase
            .table("pengujian")
            .insert(
                payload
            )
            .execute()
        )

    return response.data
def slug_filename(text):
    text = str(text).replace("/", "_").replace("\\", "_").replace(" ", "_")
    return "".join(ch for ch in text if ch.isalnum() or ch in ["_", "-", "."])


def parse_tanggal_file(data):
    tanggal = data.get("tanggal") or data.get("tanggal_pengujian")

    if tanggal:
        if isinstance(tanggal, str):
            try:
                return datetime.strptime(tanggal, "%Y-%m-%d")
            except Exception:
                pass
        return tanggal

    tanggal_penera = data.get("tanggal_penera", "")

    if tanggal_penera:
        try:
            bulan_map = {
                "Januari": 1, "Februari": 2, "Maret": 3, "April": 4,
                "Mei": 5, "Juni": 6, "Juli": 7, "Agustus": 8,
                "September": 9, "Oktober": 10, "November": 11, "Desember": 12
            }

            parts = tanggal_penera.split()

            if len(parts) == 3:
                day = int(parts[0])
                month = bulan_map[parts[1]]
                year = int(parts[2])
                return datetime(year, month, day)

        except Exception:
            pass

    return datetime.now()


def format_nama_file_dokumen(data, jenis_dokumen="Sertifikat"):
    nama_perusahaan = (
        data.get("pemilik")
        or data.get("nama_perusahaan")
        or "PERUSAHAAN"
    )

    nama_penera = (
        data.get("nama_penera")
        or data.get("penera_1")
        or data.get("penera")
        or "PENERA"
    )

    tanggal = parse_tanggal_file(data)
    tanggal_file = f"{tanggal.day:02d} {bulan_singkat_id(tanggal)}"

    nama_file = f"{nama_perusahaan}_TJ_{jenis_dokumen}_{nama_penera}_{tanggal_file}"
    return slug_filename(nama_file)
    
def normalize_nip(value):
    if pd.isna(value):
        return ""

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return str(value).strip()

def tambah_satu_tahun(tanggal_obj):
    try:
        return tanggal_obj.replace(
            year=tanggal_obj.year + 1
        )
    except ValueError:
        return tanggal_obj.replace(
            year=tanggal_obj.year + 1,
            month=2,
            day=28
        )

def format_tanggal_indonesia_tj(value):
    if not value:
        return ""

    if isinstance(value, datetime):
        value = value.date()

    elif isinstance(value, str):
        try:
            value = datetime.strptime(
                value,
                "%Y-%m-%d"
            ).date()
        except ValueError:
            return value

    bulan = [
        "Januari", "Februari", "Maret",
        "April", "Mei", "Juni",
        "Juli", "Agustus", "September",
        "Oktober", "November", "Desember"
    ]

    return (
        f"{value.day} "
        f"{bulan[value.month - 1]} "
        f"{value.year}"
    )
def gunakan_data_lama_untuk_edit(
    alat,
    perusahaan,
    pengujian
):
    detail = (
        pengujian.get("data_pengujian")
        or {}
    )

    # =====================================================
    # TANDAI MODE EDIT
    # =====================================================
    st.session_state["edit_pengujian_id"] = (
        pengujian["id"]
    )

    nama_perusahaan = str(
        perusahaan.get(
            "nama_perusahaan"
        )
        or ""
    ).strip()

    alamat = str(
        perusahaan.get(
            "alamat"
        )
        or ""
    ).strip()

    nama_penera = str(
        pengujian.get(
            "penera_1"
        )
        or ""
    ).strip()

    # =====================================================
    # CARI DATA PENERA
    # =====================================================
    nip_penera = ""
    golongan_penera = ""

    df_penera = st.session_state.get(
        "data_penera"
    )

    if (
        df_penera is not None
        and not df_penera.empty
        and nama_penera
    ):
        row = df_penera[
            df_penera["Nama"]
            .astype(str)
            .str.strip()
            == nama_penera
        ]

        if not row.empty:
            data_penera = row.iloc[0]

            nip_penera = normalize_nip(
                data_penera.get(
                    "NIP",
                    ""
                )
            )

            golongan_penera = str(
                data_penera.get(
                    "Golongan",
                    ""
                )
            ).strip()

    # =====================================================
    # DATA LAMA → SAVED DATA
    # =====================================================
    st.session_state.saved_data = {
        "pemilik": nama_perusahaan,
        "alamat": alamat,

        "merek": alat.get(
            "merk"
        ) or "",

        "model": alat.get(
            "tipe"
        ) or "",

        "no_seri": alat.get(
            "nomor_seri"
        ) or "",

        "kapasitas_max": detail.get(
            "kapasitas_max",
            60000
        ),

        "kapasitas_min": detail.get(
            "kapasitas_min",
            200
        ),

        "daya_baca": detail.get(
            "daya_baca",
            10
        ),

        "interval_skala": detail.get(
            "interval_skala",
            10
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
            "Beban Substitusi Tunggal"
        ),

        "nama_penera": nama_penera,
        "nip_penera": nip_penera,
        "golongan_penera": golongan_penera,

        "hasil_pengujian": detail.get(
            "hasil_kebenaran",
            []
        ),

        "repetability": detail.get(
            "repetability",
            []
        ),

        "eksentrisitas": detail.get(
            "eksentrisitas",
            []
        ),

        "penyetelan_nol": detail.get(
            "penyetelan_nol",
            {}
        ),

        "visual": detail.get(
            "visual",
            {}
        ),

        "tanggal": pengujian.get(
            "tanggal_pengujian"
        ),
        
        "tanggal_penera": (
            format_tanggal_indonesia_tj(
                pengujian.get(
                    "tanggal_pengujian"
                )
            )
        ),
        
        "tanggal_sertifikat": (
            pengujian.get(
                "tanggal_sertifikat"
            )
            or pengujian.get(
                "tanggal_pengujian"
            )
        ),
        
        "tanggal_tanda_tangan": (
            format_tanggal_indonesia_tj(
                pengujian.get(
                    "tanggal_sertifikat"
                )
                or pengujian.get(
                    "tanggal_pengujian"
                )
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

        "nomor_sertifikat": pengujian.get(
            "nomor_sertifikat",
            ""
        ),

        "berlaku_sampai": pengujian.get(
            "berlaku_sampai"
        ),
    }

    # =====================================================
    # PERUSAHAAN
    # =====================================================
    st.session_state[
        "nama_perusahaan_tj"
    ] = nama_perusahaan

    st.session_state[
        "alamat_input_tj"
    ] = alamat

    st.session_state[
        "perusahaan_select"
    ] = nama_perusahaan

    st.session_state[
        "input_manual_perusahaan_tj"
    ] = False

    # =====================================================
    # KAPASITAS
    # =====================================================
    st.session_state[
        "kapasitas_max_input"
    ] = int(
        detail.get(
            "kapasitas_max",
            60000
        )
    )

    st.session_state[
        "daya_baca_input"
    ] = int(
        detail.get(
            "daya_baca",
            10
        )
    )

    st.session_state[
        "interval_skala_input"
    ] = int(
        detail.get(
            "interval_skala",
            10
        )
    )

    st.session_state[
        "kapasitas_min_input"
    ] = int(
        detail.get(
            "kapasitas_min",
            200
        )
    )

    st.session_state["kelas"] = (
        detail.get(
            "kelas",
            "III"
        )
    )

    st.session_state["keterangan"] = (
        pengujian.get(
            "jenis_pengujian",
            "Tera Ulang"
        )
    )
    # =====================================================
    # PULIHKAN HASIL PENGUJIAN KEBENARAN
    # =====================================================
    hasil_kebenaran = detail.get(
        "hasil_kebenaran",
        []
    ) or []
    
    e_edit = int(
        detail.get(
            "interval_skala",
            10
        )
    )
    
    for i, row in enumerate(
        hasil_kebenaran[:8]
    ):
        standar = int(
            row.get(
                "standar",
                0
            ) or 0
        )
    
        balas = int(
            row.get(
                "balas",
                0
            ) or 0
        )
    
        delta_l = float(
            row.get(
                "imbuh",
                e_edit / 2
            ) or 0
        )
    
        kesalahan = int(
            row.get(
                "kesalahan",
                0
            ) or 0
        )
    
        hasil = (
            "SAH"
            if row.get(
                "hasil",
                True
            )
            else "TIDAK SAH"
        )
    
        st.session_state[
            f"standar_{i}_{e_edit}"
        ] = standar
    
        st.session_state[
            f"balas_{i}"
        ] = balas
    
        st.session_state[
            f"delta_l_{i}_{e_edit}"
        ] = delta_l
    
        st.session_state[
            f"kesalahan_{i}_{e_edit}"
        ] = kesalahan
    
        st.session_state[
            f"hasil_{i}_{e_edit}"
        ] = hasil
    
    
    # =====================================================
    # PULIHKAN PEMERIKSAAN VISUAL
    # =====================================================
    visual_lama = detail.get(
        "visual",
        {}
    ) or {}
    
    for item, nilai in visual_lama.items():
        st.session_state[
            f"vis_{item}"
        ] = bool(nilai)

    # =====================================================
    # PULIHKAN REPETABILITY
    # =====================================================
    repet_lama = detail.get(
        "repetability",
        []
    ) or []
    
    if repet_lama:
        # Penunjukan baris pertama menjadi acuan
        st.session_state[
            "repet_I_1"
        ] = int(
            repet_lama[0].get(
                "penunjukan",
                0
            ) or 0
        )
    
        for i, row in enumerate(
            repet_lama[:3],
            start=1
        ):
            hasil_repet = (
                "SAH"
                if row.get(
                    "hasil",
                    True
                )
                else "TIDAK SAH"
            )
    
            st.session_state[
                f"repet_hasil_{i}"
            ] = hasil_repet
    
    # =====================================================
    # PULIHKAN EKSENTRISITAS
    # =====================================================
    eksen_lama = detail.get(
        "eksentrisitas",
        []
    ) or []
    
    if eksen_lama:
        # Penunjukan baris pertama menjadi acuan
        st.session_state[
            "eksen_I_1"
        ] = int(
            eksen_lama[0].get(
                "penunjukan",
                0
            ) or 0
        )
    
        for i, row in enumerate(
            eksen_lama[:3],
            start=1
        ):
            hasil_eksen = (
                "SAH"
                if row.get(
                    "hasil",
                    True
                )
                else "TIDAK SAH"
            )
    
            st.session_state[
                f"eksen_hasil_{i}"
            ] = hasil_eksen
    
    # =====================================================
    # PULIHKAN PENYETELAN NOL
    # =====================================================
    nol_lama = detail.get(
        "penyetelan_nol",
        {}
    ) or {}
    
    if nol_lama:
        e_edit = int(
            detail.get(
                "interval_skala",
                10
            )
        )
    
        st.session_state[
            f"nol_setel_{e_edit}"
        ] = int(
            nol_lama.get(
                "setel_nol",
                0
            ) or 0
        )
    
        st.session_state[
            f"nol_muatan_{e_edit}"
        ] = int(
            nol_lama.get(
                "muatan_10e",
                10 * e_edit
            ) or 0
        )
    
        st.session_state[
            f"nol_awal_{e_edit}"
        ] = int(
            nol_lama.get(
                "awal",
                10 * e_edit
            ) or 0
        )
    
        st.session_state[
            f"nol_plus025_{e_edit}"
        ] = int(
            nol_lama.get(
                "plus025e",
                10 * e_edit
            ) or 0
        )
    
        st.session_state[
            f"nol_plus05_{e_edit}"
        ] = int(
            nol_lama.get(
                "plus05e",
                11 * e_edit
            ) or 0
        )
    # =====================================================
    # PENERA
    # =====================================================
    st.session_state[
        "penera_select"
    ] = nama_penera

    st.session_state[
        "nama_penera"
    ] = nama_penera

    st.session_state[
        "nip_penera"
    ] = nip_penera

    st.session_state[
        "golongan_penera"
    ] = golongan_penera

    # =====================================================
    # TANGGAL
    # =====================================================
    tanggal_lama = pengujian.get(
        "tanggal_pengujian"
    )

    if isinstance(
        tanggal_lama,
        datetime
    ):
        tanggal_lama = (
            tanggal_lama.date()
        )

    elif isinstance(
        tanggal_lama,
        str
    ):
        try:
            tanggal_lama = (
                datetime.strptime(
                    tanggal_lama,
                    "%Y-%m-%d"
                ).date()
            )

        except ValueError:
            tanggal_lama = date.today()

    elif not isinstance(
        tanggal_lama,
        date
    ):
        tanggal_lama = date.today()

    st.session_state[
        "tanggal_pengujian_tj"
    ] = tanggal_lama
    tanggal_sertifikat_lama = (
        pengujian.get(
            "tanggal_sertifikat"
        )
        or pengujian.get(
            "tanggal_pengujian"
        )
    )
    
    if isinstance(
        tanggal_sertifikat_lama,
        datetime
    ):
        tanggal_sertifikat_lama = (
            tanggal_sertifikat_lama.date()
        )
    
    elif isinstance(
        tanggal_sertifikat_lama,
        str
    ):
        try:
            tanggal_sertifikat_lama = (
                datetime.strptime(
                    tanggal_sertifikat_lama,
                    "%Y-%m-%d"
                ).date()
            )
        except ValueError:
            tanggal_sertifikat_lama = (
                tanggal_lama
            )
    
    elif not isinstance(
        tanggal_sertifikat_lama,
        date
    ):
        tanggal_sertifikat_lama = (
            tanggal_lama
        )
    
    st.session_state[
        "tanggal_sertifikat_tj"
    ] = tanggal_sertifikat_lama
    # =====================================================
    # NOMOR DOKUMEN
    # =====================================================
    st.session_state[
        "nomor_sertifikat_tj"
    ] = str(
        pengujian.get(
            "nomor_sertifikat"
        )
        or ""
    )

    st.session_state[
        "nomor_order_tj"
    ] = str(
        pengujian.get(
            "nomor_order"
        )
        or ""
    )

    st.session_state.generated_files = {}

    # =====================================================
    # PINDAH KE INPUT
    # =====================================================
    st.session_state[
        "next_mode_tj"
    ] = "📝 Input Data Pengujian"       

def gunakan_data_lama_untuk_pengujian_baru(
    alat,
    perusahaan,
    pengujian
):
    detail = (
        pengujian.get("data_pengujian")
        or {}
    )

    # =====================================================
    # PASTIKAN BUKAN MODE EDIT
    # =====================================================
    st.session_state.pop(
        "edit_pengujian_id",
        None
    )

    nama_perusahaan = str(
        perusahaan.get(
            "nama_perusahaan"
        )
        or ""
    ).strip()

    alamat = str(
        perusahaan.get(
            "alamat"
        )
        or ""
    ).strip()

    nama_penera = str(
        pengujian.get(
            "penera_1"
        )
        or ""
    ).strip()

    # =====================================================
    # DATA LAMA → IDENTITAS & SPESIFIKASI SAJA
    # =====================================================
    st.session_state.saved_data = {
        "pemilik": nama_perusahaan,
        "alamat": alamat,

        "merek": alat.get(
            "merk"
        ) or "",

        "model": alat.get(
            "tipe"
        ) or "",

        "no_seri": alat.get(
            "nomor_seri"
        ) or "",

        "kapasitas_max": detail.get(
            "kapasitas_max",
            60000
        ),

        "kapasitas_min": detail.get(
            "kapasitas_min",
            200
        ),

        "daya_baca": detail.get(
            "daya_baca",
            10
        ),

        "interval_skala": detail.get(
            "interval_skala",
            10
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
            "Beban Substitusi Tunggal"
        ),

        "nama_penera": nama_penera,

        # Pengujian baru
        "hasil_pengujian": [],
        "repetability": [],
        "eksentrisitas": [],
        "penyetelan_nol": {},
        "visual": {},

        "keterangan": "Tera Ulang",

        # Nomor dokumen harus baru
        "nomor_order": "",
        "nomor_sertifikat": "",
    }

    # =====================================================
    # SINKRONKAN FORM
    # =====================================================
    st.session_state[
        "nama_perusahaan_tj"
    ] = nama_perusahaan

    st.session_state[
        "alamat_input_tj"
    ] = alamat

    st.session_state[
        "perusahaan_select"
    ] = nama_perusahaan

    st.session_state[
        "input_manual_perusahaan_tj"
    ] = False

    st.session_state[
        "kapasitas_max_input"
    ] = int(
        detail.get(
            "kapasitas_max",
            60000
        )
    )

    st.session_state[
        "daya_baca_input"
    ] = int(
        detail.get(
            "daya_baca",
            10
        )
    )

    st.session_state[
        "interval_skala_input"
    ] = int(
        detail.get(
            "interval_skala",
            10
        )
    )

    st.session_state[
        "kapasitas_min_input"
    ] = int(
        detail.get(
            "kapasitas_min",
            200
        )
    )

    st.session_state[
        "kelas"
    ] = detail.get(
        "kelas",
        "III"
    )

    st.session_state[
        "keterangan"
    ] = "Tera Ulang"

    # =====================================================
    # PENERA
    # =====================================================
    st.session_state[
        "penera_select"
    ] = nama_penera

    st.session_state[
        "nama_penera"
    ] = nama_penera

    # =====================================================
    # TANGGAL BARU
    # =====================================================
    st.session_state[
        "tanggal_pengujian_tj"
    ] = date.today()

    st.session_state[
        "tanggal_sertifikat_tj"
    ] = date.today()

    # =====================================================
    # NOMOR DOKUMEN LAMA JANGAN IKUT
    # =====================================================
    st.session_state.pop(
        "nomor_sertifikat_tj",
        None
    )

    st.session_state.pop(
        "nomor_order_tj",
        None
    )

    # =====================================================
    # HAPUS HASIL PENGUJIAN LAMA DARI WIDGET
    # =====================================================
    prefixes_to_remove = [
        "standar_",
        "balas_",
        "delta_l_",
        "kesalahan_",
        "penunjukan_",
        "hasil_",
        "repet_",
        "eksen_",
        "nol_",
        "vis_",
    ]

    for key in list(
        st.session_state.keys()
    ):
        if any(
            key.startswith(prefix)
            for prefix in prefixes_to_remove
        ):
            st.session_state.pop(
                key,
                None
            )

    st.session_state.generated_files = {}

    # =====================================================
    # PINDAH KE INPUT
    # =====================================================
    st.session_state[
        "next_mode_tj"
    ] = "📝 Input Data Pengujian"
def run():
    st.title("Pengujian Timbangan Jembatan")

    col_nav1, col_nav2 = st.columns([1, 1])

    with col_nav1:
        if st.button("← Kembali ke Home", use_container_width=True):
            st.session_state.halaman = "home"
            st.rerun()

    with col_nav2:
        if st.button("📋 Ke Pengujian UTTP", use_container_width=True):
            st.session_state.halaman_uttp = "home_uttp"
            st.rerun()
            
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
    @st.cache_data(ttl=60)
    def load_data_perusahaan():
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
                df[col] = (
                    df[col]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                )
    
            df = df[
                df["Nama Perusahaan"] != ""
            ].copy()
    
            return (
                df
                .sort_values("Nama Perusahaan")
                .reset_index(drop=True)
            )
    
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
    
    if 'data_perusahaan' not in st.session_state:
        st.session_state.data_perusahaan = load_data_perusahaan()
    def update_perusahaan_terpilih_tj():
        selected = str(
            st.session_state.get(
                "perusahaan_select",
                ""
            )
        ).strip()
    
        df_perusahaan = st.session_state.get(
            "data_perusahaan"
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
    
        st.session_state[
            "nama_perusahaan_tj"
        ] = selected
    
        st.session_state[
            "alamat_input_tj"
        ] = str(
            alamat_perusahaan
        ).strip()
    
        st.session_state[
            "input_manual_perusahaan_tj"
        ] = False
    @st.cache_data(ttl=60)
    def load_data_penera():
        try:
            supabase = get_supabase()
    
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
    
            df["Nama"] = (
                df["Nama"]
                .fillna("")
                .astype(str)
                .str.strip()
            )
    
            df["NIP"] = (
                df["NIP"]
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
    
            df = df[
                df["Nama"] != ""
            ].copy()
    
            return (
                df
                .sort_values("Nama")
                .reset_index(drop=True)
            )
    
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
    
    if 'data_penera' not in st.session_state:
        st.session_state.data_penera = load_data_penera()
    def copy_standar():
        """Salin nilai standar baris ke-2 (indeks 1) ke baris 4, 6, 8 (indeks 3,5,7)."""
        e = st.session_state.get('interval_skala_input', 20)
        key_src = f"standar_1_{e}"
        if key_src in st.session_state:
            val = st.session_state[key_src]
            st.session_state[f"standar_3_{e}"] = val
            st.session_state[f"standar_5_{e}"] = val
            st.session_state[f"standar_7_{e}"] = val
    
    def sync_balas(prev_key, next_key):
        """Salin nilai dari prev_key ke next_key di session state."""
        if prev_key in st.session_state:
            st.session_state[next_key] = st.session_state[prev_key]
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
    def reset_form_timbangan_jembatan():
        # Key utama form
        keys_to_remove = [
            "saved_data",
            "test_results",
            "generated_files",
             "edit_pengujian_id",
            "merek_tj",
            "model_tj",
            "no_seri_tj",
            "nama_perusahaan_tj",
            "alamat_input_tj",
            "input_manual_perusahaan_tj",
            "perusahaan_select",

            "kapasitas_max_input",
            "daya_baca_input",
            "interval_skala_input",
            "kapasitas_min_input",
            "prev_interval_skala_tj",

            "kelas",
            "keterangan",

            "tanggal_pengujian_tj",
            "tanggal_sertifikat_tj",

            "penera_select",
            "nama_penera",
            "nip_penera",
            "golongan_penera",

            "jumlah_bidur_tj",
            "jumlah_at_10kg_tj",
            "jumlah_at_5kg_tj",
            "jumlah_at_2kg_tj",
            "jumlah_at_1kg_tj",

            "tambahkan_alat_standar_tj",
            "pilihan_alat_tambahan_tj",
            "jumlah_alat_tambahan_tj",

            "prev_kapasitas_max",
            "prev_kapasitas_max_eks",
            "repet_I_1",
            "eksen_I_1",
        ]

        for key in keys_to_remove:
            st.session_state.pop(
                key,
                None
            )

        # Hapus key dinamis tabel pengujian
        prefixes_to_remove = [
            "standar_",
            "balas_",
            "delta_l_",
            "kesalahan_",
            "penunjukan_",
            "hasil_",
            "repet_",
            "eksen_",
            "nol_",
            "vis_",
        ]

        for key in list(
            st.session_state.keys()
        ):
            if any(
                key.startswith(prefix)
                for prefix in prefixes_to_remove
            ):
                st.session_state.pop(
                    key,
                    None
                )

        st.session_state.saved_data = {}
        st.session_state.test_results = []
        st.session_state.generated_files = {}
    
    # ===== INISIALISASI SESSION STATE =====
    if 'saved_data' not in st.session_state:
        st.session_state.saved_data = {}
    
    if 'test_results' not in st.session_state:
        st.session_state.test_results = []
    
    # Nilai default untuk input utama (diambil dari saved_data jika ada)
    if 'kapasitas_max_input' not in st.session_state:
        st.session_state.kapasitas_max_input = st.session_state.saved_data.get('kapasitas_max', 60000)
    
    if 'daya_baca_input' not in st.session_state:
        st.session_state.daya_baca_input = st.session_state.saved_data.get('daya_baca', 10)
    
    if 'interval_skala_input' not in st.session_state:
        st.session_state.interval_skala_input = st.session_state.daya_baca_input
    
    if 'kelas' not in st.session_state:
        st.session_state.kelas = st.session_state.saved_data.get('kelas', 'III')
    
    if 'keterangan' not in st.session_state:
        st.session_state.keterangan = st.session_state.saved_data.get('keterangan', 'Tera')
        
    if 'generated_files' not in st.session_state:
        st.session_state.generated_files = {}
        
    # CSS styling
    st.markdown("""
        <style>
        .main {
            padding-top: 2rem;
        }
        </style>
        """, unsafe_allow_html=True)
    
    # Title
    st.title("⚖️ Aplikasi Automasi Sertifikat Tera Timbangan")
    st.markdown("---")
    
    # =========================================================
    # PINDAH MODE DARI AKSI RIWAYAT
    # Harus dilakukan sebelum widget radio dibuat
    # =========================================================
    if "next_mode_tj" in st.session_state:
        st.session_state[
            "mode_timbangan_jembatan"
        ] = st.session_state.pop(
            "next_mode_tj"
        )
    
    # Sidebar - Navigation
    with st.sidebar:
        st.header("📋 Menu Navigasi")
        mode = st.radio(
            "Pilih Mode:",
            [
                "📝 Input Data Pengujian",
                "📄 Generate Dokumen",
                "📚 Riwayat Timbangan Jembatan"
            ],
            key="mode_timbangan_jembatan",
            help="Pilih mode yang ingin Anda gunakan",
        )
    
    if mode == "📝 Input Data Pengujian":
        st.header("Masukkan Data Pengujian")
        # =====================================================
        # MODE EDIT PENGUJIAN
        # =====================================================
        edit_id = st.session_state.get(
            "edit_pengujian_id"
        )
        
        if edit_id:
            st.warning(
                f"✏️ Mode Edit Pengujian Aktif — "
                f"ID Pengujian: {edit_id}"
            )
        
            if st.button(
                "❌ Batal Edit",
                use_container_width=True,
                key="btn_batal_edit_tj"
            ):
                reset_form_timbangan_jembatan()
                st.rerun()
        # Ambil nilai dari session state untuk digunakan di seluruh blok
        e = st.session_state.get('interval_skala_input', 20)
        cls = st.session_state.get('kelas', 'III')
        jns_uji = st.session_state.get('keterangan', 'Tera')
    
        # ======================== KOLOM 1-3 ========================
        col1, col2, col3 = st.columns(3)
    
        with col1:
            st.subheader("Identitas Pemilik")

            df_perusahaan = st.session_state.get(
                "data_perusahaan"
            )

            if "nama_perusahaan_tj" not in st.session_state:
                st.session_state.nama_perusahaan_tj = str(
                    st.session_state.saved_data.get(
                        "pemilik",
                        ""
                    )
                ).strip()

            if "alamat_input_tj" not in st.session_state:
                st.session_state.alamat_input_tj = str(
                    st.session_state.saved_data.get(
                        "alamat",
                        ""
                    )
                ).strip()

            if "input_manual_perusahaan_tj" not in st.session_state:
                st.session_state.input_manual_perusahaan_tj = False

            if (
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

                if "perusahaan_select" not in st.session_state:
                    nama_tersimpan = (
                        st.session_state.nama_perusahaan_tj
                    )

                    if nama_tersimpan in all_names:
                        st.session_state.perusahaan_select = (
                            nama_tersimpan
                        )
                    else:
                        st.session_state.perusahaan_select = ""

                        if nama_tersimpan:
                            st.session_state[
                                "input_manual_perusahaan_tj"
                            ] = True

                st.selectbox(
                    "Cari & Pilih Nama Perusahaan",
                    options=[""] + all_names,
                    placeholder="Ketik nama perusahaan...",
                    key="perusahaan_select",
                    on_change=update_perusahaan_terpilih_tj,
                )

                st.text_area(
                    "Alamat",
                    height=90,
                    key="alamat_input_tj",
                    help=(
                        "Alamat otomatis muncul setelah perusahaan "
                        "dipilih dan tetap dapat diedit."
                    ),
                )

                st.checkbox(
                    "Input manual nama perusahaan",
                    key="input_manual_perusahaan_tj",
                )

                if st.session_state.input_manual_perusahaan_tj:
                    st.text_input(
                        "Nama Pemilik / Perusahaan",
                        key="nama_perusahaan_tj",
                        placeholder=(
                            "Contoh: PT. MULTI WELINDO"
                        ),
                    )

            else:
                st.info(
                    "📂 File data perusahaan tidak ditemukan. "
                    "Silakan input manual."
                )

                st.text_input(
                    "Nama Pemilik / Perusahaan",
                    key="nama_perusahaan_tj",
                )

                st.text_area(
                    "Alamat",
                    height=90,
                    key="alamat_input_tj",
                )

            pemilik = str(
                st.session_state.get(
                    "nama_perusahaan_tj",
                    ""
                )
            ).strip()

            alamat = str(
                st.session_state.get(
                    "alamat_input_tj",
                    ""
                )
            ).strip()
    
        with col2:
            st.subheader("Spesifikasi Alat")
            merek = st.text_input("Merek/Buatan",
                                  value=st.session_state.saved_data.get('merek', ''),
                                  placeholder="")
            model = st.text_input("Model/Tipe",
                                  value=st.session_state.saved_data.get('model', ''),
                                  placeholder="")
            no_seri = st.text_input("No. Seri",
                                    value=st.session_state.saved_data.get('no_seri', ''),
                                    placeholder="")
    
        with col3:
            st.subheader("Kapasitas & Skala")
    
            # Kapasitas Maksimum
            st.number_input(
                "Kapasitas Maksimum (kg)",
                value=st.session_state.kapasitas_max_input,
                min_value=100,
                step=100,
                key="kapasitas_max_input"
            )
    
            # Daya Baca
            st.number_input(
                "Daya Baca (kg)",
                value=st.session_state.daya_baca_input,
                min_value=1,
                step=1,
                key="daya_baca_input"
            )
    
            # Sinkronkan Interval Skala dengan Daya Baca
            st.session_state.interval_skala_input = st.session_state.daya_baca_input
    
            # Interval Skala Verifikasi (disabled)
            st.number_input(
                "Interval Skala Verifikasi (kg)",
                value=st.session_state.interval_skala_input,
                min_value=1,
                step=1,
                disabled=True,
                key="interval_skala_input",
                help="Interval Skala Verifikasi (e) otomatis mengikuti Daya Baca (d)."
            )
    
            # Kapasitas Minimum = 20 × interval skala
            current_e = st.session_state.interval_skala_input

            if "prev_interval_skala_tj" not in st.session_state:
                st.session_state.prev_interval_skala_tj = current_e

            if "kapasitas_min_input" not in st.session_state:
                st.session_state.kapasitas_min_input = (
                    20 * current_e
                )

            if (
                current_e
                != st.session_state.prev_interval_skala_tj
            ):
                st.session_state.kapasitas_min_input = (
                    20 * current_e
                )

                st.session_state.prev_interval_skala_tj = (
                    current_e
                )

            st.number_input(
                "Kapasitas Minimum (kg)",
                min_value=1,
                step=1,
                disabled=True,
                key="kapasitas_min_input",
                help=(
                    "Kapasitas minimum otomatis sama dengan "
                    "20 × interval skala verifikasi."
                ),
            )
        st.markdown("---")
    
        # ======================== KELAS & JENIS PENGUJIAN ========================
        col_extra1, col_extra2, col_extra3 = st.columns(3)
        with col_extra1:
            st.text_input(
                "Kelas Timbangan",
                value="III",
                disabled=True
            )
            st.session_state.kelas = "III"
    
        with col_extra2:
            default_keterangan = st.session_state.saved_data.get("keterangan", "Tera Ulang")
    
            keterangan = st.selectbox(
                "Jenis Pengujian",
                ["Tera", "Tera Ulang"],
                index=0 if default_keterangan == "Tera" else 1
            )
    
            st.session_state.keterangan = keterangan
    
        with col_extra3:
            # kosong atau bisa untuk informasi tambahan
            st.write("")
    
        st.markdown("---")
    
        # ======================== DATA PENGUJIAN LAINNYA ========================
        col4, col5, col6 = st.columns(3)
    
        with col4:
            st.subheader("Data Pengujian")
            
            tanggal = st.date_input(
                "Tanggal Pengujian",
                value=parse_date_value(
                    st.session_state.saved_data.get(
                        "tanggal",
                        date.today()
                    )
                ),
                key="tanggal_pengujian_tj",
            )
            
            # Lokasi Pengujian selalu "Perusahaan" (tidak bisa diubah)
            lokasi = st.text_input(
                "Lokasi Pengujian",
                value="Perusahaan",
                disabled=True,
                help="Lokasi pengujian tetap Perusahaan sesuai standar."
            )
            tanggal_tanda_tangan = st.date_input(
                "Tanggal Tanda Tangan",
                value=parse_date_value(
                    st.session_state.saved_data.get(
                        "tanggal_sertifikat",
                        date.today()
                    )
                ),
                key="tanggal_sertifikat_tj",
                help=(
                    "Tanggal ini digunakan pada bagian tanda tangan "
                    "sertifikat."
                ),
            )
    
        with col5:
            st.subheader("Data Penera")
            
            df_penera = st.session_state.get('data_penera')
            
            if df_penera is not None and not df_penera.empty:
                # Pilihan nama dari dropdown
                selected_nama = st.selectbox(
                    "Pilih Nama Penera",
                    options=df_penera['Nama'].tolist(),
                    index=None,
                    placeholder="Ketik atau pilih nama...",
                    key="penera_select"
                )
                
                if selected_nama:
                    row = df_penera[df_penera['Nama'] == selected_nama].iloc[0]
                    # Simpan ke session state
                    st.session_state.nama_penera = selected_nama
                    st.session_state.nip_penera = normalize_nip(
                        row.get("NIP", "")
                    )

                    st.session_state.golongan_penera = str(
                        row.get("Golongan", "")
                    ).strip()
                    
                    # Tampilkan info
                    st.caption(f"**NIP:** {row['NIP']}")
                    st.caption(f"**Golongan:** {row.get('Golongan', '')}")
                else:
                    # Jika belum memilih, tetap gunakan nilai session state (jika ada)
                    st.session_state.nama_penera = st.session_state.get('nama_penera', '')
                    st.session_state.nip_penera = st.session_state.get('nip_penera', '')
                    
                    # Opsi input manual
                    if st.checkbox("Input manual"):
                        manual_nama = st.text_input(
                            "Nama Penera (manual)",
                            value=st.session_state.saved_data.get('nama_penera', '')
                        )
                        manual_nip = st.text_input(
                            "NIP Penera (manual)",
                            value=st.session_state.saved_data.get('nip_penera', '')
                        )
                        st.session_state.nama_penera = manual_nama
                        st.session_state.nip_penera = manual_nip
            else:
                # Jika file tidak ada, input manual
                st.info("📂 File data penera tidak ditemukan. Silakan input manual.")
                manual_nama = st.text_input(
                    "Nama Penera",
                    value=st.session_state.saved_data.get('nama_penera', '')
                )
                manual_nip = st.text_input(
                    "NIP Penera",
                    value=st.session_state.saved_data.get('nip_penera', '')
                )
                st.session_state.nama_penera = manual_nama
                st.session_state.nip_penera = manual_nip
            
            # Ambil nilai dari session state untuk digunakan di submit
            nama_penera = st.session_state.get('nama_penera', '')
            nip_penera = st.session_state.get('nip_penera', '')
    
        with col6:
            st.subheader("Informasi Tambahan")
            
            # Suhu ruangan selalu "Ambient" (tidak bisa diubah)
            suhu = st.text_input(
                "Suhu Ruangan",
                value="Ambient",
                disabled=True,
                help="Nilai tetap Ambient sesuai standar pengujian."
            )
            
            # Kelembaban selalu "Ambient" (tidak bisa diubah)
            kelembaban = st.text_input(
                "Kelembaban",
                value="Ambient",
                disabled=True,
                help="Nilai tetap Ambient sesuai standar pengujian."
            )
            
            # Metode pengujian tetap "Beban Substitusi Tunggal"
            metode = st.text_input(
                "Metode Pengujian",
                value="Beban Substitusi Tunggal",
                disabled=True,
            )
    
        st.markdown("---")
        st.subheader("Hasil Pengujian Kebenaran")
    
        # ======================== TABEL PENGUJIAN KEBENARAN ========================
        # Ambil nilai dari session state
        e = st.session_state.get('interval_skala_input', 20)
        cls = st.session_state.get('kelas', 'III')
        jns_uji = st.session_state.get('keterangan', 'Tera')
    
        # ======================== TABEL PENGUJIAN KEBENARAN ========================
        num_results = 8
        test_results = []
    
        st.write("**Masukkan Hasil Pengujian**")
    
        # Header kolom
        cols_header = st.columns([0.5, 1.6, 1.6, 1.2, 1.4, 1.6, 1.0, 1.0])
        for col, label in zip(cols_header, [
            "**No**", "**Standar (S)**", "**Balas (B)**",
            "**ΔL**", "**Kesalahan**", "**Penunjukan (I)**", "**BKD**", "**Hasil**"
        ]):
            col.write(label)
    
        for i in range(num_results):
            cols = st.columns([0.5, 1.6, 1.6, 1.2, 1.4, 1.6, 1.0, 1.0])
    
            with cols[0]:
                st.write(f"{i+1}")
    
            if i == 0:
                default_s = 20 * e
                default_b = 0
                default_hasil = "SAH"
            else:
                default_s = 0
                default_b = 0
                default_hasil = "SAH"
    
            default_dl = e / 2.0
            default_kes = 0
    
            # --- Standar ---
            with cols[1]:
                if i == 1:
                    standar_val = st.number_input(
                        f"Standar {i+1}",
                        value=st.session_state.get(f"standar_{i}_{e}", default_s),
                        step=1,
                        format="%d",
                        key=f"standar_{i}_{e}",
                        on_change=copy_standar,
                        label_visibility="collapsed"
                    )
                else:
                    if i in [2, 4, 6]:
                        standar_val = 0
                    elif i in [3, 5, 7]:
                        standar_val = st.session_state.get(f"standar_1_{e}", default_s)
                    else:
                        standar_val = default_s
    
                    st.number_input(
                        f"Standar {i+1}",
                        value=standar_val,
                        step=1,
                        format="%d",
                        key=f"standar_{i}_{e}",
                        disabled=True,
                        label_visibility="collapsed"
                    )
    
            # --- Balas ---
            with cols[2]:
                if i in [2, 4, 6]:
                    balas_val = st.number_input(
                        f"Balas {i+1}",
                        value=st.session_state.get(f"balas_{i}", 0),
                        step=1,
                        format="%d",
                        key=f"balas_{i}",
                        on_change=sync_balas,
                        args=(f"balas_{i}", f"balas_{i+1}"),
                        label_visibility="collapsed"
                    )
                elif i in [3, 5, 7]:
                    prev_idx = i - 1
                    balas_val = st.session_state.get(f"balas_{prev_idx}", 0)
    
                    st.number_input(
                        f"Balas {i+1}",
                        value=balas_val,
                        step=1,
                        format="%d",
                        key=f"balas_{i}",
                        disabled=True,
                        label_visibility="collapsed"
                    )
                else:
                    balas_val = 0
    
                    st.number_input(
                        f"Balas {i+1}",
                        value=0,
                        step=1,
                        format="%d",
                        key=f"balas_{i}",
                        disabled=True,
                        label_visibility="collapsed"
                    )
    
            # --- ΔL ---
            with cols[3]:
                delta_l_val = st.number_input(
                    f"ΔL {i+1}",
                    value=default_dl,
                    step=0.1,
                    format="%g",
                    key=f"delta_l_{i}_{e}",
                    disabled=True,
                    label_visibility="collapsed"
                )
    
            # --- Kesalahan ---
            with cols[4]:
                kesalahan_val = st.number_input(
                    f"Kesalahan {i+1}",
                    value=default_kes,
                    step=1,
                    format="%d",
                    disabled=True,
                    key=f"kesalahan_{i}_{e}",
                    label_visibility="collapsed"
                )
    
            # --- Penunjukan (I) ---
            with cols[5]:
                penunjukan_default = standar_val + balas_val
                penunjukan_val = st.number_input(
                    f"Penunjukan {i+1}",
                    value=penunjukan_default,
                    step=1,
                    format="%d",
                    disabled=True,
                    key=f"penunjukan_{i}_{e}_{penunjukan_default}",
                    label_visibility="collapsed"
                )
    
            # --- BKD ---
            with cols[6]:
                muatan = standar_val + balas_val
                koef, bkd_kg = hitung_bkd(muatan, e, cls, jns_uji)
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
    
            # --- Hasil ---
            with cols[7]:
                hasil_val = st.selectbox(
                    f"Hasil {i+1}",
                    ["SAH", "TIDAK SAH"],
                    index=0 if default_hasil == "SAH" else 1,
                    key=f"hasil_{i}_{e}",
                    disabled=True,
                    label_visibility="collapsed"
                )
    
            muatan_sb = standar_val + balas_val
            p_aktual = penunjukan_val + 0.5 * e - delta_l_val
    
            test_results.append({
                'standar': standar_val,
                'balas': balas_val,
                'muatan_sb': muatan_sb,
                'timbangan': penunjukan_val,
                'imbuh': delta_l_val,
                'p_aktual': p_aktual,
                'kesalahan': kesalahan_val,
                'bkd_koef': koef,
                'bkd_kg': bkd_kg,
                'bkd_text': bkd_text,
                'hasil': hasil_val == "SAH"
            })
    
        st.markdown("---")
    
        # ======================== PEMERIKSAAN VISUAL ========================
        st.markdown("---")
        st.subheader("Pemeriksaan Visual")
        visual_items = ["Tanda Tera", "Alat Penunjuk Kedataran", "Bersih dan Siap Uji", "Sesuai Persetujuan Tipe"]
        visual_results = {}
        cols_vis = st.columns(4)
        for idx, item in enumerate(visual_items):
            with cols_vis[idx % 4]:
                visual_results[item] = st.checkbox(item, value=True, key=f"vis_{item}")
        # ======================== REPETABILITY ========================
        st.markdown("---")
        st.subheader("Repetability (50% Maks)")
    
        kapasitas_max = st.session_state.kapasitas_max_input
        interval_skala = st.session_state.interval_skala_input
        kelas = st.session_state.get('kelas', 'III')
        keterangan = st.session_state.get('keterangan', 'Tera')
    
        half_max = int(kapasitas_max * 0.5)
        deltaL_default = interval_skala / 2.0
    
        # === Perbaikan: update nilai default jika kapasitas berubah ===
        if 'prev_kapasitas_max' not in st.session_state:
            st.session_state.prev_kapasitas_max = kapasitas_max
    
        if 'repet_I_1' not in st.session_state:
            st.session_state.repet_I_1 = half_max
        else:
            # Jika kapasitas berubah dan nilai saat ini masih sama dengan default lama, update
            if kapasitas_max != st.session_state.prev_kapasitas_max:
                half_max_old = int(st.session_state.prev_kapasitas_max * 0.5)
                if st.session_state.repet_I_1 == half_max_old:
                    st.session_state.repet_I_1 = half_max
                st.session_state.prev_kapasitas_max = kapasitas_max
    
        # Header
        col_header = st.columns([1.2, 0.8, 1.5, 0.9, 1.0])
        with col_header[0]:
            st.write("**Penunjukan (I)**")
        with col_header[1]:
            st.write("**ΔL**")
        with col_header[2]:
            st.write("**P (I+0.5e-ΔL)**")
        with col_header[3]:
            st.write("**BKD**")
        with col_header[4]:
            st.write("**Hasil**")
    
        repet_data = []
        I_baris1 = st.session_state.repet_I_1  # acuan baris 1, di-refresh tiap iterasi i==1
    
        for i in range(1, 4):
            cols_repet = st.columns([1.2, 0.8, 1.5, 0.9, 1.0])
    
            with cols_repet[0]:
                if i == 1:
                    I = st.number_input(
                        f"Penunjukan (I) {i}",
                        value=st.session_state.repet_I_1,
                        step=1,
                        format="%d",
                        key="repet_I_1",
                        label_visibility="collapsed"
                    )
                    I_baris1 = I  # tangkap nilai terbaru untuk dipakai baris 2 & 3
                else:
                    # key disisipi I_baris1 supaya widget selalu "fresh" mengikuti
                    # baris 1 tiap kali nilainya berubah (widget disabled dengan
                    # key statis tidak akan ter-update lewat parameter value saja)
                    I = st.number_input(
                        f"Penunjukan (I) {i}",
                        value=I_baris1,
                        step=1,
                        format="%d",
                        disabled=True,
                        key=f"repet_I_{i}_{I_baris1}",
                        label_visibility="collapsed"
                    )
            with cols_repet[1]:
                deltaL = st.number_input(
                    f"ΔL {i}",
                    value=deltaL_default,
                    step=0.1,
                    format="%g",
                    disabled=True,
                    key=f"repet_dL_{i}_{interval_skala}",
                    label_visibility="collapsed"
                )
            with cols_repet[2]:
                # key disisipi I supaya P ikut ter-update tiap kali I berubah
                P = st.number_input(
                    f"P (I+0.5e-ΔL) {i}",
                    value=I,
                    step=1,
                    format="%d",
                    disabled=True,
                    key=f"repet_P_{i}_{interval_skala}_{I}",
                    label_visibility="collapsed"
                )
            with cols_repet[3]:
                muatan = I
                koef, bkd_kg = hitung_bkd(muatan, interval_skala, kelas, keterangan)
                bkd_text = "±0.5e" if koef == 0.5 else \
                           "±1e" if koef == 1.0 else \
                           "±1.5e" if koef == 1.5 else \
                           "±2e" if koef == 2.0 else \
                           "±3e" if koef == 3.0 else f"±{koef:.1f}e"
                st.write(f"**{bkd_text}**")
            with cols_repet[4]:
                hasil = st.selectbox(
                    f"Hasil {i}",
                    ["SAH", "TIDAK SAH"],
                     index=0,
                    key=f"repet_hasil_{i}",
                    disabled=True,
                    label_visibility="collapsed"
                )
    
            repet_data.append({
                "penunjukan": I,
                "delta_l": deltaL,
                "p_value": P,
                "hasil": hasil == "SAH",
                "bkd_koef": koef,
                "bkd_kg": bkd_kg,
                "bkd_text": bkd_text
            })
    # ======================== EKSENTRISITAS ========================
        st.markdown("---")
        st.subheader("Eksentrisitas (1/3 Maks)")
    
        kapasitas_max = st.session_state.kapasitas_max_input
        interval_skala = st.session_state.interval_skala_input
        kelas = st.session_state.get('kelas', 'III')
        keterangan = st.session_state.get('keterangan', 'Tera')
    
        one_third = int(kapasitas_max / 3.0)
        deltaL_eks = interval_skala / 2.0
    
        # === Perbaikan: update nilai default jika kapasitas berubah ===
        if 'prev_kapasitas_max_eks' not in st.session_state:
            st.session_state.prev_kapasitas_max_eks = kapasitas_max
    
        if 'eksen_I_1' not in st.session_state:
            st.session_state.eksen_I_1 = one_third
        else:
            if kapasitas_max != st.session_state.prev_kapasitas_max_eks:
                one_third_old = int(st.session_state.prev_kapasitas_max_eks / 3.0)
                if st.session_state.eksen_I_1 == one_third_old:
                    st.session_state.eksen_I_1 = one_third
                st.session_state.prev_kapasitas_max_eks = kapasitas_max
    
        # Header
        col_header = st.columns([1.2, 0.8, 1.5, 0.9, 1.0])
        with col_header[0]:
            st.write("**Penunjukan (I)**")
        with col_header[1]:
            st.write("**ΔL**")
        with col_header[2]:
            st.write("**P (I+0.5e-ΔL)**")
        with col_header[3]:
            st.write("**BKD**")
        with col_header[4]:
            st.write("**Hasil**")
    
        eksen_data = []
        selisih_labels = ["3 & 1", "1 & 2", "2 & 3"]
        I_baris1 = st.session_state.eksen_I_1
    
        for i in range(1, 4):
            cols_eksen = st.columns([1.2, 0.8, 1.5, 0.9, 1.0])
    
            with cols_eksen[0]:
                if i == 1:
                    I = st.number_input(
                        f"Penunjukan (I) {i}",
                        value=st.session_state.eksen_I_1,
                        step=1,
                        format="%d",
                        key="eksen_I_1",
                        label_visibility="collapsed"
                    )
                    I_baris1 = I
                else:
                    I = st.number_input(
                        f"Penunjukan (I) {i}",
                        value=I_baris1,
                        step=1,
                        format="%d",
                        disabled=True,
                        key=f"eksen_I_{i}_{I_baris1}",
                        label_visibility="collapsed"
                    )
            with cols_eksen[1]:
                deltaL = st.number_input(
                    f"ΔL {i}",
                    value=deltaL_eks,
                    step=0.1,
                    format="%g",
                    disabled=True,
                    key=f"eksen_dL_{i}_{interval_skala}",
                    label_visibility="collapsed"
                )
            with cols_eksen[2]:
                P = st.number_input(
                    f"P (I+0.5e-ΔL) {i}",
                    value=I,
                    step=1,
                    format="%d",
                    disabled=True,
                    key=f"eksen_P_{i}_{interval_skala}_{I}",
                    label_visibility="collapsed"
                )
            with cols_eksen[3]:
                muatan = I
                koef, bkd_kg = hitung_bkd(muatan, interval_skala, kelas, keterangan)
                bkd_text = "±0.5e" if koef == 0.5 else \
                           "±1e" if koef == 1.0 else \
                           "±1.5e" if koef == 1.5 else \
                           "±2e" if koef == 2.0 else \
                           "±3e" if koef == 3.0 else f"±{koef:.1f}e"
                st.write(f"**{bkd_text}**")
            with cols_eksen[4]:
                hasil = st.selectbox(
                    f"Hasil {i}",
                    ["SAH", "TIDAK SAH"],
                     index=0,
                    key=f"eksen_hasil_{i}",
                    disabled=True,
                    label_visibility="collapsed"
                )
    
            eksen_data.append({
                "penunjukan": I,
                "delta_l": deltaL,
                "p_value": P,
                "selisih": selisih_labels[i-1],
                "hasil": hasil == "SAH",
                "bkd_koef": koef,
                "bkd_kg": bkd_kg,
                "bkd_text": bkd_text
            })
    
            # ======================== PENGUJIAN PENYETELAN NOL ========================
        st.markdown("---")
        st.subheader("Pengujian Penyetelan Nol")
    
        # Ambil interval_skala langsung dari session state (reaktif)
        e = st.session_state.get('interval_skala_input', 20)
    
        col_nol1, col_nol2, col_nol3, col_nol4, col_nol5 = st.columns(5)
        with col_nol1:
            setel_nol = st.number_input(
                "SETEL NOL",
                value=0,
                step=1,
                key=f"nol_setel_{e}",  # key dinamis
                disabled=True,
            )
        with col_nol2:
            muatan_10e = st.number_input(
                "MUATAN 10e (kg)",
                value=10 * e,
                step=1,
                key=f"nol_muatan_{e}",  # key dinamis
                disabled=True,
            )
        with col_nol3:
            awal = st.number_input(
                "AWAL",
                value=10 * e,
                step=1,
                key=f"nol_awal_{e}",  # key dinamis
                disabled=True,
            )
        with col_nol4:
            plus025e = st.number_input(
                "+0,25e",
                value=10 * e,
                step=1,
                key=f"nol_plus025_{e}",  # key dinamis
                disabled=True,
            )
        with col_nol5:
            plus05e = st.number_input(
                "+0,5e",
                value=10 * e + e,
                step=1,
                key=f"nol_plus05_{e}",  # key dinamis
                disabled=True,
            )
    
        nol_data = {
            "setel_nol": setel_nol,
            "muatan_10e": muatan_10e,
            "awal": awal,
            "plus025e": plus025e,
            "plus05e": plus05e
        }
            # ======================== PENGUJIAN PENYETEL TARA (TERA) ========================
        st.markdown("---")
        st.subheader("Pengujian Penyetel Tara (TERA)")
    
        # Hanya tampil jika jenis pengujian adalah "Tera"
        if st.session_state.get('keterangan', 'Tera') == "Tera":
            st.info("Tabel ini otomatis dihitung berdasarkan Kapasitas Maksimum dan Interval Skala.")
    
            kapasitas_max_tara = st.session_state.get('kapasitas_max_input', 60000)
            interval_skala_tara = st.session_state.get('interval_skala_input', 10)
    
            # Hitung nilai
            muatan_tara_val = int(0.2 * kapasitas_max_tara)
            muatan_10e_val = 10 * interval_skala_tara
            imbuh_025e_val = muatan_10e_val
            imbuh_05e_val = 11 * interval_skala_tara
    
            data_tara = {
                "KEGIATAN": ["SETEL NOL", "MUATAN TARA (20% MAKS)", "AKTIFKAN TARA", "+ muatan 10e", "+ imbuh 0,25e", "+ imbuh 0,5e"],
                "PENUNJUKKAN": [0, muatan_tara_val, 0, muatan_10e_val, imbuh_025e_val, imbuh_05e_val]
            }
    
            df_tara = pd.DataFrame(data_tara)
            st.dataframe(df_tara, use_container_width=True, hide_index=True)
        else:
            st.info("Pengujian Penyetel Tara hanya dilakukan pada Tera (bukan Tera Ulang).")
            
        # =========================================================
        # DATA PEMINJAMAN ALAT STANDAR
        # =========================================================
        st.markdown("---")
        st.subheader("⚖️ Peminjaman Alat Standar")
        st.caption(
            "Jenis alat standar sudah ditentukan. "
            "Silakan ubah jumlahnya apabila diperlukan."
        )

        col_at1, col_at2, col_at3, col_at4, col_at5 = st.columns(5)

        with col_at1:
            jumlah_bidur = st.number_input(
                "BIDUR",
                min_value=0,
                step=1,
                value=int(
                    st.session_state.saved_data.get(
                        "jumlah_bidur",
                        100
                    )
                ),
                key="jumlah_bidur_tj"
            )

        with col_at2:
            jumlah_at_10kg = st.number_input(
                "AT 10 kg",
                min_value=0,
                step=1,
                value=int(
                    st.session_state.saved_data.get(
                        "jumlah_at_10kg",
                        1
                    )
                ),
                key="jumlah_at_10kg_tj"
            )

        with col_at3:
            jumlah_at_5kg = st.number_input(
                "AT 5 kg",
                min_value=0,
                step=1,
                value=int(
                    st.session_state.saved_data.get(
                        "jumlah_at_5kg",
                        1
                    )
                ),
                key="jumlah_at_5kg_tj"
            )

        with col_at4:
            jumlah_at_2kg = st.number_input(
                "AT 2 kg",
                min_value=0,
                step=1,
                value=int(
                    st.session_state.saved_data.get(
                        "jumlah_at_2kg",
                        2
                    )
                ),
                key="jumlah_at_2kg_tj"
            )

        with col_at5:
            jumlah_at_1kg = st.number_input(
                "AT 1 kg",
                min_value=0,
                step=1,
                value=int(
                    st.session_state.saved_data.get(
                        "jumlah_at_1kg",
                        1
                    )
                ),
                key="jumlah_at_1kg_tj"
            )
        
        # =========================================================
        # ALAT STANDAR TAMBAHAN
        # =========================================================
        st.markdown("---")
        st.subheader("➕ Alat Standar Tambahan")

        tambahkan_alat_standar = st.checkbox(
            "Tambahkan alat standar",
            value=bool(
                st.session_state.saved_data.get(
                    "tambahkan_alat_standar",
                    False
                )
            ),
            key="tambahkan_alat_standar_tj"
        )

        # Nilai default supaya variabel tetap tersedia saat disimpan
        pilihan_alat_tambahan = ""
        jumlah_alat_tambahan = 1

        if tambahkan_alat_standar:
            col_tambah1, col_tambah2 = st.columns(2)

            with col_tambah1:
                pilihan_alat_tambahan = st.selectbox(
                    "Pilih Alat Standar Tambahan",
                    options=[
                        "AT M1",
                        "AT F2"
                    ],
                    index=0,
                    key="pilihan_alat_tambahan_tj"
                )

            with col_tambah2:
                jumlah_alat_tambahan = st.number_input(
                    "Jumlah (set)",
                    min_value=1,
                    value=int(
                        st.session_state.saved_data.get(
                            "jumlah_alat_tambahan",
                            1
                        )
                    ),
                    step=1,
                    key="jumlah_alat_tambahan_tj"
                )
        # ======================== TOMBOL SIMPAN ========================
        col_submit1, col_submit2 = st.columns(2)
        with col_submit1:
            submit_btn = st.button("💾 Simpan Data", use_container_width=True, type="primary")
        with col_submit2:
            st.button(
                "🔄 Reset Form",
                use_container_width=True,
                key="reset_form_tj",
                on_click=reset_form_timbangan_jembatan,
            )
        
        if submit_btn:
            # Ambil semua nilai dari session state (dengan default)
            kapasitas_max_final = st.session_state.get('kapasitas_max_input', 60000)
            daya_baca_final = st.session_state.get('daya_baca_input', 10)
            interval_skala_final = st.session_state.get('interval_skala_input', 10)
            kapasitas_min_final = st.session_state.get('kapasitas_min_input', 20 * interval_skala_final)
            kelas_final = st.session_state.get('kelas', 'III')
            keterangan_final = st.session_state.get('keterangan', 'Tera')
            berlaku_sampai = tambah_satu_tahun(tanggal)
            st.session_state.generated_files = {}
            # Ambil nilai dari input yang masih berupa variabel lokal
            # (pemilik, alamat, merek, model, no_seri, suhu, kelembaban, metode, lokasi, nama_penera, nip_penera, tanggal)
            # Pastikan variabel-variabel ini sudah didefinisikan di atas (masih dalam scope yang sama)
            # Jika ada yang belum, gunakan session state atau default.

            # =====================================================
            # PERTAHANKAN NOMOR DOKUMEN SAAT MODE EDIT
            # =====================================================
            sedang_edit = bool(
                st.session_state.get(
                    "edit_pengujian_id"
                )
            )
            
            nomor_sertifikat_lama = str(
                st.session_state.get(
                    "nomor_sertifikat_tj",
                    st.session_state.saved_data.get(
                        "nomor_sertifikat",
                        ""
                    )
                )
                or ""
            ).strip()
            
            nomor_order_lama = str(
                st.session_state.get(
                    "nomor_order_tj",
                    st.session_state.saved_data.get(
                        "nomor_order",
                        ""
                    )
                )
                or ""
            ).strip()
            st.session_state.saved_data = {
                'pemilik': pemilik,
                'alamat': alamat,
                'merek': merek,
                'model': model,
                'no_seri': no_seri,
                'kapasitas_max': kapasitas_max_final,
                'kapasitas_min': kapasitas_min_final,
                'daya_baca': daya_baca_final,
                'interval_skala': interval_skala_final,
                'kelas': kelas_final,
                'suhu': suhu,          # suhu sudah di-set "Ambient" (disabled)
                'kelembaban': kelembaban,  # kelembaban sudah di-set "Ambient"
                'metode': metode,      # metode sudah di-set "Beban Substitusi Tunggal"
                'lokasi': lokasi,      # lokasi sudah di-set "Perusahaan"
                'nama_penera': nama_penera,
                'nip_penera': nip_penera,
                'golongan_penera': st.session_state.get('golongan_penera', ''),
                'hasil_pengujian': test_results,
                'tanggal': tanggal,
                'tanggal_penera': format_tanggal_indonesia(tanggal.strftime('%Y-%m-%d')),
                'tanggal_sertifikat': tanggal_tanda_tangan,
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
                'berlaku_sampai': berlaku_sampai.strftime('%Y-%m-%d'),
                'repetability': repet_data,      # dari bagian repetability
                'eksentrisitas': eksen_data,     # dari bagian eksentrisitas
                'penyetelan_nol': nol_data,      # dari bagian penyetelan nol
                'visual': visual_results,        # dari bagian pemeriksaan visual
                "jumlah_bidur": int(jumlah_bidur),
                "jumlah_at_10kg": int(jumlah_at_10kg),
                "jumlah_at_5kg": int(jumlah_at_5kg),
                "jumlah_at_2kg": int(jumlah_at_2kg),
                "jumlah_at_1kg": int(jumlah_at_1kg),
                'tambahkan_alat_standar': bool(tambahkan_alat_standar),
                'pilihan_alat_tambahan': (
                    pilihan_alat_tambahan
                    if tambahkan_alat_standar
                    else ""
                ),

                'jumlah_alat_tambahan': (
                    int(jumlah_alat_tambahan)
                    if tambahkan_alat_standar
                    else 0
                ),
            }
            st.session_state.test_results = test_results
            st.success("✅ Data berhasil disimpan!")
            st.balloons()
    
    
    # ===== MODE 2: GENERATE DOKUMEN =====
    elif mode == "📄 Generate Dokumen":
        st.header("Generate Dokumen Cerapan & Sertifikat")
        
        if not st.session_state.saved_data:
            st.warning("⚠️ Silakan input data pengujian terlebih dahulu di menu 'Input Data Pengujian'")
        else:
            data = st.session_state.saved_data
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📋 Preview Data")
                preview_cols = st.columns(2)
                
                with preview_cols[0]:
                    st.write(f"**Pemilik:** {data.get('pemilik', '-')}")
                    st.write(f"**Merek:** {data.get('merek', '-')}")
                    st.write(f"**Model:** {data.get('model', '-')}")
                    st.write(f"**No. Seri:** {data.get('no_seri', '-')}")
                
                with preview_cols[1]:
                    st.write(f"**Penera:** {data.get('nama_penera', '-')}")
                    st.write(f"**Tanggal:** {data.get('tanggal_penera', '-')}")
                    st.write(f"**Kelas:** {data.get('kelas', '-')}")
                    st.write(f"**Hasil Pengujian:** {len(data.get('hasil_pengujian', []))} data")
            
            with col2:
                st.subheader("📊 Nomor Dokumen")

                # Ambil tanggal pengujian dari saved_data
                tanggal_data = data.get(
                    "tanggal",
                    date.today()
                )

                tanggal_data = parse_date_value(
                    tanggal_data,
                    date.today()
                )

                # Generate nomor berdasarkan tanggal pengujian
                default_sertifikat = generate_nomor_sertifikat(
                    tanggal_data
                )

                default_order = generate_nomor_order(
                    tanggal_data
                )

                # =====================================================
                # NOMOR DOKUMEN
                # Edit  -> pertahankan nomor lama
                # Baru  -> gunakan nomor default
                # =====================================================
                nomor_sertifikat_awal = (
                    data.get("nomor_sertifikat")
                    or default_sertifikat
                )
                
                nomor_order_awal = (
                    data.get("nomor_order")
                    or default_order
                )
                
                # Jika session state belum ada / kosong,
                # isi dari nomor lama atau nomor default.
                if not str(
                    st.session_state.get(
                        "nomor_sertifikat_tj",
                        ""
                    )
                ).strip():
                    st.session_state[
                        "nomor_sertifikat_tj"
                    ] = nomor_sertifikat_awal
                
                if not str(
                    st.session_state.get(
                        "nomor_order_tj",
                        ""
                    )
                ).strip():
                    st.session_state[
                        "nomor_order_tj"
                    ] = nomor_order_awal
                
                
                nomor_sertifikat = st.text_input(
                    "Nomor Sertifikat",
                    placeholder=(
                        "Format: "
                        "XXX.X.X.XX/XXXX/XXX-X/X/XXXX"
                    ),
                    key="nomor_sertifikat_tj",
                )
                
                nomor_order = st.text_input(
                    "Nomor Order",
                    placeholder="Format nomor order",
                    key="nomor_order_tj",
                )

                st.session_state.saved_data[
                    "nomor_sertifikat"
                ] = nomor_sertifikat

                st.session_state.saved_data[
                    "nomor_order"
                ] = nomor_order

                data = st.session_state.saved_data
            
            st.markdown("---")
            
            # =====================================================
            # GENERATE DOKUMEN
            # =====================================================
            st.markdown("---")
            st.subheader("📄 Generate Dokumen")

            if "generated_files" not in st.session_state:
                st.session_state.generated_files = {}

            # =====================================================
            # GENERATE CERAPAN + SERTIFIKAT SEKALIGUS
            # =====================================================
            if st.button(
                "📦 Generate Cerapan dan Sertifikat",
                type="primary",
                use_container_width=True,
                key="tj_generate_kedua_dokumen",
            ):
                try:
                    output_path = Path(
                        "./output/timbangan_jembatan"
                    )

                    output_path.mkdir(
                        parents=True,
                        exist_ok=True,
                    )

                    nama_file_cerapan = (
                        format_nama_file_dokumen(
                            data,
                            "Cerapan"
                        )
                    )

                    cerapan_file = (
                        output_path
                        / f"{nama_file_cerapan}.pdf"
                    )

                    generate_cerapan_pdf(
                        st.session_state.saved_data,
                        str(cerapan_file),
                    )

                    st.session_state.generated_files[
                        "cerapan"
                    ] = str(cerapan_file)

                    nama_file_sertifikat = (
                        format_nama_file_dokumen(
                            data,
                            "Sertifikat"
                        )
                    )

                    sertifikat_file = (
                        output_path
                        / f"{nama_file_sertifikat}.pdf"
                    )

                    generate_sertifikat_pdf(
                        st.session_state.saved_data,
                        str(sertifikat_file),
                        nomor_sertifikat,
                    )

                    st.session_state.generated_files[
                        "sertifikat"
                    ] = str(sertifikat_file)
                    # =====================================================
                    # SIMPAN PENGUJIAN KE SUPABASE
                    # =====================================================
                    try:
                        st.session_state.saved_data[
                            "nomor_sertifikat"
                        ] = nomor_sertifikat
                    
                        st.session_state.saved_data[
                            "nomor_order"
                        ] = nomor_order
                    
                        simpan_pengujian_tj_ke_supabase(
                            st.session_state.saved_data
                        )

                        load_data_perusahaan.clear()

                        st.session_state[
                            "data_perusahaan"
                        ] = load_data_perusahaan()
                        
                        st.success(
                            "✅ Cerapan dan sertifikat berhasil dibuat "
                            "serta data pengujian berhasil disimpan "
                            "ke database."
                        )
                        st.success(
                            "✅ Cerapan dan sertifikat berhasil dibuat "
                            "serta data pengujian berhasil disimpan "
                            "ke database."
                        )
                    
                    except Exception as db_error:
                        error_text = str(
                            db_error
                        )
                    
                        if (
                            "duplicate key value violates unique constraint"
                            in error_text
                            and
                            "pengujian_nomor_sertifikat_unique"
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
                    
                            st.exception(
                                db_error
                            )
                    st.success(
                        "✅ Cerapan dan sertifikat "
                        "berhasil dibuat."
                    )

                except Exception as exc:
                    st.error(
                        f"❌ Gagal membuat dokumen: {exc}"
                    )

                    import traceback
                    st.code(traceback.format_exc())


            st.markdown("### Dokumen Individual")

            col_doc1, col_doc2, col_doc3, col_doc4 = (
                st.columns(4)
            )
            with col_doc1:
                with st.container(border=True):
                    st.markdown("### 📝 Cerapan")

                    st.caption(
                        "Generate dan download cerapan "
                        "pengujian Timbangan Jembatan."
                    )

                    if st.button(
                        "Generate Cerapan",
                        type="primary",
                        use_container_width=True,
                        key="tj_generate_cerapan",
                    ):
                        try:
                            output_path = Path(
                                "./output/timbangan_jembatan"
                            )

                            output_path.mkdir(
                                parents=True,
                                exist_ok=True,
                            )

                            nama_file = (
                                format_nama_file_dokumen(
                                    data,
                                    "Cerapan"
                                )
                            )

                            filename = (
                                output_path
                                / f"{nama_file}.pdf"
                            )

                            generate_cerapan_pdf(
                                st.session_state.saved_data,
                                str(filename),
                            )

                            st.session_state.generated_files[
                                "cerapan"
                            ] = str(filename)

                            st.success(
                                "✅ Cerapan berhasil dibuat."
                            )

                        except Exception as exc:
                            st.error(
                                f"❌ Gagal membuat cerapan: {exc}"
                            )

                    cerapan_path = (
                        st.session_state.generated_files.get(
                            "cerapan"
                        )
                    )

                    if (
                        cerapan_path
                        and Path(cerapan_path).exists()
                    ):
                        with open(
                            cerapan_path,
                            "rb"
                        ) as file_pdf:
                            st.download_button(
                                "⬇️ Download Cerapan",
                                data=file_pdf.read(),
                                file_name=Path(
                                    cerapan_path
                                ).name,
                                mime="application/pdf",
                                use_container_width=True,
                                key="tj_download_cerapan",
                            )
                    else:
                        st.caption(
                            "Cerapan belum digenerate."
                        )
            with col_doc2:
                with st.container(border=True):
                    st.markdown("### 🎫 Sertifikat")

                    st.caption(
                        "Generate dan download sertifikat "
                        "Timbangan Jembatan."
                    )

                    if st.button(
                        "Generate Sertifikat",
                        type="primary",
                        use_container_width=True,
                        key="tj_generate_sertifikat",
                    ):
                        try:
                            output_path = Path(
                                "./output/timbangan_jembatan"
                            )

                            output_path.mkdir(
                                parents=True,
                                exist_ok=True,
                            )

                            nama_file = (
                                format_nama_file_dokumen(
                                    data,
                                    "Sertifikat"
                                )
                            )

                            filename = (
                                output_path
                                / f"{nama_file}.pdf"
                            )

                            generate_sertifikat_pdf(
                                st.session_state.saved_data,
                                str(filename),
                                nomor_sertifikat,
                            )

                            st.session_state.generated_files[
                                "sertifikat"
                            ] = str(filename)
                            
                            # Pastikan nomor dokumen masuk ke saved_data
                            st.session_state.saved_data[
                                "nomor_sertifikat"
                            ] = nomor_sertifikat
                            
                            st.session_state.saved_data[
                                "nomor_order"
                            ] = nomor_order
                            
                            # Simpan ke Supabase
                            try:
                                simpan_pengujian_tj_ke_supabase(
                                    st.session_state.saved_data
                                )
                            
                                # Refresh master perusahaan dari Supabase
                                load_data_perusahaan.clear()
                            
                                st.session_state[
                                    "data_perusahaan"
                                ] = load_data_perusahaan()
                            
                                st.success(
                                    "✅ Sertifikat berhasil dibuat dan "
                                    "data pengujian berhasil disimpan ke database."
                                )
                            
                            except Exception as db_error:
                                error_text = str(db_error)
                            
                                if (
                                    "duplicate key value violates unique constraint"
                                    in error_text
                                    and
                                    "pengujian_nomor_sertifikat_unique"
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
                            st.error(
                                "❌ Gagal membuat sertifikat: "
                                f"{exc}"
                            )

                    sertifikat_path = (
                        st.session_state.generated_files.get(
                            "sertifikat"
                        )
                    )

                    if (
                        sertifikat_path
                        and Path(sertifikat_path).exists()
                    ):
                        with open(
                            sertifikat_path,
                            "rb"
                        ) as file_pdf:
                            st.download_button(
                                "⬇️ Download Sertifikat",
                                data=file_pdf.read(),
                                file_name=Path(
                                    sertifikat_path
                                ).name,
                                mime="application/pdf",
                                use_container_width=True,
                                key="tj_download_sertifikat",
                            )
                    else:
                        st.caption(
                            "Sertifikat belum digenerate."
                        )
            with col_doc3:
                with st.container(border=True):
                    st.markdown("### ⚖️ Peminjaman Standar")

                    st.caption(
                        "Generate dan download formulir "
                        "peminjaman alat standar."
                    )

                    if st.button(
                        "Generate Form Standar",
                        type="primary",
                        use_container_width=True,
                        key="tj_generate_form_standar",
                    ):
                        try:
                            output_path = Path(
                                "./output/timbangan_jembatan"
                            )

                            output_path.mkdir(
                                parents=True,
                                exist_ok=True,
                            )

                            nama_file = (
                                format_nama_file_dokumen(
                                    data,
                                    "Form_Peminjaman_Alat_Standar"
                                )
                            )

                            filename = (
                                output_path
                                / f"{nama_file}.pdf"
                            )

                            generate_form_peminjaman_standar_pdf(
                                st.session_state.saved_data,
                                str(filename),
                                nomor_surat_perintah="",
                            )

                            st.session_state.generated_files[
                                "form_peminjaman_standar"
                            ] = str(filename)

                            st.success(
                                "✅ Form standar berhasil dibuat."
                            )

                        except Exception as exc:
                            st.error(
                                "❌ Gagal membuat form standar: "
                                f"{exc}"
                            )

                    form_standar_path = (
                        st.session_state.generated_files.get(
                            "form_peminjaman_standar"
                        )
                    )

                    if (
                        form_standar_path
                        and Path(form_standar_path).exists()
                    ):
                        with open(
                            form_standar_path,
                            "rb"
                        ) as file_pdf:
                            st.download_button(
                                "⬇️ Download Form Standar",
                                data=file_pdf.read(),
                                file_name=Path(
                                    form_standar_path
                                ).name,
                                mime="application/pdf",
                                use_container_width=True,
                                key="tj_download_form_standar",
                            )
                    else:
                        st.caption(
                            "Form standar belum digenerate."
                        )
            with col_doc4:
                with st.container(border=True):
                    st.markdown("### 🔏 Peminjaman CTT")

                    st.caption(
                        "Generate dan download formulir "
                        "peminjaman Cap Tanda Tera."
                    )

                    if st.button(
                        "Generate Form CTT",
                        type="primary",
                        use_container_width=True,
                        key="tj_generate_form_ctt",
                    ):
                        try:
                            output_path = Path(
                                "./output/timbangan_jembatan"
                            )

                            output_path.mkdir(
                                parents=True,
                                exist_ok=True,
                            )

                            nama_file = (
                                format_nama_file_dokumen(
                                    data,
                                    "Form_Peminjaman_CTT"
                                )
                            )

                            filename = (
                                output_path
                                / f"{nama_file}.pdf"
                            )

                            generate_form_peminjaman_ctt_pdf(
                                st.session_state.saved_data,
                                str(filename),
                                nomor_surat_perintah="",
                            )

                            st.session_state.generated_files[
                                "form_peminjaman_ctt"
                            ] = str(filename)

                            st.success(
                                "✅ Form CTT berhasil dibuat."
                            )

                        except Exception as exc:
                            st.error(
                                f"❌ Gagal membuat form CTT: {exc}"
                            )

                    form_ctt_path = (
                        st.session_state.generated_files.get(
                            "form_peminjaman_ctt"
                        )
                    )

                    if (
                        form_ctt_path
                        and Path(form_ctt_path).exists()
                    ):
                        with open(
                            form_ctt_path,
                            "rb"
                        ) as file_pdf:
                            st.download_button(
                                "⬇️ Download Form CTT",
                                data=file_pdf.read(),
                                file_name=Path(
                                    form_ctt_path
                                ).name,
                                mime="application/pdf",
                                use_container_width=True,
                                key="tj_download_form_ctt",
                            )
                    else:
                        st.caption(
                            "Form CTT belum digenerate."
                        )
    
    elif mode == "📚 Riwayat Timbangan Jembatan":

        st.header("📚 Riwayat Timbangan Jembatan")
    
        try:
            supabase = get_supabase()
    
            # =====================================================
            # AMBIL DATA TIMBANGAN JEMBATAN
            # =====================================================
            response_uttp = (
                supabase
                .table("uttp")
                .select(
                    "id, perusahaan_id, jenis_uttp, merk, tipe, "
                    "nomor_seri, kapasitas, status"
                )
                .eq(
                    "jenis_uttp",
                    "Timbangan Jembatan"
                )
                .order("id")
                .execute()
            )
    
            daftar_uttp = response_uttp.data or []
    
            if not daftar_uttp:
                st.info(
                    "Belum ada data Timbangan Jembatan."
                )
                st.stop()
    
            # =====================================================
            # AMBIL HANYA PERUSAHAAN YANG PUNYA TJ
            # =====================================================
            daftar_perusahaan_id = list({
                alat_item.get("perusahaan_id")
                for alat_item in daftar_uttp
                if alat_item.get(
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
    
                data_perusahaan_riwayat = (
                    response_perusahaan.data
                    or []
                )
    
            else:
                data_perusahaan_riwayat = []
    
            perusahaan_by_id = {
                p["id"]: p
                for p in data_perusahaan_riwayat
            }
    
            # =====================================================
            # PILIH PERUSAHAAN
            # =====================================================
            perusahaan_tj_map = {}
    
            for alat_item in daftar_uttp:
                perusahaan_id = alat_item.get(
                    "perusahaan_id"
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
                ).strip()
    
                if nama_perusahaan:
                    perusahaan_tj_map[
                        nama_perusahaan
                    ] = perusahaan_item
    
            st.subheader("Cari Perusahaan")
    
            nama_perusahaan_terpilih = st.selectbox(
                "Nama Perusahaan",
                options=sorted(
                    perusahaan_tj_map.keys()
                ),
                index=None,
                placeholder=(
                    "Ketik atau pilih nama perusahaan..."
                ),
                key="tj_riwayat_perusahaan"
            )
    
            if not nama_perusahaan_terpilih:
                st.info(
                    "Silakan pilih perusahaan untuk melihat "
                    "Timbangan Jembatan yang terdaftar."
                )
                st.stop()
    
            perusahaan = perusahaan_tj_map[
                nama_perusahaan_terpilih
            ]
    
            perusahaan_id_terpilih = (
                perusahaan.get("id")
            )
    
            # =====================================================
            # FILTER TJ MILIK PERUSAHAAN
            # =====================================================
            daftar_tj_perusahaan = [
                alat_item
                for alat_item in daftar_uttp
                if alat_item.get(
                    "perusahaan_id"
                ) == perusahaan_id_terpilih
            ]
    
            if not daftar_tj_perusahaan:
                st.info(
                    "Belum ada Timbangan Jembatan "
                    "untuk perusahaan ini."
                )
                st.stop()
    
            # =====================================================
            # PILIH TIMBANGAN
            # =====================================================
            pilihan_alat_map = {}
    
            for alat_item in daftar_tj_perusahaan:
                label_alat = (
                    f"{alat_item.get('merk') or '-'} | "
                    f"{alat_item.get('tipe') or '-'} | "
                    f"No. Seri: "
                    f"{alat_item.get('nomor_seri') or '-'}"
                )
    
                pilihan_alat_map[
                    label_alat
                ] = alat_item
    
            alat_terpilih_label = st.selectbox(
                "Timbangan Jembatan",
                options=list(
                    pilihan_alat_map.keys()
                ),
                index=None,
                placeholder=(
                    "Pilih Timbangan Jembatan..."
                ),
                key="tj_riwayat_alat"
            )
    
            if not alat_terpilih_label:
                st.info(
                    "Silakan pilih Timbangan Jembatan "
                    "untuk melihat riwayat pengujiannya."
                )
                st.stop()
    
            alat = pilihan_alat_map[
                alat_terpilih_label
            ]
    
            # =====================================================
            # RINGKASAN
            # =====================================================
            st.markdown("---")
            st.subheader("Ringkasan Timbangan")
    
            col1, col2, col3 = st.columns(3)
    
            with col1:
                st.metric(
                    "Perusahaan",
                    perusahaan.get(
                        "nama_perusahaan",
                        "-"
                    )
                )
    
            with col2:
                st.metric(
                    "Nomor Seri",
                    alat.get(
                        "nomor_seri"
                    ) or "-"
                )
    
            with col3:
                kapasitas_text = (
                    alat.get("kapasitas")
                    or "-"
                )
    
                st.metric(
                    "Kapasitas",
                    f"{kapasitas_text} kg"
                    if kapasitas_text != "-"
                    else "-"
                )
    
            # =====================================================
            # AMBIL RIWAYAT
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
    
            riwayat = response_riwayat.data or []
    
            st.markdown("---")
            st.subheader(
                "Riwayat Tera / Tera Ulang"
            )
    
            if not riwayat:
                st.info(
                    "Belum ada riwayat pengujian "
                    "untuk Timbangan Jembatan ini."
                )
    
            else:
                pilihan_riwayat = {}
    
                for r in riwayat:
                    label = (
                        f"{r.get('tanggal_pengujian', '-')} | "
                        f"{r.get('jenis_pengujian', '-')} | "
                        f"{r.get('nomor_sertifikat', '-')} | "
                        f"{r.get('penera_1', '-')}"
                    )
    
                    pilihan_riwayat[label] = r
    
                riwayat_terpilih_label = st.selectbox(
                    "Pilih riwayat pengujian",
                    options=list(
                        pilihan_riwayat.keys()
                    ),
                    key=(
                        f"tj_pilih_riwayat_"
                        f"{alat['id']}"
                    )
                )
    
                riwayat_terpilih = (
                    pilihan_riwayat[
                        riwayat_terpilih_label
                    ]
                )
    
                with st.container(
                    border=True
                ):
                    st.write(
                        f"**Tanggal:** "
                        f"{riwayat_terpilih.get('tanggal_pengujian', '-')}"
                    )
    
                    st.write(
                        f"**Jenis:** "
                        f"{riwayat_terpilih.get('jenis_pengujian', '-')}"
                    )
    
                    st.write(
                        f"**Nomor Sertifikat:** "
                        f"{riwayat_terpilih.get('nomor_sertifikat', '-')}"
                    )
    
                    st.write(
                        f"**Penera:** "
                        f"{riwayat_terpilih.get('penera_1', '-')}"
                    )
                st.markdown("---")

                # =====================================================
                # AKSI RIWAYAT
                # =====================================================
                col_aksi1, col_aksi2 = st.columns(2)
                
                with col_aksi1:
                    if st.button(
                        "✏️ Edit Pengujian",
                        use_container_width=True,
                        key=(
                            f"tj_edit_riwayat_"
                            f"{riwayat_terpilih['id']}"
                        )
                    ):
                        gunakan_data_lama_untuk_edit(
                            alat,
                            perusahaan,
                            riwayat_terpilih
                        )
                
                        st.rerun()
                
                
                with col_aksi2:
                    if st.button(
                        "➕ Tambah Pengujian Baru",
                        type="primary",
                        use_container_width=True,
                        key=(
                            f"tj_tambah_pengujian_"
                            f"{riwayat_terpilih['id']}"
                        )
                    ):
                        gunakan_data_lama_untuk_pengujian_baru(
                            alat,
                            perusahaan,
                            riwayat_terpilih
                        )
                
                        st.rerun()
        except Exception as e:
            st.error(
                "Gagal mengambil riwayat "
                "Timbangan Jembatan dari Supabase."
            )
    
            st.exception(e)
    st.markdown("---")
    st.markdown("""
        <div style='text-align: center; color: #888; font-size: 12px;'>
        <p>Aplikasi Automasi Sertifikat Tera © 2026</p>
        <p>Match dengan Template Excel & Word</p>
        </div>
        """, unsafe_allow_html=True)
