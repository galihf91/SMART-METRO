import streamlit as st
import pandas as pd
from datetime import date, datetime
from pathlib import Path

def find_project_root():
    current = Path(__file__).resolve()

    for parent in [current.parent] + list(current.parents):
        if (
            (parent / "app.py").exists()
            or (parent / "modules").exists()
        ):
            return parent

    return current.parent


PROJECT_ROOT = find_project_root()

DATA_DIR = PROJECT_ROOT / "data"

OUTPUT_DIR = (
    PROJECT_ROOT
    / "output"
    / "kwh_meter"
    / "sertifikat"
)
try:
    from modules.kwh_meter.sertifikat_kwh_generator import generate_sertifikat_kwh
except ModuleNotFoundError:
    # Fallback jika file generator diletakkan satu folder dengan halaman ini
    from sertifikat_kwh_generator import generate_sertifikat_kwh


# =========================
# HELPER DATA
# =========================
def bulan_singkat_id(tanggal):
    bulan = {
        1: "JAN", 2: "FEB", 3: "MAR", 4: "APR",
        5: "MEI", 6: "JUN", 7: "JUL", 8: "AGS",
        9: "SEP", 10: "OKT", 11: "NOV", 12: "DES"
    }
    return bulan.get(tanggal.month, "")


def format_nama_file_sertifikat(data):
    pemilik = data.get("pemilik", "KWH")
    penera = data.get("penera_1", "PENERA")
    tanggal = data.get("tanggal_pengujian") or date.today()

    if isinstance(tanggal, str):
        tanggal = datetime.strptime(tanggal, "%Y-%m-%d")

    tanggal_file = f"{tanggal.day:02d} {bulan_singkat_id(tanggal)}"

    nama_file = f"{pemilik}_{penera}_{tanggal_file}"
    return slug_filename(nama_file)
    
def normalize_nip(value):
    if pd.isna(value):
        return ""

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


@st.cache_data
def load_data_penera():
    try:
        df = pd.read_excel(
            DATA_DIR / "data_penera.xlsx",
            engine="openpyxl"
        )

        df.columns = (
            df.columns
            .astype(str)
            .str.strip()
        )

        required_columns = [
            "Nama",
            "NIP",
            "Golongan"
        ]

        if not all(
            col in df.columns
            for col in required_columns
        ):
            return pd.DataFrame(
                columns=required_columns
            )

        # Hapus baris yang nama peneranya kosong
        df = df.dropna(
            subset=["Nama"]
        ).copy()

        df["Nama"] = (
            df["Nama"]
            .astype(str)
            .str.strip()
        )

        # Bersihkan NIP
        df["NIP"] = (
            df["NIP"]
            .apply(normalize_nip)
        )

        # Bersihkan Golongan
        df["Golongan"] = (
            df["Golongan"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        return df

    except Exception as exc:
        st.warning(
            "Data penera tidak dapat dibaca: "
            f"{exc}"
        )

        return pd.DataFrame(
            columns=[
                "Nama",
                "NIP",
                "Golongan"
            ]
        )

def bulan_ke_romawi(bulan):
    romawi = {
        1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI",
        7: "VII", 8: "VIII", 9: "IX", 10: "X", 11: "XI", 12: "XII"
    }
    return romawi.get(int(bulan), "")


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
    # Disesuaikan contoh SKHP kWh Meter: 0046/UAPV/SCD/X/2025
    return f"0000/UAPV/SCD/{bulan_ke_romawi(t.month)}/{t.year}"


def tambah_tahun(tanggal, tahun=10):
    try:
        return tanggal.replace(year=tanggal.year + tahun)
    except ValueError:
        return tanggal.replace(month=2, day=28, year=tanggal.year + tahun)


def slug_filename(text):
    text = str(text).replace("/", "_").replace("\\", "_").replace(" ", "_")
    return "".join(ch for ch in text if ch.isalnum() or ch in ["_", "-", "."])


def parse_tanggal_kwh(value, default=None):
    if default is None:
        default = date.today()

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

    return default


def init_state():
    if "saved_data_kwh" not in st.session_state:
        st.session_state.saved_data_kwh = {}

    saved = st.session_state.saved_data_kwh

    tanggal_pengujian_saved = parse_tanggal_kwh(
        saved.get("tanggal_pengujian")
    )

    tanggal_cetak_saved = parse_tanggal_kwh(
        saved.get("tanggal_cetak")
    )

    berlaku_sampai_saved = parse_tanggal_kwh(
        saved.get(
            "berlaku_sampai",
            tambah_tahun(tanggal_pengujian_saved, 10)
        )
    )

    defaults = {
        "data_penera": load_data_penera(),
        "data_kwh": saved.copy() if saved else {},
        "generated_files_kwh": {},

        "menu_kwh": "📝 Input Data Pengujian",

        "merk_buatan_kwh": saved.get(
            "merk_buatan",
            "SMART / INDONESIA"
        ),

        "jenis_pengujian_kwh": saved.get(
            "jenis_pengujian",
            "Tera"
        ),

        "tanggal_pengujian_kwh": tanggal_pengujian_saved,
        "tanggal_cetak_kwh": tanggal_cetak_saved,
        "berlaku_sampai_kwh": berlaku_sampai_saved,

        "nomor_sertifikat_kwh": saved.get(
            "nomor_sertifikat",
            generate_nomor_sertifikat(
                tanggal_pengujian_saved
            )
        ),

        "nomor_order_kwh": saved.get(
            "nomor_order",
            generate_nomor_order(
                tanggal_pengujian_saved
            )
        ),

        "jumlah_penera_kwh": saved.get(
            "jumlah_penera",
            1
        ),

        "penera_1_kwh_select": saved.get(
            "penera_1",
            ""
        ),

        "penera_2_kwh_select": saved.get(
            "penera_2",
            ""
        ),

        "nip_penera_1_kwh": saved.get(
            "nip_penera_1",
            ""
        ),

        "golongan_penera_1_kwh": saved.get(
            "golongan_penera_1",
            ""
        ),

        "nip_penera_2_kwh": saved.get(
            "nip_penera_2",
            ""
        ),

        "golongan_penera_2_kwh": saved.get(
            "golongan_penera_2",
            ""
        ),
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def update_nomor_dokumen_kwh():
    tanggal = st.session_state.get(
        "tanggal_pengujian_kwh",
        date.today()
    )

    st.session_state[
        "nomor_sertifikat_kwh"
    ] = generate_nomor_sertifikat(tanggal)

    st.session_state[
        "nomor_order_kwh"
    ] = generate_nomor_order(tanggal)

    st.session_state[
        "berlaku_sampai_kwh"
    ] = tambah_tahun(tanggal, 10)


def update_penera_1_kwh():
    selected = str(
        st.session_state.get(
            "penera_1_kwh_select",
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
        st.session_state["nip_penera_1_kwh"] = ""
        st.session_state["golongan_penera_1_kwh"] = ""
        return

    row = df_penera[
        df_penera["Nama"].astype(str) == selected
    ]

    if row.empty:
        return

    data_penera = row.iloc[0]

    st.session_state[
        "nip_penera_1_kwh"
    ] = normalize_nip(
        data_penera.get(
            "NIP",
            ""
        )
    )

    st.session_state["golongan_penera_1_kwh"] = str(
        data_penera.get("Golongan", "")
    ).strip()


def update_penera_2_kwh():
    selected = str(
        st.session_state.get(
            "penera_2_kwh_select",
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
        st.session_state["nip_penera_2_kwh"] = ""
        st.session_state["golongan_penera_2_kwh"] = ""
        return

    row = df_penera[
        df_penera["Nama"].astype(str) == selected
    ]

    if row.empty:
        return

    data_penera = row.iloc[0]

    st.session_state[
        "nip_penera_2_kwh"
    ] = normalize_nip(
        data_penera.get(
            "NIP",
            ""
        )
    )

    st.session_state["golongan_penera_2_kwh"] = str(
        data_penera.get("Golongan", "")
    ).strip()


def kembali_ke_input_kwh():
    st.session_state[
        "menu_kwh"
    ] = "📝 Input Data Pengujian"


def reset_form_kwh():
    for key in list(st.session_state.keys()):
        if (
            key.endswith("_kwh")
            or key.startswith("kwh_")
            or key in {
                "saved_data_kwh",
                "data_kwh",
                "generated_files_kwh",
                "menu_kwh",
            }
        ):
            st.session_state.pop(key, None)

def kembali_edit_kwh():
    st.session_state["menu_kwh"] = (
        "📝 Input Data Pengujian"
    )

# =========================
# KONFIGURASI HALAMAN
def run():
    init_state()

    st.title("⚡ Pengujian kWh Meter")

    col_nav1, col_nav2 = st.columns(2)

    with col_nav1:
        if st.button(
            "← Kembali ke Home",
            use_container_width=True,
            key="kwh_nav_home",
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

    mode = st.sidebar.radio(
        "Menu kWh Meter",
        [
            "📝 Input Data Pengujian",
            "📄 Preview & Generate Data"
        ],
        key="menu_kwh"
    )

    # =========================
    # MODE INPUT
    # =========================
    if mode == "📝 Input Data Pengujian":
        st.header("Masukkan Data Pengujian kWh Meter")

        saved = st.session_state.get("saved_data_kwh", {})

        # ========================
        # DATA UMUM ALAT
        # ========================
        st.subheader("Data Umum Alat")

        col_a1, col_a2, col_a3 = st.columns(3)

        with col_a1:
            nama_alat = st.text_input(
                "Nama Alat",
                value="kWh Meter",
                disabled=True,
                key="nama_alat_kwh",
            )

        with col_a2:
            pilihan_merk_buatan = [
                "SMART / INDONESIA",
                "CANNET / INDONESIA",
            ]

            merk_buatan = st.selectbox(
                "Merk / Buatan",
                options=pilihan_merk_buatan,
                index=pilihan_merk_buatan.index(
                    saved.get("merk_buatan", "SMART / INDONESIA")
                ) if saved.get("merk_buatan", "SMART / INDONESIA") in pilihan_merk_buatan else 0,
                key="merk_buatan_kwh",
            )

        with col_a3:
            model_tipe = st.text_input(
                "Model / Tipe",
                value=saved.get("model_tipe", ""),
                placeholder="Contoh: SMI810V3",
                key="model_tipe_kwh",
            )

        st.markdown("---")

        col1, col2 = st.columns(2)

        # ======================== KOLOM 1: PEMILIK ========================
        with col1:
            st.subheader("Identitas Pemilik / Pengguna")

            saved = st.session_state.get("saved_data_kwh", {})

            if merk_buatan == "SMART / INDONESIA":
                pemilik = "PT. SMART METER INDONESIA"
                alamat = (
                    "Jalan Karet Utara II Zona Industri Mekarjaya No. 07, Kelurahan Mekar Jaya "
                    "Kecamatan Sepatan, Kabupaten Tangerang - Banten"
                )

            elif merk_buatan == "CANNET / INDONESIA":
                pemilik = "PT. CANNET ELEKTRIK INDONESIA"
                alamat = (
                    "Jalan Bhumimas VIII No. 16 Talagasari Kecamatan Cikupa, "
                    "Kabupaten Tangerang - Banten"
                )

            else:
                pemilik = ""
                alamat = ""

            st.text_input(
                "Nama Pemilik / Perusahaan",
                value=pemilik,
                disabled=True
            )

            st.text_area(
                "Alamat",
                value=alamat,
                height=90,
                disabled=True
            )

            if merk_buatan == "SMART / INDONESIA":
                untuk_pengguna = st.text_input(
                    "Untuk / Tujuan Penggunaan",
                    value=saved.get("untuk_pengguna", ""),
                    placeholder="Contoh: PT. PLN (Persero) LHOKSEUMAWE",
                )
            else:
                untuk_pengguna = ""

        # ======================== KOLOM 2: SERTIFIKAT ========================
        with col2:
            st.subheader("Data Sertifikat")

            jenis_pengujian = st.selectbox(
                "Jenis Pengujian",
                options=[
                    "Tera",
                    "Tera Ulang"
                ],
                key="jenis_pengujian_kwh",
            )

            tanggal_pengujian = st.date_input(
                "Tanggal Pengujian",
                key="tanggal_pengujian_kwh",
                on_change=update_nomor_dokumen_kwh,
            )

            tanggal_cetak = st.date_input(
                "Tanggal Cetak / Tanggal Tanda Tangan",
                key="tanggal_cetak_kwh",
            )

            nomor_sertifikat = st.text_input(
                "Nomor Sertifikat",
                key="nomor_sertifikat_kwh",
                placeholder=(
                    "500.2.3.15/0000/BID-K/X/2026"
                ),
            )

            nomor_order = st.text_input(
                "Nomor Order",
                key="nomor_order_kwh",
                placeholder=(
                    "0000/UAPV/SCD/X/2026"
                ),
            )

            # Berlaku sampai selalu dihitung dari tanggal pengujian
            berlaku_sampai = tambah_tahun(
                tanggal_pengujian,
                10
            )
            
            st.date_input(
                "Berlaku Sampai",
                value=berlaku_sampai,
                disabled=True,
                key=(
                    "berlaku_sampai_kwh_"
                    f"{tanggal_pengujian.isoformat()}"
                )
            )

        st.markdown("---")

        # =========================
        # PENERA
        # =========================
        st.subheader("Penera / Pegawai Berhak")

        df_penera = st.session_state.get("data_penera")
        if df_penera is None or df_penera.empty:
            st.warning("Data penera tidak ditemukan. Input manual nama dan NIP.")
            jumlah_penera = 1
            col4, col5, col6 = st.columns(3)
            with col4:
                penera_1 = st.text_input("Nama Penera 1")
            with col5:
                nip_penera_1 = st.text_input("NIP Penera 1")
            with col6:
                golongan_penera_1 = st.text_input("Golongan Penera 1")
            penera_2 = nip_penera_2 = golongan_penera_2 = ""
        else:
            jumlah_penera = st.radio("Jumlah Penera", [1, 2], horizontal=True, key="jumlah_penera_kwh")
            col4, col5 = st.columns(2)

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
                    key="penera_1_kwh_select",
                    on_change=update_penera_1_kwh,
                )

                penera_1 = nama_penera_1

                nip_penera_1 = str(
                    st.session_state.get(
                        "nip_penera_1_kwh",
                        ""
                    )
                ).strip()

                golongan_penera_1 = str(
                    st.session_state.get(
                        "golongan_penera_1_kwh",
                        ""
                    )
                ).strip()

                st.text_input(
                    "NIP Penera 1",
                    key="nip_penera_1_kwh",
                    disabled=True,
                )

                st.text_input(
                    "Golongan Penera 1",
                    key="golongan_penera_1_kwh",
                    disabled=True,
                )

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
                        key="penera_2_kwh_select",
                        on_change=update_penera_2_kwh,
                    )

                    penera_2 = nama_penera_2

                    nip_penera_2 = str(
                        st.session_state.get(
                            "nip_penera_2_kwh",
                            ""
                        )
                    ).strip()

                    golongan_penera_2 = str(
                        st.session_state.get(
                            "golongan_penera_2_kwh",
                            ""
                        )
                    ).strip()

                    st.text_input(
                        "NIP Penera 2",
                        key="nip_penera_2_kwh",
                        disabled=True,
                    )

                    st.text_input(
                        "Golongan Penera 2",
                        key="golongan_penera_2_kwh",
                        disabled=True,
                    )
            else:
                penera_2 = ""
                nip_penera_2 = ""
                golongan_penera_2 = ""

        st.markdown("---")

        # =========================
        # DATA KWH METER
        # =========================
        st.subheader("Data kWh Meter")

        st.markdown(
            """
            <style>
            .kwh-card {
                padding: 18px;
                border-radius: 14px;
                border: 1px solid #e5e7eb;
                background-color: #fafafa;
                margin-bottom: 14px;
            }
            .kwh-title {
                font-size: 18px;
                font-weight: 700;
                margin-bottom: 4px;
            }
            .kwh-help {
                font-size: 13px;
                color: #6b7280;
                margin-bottom: 12px;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            """
            <div class="kwh-card">
                <div class="kwh-title">Data Utama kWh Meter</div>
                <div class="kwh-help">
                    Isi data sesuai kolom pada sertifikat: UNIT, TEGANGAN, ARUS, PHS, KLS, KONST.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        c1, c2, c3 = st.columns(3)

        with c1:
            unit = st.text_input(
                "UNIT",
                value=saved.get("unit", "1"),
                key="kwh_unit"
            )

            tegangan = st.text_input(
                "TEGANGAN",
                value=saved.get("tegangan", "230 V"),
                key="kwh_tegangan"
            )

        with c2:
            arus = st.text_input(
                "ARUS",
                value=saved.get("arus", "5(60) A"),
                key="kwh_arus"
            )

            phs = st.selectbox(
                "PHS",
                ["1", "3"],
                index=0 if saved.get("phs", "1") == "1" else 1,
                key="kwh_phs"
            )

        with c3:
            kelas = st.text_input(
                "KLS",
                value=saved.get("kelas", "1"),
                key="kwh_kls"
            )

            konstanta = st.text_input(
                "KONST",
                value=saved.get("konstanta", "1600 imp/kWh"),
                key="kwh_konst"
            )

        kwh_df = pd.DataFrame(
            [
                {
                    "UNIT": str(unit).strip(),
                    "TEGANGAN": str(tegangan).strip(),
                    "ARUS": str(arus).strip(),
                    "PHS": str(phs).strip(),
                    "KLS": str(kelas).strip(),
                    "KONST": str(konstanta).strip(),
                }
            ],
            columns=["UNIT", "TEGANGAN", "ARUS", "PHS", "KLS", "KONST"]
        )
        
        st.markdown("---")

        data_kwh = {
            "nomor_sertifikat": nomor_sertifikat,
            "nomor_order": nomor_order,
            "tanggal_pengujian": (
                tanggal_pengujian.strftime(
                    "%Y-%m-%d"
                )
            ),

            "tanggal_cetak": (
                tanggal_cetak.strftime(
                    "%Y-%m-%d"
                )
            ),

            "berlaku_sampai": (
                berlaku_sampai.strftime(
                    "%Y-%m-%d"
                )
            ),
            "jenis_pengujian": jenis_pengujian,
            "nama_alat": nama_alat,
            "merk_buatan": merk_buatan,
            "model_tipe": model_tipe,
            "pemilik": pemilik,
            "alamat": alamat,
            "untuk_pengguna": untuk_pengguna,
            "penera_1": penera_1,
            "nip_penera_1": nip_penera_1,
            "golongan_penera_1": golongan_penera_1,
            "penera_2": penera_2,
            "nip_penera_2": nip_penera_2,
            "golongan_penera_2": golongan_penera_2,
            "jumlah_penera": jumlah_penera,
            "jumlah_unit": 1,
            "kwh_meter": kwh_df,
            "unit": unit,
            "tegangan": tegangan,
            "arus": arus,
            "phs": phs,
            "kelas": kelas,
            "konstanta": konstanta,
        }

        col_simpan, col_reset = st.columns(2)

        with col_simpan:
            simpan_kwh = st.button(
                "💾 Simpan Data",
                type="primary",
                use_container_width=True,
                key="simpan_data_kwh",
            )

        with col_reset:
            st.button(
                "🔄 Reset Form",
                use_container_width=True,
                key="reset_form_kwh",
                on_click=reset_form_kwh,
            )

        if simpan_kwh:
            if not str(model_tipe).strip():
                st.error(
                    "Model / Tipe belum diisi."
                )
                st.stop()

            if not str(nomor_sertifikat).strip():
                st.error(
                    "Nomor Sertifikat belum diisi."
                )
                st.stop()

            if not str(nomor_order).strip():
                st.error(
                    "Nomor Order belum diisi."
                )
                st.stop()

            if not str(penera_1).strip():
                st.error(
                    "Penera 1 belum dipilih."
                )
                st.stop()

            if (
                jumlah_penera == 2
                and not str(penera_2).strip()
            ):
                st.error(
                    "Penera 2 belum dipilih."
                )
                st.stop()

            st.session_state.data_kwh = data_kwh
            st.session_state.saved_data_kwh = data_kwh
            st.session_state.generated_files_kwh = {}

            st.success(
                "Data kWh Meter berhasil disimpan. "
                "Silakan buka menu Preview & Generate Data."
            )
            st.balloons()

    # =========================
    # MODE PREVIEW
    # =========================
    elif mode == "📄 Preview & Generate Data":

        st.header("Preview Data kWh Meter")
        col_kembali, col_kosong = st.columns(
            [1.6, 4]
        )

        with col_kembali:
            st.button(
                "← Kembali dan Edit Data",
                use_container_width=True,
                key="kembali_edit_kwh",
                on_click=kembali_ke_input_kwh,
            )
        data_kwh = st.session_state.get("data_kwh", {})

        if not data_kwh:
            st.warning("Belum ada data. Silakan isi data terlebih dahulu di menu Input Data Pengujian.")
            st.stop()

        st.subheader("Data Umum Alat")

        col_a1, col_a2, col_a3 = st.columns(3)

        with col_a1:
            st.write("**Nama Alat:**")
            st.write(data_kwh.get("nama_alat", ""))

        with col_a2:
            st.write("**Merk / Buatan:**")
            st.write(data_kwh.get("merk_buatan", ""))

        with col_a3:
            st.write("**Model / Tipe:**")
            st.write(data_kwh.get("model_tipe", ""))

        st.markdown("---")

        st.subheader("Identitas Pemilik / Pengguna")
        st.write("**Pemilik:**")
        st.write(data_kwh.get("pemilik", ""))
        st.write("**Alamat:**")
        st.write(data_kwh.get("alamat", ""))
        st.write("**Untuk:**")
        st.write(data_kwh.get("untuk_pengguna", ""))

        st.markdown("---")

        st.subheader("Penera / Pegawai Berhak")
        st.write("**Penera 1:**")
        st.write(
            f"{data_kwh.get('penera_1', '')} / "
            f"NIP. {data_kwh.get('nip_penera_1', '')} / "
            f"{data_kwh.get('golongan_penera_1', '')}"
        )

        if data_kwh.get("jumlah_penera") == 2:
            st.write("**Penera 2:**")
            st.write(
                f"{data_kwh.get('penera_2', '')} / "
                f"NIP. {data_kwh.get('nip_penera_2', '')} / "
                f"{data_kwh.get('golongan_penera_2', '')}"
            )

        st.markdown("---")

        st.subheader("Data kWh Meter")
        kwh_df = data_kwh.get("kwh_meter")
        if kwh_df is None or kwh_df.empty:
            st.warning("Data kWh Meter belum diisi.")
        else:
            st.dataframe(kwh_df, use_container_width=True, hide_index=True)

        st.markdown("---")

        hasil_uji_df = data_kwh.get("hasil_uji")
        if hasil_uji_df is not None and not hasil_uji_df.empty:
            st.dataframe(hasil_uji_df, use_container_width=True, hide_index=True)

        st.markdown("---")

        st.subheader("Generate Sertifikat")

        if st.button("📄 Generate Sertifikat kWh Meter", type="primary"):
            try:
                OUTPUT_DIR.mkdir(
                    parents=True,
                    exist_ok=True
                )

                nama_file = format_nama_file_sertifikat(
                    data_kwh
                )

                output_file = OUTPUT_DIR / (
                    f"{nama_file}.pdf"
                )

                generate_sertifikat_kwh(
                    data_kwh,
                    str(output_file)
                )

                st.session_state.generated_files_kwh[
                    "sertifikat"
                ] = str(output_file)

                st.success(
                    f"Sertifikat berhasil dibuat: "
                    f"{output_file.name}"
                )

            except Exception as e:
                st.error(f"Gagal membuat sertifikat: {e}")
                import traceback
                st.code(traceback.format_exc())
                
        sertifikat_path = (
            st.session_state.generated_files_kwh.get(
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
            ) as pdf:
                st.download_button(
                    label=(
                        "⬇️ Download Sertifikat kWh Meter"
                    ),
                    data=pdf.read(),
                    file_name=Path(
                        sertifikat_path
                    ).name,
                    mime="application/pdf",
                    use_container_width=True,
                    key="download_sertifikat_kwh",
                )
        else:
            st.caption(
                "Sertifikat belum digenerate."
            )
