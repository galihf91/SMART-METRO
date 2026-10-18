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

from modules.timbangan.cerapan_timbangan_generator import (
    generate_cerapan_pdf,
)


def find_project_root():
    current = Path(__file__).resolve()

    for parent in [current.parent] + list(current.parents):
        if (parent / "modules").exists() or (parent / "app.py").exists():
            return parent

    return current.parent


PROJECT_ROOT = find_project_root()
OUTPUT_DIR = PROJECT_ROOT / "output" / "uttp"

# =====================================================================
# NOMOR ORDER UTTP: PAKAI ULANG JIKA PERUSAHAAN + TANGGAL SAMA
# =====================================================================

def _uttp_nomor_order_siap_pakai(nomor):
    """True kalau nomor order sudah terisi dan bukan template 0000."""
    if not nomor:
        return False

    teks = str(nomor).strip()
    if not teks:
        return False

    depan = teks.split("/")[0].strip()
    if not depan.isdigit():
        return False

    return int(depan) > 0


def _uttp_ke_iso_tanggal(nilai_tanggal):
    """Ubah date / datetime / string menjadi format YYYY-MM-DD."""
    from datetime import datetime

    if nilai_tanggal is None:
        return None

    if hasattr(nilai_tanggal, "strftime"):
        return nilai_tanggal.strftime("%Y-%m-%d")

    teks = str(nilai_tanggal).strip()
    for pola in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(teks, pola).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return teks


def _uttp_nama_normal(nama):
    """Rapikan nama untuk perbandingan: huruf besar, spasi ganda dibuang."""
    return " ".join(str(nama or "").upper().split())


def _ambil_nama_perusahaan_form_uttp():
    """Ambil nama perusahaan dari session_state form UTTP."""
    daftar_kunci = (
        "uttp_nama_perusahaan",
        "nama_perusahaan",
        "uttp_perusahaan_manual",
    )

    for kunci in daftar_kunci:
        nilai = st.session_state.get(kunci)
        if nilai and str(nilai).strip():
            return str(nilai).strip()

    for kunci, nilai in st.session_state.items():
        if not isinstance(kunci, str) or not isinstance(nilai, str):
            continue
        if not nilai.strip():
            continue

        kunci_kecil = kunci.lower()
        cocok = "nama" in kunci_kecil and (
            "perusahaan" in kunci_kecil or "pemilik" in kunci_kecil
        )
        if cocok:
            return nilai.strip()

    return ""


def _uttp_cari_perusahaan_id(supabase, nama):
    """
    Cari id perusahaan dari nama.
    Cara 1: cocok persis.
    Cara 2: cocok setelah dinormalisasi (spasi ganda / huruf besar-kecil),
    menyesuaikan cara kerja simpan_atau_update_perusahaan_uttp yang
    mencocokkan nama dengan ilike.
    """
    nama = str(nama or "").strip()
    if not nama:
        return None

    res_persis = (
        supabase.table("perusahaan")
        .select("id, nama_perusahaan")
        .eq("nama_perusahaan", nama)
        .limit(1)
        .execute()
    )
    if res_persis.data:
        return res_persis.data[0]["id"]

    target = _uttp_nama_normal(nama)
    res_mirip = (
        supabase.table("perusahaan")
        .select("id, nama_perusahaan")
        .ilike("nama_perusahaan", f"%{nama}%")
        .limit(50)
        .execute()
    )
    for baris in (res_mirip.data or []):
        if _uttp_nama_normal(baris.get("nama_perusahaan")) == target:
            return baris["id"]

    return None


def cari_nomor_order_sebelumnya_uttp(
    nama_perusahaan,
    tanggal_pengujian,
    perusahaan_id=None,
):
    """
    Cari nomor order yang sudah ada untuk perusahaan + tanggal pengujian sama.
    Membaca tabel `pengujian`, jadi berlaku lintas modul
    (Timbangan biasa, Jembatan, PUBBM, UTTP Umum).

    Ketemu  : kembalikan nomor order (dipakai ulang)
    Tidak ada: kembalikan None
    """
    from supabase import create_client

    try:
        tanggal_iso = _uttp_ke_iso_tanggal(tanggal_pengujian)
        if not tanggal_iso:
            return None

        supabase = create_client(
            st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
        )

        # 1. tentukan perusahaan_id
        if not perusahaan_id:
            if not str(nama_perusahaan or "").strip():
                return None

            perusahaan_id = _uttp_cari_perusahaan_id(
                supabase, nama_perusahaan
            )
            if not perusahaan_id:
                return None

        # 2. daftar uttp milik perusahaan ini (jalur cadangan)
        res_uttp = (
            supabase.table("uttp")
            .select("id")
            .eq("perusahaan_id", perusahaan_id)
            .limit(500)
            .execute()
        )
        uttp_ids = {
            baris.get("id")
            for baris in (res_uttp.data or [])
            if baris.get("id") is not None
        }

        # 3. semua pengujian pada tanggal itu
        res_pengujian = (
            supabase.table("pengujian")
            .select("id, nomor_order, perusahaan_id, uttp_id")
            .eq("tanggal_pengujian", tanggal_iso)
            .order("id", desc=False)
            .limit(500)
            .execute()
        )

        for baris in (res_pengujian.data or []):
            nomor = baris.get("nomor_order")
            if not _uttp_nomor_order_siap_pakai(nomor):
                continue

            id_perusahaan_baris = baris.get("perusahaan_id")
            id_uttp_baris = baris.get("uttp_id")

            milik_perusahaan = (
                id_perusahaan_baris == perusahaan_id
                or (not id_perusahaan_baris and id_uttp_baris in uttp_ids)
            )

            if milik_perusahaan:
                return str(nomor).strip()

    except Exception as e:
        st.warning(f"Gagal mengecek nomor order sebelumnya: {e}")

    return None

# =========================================================
# CERAPAN UTTP - INPUT PENGUKURAN PER ALAT (SAMPLE)
# =========================================================

VISUAL_ITEMS_CERAPAN_UTTP = [
    "Timbangan bersih, kering dan tidak berkarat",
    "Bahan & Konstruksi Sesuai (Tera)",
    "Posisi timbangan datar",
    "Telah dilakukan pemanasan timbangan",
]


def teks_bkd_cerapan_uttp(koef):
    if koef == 0.5:
        return "±0.5e"
    if koef == 1.0:
        return "±1e"
    if koef == 1.5:
        return "±1.5e"
    if koef == 2.0:
        return "±2e"
    if koef == 3.0:
        return "±3e"
    if koef > 0:
        return f"±{koef:g}e"
    return ""

def _desimal_dari_angka_uttp(nilai):
    """Jumlah angka desimal sebuah nilai (0.005 menjadi 3, 5 menjadi 0)."""
    try:
        teks = f"{float(nilai):.10f}".rstrip("0")
    except (TypeError, ValueError):
        return 0

    if "." not in teks:
        return 0

    return len(teks.split(".")[1])


def hitung_muatan_uji_cerapan_uttp(
    kelas,
    e_kg,
    kapasitas_max_kg,
    jumlah_titik,
):
    """
    Titik muatan uji (kg), disalin dari aturan aplikasi Timbangan.
    3 titik : Minimum, 50% Maksimum, Maksimum.
    5 titik : Minimum, tiga titik tengah, Maksimum.
    """
    kelas = str(kelas or "III").strip()
    e_kg = float(e_kg or 0)
    kapasitas_max_kg = float(kapasitas_max_kg or 0)

    if e_kg <= 0 or kapasitas_max_kg <= 0:
        return [0.0] * int(jumlah_titik)

    if kelas == "II":
        faktor_min = 50 if e_kg >= 0.0001 else 20
    else:
        faktor_min = {
            "I": 100,
            "III": 20,
            "IIII": 10,
        }.get(kelas, 20)

    minimum_kg = min(faktor_min * e_kg, kapasitas_max_kg)

    if int(jumlah_titik) == 3:
        return [
            minimum_kg,
            kapasitas_max_kg * 0.5,
            kapasitas_max_kg,
        ]

    if abs(minimum_kg - kapasitas_max_kg) < 1e-12:
        return [kapasitas_max_kg] * 5

    def valid_middle(nilai):
        return minimum_kg < nilai < kapasitas_max_kg

    def finalize(kandidat):
        tengah = []

        for nilai in kandidat:
            nilai = round(float(nilai), 12)
            if valid_middle(nilai) and nilai not in tengah:
                tengah.append(nilai)

        if len(tengah) < 3:
            for pecahan in (0.25, 0.50, 0.75):
                nilai = round(kapasitas_max_kg * pecahan, 12)
                if valid_middle(nilai) and nilai not in tengah:
                    tengah.append(nilai)
                if len(tengah) >= 3:
                    break

        if len(tengah) < 3:
            rentang = kapasitas_max_kg - minimum_kg
            for pecahan in (0.20, 0.40, 0.60, 0.80):
                nilai = round(minimum_kg + rentang * pecahan, 12)
                if valid_middle(nilai) and nilai not in tengah:
                    tengah.append(nilai)
                if len(tengah) >= 3:
                    break

        tengah = sorted(tengah)

        if len(tengah) > 3:
            pilihan = [
                tengah[0],
                tengah[len(tengah) // 2],
                tengah[-1],
            ]
            tengah = sorted(set(pilihan))

        while len(tengah) < 3:
            tengah.append(tengah[-1] if tengah else minimum_kg)

        return [
            minimum_kg,
            tengah[0],
            tengah[1],
            tengah[2],
            kapasitas_max_kg,
        ]

    if kelas == "II":
        titik_5000e = 5000 * e_kg
        titik_20000e = 20000 * e_kg
        titik_100000e = 100000 * e_kg

        if valid_middle(titik_100000e):
            return finalize([
                titik_5000e,
                titik_20000e,
                titik_100000e,
            ])

        if valid_middle(titik_20000e):
            titik_sebelum = titik_20000e * 0.5
            if not (titik_5000e < titik_sebelum < titik_20000e):
                titik_sebelum = (titik_5000e + titik_20000e) / 2.0
            return finalize([
                titik_5000e,
                titik_sebelum,
                titik_20000e,
            ])

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

    kandidat = [
        faktor * e_kg
        for faktor in faktor_tengah
        if valid_middle(faktor * e_kg)
    ]

    return finalize(kandidat)


def render_input_cerapan_uttp(
    index,
    nama_alat,
    data_lama,
    tampilkan_checkbox=True,
):
    """
    Input pengukuran cerapan versi LITE.
    - e = daya baca, kelas mengikuti isian user di form input data.
    - Visual: default tercentang semua, kecuali "Bahan & Konstruksi
      Sesuai (Tera)" yang hanya tercentang untuk jenis pengujian Tera.
    - Penunjukan selalu sama dengan Muatan Uji (disabled), jadi hasil SAH.
    - BKD dihitung otomatis dari muatan uji (kebenaran, eksentrisitas,
      repetability) mengikuti aturan aplikasi Timbangan.
    """
    data_lama = data_lama or {}
    cerapan_lama = data_lama.get("data_cerapan") or {}

    nama_alat_kecil = str(nama_alat or "").strip().lower()
    is_neraca_obat = nama_alat_kecil in {
        "neraca obat",
        "timbangan neraca obat",
    }
    is_timbangan_meja = nama_alat_kecil in {
        "timbangan meja",
        "meja",
    }

    cukup_satu_baris = is_neraca_obat or is_timbangan_meja

    satuan = str(data_lama.get("satuan", "kg") or "kg").strip()

    data_uttp = st.session_state.get("uttp_saved_data", {}) or {}
    jenis_pengujian = str(
        data_uttp.get("jenis_pengujian", "Tera Ulang") or "Tera Ulang"
    ).strip()

    kapasitas_kg = angka_numeric_uttp(data_lama.get("kapasitas")) or 0.0
    daya_baca_kg = angka_numeric_uttp(data_lama.get("daya_baca")) or 0.0
    kelas_uttp = str(data_lama.get("kelas", "") or "III").strip()

    if daya_baca_kg <= 0:
        daya_baca_kg = 0.0

    # ---- interval skala verifikasi (e) ----
    if is_neraca_obat:
        interval_skala_kg = kapasitas_kg / 10000.0
    elif is_timbangan_meja:
        interval_skala_kg = kapasitas_kg / 1000.0
    else:
        interval_skala_kg = daya_baca_kg

    desimal_tampil = _desimal_dari_angka_uttp(interval_skala_kg)
    step_tampil = interval_skala_kg if interval_skala_kg > 0 else 0.001
    format_tampil = f"%.{desimal_tampil}f"


    if tampilkan_checkbox:
        kunci_sample = f"uttp_rincian_sample_{index}"
        if kunci_sample not in st.session_state:
            st.session_state[kunci_sample] = bool(
                data_lama.get("sample_cerapan", False)
            )

        sample_cerapan = st.checkbox(
            "Jadikan sample cerapan",
            key=kunci_sample,
        )

        if not sample_cerapan:
            return False, {}

    # ---- kapasitas minimum ----
    if is_neraca_obat:
        kapasitas_min_awal_kg = float(
            cerapan_lama.get("kapasitas_min") or kapasitas_kg
        )

        st.markdown("---")
        st.subheader("Spesifikasi Alat")
        st.caption(
            "Neraca obat tidak memiliki daya baca. Interval skala "
            "verifikasi dihitung Maksimum / 10.000."
        )

        kapasitas_min_kg = st.number_input(
            f"Minimum Menimbang ({satuan})",
            value=float(kapasitas_min_awal_kg),
            step=float(step_tampil),
            format="%g",
            key=f"uttp_cerapan_kapasitas_min_{index}",
        )
    elif is_timbangan_meja:
        kapasitas_min_kg = 20.0 * interval_skala_kg
    else:
        kapasitas_min_kg = 0.0

    # ======================== PEMERIKSAAN VISUAL ========================
    st.markdown("---")
    st.subheader("Pemeriksaan Visual")

    visual_lama = cerapan_lama.get("visual", {}) or {}
    visual = {}

    kolom_visual = st.columns(4)

    for nomor_visual, item_visual in enumerate(
        VISUAL_ITEMS_CERAPAN_UTTP
    ):
        with kolom_visual[nomor_visual % 4]:
            is_bahan_konstruksi = (
                item_visual == "Bahan & Konstruksi Sesuai (Tera)"
            )

            if item_visual in visual_lama:
                default_visual = bool(visual_lama.get(item_visual))
            elif is_bahan_konstruksi:
                default_visual = (jenis_pengujian == "Tera")
            else:
                default_visual = True

            visual[item_visual] = st.checkbox(
                item_visual,
                value=default_visual,
                key=f"uttp_cerapan_visual_{index}_{nomor_visual}",
            )

    # ======================== PENGUJIAN KEBENARAN ========================
    st.markdown("---")
    st.subheader("Pengujian Kebenaran")

    benar_lama = list(cerapan_lama.get("hasil_pengujian", []) or [])

    if cukup_satu_baris:
        jumlah_titik = 1

    else:
        default_titik = 3 if len(benar_lama) == 3 else 5

        kunci_titik = f"uttp_cerapan_jumlah_titik_{index}"
        if kunci_titik not in st.session_state:
            st.session_state[kunci_titik] = default_titik

        jumlah_titik = st.radio(
            "Jumlah Titik Uji",
            options=[5, 3],
            horizontal=True,
            key=kunci_titik,
            format_func=lambda x: f"{x} Titik Uji",
            help=(
                "5 titik menggunakan susunan muatan uji standar. "
                "3 titik menggunakan Minimum Menimbang, 50% Maksimum, "
                "dan Maksimum."
            ),
        )

    if not is_neraca_obat:
        st.caption("e = d")

    if cukup_satu_baris:
        # Neraca Obat & Timbangan Meja: satu titik, muatan maksimum
        daftar_muatan_auto = [kapasitas_kg]
    else:
        daftar_muatan_auto = hitung_muatan_uji_cerapan_uttp(
            kelas_uttp,
            daya_baca_kg,
            kapasitas_kg,
            jumlah_titik,
        )


    st.write("**Masukkan Hasil Pengujian**")
    st.caption(
        "Penunjukan otomatis sama dengan Muatan Uji. "
        "BKD mengikuti nilai Muatan Uji."
    )

    kolom_header_benar = st.columns(
        [0.5, 2.1, 2.3, 1.4, 3.6, 1.2, 1.4]
    )

    for kolom_header, label_header in zip(
        kolom_header_benar,
        [
            "**No**",
            "**Muatan Uji**",
            "**Penunjukan**",
            "**BKD**",
            "**Pengamatan Penunjukan**",
            "**Hasil**",
            "**Cek**",
        ],
    ):
        kolom_header.write(label_header)

    hasil_pengujian = []

    for nomor_titik in range(1, int(jumlah_titik) + 1):
        item_lama = {}

        if (nomor_titik - 1) < len(benar_lama):
            calon_item = benar_lama[nomor_titik - 1]
            if isinstance(calon_item, dict):
                item_lama = calon_item

        muatan_auto_kg = 0.0
        if (nomor_titik - 1) < len(daftar_muatan_auto):
            muatan_auto_kg = float(
                daftar_muatan_auto[nomor_titik - 1]
            )

        try:
            muatan_lama_kg = float(
                item_lama.get("muatan_uji", 0.0) or 0.0
            )
        except (TypeError, ValueError):
            muatan_lama_kg = 0.0

        if muatan_lama_kg <= 0:
            muatan_lama_kg = muatan_auto_kg

        kolom_baris = st.columns([0.5, 2.1, 2.3, 1.4, 3.6, 1.2, 1.4])

        with kolom_baris[0]:
            st.text_input(
                f"No {nomor_titik}",
                value=str(nomor_titik),
                disabled=True,
                key=f"uttp_cerapan_benar_no_{index}_{nomor_titik}",
                label_visibility="collapsed",
            )

        with kolom_baris[1]:
            muatan_tampil = st.number_input(
                f"Muatan Uji {nomor_titik}",
                value=float(muatan_lama_kg),
                step=float(step_tampil),
                format="%g",
                key=f"uttp_cerapan_benar_muatan_{index}_{nomor_titik}",
                label_visibility="collapsed",
            )


        # Penunjukan selalu sama dengan Muatan Uji
        penunjukan_tampil = float(muatan_tampil)
        teks_penunjukan = format_tampil % penunjukan_tampil


        kunci_penunjukan = (
            f"uttp_cerapan_benar_penunjukan_{index}_{nomor_titik}"
        )
        st.session_state[kunci_penunjukan] = teks_penunjukan

        with kolom_baris[2]:
            st.text_input(
                f"Penunjukan {nomor_titik}",
                value=teks_penunjukan,
                disabled=True,
                key=kunci_penunjukan,
                label_visibility="collapsed",
            )

        # BKD mengikuti Muatan Uji
        koef_baris = hitung_koef_bkd_cerapan_uttp(
            kelas_uttp,
            muatan_tampil,
            interval_skala_kg,
            jenis_pengujian,
        )

        teks_bkd_baris = teks_bkd_cerapan_uttp(koef_baris)

        with kolom_baris[3]:
            st.write(teks_bkd_baris if teks_bkd_baris else "-")

        with kolom_baris[4]:
            st.write("penunjukan ≤ massa ATS ± BKD")

        with kolom_baris[5]:
            st.write("SAH")

        with kolom_baris[6]:
            st.write("✅")

        hasil_pengujian.append({
            "muatan_uji": float(muatan_tampil),
            "penunjukan": penunjukan_tampil,
        })

    # ======================== EKSENTRISITAS ========================
    eksentrisitas = []

    if not is_neraca_obat:
        st.markdown("---")
        st.subheader("Eksentrisitas (1/3 Maks)")

        muatan_eks_awal_kg = kapasitas_kg / 3.0

        _muatan_eks_tersimpan = cerapan_lama.get("muatan_eksentrisitas")
        if _muatan_eks_tersimpan:
            try:
                muatan_eks_awal_kg = float(_muatan_eks_tersimpan)
            except (TypeError, ValueError):
                pass

        muatan_eks_kg = st.number_input(
            f"Muatan Uji Eksentrisitas ({satuan})",
            value=float(muatan_eks_awal_kg),
            step=float(step_tampil),
            format="%g",
            key=f"uttp_cerapan_eksen_muatan_{index}",
        )

        koef_eksen = hitung_koef_bkd_cerapan_uttp(
            kelas_uttp,
            muatan_eks_kg,
            interval_skala_kg,
            jenis_pengujian,
        )
        teks_bkd_eksen = teks_bkd_cerapan_uttp(koef_eksen)


        kolom_header_eks = st.columns([0.8, 2.2, 1.4, 3.4, 1.4, 1.2])

        for kolom_header, label_header in zip(
            kolom_header_eks,
            [
                "**Posisi**",
                "**Penunjukan (I)**",
                "**BKD**",
                "**Pengamatan Penunjukan**",
                "**Hasil**",
                "**Cek**",
            ],
        ):
            kolom_header.write(label_header)

        eksen_lama = list(cerapan_lama.get("eksentrisitas", []) or [])

        for posisi in range(1, 5):
            teks_penunjukan_eksen = format_tampil % float(muatan_eks_kg)


            kunci_penunjukan_eksen = (
                f"uttp_cerapan_eksen_{index}_{posisi}"
            )
            st.session_state[kunci_penunjukan_eksen] = (
                teks_penunjukan_eksen
            )

            kolom_baris = st.columns([0.8, 2.2, 1.4, 3.4, 1.4, 1.2])

            with kolom_baris[0]:
                st.text_input(
                    f"Posisi {posisi}",
                    value=str(posisi),
                    disabled=True,
                    key=f"uttp_cerapan_eksen_posisi_{index}_{posisi}",
                    label_visibility="collapsed",
                )

            with kolom_baris[1]:
                st.text_input(
                    f"Penunjukan Eksentrisitas {posisi}",
                    value=teks_penunjukan_eksen,
                    disabled=True,
                    key=kunci_penunjukan_eksen,
                    label_visibility="collapsed",
                )

            with kolom_baris[2]:
                st.write(teks_bkd_eksen if teks_bkd_eksen else "-")

            with kolom_baris[3]:
                st.write("penunjukan ≤ massa ATS ± BKD")

            with kolom_baris[4]:
                st.write("SAH")

            with kolom_baris[5]:
                st.write("✅")

            eksentrisitas.append({
                "posisi": posisi,
                "penunjukan": float(muatan_eks_kg),
            })


        eksentrisitas_muatan_kg = float(muatan_eks_kg)
    else:
        eksentrisitas_muatan_kg = 0.0

    # ======================== REPETABILITY ========================
    st.markdown("---")
    st.subheader("Repetability")

    if not is_neraca_obat:
        st.caption("e = d")

    muatan_repet_awal_kg = kapasitas_kg * 0.5
    if cukup_satu_baris:
        muatan_repet_awal_kg = kapasitas_kg


    _muatan_repet_tersimpan = cerapan_lama.get("muatan_repetability")
    if _muatan_repet_tersimpan:
        try:
            muatan_repet_awal_kg = float(_muatan_repet_tersimpan)
        except (TypeError, ValueError):
            pass

    muatan_repet_kg = st.number_input(
        f"Muatan Uji Repetability ({satuan})",
        value=float(muatan_repet_awal_kg),
        step=float(step_tampil),
        format="%g",
        key=f"uttp_cerapan_repet_muatan_{index}",
    )


    koef_repet = hitung_koef_bkd_cerapan_uttp(
        kelas_uttp,
        muatan_repet_kg,
        interval_skala_kg,
        jenis_pengujian,
    )

    teks_bkd_repet = teks_bkd_cerapan_uttp(koef_repet)

    kolom_header_repet = st.columns([3.5, 1.5, 1.5])

    with kolom_header_repet[0]:
        st.write("**Penunjukan Akhir**")

    with kolom_header_repet[1]:
        st.write("**BKD**")

    with kolom_header_repet[2]:
        st.write("**Hasil**")

    repet_lama = list(cerapan_lama.get("repetability", []) or [])
    repetability = []

    for ulang in range(1, 4):
        teks_penunjukan_repet = format_tampil % float(muatan_repet_kg)


        kunci_penunjukan_repet = (
            f"uttp_cerapan_repet_{index}_{ulang}"
        )
        st.session_state[kunci_penunjukan_repet] = (
            teks_penunjukan_repet
        )

        kolom_baris = st.columns([3.5, 1.5, 1.5])

        with kolom_baris[0]:
            st.text_input(
                f"Penunjukan Akhir {ulang}",
                value=teks_penunjukan_repet,
                disabled=True,
                key=kunci_penunjukan_repet,
                label_visibility="collapsed",
            )

        with kolom_baris[1]:
            st.write(teks_bkd_repet if teks_bkd_repet else "-")

        with kolom_baris[2]:
            st.write("✅")

        repetability.append({
            "penunjukan": float(muatan_repet_kg),
            "penunjukan_akhir": float(muatan_repet_kg),
            "hasil": True,
        })



    data_cerapan = {
        "visual": visual,
        "hasil_pengujian": hasil_pengujian,
        "eksentrisitas": eksentrisitas,
        "repetability": repetability,
        "muatan_eksentrisitas": eksentrisitas_muatan_kg,
        "muatan_repetability": float(muatan_repet_kg),
        "kapasitas_min": float(kapasitas_min_kg),
        "interval_skala": float(interval_skala_kg),
        "repetability_sederhana": bool(cukup_satu_baris),
        "satu_baris_benar": bool(cukup_satu_baris),
        "sembunyikan_daya_baca": bool(is_timbangan_meja),
    }

    return True, data_cerapan




def hitung_koef_bkd_cerapan_uttp(
    kelas,
    muatan_kg,
    interval_skala_kg,
    jenis_pengujian,
):
    """Koefisien BKD (kali e), sama dengan aturan di cerapan_timbangan_generator."""
    e_kg = float(interval_skala_kg or 0)

    if e_kg <= 0:
        return 0.0

    m = float(muatan_kg or 0) / e_kg

    batas = {
        "I": [(50000, 0.5), (200000, 1.0), (float("inf"), 1.5)],
        "II": [(5000, 0.5), (20000, 1.0), (100000, 1.5)],
        "III": [(500, 0.5), (2000, 1.0), (10000, 1.5)],
        "IIII": [(50, 0.5), (200, 1.0), (1000, 1.5)],
    }

    koef = 1.5

    for batas_m, nilai_koef in batas.get(
        str(kelas).strip(), batas["III"]
    ):
        if m <= batas_m:
            koef = nilai_koef
            break

    if str(jenis_pengujian).strip() == "Tera Ulang":
        koef *= 2.0

    return koef

def rakit_data_cerapan_uttp(data, rincian):
    """
    Menggabungkan identitas pengujian + spesifikasi alat + data pengukuran
    menjadi satu dict untuk generate_cerapan_pdf().
    """
    data = data or {}
    rincian = rincian or {}

    satuan = str(rincian.get("satuan", "kg") or "kg").strip()

    daya_baca = angka_numeric_uttp(rincian.get("daya_baca"))
    if daya_baca is None:
        daya_baca = 0.0

    hasil = {
        # ---------- identitas ----------
        "pemilik": (
            rincian.get("nama_pemilik")
            or data.get("pemilik", "")
        ),
        "alamat": (
            rincian.get("alamat")
            or data.get("alamat", "")
        ),


        "nomor_order": data.get("nomor_order", ""),
        "nomor_sertifikat": data.get("nomor_sertifikat", ""),

        # ---------- spesifikasi alat ----------
        "nama_alat": rincian.get("nama_alat", "Timbangan Elektronik"),
        "merek": rincian.get("merek", ""),
        "model": rincian.get("model_tipe", ""),
        "no_seri": rincian.get("nomor_seri", ""),
        "no_alat": "",
        "kapasitas_max": (
            angka_numeric_uttp(rincian.get("kapasitas")) or 0.0
        ),
        "kapasitas_min": 0.0,
        "daya_baca": daya_baca,
        "interval_skala": daya_baca,
        "kelas": rincian.get("kelas", ""),
        "satuan": satuan,

        # ---------- data pengujian ----------
        "tanggal": data.get("tanggal_pengujian"),
        "tanggal_penera": data.get("tanggal_pengujian"),
        "lokasi": data.get("lokasi", "") or "Perusahaan",
        "suhu": data.get("suhu", "Ambient"),
        "kelembaban": data.get("kelembaban", "Ambient"),
        "metode": data.get("metode", "") or "Beban Substitusi Tunggal",
        "at_standar": (
            data.get("at_standar")
            or ", ".join(data.get("alat_standar") or [])
            or "M2"
        ),

        "keterangan": (
            data.get("jenis_pengujian")
            or data.get("keterangan")
            or "Tera Ulang"
        ),

        # ---------- penera ----------
        "nama_penera": data.get("penera_1", ""),
        "nama_penera_2": data.get("penera_2", ""),
    }

    hasil.update(dict(rincian.get("data_cerapan") or {}))

    # ---- format penunjukan mengikuti desimal daya baca ----
    desimal_daya_baca = _desimal_dari_angka_uttp(daya_baca)

    def _teks_penunjukan(nilai_kg):
        try:
            angka = float(nilai_kg)
        except (TypeError, ValueError):
            return ""

        teks = f"{angka:.{desimal_daya_baca}f}".replace(".", ",")
        return f"{teks} {satuan}"

    # ---- pengujian kebenaran ----
    benar_lengkap = []

    for item_benar in list(hasil.get("hasil_pengujian") or []):
        item_baru = dict(item_benar)
        item_baru["penunjukan_text"] = _teks_penunjukan(
            item_baru.get("penunjukan", 0.0)
        )
        benar_lengkap.append(item_baru)

    hasil["hasil_pengujian"] = benar_lengkap
    # ---- kapasitas minimum ----
    kapasitas_min_eksplisit = float(
        (rincian.get("data_cerapan") or {}).get("kapasitas_min") or 0.0
    )

    if kapasitas_min_eksplisit > 0:
        hasil["kapasitas_min"] = kapasitas_min_eksplisit
    elif benar_lengkap:
        kapasitas_min_kg = float(
            benar_lengkap[0].get(
                "muatan_uji",
                benar_lengkap[0].get("penunjukan", 0.0),
            ) or 0.0
        )

        if kapasitas_min_kg > 0:
            hasil["kapasitas_min"] = kapasitas_min_kg



    # ---- eksentrisitas: kolom Penunjukan + BKD ----
    kelas_cerapan = str(rincian.get("kelas", "") or "III").strip()
    jenis_cerapan = str(
        data.get("jenis_pengujian")
        or data.get("keterangan")
        or "Tera Ulang"
    ).strip()

    muatan_eks_kg = (
        angka_numeric_uttp(rincian.get("kapasitas")) or 0.0
    ) / 3.0

    koef_eksen = hitung_koef_bkd_cerapan_uttp(
        kelas_cerapan,
        muatan_eks_kg,
        hasil.get("interval_skala") or daya_baca,
        jenis_cerapan,
    )
    teks_bkd_eksen = teks_bkd_cerapan_uttp(koef_eksen)


    eksen_lengkap = []

    for item_eksen in list(hasil.get("eksentrisitas") or []):
        item_baru = dict(item_eksen)
        nilai_eksen = item_baru.get("penunjukan", 0.0)

        item_baru["penunjukan_tampil"] = nilai_eksen
        item_baru["penunjukan_text"] = _teks_penunjukan(nilai_eksen)
        item_baru["pengamatan_penunjukan"] = (
            "penunjukan ≤ massa ATS ± BKD"
        )
        item_baru["bkd_text"] = teks_bkd_eksen
        item_baru["hasil"] = True
        item_baru["hasil_text"] = "SAH"

        eksen_lengkap.append(item_baru)

    hasil["eksentrisitas"] = eksen_lengkap

    # ---- repetability: penunjukan pertama = penunjukan timbangan ----
    repet_lengkap = []

    for item_repet in list(hasil.get("repetability") or []):
        item_baru = dict(item_repet)

        nilai_repet = item_baru.get(
            "penunjukan_akhir",
            item_baru.get("penunjukan", 0.0),
        )
        teks_repet = _teks_penunjukan(nilai_repet)

        item_baru["penunjukan"] = nilai_repet
        item_baru["penunjukan_text"] = teks_repet
        item_baru["penunjukan_akhir"] = nilai_repet
        item_baru["penunjukan_akhir_text"] = teks_repet
        item_baru["naik_05e"] = 0.5 * daya_baca
        item_baru["naik_05e_text"] = (
            f"{0.5 * daya_baca:g}".replace(".", ",") + f" {satuan}"
        )

        item_baru["hasil"] = True

        repet_lengkap.append(item_baru)

    hasil["repetability"] = repet_lengkap
    
    # ---- generator PDF memakai kg, sedangkan input rincian
    #      memakai satuan alat. Faktor diambil dari fungsi generator
    #      supaya cocok untuk satuan apa pun (g, gr, gram, kg, mg). ----
    try:
        from modules.timbangan.cerapan_timbangan_generator import (
            nilai_dengan_satuan_dari_kg as _nilai_dalam_satuan,
        )

        teks_contoh_satuan = str(
            _nilai_dalam_satuan(0.001, satuan)
        )
        angka_contoh_satuan = float(
            teks_contoh_satuan.split()[0].replace(",", ".")
        )

        faktor_ke_kg = (
            0.001 / angka_contoh_satuan
            if angka_contoh_satuan > 0
            else 1.0
        )
    except Exception:
        faktor_ke_kg = {
            "kg": 1.0,
            "g": 0.001,
            "gr": 0.001,
            "gram": 0.001,
            "mg": 0.000001,
            "ton": 1000.0,
        }.get(str(satuan).strip().lower(), 1.0)


    if faktor_ke_kg != 1.0:

        def _ke_kg(nilai):
            try:
                return float(nilai) * faktor_ke_kg
            except (TypeError, ValueError):
                return 0.0

        hasil["kapasitas_max"] = _ke_kg(
            hasil.get("kapasitas_max", 0)
        )
        hasil["kapasitas_min"] = _ke_kg(
            hasil.get("kapasitas_min", 0)
        )
        hasil["daya_baca"] = _ke_kg(
            hasil.get("daya_baca", 0)
        )
        hasil["interval_skala"] = _ke_kg(
            hasil.get("interval_skala", 0)
        )

        for item_benar in list(hasil.get("hasil_pengujian") or []):
            item_benar["penunjukan"] = _ke_kg(
                item_benar.get("penunjukan", 0)
            )
            if "muatan_uji" in item_benar:
                item_benar["muatan_uji"] = _ke_kg(
                    item_benar.get("muatan_uji", 0)
                )

        for item_eksen in list(hasil.get("eksentrisitas") or []):
            item_eksen["penunjukan"] = _ke_kg(
                item_eksen.get("penunjukan", 0)
            )
            item_eksen["penunjukan_tampil"] = item_eksen["penunjukan"]

        for item_repet in list(hasil.get("repetability") or []):
            item_repet["penunjukan"] = _ke_kg(
                item_repet.get("penunjukan", 0)
            )
            item_repet["penunjukan_akhir"] = _ke_kg(
                item_repet.get("penunjukan_akhir", 0)
            )
            if "naik_05e" in item_repet:
                item_repet["naik_05e"] = _ke_kg(
                    item_repet.get("naik_05e", 0)
                )
    
    return hasil

def rapikan_teks_angka_uttp(nilai):
    """Teks angka untuk UI: 1.0 menjadi "1", 0.50 menjadi "0.5"."""
    if nilai is None:
        return ""
    if isinstance(nilai, str):
        return nilai.strip()
    try:
        angka = float(nilai)
    except (TypeError, ValueError):
        return str(nilai)
    if angka != angka:
        return ""
    teks = f"{angka:.6f}".rstrip("0").rstrip(".")
    if teks in ("", "-0"):
        teks = "0"
    return teks

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
    """
    Aturan:

    1. Perusahaan belum ada
       → INSERT perusahaan baru.

    2. Perusahaan sudah ada, alamat berubah
       → UPDATE alamat.

    3. Perusahaan sudah ada, alamat sama
       → gunakan ID perusahaan lama.

    Berlaku baik untuk:
    - perusahaan yang dipilih dari daftar;
    - perusahaan yang diinput manual.
    """

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

    if not alamat:
        raise ValueError(
            "Alamat pemilik / perusahaan belum diisi."
        )

    # =====================================================
    # CARI PERUSAHAAN BERDASARKAN NAMA
    #
    # ilike digunakan supaya:
    # PT ABC
    # pt abc
    # dianggap perusahaan yang sama.
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

        # =================================================
        # CEK APAKAH ADA PERUBAHAN
        # =================================================
        payload_update = {}

        # Nama ikut diperbarui agar kapitalisasi / penulisan
        # mengikuti input terbaru user.
        if nama_perusahaan != nama_lama:
            payload_update[
                "nama_perusahaan"
            ] = nama_perusahaan

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
    # PERUSAHAAN BELUM ADA → INSERT BARU
    # =====================================================
    response_insert = (
        supabase
        .table("perusahaan")
        .insert({
            "nama_perusahaan": (
                nama_perusahaan
            ),
            "alamat": alamat,
        })
        .execute()
    )

    if not response_insert.data:
        raise RuntimeError(
            "Perusahaan baru gagal disimpan "
            "ke Supabase."
        )

    return response_insert.data[0][
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

    Identitas utama master UTTP adalah ID database.

    Jika berasal dari Edit / Riwayat:
    - gunakan _uttp_id yang sudah tersimpan.

    Jika rincian baru:
    - buat master UTTP baru.

    Nomor seri hanya atribut alat dan tidak digunakan
    sebagai identitas unik karena nomor seri dapat sama
    pada lebih dari satu UTTP.
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
        "perusahaan_id": perusahaan_id,

        "jenis_uttp": jenis_uttp,

        "merk": merk,

        "tipe": (
            tipe
            if tipe
            else None
        ),

        "nomor_seri": nomor_seri,

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

        "daya_baca": daya_baca,

        "satuan_daya_baca": (
            satuan_daya_baca
        ),

        "interval_skala_verifikasi": None,

        "kelas": (
            kelas
            if kelas
            else None
        ),

        "status": "aktif",
    }

    # =====================================================
    # ID MASTER UTTP DARI RIWAYAT / EDIT
    # =====================================================
    uttp_id_lama = rincian.get(
        "_uttp_id"
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

    # =====================================================
    # ADA ID UTTP LAMA
    # =====================================================
    if uttp_id_lama is not None:

        response_uttp_lama = (
            supabase
            .table("uttp")
            .select(
                "id, perusahaan_id"
            )
            .eq(
                "id",
                uttp_id_lama
            )
            .limit(1)
            .execute()
        )

        if response_uttp_lama.data:

            uttp_lama = (
                response_uttp_lama.data[0]
            )

            perusahaan_id_lama = (
                uttp_lama.get(
                    "perusahaan_id"
                )
            )

            try:
                perusahaan_id_lama = (
                    int(
                        perusahaan_id_lama
                    )
                    if perusahaan_id_lama
                    is not None
                    else None
                )

            except (
                TypeError,
                ValueError
            ):
                perusahaan_id_lama = None

            # =============================================
            # PERUSAHAAN SAMA
            # → UPDATE MASTER UTTP YANG SAMA
            # =============================================
            if (
                perusahaan_id_lama
                == perusahaan_id
            ):

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
                    .execute()
                )

                if not response_update.data:
                    raise RuntimeError(
                        "Master UTTP lama "
                        "gagal diperbarui."
                    )

                return (
                    uttp_id_lama,
                    False
                )

            # =============================================
            # PERUSAHAAN BERUBAH
            # → BUAT MASTER BARU
            # =============================================
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
                    "Master UTTP baru gagal "
                    "dibuat untuk perusahaan baru."
                )

            return (
                response_insert.data[0]["id"],
                True
            )

        # =================================================
        # ID LAMA SUDAH TIDAK ADA
        # → BUAT MASTER BARU
        # =================================================
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
                "Master UTTP baru gagal dibuat."
            )

        return (
            response_insert.data[0]["id"],
            True
        )

    # =====================================================
    # RINCIAN BARU
    #
    # Tidak ada _uttp_id.
    # SELALU buat master UTTP baru.
    #
    # Nomor seri TIDAK dipakai untuk mencari master.
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
        "jenis_layanan": str(
            data.get("jenis_layanan", "UTTP Umum")
            or "UTTP Umum"
        ).strip(),


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

                "data_detail": {
                    "nama_pemilik": str(
                        rincian.get("nama_pemilik", "") or ""
                    ).strip(),
                    "alamat": str(
                        rincian.get("alamat", "") or ""
                    ).strip(),
                    "perusahaan_id": rincian.get("perusahaan_id"),
                    "cerapan": (
                        rincian.get("data_cerapan") or {}
                    ),
                },


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
            "uttp_id, urutan, hasil, data_detail"

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
            
            data_detail_riwayat = relasi.get(
                "data_detail"
            ) or {}

            if not isinstance(data_detail_riwayat, dict):
                data_detail_riwayat = {}

            cerapan_riwayat = (
                data_detail_riwayat.get("cerapan") or {}
            )

            if not isinstance(cerapan_riwayat, dict):
                cerapan_riwayat = {}

            # dukungan data lama: cerapan tersimpan langsung tanpa pembungkus
            if (
                not cerapan_riwayat
                and data_detail_riwayat.get("visual")
            ):
                cerapan_riwayat = data_detail_riwayat

            nama_pemilik_riwayat = str(
                data_detail_riwayat.get("nama_pemilik", "") or ""
            ).strip()

            alamat_pemilik_riwayat = str(
                data_detail_riwayat.get("alamat", "") or ""
            ).strip()

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
                "nama_pemilik": nama_pemilik_riwayat,
                "alamat": alamat_pemilik_riwayat,
                "data_cerapan": cerapan_riwayat,

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

def ambil_nomor_order_berikutnya(tanggal, supabase=None):
    """Nomor order berikutnya dari tabel `pengujian` (bulan + tahun sama)."""
    if supabase is None:
        supabase = get_supabase_uttp()

    if isinstance(tanggal, str):
        tanggal = parse_tanggal_uttp(tanggal)

    romawi = bulan_ke_romawi(tanggal.month)
    tahun = tanggal.year

    response = (
        supabase
        .table("pengujian")
        .select("nomor_order")
        .ilike("nomor_order", f"%/SCD/{romawi}/{tahun}")
        .execute()
    )

    pola = re.compile(
        rf"^\s*(\d{{1,6}})\s*/\s*SCD\s*/\s*{romawi}\s*/\s*{tahun}\s*$",
        re.IGNORECASE,
    )

    tertinggi = 0
    for baris in (response.data or []):
        cocok = pola.match(str(baris.get("nomor_order") or "").strip())
        if cocok:
            tertinggi = max(tertinggi, int(cocok.group(1)))

    return f"{tertinggi + 1:04d}/SCD/{romawi}/{tahun}"


def ambil_nomor_sertifikat_berikutnya(tanggal, supabase=None):
    """Nomor sertifikat berikutnya. Format: 500.2.3.15/NNNN/BID-K/ROMAWI/TAHUN"""
    if supabase is None:
        supabase = get_supabase_uttp()

    if isinstance(tanggal, str):
        tanggal = parse_tanggal_uttp(tanggal)

    romawi = bulan_ke_romawi(tanggal.month)
    tahun = tanggal.year

    response = (
        supabase
        .table("pengujian")
        .select("nomor_sertifikat")
        .ilike("nomor_sertifikat", f"%/BID-K/{romawi}/{tahun}")
        .execute()
    )

    pola = re.compile(
        rf"^\s*500\.2\.3\.15\s*/\s*(\d{{1,6}})\s*/\s*BID-K"
        rf"\s*/\s*{romawi}\s*/\s*{tahun}\s*$",
        re.IGNORECASE,
    )

    tertinggi = 0
    for baris in (response.data or []):
        cocok = pola.match(str(baris.get("nomor_sertifikat") or "").strip())
        if cocok:
            tertinggi = max(tertinggi, int(cocok.group(1)))

    return f"500.2.3.15/{tertinggi + 1:04d}/BID-K/{romawi}/{tahun}"


def nomor_sertifikat_sudah_dipakai(nomor, kecuali_id=None, supabase=None):
    """True kalau `nomor` sudah dipakai baris LAIN di tabel pengujian."""
    if supabase is None:
        supabase = get_supabase_uttp()

    nomor = str(nomor or "").strip()
    if not nomor:
        return False

    res = (
        supabase
        .table("pengujian")
        .select("id")
        .eq("nomor_sertifikat", nomor)
        .limit(1)
        .execute()
    )

    data = res.data or []
    if not data:
        return False

    if kecuali_id is not None and str(data[0]["id"]) == str(kecuali_id):
        return False

    return True


def ambil_nomor_tersimpan(id_baris, kolom, supabase=None):
    """Ambil nomor_order / nomor_sertifikat dari baris pengujian tertentu."""
    if not id_baris:
        return ""

    if supabase is None:
        supabase = get_supabase_uttp()

    try:
        res = (
            supabase
            .table("pengujian")
            .select(kolom)
            .eq("id", id_baris)
            .limit(1)
            .execute()
        )
    except Exception:
        return ""

    if not res.data:
        return ""

    return str(res.data[0].get(kolom) or "").strip()


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
    """
    Ambil daftar perusahaan dari Supabase (tabel: perusahaan).
    Fallback: file Excel lokal data/data_perusahaan.xlsx.
    Hasil di-cache di session_state agar tidak query tiap rerun.
    """
    cache_key = "uttp_cache_data_perusahaan"

    cache = st.session_state.get(cache_key)

    if isinstance(cache, pd.DataFrame) and not cache.empty:
        return cache

    df = pd.DataFrame(
        columns=["Nama Perusahaan", "Alamat"]
    )

    try:
        supabase = get_supabase_uttp()

        response = (
            supabase
            .table("perusahaan")
            .select("nama_perusahaan, alamat")
            .limit(5000)
            .execute()
        )

        rows = response.data or []

        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(
                columns={
                    "nama_perusahaan": "Nama Perusahaan",
                    "alamat": "Alamat",
                }
            )

    except Exception as exc:
        st.warning(
            f"Gagal mengambil data perusahaan dari Supabase: {exc}"
        )

    if df.empty:
        try:
            df_excel = _read_excel(
                PROJECT_ROOT / "data" / "data_perusahaan.xlsx"
            )

            if df_excel is not None:
                df = df_excel

        except Exception as exc:
            st.warning(
                f"Data perusahaan tidak dapat dibaca: {exc}"
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

    df = df[df["Nama Perusahaan"] != ""]

    df["_panjang_alamat"] = df["Alamat"].str.len()

    df = (
        df.sort_values("_panjang_alamat", ascending=False)
        .drop_duplicates(subset=["Nama Perusahaan"], keep="first")
        .drop(columns=["_panjang_alamat"])
        .sort_values("Nama Perusahaan")
        .reset_index(drop=True)
    )

    if not df.empty:
        st.session_state[cache_key] = df

    return df

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
    """
    Dipanggil saat Tanggal Pengujian / Tanggal Sertifikat berubah.
    - Nomor Order      : bulan Romawi = bulan Tanggal Pengujian
    - Nomor Sertifikat : bulan Romawi = bulan Tanggal Sertifikat
    Nomor yang sudah diedit manual TIDAK ditimpa.
    """
    tanggal_uji = st.session_state.get(
        "uttp_tanggal_pengujian",
        date.today()
    )

    tanggal_sert = st.session_state.get(
        "uttp_tanggal_sertifikat",
        tanggal_uji
    )

    nomor_order_skrg = str(
        st.session_state.get("uttp_nomor_order", "") or ""
    ).strip()

    if (not nomor_order_skrg) or nomor_order_skrg.startswith("0000/SCD/"):
        # ---- pakai ulang kalau perusahaan + tanggal pengujian sama ----
        nama_perusahaan_form = _ambil_nama_perusahaan_form_uttp()

        nomor_order_lama = cari_nomor_order_sebelumnya_uttp(
            nama_perusahaan_form,
            tanggal_uji,
        )

        if nomor_order_lama:
            st.session_state["uttp_nomor_order"] = nomor_order_lama
        else:
            try:
                st.session_state["uttp_nomor_order"] = (
                    ambil_nomor_order_berikutnya(tanggal_uji)
                )
            except Exception:
                pass


    nomor_sert_skrg = str(
        st.session_state.get("uttp_nomor_sertifikat", "") or ""
    ).strip()

    if (
        (not nomor_sert_skrg)
        or nomor_sert_skrg.startswith("500.2.3.15/0000/BID-K/")
    ):
        try:
            st.session_state["uttp_nomor_sertifikat"] = (
                ambil_nomor_sertifikat_berikutnya(tanggal_sert)
            )
        except Exception:
            pass

    
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
                "nomor_sertifikat"
            )
            or generate_nomor_sertifikat(
                tanggal_sertifikat_saved
            )
        ),

        
        "uttp_nomor_order": (
            saved.get(
                "nomor_order"
            )
            or generate_nomor_order(
                tanggal_pengujian_saved
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

    saved = st.session_state.get(
        "uttp_saved_data",
        {}
    ) or {}

    # =====================================================
    # IDENTITAS PEMILIK
    # =====================================================
    st.session_state[
        "uttp_nama_perusahaan"
    ] = str(
        saved.get(
            "pemilik",
            ""
        )
        or ""
    ).strip()

    st.session_state[
        "uttp_alamat_input"
    ] = str(
        saved.get(
            "alamat",
            ""
        )
        or ""
    ).strip()

    # =====================================================
    # DATA SERTIFIKAT
    # =====================================================
    st.session_state[
        "uttp_jenis_pengujian"
    ] = saved.get(
        "jenis_pengujian",
        "Tera Ulang"
    )

    st.session_state[
        "uttp_lokasi_pengujian"
    ] = saved.get(
        "lokasi_pengujian",
        "Perusahaan"
    )

    st.session_state[
        "uttp_tanggal_pengujian"
    ] = parse_tanggal_uttp(
        saved.get(
            "tanggal_pengujian"
        )
    )

    st.session_state[
        "uttp_tanggal_sertifikat"
    ] = parse_tanggal_uttp(
        saved.get(
            "tanggal_sertifikat"
        )
    )

    tanggal_pengujian_restore = (
        parse_tanggal_uttp(
            saved.get(
                "tanggal_pengujian"
            )
        )
    )
    
    st.session_state[
        "uttp_nomor_sertifikat"
    ] = str(
        saved.get(
            "nomor_sertifikat"
        )
        or generate_nomor_sertifikat(
            parse_tanggal_uttp(
                saved.get("tanggal_sertifikat")
            )
        )

    ).strip()
    
    st.session_state[
        "uttp_nomor_order"
    ] = str(
        saved.get(
            "nomor_order"
        )
        or generate_nomor_order(
            tanggal_pengujian_restore
        )
    ).strip()

    # =====================================================
    # ALAT STANDAR
    # =====================================================
    st.session_state[
        "uttp_alat_standar"
    ] = (
        saved.get(
            "alat_standar",
            []
        )
        or []
    )

    # =====================================================
    # JUMLAH RINCIAN
    # =====================================================
    daftar_rincian = (
        saved.get(
            "daftar_rincian_uttp",
            []
        )
        or []
    )

    st.session_state[
        "uttp_jumlah_rincian_alat"
    ] = max(
        1,
        len(
            daftar_rincian
        )
    )

    # =====================================================
    # PENERA
    # =====================================================
    st.session_state[
        "uttp_jumlah_penera"
    ] = int(
        saved.get(
            "jumlah_penera",
            1
        )
        or 1
    )

    st.session_state[
        "uttp_penera_1"
    ] = str(
        saved.get(
            "penera_1",
            ""
        )
        or ""
    ).strip()

    st.session_state[
        "uttp_nip_penera_1"
    ] = str(
        saved.get(
            "nip_penera_1",
            ""
        )
        or ""
    ).strip()

    st.session_state[
        "uttp_golongan_penera_1"
    ] = str(
        saved.get(
            "golongan_penera_1",
            ""
        )
        or ""
    ).strip()

    st.session_state[
        "uttp_penera_2"
    ] = str(
        saved.get(
            "penera_2",
            ""
        )
        or ""
    ).strip()

    st.session_state[
        "uttp_nip_penera_2"
    ] = str(
        saved.get(
            "nip_penera_2",
            ""
        )
        or ""
    ).strip()

    st.session_state[
        "uttp_golongan_penera_2"
    ] = str(
        saved.get(
            "golongan_penera_2",
            ""
        )
        or ""
    ).strip()

    # =====================================================
    # MODE INPUT
    # =====================================================
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
        "jenis_layanan": (
            detail.get(
                "jenis_layanan",
                "UTTP Umum"
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
        "jenis_layanan": (
            detail.get(
                "jenis_layanan",
                "UTTP Umum"
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
                "📐 Cerapan",
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

        # =====================================================
        # IDENTITAS PEMILIK (LEBAR PENUH)
        # =====================================================
        with st.container():
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

        # =====================================================
        # NOMOR DOKUMEN
        # =====================================================
        st.markdown("---")
        st.subheader("📊 Nomor Dokumen")

        col_tgl1, col_tgl2 = st.columns(2)

        with col_tgl1:
            tanggal_pengujian = st.date_input(
                "Tanggal Pengujian",
                key="uttp_tanggal_pengujian",
                on_change=update_nomor_dokumen_uttp,
            )

        with col_tgl2:
            tanggal_sertifikat = st.date_input(
                "Tanggal Sertifikat",
                key="uttp_tanggal_sertifikat",
                on_change=update_nomor_dokumen_uttp,
            )

        if st.button(
            "🔢 Generate Nomor Order & Sertifikat",
            type="primary",
            use_container_width=True,
            key="uttp_btn_generate_nomor",
        ):
            # ---- NOMOR ORDER: pakai ulang kalau perusahaan + tanggal sama ----
            nama_perusahaan_form = _ambil_nama_perusahaan_form_uttp()

            if not nama_perusahaan_form:
                st.warning(
                    "Nama perusahaan belum terbaca dari form, jadi nomor "
                    "order tidak bisa dipakai ulang."
                )

            nomor_order_dipakai_ulang = cari_nomor_order_sebelumnya_uttp(
                nama_perusahaan_form,
                tanggal_pengujian,
            )

            if nomor_order_dipakai_ulang:
                st.session_state["uttp_nomor_order"] = (
                    nomor_order_dipakai_ulang
                )
                st.info(
                    f"♻️ Nomor order {nomor_order_dipakai_ulang} dipakai ulang "
                    "(nama perusahaan dan tanggal pengujian sama)."
                )
            else:
                try:
                    st.session_state["uttp_nomor_order"] = (
                        ambil_nomor_order_berikutnya(tanggal_pengujian)
                    )
                except Exception as exc_order:
                    st.error(f"❌ Gagal membuat nomor order: {exc_order}")

            # ---- NOMOR SERTIFIKAT: tetap seperti semula ----
            try:
                st.session_state["uttp_nomor_sertifikat"] = (
                    ambil_nomor_sertifikat_berikutnya(tanggal_sertifikat)
                )
            except Exception as exc_sert:
                st.error(f"❌ Gagal membuat nomor sertifikat: {exc_sert}")


        col_nomor1, col_nomor2 = st.columns(2)

        with col_nomor1:
            nomor_order = st.text_input(
                "Nomor Order",
                key="uttp_nomor_order",
            )

        with col_nomor2:
            nomor_sertifikat = st.text_input(
                "Nomor Sertifikat",
                key="uttp_nomor_sertifikat",
            )

        # =====================================================
        # DATA PENGUJIAN
        # =====================================================
        st.markdown("---")
        st.subheader("🗂️ Data Pengujian")
        opsi_jenis_layanan = [
            "UTTP Umum",
            "UTTP Pangkalan GAS LPG",
        ]

        if (
            st.session_state.get("uttp_jenis_layanan")
            not in opsi_jenis_layanan
        ):
            jenis_layanan_tersimpan = str(
                st.session_state.uttp_saved_data.get(
                    "jenis_layanan",
                    "",
                ) or ""
            ).strip()

            st.session_state["uttp_jenis_layanan"] = (
                jenis_layanan_tersimpan
                if jenis_layanan_tersimpan in opsi_jenis_layanan
                else "UTTP Umum"
            )

        jenis_layanan_uttp = st.selectbox(
            "Jenis Layanan",
            options=opsi_jenis_layanan,
            key="uttp_jenis_layanan",
            help=(
                "UTTP Umum: pengujian alat seperti biasa. "
                "UTTP Pangkalan GAS LPG: setiap rincian memiliki "
                "nama pemilik dan alamat sendiri."
            ),
        )

        is_lpg = (jenis_layanan_uttp == "UTTP Pangkalan GAS LPG")

        col_jenis, col_lokasi = st.columns(2)

        with col_jenis:
            jenis_pengujian = st.selectbox(
                "Jenis Pengujian",
                options=[
                    "Tera",
                    "Tera Ulang"
                ],
                key="uttp_jenis_pengujian",
            )

        with col_lokasi:
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


        opsi_nama_alat = [
            "Timbangan Elektronik",
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
                        "Timbangan Pegas",
                        "Timbangan Bobot Ingsut",
                        "Timbangan Sentisimal",
                        "Timbangan Meja",
                        "Timbangan Neraca Obat",
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
                    nama_alat_rincian_kecil = str(
                        nama_alat_rincian or ""
                    ).strip().lower()

                    daya_baca_wajib_kosong = (
                        nama_alat_rincian_kecil
                        in {
                            "timbangan meja",
                            "timbangan neraca obat",
                        }
                    )

                    kunci_tanpa_daya_baca = (
                        f"uttp_tanpa_daya_baca_{index}"
                    )

                    if daya_baca_wajib_kosong:
                        st.session_state[kunci_tanpa_daya_baca] = True
                        st.session_state[
                            f"uttp_rincian_daya_baca_{index}"
                        ] = ""

                    tanpa_daya_baca = st.checkbox(
                        "Tidak ada daya baca",
                        value=bool(
                            data_lama.get(
                                "tanpa_daya_baca",
                                False
                            )
                        ),
                        disabled=daya_baca_wajib_kosong,
                        key=kunci_tanpa_daya_baca,
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

                    opsi_kelas = ["I", "II", "III", "IIII"]

                    signature_baru = (
                        str(kapasitas_rincian),
                        str(daya_baca_rincian),
                        str(satuan_rincian),
                    )

                    kelas_tersimpan = str(
                        data_lama.get("kelas", "") or ""
                    ).strip()

                    kelas_sekarang = st.session_state.get(kelas_key)

                    # Pastikan kunci kelas SELALU terisi sebelum selectbox
                    # dibuat, supaya tidak jatuh ke opsi pertama (kelas I).
                    if kelas_sekarang not in opsi_kelas:
                        if kelas_tersimpan in opsi_kelas:
                            st.session_state[kelas_key] = kelas_tersimpan
                        elif kelas_otomatis:
                            st.session_state[kelas_key] = kelas_otomatis
                        else:
                            st.session_state[kelas_key] = "III"

                        st.session_state[kelas_signature_key] = (
                            signature_baru
                        )

                    # Rekomendasi otomatis hanya jalan kalau
                    # Max / e / satuan berubah.
                    elif (
                        st.session_state.get(kelas_signature_key)
                        != signature_baru
                    ):
                        st.session_state[kelas_key] = (
                            kelas_otomatis
                            if kelas_otomatis
                            else "III"
                        )

                        st.session_state[kelas_signature_key] = (
                            signature_baru
                        )

                    kelas_rincian = st.selectbox(
                        "Kelas Timbangan",
                        options=opsi_kelas,
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
                
                nama_pemilik_lpg = ""
                alamat_lpg = ""

                if is_lpg:
                    st.markdown("**Pemilik Pangkalan LPG**")

                    df_pemilik_lpg = load_data_perusahaan()

                    daftar_pemilik_lpg = []
                    peta_alamat_lpg = {}

                    if not df_pemilik_lpg.empty:
                        for _, baris_pemilik in df_pemilik_lpg.iterrows():
                            nama_baris = str(
                                baris_pemilik.get(
                                    "Nama Perusahaan", ""
                                ) or ""
                            ).strip()

                            alamat_baris = str(
                                baris_pemilik.get("Alamat", "") or ""
                            ).strip()

                            if nama_baris:
                                daftar_pemilik_lpg.append(nama_baris)
                                peta_alamat_lpg[nama_baris] = alamat_baris

                    opsi_pemilik_lpg = [
                        "➕ Tambah pemilik baru"
                    ] + daftar_pemilik_lpg

                    pemilik_tersimpan = str(
                        data_lama.get("nama_pemilik", "") or ""
                    ).strip()

                    alamat_tersimpan = str(
                        data_lama.get("alamat", "") or ""
                    ).strip()

                    kunci_pilih_pemilik = (
                        f"uttp_rincian_pemilik_pilih_{index}"
                    )

                    if kunci_pilih_pemilik not in st.session_state:
                        st.session_state[kunci_pilih_pemilik] = (
                            pemilik_tersimpan
                            if pemilik_tersimpan in daftar_pemilik_lpg
                            else "➕ Tambah pemilik baru"
                        )

                    pilihan_pemilik_lpg = st.selectbox(
                        "Nama Pemilik",
                        options=opsi_pemilik_lpg,
                        key=kunci_pilih_pemilik,
                        help=(
                            "Pilih pemilik yang sudah terdaftar, atau "
                            "'Tambah pemilik baru' untuk mengisi manual. "
                            "Data baru otomatis disimpan ke tabel "
                            "perusahaan saat klik Simpan Data."
                        ),
                    )

                    kolom_lpg1, kolom_lpg2 = st.columns(2)

                    if pilihan_pemilik_lpg == "➕ Tambah pemilik baru":
                        with kolom_lpg1:
                            nama_pemilik_lpg = st.text_input(
                                "Nama Pemilik Baru",
                                value=pemilik_tersimpan,
                                key=f"uttp_rincian_pemilik_{index}",
                            )

                        with kolom_lpg2:
                            alamat_lpg = st.text_input(
                                "Alamat Pemilik",
                                value=alamat_tersimpan,
                                key=f"uttp_rincian_alamat_{index}",
                            )
                    else:
                        nama_pemilik_lpg = pilihan_pemilik_lpg

                        alamat_master = peta_alamat_lpg.get(
                            pilihan_pemilik_lpg, ""
                        )

                        kunci_nama_tampil = (
                            f"uttp_rincian_pemilik_tampil_{index}"
                        )
                        st.session_state[kunci_nama_tampil] = (
                            nama_pemilik_lpg
                        )

                        kunci_alamat_pemilik = (
                            f"uttp_rincian_alamat_{index}"
                        )
                        kunci_pemilik_terakhir = (
                            f"uttp_rincian_pemilik_terakhir_{index}"
                        )

                        if (
                            st.session_state.get(
                                kunci_pemilik_terakhir
                            )
                            != nama_pemilik_lpg
                        ):
                            st.session_state[
                                kunci_pemilik_terakhir
                            ] = nama_pemilik_lpg

                            st.session_state[
                                kunci_alamat_pemilik
                            ] = (
                                alamat_master or alamat_tersimpan
                            )

                        with kolom_lpg1:
                            st.text_input(
                                "Nama Pemilik",
                                value=nama_pemilik_lpg,
                                disabled=True,
                                key=kunci_nama_tampil,
                            )

                        with kolom_lpg2:
                            alamat_lpg = st.text_input(
                                "Alamat Pemilik",
                                key=kunci_alamat_pemilik,
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
                    "nama_pemilik": nama_pemilik_lpg,
                    "alamat": alamat_lpg,


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
            
                # ---- simpan pemilik LPG ke master perusahaan ----
                if is_lpg:
                    try:
                        supabase_pemilik_lpg = get_supabase_uttp()
                        ada_pemilik_diproses = False

                        for rincian_lpg in daftar_rincian_uttp:
                            nama_pemilik_simpan = str(
                                rincian_lpg.get(
                                    "nama_pemilik", ""
                                ) or ""
                            ).strip()

                            alamat_pemilik_simpan = str(
                                rincian_lpg.get("alamat", "") or ""
                            ).strip()

                            if (
                                nama_pemilik_simpan
                                and alamat_pemilik_simpan
                            ):
                                perusahaan_id_lpg = (
                                    simpan_atau_update_perusahaan_uttp(
                                        supabase_pemilik_lpg,
                                        nama_pemilik_simpan,
                                        alamat_pemilik_simpan,
                                    )
                                )

                                rincian_lpg["perusahaan_id"] = (
                                    perusahaan_id_lpg
                                )
                                ada_pemilik_diproses = True

                        if ada_pemilik_diproses:
                            st.session_state.pop(
                                "uttp_cache_data_perusahaan",
                                None,
                            )
                    except Exception as exc_pemilik_lpg:
                        st.warning(
                            "Gagal menyimpan pemilik ke master "
                            "perusahaan: "
                            f"{exc_pemilik_lpg}"
                        )
            
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
                "jenis_layanan": (
                    jenis_layanan_uttp
                ),
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

                # =====================================================
                # 1) SIMPAN DULU KE DATABASE
                # =====================================================
                hasil_simpan = (
                    simpan_pengujian_uttp_umum_ke_supabase(
                        data
                    )
                )

                pengujian_rows = (
                    hasil_simpan.get("pengujian", [])
                    or []
                )

                pengujian_id_hasil = None

                if pengujian_rows:
                    pengujian_id_hasil = (
                        pengujian_rows[0].get("id")
                    )

                # =====================================================
                # 2) BARU BUAT PDF
                # =====================================================
                generate_sertifikat_uttp_pdf(
                    data,
                    str(output_file),
                )

                st.session_state[
                    "uttp_sudah_disimpan_db"
                ] = True

                st.session_state[
                    "uttp_last_pengujian_id"
                ] = pengujian_id_hasil

                st.session_state.uttp_generated_files[
                    "sertifikat"
                ] = str(output_file)

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

            except ValueError as exc:
                # mis. nomor sertifikat sudah dipakai
                st.error(
                    "❌ DITOLAK — "
                    f"{exc} Tidak ada nomor sertifikat dobel "
                    "di database. Dokumen tidak dibuat."
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

        # =====================================================
        # CERAPAN (SAMPLE)
        # =====================================================
        st.markdown("---")
        st.subheader("📝 Cerapan")

        daftar_rincian_cerapan = list(
            data.get("daftar_rincian_uttp", []) or []
        )

        opsi_cerapan = []

        for nomor_rincian, rincian_cerapan in enumerate(
            daftar_rincian_cerapan
        ):
            if not (rincian_cerapan.get("data_cerapan") or {}):
                continue

            label_cerapan = (
                f"{nomor_rincian + 1}. "
                f"{rincian_cerapan.get('nama_alat', 'Timbangan')}"
                f" - {rincian_cerapan.get('merek', '')}"
                f" - {rincian_cerapan.get('nomor_seri', '')}"
            )
            opsi_cerapan.append((nomor_rincian, label_cerapan))

        if not opsi_cerapan:
            st.info(
                "Belum ada alat yang ditandai sample cerapan. "
                "Buka mode input data, centang 'Jadikan sample cerapan' "
                "pada alat yang akan dicerap, lalu simpan."
            )
        else:
            peta_label_ke_index = {
                label: index_alat
                for index_alat, label in opsi_cerapan
            }

            pilihan_label = st.multiselect(
                "Alat yang dicerapkan (sample)",
                options=[label for _, label in opsi_cerapan],
                default=[label for _, label in opsi_cerapan],
                key="uttp_cerapan_pilih_alat",
            )

            pilihan_index = [
                peta_label_ke_index[label]
                for label in pilihan_label
            ]

            if st.button(
                "🖨️ Buat Cerapan",
                use_container_width=True,
                key="uttp_buat_cerapan",
            ):
                try:
                    output_cerapan_dir = OUTPUT_DIR
                    output_cerapan_dir.mkdir(
                        parents=True, exist_ok=True
                    )

                    nama_dasar = format_nama_file_uttp(
                        data, "CERAPAN"
                    )
                    if nama_dasar.endswith(".pdf"):
                        nama_dasar = nama_dasar[:-4]

                    for index_alat in pilihan_index:
                        rincian_terpilih = (
                            daftar_rincian_cerapan[index_alat]
                        )

                        data_alat_cerapan = rakit_data_cerapan_uttp(
                            data, rincian_terpilih
                        )

                        nama_file_cerapan = (
                            f"{nama_dasar}_Alat{index_alat + 1}.pdf"
                        )
                        path_cerapan = (
                            output_cerapan_dir / nama_file_cerapan
                        )
                        st.write(
                            "CEK PEMILIK RINCIAN:",
                            rincian_terpilih.get("nama_pemilik"),
                            "|",
                            rincian_terpilih.get("alamat"),
                        )

                        generate_cerapan_pdf(
                            data_alat_cerapan,
                            str(path_cerapan),
                        )

                        st.session_state.uttp_generated_files[
                            f"cerapan_{index_alat}"
                        ] = str(path_cerapan)

                        st.success(
                            f"✅ Cerapan alat {index_alat + 1} "
                            f"({rincian_terpilih.get('nama_alat', '')}) "
                            "berhasil dibuat."
                        )

                except Exception as exc:
                    st.error(f"❌ Error membuat cerapan: {exc}")
                    st.code(traceback.format_exc())

            if pilihan_index:
                kolom_download_cerapan = st.columns(
                    len(pilihan_index)
                )

                for urutan, index_alat in enumerate(pilihan_index):
                    with kolom_download_cerapan[urutan]:
                        path_cerapan = (
                            st.session_state.uttp_generated_files.get(
                                f"cerapan_{index_alat}"
                            )
                        )

                        if path_cerapan and Path(path_cerapan).exists():
                            with open(path_cerapan, "rb") as berkas:
                                st.download_button(
                                    label=(
                                        f"⬇️ Cerapan {index_alat + 1}"
                                    ),
                                    data=berkas.read(),
                                    file_name=Path(path_cerapan).name,
                                    mime="application/pdf",
                                    use_container_width=True,
                                    key=(
                                        "uttp_download_cerapan_"
                                        f"{index_alat}"
                                    ),
                                )
                        else:
                            st.caption(
                                f"Cerapan {index_alat + 1} belum dibuat."
                            )

    elif mode == "📐 Cerapan":
        st.header("📐 Cerapan UTTP")

        data_cerapan_hal = st.session_state.get(
            "uttp_saved_data",
            {},
        ) or {}

        daftar_rincian_hal = list(
            data_cerapan_hal.get("daftar_rincian_uttp", []) or []
        )

        # =====================================================
        # PARAMETER PENGUJIAN (berlaku untuk semua sample)
        # =====================================================
        st.subheader("Parameter Pengujian")

        kolom_param1, kolom_param2 = st.columns(2)

        with kolom_param1:
            lokasi_options = ["Perusahaan", "Dalam Kantor"]

            lokasi_tersimpan = str(
                data_cerapan_hal.get("lokasi", "") or ""
            ).strip()

            if lokasi_tersimpan not in lokasi_options:
                if lokasi_tersimpan:
                    st.session_state["uttp_cerapan_lokasi"] = "Perusahaan"
                    st.session_state["uttp_cerapan_lokasi_beda"] = True
                    st.session_state[
                        "uttp_cerapan_lokasi_nama"
                    ] = lokasi_tersimpan
                else:
                    st.session_state["uttp_cerapan_lokasi"] = "Perusahaan"

            lokasi_pilihan = st.selectbox(
                "Lokasi Pengujian",
                options=lokasi_options,
                key="uttp_cerapan_lokasi",
                help="Pilih lokasi pelaksanaan pengujian.",
            )

            lokasi_final = lokasi_pilihan

            if lokasi_pilihan == "Perusahaan":
                beda_pemilik = st.checkbox(
                    "Nama perusahaan lokasi berbeda dengan identitas pemilik",
                    key="uttp_cerapan_lokasi_beda",
                )

                if beda_pemilik:
                    nama_lokasi = st.text_input(
                        "Nama perusahaan lokasi",
                        key="uttp_cerapan_lokasi_nama",
                    )
                    if str(nama_lokasi or "").strip():
                        lokasi_final = str(nama_lokasi).strip()

        with kolom_param2:
            opsi_metode = [
                "Beban Substitusi Tunggal",
                "Perbandingan Langsung",
            ]

            metode_tersimpan = str(
                data_cerapan_hal.get("metode", "") or ""
            ).strip()

            if (
                metode_tersimpan in opsi_metode
                and "uttp_cerapan_metode" not in st.session_state
            ):
                st.session_state["uttp_cerapan_metode"] = metode_tersimpan

            metode_pilihan = st.selectbox(
                "Metode Pengujian",
                options=opsi_metode,
                key="uttp_cerapan_metode",
                help="Pilih metode pengujian yang digunakan.",
            )

            opsi_standar = ["M2", "M1", "F2", "F1"]

            standar_tersimpan = (
                data_cerapan_hal.get("alat_standar", []) or []
            )

            if "uttp_cerapan_standar" not in st.session_state:
                st.session_state["uttp_cerapan_standar"] = [
                    item
                    for item in standar_tersimpan
                    if item in opsi_standar
                ]

            standar_pilihan = st.multiselect(
                "Kelas Anak Timbangan Standar",
                options=opsi_standar,
                key="uttp_cerapan_standar",
                placeholder="Pilih satu atau lebih kelas standar",
            )

        data_cerapan_hal["lokasi"] = lokasi_final
        data_cerapan_hal["metode"] = metode_pilihan
        data_cerapan_hal["alat_standar"] = list(standar_pilihan)
        data_cerapan_hal["at_standar"] = ", ".join(standar_pilihan)

        st.session_state.uttp_saved_data = data_cerapan_hal

        st.markdown("---")

        
        if not daftar_rincian_hal:
            st.info(
                "Belum ada data pengujian. Isi dulu di menu "
                "'📝 Input Data Pengujian', lalu simpan."
            )
        else:
            opsi_alat_hal = []

            for index_alat, rincian_alat in enumerate(daftar_rincian_hal):
                label_alat_hal = (
                    f"{index_alat + 1}. "
                    f"{rincian_alat.get('nama_alat', 'Timbangan')}"
                    f" - {rincian_alat.get('merek', '')}"
                    f" - {rincian_alat.get('nomor_seri', '')}"
                )
                opsi_alat_hal.append((index_alat, label_alat_hal))

            peta_label_hal = {
                label: index_alat
                for index_alat, label in opsi_alat_hal
            }

            default_alat_hal = [
                label
                for index_alat, label in opsi_alat_hal
                if (
                    daftar_rincian_hal[index_alat].get("data_cerapan")
                    or {}
                )
            ]

            pilihan_label_hal = st.multiselect(
                "Pilih alat yang dicerapkan (sample)",
                options=[label for _, label in opsi_alat_hal],
                default=default_alat_hal,
                key="uttp_cerapan_pilih_alat_hal",
            )

            pilihan_index_hal = [
                peta_label_hal[label]
                for label in pilihan_label_hal
            ]

            st.caption(
                "Contoh: dari 10 timbangan, pilih 1, 2, 3 alat saja "
                "sebagai sample cerapan."
            )

            hasil_input_cerapan = {}

            for index_alat in pilihan_index_hal:
                rincian_alat = daftar_rincian_hal[index_alat]

                st.markdown("---")
                st.subheader(
                    f"Alat {index_alat + 1}: "
                    f"{rincian_alat.get('nama_alat', 'Timbangan')}"
                )
                st.caption(
                    f"Merek: {rincian_alat.get('merek', '-')} | "
                    f"Model: {rincian_alat.get('model_tipe', '-')} | "
                    f"No. Seri: {rincian_alat.get('nomor_seri', '-')} | "
                    f"Kapasitas: {rincian_alat.get('kapasitas', '-')} | "
                    f"Daya Baca: {rincian_alat.get('daya_baca', '-')} | "
                    f"Kelas: {rincian_alat.get('kelas', '-')}"
                )


                _, isi_cerapan_alat = render_input_cerapan_uttp(
                    index=index_alat,
                    nama_alat=rincian_alat.get("nama_alat", ""),
                    data_lama=rincian_alat,
                    tampilkan_checkbox=False,
                )

                hasil_input_cerapan[index_alat] = isi_cerapan_alat

            if st.button(
                "💾 Simpan Data Cerapan",
                type="primary",
                use_container_width=True,
                key="uttp_simpan_cerapan",
            ):
                for index_alat, isi_cerapan_alat in (
                    hasil_input_cerapan.items()
                ):
                    daftar_rincian_hal[index_alat][
                        "sample_cerapan"
                    ] = True
                    daftar_rincian_hal[index_alat][
                        "data_cerapan"
                    ] = isi_cerapan_alat

                data_cerapan_hal[
                    "daftar_rincian_uttp"
                ] = daftar_rincian_hal

                st.session_state.uttp_saved_data = data_cerapan_hal

                st.success(
                    "✅ Data cerapan disimpan. Lanjut ke menu "
                    "'📄 Preview & Generate Data' untuk membuat PDF."
                )

    
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

                col_edit, col_baru = st.columns(2)
                
                # =========================================================
                # EDIT PENGUJIAN
                # =========================================================
                with col_edit:
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
                
                
                # =========================================================
                # PENGUJIAN BARU DARI RIWAYAT
                # =========================================================
                with col_baru:
                    if st.button(
                        "➕ Pengujian Baru",
                        use_container_width=True,
                        key=(
                            "uttp_baru_riwayat_"
                            f"{pengujian.get('id')}"
                        ),
                    ):
                        gunakan_riwayat_untuk_pengujian_baru_uttp(
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
