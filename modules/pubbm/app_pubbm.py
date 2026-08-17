import streamlit as st
import pandas as pd
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
    @st.cache_data
    def load_data_bejana():
        try:
            df = pd.read_excel("data/data_bejana.xlsx")
            df.columns = df.columns.str.strip()
            return df
        except FileNotFoundError:
            return pd.DataFrame(
                columns=[
                    "Standar Volume", "Merk", "Tipe", "Nomor Seri",
                    "Kelas", "Kapasitas", "Daya Baca", "Telusuran"
                ]
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
    @st.cache_data
    def load_data_penera():
        try:
            df = pd.read_excel("data/data_penera.xlsx")
            df.columns = df.columns.str.strip()
            return df
        except FileNotFoundError:
            return pd.DataFrame(columns=["Nama", "NIP", "Golongan"])
    
    @st.cache_data
    def load_data_spbu():
        try:
            df = pd.read_csv("data/data_spbu.csv", sep=";", encoding="utf-8-sig")
            df.columns = df.columns.str.strip()
            return df
        except FileNotFoundError:
            return pd.DataFrame(columns=["Nama SPBU", "Alamat"])
    
    # =========================
    # SESSION STATE AWAL
    # =========================
    if "data_penera" not in st.session_state:
        st.session_state.data_penera = load_data_penera()
    
    if "saved_data" not in st.session_state:
        st.session_state.saved_data = {}
    if "pubbm_dispenser" not in st.session_state:
        st.session_state.pubbm_dispenser = pd.DataFrame(
            columns=["No", "Posisi", "Merk", "Tipe", "No. Seri", "Media"]
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
    
        # Identitas SPBU
        st.session_state["nama_perusahaan"] = data.get(
            "pemilik",
            ""
        )
    
        st.session_state["alamat_input_pubbm"] = data.get(
            "alamat",
            ""
        )
    
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
        # Jumlah alat standar
        st.session_state["jumlah_alat_standar_pubbm"] = int(
            data.get(
                "jumlah_alat_standar",
                1
            )
        )
    
        alat_standar = data.get("alat_standar")

        if (
            isinstance(alat_standar, pd.DataFrame)
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

                # Hilangkan .0 jika nomor seri berasal dari Excel
                if nomor_seri.endswith(".0"):
                    nomor_seri = nomor_seri[:-2]

                st.session_state[
                    f"bejana_select_{nomor}"
                ] = (
                    f"{merk} | No Seri : {nomor_seri}"
                )
    
        # Jumlah dispenser
        jumlah_dispenser = int(
            data.get(
                "jumlah_dispenser",
                1
            )
        )
    
        st.session_state[
            "jumlah_dispenser_pubbm"
        ] = max(1, jumlah_dispenser)
    
        # PULIHKAN DATA DISPENSER
        # =========================
        dispenser_df = data.get(
            "dispenser"
        )

        if (
            isinstance(
                dispenser_df,
                pd.DataFrame
            )
            and not dispenser_df.empty
        ):
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

                # =========================
                # IDENTITAS DISPENSER
                # =========================
                baris_pertama = (
                    data_dispenser.iloc[0]
                )

                merk_restore = str(
                    baris_pertama.get(
                        "Merk",
                        ""
                    )
                ).strip()

                tipe_restore = str(
                    baris_pertama.get(
                        "Tipe",
                        ""
                    )
                ).strip()

                no_seri_restore = str(
                    baris_pertama.get(
                        "No. Seri",
                        ""
                    )
                ).strip()

                # Hindari tulisan nan
                if merk_restore.lower() == "nan":
                    merk_restore = ""

                if tipe_restore.lower() == "nan":
                    tipe_restore = ""

                if no_seri_restore.lower() == "nan":
                    no_seri_restore = ""

                # Hilangkan .0 jika nomor seri terbaca sebagai angka Excel
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

                # =========================
                # JUMLAH POSISI
                # =========================
                jumlah_posisi = len(
                    data_dispenser
                )

                st.session_state[
                    f"jumlah_posisi_{nomor_dispenser}"
                ] = max(
                    1,
                    jumlah_posisi
                )

                # =========================
                # POSISI & MEDIA
                # =========================
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
                    ).strip()

                    if (
                        media_tersimpan.lower()
                        == "nan"
                    ):
                        media_tersimpan = ""

                    st.session_state[
                        f"posisi_{nomor_dispenser}_{nomor_posisi}"
                    ] = posisi_restore

                    # Media dipulihkan lewat key sementara.
                    # Nanti di bagian selectbox akan ditentukan:
                    # media standar atau media manual.
                    st.session_state[
                        f"media_restore_{nomor_dispenser}_{nomor_posisi}"
                    ] = media_tersimpan
                    
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
    # =========================
    # SIDEBAR
    # =========================
    mode = st.sidebar.radio(
        "Menu",
        [
            "📝 Input Data Pengujian",
            "📄 Preview & Generate Data",
        ],
        key="mode_pubbm",
    )
    
    
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

            match_spbu = re.search(
                r"SPBU\s*[\d\.-]+",
                pemilik,
                re.IGNORECASE,
            )

            if match_spbu:
                nomor_spbu = match_spbu.group(0).upper()
            else:
                nomor_spbu = ""
    
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
                    col_posisi, col_media = st.columns(
                        [1, 2]
                    )
                
                    key_posisi = f"posisi_{i}_{idx}"
                    key_media_pilihan = f"media_{i}_{idx}"
                    key_media_manual = f"media_manual_{i}_{idx}"
                    key_media_restore = f"media_restore_{i}_{idx}"
                
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
                
                    if media:
                        data_rows.append(
                            {
                                "No": i,
                                "Posisi": posisi.strip(),
                                "Merk": merk.strip(),
                                "Tipe": tipe.strip(),
                                "No. Seri": no_seri.strip(),
                                "Media": media
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
            "Media"
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

            st.session_state.saved_data.update(
                {
                    "tanggal_pengujian": tanggal_pengujian,
                    "tanggal_cetak": tanggal_tanda_tangan,
                    "jenis_pengujian": jenis_pengujian,
                    "nomor_sertifikat": nomor_sertifikat,
                    "nomor_order": nomor_order,
                    "pemilik": pemilik,
                    "alamat": alamat,
                    "jumlah_penera": jumlah_penera,
                    "penera_1": penera_1,
                    "penera_2": penera_2,
                    "jumlah_alat_standar": jumlah_alat_standar,
                    "jumlah_dispenser": jumlah_dispenser,
                }
            )

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
    
        dispenser_df = data_pubbm.get("dispenser")
    
        if dispenser_df is None or dispenser_df.empty:
            st.warning("Data pompa ukur BBM belum diisi.")
        else:
            st.dataframe(
                dispenser_df,
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
                        output_dir_sertifikat = Path(
                            "output/pubbm/sertifikat"
                        )

                        output_dir_sertifikat.mkdir(
                            parents=True,
                            exist_ok=True,
                        )

                        nama_file = format_nama_file_pubbm(
                            data_pubbm
                        )

                        output_file = (
                            output_dir_sertifikat
                            / f"{nama_file}.pdf"
                        )

                        generate_sertifikat_pubbm(
                            data_pubbm,
                            str(output_file),
                        )

                        st.session_state.pubbm_generated_files[
                            "sertifikat"
                        ] = str(output_file)

                        st.success(
                            "✅ Sertifikat berhasil dibuat."
                        )

                    except Exception as exc:
                        st.error(
                            f"Gagal membuat sertifikat: {exc}"
                        )

                        import traceback
                        st.code(traceback.format_exc())

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