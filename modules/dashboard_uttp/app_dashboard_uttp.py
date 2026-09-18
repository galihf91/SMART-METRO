import html
from datetime import date

import pandas as pd
import streamlit as st
import altair as alt
from supabase import create_client


# =========================================================
# KONSTANTA
# =========================================================
BATAS_JATUH_TEMPO_HARI = 30

STATUS_AKTIF = "Aktif"
STATUS_JATUH_TEMPO = "Akan Jatuh Tempo"
STATUS_KEDALUWARSA = "Kedaluwarsa"
STATUS_BELUM_UJI = "Belum Ada Pengujian"
STATUS_DATA_KURANG = "Data Belum Lengkap"

STATUS_ORDER = [
    STATUS_KEDALUWARSA,
    STATUS_JATUH_TEMPO,
    STATUS_AKTIF,
    STATUS_BELUM_UJI,
    STATUS_DATA_KURANG,
]

STATUS_COLOR = {
    STATUS_AKTIF: "#16A34A",
    STATUS_JATUH_TEMPO: "#F59E0B",
    STATUS_KEDALUWARSA: "#DC2626",
    STATUS_BELUM_UJI: "#6B7280",
    STATUS_DATA_KURANG: "#64748B",
}

# =========================================================
# MAPPING LAPORAN BULANAN
# =========================================================

MAPPING_JENIS_LAPORAN = {
    # MASSA TIMBANGAN
    "Timbangan Jembatan": ("MT", "TJE"),
    "Timbangan Elektronik": ("MT", "TE"),
    "Timbangan Meja": ("MT", "TE"),
    "Timbangan Sentisimal": ("MT", "SENTISIMAL"),
    "Timbangan Bobot Insut": ("MT", "TBI"),
    "Timbangan Pegas": ("MT", "PEGAS"),
    "Neraca": ("MT", "NERACA"),
    "Dacin": ("MT", "DACIN"),

    # UAPV
    "kWh Meter": ("UAPV", "KWH"),
    "Tangki Ukur Mobil": ("UAPV", "TUM"),
    "Pompa Ukur BBM": ("UAPV", "NOZZLE"),
    "Meter Air": ("UAPV", "METER_AIR"),
}
# =========================================================
# SUPABASE
# =========================================================
@st.cache_resource
def get_supabase_dashboard_uttp():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]

    return create_client(
        url,
        key,
    )


def fetch_all_rows(
    table_name,
    select_columns,
    page_size=1000,
):
    """
    Ambil seluruh data dari Supabase dengan pagination.
    """

    supabase = get_supabase_dashboard_uttp()

    rows = []
    start = 0

    while True:

        response = (
            supabase
            .table(table_name)
            .select(select_columns)
            .range(
                start,
                start + page_size - 1,
            )
            .execute()
        )

        batch = response.data or []

        rows.extend(
            batch
        )

        if len(batch) < page_size:
            break

        start += page_size

    return rows


@st.cache_data(
    ttl=60,
    show_spinner=False,
)
def load_data_dashboard_uttp():

    perusahaan_rows = fetch_all_rows(
        "perusahaan",
        (
            "id, "
            "nama_perusahaan, "
            "alamat"
        ),
    )
    penera_rows = fetch_all_rows(
        "penera",
        (
            "id, "
            "nama_penera, "
            "kode_penera"
        ),
    )
    spbu_rows = fetch_all_rows(
        "spbu",
        (
            "id, "
            "nama_spbu, "
            "nomor_spbu, "
            "alamat, "
            "jenis_lokasi, "
            "kecamatan, "
            "status"
        ),
    )
    uttp_rows = fetch_all_rows(
        "uttp",
        (
            "id, "
            "perusahaan_id, "
            "spbu_id, "
            "jenis_uttp, "
            "merk, "
            "tipe, "
            "nomor_seri, "
            "kapasitas, "
            "satuan_kapasitas, "
            "daya_baca, "
            "satuan_daya_baca, "
            "interval_skala_verifikasi, "
            "kelas, "
            "lokasi, "
            "status"
        ),
    )

    pengujian_rows = fetch_all_rows(
        "pengujian",
        (
            "id, "
            "perusahaan_id, "
            "uttp_id, "
            "tanggal_pengujian, "
            "tanggal_sertifikat, "
            "jenis_pengujian, "
            "hasil, "
            "nomor_order, "
            "nomor_sertifikat, "
            "penera_1, "
            "penera_2, "
            "berlaku_sampai, "
            "jumlah_alat, "
            "data_pengujian"
        ),
    )

    relasi_rows = fetch_all_rows(
        "pengujian_uttp",
        (
            "id, "
            "pengujian_id, "
            "uttp_id, "
            "urutan, "
            "hasil, "
            "data_detail"
        ),
    )

    return (
        pd.DataFrame(
            perusahaan_rows
        ),
        pd.DataFrame(penera_rows),
        pd.DataFrame(
            spbu_rows
        ),
        pd.DataFrame(
            uttp_rows
        ),
        pd.DataFrame(
            pengujian_rows
        ),
        pd.DataFrame(
            relasi_rows
        ),
    )


# =========================================================
# UTILITAS
# =========================================================
def buat_lookup_kode_penera(
    df_penera,
):

    if df_penera.empty:
        return {}

    lookup = {}

    for _, row in df_penera.iterrows():

        nama = clean_text(
            row.get(
                "nama_penera"
            )
        )

        kode = clean_text(
            row.get(
                "kode_penera"
            )
        )

        if nama and kode:

            lookup[
                nama.lower()
            ] = kode

    return lookup
def format_kode_penera_laporan(
    penera_1,
    penera_2,
    lookup_kode,
):

    nama_1 = clean_text(
        penera_1
    )

    nama_2 = clean_text(
        penera_2
    )

    kode_1 = (
        lookup_kode.get(
            nama_1.lower(),
            ""
        )
        if nama_1
        else ""
    )

    kode_2 = (
        lookup_kode.get(
            nama_2.lower(),
            ""
        )
        if nama_2
        else ""
    )

    kode_list = [
        kode
        for kode
        in [
            kode_1,
            kode_2,
        ]
        if kode
    ]

    return " & ".join(
        kode_list
    )
def clean_text(value):

    if value is None:
        return ""

    try:
        if pd.isna(
            value
        ):
            return ""
    except Exception:
        pass

    text = str(
        value
    ).strip()

    if text.lower() in {
        "",
        "nan",
        "none",
        "null",
    }:
        return ""

    return text

def normalisasi_jenis_pengujian(value):

    text = (
        clean_text(value)
        .lower()
    )

    if "ulang" in text:
        return "TERA_ULANG"

    if "tera" in text:
        return "TERA"

    return ""
def kategori_laporan_dari_jenis_uttp(jenis_uttp):

    jenis = clean_text(
        jenis_uttp
    )

    mapping = (
        MAPPING_JENIS_LAPORAN.get(
            jenis
        )
    )

    if not mapping:
        return ""

    return mapping[0]
def kode_alat_laporan(jenis_uttp):

    jenis = clean_text(
        jenis_uttp
    )

    mapping = (
        MAPPING_JENIS_LAPORAN.get(
            jenis
        )
    )

    if not mapping:
        return ""

    return mapping[1]
def tentukan_lokasi_laporan(
    jenis_uttp,
    data_pengujian,
):

    jenis = (
        clean_text(
            jenis_uttp
        )
        .lower()
    )

    # =====================================================
    # MODUL YANG SELALU LUAR KANTOR
    # =====================================================
    if jenis in {
        "timbangan jembatan",
        "pompa ukur bbm",
        "kwh meter",
    }:
        return "Luar Kantor"

    # =====================================================
    # MODUL LAIN:
    # baca dari data_pengujian
    # =====================================================
    detail = (
        data_pengujian
        if isinstance(
            data_pengujian,
            dict,
        )
        else {}
    )

    lokasi_raw = (
        detail.get(
            "lokasi_pengujian"
        )
        or detail.get(
            "lokasi"
        )
        or detail.get(
            "jenis_lokasi"
        )
        or ""
    )

    lokasi_text = (
        clean_text(
            lokasi_raw
        )
        .lower()
    )

    if lokasi_text in {
        "dalam kantor",
        "kantor",
        "di kantor",
        "unit metrologi legal",
    }:
        return "Dalam Kantor"

    if lokasi_text in {
        "luar kantor",
        "perusahaan",
        "di perusahaan",
        "lokasi perusahaan",
        "lapangan",
    }:
        return "Luar Kantor"

    return ""
def format_tanggal(value):

    if value is None:
        return "-"

    tanggal = pd.to_datetime(
        value,
        errors="coerce",
    )

    if pd.isna(
        tanggal
    ):
        return "-"

    return tanggal.strftime(
        "%d-%m-%Y"
    )


def format_sisa_hari(value):

    if pd.isna(
        value
    ):
        return "-"

    try:
        value = int(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return "-"

    if value < 0:

        return (
            f"Lewat "
            f"{abs(value)} hari"
        )

    if value == 0:
        return "Hari ini"

    return (
        f"{value} hari"
    )


def kapasitas_text(row):

    kapasitas = clean_text(
        row.get(
            "kapasitas"
        )
    )

    satuan = clean_text(
        row.get(
            "satuan_kapasitas"
        )
    )

    if not kapasitas:
        return "-"

    return (
        f"{kapasitas} {satuan}"
    ).strip()


def daya_baca_text(row):

    daya_baca = row.get(
        "daya_baca"
    )

    if daya_baca is None:
        return "-"

    try:
        if pd.isna(
            daya_baca
        ):
            return "-"
    except Exception:
        pass

    satuan = clean_text(
        row.get(
            "satuan_daya_baca"
        )
    )

    return (
        f"{daya_baca} {satuan}"
    ).strip()


# =========================================================
# CEK HEADER PENGUJIAN UTTP UMUM
# =========================================================
def is_pengujian_uttp_umum(row):

    detail = row.get(
        "data_pengujian"
    )

    if not isinstance(
        detail,
        dict,
    ):
        return False

    schema = str(
        detail.get(
            "schema_uttp_umum",
            ""
        )
        or ""
    ).strip()

    return (
        schema == "1"
    )


# =========================================================
# STYLE
# =========================================================
def render_header():

    st.markdown(
        """
<style>
.dashboard-header {
    width: 100%;
    padding: 28px 30px;
    margin-bottom: 24px;
    border-radius: 16px;
    background: linear-gradient(
        135deg,
        #1E3A8A 0%,
        #2563EB 100%
    );
    box-shadow: 0 8px 20px rgba(15, 23, 42, 0.12);
}

.dashboard-header h1 {
    color: white;
    font-size: 31px;
    font-weight: 800;
    margin: 0 0 6px 0;
}

.dashboard-header p {
    color: rgba(255,255,255,0.92);
    font-size: 15px;
    margin: 0;
}

.kpi-card {
    background: white;
    border-radius: 14px;
    padding: 17px;
    min-height: 115px;
    border: 1px solid #E2E8F0;
    box-shadow: 0 4px 12px rgba(15,23,42,0.06);
}

.kpi-title {
    font-size: 13px;
    font-weight: 600;
    color: #64748B;
    margin-bottom: 8px;
}

.kpi-value {
    font-size: 29px;
    font-weight: 800;
    color: #0F172A;
    line-height: 1.1;
}

.kpi-sub {
    font-size: 12px;
    color: #94A3B8;
    margin-top: 6px;
}
/* =====================================================
   KPI CLICKABLE
   ===================================================== */

div[data-testid="stButton"] > button {
    border-radius: 10px;
    font-weight: 650;
    transition:
        transform 0.18s ease,
        box-shadow 0.18s ease,
        border-color 0.18s ease;
}

div[data-testid="stButton"] > button:hover {
    transform: translateY(-1px);
    box-shadow:
        0 5px 14px
        rgba(15, 23, 42, 0.08);
}

div[data-testid="stButton"] > button p {
    white-space: pre-line;
    line-height: 1.35;
}
/* =====================================================
   KHUSUS KPI CLICKABLE
   ===================================================== */

div[data-testid="stVerticalBlockBorderWrapper"]
div[data-testid="stButton"] > button {
    min-height: 92px;
    border-radius: 12px;
    font-weight: 700;
    padding: 12px 14px;
}

div[data-testid="stVerticalBlockBorderWrapper"]
div[data-testid="stButton"] > button p {
    white-space: pre-line;
    line-height: 1.45;
    font-size: 14px;
}

div[data-testid="stVerticalBlockBorderWrapper"]
div[data-testid="stButton"] > button:hover {
    transform: translateY(-2px);
    box-shadow:
        0 8px 18px
        rgba(15, 23, 42, 0.10);
}
.company-card {
    background: #F8FAFC;
    padding: 18px 20px;
    border-radius: 14px;
    border-left: 6px solid #2563EB;
    margin-bottom: 15px;
}
</style>

<div class="dashboard-header"><h1>⚖️ Dashboard Monitoring UTTP SMART METRO</h1><p>Monitoring seluruh UTTP, status tera/tera ulang, masa berlaku, riwayat pengujian, dan prioritas pengawasan.</p></div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi(
    title,
    value,
    subtitle,
    color,
):

    title_safe = html.escape(
        str(title)
    )

    value_safe = html.escape(
        str(value)
    )

    subtitle_safe = html.escape(
        str(subtitle)
    )

    card_html = (
        f'<div class="kpi-card" '
        f'style="border-top:5px solid {color};">'
        f'<div class="kpi-title">{title_safe}</div>'
        f'<div class="kpi-value">{value_safe}</div>'
        f'<div class="kpi-sub">{subtitle_safe}</div>'
        f'</div>'
    )

    st.markdown(
        card_html,
        unsafe_allow_html=True,
    )

def render_kpi_button(
    title,
    value,
    subtitle,
    color,
    key,
    mode,
):
    """
    KPI card interaktif.
    """

    aktif = (
        st.session_state.get(
            "dashboard_uttp_mode",
            "total_uttp",
        )
        == mode
    )

    status_aktif = (
        "● "
        if aktif
        else ""
    )

    label = (
        f"{status_aktif}{title}\n"
        f"**{value}**\n"
        f"{subtitle}"
    )

    with st.container(
        border=True
    ):

        st.markdown(
            f"""
            <div style="
                height:5px;
                width:100%;
                background:{color};
                border-radius:999px;
                margin-bottom:7px;
            ">
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(
            label,
            key=key,
            use_container_width=True,
            type=(
                "primary"
                if aktif
                else "secondary"
            ),
        ):

            st.session_state[
                "dashboard_uttp_mode"
            ] = mode

            st.session_state[
                "dashboard_uttp_page"
            ] = 1

            st.rerun()
def render_tabel_ringkasan_pemilik(
    data,
    title,
    color="#2563EB",
):
    """
    Ringkasan UTTP per pemilik / lokasi.
    1 pemilik = 1 baris.
    """

    if data.empty:
        st.info(
            "Tidak ada data yang dapat ditampilkan."
        )
        return

    # =====================================================
    # AGREGASI PER PEMILIK
    # =====================================================
    ringkasan = (
        data
        .groupby(
            [
                "pemilik_key",
                "pemilik_display",
            ],
            dropna=False,
        )[
            "uttp_id"
        ]
        .nunique()
        .rename(
            "Jumlah UTTP"
        )
        .reset_index()
        .sort_values(
            [
                "Jumlah UTTP",
                "pemilik_display",
            ],
            ascending=[
                False,
                True,
            ],
        )
        .reset_index(
            drop=True
        )
    )

    ringkasan[
        "pemilik_display"
    ] = ringkasan[
        "pemilik_display"
    ].fillna(
        "Pemilik Belum Diketahui"
    )

    total_pemilik = len(
        ringkasan
    )

    total_uttp = int(
        ringkasan[
            "Jumlah UTTP"
        ].sum()
    )

    # =====================================================
    # PAGINATION
    # =====================================================
    per_page = 10

    total_page = max(
        1,
        (
            total_pemilik
            + per_page
            - 1
        )
        // per_page
    )

    halaman = int(
        st.session_state.get(
            "dashboard_uttp_page",
            1,
        )
    )

    halaman = max(
        1,
        min(
            halaman,
            total_page,
        )
    )

    st.session_state[
        "dashboard_uttp_page"
    ] = halaman

    start = (
        halaman - 1
    ) * per_page

    end = (
        start
        + per_page
    )

    tampil = (
        ringkasan
        .iloc[
            start:end
        ]
        .copy()
    )

    tampil.insert(
        0,
        "No.",
        range(
            start + 1,
            start + 1 + len(tampil),
        ),
    )

    tampil = tampil[
        [
            "No.",
            "pemilik_key",
            "pemilik_display",
            "Jumlah UTTP",
        ]
    ]

    tampil.columns = [
        "No.",
        "pemilik_key",
        "Pemilik / Lokasi",
        "Jumlah UTTP",
    ]

    # =====================================================
    # HEADER TABEL
    # =====================================================
    st.html(
        f"""
        <div style="
            background:white;
            border:1px solid #E2E8F0;
            border-left:6px solid {color};
            border-radius:14px;
            padding:16px 18px;
            margin-top:18px;
            margin-bottom:10px;
        ">
            <div style="
                font-size:18px;
                font-weight:800;
                color:#0F172A;
            ">
                {html.escape(title)}
            </div>

            <div style="
                font-size:13px;
                color:#64748B;
                margin-top:4px;
            ">
                {total_pemilik:,} pemilik / lokasi
                •
                {total_uttp:,} UTTP
            </div>
        </div>
        """,
    )

    # =====================================================
    # TABEL RINGKASAN - DASHBOARD STYLE
    # =====================================================
    nilai_maks = max(
        1,
        int(
            ringkasan[
                "Jumlah UTTP"
            ].max()
        )
    )

    rows_html = ""

    for _, row in tampil.iterrows():

        nomor = int(
            row["No."]
        )

        nama = (
            clean_text(
                row[
                    "Pemilik / Lokasi"
                ]
            )
            or "Pemilik Belum Diketahui"
        )

        jumlah = int(
            row[
                "Jumlah UTTP"
            ]
        )

        persen = min(
            100,
            (
                jumlah
                / nilai_maks
                * 100
            ),
        )

        rows_html += f"""
        <div style="
            display:grid;
            grid-template-columns:60px 1fr 180px;
            align-items:center;
            gap:14px;
            padding:13px 16px;
            border-bottom:1px solid #F1F5F9;
        ">

            <div style="
                display:flex;
                align-items:center;
                justify-content:center;
            ">
                <div style="
                    width:30px;
                    height:30px;
                    border-radius:50%;
                    background:#F1F5F9;
                    color:#475569;
                    display:flex;
                    align-items:center;
                    justify-content:center;
                    font-size:12px;
                    font-weight:800;
                ">
                    {nomor}
                </div>
            </div>

            <div style="
                font-size:14px;
                font-weight:650;
                color:#0F172A;
            ">
                {html.escape(nama)}
            </div>

            <div>
                <div style="
                    display:flex;
                    align-items:center;
                    justify-content:space-between;
                    margin-bottom:5px;
                ">
                    <span style="
                        font-size:12px;
                        color:#64748B;
                    ">
                        Jumlah UTTP
                    </span>

                    <span style="
                        font-size:13px;
                        font-weight:800;
                        color:{color};
                    ">
                        {jumlah}
                    </span>
                </div>

                <div style="
                    width:100%;
                    height:7px;
                    border-radius:999px;
                    background:#E2E8F0;
                    overflow:hidden;
                ">
                    <div style="
                        width:{persen:.1f}%;
                        height:100%;
                        background:{color};
                        border-radius:999px;
                    ">
                    </div>
                </div>
            </div>

        </div>
        """

    table_html = f"""
    <div style="
        background:#FFFFFF;
        border:1px solid #E2E8F0;
        border-radius:14px;
        overflow:hidden;
        box-shadow:0 4px 14px rgba(15,23,42,0.05);
        margin-bottom:12px;
    ">

        <div style="
            display:grid;
            grid-template-columns:60px 1fr 180px;
            gap:14px;
            padding:11px 16px;
            background:#F8FAFC;
            border-bottom:1px solid #E2E8F0;
            font-size:12px;
            font-weight:800;
            color:#64748B;
            text-transform:uppercase;
            letter-spacing:0.4px;
        ">
            <div style="text-align:center;">
                No.
            </div>

            <div>
                Pemilik / Lokasi
            </div>

            <div>
                Jumlah UTTP
            </div>
        </div>

        {rows_html}

    </div>
    """

    st.html(
        table_html,
    )
    # =====================================================
    # BUKA DETAIL PEMILIK / LOKASI
    # =====================================================
    pilihan_detail = {
        str(row["Pemilik / Lokasi"]):
        row["pemilik_key"]

        for _, row
        in tampil.iterrows()
    }

    if pilihan_detail:

        col_pilih, col_buka = st.columns(
            [4, 1]
        )

        with col_pilih:

            nama_detail = st.selectbox(
                "Lihat detail Pemilik / Lokasi",
                options=[
                    ""
                ]
                + list(
                    pilihan_detail.keys()
                ),
                key="pilih_detail_ringkasan_uttp",
            )

        with col_buka:

            st.markdown(
                "<div style='height:28px'></div>",
                unsafe_allow_html=True,
            )

            if st.button(
                "Buka Detail →",
                key="btn_buka_detail_ringkasan",
                use_container_width=True,
                disabled=(
                    not nama_detail
                ),
            ):

                st.session_state[
                    "dashboard_uttp_pemilik_detail"
                ] = pilihan_detail[
                    nama_detail
                ]

                st.rerun()
    # =====================================================
    # NAVIGASI HALAMAN
    # =====================================================
    b1, b2, b3 = st.columns(
        [
            1,
            2,
            1,
        ]
    )

    with b1:

        if st.button(
            "← Sebelumnya",
            disabled=(
                halaman <= 1
            ),
            use_container_width=True,
            key="btn_ringkasan_prev",
        ):

            st.session_state[
                "dashboard_uttp_page"
            ] = halaman - 1

            st.rerun()

    with b2:

        st.markdown(
            f"""
            <div style="
                text-align:center;
                padding-top:8px;
                font-size:13px;
                color:#64748B;
            ">
                Halaman <b>{halaman}</b>
                dari <b>{total_page}</b>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with b3:

        if st.button(
            "Selanjutnya →",
            disabled=(
                halaman >= total_page
            ),
            use_container_width=True,
            key="btn_ringkasan_next",
        ):

            st.session_state[
                "dashboard_uttp_page"
            ] = halaman + 1

            st.rerun()
# =========================================================
# BUILD MONITORING
# =========================================================
def build_monitoring_data(
    df_perusahaan,
    df_spbu,
    df_uttp,
    df_pengujian,
    df_relasi,
):

    if df_uttp.empty:

        return (
            pd.DataFrame(),
            pd.DataFrame(),
        )

    # =====================================================
    # MASTER PERUSAHAAN
    # =====================================================
    perusahaan = (
        df_perusahaan.copy()
        if not df_perusahaan.empty
        else pd.DataFrame()
    )

    if perusahaan.empty:

        perusahaan = pd.DataFrame(
            columns=[
                "perusahaan_id",
                "nama_perusahaan",
                "alamat",
            ]
        )

    else:

        perusahaan = perusahaan.rename(
            columns={
                "id":
                "perusahaan_id"
            }
        )
    # =====================================================
    # MASTER SPBU
    # =====================================================
    spbu = (
        df_spbu.copy()
        if not df_spbu.empty
        else pd.DataFrame()
    )

    if spbu.empty:

        spbu = pd.DataFrame(
            columns=[
                "spbu_id",
                "nama_spbu",
                "nomor_spbu",
                "alamat_spbu",
                "jenis_lokasi",
                "kecamatan",
            ]
        )

    else:

        spbu = spbu.rename(
            columns={
                "id": "spbu_id",
                "alamat": "alamat_spbu",
            }
        )

        spbu[
            "spbu_id"
        ] = pd.to_numeric(
            spbu["spbu_id"],
            errors="coerce",
        )
    # =====================================================
    # LOOKUP KODE PENERA
    # =====================================================
    lookup_kode_penera = (
        buat_lookup_kode_penera(
            df_penera
        )
    )
    # =====================================================
    # MASTER UTTP
    # =====================================================
    master = df_uttp.copy()

    if (
        "perusahaan_id"
        not in master.columns
    ):
        master[
            "perusahaan_id"
        ] = None

    if (
        "spbu_id"
        not in master.columns
    ):
        master[
            "spbu_id"
        ] = None

    # =====================================================
    # UTTP SMART METRO
    #
    # Alat boleh dimiliki perusahaan ATAU terkait SPBU.
    # =====================================================
    master = master[
        (
            master[
                "perusahaan_id"
            ].notna()
        )
        |
        (
            master[
                "spbu_id"
            ].notna()
        )
    ].copy()

    # =====================================================
    # HANYA MASTER AKTIF
    # =====================================================
    if (
        "status"
        in master.columns
    ):

        status_master = (
            master["status"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
        )

        master = master[
            status_master.eq("")
            |
            status_master.eq(
                "aktif"
            )
        ].copy()

    master[
        "uttp_id"
    ] = pd.to_numeric(
        master["id"],
        errors="coerce",
    )

    master[
        "perusahaan_id"
    ] = pd.to_numeric(
        master[
            "perusahaan_id"
        ],
        errors="coerce",
    )
    master[
        "spbu_id"
    ] = pd.to_numeric(
        master[
            "spbu_id"
        ],
        errors="coerce",
    )
    perusahaan[
        "perusahaan_id"
    ] = pd.to_numeric(
        perusahaan[
            "perusahaan_id"
        ],
        errors="coerce",
    )

    # =====================================================
    # GABUNG MASTER PERUSAHAAN
    # =====================================================
    monitor = master.merge(
        perusahaan[
            [
                "perusahaan_id",
                "nama_perusahaan",
                "alamat",
            ]
        ],
        on="perusahaan_id",
        how="left",
    )

    # =====================================================
    # GABUNG MASTER SPBU
    # =====================================================
    monitor = monitor.merge(
        spbu[
            [
                "spbu_id",
                "nama_spbu",
                "nomor_spbu",
                "alamat_spbu",
                "jenis_lokasi",
                "kecamatan",
            ]
        ],
        on="spbu_id",
        how="left",
    )

    # =====================================================
    # IDENTITAS PEMILIK / LOKASI
    #
    # Jika alat PUBBM → gunakan master SPBU.
    # Selain itu → gunakan master perusahaan.
    # =====================================================
    monitor[
        "pemilik_display"
    ] = monitor.apply(
        lambda row: (
            clean_text(
                row.get(
                    "nama_spbu"
                )
            )
            if pd.notna(
                row.get(
                    "spbu_id"
                )
            )
            else clean_text(
                row.get(
                    "nama_perusahaan"
                )
            )
        ),
        axis=1,
    )

    monitor[
        "alamat_display"
    ] = monitor.apply(
        lambda row: (
            clean_text(
                row.get(
                    "alamat_spbu"
                )
            )
            if pd.notna(
                row.get(
                    "spbu_id"
                )
            )
            else clean_text(
                row.get(
                    "alamat"
                )
            )
        ),
        axis=1,
    )

    # =====================================================
    # KEY PEMILIK
    #
    # Prefix dibedakan agar:
    # perusahaan ID 10 != SPBU ID 10
    # =====================================================
    def buat_pemilik_key(row):

        if pd.notna(
            row.get(
                "spbu_id"
            )
        ):
            return (
                f"SPBU:{int(row['spbu_id'])}"
            )

        if pd.notna(
            row.get(
                "perusahaan_id"
            )
        ):
            return (
                f"PERUSAHAAN:"
                f"{int(row['perusahaan_id'])}"
            )

        return (
            f"UTTP:{int(row['uttp_id'])}"
        )

    monitor[
        "pemilik_key"
    ] = monitor.apply(
        buat_pemilik_key,
        axis=1,
    )

    # =====================================================
    # PENGUJIAN SELURUH MODUL UTTP
    #
    # Dashboard tidak lagi bergantung pada schema tertentu.
    # Selama pengujian terhubung ke master UTTP,
    # riwayat dianggap valid.
    # =====================================================
    if df_pengujian.empty:

        pengujian_all = pd.DataFrame()

    else:

        pengujian_all = (
            df_pengujian.copy()
        )

    # =====================================================
    # BELUM ADA PENGUJIAN SAMA SEKALI
    # =====================================================
    if pengujian_all.empty:

        monitor[
            "status_tera"
        ] = STATUS_BELUM_UJI

        monitor[
            "jumlah_pengujian"
        ] = 0

        for col in [
            "pengujian_id_terakhir",
            "tanggal_pengujian",
            "tanggal_sertifikat",
            "jenis_pengujian",
            "hasil_pengujian",
            "nomor_order",
            "nomor_sertifikat",
            "penera_1",
            "penera_2",
            "berlaku_sampai",
            "sisa_hari",
        ]:
            monitor[col] = None

        return (
            monitor,
            pd.DataFrame(),
        )

    # =====================================================
    # SIAPKAN HEADER PENGUJIAN
    # =====================================================
    pengujian_all = (
        pengujian_all
        .rename(
            columns={
                "id":
                "pengujian_id",

                "hasil":
                "hasil_pengujian",
            }
        )
        .copy()
    )

    pengujian_all[
        "pengujian_id"
    ] = pd.to_numeric(
        pengujian_all[
            "pengujian_id"
        ],
        errors="coerce",
    )

    if (
        "uttp_id"
        not in pengujian_all.columns
    ):
        pengujian_all[
            "uttp_id"
        ] = None

    pengujian_all[
        "uttp_id"
    ] = pd.to_numeric(
        pengujian_all[
            "uttp_id"
        ],
        errors="coerce",
    )

    pengujian_all[
        "tanggal_pengujian_dt"
    ] = pd.to_datetime(
        pengujian_all[
            "tanggal_pengujian"
        ],
        errors="coerce",
    )

    pengujian_all[
        "berlaku_sampai_dt"
    ] = pd.to_datetime(
        pengujian_all[
            "berlaku_sampai"
        ],
        errors="coerce",
    )

    pengujian_all[
        "pengujian_id_num"
    ] = pd.to_numeric(
        pengujian_all[
            "pengujian_id"
        ],
        errors="coerce",
    ).fillna(0)

    # =====================================================
    # ID MASTER UTTP YANG MEMANG MASUK DASHBOARD
    # =====================================================
    master_uttp_ids = set(
        monitor[
            "uttp_id"
        ]
        .dropna()
        .tolist()
    )

    history_parts = []

    # =====================================================
    # 1. HISTORY MELALUI pengujian_uttp
    #
    # Dipakai UTTP Umum, Timbangan, TUM,
    # Meter Air, dan modul struktur baru lainnya.
    # =====================================================
    if not df_relasi.empty:

        relasi = (
            df_relasi.copy()
        )

        relasi[
            "pengujian_id"
        ] = pd.to_numeric(
            relasi[
                "pengujian_id"
            ],
            errors="coerce",
        )

        relasi[
            "uttp_id"
        ] = pd.to_numeric(
            relasi[
                "uttp_id"
            ],
            errors="coerce",
        )

        # Hanya relasi milik master yang tampil
        # pada dashboard ini.
        relasi = relasi[
            relasi[
                "uttp_id"
            ].isin(
                master_uttp_ids
            )
        ].copy()

        if not relasi.empty:

            # uttp_id dari relasi adalah sumber utama.
            header_relasi = (
                pengujian_all
                .drop(
                    columns=[
                        "uttp_id"
                    ],
                    errors="ignore",
                )
            )

            history_relasi = (
                relasi[
                    [
                        "pengujian_id",
                        "uttp_id",
                    ]
                ]
                .merge(
                    header_relasi,
                    on="pengujian_id",
                    how="left",
                    validate="many_to_one",
                )
            )

            history_parts.append(
                history_relasi
            )

    # =====================================================
    # 2. HISTORY DARI pengujian.uttp_id
    #
    # Fallback untuk modul yang menyimpan relasi langsung
    # pada header pengujian.
    # =====================================================
    history_direct = (
        pengujian_all[
            pengujian_all[
                "uttp_id"
            ].isin(
                master_uttp_ids
            )
        ]
        .copy()
    )

    if not history_direct.empty:

        history_parts.append(
            history_direct
        )

    # =====================================================
    # GABUNGKAN SELURUH HISTORY
    # =====================================================
    if history_parts:

        history = pd.concat(
            history_parts,
            ignore_index=True,
            sort=False,
        )

        # Pengujian yang mempunyai pengujian.uttp_id
        # sekaligus pengujian_uttp tidak boleh dihitung 2 kali.
        history = (
            history
            .drop_duplicates(
                subset=[
                    "pengujian_id",
                    "uttp_id",
                ],
                keep="last",
            )
            .copy()
        )

    else:

        history = pd.DataFrame()

    # =====================================================
    # MASTER ADA, TETAPI BELUM PUNYA RIWAYAT
    # =====================================================
    if history.empty:

        monitor[
            "status_tera"
        ] = STATUS_BELUM_UJI

        monitor[
            "jumlah_pengujian"
        ] = 0

        for col in [
            "pengujian_id_terakhir",
            "tanggal_pengujian",
            "tanggal_sertifikat",
            "jenis_pengujian",
            "hasil_pengujian",
            "nomor_order",
            "nomor_sertifikat",
            "penera_1",
            "penera_2",
            "berlaku_sampai",
            "sisa_hari",
        ]:
            monitor[col] = None

        return (
            monitor,
            history,
        )

    # =====================================================
    # JUMLAH PENGUJIAN
    # =====================================================
    jumlah_pengujian = (
        history
        .groupby(
            "uttp_id"
        )
        .size()
        .rename(
            "jumlah_pengujian"
        )
        .reset_index()
    )

    # =====================================================
    # PENGUJIAN TERAKHIR
    # =====================================================
    latest = (
        history
        .sort_values(
            [
                "uttp_id",
                "tanggal_pengujian_dt",
                "pengujian_id_num",
            ],
            na_position="first",
        )
        .groupby(
            "uttp_id",
            as_index=False,
        )
        .tail(1)
        .copy()
    )

    today = pd.Timestamp(
        date.today()
    )

    latest[
        "sisa_hari"
    ] = (
        latest[
            "berlaku_sampai_dt"
        ].dt.normalize()
        - today
    ).dt.days

    # =====================================================
    # STATUS TERA
    # =====================================================
    def hitung_status(row):

        berlaku = row.get(
            "berlaku_sampai_dt"
        )

        if pd.isna(
            berlaku
        ):
            return (
                STATUS_DATA_KURANG
            )

        sisa = row.get(
            "sisa_hari"
        )

        if pd.isna(
            sisa
        ):
            return (
                STATUS_DATA_KURANG
            )

        if sisa < 0:

            return (
                STATUS_KEDALUWARSA
            )

        if (
            sisa
            <= BATAS_JATUH_TEMPO_HARI
        ):

            return (
                STATUS_JATUH_TEMPO
            )

        return STATUS_AKTIF

    latest[
        "status_tera"
    ] = latest.apply(
        hitung_status,
        axis=1,
    )

    latest = latest[
        [
            "uttp_id",
            "pengujian_id",
            "tanggal_pengujian",
            "tanggal_sertifikat",
            "jenis_pengujian",
            "hasil_pengujian",
            "nomor_order",
            "nomor_sertifikat",
            "penera_1",
            "penera_2",
            "berlaku_sampai",
            "sisa_hari",
            "status_tera",
        ]
    ]

    latest = latest.rename(
        columns={
            "pengujian_id":
            "pengujian_id_terakhir"
        }
    )

    monitor = monitor.merge(
        latest,
        on="uttp_id",
        how="left",
    )

    monitor = monitor.merge(
        jumlah_pengujian,
        on="uttp_id",
        how="left",
    )

    monitor[
        "status_tera"
    ] = monitor[
        "status_tera"
    ].fillna(
        STATUS_BELUM_UJI
    )

    monitor[
        "jumlah_pengujian"
    ] = pd.to_numeric(
        monitor[
            "jumlah_pengujian"
        ],
        errors="coerce",
    ).fillna(
        0
    ).astype(
        int
    )

    return (
        monitor,
        history,
    )

# =========================================================
# DETAIL PERUSAHAAN
# =========================================================
def render_detail_perusahaan(
    company_df,
    history,
):

    if company_df.empty:

        st.info(
            "Tidak ada UTTP "
            "sesuai filter."
        )

        return

    first = (
        company_df.iloc[0]
    )

    nama_perusahaan = (
        clean_text(
            first.get(
                "pemilik_display"
            )
        )
        or "Pemilik / Lokasi"
    )

    alamat = (
        clean_text(
            first.get(
                "alamat_display"
            )
        )
        or "-"
    )

    tipe_pemilik = (
        "SPBU"
        if pd.notna(
            first.get(
                "spbu_id"
            )
        )
        else "Perusahaan"
    )

    nomor_spbu = (
        clean_text(
            first.get(
                "nomor_spbu"
            )
        )
    )

    info_spbu_html = ""

    if nomor_spbu:
        info_spbu_html = (
            '<b>Nomor SPBU:</b> '
            f'{html.escape(nomor_spbu)}'
            '<br>'
        )
    # =====================================================
    # CARD PERUSAHAAN
    # =====================================================
    company_html = (
        '<div class="company-card">'
        '<div style="'
        'font-size:22px;'
        'font-weight:800;'
        'color:#0F172A;'
        '">'
        f'🏢 {html.escape(nama_perusahaan)}'
        '</div>'
        '<div style="'
        'font-size:13px;'
        'color:#475569;'
        'margin-top:6px;'
        '">'
        '<b>Tipe:</b> '
        f'{html.escape(tipe_pemilik)}'
        '<br>'
        f'{info_spbu_html}'
        '<b>Alamat:</b> '
        f'{html.escape(alamat)}'
        '</div>'
        '</div>'
    )
    
    st.markdown(
        company_html,
        unsafe_allow_html=True,
    )

    # =====================================================
    # KPI PERUSAHAAN
    # =====================================================
    total_uttp = (
        company_df[
            "uttp_id"
        ].nunique()
    )

    tera_aktif = int(
        (
            company_df[
                "status_tera"
            ]
            == STATUS_AKTIF
        ).sum()
    )

    akan_habis = int(
        (
            company_df[
                "status_tera"
            ]
            == STATUS_JATUH_TEMPO
        ).sum()
    )

    kedaluwarsa = int(
        (
            company_df[
                "status_tera"
            ]
            == STATUS_KEDALUWARSA
        ).sum()
    )

    belum_uji = int(
        (
            company_df[
                "status_tera"
            ]
            == STATUS_BELUM_UJI
        ).sum()
    )
    data_kurang = int(
        (
            company_df[
                "status_tera"
            ]
            == STATUS_DATA_KURANG
        ).sum()
    )
    c1, c2, c3, c4, c5, c6 = (
        st.columns(6)
    )

    with c1:

        render_kpi(
            "Total UTTP",
            total_uttp,
            "Seluruh alat",
            "#2563EB",
        )

    with c2:

        render_kpi(
            "Tera Aktif",
            tera_aktif,
            "Masih berlaku",
            "#16A34A",
        )

    with c3:

        render_kpi(
            f"≤ {BATAS_JATUH_TEMPO_HARI} Hari",
            akan_habis,
            "Akan habis",
            "#F59E0B",
        )

    with c4:

        render_kpi(
            "Kedaluwarsa",
            kedaluwarsa,
            "Perlu tindak lanjut",
            "#DC2626",
        )

    with c5:

        render_kpi(
            "Belum Uji",
            belum_uji,
            "Belum ada riwayat",
            "#64748B",
        )
    with c6:

        render_kpi(
            "Data Belum Lengkap",
            data_kurang,
            "Perlu verifikasi",
            "#475569",
        )

    # =====================================================
    # TOTAL PER JENIS UTTP
    # =====================================================
    st.markdown("---")

    st.subheader(
        "📊 Komposisi UTTP Pemilik / Lokasi"
    )

    jenis_count = (
        company_df
        .assign(
            jenis_display=(
                company_df[
                    "jenis_uttp"
                ]
                .fillna("")
                .astype(str)
                .str.strip()
                .replace(
                    "",
                    "Jenis Belum Diisi",
                )
            )
        )
        .groupby(
            "jenis_display"
        )[
            "uttp_id"
        ]
        .nunique()
        .sort_values(
            ascending=False
        )
        .rename(
            "Jumlah UTTP"
        )
        .reset_index()
    )

    jenis_count.columns = [
        "Jenis UTTP",
        "Jumlah UTTP",
    ]

    if not jenis_count.empty:

        jumlah_jenis = len(
            jenis_count
        )

        total_dalam_grafik = int(
            jenis_count[
                "Jumlah UTTP"
            ].sum()
        )

        tinggi_chart = min(
            max(
                220,
                jumlah_jenis * 34
            ),
            420
        )

        nilai_maks = max(
            1,
            int(
                jenis_count[
                    "Jumlah UTTP"
                ].max()
            )
        )

        st.caption(
            f"{total_dalam_grafik:,} UTTP "
            f"• {jumlah_jenis} jenis alat"
        )

        base = (
            alt.Chart(
                jenis_count
            )
            .encode(
                y=alt.Y(
                    "Jenis UTTP:N",
                    sort="-x",
                    title=None,
                    axis=alt.Axis(
                        labelLimit=220,
                        labelFontSize=12,
                    ),
                ),

                x=alt.X(
                    "Jumlah UTTP:Q",
                    title="Jumlah UTTP",
                    scale=alt.Scale(
                        domain=[
                            0,
                            nilai_maks * 1.18,
                        ]
                    ),
                    axis=alt.Axis(
                        tickMinStep=1,
                        grid=True,
                    ),
                ),

                tooltip=[
                    alt.Tooltip(
                        "Jenis UTTP:N",
                        title="Jenis UTTP",
                    ),
                    alt.Tooltip(
                        "Jumlah UTTP:Q",
                        title="Jumlah",
                        format=",.0f",
                    ),
                ],
            )
        )

        bar = base.mark_bar(
            size=22,
            cornerRadiusEnd=7,
            color="#2563EB",
        )

        label = (
            base
            .mark_text(
                align="left",
                baseline="middle",
                dx=7,
                fontSize=12,
                fontWeight="bold",
                color="#334155",
            )
            .encode(
                text=alt.Text(
                    "Jumlah UTTP:Q",
                    format=".0f",
                )
            )
        )

        chart = (
            bar
            + label
        ).properties(
            height=tinggi_chart
        )

        st.altair_chart(
            chart,
            use_container_width=True,
        )

    # =====================================================
    # DAFTAR UTTP PERUSAHAAN
    # =====================================================
    st.markdown("---")

    st.subheader(
        "⚖️ Daftar UTTP Pemilik / Lokasi"
    )

    daftar = company_df.copy()

    daftar[
        "kapasitas_tampil"
    ] = daftar.apply(
        kapasitas_text,
        axis=1,
    )

    daftar[
        "tanggal_tampil"
    ] = daftar[
        "tanggal_pengujian"
    ].apply(
        format_tanggal
    )

    daftar[
        "berlaku_tampil"
    ] = daftar[
        "berlaku_sampai"
    ].apply(
        format_tanggal
    )

    daftar[
        "merk_model"
    ] = daftar.apply(
        lambda row: (
            f"{clean_text(row.get('merk'))}"
            f" / "
            f"{clean_text(row.get('tipe'))}"
        ).strip(" /"),
        axis=1,
    )

    view = daftar[
        [
            "jenis_uttp",
            "merk_model",
            "nomor_seri",
            "status_tera",
            "berlaku_tampil",
        ]
    ].copy()
    view.columns = [
        "Jenis UTTP",
        "Merek / Model",
        "Nomor Seri",
        "Status",
        "Berlaku Sampai",
    ]

    st.dataframe(
        view,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Jenis UTTP":
                st.column_config.TextColumn(
                    "Jenis UTTP",
                    width="medium",
                ),

            "Merek / Model":
                st.column_config.TextColumn(
                    "Merek / Model",
                    width="medium",
                ),

            "Nomor Seri":
                st.column_config.TextColumn(
                    "Nomor Seri",
                    width="medium",
                ),

            "Status":
                st.column_config.TextColumn(
                    "Status",
                    width="medium",
                ),

            "Berlaku Sampai":
                st.column_config.TextColumn(
                    "Berlaku Sampai",
                    width="small",
                ),
        },
    )

    # =====================================================
    # PILIH SATU UTTP
    # =====================================================
    st.markdown("---")

    st.subheader(
        "🔎 Detail UTTP"
    )

    pilihan_uttp = {}

    for _, row in (
        company_df.iterrows()
    ):

        uttp_id = row.get(
            "uttp_id"
        )

        if pd.isna(
            uttp_id
        ):
            continue

        jenis = (
            clean_text(
                row.get(
                    "jenis_uttp"
                )
            )
            or "UTTP"
        )

        merk = (
            clean_text(
                row.get(
                    "merk"
                )
            )
            or "-"
        )

        nomor_seri = (
            clean_text(
                row.get(
                    "nomor_seri"
                )
            )
            or "-"
        )

        label = (
            f"{jenis} | "
            f"{merk} | "
            f"No. Seri {nomor_seri}"
        )

        pilihan_uttp[
            label
        ] = uttp_id

    pilih = st.selectbox(
        "Pilih UTTP untuk melihat detail",
        options=[
            ""
        ]
        + list(
            pilihan_uttp.keys()
        ),
        key="dashboard_uttp_detail",
    )

    if not pilih:
        return

    selected_id = (
        pilihan_uttp[
            pilih
        ]
    )

    selected = company_df[
        company_df[
            "uttp_id"
        ]
        == selected_id
    ]

    if selected.empty:
        return

    info = (
        selected.iloc[0]
    )

    status = info.get(
        "status_tera",
        STATUS_BELUM_UJI,
    )

    color = STATUS_COLOR.get(
        status,
        "#64748B",
    )

    # =====================================================
    # CARD ALAT
    # =====================================================
    jenis_uttp_tampil = (
        clean_text(
            info.get("jenis_uttp")
        )
        or "UTTP"
    )
    
    merk_tampil = (
        clean_text(
            info.get("merk")
        )
        or "-"
    )
    
    tipe_tampil = (
        clean_text(
            info.get("tipe")
        )
        or "-"
    )
    
    nomor_seri_tampil = (
        clean_text(
            info.get("nomor_seri")
        )
        or "-"
    )
    
    kelas_tampil = (
        clean_text(
            info.get("kelas")
        )
        or "-"
    )
    
    kapasitas_tampil = (
        kapasitas_text(
            info
        )
    )
    
    daya_baca_tampil = (
        daya_baca_text(
            info
        )
    )
    
    alat_html = (
        '<div style="'
        'background:#F8FAFC;'
        'padding:18px 20px;'
        'border-radius:14px;'
        f'border-left:6px solid {color};'
        '">'
    
        '<div style="'
        'font-size:21px;'
        'font-weight:800;'
        'color:#0F172A;'
        '">'
        f'⚖️ {html.escape(jenis_uttp_tampil)}'
        '</div>'
    
        '<div style="'
        'font-size:13px;'
        'color:#475569;'
        'margin-top:6px;'
        '">'
    
        '<b>Merek:</b> '
        f'{html.escape(merk_tampil)}'
        '<br>'
    
        '<b>Model / Tipe:</b> '
        f'{html.escape(tipe_tampil)}'
        '<br>'
    
        '<b>Nomor Seri:</b> '
        f'{html.escape(nomor_seri_tampil)}'
        '<br>'
    
        '<b>Kapasitas:</b> '
        f'{html.escape(kapasitas_tampil)}'
        '<br>'
    
        '<b>Daya Baca:</b> '
        f'{html.escape(daya_baca_tampil)}'
        '<br>'
    
        '<b>Kelas:</b> '
        f'{html.escape(kelas_tampil)}'
        '<br>'
    
        '<b>Status Tera:</b> '
        '<span style="'
        f'color:{color};'
        'font-weight:800;'
        '">'
        f'{html.escape(str(status))}'
        '</span>'
    
        '</div>'
        '</div>'
    )
    
    st.markdown(
        alat_html,
        unsafe_allow_html=True,
    )
    # =====================================================
    # INFO MASA TERA
    # =====================================================
    d1, d2, d3, d4 = (
        st.columns(4)
    )

    d1.metric(
        "Pengujian Terakhir",
        format_tanggal(
            info.get(
                "tanggal_pengujian"
            )
        ),
    )

    d2.metric(
        "Berlaku Sampai",
        format_tanggal(
            info.get(
                "berlaku_sampai"
            )
        ),
    )

    d3.metric(
        "Sisa Masa Tera",
        format_sisa_hari(
            info.get(
                "sisa_hari"
            )
        ),
    )

    d4.metric(
        "Jumlah Riwayat",
        int(
            info.get(
                "jumlah_pengujian",
                0,
            )
            or 0
        ),
    )

    # =====================================================
    # INFORMASI TERA TERAKHIR
    # =====================================================
    st.markdown(
        "#### 🧾 Informasi Tera Terakhir"
    )

    x1, x2 = (
        st.columns(2)
    )

    with x1:

        st.write(
            "**Jenis Pengujian:**",
            clean_text(
                info.get(
                    "jenis_pengujian"
                )
            )
            or "-",
        )

        st.write(
            "**Nomor Sertifikat:**",
            clean_text(
                info.get(
                    "nomor_sertifikat"
                )
            )
            or "-",
        )

        st.write(
            "**Nomor Order:**",
            clean_text(
                info.get(
                    "nomor_order"
                )
            )
            or "-",
        )

    with x2:

        st.write(
            "**Hasil:**",
            clean_text(
                info.get(
                    "hasil_pengujian"
                )
            )
            or "-",
        )

        st.write(
            "**Penera 1:**",
            clean_text(
                info.get(
                    "penera_1"
                )
            )
            or "-",
        )

        st.write(
            "**Penera 2:**",
            clean_text(
                info.get(
                    "penera_2"
                )
            )
            or "-",
        )

    # =====================================================
    # RIWAYAT UTTP
    # =====================================================
    if not history.empty:

        hist = history[
            history[
                "uttp_id"
            ]
            == selected_id
        ].copy()

        if not hist.empty:

            hist = hist.sort_values(
                [
                    "tanggal_pengujian_dt",
                    "pengujian_id_num",
                ],
                ascending=False,
            )

            with st.expander(
                "📚 Riwayat Tera / Tera Ulang"
            ):

                hist_view = hist[
                    [
                        "tanggal_pengujian",
                        "jenis_pengujian",
                        "nomor_sertifikat",
                        "hasil_pengujian",
                        "berlaku_sampai",
                        "penera_1",
                    ]
                ].copy()

                hist_view[
                    "tanggal_pengujian"
                ] = hist_view[
                    "tanggal_pengujian"
                ].apply(
                    format_tanggal
                )

                hist_view[
                    "berlaku_sampai"
                ] = hist_view[
                    "berlaku_sampai"
                ].apply(
                    format_tanggal
                )

                hist_view.columns = [
                    "Tanggal",
                    "Jenis",
                    "Nomor Sertifikat",
                    "Hasil",
                    "Berlaku Sampai",
                    "Penera",
                ]

                st.dataframe(
                    hist_view,
                    use_container_width=True,
                    hide_index=True,
                )

def build_data_laporan_bulanan(
    df_pengujian,
    df_relasi,
    df_uttp,
    df_perusahaan,
    df_penera,
    df_spbu,
    bulan,
    tahun,
):

    if df_pengujian.empty:
        return pd.DataFrame()

    pengujian = df_pengujian.copy()

    pengujian[
        "tanggal_pengujian_dt"
    ] = pd.to_datetime(
        pengujian[
            "tanggal_pengujian"
        ],
        errors="coerce",
    )

    # =====================================================
    # FILTER BULAN & TAHUN
    # =====================================================
    pengujian = pengujian[
        (
            pengujian[
                "tanggal_pengujian_dt"
            ].dt.month
            == bulan
        )
        &
        (
            pengujian[
                "tanggal_pengujian_dt"
            ].dt.year
            == tahun
        )
    ].copy()

    if pengujian.empty:
        return pd.DataFrame()

    # =====================================================
    # MASTER UTTP
    # =====================================================
    uttp = df_uttp.copy()

    uttp = uttp.rename(
        columns={
            "id": "uttp_id"
        }
    )

    uttp[
        "uttp_id"
    ] = pd.to_numeric(
        uttp[
            "uttp_id"
        ],
        errors="coerce",
    )

    # =====================================================
    # RELASI PENGUJIAN - UTTP
    # =====================================================
    relasi = df_relasi.copy()

    if not relasi.empty:

        relasi[
            "pengujian_id"
        ] = pd.to_numeric(
            relasi[
                "pengujian_id"
            ],
            errors="coerce",
        )

        relasi[
            "uttp_id"
        ] = pd.to_numeric(
            relasi[
                "uttp_id"
            ],
            errors="coerce",
        )

    # =====================================================
    # MASTER PERUSAHAAN
    # =====================================================
    perusahaan = df_perusahaan.copy()

    if not perusahaan.empty:

        perusahaan = perusahaan.rename(
            columns={
                "id": "perusahaan_id"
            }
        )

        perusahaan[
            "perusahaan_id"
        ] = pd.to_numeric(
            perusahaan[
                "perusahaan_id"
            ],
            errors="coerce",
        )

    # =====================================================
    # MASTER SPBU
    # =====================================================
    spbu = df_spbu.copy()

    if not spbu.empty:

        spbu = spbu.rename(
            columns={
                "id": "spbu_id",
                "alamat": "alamat_spbu",
            }
        )

        spbu[
            "spbu_id"
        ] = pd.to_numeric(
            spbu[
                "spbu_id"
            ],
            errors="coerce",
        )

    hasil = []

    # =====================================================
    # 1 PENGUJIAN / ORDER = 1 BARIS
    # =====================================================
    for _, p in pengujian.iterrows():

        pengujian_id = p.get("id")

        nomor_order = clean_text(
            p.get("nomor_order")
        )

        jenis_pengujian = (
            normalisasi_jenis_pengujian(
                p.get(
                    "jenis_pengujian"
                )
            )
        )

        tanggal = p.get(
            "tanggal_pengujian_dt"
        )

        # =================================================
        # CARI UTTP YANG TERKAIT
        # =================================================
        relasi_pengujian = (
            relasi[
                relasi[
                    "pengujian_id"
                ]
                == pengujian_id
            ]
            .copy()
            if not relasi.empty
            else pd.DataFrame()
        )

        alat = pd.DataFrame()

        if not relasi_pengujian.empty:

            alat = (
                relasi_pengujian[
                    [
                        "uttp_id"
                    ]
                ]
                .merge(
                    uttp,
                    on="uttp_id",
                    how="left",
                )
            )

        # =================================================
        # FALLBACK pengujian.uttp_id
        # =================================================
        if alat.empty:

            uttp_id_direct = p.get(
                "uttp_id"
            )

            if pd.notna(
                uttp_id_direct
            ):

                alat = uttp[
                    uttp[
                        "uttp_id"
                    ]
                    == uttp_id_direct
                ].copy()

        # =================================================
        # IDENTITAS
        # =================================================
        nama_perusahaan = ""
        alamat = ""
        lokasi = ""
        ket = ""

        # =================================================
        # HITUNG JUMLAH PER JENIS
        # =================================================
        jumlah_per_jenis = {}

        if not alat.empty:

            for _, a in alat.iterrows():

                jenis_uttp = clean_text(
                    a.get(
                        "jenis_uttp"
                    )
                )

                kategori = (
                    kategori_laporan_dari_jenis_uttp(
                        jenis_uttp
                    )
                )

                kode_alat = (
                    kode_alat_laporan(
                        jenis_uttp
                    )
                )

                if not kategori or not kode_alat:
                    continue

                ket = kategori

                key = (
                    f"{kategori}_"
                    f"{jenis_pengujian}_"
                    f"{kode_alat}"
                )

                # =============================================
                # JUMLAH ALAT
                # =============================================
                if kode_alat == "KWH":
                
                    jumlah_alat = pd.to_numeric(
                        p.get(
                            "jumlah_alat"
                        ),
                        errors="coerce",
                    )
                
                    if pd.isna(
                        jumlah_alat
                    ):
                        jumlah_alat = 0
                
                    jumlah_alat = int(
                        jumlah_alat
                    )
                
                    # kWh hanya dihitung sekali per pengujian,
                    # walaupun mempunyai master UTTP terkait.
                    jumlah_per_jenis[
                        key
                    ] = jumlah_alat
                
                else:
                
                    jumlah_per_jenis[
                        key
                    ] = (
                        jumlah_per_jenis.get(
                            key,
                            0,
                        )
                        + 1
                    )

            # =============================================
            # PEMILIK / LOKASI DARI ALAT PERTAMA
            # =============================================
            alat_pertama = alat.iloc[0]
            jenis_uttp_utama = clean_text(
                alat_pertama.get(
                    "jenis_uttp"
                )
            )
            
            lokasi = tentukan_lokasi_laporan(
                jenis_uttp=jenis_uttp_utama,
                data_pengujian=p.get(
                    "data_pengujian"
                ),
            )
            spbu_id = alat_pertama.get(
                "spbu_id"
            )

            perusahaan_id = (
                alat_pertama.get(
                    "perusahaan_id"
                )
            )

            if pd.notna(
                spbu_id
            ):

                data_spbu = spbu[
                    spbu[
                        "spbu_id"
                    ]
                    == spbu_id
                ]

                if not data_spbu.empty:

                    s = data_spbu.iloc[0]

                    nomor_spbu = (
                        clean_text(
                            s.get(
                                "nomor_spbu"
                            )
                        )
                    )

                    nama_perusahaan = (
                        f"SPBU {nomor_spbu}"
                        if nomor_spbu
                        else clean_text(
                            s.get(
                                "nama_spbu"
                            )
                        )
                    )

                    alamat = clean_text(
                        s.get(
                            "alamat_spbu"
                        )
                    )

            elif pd.notna(
                perusahaan_id
            ):

                data_perusahaan = (
                    perusahaan[
                        perusahaan[
                            "perusahaan_id"
                        ]
                        == perusahaan_id
                    ]
                )

                if not data_perusahaan.empty:

                    pr = (
                        data_perusahaan.iloc[0]
                    )

                    nama_perusahaan = (
                        clean_text(
                            pr.get(
                                "nama_perusahaan"
                            )
                        )
                    )

                    alamat = clean_text(
                        pr.get(
                            "alamat"
                        )
                    )

        # =================================================
        # BASE ROW
        # =================================================
        kode_penera = (
            format_kode_penera_laporan(
                penera_1=p.get(
                    "penera_1"
                ),
                penera_2=p.get(
                    "penera_2"
                ),
                lookup_kode=(
                    lookup_kode_penera
                ),
            )
        )
        row = {
            "Tanggal": tanggal,
            "No. Order": nomor_order,
            "Nama Perusahaan": nama_perusahaan,
            "Alamat": alamat,
            "Lokasi": lokasi,
            "KET": ket,
            "Jenis Pengujian": jenis_pengujian,
            "Penera": kode_penera,
        }

        row.update(
            jumlah_per_jenis
        )

        hasil.append(
            row
        )

    laporan = pd.DataFrame(
        hasil
    )

    if laporan.empty:
        return laporan

    laporan = laporan.sort_values(
        [
            "Tanggal",
            "No. Order",
        ]
    ).reset_index(
        drop=True
    )

    laporan.insert(
        0,
        "No.",
        range(
            1,
            len(laporan) + 1,
        ),
    )

    return laporan
# =========================================================
# DASHBOARD
# =========================================================
def render_dashboard_uttp():
    # =====================================================
    # MODE INTERAKSI CARD DASHBOARD
    # =====================================================
    if (
        "dashboard_uttp_mode"
        not in st.session_state
    ):
        st.session_state[
            "dashboard_uttp_mode"
        ] = "total_uttp"

    if (
        "dashboard_uttp_page"
        not in st.session_state
    ):
        st.session_state[
            "dashboard_uttp_page"
        ] = 1
    # =====================================================
    # NAVIGASI
    # =====================================================
    col_back, col_home, col_space = st.columns([1.4, 1.4, 5])
    
    with col_back:
        if st.button(
            "← Dashboard Tera Ulang",
            use_container_width=True,
            key="btn_uttp_kembali_dashboard"
        ):
            st.session_state.halaman_dashboard = "home_dashboard"
            st.rerun()
    
    with col_home:
        if st.button(
            "🏠 Home SMART METRO",
            use_container_width=True,
            key="btn_uttp_kembali_home"
        ):
            st.session_state.halaman = "home"
            st.session_state.halaman_dashboard = "home_dashboard"
            st.rerun()

    # =====================================================
    # LOAD DATA
    # =====================================================
    try:

        (
            df_perusahaan,
            df_penera,
            df_spbu,
            df_uttp,
            df_pengujian,
            df_relasi,
        ) = (
            load_data_dashboard_uttp()
        )

    except Exception as exc:

        st.error(
            "Data Supabase "
            "tidak dapat dibaca: "
            f"{exc}"
        )

        return

    (
        monitor,
        history,
    ) = build_monitoring_data(
        df_perusahaan,
        df_spbu,
        df_uttp,
        df_pengujian,
        df_relasi,
    )

    render_header()

    # =====================================================
    # EXPORT LAPORAN BULANAN
    # =====================================================
    with st.expander(
        "📥 Export Laporan Bulanan",
        expanded=False,
    ):

        st.caption(
            "Rekap pelayanan tera / tera ulang berdasarkan "
            "tanggal pengujian."
        )

        nama_bulan = {
            1: "Januari",
            2: "Februari",
            3: "Maret",
            4: "April",
            5: "Mei",
            6: "Juni",
            7: "Juli",
            8: "Agustus",
            9: "September",
            10: "Oktober",
            11: "November",
            12: "Desember",
        }

        # =================================================
        # DAFTAR TAHUN DARI DATA PENGUJIAN
        # =================================================
        tanggal_laporan = pd.to_datetime(
            df_pengujian[
                "tanggal_pengujian"
            ],
            errors="coerce",
        )

        tahun_tersedia = sorted(
            tanggal_laporan
            .dropna()
            .dt.year
            .unique()
            .tolist(),
            reverse=True,
        )

        if not tahun_tersedia:
            tahun_tersedia = [
                date.today().year
            ]

        col_bulan, col_tahun = (
            st.columns(2)
        )

        with col_bulan:

            bulan_laporan = (
                st.selectbox(
                    "Bulan",
                    options=list(
                        nama_bulan.keys()
                    ),
                    format_func=lambda x: (
                        nama_bulan[x]
                    ),
                    index=(
                        date.today().month
                        - 1
                    ),
                    key=(
                        "dashboard_laporan_bulan"
                    ),
                )
            )

        with col_tahun:

            tahun_laporan = (
                st.selectbox(
                    "Tahun",
                    options=tahun_tersedia,
                    key=(
                        "dashboard_laporan_tahun"
                    ),
                )
            )

        # =================================================
        # BANGUN DATA LAPORAN
        # =================================================
        laporan_bulanan = (
            build_data_laporan_bulanan(
                df_pengujian=(
                    df_pengujian
                ),
                df_relasi=(
                    df_relasi
                ),
                df_uttp=(
                    df_uttp
                ),
                df_perusahaan=(
                    df_perusahaan
                ),
                df_penera=(
                    df_penera
                ),
                df_spbu=(
                    df_spbu
                ),
                bulan=(
                    bulan_laporan
                ),
                tahun=(
                    tahun_laporan
                ),
            )
        )

        # =================================================
        # PREVIEW
        # =================================================
        if laporan_bulanan.empty:

            st.info(
                f"Belum ada data pelayanan "
                f"{nama_bulan[bulan_laporan]} "
                f"{tahun_laporan}."
            )

        else:

            total_order = len(
                laporan_bulanan
            )

            st.success(
                f"Ditemukan {total_order:,} "
                f"nomor order pada "
                f"{nama_bulan[bulan_laporan]} "
                f"{tahun_laporan}."
            )

            st.markdown(
                "##### Preview Data"
            )

            st.dataframe(
                laporan_bulanan,
                use_container_width=True,
                hide_index=True,
            )

    if monitor.empty:

        st.warning(
            "Data UTTP umum "
            "belum tersedia."
        )

        return

    # =====================================================
    # FILTER
    # =====================================================
    st.sidebar.markdown(
        "---"
    )

    st.sidebar.subheader(
        "Filter UTTP"
    )

    # =====================================================
    # DAFTAR PEMILIK / LOKASI
    # =====================================================
    pemilik_master = (
        monitor[
            [
                "pemilik_key",
                "pemilik_display",
                "spbu_id",
                "nomor_spbu",
            ]
        ]
        .drop_duplicates(
            subset=[
                "pemilik_key"
            ]
        )
        .copy()
    )

    pemilik_master[
        "label_filter"
    ] = pemilik_master.apply(
        lambda row: (
            (
                f"{clean_text(row['pemilik_display'])} "
                f"| SPBU "
                f"{clean_text(row.get('nomor_spbu'))}"
            )
            if pd.notna(
                row.get(
                    "spbu_id"
                )
            )
            and clean_text(
                row.get(
                    "nomor_spbu"
                )
            )
            else clean_text(
                row.get(
                    "pemilik_display"
                )
            )
        ),
        axis=1,
    )

    pemilik_master = (
        pemilik_master
        .sort_values(
            "label_filter"
        )
    )

    pemilik_options = {
        row[
            "label_filter"
        ]: row[
            "pemilik_key"
        ]
        for _, row
        in pemilik_master.iterrows()
        if clean_text(
            row[
                "label_filter"
            ]
        )
    }

    pemilik_pick = (
        st.sidebar.selectbox(
            "Pemilik / Lokasi",
            options=[
                "(Semua)"
            ]
            + list(
                pemilik_options.keys()
            ),
        )
    )

    data_filter = (
        monitor.copy()
    )

    pemilik_key_pick = None

    if (
        pemilik_pick
        != "(Semua)"
    ):

        pemilik_key_pick = (
            pemilik_options[
                pemilik_pick
            ]
        )

        data_filter = (
            data_filter[
                data_filter[
                    "pemilik_key"
                ]
                == pemilik_key_pick
            ]
            .copy()
        )

    # =====================================================
    # JENIS UTTP
    # =====================================================
    jenis_options = sorted(
        [
            item
            for item in (
                data_filter[
                    "jenis_uttp"
                ]
                .fillna("")
                .astype(str)
                .str.strip()
                .unique()
            )
            if item
        ]
    )

    jenis_pick = (
        st.sidebar.selectbox(
            "Jenis UTTP",
            options=[
                "(Semua)"
            ]
            + jenis_options,
        )
    )

    # =====================================================
    # STATUS
    # =====================================================
    status_available = set(
        data_filter[
            "status_tera"
        ]
    )

    status_options = [
        status
        for status
        in STATUS_ORDER
        if status
        in status_available
    ]

    status_pick = (
        st.sidebar.selectbox(
            "Status Tera",
            options=[
                "(Semua)"
            ]
            + status_options,
        )
    )

    # =====================================================
    # TERAPKAN FILTER
    # =====================================================
    fdf = (
        data_filter.copy()
    )

    if (
        jenis_pick
        != "(Semua)"
    ):

        fdf = fdf[
            fdf[
                "jenis_uttp"
            ]
            == jenis_pick
        ]

    if (
        status_pick
        != "(Semua)"
    ):

        fdf = fdf[
            fdf[
                "status_tera"
            ]
            == status_pick
        ]
    # =====================================================
    # DRILL-DOWN DARI TABEL RINGKASAN
    # =====================================================
    pemilik_detail_key = (
        st.session_state.get(
            "dashboard_uttp_pemilik_detail"
        )
    )

    if pemilik_detail_key:

        detail_df = monitor[
            monitor[
                "pemilik_key"
            ]
            == pemilik_detail_key
        ].copy()

        if not detail_df.empty:

            if st.button(
                "← Kembali ke Dashboard Umum",
                key="btn_kembali_dari_detail_ringkasan",
            ):

                st.session_state.pop(
                    "dashboard_uttp_pemilik_detail",
                    None,
                )

                st.rerun()

            render_detail_perusahaan(
                detail_df,
                history,
            )

            return
    # =====================================================
    # MODE SEMUA PERUSAHAAN
    # =====================================================
    if (
        pemilik_pick
        == "(Semua)"
    ):

        # =================================================
        # KPI UMUM SMART METRO
        # =================================================

        total_pemilik = (
            fdf[
                "pemilik_key"
            ]
            .dropna()
            .nunique()
        )

        total_uttp = (
            fdf[
                "uttp_id"
            ]
            .dropna()
            .nunique()
        )

        total_aktif = (
            fdf.loc[
                fdf["status_tera"]
                == STATUS_AKTIF,
                "uttp_id"
            ]
            .dropna()
            .nunique()
        )

        total_jatuh_tempo = (
            fdf.loc[
                fdf["status_tera"]
                == STATUS_JATUH_TEMPO,
                "uttp_id"
            ]
            .dropna()
            .nunique()
        )

        total_kedaluwarsa = (
            fdf.loc[
                fdf["status_tera"]
                == STATUS_KEDALUWARSA,
                "uttp_id"
            ]
            .dropna()
            .nunique()
        )

        total_belum_uji = (
            fdf.loc[
                fdf["status_tera"]
                == STATUS_BELUM_UJI,
                "uttp_id"
            ]
            .dropna()
            .nunique()
        )

        total_data_kurang = (
            fdf.loc[
                fdf["status_tera"]
                == STATUS_DATA_KURANG,
                "uttp_id"
            ]
            .dropna()
            .nunique()
        )

        total_status = (
            total_aktif
            + total_jatuh_tempo
            + total_kedaluwarsa
            + total_belum_uji
            + total_data_kurang
        )

        # =================================================
        # IDENTITAS
        # =================================================
        k1, k2 = st.columns(2)

        with k1:
            render_kpi_button(
                title="Pemilik / Lokasi",
                value=total_pemilik,
                subtitle="Perusahaan & SPBU",
                color="#1D4ED8",
                key="btn_kpi_pemilik",
                mode="pemilik",
            )
        with k2:
            render_kpi_button(
                title="Total UTTP",
                value=total_uttp,
                subtitle="Seluruh alat aktif",
                color="#2563EB",
                key="btn_kpi_total_uttp",
                mode="total_uttp",
            )

        st.markdown(
            "#### Status Tera / Tera Ulang"
        )

        # =================================================
        # STATUS
        # =================================================
        s1, s2, s3, s4, s5 = (
            st.columns(5)
        )

        with s1:
            render_kpi_button(
                title="Tera Aktif",
                value=total_aktif,
                subtitle="Masih berlaku",
                color="#16A34A",
                key="btn_kpi_aktif",
                mode="aktif",
            )

        with s2:
            render_kpi_button(
                title=f"≤ {BATAS_JATUH_TEMPO_HARI} Hari",
                value=total_jatuh_tempo,
                subtitle="Akan jatuh tempo",
                color="#F59E0B",
                key="btn_kpi_jatuh_tempo",
                mode="jatuh_tempo",
            )

        with s3:
            render_kpi_button(
                title="Kedaluwarsa",
                value=total_kedaluwarsa,
                subtitle="Perlu tindak lanjut",
                color="#DC2626",
                key="btn_kpi_kedaluwarsa",
                mode="kedaluwarsa",
            )

        with s4:
            render_kpi_button(
                title="Belum Uji",
                value=total_belum_uji,
                subtitle="Belum ada riwayat",
                color="#64748B",
                key="btn_kpi_belum_uji",
                mode="belum_uji",
            )

        with s5:
            render_kpi_button(
                title="Data Belum Lengkap",
                value=total_data_kurang,
                subtitle="Perlu verifikasi",
                color="#475569",
                key="btn_kpi_data_kurang",
                mode="data_kurang",
            )

        # =================================================
        # VALIDASI
        # =================================================
        if total_status != total_uttp:

            selisih = (
                total_uttp
                - total_status
            )

            st.warning(
                f"Ada {abs(selisih)} UTTP "
                "yang statusnya belum terklasifikasi."
            )
        # =================================================
        # AREA INTERAKTIF CARD
        # =================================================
        mode_dashboard = (
            st.session_state.get(
                "dashboard_uttp_mode",
                "total_uttp",
            )
        )

        # =================================================
        # PEMILIK / LOKASI
        # =================================================
        if (
            mode_dashboard
            == "pemilik"
        ):

            render_tabel_ringkasan_pemilik(
                data=fdf,
                title="🏢 Daftar Pemilik / Lokasi UTTP",
                color="#1D4ED8",
            )

        # =================================================
        # TERA AKTIF
        # =================================================
        elif (
            mode_dashboard
            == "aktif"
        ):

            data_aktif = fdf[
                fdf[
                    "status_tera"
                ]
                == STATUS_AKTIF
            ].copy()

            render_tabel_ringkasan_pemilik(
                data=data_aktif,
                title="✅ Pemilik dengan UTTP Tera Aktif",
                color="#16A34A",
            )

        # =================================================
        # AKAN JATUH TEMPO
        # =================================================
        elif (
            mode_dashboard
            == "jatuh_tempo"
        ):

            data_jatuh_tempo = fdf[
                fdf[
                    "status_tera"
                ]
                == STATUS_JATUH_TEMPO
            ].copy()

            render_tabel_ringkasan_pemilik(
                data=data_jatuh_tempo,
                title=(
                    f"⏳ Pemilik dengan UTTP "
                    f"≤ {BATAS_JATUH_TEMPO_HARI} Hari"
                ),
                color="#F59E0B",
            )
        # =================================================
        # KEDALUWARSA
        # =================================================
        elif (
            mode_dashboard
            == "kedaluwarsa"
        ):

            data_kedaluwarsa = fdf[
                fdf[
                    "status_tera"
                ]
                == STATUS_KEDALUWARSA
            ].copy()

            render_tabel_ringkasan_pemilik(
                data=data_kedaluwarsa,
                title="🚨 Pemilik dengan UTTP Kedaluwarsa",
                color="#DC2626",
            )
        # =================================================
        # BELUM UJI
        # =================================================
        elif (
            mode_dashboard
            == "belum_uji"
        ):

            data_belum_uji = fdf[
                fdf[
                    "status_tera"
                ]
                == STATUS_BELUM_UJI
            ].copy()

            render_tabel_ringkasan_pemilik(
                data=data_belum_uji,
                title="🕒 Pemilik dengan UTTP Belum Pernah Diuji",
                color="#64748B",
            )
        # =================================================
        # DATA BELUM LENGKAP
        # =================================================
        elif (
            mode_dashboard
            == "data_kurang"
        ):

            data_kurang = fdf[
                fdf[
                    "status_tera"
                ]
                == STATUS_DATA_KURANG
            ].copy()

            render_tabel_ringkasan_pemilik(
                data=data_kurang,
                title="⚠️ Pemilik dengan Data UTTP Belum Lengkap",
                color="#475569",
            )
        # =================================================
        # DATA GRAFIK SESUAI CARD AKTIF
        # =================================================
        data_grafik = fdf.copy()

        judul_grafik = (
            "📊 Komposisi Jenis UTTP"
        )

        if (
            mode_dashboard
            == "aktif"
        ):
            data_grafik = fdf[
                fdf[
                    "status_tera"
                ]
                == STATUS_AKTIF
            ].copy()

            judul_grafik = (
                "📊 Komposisi UTTP Tera Aktif"
            )

        elif (
            mode_dashboard
            == "jatuh_tempo"
        ):
            data_grafik = fdf[
                fdf[
                    "status_tera"
                ]
                == STATUS_JATUH_TEMPO
            ].copy()

            judul_grafik = (
                f"📊 Komposisi UTTP "
                f"≤ {BATAS_JATUH_TEMPO_HARI} Hari"
            )

        elif (
            mode_dashboard
            == "kedaluwarsa"
        ):
            data_grafik = fdf[
                fdf[
                    "status_tera"
                ]
                == STATUS_KEDALUWARSA
            ].copy()

            judul_grafik = (
                "📊 Komposisi UTTP Kedaluwarsa"
            )

        elif (
            mode_dashboard
            == "belum_uji"
        ):
            data_grafik = fdf[
                fdf[
                    "status_tera"
                ]
                == STATUS_BELUM_UJI
            ].copy()

            judul_grafik = (
                "📊 Komposisi UTTP Belum Uji"
            )

        elif (
            mode_dashboard
            == "data_kurang"
        ):
            data_grafik = fdf[
                fdf[
                    "status_tera"
                ]
                == STATUS_DATA_KURANG
            ].copy()

            judul_grafik = (
                "📊 Komposisi UTTP "
                "Data Belum Lengkap"
            )

        # Pemilik dan Total UTTP
        # tetap menggunakan seluruh fdf

        # =================================================
        # KOMPOSISI JENIS UTTP GLOBAL
        # =================================================
        st.markdown("---")

        st.subheader(
            judul_grafik
        )

        # =================================================
        # SIAPKAN DATA
        # =================================================
        jenis_global = (
            data_grafik
            .assign(
                jenis_display=(
                    data_grafik[
                        "jenis_uttp"
                    ]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .replace(
                        "",
                        "Jenis Belum Diisi"
                    )
                )
            )
            .groupby(
                "jenis_display"
            )[
                "uttp_id"
            ]
            .nunique()
            .rename(
                "Jumlah UTTP"
            )
            .reset_index()
            .rename(
                columns={
                    "jenis_display":
                    "Jenis UTTP"
                }
            )
            .sort_values(
                "Jumlah UTTP",
                ascending=False
            )
            .reset_index(
                drop=True
            )
        )

        if not jenis_global.empty:

            jumlah_jenis = len(
                jenis_global
            )

            total_dalam_grafik = int(
                jenis_global[
                    "Jumlah UTTP"
                ].sum()
            )

            tinggi_chart = min(
                max(
                    220,
                    jumlah_jenis * 34
                ),
                480
            )

            nilai_maks = max(
                1,
                int(
                    jenis_global[
                        "Jumlah UTTP"
                    ].max()
                )
            )

            st.caption(
                f"{total_dalam_grafik:,} UTTP "
                f"• {jumlah_jenis} jenis alat"
            )
            # =================================================
            # BASE CHART
            # =================================================
            base = (
                alt.Chart(
                    jenis_global
                )
                .encode(
                    y=alt.Y(
                        "Jenis UTTP:N",
                        sort="-x",
                        title=None,
                        axis=alt.Axis(
                            labelLimit=220,
                            labelFontSize=12
                        )
                    ),

                    x=alt.X(
                        "Jumlah UTTP:Q",
                        title="Jumlah UTTP",
                        scale=alt.Scale(
                            domain=[
                                0,
                                nilai_maks * 1.18
                            ]
                        ),
                        axis=alt.Axis(
                            tickMinStep=1,
                            grid=True
                        )
                    ),

                    tooltip=[
                        alt.Tooltip(
                            "Jenis UTTP:N",
                            title="Jenis UTTP"
                        ),
                        alt.Tooltip(
                            "Jumlah UTTP:Q",
                            title="Jumlah",
                            format=",.0f"
                        ),
                    ]
                )
            )

            # =================================================
            # BATANG
            # =================================================
            bar = base.mark_bar(
                size=22,
                cornerRadiusEnd=7,
                color="#2563EB"
            )

            # =================================================
            # LABEL NILAI
            # =================================================
            label = (
                base
                .mark_text(
                    align="left",
                    baseline="middle",
                    dx=7,
                    fontSize=12,
                    fontWeight="bold",
                    color="#334155"
                )
                .encode(
                    text=alt.Text(
                        "Jumlah UTTP:Q",
                        format=".0f"
                    )
                )
            )

            chart = (
                bar
                + label
            ).properties(
                height=tinggi_chart
            )

            st.altair_chart(
                chart,
                use_container_width=True
            )

    # =====================================================
    # MODE SATU PERUSAHAAN
    # =====================================================
    else:

        render_detail_perusahaan(
            fdf,
            history,
        )


# =========================================================
# RUN
# =========================================================
def run():

    render_dashboard_uttp()


if __name__ == "__main__":

    run()
