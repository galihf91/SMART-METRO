import re
import streamlit as st
import pandas as pd

from datetime import date, datetime
from pathlib import Path
from supabase import create_client
from modules.utils_perusahaan import ambil_kecamatan_dari_alamat

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

# =========================================================
# MODE
# =========================================================
MODE_INPUT = "📝 Input Data Pengujian"
MODE_PREVIEW = "📄 Preview & Generate Data"
MODE_HISTORY = "📚 Riwayat kWh Meter"


# =========================================================
# SUPABASE
# =========================================================
@st.cache_resource
def get_supabase_kwh():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"],
    )
    

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


@st.cache_data(ttl=60)
def load_data_penera():
    try:
        supabase = get_supabase_kwh()

        response = (
            supabase
            .table("penera")
            .select(
                "id, nama, nip, golongan, status"
            )
            .eq(
                "status",
                "aktif",
            )
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

        return (
            df[
                df["Nama"] != ""
            ]
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

@st.cache_data(ttl=60)
def load_data_perusahaan():
    try:
        supabase = get_supabase_kwh()

        response = (
            supabase
            .table("perusahaan")
            .select(
                "id, nama_perusahaan, alamat"
            )
            .order(
                "nama_perusahaan"
            )
            .execute()
        )

        data = response.data or []

        if not data:
            return pd.DataFrame(
                columns=[
                    "ID",
                    "Nama Perusahaan",
                    "Alamat",
                ]
            )

        df = pd.DataFrame(data)

        df = df.rename(
            columns={
                "id": "ID",
                "nama_perusahaan": (
                    "Nama Perusahaan"
                ),
                "alamat": "Alamat",
            }
        )

        for col in [
            "Nama Perusahaan",
            "Alamat",
        ]:
            if col not in df.columns:
                df[col] = ""

            df[col] = (
                df[col]
                .fillna("")
                .astype(str)
                .str.strip()
            )

        return (
            df[
                df["Nama Perusahaan"] != ""
            ]
            .drop_duplicates(
                subset=[
                    "Nama Perusahaan"
                ],
                keep="first",
            )
            .sort_values(
                "Nama Perusahaan"
            )
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
            ]
        )

def update_perusahaan_kwh():

    selected = str(
        st.session_state.get(
            "kwh_perusahaan_select",
            "",
        )
        or ""
    ).strip()

    df = st.session_state.get(
        "data_perusahaan_kwh"
    )

    if (
        not selected
        or df is None
        or df.empty
    ):
        return

    row = df[
        df["Nama Perusahaan"]
        .astype(str)
        .str.strip()
        == selected
    ]

    if row.empty:
        return

    data = row.iloc[0]

    st.session_state[
        "kwh_nama_perusahaan"
    ] = selected

    st.session_state[
        "kwh_alamat_perusahaan"
    ] = str(
        data.get(
            "Alamat",
            "",
        )
        or ""
    ).strip()
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
        "data_penera_kwh": load_data_penera(),
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
        "data_perusahaan_kwh": (
            load_data_perusahaan()
        ),

        "kwh_nama_perusahaan": (
            saved.get(
                "pemilik",
                "",
            )
        ),
        "kwh_perusahaan_select": (
            saved.get(
                "pemilik",
                "",
            )
        ),
        "kwh_alamat_perusahaan": (
            saved.get(
                "alamat",
                "",
            )
        ),

        "kwh_input_manual_perusahaan": False,

        "kwh_sudah_disimpan_db": False,
        "kwh_last_pengujian_id": None,
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
        "data_penera_kwh"
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
        "data_penera_kwh"
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
            
def ambil_nomor_order_kwh_berikutnya(
    tanggal,
    supabase=None,
):
    if supabase is None:
        supabase = get_supabase_kwh()

    tanggal = parse_tanggal_kwh(
        tanggal
    )

    romawi = bulan_ke_romawi(
        tanggal.month
    )

    tahun = tanggal.year

    response = (
        supabase
        .table("pengujian")
        .select("nomor_order")
        .ilike(
            "nomor_order",
            (
                f"%/UAPV/SCD/"
                f"{romawi}/{tahun}"
            ),
        )
        .execute()
    )

    pola = re.compile(
        rf"^\s*(\d+)\s*/\s*UAPV\s*/\s*SCD"
        rf"\s*/\s*{romawi}\s*/\s*{tahun}\s*$",
        re.IGNORECASE,
    )

    tertinggi = 0

    for row in (
        response.data
        or []
    ):
        cocok = pola.match(
            str(
                row.get(
                    "nomor_order"
                )
                or ""
            ).strip()
        )

        if cocok:
            tertinggi = max(
                tertinggi,
                int(
                    cocok.group(1)
                ),
            )

    return (
        f"{tertinggi + 1:04d}"
        f"/UAPV/SCD/"
        f"{romawi}/{tahun}"
    )


def ambil_nomor_sertifikat_kwh_berikutnya(
    tanggal,
    supabase=None,
):
    if supabase is None:
        supabase = get_supabase_kwh()

    tanggal = parse_tanggal_kwh(
        tanggal
    )

    romawi = bulan_ke_romawi(
        tanggal.month
    )

    tahun = tanggal.year

    response = (
        supabase
        .table("pengujian")
        .select(
            "nomor_sertifikat"
        )
        .ilike(
            "nomor_sertifikat",
            (
                "%/BID-K/"
                f"{romawi}/{tahun}"
            ),
        )
        .execute()
    )

    pola = re.compile(
        rf"^500\.2\.3\.15\s*/\s*(\d+)"
        rf"\s*/\s*BID-K\s*/\s*{romawi}"
        rf"\s*/\s*{tahun}\s*$",
        re.IGNORECASE,
    )

    tertinggi = 0

    for row in (
        response.data
        or []
    ):
        cocok = pola.match(
            str(
                row.get(
                    "nomor_sertifikat"
                )
                or ""
            ).strip()
        )

        if cocok:
            tertinggi = max(
                tertinggi,
                int(
                    cocok.group(1)
                ),
            )

    return (
        "500.2.3.15/"
        f"{tertinggi + 1:04d}"
        f"/BID-K/{romawi}/{tahun}"
    )

# =========================================================
# HELPER ANGKA kWh
# =========================================================
def angka_kwh(value, default=0.0):
    """
    Mengambil angka pertama dari teks.

    Contoh:
    "1600 imp/kWh" -> 1600
    "230 V"        -> 230
    """
    if value is None:
        return float(default)

    text = str(value).strip()

    if not text:
        return float(default)

    text = text.replace(",", ".")

    cocok = re.search(
        r"-?\d+(?:\.\d+)?",
        text,
    )

    if not cocok:
        return float(default)

    try:
        return float(
            cocok.group(0)
        )
    except ValueError:
        return float(default)


# =========================================================
# SIMPAN / UPDATE PERUSAHAAN kWh
# =========================================================
def simpan_atau_update_perusahaan_kwh(
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
            "Nama perusahaan belum tersedia."
        )

    if not alamat:
        raise ValueError(
            "Alamat perusahaan belum tersedia."
        )

    kecamatan = (
        ambil_kecamatan_dari_alamat(
            alamat
        )
        or ""
    )

    response_cari = (
        supabase
        .table("perusahaan")
        .select(
            "id, nama_perusahaan, "
            "alamat, kecamatan"
        )
        .ilike(
            "nama_perusahaan",
            nama_perusahaan,
        )
        .limit(1)
        .execute()
    )

    # =====================================================
    # PERUSAHAAN SUDAH ADA
    # =====================================================
    if response_cari.data:

        lama = (
            response_cari.data[0]
        )

        perusahaan_id = (
            lama["id"]
        )

        payload_update = {}

        nama_lama = str(
            lama.get(
                "nama_perusahaan",
                "",
            )
            or ""
        ).strip()

        alamat_lama = str(
            lama.get(
                "alamat",
                "",
            )
            or ""
        ).strip()

        kecamatan_lama = str(
            lama.get(
                "kecamatan",
                "",
            )
            or ""
        ).strip()

        if nama_lama != nama_perusahaan:
            payload_update[
                "nama_perusahaan"
            ] = nama_perusahaan

        if alamat_lama != alamat:
            payload_update[
                "alamat"
            ] = alamat

        if (
            kecamatan
            and kecamatan != kecamatan_lama
        ):
            payload_update[
                "kecamatan"
            ] = kecamatan

        if payload_update:

            response_update = (
                supabase
                .table("perusahaan")
                .update(
                    payload_update
                )
                .eq(
                    "id",
                    perusahaan_id,
                )
                .execute()
            )

            if not response_update.data:
                raise RuntimeError(
                    "Data perusahaan gagal diperbarui."
                )

        return perusahaan_id

    # =====================================================
    # PERUSAHAAN BARU
    # =====================================================
    payload_insert = {
        "nama_perusahaan": (
            nama_perusahaan
        ),
        "alamat": alamat,
    }

    if kecamatan:
        payload_insert[
            "kecamatan"
        ] = kecamatan

    response_insert = (
        supabase
        .table("perusahaan")
        .insert(
            payload_insert
        )
        .execute()
    )

    if not response_insert.data:
        raise RuntimeError(
            "Perusahaan gagal disimpan "
            "ke Supabase."
        )

    return (
        response_insert
        .data[0]["id"]
    )


# =========================================================
# CARI / BUAT MASTER kWh METER
# =========================================================
def get_or_create_master_kwh(
    supabase,
    perusahaan_id,
    data,
):
    """
    Satu master UTTP mewakili satu spesifikasi/model kWh.

    UNIT bukan jumlah row master UTTP.

    Contoh:
    UNIT = 1000
    → master UTTP tetap 1
    → pengujian.jumlah_alat = 1000
    """

    jenis_uttp = "kWh Meter"

    merk_buatan = str(
        data.get(
            "merk_buatan",
            ""
        )
        or ""
    ).strip()

    model_tipe = str(
        data.get(
            "model_tipe",
            ""
        )
        or ""
    ).strip()

    tegangan = str(
        data.get(
            "tegangan",
            ""
        )
        or ""
    ).strip()

    arus = str(
        data.get(
            "arus",
            ""
        )
        or ""
    ).strip()

    phase = str(
        data.get(
            "phs",
            ""
        )
        or ""
    ).strip()

    kelas = str(
        data.get(
            "kelas",
            ""
        )
        or ""
    ).strip()

    konstanta_raw = str(
        data.get(
            "konstanta",
            ""
        )
        or ""
    ).strip()

    konstanta = angka_kwh(
        konstanta_raw
    )

    if not merk_buatan:
        raise ValueError(
            "Merk / Buatan belum diisi."
        )

    if not model_tipe:
        raise ValueError(
            "Model / Tipe belum diisi."
        )

    if not tegangan:
        raise ValueError(
            "Tegangan belum diisi."
        )

    if not arus:
        raise ValueError(
            "Arus belum diisi."
        )

    if not phase:
        raise ValueError(
            "PHS belum diisi."
        )

    if not kelas:
        raise ValueError(
            "Kelas belum diisi."
        )

    if konstanta <= 0:
        raise ValueError(
            "Konstanta kWh Meter "
            "harus lebih besar dari 0."
        )

    payload = {
        "perusahaan_id": (
            perusahaan_id
        ),

        "jenis_uttp": (
            jenis_uttp
        ),

        "merk": (
            merk_buatan
        ),

        "tipe": (
            model_tipe
        ),

        "tegangan": (
            tegangan
        ),

        "satuan_tegangan": (
            "V"
        ),

        "arus": (
            arus
        ),

        "satuan_arus": (
            "A"
        ),

        "phase": (
            phase
        ),

        "kelas": (
            kelas
        ),

        "konstanta": (
            konstanta
        ),

        "satuan_konstanta": (
            "imp/kWh"
        ),

        "status": (
            "aktif"
        ),
    }

    # =====================================================
    # EDIT / PENGUJIAN BARU DARI RIWAYAT
    # MASTER SUDAH DIKENAL
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
        ).strip()
    ):
        try:
            uttp_id_lama = int(
                float(
                    uttp_id_lama
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            uttp_id_lama = None

    if uttp_id_lama is not None:

        response_update = (
            supabase
            .table("uttp")
            .update(
                payload
            )
            .eq(
                "id",
                uttp_id_lama,
            )
            .execute()
        )

        if not response_update.data:
            raise RuntimeError(
                "Master kWh Meter lama "
                "tidak ditemukan."
            )

        return (
            uttp_id_lama,
            False,
        )

    # =====================================================
    # CARI MASTER DENGAN SPESIFIKASI SAMA
    # =====================================================
    response_cari = (
        supabase
        .table("uttp")
        .select("id")
        .eq(
            "perusahaan_id",
            perusahaan_id,
        )
        .eq(
            "jenis_uttp",
            jenis_uttp,
        )
        .eq(
            "merk",
            merk_buatan,
        )
        .eq(
            "tipe",
            model_tipe,
        )
        .eq(
            "tegangan",
            tegangan,
        )
        .eq(
            "arus",
            arus,
        )
        .eq(
            "phase",
            phase,
        )
        .eq(
            "kelas",
            kelas,
        )
        .eq(
            "konstanta",
            konstanta,
        )
        .limit(1)
        .execute()
    )

    if response_cari.data:

        return (
            response_cari.data[0][
                "id"
            ],
            False,
        )

    # =====================================================
    # MASTER BARU
    # =====================================================
    response_insert = (
        supabase
        .table("uttp")
        .insert(
            payload
        )
        .execute()
    )

    if not response_insert.data:
        raise RuntimeError(
            "Master kWh Meter gagal disimpan."
        )

    return (
        response_insert.data[0]["id"],
        True,
    )


# =========================================================
# SIMPAN / UPDATE PENGUJIAN kWh
# =========================================================
def simpan_pengujian_kwh_ke_supabase(
    data
):
    if not data:
        raise ValueError(
            "Data kWh Meter belum tersedia."
        )

    supabase = (
        get_supabase_kwh()
    )

    # =====================================================
    # MODE EDIT
    # =====================================================
    edit_id = (
        st.session_state.get(
            "kwh_edit_pengujian_id"
        )
        or data.get(
            "_edit_pengujian_id"
        )
    )

    if (
        edit_id is not None
        and str(edit_id).strip()
    ):
        try:
            edit_id = int(
                float(edit_id)
            )
        except (
            TypeError,
            ValueError,
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
            "Tera"
        )
        or "Tera"
    ).strip()

    # =====================================================
    # UNIT = JUMLAH ALAT
    # =====================================================
    try:
        jumlah_alat = int(
            data.get(
                "jumlah_alat",
                data.get(
                    "jumlah_unit",
                    data.get(
                        "unit",
                        1,
                    ),
                ),
            )
            or 1
        )
    except (
        TypeError,
        ValueError,
    ):
        jumlah_alat = 0

    if not pemilik:
        raise ValueError(
            "Nama perusahaan belum tersedia."
        )

    if not alamat:
        raise ValueError(
            "Alamat perusahaan belum tersedia."
        )

    if not nomor_order:
        raise ValueError(
            "Nomor order belum tersedia."
        )

    if not nomor_sertifikat:
        raise ValueError(
            "Nomor sertifikat belum tersedia."
        )

    if not penera_1:
        raise ValueError(
            "Penera 1 belum dipilih."
        )

    if jumlah_alat <= 0:
        raise ValueError(
            "UNIT harus lebih besar dari 0."
        )

    # =====================================================
    # CEK NOMOR SERTIFIKAT GANDA
    # =====================================================
    query_sertifikat = (
        supabase
        .table("pengujian")
        .select("id")
        .eq(
            "nomor_sertifikat",
            nomor_sertifikat,
        )
    )

    if sedang_edit:
        query_sertifikat = (
            query_sertifikat
            .neq(
                "id",
                edit_id,
            )
        )

    response_duplikat = (
        query_sertifikat
        .limit(1)
        .execute()
    )

    if response_duplikat.data:
        raise ValueError(
            "Nomor sertifikat sudah digunakan."
        )

    # =====================================================
    # PERUSAHAAN
    # =====================================================
    perusahaan_id = (
        simpan_atau_update_perusahaan_kwh(
            supabase,
            pemilik,
            alamat,
        )
    )

    uttp_id = None
    uttp_baru = False
    pengujian_id = None

    try:
        # =================================================
        # MASTER UTTP
        # =================================================
        (
            uttp_id,
            uttp_baru,
        ) = (
            get_or_create_master_kwh(
                supabase,
                perusahaan_id,
                data,
            )
        )

        # =================================================
        # TANGGAL
        # =================================================
        tanggal_pengujian = (
            parse_tanggal_kwh(
                data.get(
                    "tanggal_pengujian"
                )
            )
        )

        tanggal_sertifikat = (
            parse_tanggal_kwh(
                data.get(
                    "tanggal_cetak"
                ),
                tanggal_pengujian,
            )
        )

        berlaku_sampai = (
            parse_tanggal_kwh(
                data.get(
                    "berlaku_sampai"
                ),
                tambah_tahun(
                    tanggal_pengujian,
                    10,
                ),
            )
        )

        kecamatan = (
            ambil_kecamatan_dari_alamat(
                alamat
            )
            or ""
        )

        # =================================================
        # SNAPSHOT KEGIATAN
        # =================================================
        data_pengujian = {
            "schema_kwh": 1,

            "nama_alat": (
                "kWh Meter"
            ),

            "untuk_pengguna": (
                data.get(
                    "untuk_pengguna",
                    ""
                )
            ),

            "jumlah_alat": (
                jumlah_alat
            ),

            "jumlah_unit": (
                jumlah_alat
            ),

            "kecamatan": (
                kecamatan
            ),

            "nip_penera_1": (
                data.get(
                    "nip_penera_1",
                    ""
                )
            ),

            "golongan_penera_1": (
                data.get(
                    "golongan_penera_1",
                    ""
                )
            ),

            "nip_penera_2": (
                data.get(
                    "nip_penera_2",
                    ""
                )
            ),

            "golongan_penera_2": (
                data.get(
                    "golongan_penera_2",
                    ""
                )
            ),
        }

        # =================================================
        # HEADER PENGUJIAN
        # =================================================
        payload_pengujian = {
            "perusahaan_id": (
                perusahaan_id
            ),

            "uttp_id": (
                uttp_id
            ),

            "tanggal_pengujian": (
                tanggal_pengujian
                .isoformat()
            ),

            "tanggal_sertifikat": (
                tanggal_sertifikat
                .isoformat()
            ),

            "jenis_pengujian": (
                jenis_pengujian
            ),

            "hasil": (
                "SAH"
            ),

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
                berlaku_sampai
                .isoformat()
            ),

            # =============================================
            # PALING PENTING UNTUK LAPORAN
            # =============================================
            "jumlah_alat": (
                jumlah_alat
            ),

            "data_pengujian": (
                data_pengujian
            ),
        }

        data_detail = {
            "schema_kwh_detail": 1,

            "jumlah_alat": (
                jumlah_alat
            ),

            "jumlah_unit": (
                jumlah_alat
            ),
        }

        payload_relasi = {
            "uttp_id": (
                uttp_id
            ),

            "urutan": 1,

            "hasil": (
                "SAH"
            ),

            "data_detail": (
                data_detail
            ),

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
                    "Pengujian kWh Meter "
                    "gagal disimpan."
                )

            pengujian_id = (
                response_pengujian
                .data[0]["id"]
            )

            response_relasi = (
                supabase
                .table(
                    "pengujian_uttp"
                )
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
                    "Relasi kWh Meter "
                    "gagal disimpan."
                )

            return {
                "mode": "baru",
                "pengujian_id": (
                    pengujian_id
                ),
                "uttp_id": uttp_id,
                "perusahaan_id": (
                    perusahaan_id
                ),
            }

        # =================================================
        # EDIT
        # =================================================
        pengujian_id = (
            edit_id
        )

        response_pengujian = (
            supabase
            .table("pengujian")
            .update(
                payload_pengujian
            )
            .eq(
                "id",
                pengujian_id,
            )
            .execute()
        )

        if not response_pengujian.data:
            raise RuntimeError(
                "Pengujian kWh Meter "
                "gagal diperbarui."
            )

        response_relasi_lama = (
            supabase
            .table("pengujian_uttp")
            .select("id")
            .eq(
                "pengujian_id",
                pengujian_id,
            )
            .order("id")
            .execute()
        )

        relasi_lama = (
            response_relasi_lama.data
            or []
        )

        if relasi_lama:

            relasi_id = (
                relasi_lama[0]["id"]
            )

            response_relasi = (
                supabase
                .table("pengujian_uttp")
                .update(
                    payload_relasi
                )
                .eq(
                    "id",
                    relasi_id,
                )
                .execute()
            )

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
                "Relasi kWh Meter "
                "gagal diperbarui."
            )

        return {
            "mode": "edit",
            "pengujian_id": (
                pengujian_id
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
        # ROLLBACK DATA BARU
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
                        pengujian_id,
                    )
                    .execute()
                )
            except Exception:
                pass

        if (
            uttp_baru
            and uttp_id is not None
        ):
            try:
                (
                    supabase
                    .table("uttp")
                    .delete()
                    .eq(
                        "id",
                        uttp_id,
                    )
                    .execute()
                )
            except Exception:
                pass

        raise


# =========================================================
# PENGAMAN DUPLIKASI DATABASE
# =========================================================
def pastikan_kwh_tersimpan_db(
    data
):
    edit_id = (
        st.session_state.get(
            "kwh_edit_pengujian_id"
        )
        or data.get(
            "_edit_pengujian_id"
        )
    )

    sedang_edit = (
        edit_id is not None
        and str(edit_id).strip()
    )

    # =====================================================
    # EDIT → SELALU UPDATE ID YANG SAMA
    # =====================================================
    if sedang_edit:

        hasil = (
            simpan_pengujian_kwh_ke_supabase(
                data
            )
        )

        st.session_state[
            "kwh_last_pengujian_id"
        ] = hasil.get(
            "pengujian_id"
        )

        return hasil

    # =====================================================
    # DATA BARU SUDAH PERNAH DISIMPAN
    # JANGAN INSERT LAGI
    # =====================================================
    if st.session_state.get(
        "kwh_sudah_disimpan_db",
        False,
    ):
        return {
            "mode": (
                "sudah_tersimpan"
            ),

            "pengujian_id": (
                st.session_state.get(
                    "kwh_last_pengujian_id"
                )
            ),
        }

    # =====================================================
    # INSERT PERTAMA
    # =====================================================
    hasil = (
        simpan_pengujian_kwh_ke_supabase(
            data
        )
    )

    st.session_state[
        "kwh_sudah_disimpan_db"
    ] = True

    st.session_state[
        "kwh_last_pengujian_id"
    ] = hasil.get(
        "pengujian_id"
    )

    return hasil

# =========================================================
# AMBIL RIWAYAT PENGUJIAN kWh METER
# =========================================================
def ambil_riwayat_kwh():

    supabase = get_supabase_kwh()

    # =====================================================
    # 1. HEADER PENGUJIAN
    # =====================================================
    response_pengujian = (
        supabase
        .table("pengujian")
        .select("*")
        .order(
            "tanggal_pengujian",
            desc=True,
        )
        .execute()
    )

    semua_pengujian = (
        response_pengujian.data
        or []
    )

    # Hanya kWh Meter struktur baru
    daftar_pengujian = []

    for row in semua_pengujian:

        detail = (
            row.get(
                "data_pengujian"
            )
            or {}
        )

        if str(
            detail.get(
                "schema_kwh",
                "",
            )
        ).strip() == "1":

            daftar_pengujian.append(
                row
            )

    if not daftar_pengujian:
        return []

    # =====================================================
    # 2. RELASI PENGUJIAN - UTTP
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
            daftar_pengujian_id,
        )
        .execute()
    )

    semua_relasi = (
        response_relasi.data
        or []
    )

    relasi_map = {}

    for relasi in semua_relasi:

        pengujian_id = (
            relasi.get(
                "pengujian_id"
            )
        )

        # kWh hanya menggunakan 1 relasi utama
        if pengujian_id not in relasi_map:
            relasi_map[
                pengujian_id
            ] = relasi

    # =====================================================
    # 3. MASTER UTTP
    # =====================================================
    daftar_uttp_id = list({
        row.get(
            "uttp_id"
        )
        for row in semua_relasi
        if row.get(
            "uttp_id"
        ) is not None
    })

    # Fallback pengujian.uttp_id
    for row in daftar_pengujian:

        uttp_id = row.get(
            "uttp_id"
        )

        if (
            uttp_id is not None
            and uttp_id not in daftar_uttp_id
        ):
            daftar_uttp_id.append(
                uttp_id
            )

    uttp_map = {}

    if daftar_uttp_id:

        response_uttp = (
            supabase
            .table("uttp")
            .select(
                "id, perusahaan_id, jenis_uttp, "
                "merk, tipe, "
                "tegangan, satuan_tegangan, "
                "arus, satuan_arus, "
                "phase, kelas, "
                "konstanta, satuan_konstanta, "
                "status"
            )
            .in_(
                "id",
                daftar_uttp_id,
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
        row.get(
            "perusahaan_id"
        )
        for row in daftar_pengujian
        if row.get(
            "perusahaan_id"
        ) is not None
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
                daftar_perusahaan_id,
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
    # 5. GABUNGKAN
    # =====================================================
    hasil = []

    for header in daftar_pengujian:

        pengujian_id = (
            header.get("id")
        )

        detail = dict(
            header.get(
                "data_pengujian"
            )
            or {}
        )

        perusahaan = (
            perusahaan_map.get(
                header.get(
                    "perusahaan_id"
                ),
                {},
            )
            or {}
        )

        relasi = (
            relasi_map.get(
                pengujian_id,
                {},
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
                {},
            )
            or {}
        )

        # =================================================
        # IDENTITAS INTERNAL
        # =================================================
        detail[
            "_uttp_id"
        ] = uttp_id

        # =================================================
        # PERUSAHAAN
        # =================================================
        nama_perusahaan = str(
            perusahaan.get(
                "nama_perusahaan",
                ""
            )
            or ""
        ).strip()

        if not nama_perusahaan:
            nama_perusahaan = str(
                detail.get(
                    "pemilik",
                    ""
                )
                or ""
            ).strip()

        detail[
            "pemilik"
        ] = nama_perusahaan

        detail[
            "alamat"
        ] = str(
            perusahaan.get(
                "alamat",
                "",
            )
            or ""
        ).strip()

        # =================================================
        # MASTER kWh
        # =================================================
        detail[
            "nama_alat"
        ] = "kWh Meter"

        detail[
            "merk_buatan"
        ] = str(
            alat.get(
                "merk",
                "",
            )
            or ""
        ).strip()

        detail[
            "model_tipe"
        ] = str(
            alat.get(
                "tipe",
                "",
            )
            or ""
        ).strip()

        detail[
            "tegangan"
        ] = str(
            alat.get(
                "tegangan",
                "",
            )
            or ""
        ).strip()

        detail[
            "satuan_tegangan"
        ] = str(
            alat.get(
                "satuan_tegangan",
                "V",
            )
            or "V"
        ).strip()

        detail[
            "arus"
        ] = str(
            alat.get(
                "arus",
                "",
            )
            or ""
        ).strip()

        detail[
            "satuan_arus"
        ] = str(
            alat.get(
                "satuan_arus",
                "A",
            )
            or "A"
        ).strip()

        detail[
            "phs"
        ] = str(
            alat.get(
                "phase",
                "",
            )
            or ""
        ).strip()

        detail[
            "kelas"
        ] = str(
            alat.get(
                "kelas",
                "",
            )
            or ""
        ).strip()

        detail[
            "konstanta"
        ] = (
            alat.get(
                "konstanta",
                0,
            )
        )

        detail[
            "satuan_konstanta"
        ] = str(
            alat.get(
                "satuan_konstanta",
                "imp/kWh",
            )
            or "imp/kWh"
        ).strip()

        # =================================================
        # UNIT
        # =================================================
        try:
            jumlah_alat = int(
                header.get(
                    "jumlah_alat",
                    1,
                )
                or 1
            )
        except (
            TypeError,
            ValueError,
        ):
            jumlah_alat = 1

        detail[
            "unit"
        ] = jumlah_alat

        detail[
            "jumlah_unit"
        ] = jumlah_alat

        detail[
            "jumlah_alat"
        ] = jumlah_alat

        # =================================================
        # DATA PENGUJIAN
        # =================================================
        detail[
            "jenis_pengujian"
        ] = header.get(
            "jenis_pengujian",
            "",
        )

        detail[
            "tanggal_pengujian"
        ] = header.get(
            "tanggal_pengujian"
        )

        detail[
            "tanggal_cetak"
        ] = header.get(
            "tanggal_sertifikat"
        )

        detail[
            "berlaku_sampai"
        ] = header.get(
            "berlaku_sampai"
        )

        detail[
            "nomor_order"
        ] = header.get(
            "nomor_order",
            "",
        )

        detail[
            "nomor_sertifikat"
        ] = header.get(
            "nomor_sertifikat",
            "",
        )

        detail[
            "penera_1"
        ] = header.get(
            "penera_1",
            "",
        )
        detail[
            "nip_penera_1"
        ] = str(
            detail.get(
                "nip_penera_1",
                ""
            )
            or ""
        ).strip()

        detail[
            "golongan_penera_1"
        ] = str(
            detail.get(
                "golongan_penera_1",
                ""
            )
            or ""
        ).strip()

        detail[
            "nip_penera_2"
        ] = str(
            detail.get(
                "nip_penera_2",
                ""
            )
            or ""
        ).strip()

        detail[
            "golongan_penera_2"
        ] = str(
            detail.get(
                "golongan_penera_2",
                ""
            )
            or ""
        ).strip()
        detail[
            "penera_2"
        ] = (
            header.get(
                "penera_2",
                "",
            )
            or ""
        )

        detail[
            "hasil"
        ] = header.get(
            "hasil",
            "SAH",
        )

        hasil.append({
            "id": pengujian_id,
            "data": detail,
        })

    return hasil

# =========================================================
# EDIT PENGUJIAN kWh DARI RIWAYAT
# =========================================================
def gunakan_data_lama_untuk_edit_kwh(
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
            {},
        )
        or {}
    )

    if pengujian_id is None:
        raise ValueError(
            "ID pengujian kWh Meter "
            "tidak ditemukan."
        )

    data_riwayat[
        "_edit_pengujian_id"
    ] = pengujian_id

    # =====================================================
    # BERSIHKAN STATE FORM kWh
    # =====================================================
    for key in list(
        st.session_state.keys()
    ):

        if (
            key.endswith("_kwh")
            or key.startswith("kwh_")
            or key in {
                "saved_data_kwh",
                "data_kwh",
                "generated_files_kwh",
            }
        ):
            st.session_state.pop(
                key,
                None,
            )

    # =====================================================
    # MASUKKAN DATA RIWAYAT KE FORM
    # =====================================================
    st.session_state[
        "saved_data_kwh"
    ] = data_riwayat

    st.session_state[
        "data_kwh"
    ] = data_riwayat

    st.session_state[
        "kwh_edit_pengujian_id"
    ] = pengujian_id

    st.session_state[
        "kwh_sudah_disimpan_db"
    ] = False

    st.session_state[
        "kwh_last_pengujian_id"
    ] = None

    st.session_state[
        "generated_files_kwh"
    ] = {}

    # Pindah mode pada rerun berikutnya
    st.session_state[
        "kwh_next_mode"
    ] = MODE_INPUT
    
# =========================================================
# TAMBAH PENGUJIAN BARU DARI MASTER kWh LAMA
# =========================================================
def gunakan_riwayat_untuk_pengujian_baru_kwh(
    riwayat
):
    data_lama = dict(
        riwayat.get(
            "data",
            {},
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
            "Master kWh Meter pada riwayat "
            "tidak ditemukan."
        )

    tanggal_baru = (
        date.today()
    )

    berlaku_baru = (
        tambah_tahun(
            tanggal_baru,
            10,
        )
    )

    # =====================================================
    # IDENTITAS ALAT LAMA DIBAWA
    # DATA KEGIATAN DIBUAT BARU
    # =====================================================
    data_baru = {

        "_edit_pengujian_id": None,

        "_uttp_id": (
            uttp_id
        ),

        "nama_alat": (
            "kWh Meter"
        ),

        "merk_buatan": (
            data_lama.get(
                "merk_buatan",
                "SMART / INDONESIA",
            )
        ),

        "model_tipe": (
            data_lama.get(
                "model_tipe",
                "",
            )
        ),

        "tegangan": (
            data_lama.get(
                "tegangan",
                "",
            )
        ),

        "satuan_tegangan": (
            data_lama.get(
                "satuan_tegangan",
                "V",
            )
        ),

        "arus": (
            data_lama.get(
                "arus",
                "",
            )
        ),

        "satuan_arus": (
            data_lama.get(
                "satuan_arus",
                "A",
            )
        ),

        "phs": (
            data_lama.get(
                "phs",
                "1",
            )
        ),

        "kelas": (
            data_lama.get(
                "kelas",
                "1",
            )
        ),

        "konstanta": (
            data_lama.get(
                "konstanta",
                1600,
            )
        ),

        "satuan_konstanta": (
            data_lama.get(
                "satuan_konstanta",
                "imp/kWh",
            )
        ),

        # =============================================
        # PERUSAHAAN
        # =============================================
        "pemilik": (
            data_lama.get(
                "pemilik",
                "",
            )
        ),

        "alamat": (
            data_lama.get(
                "alamat",
                "",
            )
        ),

        "untuk_pengguna": (
            data_lama.get(
                "untuk_pengguna",
                "",
            )
        ),

        # =============================================
        # KEGIATAN BARU
        # =============================================
        "jenis_pengujian": (
            "Tera"
        ),

        "tanggal_pengujian": (
            tanggal_baru.isoformat()
        ),

        "tanggal_cetak": (
            tanggal_baru.isoformat()
        ),

        "berlaku_sampai": (
            berlaku_baru.isoformat()
        ),

        # Placeholder.
        # User tetap klik Generate Nomor.
        "nomor_order": (
            generate_nomor_order(
                tanggal_baru
            )
        ),

        "nomor_sertifikat": (
            generate_nomor_sertifikat(
                tanggal_baru
            )
        ),

        # =============================================
        # PENERA SEBAGAI DEFAULT
        # =============================================
        "penera_1": (
            data_lama.get(
                "penera_1",
                "",
            )
        ),

        "nip_penera_1": (
            data_lama.get(
                "nip_penera_1",
                "",
            )
        ),

        "golongan_penera_1": (
            data_lama.get(
                "golongan_penera_1",
                "",
            )
        ),

        "penera_2": (
            data_lama.get(
                "penera_2",
                "",
            )
        ),

        "nip_penera_2": (
            data_lama.get(
                "nip_penera_2",
                "",
            )
        ),

        "golongan_penera_2": (
            data_lama.get(
                "golongan_penera_2",
                "",
            )
        ),

        "jumlah_penera": (
            data_lama.get(
                "jumlah_penera",
                1,
            )
        ),

        # =============================================
        # PENTING:
        # JUMLAH UNIT LAMA TIDAK DIBAWA
        # =============================================
        "unit": 1,
        "jumlah_unit": 1,
        "jumlah_alat": 1,

        "hasil": "SAH",
    }

    # =====================================================
    # BERSIHKAN STATE FORM
    # =====================================================
    for key in list(
        st.session_state.keys()
    ):

        if (
            key.endswith("_kwh")
            or key.startswith("kwh_")
            or key in {
                "saved_data_kwh",
                "data_kwh",
                "generated_files_kwh",
            }
        ):
            st.session_state.pop(
                key,
                None,
            )

    # Bukan edit
    st.session_state.pop(
        "kwh_edit_pengujian_id",
        None,
    )

    st.session_state[
        "saved_data_kwh"
    ] = data_baru

    st.session_state[
        "data_kwh"
    ] = data_baru

    st.session_state[
        "kwh_sudah_disimpan_db"
    ] = False

    st.session_state[
        "kwh_last_pengujian_id"
    ] = None

    st.session_state[
        "generated_files_kwh"
    ] = {}

    st.session_state[
        "kwh_next_mode"
    ] = MODE_INPUT

def update_pemilik_dari_merk_kwh():

    merk = st.session_state.get(
        "merk_buatan_kwh",
        "SMART / INDONESIA",
    )

    set_pemilik_otomatis_kwh(
        merk
    )
    
def set_pemilik_otomatis_kwh(
    merk
):
    mapping_perusahaan = {
        "SMART / INDONESIA":
            "PT. SMART METER INDONESIA",

        "CANNET / INDONESIA":
            "PT. CANNET ELEKTRIK INDONESIA",
    }

    nama_perusahaan = (
        mapping_perusahaan.get(
            str(merk or "").strip()
        )
    )

    if not nama_perusahaan:
        return

    df = st.session_state.get(
        "data_perusahaan_kwh"
    )

    if (
        df is None
        or df.empty
    ):
        return

    row = df[
        df[
            "Nama Perusahaan"
        ]
        .astype(str)
        .str.strip()
        .str.upper()
        == nama_perusahaan.upper()
    ]

    if row.empty:
        return

    data = row.iloc[0]

    nama_master = str(
        data.get(
            "Nama Perusahaan",
            nama_perusahaan,
        )
        or nama_perusahaan
    ).strip()

    alamat_master = str(
        data.get(
            "Alamat",
            "",
        )
        or ""
    ).strip()

    st.session_state[
        "kwh_perusahaan_select"
    ] = nama_master

    st.session_state[
        "kwh_nama_perusahaan"
    ] = nama_master

    st.session_state[
        "kwh_alamat_perusahaan"
    ] = alamat_master
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

    if "kwh_next_mode" in st.session_state:
        st.session_state[
            "menu_kwh"
        ] = st.session_state.pop(
            "kwh_next_mode"
        )


    mode = st.sidebar.radio(
        "Menu kWh Meter",
        [
            MODE_INPUT,
            MODE_PREVIEW,
            MODE_HISTORY,
        ],
        key="menu_kwh",
    )

    # =========================
    # MODE INPUT
    # =========================
    if mode == MODE_INPUT:

        st.header(
            "Masukkan Data Pengujian kWh Meter"
        )

        if st.session_state.get(
            "kwh_edit_pengujian_id"
        ):

            st.warning(
                "✏️ Anda sedang mengedit "
                "pengujian kWh Meter yang "
                "sudah tersimpan."
            )

        saved = st.session_state.get("saved_data_kwh", {})
        if (
            not saved
            and not st.session_state.get(
                "kwh_nama_perusahaan"
            )
        ):
            set_pemilik_otomatis_kwh(
                "SMART / INDONESIA"
            )
        st.subheader(
            "📊 Nomor Dokumen"
        )

        col_tgl1, col_tgl2 = (
            st.columns(2)
        )

        with col_tgl1:
            tanggal_pengujian = (
                st.date_input(
                    "Tanggal Pengujian",
                    key=(
                        "tanggal_pengujian_kwh"
                    ),
                )
            )

        with col_tgl2:
            tanggal_cetak = (
                st.date_input(
                    "Tanggal Sertifikat",
                    key=(
                        "tanggal_cetak_kwh"
                    ),
                )
            )


        if st.button(
            "🔢 Generate Nomor Order & Sertifikat",
            type="primary",
            use_container_width=True,
            key=(
                "kwh_generate_nomor"
            ),
        ):
            supabase_nomor = (
                get_supabase_kwh()
            )

            st.session_state[
                "nomor_order_kwh"
            ] = (
                ambil_nomor_order_kwh_berikutnya(
                    tanggal_pengujian,
                    supabase_nomor,
                )
            )

            st.session_state[
                "nomor_sertifikat_kwh"
            ] = (
                ambil_nomor_sertifikat_kwh_berikutnya(
                    tanggal_cetak,
                    supabase_nomor,
                )
            )


        col_no1, col_no2 = (
            st.columns(2)
        )

        with col_no1:
            nomor_order = st.text_input(
                "Nomor Order",
                key="nomor_order_kwh",
            )

        with col_no2:
            nomor_sertifikat = (
                st.text_input(
                    "Nomor Sertifikat",
                    key=(
                        "nomor_sertifikat_kwh"
                    ),
                )
            )

        st.markdown("---")
        
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
                "Lainnya / Input Manual",
            ]

            merk_tersimpan = str(
                saved.get(
                    "merk_buatan",
                    "SMART / INDONESIA",
                )
                or "SMART / INDONESIA"
            ).strip()

            if merk_tersimpan in [
                "SMART / INDONESIA",
                "CANNET / INDONESIA",
            ]:
                pilihan_awal_merk = (
                    merk_tersimpan
                )
            else:
                pilihan_awal_merk = (
                    "Lainnya / Input Manual"
                )

            pilihan_merk = st.selectbox(
                "Merk / Buatan",
                options=pilihan_merk_buatan,
                index=pilihan_merk_buatan.index(
                    pilihan_awal_merk
                ),
                key="merk_buatan_kwh",
                on_change=(
                    update_pemilik_dari_merk_kwh
                ),
            )

            # =====================================================
            # INPUT MANUAL MERK / BUATAN
            # =====================================================
            if (
                pilihan_merk
                == "Lainnya / Input Manual"
            ):

                merk_buatan = st.text_input(
                    "Input Manual Merk / Buatan",
                    value=(
                        merk_tersimpan
                        if merk_tersimpan
                        not in [
                            "SMART / INDONESIA",
                            "CANNET / INDONESIA",
                        ]
                        else ""
                    ),
                    placeholder=(
                        "Contoh: HEXING / INDONESIA"
                    ),
                    key=(
                        "merk_buatan_manual_kwh"
                    ),
                )

            else:

                merk_buatan = pilihan_merk

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

            # =========================================================
            # IDENTITAS PEMILIK
            # =========================================================
            st.subheader(
                "🏢 Identitas Pemilik"
            )

            df_perusahaan = (
                st.session_state.get(
                    "data_perusahaan_kwh"
                )
            )

            if (
                df_perusahaan is not None
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

                # =====================================================
                # PILIH PERUSAHAAN
                # =====================================================
                st.selectbox(
                    "Cari & Pilih Nama Perusahaan",
                    options=[
                        ""
                    ] + options,
                    placeholder=(
                        "Ketik atau pilih perusahaan..."
                    ),
                    key=(
                        "kwh_perusahaan_select"
                    ),
                    on_change=(
                        update_perusahaan_kwh
                    ),
                    disabled=(
                        st.session_state.get(
                            "kwh_input_manual_perusahaan",
                            False,
                        )
                    ),
                )
                selected_perusahaan = str(
                    st.session_state.get(
                        "kwh_perusahaan_select",
                        ""
                    )
                    or ""
                ).strip()

                if selected_perusahaan:
                    st.session_state[
                        "kwh_nama_perusahaan"
                    ] = selected_perusahaan
                # =====================================================
                # ALAMAT
                # =====================================================
                st.text_area(
                    "Alamat",
                    height=90,
                    key=(
                        "kwh_alamat_perusahaan"
                    ),
                )

                # =====================================================
                # KHUSUS SMART:
                # UNTUK / TUJUAN PENGGUNAAN
                # =====================================================
                if (
                    str(merk_buatan).strip()
                    == "SMART / INDONESIA"
                ):

                    untuk_pengguna = st.text_input(
                        "Untuk / Tujuan Penggunaan",
                        value=str(
                            saved.get(
                                "untuk_pengguna",
                                ""
                            )
                            or ""
                        ),
                        placeholder=(
                            "Contoh: PT. PLN (Persero)"
                        ),
                        key=(
                            "untuk_pengguna_kwh"
                        ),
                    )

                else:

                    untuk_pengguna = ""

                # =====================================================
                # INPUT MANUAL PERUSAHAAN
                # =====================================================
                st.checkbox(
                    "Input manual nama perusahaan",
                    key=(
                        "kwh_input_manual_perusahaan"
                    ),
                )

                if st.session_state.get(
                    "kwh_input_manual_perusahaan",
                    False,
                ):

                    st.text_input(
                        "Nama Pemilik / Perusahaan",
                        key=(
                            "kwh_nama_perusahaan"
                        ),
                    )

            else:

                # =====================================================
                # FALLBACK JIKA MASTER PERUSAHAAN KOSONG
                # =====================================================
                st.text_input(
                    "Nama Pemilik / Perusahaan",
                    key=(
                        "kwh_nama_perusahaan"
                    ),
                )

                st.text_area(
                    "Alamat",
                    height=90,
                    key=(
                        "kwh_alamat_perusahaan"
                    ),
                )

            if st.session_state.get(
                "kwh_input_manual_perusahaan",
                False,
            ):
                pemilik = str(
                    st.session_state.get(
                        "kwh_nama_perusahaan",
                        "",
                    )
                    or ""
                ).strip()

            else:
                pemilik = str(
                    st.session_state.get(
                        "kwh_perusahaan_select",
                        "",
                    )
                    or st.session_state.get(
                        "kwh_nama_perusahaan",
                        "",
                    )
                    or ""
                ).strip()

            alamat = str(
                st.session_state.get(
                    "kwh_alamat_perusahaan",
                    "",
                )
                or ""
            ).strip()


            kecamatan_otomatis = (
                ambil_kecamatan_dari_alamat(
                    alamat
                )
            )

            st.markdown("---")
        
        # =========================================================
        # DATA PENGUJIAN
        # =========================================================
        st.subheader(
            "Data Pengujian"
        )

        col_pengujian1, col_pengujian2 = (
            st.columns(2)
        )

        with col_pengujian1:
            jenis_pengujian = st.selectbox(
                "Jenis Pengujian",
                options=[
                    "Tera",
                    "Tera Ulang",
                ],
                key="jenis_pengujian_kwh",
            )

        with col_pengujian2:
            berlaku_sampai = st.date_input(
                "Berlaku Sampai",
                key="berlaku_sampai_kwh",
                disabled=True,
            )

        st.markdown("---")

        # =========================
        # PENERA
        # =========================
        st.subheader("Penera / Pegawai Berhak")

        df_penera = st.session_state.get("data_penera_kwh")
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
        try:
            jumlah_unit = int(
                str(unit).strip()
            )
        except (
            TypeError,
            ValueError,
        ):
            jumlah_unit = 0
        data_kwh = {
            "_edit_pengujian_id": (
                saved.get(
                    "_edit_pengujian_id"
                )
            ),
            "_uttp_id": (
                saved.get(
                    "_uttp_id"
                )
            ),
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
            "penera_1": str(
                penera_1
                or st.session_state.get(
                    "penera_1_kwh_select",
                    "",
                )
                or ""
            ).strip(),

            "penera_2": str(
                penera_2
                or st.session_state.get(
                    "penera_2_kwh_select",
                    "",
                )
                or ""
            ).strip(),
            "nip_penera_1": str(
                nip_penera_1
                or st.session_state.get(
                    "nip_penera_1_kwh",
                    "",
                )
                or ""
            ).strip(),

            "golongan_penera_1": str(
                golongan_penera_1
                or st.session_state.get(
                    "golongan_penera_1_kwh",
                    "",
                )
                or ""
            ).strip(),

            "nip_penera_2": str(
                nip_penera_2
                or st.session_state.get(
                    "nip_penera_2_kwh",
                    "",
                )
                or ""
            ).strip(),

            "golongan_penera_2": str(
                golongan_penera_2
                or st.session_state.get(
                    "golongan_penera_2_kwh",
                    "",
                )
                or ""
            ).strip(),
            "jumlah_penera": jumlah_penera,
            "jumlah_unit": jumlah_unit,
            "jumlah_alat": jumlah_unit,
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
            if jumlah_unit <= 0:
                st.error(
                    "UNIT harus berupa angka "
                    "lebih besar dari 0."
                )
                st.stop()
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
            st.session_state[
                "kwh_sudah_disimpan_db"
            ] = False

            st.session_state[
                "kwh_last_pengujian_id"
            ] = None
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

        if st.button(
            "📄 Generate Sertifikat kWh Meter",
            type="primary",
        ):
            try:
                # =============================================
                # SIMPAN DATABASE
                # =============================================
                hasil_simpan = (
                    pastikan_kwh_tersimpan_db(
                        data_kwh
                    )
                )

                # =============================================
                # GENERATE PDF
                # =============================================
                OUTPUT_DIR.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                nama_file = (
                    format_nama_file_sertifikat(
                        data_kwh
                    )
                )

                output_file = (
                    OUTPUT_DIR
                    / f"{nama_file}.pdf"
                )

                generate_sertifikat_kwh(
                    data_kwh,
                    str(output_file),
                )

                st.session_state[
                    "generated_files_kwh"
                ][
                    "sertifikat"
                ] = str(
                    output_file
                )

                st.success(
                    "✅ Data kWh Meter berhasil "
                    "disimpan ke Supabase dan "
                    "sertifikat berhasil dibuat."
                )

            except Exception as exc:
                st.error(
                    f"Gagal membuat sertifikat: {exc}"
                )
        # =========================================================
        # DOWNLOAD SERTIFIKAT
        # =========================================================
        sertifikat_path = (
            st.session_state
            .get(
                "generated_files_kwh",
                {}
            )
            .get(
                "sertifikat"
            )
        )

        if sertifikat_path:

            file_sertifikat = Path(
                sertifikat_path
            )

            if file_sertifikat.exists():

                with open(
                    file_sertifikat,
                    "rb"
                ) as pdf_file:

                    st.download_button(
                        label=(
                            "⬇️ Download Sertifikat kWh Meter"
                        ),
                        data=pdf_file.read(),
                        file_name=(
                            file_sertifikat.name
                        ),
                        mime="application/pdf",
                        use_container_width=True,
                        key=(
                            "download_sertifikat_kwh"
                        ),
                    )
    # =========================================================
    # MODE RIWAYAT kWh METER
    # =========================================================
    elif mode == MODE_HISTORY:

        st.header(
            "📚 Riwayat Pengujian kWh Meter"
        )

        try:

            daftar_riwayat = (
                ambil_riwayat_kwh()
            )

            if not daftar_riwayat:

                st.info(
                    "Belum ada riwayat pengujian "
                    "kWh Meter di database."
                )

            else:

                # =================================================
                # 1. PILIH PERUSAHAAN
                # =================================================
                daftar_perusahaan = sorted({
                    str(
                        (
                            item.get(
                                "data",
                                {},
                            )
                            or {}
                        ).get(
                            "pemilik",
                            "",
                        )
                        or ""
                    ).strip()

                    for item
                    in daftar_riwayat

                    if str(
                        (
                            item.get(
                                "data",
                                {},
                            )
                            or {}
                        ).get(
                            "pemilik",
                            "",
                        )
                        or ""
                    ).strip()
                })

                perusahaan_pilih = (
                    st.selectbox(
                        "Cari & Pilih Perusahaan",
                        options=[
                            ""
                        ] + daftar_perusahaan,
                        placeholder=(
                            "Ketik atau pilih perusahaan..."
                        ),
                        key=(
                            "kwh_riwayat_perusahaan"
                        ),
                    )
                )

                # =================================================
                # PERUSAHAAN SUDAH DIPILIH
                # =================================================
                if perusahaan_pilih:

                    riwayat_perusahaan = []

                    for item in daftar_riwayat:

                        detail = (
                            item.get(
                                "data",
                                {},
                            )
                            or {}
                        )

                        pemilik_item = str(
                            detail.get(
                                "pemilik",
                                "",
                            )
                            or ""
                        ).strip()

                        if (
                            pemilik_item
                            == perusahaan_pilih
                        ):
                            riwayat_perusahaan.append(
                                item
                            )

                    # =============================================
                    # 2. SUSUN MASTER kWh
                    # =============================================
                    meter_map = {}

                    for item in riwayat_perusahaan:

                        detail = (
                            item.get(
                                "data",
                                {},
                            )
                            or {}
                        )

                        uttp_id = (
                            detail.get(
                                "_uttp_id"
                            )
                        )

                        merk = str(
                            detail.get(
                                "merk_buatan",
                                "",
                            )
                            or ""
                        ).strip()

                        tipe = str(
                            detail.get(
                                "model_tipe",
                                "",
                            )
                            or ""
                        ).strip()

                        tegangan = str(
                            detail.get(
                                "tegangan",
                                "",
                            )
                            or ""
                        ).strip()

                        arus = str(
                            detail.get(
                                "arus",
                                "",
                            )
                            or ""
                        ).strip()

                        phs = str(
                            detail.get(
                                "phs",
                                "",
                            )
                            or ""
                        ).strip()

                        kelas = str(
                            detail.get(
                                "kelas",
                                "",
                            )
                            or ""
                        ).strip()

                        konstanta = str(
                            detail.get(
                                "konstanta",
                                "",
                            )
                            or ""
                        ).strip()

                        if uttp_id is not None:

                            meter_key = (
                                f"id:{uttp_id}"
                            )

                        else:

                            meter_key = (
                                f"{merk}|"
                                f"{tipe}|"
                                f"{tegangan}|"
                                f"{arus}|"
                                f"{phs}|"
                                f"{kelas}|"
                                f"{konstanta}"
                            )

                        # Riwayat sudah urut terbaru → lama.
                        # Ambil pengujian terbaru saja
                        # untuk setiap master.
                        if (
                            meter_key
                            not in meter_map
                        ):

                            label = (
                                f"{merk or '-'}"
                                f" | "
                                f"{tipe or '-'}"
                                f" | "
                                f"{tegangan or '-'}"
                                f" | "
                                f"{arus or '-'}"
                                f" | "
                                f"{phs or '-'} Ph"
                            )

                            meter_map[
                                meter_key
                            ] = {
                                "label": label,
                                "riwayat": item,
                            }

                    # =============================================
                    # 3. PILIH kWh METER
                    # =============================================
                    if meter_map:

                        st.markdown("---")

                        opsi_meter = {
                            isi["label"]: isi
                            for isi
                            in meter_map.values()
                        }

                        meter_pilih = (
                            st.selectbox(
                                "Pilih kWh Meter",
                                options=[
                                    ""
                                ] + list(
                                    opsi_meter.keys()
                                ),
                                placeholder=(
                                    "Pilih kWh Meter..."
                                ),
                                key=(
                                    "kwh_riwayat_meter"
                                ),
                            )
                        )

                        # =========================================
                        # METER SUDAH DIPILIH
                        # =========================================
                        if meter_pilih:

                            riwayat = (
                                opsi_meter[
                                    meter_pilih
                                ][
                                    "riwayat"
                                ]
                            )

                            detail = (
                                riwayat.get(
                                    "data",
                                    {},
                                )
                                or {}
                            )

                            st.markdown("---")

                            # =====================================
                            # DETAIL MASTER
                            # =====================================
                            st.subheader(
                                "⚡ Detail kWh Meter"
                            )

                            col1, col2 = (
                                st.columns(2)
                            )

                            with col1:

                                st.write(
                                    "**Perusahaan:**",
                                    detail.get(
                                        "pemilik",
                                        "-",
                                    ),
                                )

                                st.write(
                                    "**Alamat:**",
                                    detail.get(
                                        "alamat",
                                        "-",
                                    ),
                                )

                                st.write(
                                    "**Merk / Buatan:**",
                                    detail.get(
                                        "merk_buatan",
                                        "-",
                                    ),
                                )

                                st.write(
                                    "**Model / Tipe:**",
                                    detail.get(
                                        "model_tipe",
                                        "-",
                                    ),
                                )

                            with col2:

                                st.write(
                                    "**Tegangan:**",
                                    detail.get(
                                        "tegangan",
                                        "-",
                                    ),
                                )

                                st.write(
                                    "**Arus:**",
                                    detail.get(
                                        "arus",
                                        "-",
                                    ),
                                )

                                st.write(
                                    "**PHS:**",
                                    detail.get(
                                        "phs",
                                        "-",
                                    ),
                                )

                                st.write(
                                    "**Kelas:**",
                                    detail.get(
                                        "kelas",
                                        "-",
                                    ),
                                )

                                st.write(
                                    "**Konstanta:**",
                                    (
                                        f"{detail.get('konstanta', '-')} "
                                        f"{detail.get('satuan_konstanta', '')}"
                                    ),
                                )

                            # =====================================
                            # PENGUJIAN TERAKHIR
                            # =====================================
                            st.markdown("---")

                            st.caption(
                                "Pengujian terakhir kWh Meter"
                            )

                            col3, col4 = (
                                st.columns(2)
                            )

                            with col3:

                                st.metric(
                                    "Jumlah Unit",
                                    (
                                        f"{int(detail.get('jumlah_alat', 0) or 0):,}"
                                        .replace(
                                            ",",
                                            ".",
                                        )
                                    ),
                                )

                                st.write(
                                    "**Tanggal Pengujian:**",
                                    detail.get(
                                        "tanggal_pengujian",
                                        "-",
                                    ),
                                )

                                st.write(
                                    "**Jenis Pengujian:**",
                                    detail.get(
                                        "jenis_pengujian",
                                        "-",
                                    ),
                                )

                            with col4:

                                st.write(
                                    "**Nomor Order:**",
                                    detail.get(
                                        "nomor_order",
                                        "-",
                                    ),
                                )

                                st.write(
                                    "**Nomor Sertifikat:**",
                                    detail.get(
                                        "nomor_sertifikat",
                                        "-",
                                    ),
                                )

                                st.write(
                                    "**Penera:**",
                                    detail.get(
                                        "penera_1",
                                        "-",
                                    ),
                                )

                            # =====================================
                            # AKSI
                            # =====================================
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
                                        "kwh_edit_riwayat_"
                                        f"{riwayat.get('id')}"
                                    ),
                                ):

                                    gunakan_data_lama_untuk_edit_kwh(
                                        riwayat
                                    )

                                    st.rerun()

                            with col_baru:

                                if st.button(
                                    "➕ Tambah Pengujian",
                                    use_container_width=True,
                                    key=(
                                        "kwh_baru_riwayat_"
                                        f"{riwayat.get('id')}"
                                    ),
                                ):

                                    gunakan_riwayat_untuk_pengujian_baru_kwh(
                                        riwayat
                                    )

                                    st.rerun()

        except Exception as exc:

            st.error(
                "Gagal membaca riwayat "
                f"kWh Meter: {exc}"
            )

            import traceback

            st.code(
                traceback.format_exc()
            )
