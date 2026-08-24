import traceback
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from modules.meter_air.cerapan_meter_air_generator import generate_cerapan_meter_air_pdf
from modules.meter_air.sertifikat_meter_air_generator import generate_sertifikat_meter_air_pdf
from modules.meter_air.form_peminjaman_ctt_meter_air_generator import (
    generate_form_peminjaman_ctt_meter_air_pdf
)


MODE_INPUT = "📝 Input Data Pengujian"
MODE_GENERATE = "📄 Generate Dokumen"
OUTPUT_DIR = Path("output/meter_air")
DEFAULT_BKD = [4.0, 4.0, 10.0]
BEJANA_PRESET = {
    "100 L": {
        "merek": "ANKATAMA",
        "tipe_no_seri": "Basah / ATM 01324 / 2022",
        "volume_nominal": "100 L",
        "koefisien_muai": "0,0000477 / °C",
        "sb": 0.005,
        "waktu_tetesan": "30 s",
    },
    "5000 L": {
        "merek": "ANKATAMA",
        "tipe_no_seri": "Basah / ATM 01321",
        "volume_nominal": "5000 L",
        "koefisien_muai": "0,0000477 / °C",
        "sb": 0.0,
        "waktu_tetesan": "30 s",
    },
}


def tambah_5_tahun(tanggal):
    try:
        return date(
            tanggal.year + 5,
            tanggal.month,
            tanggal.day,
        )
    except ValueError:
        return date(
            tanggal.year + 5,
            tanggal.month,
            28,
        )

def bulan_singkat_id(tanggal):
    bulan = {
        1: "JAN", 2: "FEB", 3: "MAR", 4: "APR",
        5: "MEI", 6: "JUN", 7: "JUL", 8: "AGS",
        9: "SEP", 10: "OKT", 11: "NOV", 12: "DES",
    }
    return bulan.get(tanggal.month, "")


def bulan_ke_romawi(bulan):
    return ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"][bulan - 1]


def slug_filename(text):
    text = str(text).replace("/", "_").replace("\\", "_").replace(" ", "_")
    return "".join(ch for ch in text if ch.isalnum() or ch in ["_", "-", "."])


def parse_date_value(value, default_value=None):
    if default_value is None:
        default_value = date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d").date()
        except ValueError:
            pass
    return default_value


def format_tanggal_indonesia(value):
    t = parse_date_value(value)
    bulan = [
        "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember",
    ]
    return f"{t.day} {bulan[t.month - 1]} {t.year}"


def generate_nomor_sertifikat(tanggal):
    t = parse_date_value(tanggal)
    return f"500.2.3.15/0000/BID-K/{bulan_ke_romawi(t.month)}/{t.year}"


def generate_nomor_order(tanggal):
    t = parse_date_value(tanggal)
    return f"0000/SCD/{bulan_ke_romawi(t.month)}/{t.year}"


def format_nama_file_dokumen(data, jenis_dokumen="Sertifikat"):
    nama_perusahaan = data.get("pemilik") or "PERUSAHAAN"
    nama_penera = data.get("nama_penera") or "PENERA"
    tanggal = parse_date_value(data.get("tanggal_pengujian", date.today()))
    tanggal_file = f"{tanggal.day:02d}_{bulan_singkat_id(tanggal)}"
    return slug_filename(
        f"{nama_perusahaan}_METER_AIR_{jenis_dokumen}_{nama_penera}_{tanggal_file}"
    )


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


@st.cache_data
def load_data_perusahaan():
    path = Path("data/data_perusahaan.xlsx")
    if not path.exists():
        return pd.DataFrame(columns=["Nama Perusahaan", "Alamat"])
    try:
        df = pd.read_excel(path, engine="openpyxl")
        for col in ["Nama Perusahaan", "Alamat"]:
            if col not in df.columns:
                df[col] = ""
        df["Nama Perusahaan"] = df["Nama Perusahaan"].fillna("").astype(str).str.strip()
        df["Alamat"] = df["Alamat"].fillna("").astype(str).str.strip()
        df = df[df["Nama Perusahaan"] != ""].copy()
        df["_panjang"] = df["Alamat"].str.len()
        df = (
            df.sort_values("_panjang", ascending=False)
            .drop_duplicates("Nama Perusahaan", keep="first")
            .drop(columns=["_panjang"])
            .sort_values("Nama Perusahaan")
            .reset_index(drop=True)
        )
        return df
    except Exception as exc:
        st.warning(f"Data perusahaan tidak dapat dibaca: {exc}")
        return pd.DataFrame(columns=["Nama Perusahaan", "Alamat"])


@st.cache_data
def load_data_penera():
    path = Path("data/data_penera.xlsx")
    if not path.exists():
        return pd.DataFrame(columns=["Nama", "NIP", "Golongan"])
    try:
        df = pd.read_excel(path, engine="openpyxl")
        for col in ["Nama", "NIP", "Golongan"]:
            if col not in df.columns:
                df[col] = ""
        df["Nama"] = df["Nama"].fillna("").astype(str).str.strip()
        df["Golongan"] = df["Golongan"].fillna("").astype(str).str.strip()

        def fmt_nip(v):
            if pd.isna(v):
                return ""
            if isinstance(v, float) and v.is_integer():
                return str(int(v))
            s = str(v).strip()
            return s[:-2] if s.endswith(".0") else s

        df["NIP"] = df["NIP"].apply(fmt_nip)
        return df[df["Nama"] != ""].reset_index(drop=True)
    except Exception as exc:
        st.warning(f"Data penera tidak dapat dibaca: {exc}")
        return pd.DataFrame(columns=["Nama", "NIP", "Golongan"])


def update_perusahaan_terpilih_ma():
    selected = str(st.session_state.get("ma_perusahaan_select", "")).strip()
    df = st.session_state.get("ma_data_perusahaan")
    if not selected or df is None or df.empty:
        return
    row = df[df["Nama Perusahaan"].astype(str).str.strip() == selected]
    if row.empty:
        return
    st.session_state.ma_nama_perusahaan = selected
    st.session_state.ma_alamat_input = str(row.iloc[0].get("Alamat", "") or "").strip()
    st.session_state.ma_input_manual_perusahaan = False


def update_penera_ma():
    selected = str(st.session_state.get("ma_penera_select", "")).strip()
    df = st.session_state.get("ma_data_penera")
    if not selected or df is None or df.empty:
        st.session_state.ma_nama_penera = ""
        st.session_state.ma_nip_penera = ""
        st.session_state.ma_golongan_penera = ""
        return
    row = df[df["Nama"].astype(str).str.strip() == selected]
    if row.empty:
        return
    r = row.iloc[0]
    st.session_state.ma_nama_penera = selected
    st.session_state.ma_nip_penera = str(r.get("NIP", "")).strip()
    st.session_state.ma_golongan_penera = str(r.get("Golongan", "")).strip()


def update_nomor_dokumen_ma():
    tanggal = st.session_state.get(
        "ma_tanggal_pengujian",
        date.today()
    )

    st.session_state.ma_nomor_sertifikat = (
        generate_nomor_sertifikat(tanggal)
    )

    st.session_state.ma_nomor_order = (
        generate_nomor_order(tanggal)
    )

    st.session_state.ma_masa_berlaku = (
        tambah_5_tahun(tanggal)
    )


def kembali_ke_input_ma():
    st.session_state.ma_mode = MODE_INPUT


def reset_form_meter_air():
    for key in list(st.session_state.keys()):
        if key.startswith("ma_"):
            st.session_state.pop(key, None)


def init_meter_air_state():
    if "ma_saved_data" not in st.session_state:
        st.session_state.ma_saved_data = {}

    saved = st.session_state.ma_saved_data
    t_uji = parse_date_value(saved.get("tanggal_pengujian", date.today()))
    t_ttd = parse_date_value(saved.get("tanggal_sertifikat", date.today()))
    try:
        default_masa = date(t_uji.year + 5, t_uji.month, t_uji.day)
    except ValueError:
        default_masa = date(t_uji.year + 5, t_uji.month, 28)
    masa = parse_date_value(saved.get("masa_berlaku", default_masa), default_masa)

    defaults = {
        "ma_generated_files": {},
        "ma_data_perusahaan": load_data_perusahaan(),
        "ma_data_penera": load_data_penera(),
        "ma_mode": MODE_INPUT,
        "ma_nama_perusahaan": saved.get("pemilik", ""),
        "ma_alamat_input": saved.get("alamat", ""),
        "ma_input_manual_perusahaan": False,
        "ma_jenis_pengujian": saved.get("jenis_pengujian", "Tera Ulang"),
        "ma_lokasi_pengujian": saved.get("lokasi_pengujian", "Perusahaan"),
        "ma_tanggal_pengujian": t_uji,
        "ma_tanggal_sertifikat": t_ttd,
        "ma_masa_berlaku": masa,
        "ma_nomor_sertifikat": saved.get("nomor_sertifikat", generate_nomor_sertifikat(t_uji)),
        "ma_nomor_order": saved.get("nomor_order", generate_nomor_order(t_uji)),
        "ma_penera_select": saved.get("nama_penera", ""),
        "ma_nama_penera": saved.get("nama_penera", ""),
        "ma_nip_penera": saved.get("nip_penera", ""),
        "ma_golongan_penera": saved.get("golongan_penera", ""),
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def validasi_data_meter_air(data):
    wajib = {
        "pemilik": "Nama pemilik/perusahaan belum diisi.",
        "alamat": "Alamat belum diisi.",
        "merek": "Merek meter air belum diisi.",
        "model_tipe": "Model/tipe meter air belum diisi.",
        "nomor_seri": "Nomor seri meter air belum diisi.",
        "kapasitas": "Kapasitas meter air belum diisi.",
        "diameter": "Diameter meter air belum diisi.",
        "kelas": "Kelas meter air belum diisi.",
        "nama_penera": "Penera belum dipilih.",
        "bejana_merek": "Merek bejana ukur belum diisi.",
        "bejana_tipe": "Tipe bejana ukur belum diisi.",
        "bejana_nomor_seri": "Nomor seri bejana ukur belum diisi.",
    }
    errors = []
    for key, pesan in wajib.items():
        if not str(data.get(key, "")).strip():
            errors.append(pesan)
    return errors


def get_saved_test(saved, idx):
    items = saved.get("hasil_pengujian", [])
    if isinstance(items, list) and len(items) > idx and isinstance(items[idx], dict):
        return items[idx]
    return {}


def run():
    init_meter_air_state()

    st.title("💧 Pengujian Meter Air")

    col_nav1, col_nav2 = st.columns(2)
    with col_nav1:
        if st.button("← Kembali ke Home", use_container_width=True, key="ma_nav_home"):
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
        st.header("📋 Menu Navigasi")
        mode = st.radio("Pilih Mode:", [MODE_INPUT, MODE_GENERATE], key="ma_mode")

    if mode == MODE_INPUT:
        st.header("Masukkan Data Pengujian Meter Air")
        saved = st.session_state.ma_saved_data

        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("Identitas Pemilik")
            df_perusahaan = st.session_state.get("ma_data_perusahaan")
            if df_perusahaan is not None and not df_perusahaan.empty:
                options = df_perusahaan["Nama Perusahaan"].dropna().astype(str).str.strip().tolist()
                if "ma_perusahaan_select" not in st.session_state:
                    nama_lama = str(st.session_state.get("ma_nama_perusahaan", "")).strip()
                    st.session_state.ma_perusahaan_select = nama_lama if nama_lama in options else ""
                    if nama_lama and nama_lama not in options:
                        st.session_state.ma_input_manual_perusahaan = True
                st.selectbox(
                    "Cari & Pilih Nama Perusahaan",
                    options=[""] + options,
                    placeholder="Ketik atau pilih perusahaan...",
                    key="ma_perusahaan_select",
                    on_change=update_perusahaan_terpilih_ma,
                )
                st.text_area("Alamat", height=90, key="ma_alamat_input")
                st.checkbox("Input manual nama perusahaan", key="ma_input_manual_perusahaan")
                if st.session_state.ma_input_manual_perusahaan:
                    st.text_input("Nama Pemilik / Perusahaan", key="ma_nama_perusahaan")
            else:
                st.info("Data perusahaan tidak ditemukan. Silakan input manual.")
                st.text_input("Nama Pemilik / Perusahaan", key="ma_nama_perusahaan")
                st.text_area("Alamat", height=90, key="ma_alamat_input")

            pemilik = str(st.session_state.get("ma_nama_perusahaan", "")).strip()
            alamat = str(st.session_state.get("ma_alamat_input", "")).strip()

        with col2:
            st.subheader("Data Meter Air")
            merek = st.text_input("Merek", value=str(saved.get("merek", "")), key="ma_merek")
            model_tipe = st.text_input("Model / Tipe", value=str(saved.get("model_tipe", "")), key="ma_model_tipe")
            nomor_seri = st.text_input("Nomor Seri", value=str(saved.get("nomor_seri", "")), key="ma_nomor_seri")
            col_kapasitas, col_satuan_kapasitas = st.columns(
                [3, 1]
            )

            with col_kapasitas:
                kapasitas = st.text_input(
                    "Kapasitas",
                    value=str(
                        saved.get(
                            "kapasitas",
                            ""
                        )
                    ),
                    placeholder="Contoh: 3,5",
                    key="ma_kapasitas"
                )

            with col_satuan_kapasitas:
                st.text_input(
                    "Satuan",
                    value="m³/h",
                    disabled=True,
                    key="ma_satuan_kapasitas"
                )


            col_diameter, col_satuan_diameter = st.columns(
                [3, 1]
            )

            with col_diameter:
                diameter = st.text_input(
                    "Diameter",
                    value=str(
                        saved.get(
                            "diameter",
                            ""
                        )
                    ),
                    placeholder="Contoh: 25",
                    key="ma_diameter"
                )

            with col_satuan_diameter:
                st.text_input(
                    "Satuan ",
                    value="mm",
                    disabled=True,
                    key="ma_satuan_diameter"
                )


            kelas = st.text_input(
                "Kelas",
                value=str(
                    saved.get(
                        "kelas",
                        "II"
                    )
                ),
                placeholder="Contoh: II",
                key="ma_kelas"
            )

        with col3:
            st.subheader("Data Pengujian")
            jenis_pengujian = st.selectbox("Jenis Pengujian", ["Tera", "Tera Ulang"], key="ma_jenis_pengujian")
            lokasi_pengujian = st.selectbox("Lokasi Pengujian", ["Dalam Kantor", "Perusahaan"], key="ma_lokasi_pengujian")
            tanggal_pengujian = st.date_input("Tanggal Pengujian", key="ma_tanggal_pengujian", on_change=update_nomor_dokumen_ma)
            masa_berlaku = st.date_input(
                "Masa Berlaku",
                key="ma_masa_berlaku",
                disabled=True,
                help="Masa berlaku otomatis 5 tahun sejak tanggal pengujian."
            )
            tanggal_sertifikat = st.date_input("Tanggal Tanda Tangan", key="ma_tanggal_sertifikat")
            nomor_order = st.text_input("Nomor Order", key="ma_nomor_order")
            nomor_sertifikat = st.text_input("Nomor Sertifikat", key="ma_nomor_sertifikat")

        st.markdown("---")
        col4, col5, col6 = st.columns(3)

        with col4:
            st.subheader("Data Bejana Ukur Standar")

            volume_nominal_pilihan = st.selectbox(
                "Volume Nominal",
                options=[
                    "100 L",
                    "5000 L",
                ],
                index=(
                    1
                    if str(
                        saved.get(
                            "bejana_volume_nominal",
                            "100 L"
                        )
                    ) == "5000 L"
                    else 0
                ),
                key="ma_bejana_volume_pilihan"
            )

            data_bejana = BEJANA_PRESET[
                volume_nominal_pilihan
            ]

            bejana_volume_nominal = (
                data_bejana["volume_nominal"]
            )

            bejana_merek = (
                data_bejana["merek"]
            )

            bejana_tipe_no_seri = (
                data_bejana["tipe_no_seri"]
            )

            bejana_koefisien_muai = (
                data_bejana["koefisien_muai"]
            )

            bejana_sb = float(
                data_bejana["sb"]
            )

            bejana_waktu_tetesan = (
                data_bejana["waktu_tetesan"]
            )

            st.text_input(
                "Merek",
                value=bejana_merek,
                disabled=True,
                key=(
                    f"ma_bejana_merek_"
                    f"{volume_nominal_pilihan}"
                )
            )

            st.text_input(
                "Tipe / No. Seri",
                value=bejana_tipe_no_seri,
                disabled=True,
                key=(
                    f"ma_bejana_tipe_seri_"
                    f"{volume_nominal_pilihan}"
                )
            )

            st.text_input(
                "Koefisien Muai Bahan (α)",
                value=bejana_koefisien_muai,
                disabled=True,
                key=(
                    f"ma_bejana_muai_"
                    f"{volume_nominal_pilihan}"
                )
            )

            st.number_input(
                "Kesalahan Penunjukan (SB) (L)",
                value=bejana_sb,
                format="%.3f",
                disabled=True,
                key=(
                    f"ma_bejana_sb_"
                    f"{volume_nominal_pilihan}"
                )
            )

            st.text_input(
                "Waktu Tetesan",
                value=bejana_waktu_tetesan,
                disabled=True,
                key=(
                    f"ma_bejana_tetesan_"
                    f"{volume_nominal_pilihan}"
                )
            )

        with col5:
            st.subheader("Cairan Uji")

            jenis_cairan = st.text_input(
                "Jenis Cairan",
                value="Air",
                disabled=True,
                key="ma_jenis_cairan"
            )

        with col6:
            st.subheader("Data Penera")
            df_penera = st.session_state.get("ma_data_penera")
            if df_penera is not None and not df_penera.empty:
                st.selectbox(
                    "Pilih Nama Penera",
                    options=[""] + df_penera["Nama"].dropna().astype(str).tolist(),
                    key="ma_penera_select",
                    on_change=update_penera_ma,
                )
                st.text_input("Nama Penera", key="ma_nama_penera", disabled=True)
                st.text_input("NIP", key="ma_nip_penera", disabled=True)
                st.text_input("Golongan", key="ma_golongan_penera", disabled=True)
            else:
                st.info("Data penera tidak ditemukan. Silakan input manual.")
                st.text_input("Nama Penera", key="ma_nama_penera")
                st.text_input("NIP", key="ma_nip_penera")
                st.text_input("Golongan", key="ma_golongan_penera")

            nama_penera = str(st.session_state.get("ma_nama_penera", "")).strip()
            nip_penera = str(st.session_state.get("ma_nip_penera", "")).strip()
            golongan_penera = str(st.session_state.get("ma_golongan_penera", "")).strip()

        st.markdown("---")
        st.subheader("📊 Hasil Pengujian Meter Air")
        st.caption(
            "Struktur mengikuti Cerapan Meter Air: 3 kali pengujian. "
            "Vb, Vm2, Vm, Kesalahan Meter Air, dan hasil dihitung otomatis."
        )

        widths = [2.8, 0.8, 1.4, 1.4, 1.4]
        header = st.columns(widths)
        for col, label in zip(header, ["**URAIAN**", "**SATUAN**", "**UJI 1**", "**UJI 2**", "**UJI 3**"]):
            col.write(label)

        def input_three_row(label, satuan, key_prefix, defaults, step=0.01, fmt="%.3f", min_value=None):
            row = st.columns(widths)
            row[0].write(label)
            row[1].write(satuan)
            values = []
            for idx in range(3):
                kwargs = {
                    "label": f"{label} Uji {idx + 1}",
                    "value": float(defaults[idx]),
                    "step": step,
                    "format": fmt,
                    "key": f"{key_prefix}_{idx + 1}",
                    "label_visibility": "collapsed",
                }
                if min_value is not None:
                    kwargs["min_value"] = min_value
                with row[idx + 2]:
                    values.append(st.number_input(**kwargs))
            return values

        saved_tests = [get_saved_test(saved, i) for i in range(3)]

        kecepatan_alir = input_three_row(
            "Kecepatan Alir", "L/h", "ma_kecepatan_alir",
            [safe_float(saved_tests[i].get("kecepatan_alir", 0.0)) for i in range(3)],
            step=1.0, fmt="%.1f", min_value=0.0,
        )

        st.markdown("**Bejana Ukur**")
        vb2 = input_three_row(
            "1. Pembacaan Akhir (Vb2)", "L", "ma_vb2",
            [safe_float(saved_tests[i].get("vb2", 0.0)) for i in range(3)],
        )
        row = st.columns(widths)

        row[0].write(
            "2. Pembacaan Awal (Vb1)"
        )

        row[1].write("L")

        vb1 = [
            0.0,
            0.0,
            0.0,
        ]

        for i in range(3):
            with row[i + 2]:
                st.number_input(
                    f"Vb1 Uji {i + 1}",
                    value=0.0,
                    format="%.3f",
                    disabled=True,
                    key=f"ma_vb1_{i + 1}",
                    label_visibility="collapsed",
                )
        vb = [vb2[i] - vb1[i] for i in range(3)]

        row = st.columns(widths)
        row[0].write("3. Volume yang diukur Vb = Vb2 - Vb1")
        row[1].write("L")
        for i in range(3):
            with row[i + 2]:
                st.number_input(
                    f"Vb Uji {i + 1}", value=float(vb[i]), format="%.3f",
                    disabled=True, key=f"ma_vb_hasil_{i + 1}_{vb[i]:.6f}",
                    label_visibility="collapsed",
                )

        st.markdown("**Meter Air**")
        meter_akhir = input_three_row(
            "4. Pembacaan Akhir", "L", "ma_meter_akhir",
            [safe_float(saved_tests[i].get("pembacaan_akhir_meter", 0.0)) for i in range(3)],
        )
        vm2 = [meter_akhir[i] - bejana_sb for i in range(3)]

        row = st.columns(widths)
        row[0].write("5. Vm2 = Pembacaan Akhir - SB")
        row[1].write("L")
        for i in range(3):
            with row[i + 2]:
                st.number_input(
                    f"Vm2 Uji {i + 1}", value=float(vm2[i]), format="%.3f",
                    disabled=True, key=f"ma_vm2_hasil_{i + 1}_{vm2[i]:.6f}",
                    label_visibility="collapsed",
                )

        vm1 = input_three_row(
            "6. Pembacaan Awal = Vm1", "L", "ma_vm1",
            [safe_float(saved_tests[i].get("vm1", 0.0)) for i in range(3)],
        )
        vm = [vm2[i] - vm1[i] for i in range(3)]

        row = st.columns(widths)
        row[0].write("7. Volume yang diukur Vm = Vm2 - Vm1")
        row[1].write("L")
        for i in range(3):
            with row[i + 2]:
                st.number_input(
                    f"Vm Uji {i + 1}", value=float(vm[i]), format="%.3f",
                    disabled=True, key=f"ma_vm_hasil_{i + 1}_{vm[i]:.6f}",
                    label_visibility="collapsed",
                )

        suhu = input_three_row(
            "8. Suhu (Tm)",
            "°C",
            "ma_suhu",
            [
                25.0,
                25.0,
                25.0,
            ],
            step=0.1,
            fmt="%.1f",
        )
        tekanan = input_three_row(
            "9. Tekanan (Pm)",
            "kPa (kg/cm²)",
            "ma_tekanan",
            [
                2.0,
                2.0,
                2.0,
            ],
            step=0.01,
            fmt="%.2f",
        )

        kesalahan = [((vm[i] - vb[i]) / vb[i] * 100) if vb[i] != 0 else 0.0 for i in range(3)]
        row = st.columns(widths)
        row[0].write("10. Kesalahan Meter Air")
        row[1].write("%")
        for i in range(3):
            with row[i + 2]:
                st.number_input(
                    f"Kesalahan Uji {i + 1}", value=float(kesalahan[i]), format="%.3f",
                    disabled=True, key=f"ma_error_hasil_{i + 1}_{kesalahan[i]:.6f}",
                    label_visibility="collapsed",
                )

        bkd = input_three_row(
            "11. BKD", "%", "ma_bkd",
            [safe_float(saved_tests[i].get("bkd", DEFAULT_BKD[i])) for i in range(3)],
            step=0.1, fmt="%.2f", min_value=0.0,
        )
        ketidaktetapan = input_three_row(
            "12. Ketidaktetapan", "%", "ma_ketidaktetapan",
            [safe_float(saved_tests[i].get("ketidaktetapan", 0.0)) for i in range(3)],
            step=0.01, fmt="%.3f",
        )
        kepekaan = input_three_row(
            "13. Kepekaan (khusus DN = 15 mm)", "L/min", "ma_kepekaan",
            [safe_float(saved_tests[i].get("kepekaan", 0.0)) for i in range(3)],
            step=0.01, fmt="%.3f",
        )

        hasil_pengujian = []

        for i in range(3):

            # Pengujian dianggap sudah memiliki data
            # apabila volume bejana hasil pengukuran tidak nol.
            data_uji_terisi = vb[i] != 0

            if data_uji_terisi:

                # Aturan:
                # |Kesalahan Meter Air| <= BKD  → SAH
                # |Kesalahan Meter Air| > BKD   → TIDAK SAH
                sah = abs(kesalahan[i]) <= bkd[i]

                hasil_baris = (
                    "SAH"
                    if sah
                    else "TIDAK SAH"
                )

            else:
                hasil_baris = "BELUM DIUJI"

            hasil_pengujian.append({
                "no": i + 1,
                "kecepatan_alir": kecepatan_alir[i],

                "vb2": vb2[i],
                "vb1": vb1[i],
                "vb": vb[i],

                "pembacaan_akhir_meter": meter_akhir[i],
                "vm2": vm2[i],
                "vm1": vm1[i],
                "vm": vm[i],

                "suhu": suhu[i],
                "tekanan": tekanan[i],

                "kesalahan_meter_air": kesalahan[i],
                "bkd": bkd[i],

                "ketidaktetapan": ketidaktetapan[i],
                "kepekaan": kepekaan[i],

                "hasil": hasil_baris,
            })


        # =========================================================
        # HASIL AKHIR
        # =========================================================
        semua_sudah_diuji = all(
            item["hasil"] != "BELUM DIUJI"
            for item in hasil_pengujian
        )

        ada_yang_tidak_sah = any(
            item["hasil"] == "TIDAK SAH"
            for item in hasil_pengujian
        )

        if not semua_sudah_diuji:
            hasil_akhir = "BELUM LENGKAP"

        elif ada_yang_tidak_sah:
            hasil_akhir = "BATAL"

        else:
            hasil_akhir = "SAH"
        st.markdown("---")

        if hasil_akhir == "SAH":
            st.success("### Keterangan: SAH")

        elif hasil_akhir == "BATAL":
            st.error("### Keterangan: BATAL")

        else:
            st.info(
                "### Keterangan: BELUM LENGKAP"
            )

        col_simpan, col_reset = st.columns(2)
        with col_simpan:
            simpan_btn = st.button("💾 Simpan Data", type="primary", use_container_width=True, key="ma_simpan_data")
        with col_reset:
            st.button("🔄 Reset Form", use_container_width=True, key="ma_reset_form", on_click=reset_form_meter_air)

        if simpan_btn:
            lokasi_kegiatan = (
                "Unit Metrologi Legal Kabupaten Tangerang"
                if lokasi_pengujian == "Dalam Kantor"
                else pemilik
            )
            bejana_tipe = (
                bejana_tipe_no_seri.split("/")[0].strip()
            )

            bejana_nomor_seri = (
                "/".join(
                    bejana_tipe_no_seri.split("/")[1:]
                ).strip()
            )
            data_meter_air = {
                "nama_alat": "Meter Air",
                "pemilik": pemilik,
                "alamat": alamat,
                "merek": merek,
                "model_tipe": model_tipe,
                "model": model_tipe,
                "nomor_seri": nomor_seri,
                "no_seri": nomor_seri,
                "kapasitas": kapasitas,
                "diameter": diameter,
                "kelas": kelas,
                "masa_berlaku": masa_berlaku.strftime("%Y-%m-%d"),
                "masa_berlaku_indonesia": format_tanggal_indonesia(masa_berlaku),
                "jenis_pengujian": jenis_pengujian,
                "keterangan": jenis_pengujian,
                "lokasi_pengujian": lokasi_pengujian,
                "lokasi_kegiatan": lokasi_kegiatan,
                "tanggal_pengujian": tanggal_pengujian.strftime("%Y-%m-%d"),
                "tanggal": tanggal_pengujian.strftime("%Y-%m-%d"),
                "tanggal_penera": format_tanggal_indonesia(tanggal_pengujian),
                "tanggal_sertifikat": tanggal_sertifikat.strftime("%Y-%m-%d"),
                "nomor_sertifikat": nomor_sertifikat,
                "nomor_order": nomor_order,
                "bejana_merek": bejana_merek,
                "bejana_tipe": bejana_tipe,
                "bejana_nomor_seri": bejana_nomor_seri,
                "bejana_tipe_no_seri": f"{bejana_tipe} / {bejana_nomor_seri}".strip(" /"),
                "bejana_volume_nominal": bejana_volume_nominal,
                "bejana_koefisien_muai": bejana_koefisien_muai,
                "bejana_sb": float(bejana_sb),
                "bejana_waktu_tetesan": bejana_waktu_tetesan,
                "jenis_cairan": jenis_cairan,
                "nama_penera": nama_penera,
                "penera_1": nama_penera,
                "nip_penera": nip_penera,
                "nip_penera_1": nip_penera,
                "golongan_penera": golongan_penera,
                "golongan_penera_1": golongan_penera,
                "hasil_pengujian": hasil_pengujian,
                "hasil_akhir": hasil_akhir,
                "hasil": hasil_akhir,
            }

            errors = validasi_data_meter_air(data_meter_air)
            if errors:
                st.error("Data belum dapat disimpan. Periksa bagian berikut:")
                for pesan in errors:
                    st.write(f"- {pesan}")
                st.stop()

            st.session_state.ma_saved_data = data_meter_air
            st.session_state.ma_generated_files = {}
            st.success("✅ Data Meter Air berhasil disimpan.")
            st.balloons()

    elif mode == MODE_GENERATE:
        st.header("Generate Dokumen Cerapan & Sertifikat")
        data = st.session_state.get("ma_saved_data", {})
        if not data:
            st.warning("⚠️ Silakan input dan simpan data pengujian terlebih dahulu.")
            return

        st.button(
            "✏️ Kembali dan Edit Data",
            use_container_width=True,
            key="ma_kembali_edit",
            on_click=kembali_ke_input_ma,
        )

        st.markdown("---")
        colp1, colp2 = st.columns(2)
        with colp1:
            st.subheader("📋 Preview Data Meter")
            st.write(f"**Pemilik:** {data.get('pemilik', '-')}")
            st.write(f"**Alamat:** {data.get('alamat', '-')}")
            st.write(f"**Merek:** {data.get('merek', '-')}")
            st.write(f"**Model / Tipe:** {data.get('model_tipe', '-')}")
            st.write(f"**Nomor Seri:** {data.get('nomor_seri', '-')}")
            st.write(f"**Kapasitas:** {data.get('kapasitas', '-')}")
            st.write(f"**Diameter:** {data.get('diameter', '-')}")
            st.write(f"**Kelas:** {data.get('kelas', '-')}")
        with colp2:
            st.subheader("📄 Data Dokumen")
            st.write(f"**Nomor Order:** {data.get('nomor_order', '-')}")
            st.write(f"**Nomor Sertifikat:** {data.get('nomor_sertifikat', '-')}")
            st.write(f"**Tanggal Pengujian:** {data.get('tanggal_penera', '-')}")
            st.write(f"**Masa Berlaku:** {data.get('masa_berlaku_indonesia', '-')}")
            st.write(f"**Penera:** {data.get('nama_penera', '-')}")
            st.write(f"**Hasil Akhir:** {data.get('hasil_akhir', '-')}")

        st.markdown("---")
        st.subheader("📊 Hasil Pengujian")
        hasil_df = pd.DataFrame(data.get("hasil_pengujian", []))
        if not hasil_df.empty:
            st.dataframe(hasil_df, use_container_width=True, hide_index=True)

        st.markdown("---")
        if st.button(
            "📦 Generate Cerapan dan Sertifikat",
            type="primary",
            use_container_width=True,
            key="ma_generate_kedua_dokumen",
        ):
            try:
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                cerapan_file = OUTPUT_DIR / f"{format_nama_file_dokumen(data, 'Cerapan')}.pdf"
                generate_cerapan_meter_air_pdf(data, str(cerapan_file))
                st.session_state.ma_generated_files["cerapan"] = str(cerapan_file)

                sertifikat_file = OUTPUT_DIR / f"{format_nama_file_dokumen(data, 'Sertifikat')}.pdf"
                generate_sertifikat_meter_air_pdf(data, str(sertifikat_file))
                st.session_state.ma_generated_files["sertifikat"] = str(sertifikat_file)
                st.success("✅ Cerapan dan sertifikat berhasil dibuat.")
            except Exception as exc:
                st.error(f"❌ Gagal membuat dokumen: {exc}")
                st.code(traceback.format_exc())

        st.markdown("### Dokumen Individual")
        col_doc1, col_doc2, col_doc3 = st.columns(3)

        with col_doc1:
            with st.container(border=True):
                st.markdown("### 📝 Cerapan")
                if st.button("Generate Cerapan", type="primary", use_container_width=True, key="ma_generate_cerapan"):
                    try:
                        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                        filename = OUTPUT_DIR / f"{format_nama_file_dokumen(data, 'Cerapan')}.pdf"
                        generate_cerapan_meter_air_pdf(data, str(filename))
                        st.session_state.ma_generated_files["cerapan"] = str(filename)
                        st.success("✅ Cerapan berhasil dibuat.")
                    except Exception as exc:
                        st.error(f"❌ Gagal membuat cerapan: {exc}")
                        st.code(traceback.format_exc())

                path = st.session_state.ma_generated_files.get("cerapan")
                if path and Path(path).exists():
                    with open(path, "rb") as pdf:
                        st.download_button(
                            "⬇️ Download Cerapan",
                            data=pdf.read(),
                            file_name=Path(path).name,
                            mime="application/pdf",
                            use_container_width=True,
                            key="ma_download_cerapan",
                        )
                else:
                    st.caption("Cerapan belum digenerate.")

        with col_doc2:
            with st.container(border=True):
                st.markdown("### 🎫 Sertifikat")
                if st.button("Generate Sertifikat", type="primary", use_container_width=True, key="ma_generate_sertifikat"):
                    try:
                        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                        filename = OUTPUT_DIR / f"{format_nama_file_dokumen(data, 'Sertifikat')}.pdf"
                        generate_sertifikat_meter_air_pdf(data, str(filename))
                        st.session_state.ma_generated_files["sertifikat"] = str(filename)
                        st.success("✅ Sertifikat berhasil dibuat.")
                    except Exception as exc:
                        st.error(f"❌ Gagal membuat sertifikat: {exc}")
                        st.code(traceback.format_exc())

                path = st.session_state.ma_generated_files.get("sertifikat")
                if path and Path(path).exists():
                    with open(path, "rb") as pdf:
                        st.download_button(
                            "⬇️ Download Sertifikat",
                            data=pdf.read(),
                            file_name=Path(path).name,
                            mime="application/pdf",
                            use_container_width=True,
                            key="ma_download_sertifikat",
                        )
                else:
                    st.caption("Sertifikat belum digenerate.")
                    
        with col_doc3:
            with st.container(border=True):
                st.markdown("### 🔏 Form CTT")

                if st.button(
                    "Generate Form CTT",
                    type="primary",
                    use_container_width=True,
                    key="ma_generate_ctt"
                ):
                    try:
                        OUTPUT_DIR.mkdir(
                            parents=True,
                            exist_ok=True
                        )

                        filename = (
                            OUTPUT_DIR
                            / f"{format_nama_file_dokumen(data, 'Form_CTT')}.pdf"
                        )

                        generate_form_peminjaman_ctt_meter_air_pdf(
                            data,
                            str(filename)
                        )

                        st.session_state.ma_generated_files[
                            "ctt"
                        ] = str(filename)

                        st.success(
                            "✅ Form Peminjaman CTT berhasil dibuat."
                        )

                    except Exception as exc:
                        st.error(
                            f"❌ Gagal membuat Form CTT: {exc}"
                        )

                        st.code(
                            traceback.format_exc()
                        )

                path = st.session_state.ma_generated_files.get(
                    "ctt"
                )

                if path and Path(path).exists():

                    with open(path, "rb") as pdf:

                        st.download_button(
                            "⬇️ Download Form CTT",
                            data=pdf.read(),
                            file_name=Path(path).name,
                            mime="application/pdf",
                            use_container_width=True,
                            key="ma_download_ctt",
                        )

                else:
                    st.caption(
                        "Form CTT belum digenerate."
                    )

    st.markdown("---")
    st.markdown(
        """
        <div style='text-align:center; color:#888; font-size:12px;'>
            <p>Aplikasi Pengujian Meter Air © 2026</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    run()
