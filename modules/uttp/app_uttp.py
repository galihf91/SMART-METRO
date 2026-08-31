import re
import traceback
from datetime import date
from pathlib import Path

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

    # Ubah ke kg agar sama dengan logika aplikasi Timbangan
    max_kg = max_gram / 1000
    e_kg = e_gram / 1000

    n = max_kg / e_kg

    # ==========================================
    # KAPASITAS > 75 KG
    # HANYA KELAS III ATAU IIII
    # ==========================================
    if max_kg > 75:

        # Kelas IIII
        if (
            0.005 <= e_kg <= 0.05
            and 100 <= n <= 2000
        ):
            return "IIII", n

        # Kelas III
        if (
            (
                0.0001 <= e_kg <= 0.002
                and 100 <= n <= 10000
            )
            or
            (
                e_kg >= 0.005
                and 500 <= n <= 10000
            )
        ):
            return "III", n

        # Kapasitas > 75 kg tidak masuk kelas I/II
        if 10000 < n <= 100000:
            return "III", n

        return "", n

    # ==========================================
    # KAPASITAS <= 75 KG
    # ==========================================

    # Kelas I
    if (
        e_kg >= 0.000001
        and n >= 50000
    ):
        return "I", n

    # Kelas III
    if (
        (
            0.0001 <= e_kg <= 0.002
            and 100 <= n <= 10000
        )
        or
        (
            e_kg >= 0.005
            and 500 <= n <= 10000
        )
    ):
        return "III", n

    # Kelas II
    # hanya jika n > 10000
    if (
        0.000001 <= e_kg <= 0.00005
        and 10000 < n <= 100000
    ):
        return "II", n

    if (
        e_kg >= 0.0001
        and 10000 < n <= 100000
    ):
        return "II", n

    # Kelas IIII
    if (
        0.005 <= e_kg <= 0.05
        and 100 <= n <= 2000
    ):
        return "IIII", n

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
        "uttp_generated_files": {},

        "uttp_data_penera": load_data_penera(),
        "uttp_data_perusahaan": (
            load_data_perusahaan()
        ),

        "uttp_nama_perusahaan": saved.get(
            "pemilik",
            ""
        ),
        
        "uttp_alamat_input": saved.get(
            "alamat",
            ""
        ),

        "uttp_manual_perusahaan": False,

        "uttp_mode": (
            "📝 Input Data Pengujian"
        ),

        "uttp_jumlah_rincian_alat": max(
            1,
            len(rincian_saved)
        ),

        "uttp_jenis_pengujian": saved.get(
            "jenis_pengujian",
            "Tera Ulang"
        ),
        "uttp_jenis_pengujian": saved.get(
            "jenis_pengujian",
            "Tera Ulang"
        ),
        "uttp_tanggal_pengujian": (
            tanggal_pengujian_saved
        ),

        "uttp_tanggal_sertifikat": (
            tanggal_sertifikat_saved
        ),

        "uttp_nomor_sertifikat": saved.get(
            "nomor_sertifikat",
            generate_nomor_sertifikat(
                tanggal_pengujian_saved
            )
        ),

        "uttp_nomor_order": saved.get(
            "nomor_order",
            generate_nomor_order(
                tanggal_pengujian_saved
            )
        ),

        "uttp_alat_standar": saved.get(
            "alat_standar",
            []
        ),

        "uttp_jumlah_penera": saved.get(
            "jumlah_penera",
            1
        ),

        "uttp_penera_1": saved.get(
            "penera_1",
            ""
        ),

        "uttp_penera_2": saved.get(
            "penera_2",
            ""
        ),
        "uttp_nip_penera_1": saved.get(
            "nip_penera_1",
            ""
        ),

        "uttp_golongan_penera_1": saved.get(
            "golongan_penera_1",
            ""
        ),

        "uttp_nip_penera_2": saved.get(
            "nip_penera_2",
            ""
        ),

        "uttp_golongan_penera_2": saved.get(
            "golongan_penera_2",
            ""
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

        if not daya_baca:
            errors.append(
                f"Rincian {index}: daya baca belum diisi."
            )

        if not kelas:
            errors.append(
                f"Rincian {index}: kelas timbangan tidak valid."
            )

    return errors
    


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
            ],
            key="uttp_mode",
        )

    if mode == "📝 Input Data Pengujian":
        st.header("Masukkan Data Pengujian UTTP")

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
                    daya_baca_rincian = st.text_input(
                        f"Daya Baca ({satuan_rincian})",
                        value=str(
                            data_lama.get(
                                "daya_baca",
                                ""
                            )
                        ),
                        placeholder="Contoh: 0,005",
                        key=f"uttp_rincian_daya_baca_{index}",
                    )

                    # ==============================
                    # KELAS
                    # ==============================
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
                    "no": index + 1,
                    "nama_alat": nama_alat_rincian,
                    "merek": merek_rincian,
                    "model_tipe": model_tipe_rincian,
                    "nomor_seri": nomor_seri_rincian,
                    "kapasitas": kapasitas_rincian,
                    "daya_baca": daya_baca_rincian,
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
            if simpan:
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

                st.session_state.uttp_saved_data = {
                    ...
                }
            st.session_state.uttp_saved_data = {
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

            st.success("✅ Data berhasil disimpan!")
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

        if st.button(
            "🎫 Generate Sertifikat",
            type="primary",
            use_container_width=True,
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

                st.session_state.uttp_generated_files[
                    "sertifikat"
                ] = str(output_file)

                st.success(
                    "✅ Sertifikat berhasil dibuat!"
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


if __name__ == "__main__":
    run()
