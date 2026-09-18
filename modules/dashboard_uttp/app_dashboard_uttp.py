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
    KPI card sederhana yang bisa diklik.
    """

    aktif = (
        st.session_state.get(
            "dashboard_uttp_mode"
        )
        == mode
    )

    label = (
        f"{title}\n"
        f"{value}\n"
        f"{subtitle}"
    )

    if aktif:
        label = (
            f"● {title}\n"
            f"{value}\n"
            f"{subtitle}"
        )

    if st.button(
        label,
        key=key,
        use_container_width=True,
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
            "pemilik_display",
            "Jumlah UTTP",
        ]
    ]

    tampil.columns = [
        "No.",
        "Pemilik / Lokasi",
        "Jumlah UTTP",
    ]

    # =====================================================
    # HEADER TABEL
    # =====================================================
    st.markdown(
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
        unsafe_allow_html=True,
    )

    # =====================================================
    # TABEL
    # =====================================================
    nilai_maks = max(
        1,
        int(
            ringkasan[
                "Jumlah UTTP"
            ].max()
        )
    )

    st.dataframe(
        tampil,
        use_container_width=True,
        hide_index=True,
        column_config={
            "No.": st.column_config.NumberColumn(
                "No.",
                width="small",
            ),

            "Pemilik / Lokasi":
                st.column_config.TextColumn(
                    "Pemilik / Lokasi",
                    width="large",
                ),

            "Jumlah UTTP":
                st.column_config.ProgressColumn(
                    "Jumlah UTTP",
                    min_value=0,
                    max_value=nilai_maks,
                    format="%d",
                ),
        },
    )

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
    nomor_spbu = (
        clean_text(
            first.get(
                "nomor_spbu"
            )
        )
    )
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

    c1, c2, c3, c4, c5 = (
        st.columns(5)
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

    col_chart, col_table = (
        st.columns(
            [1.5, 1]
        )
    )

    with col_chart:

        st.bar_chart(
            jenis_count.set_index(
                "Jenis UTTP"
            )
        )

    with col_table:

        st.dataframe(
            jenis_count,
            use_container_width=True,
            hide_index=True,
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

    view = daftar[
        [
            "uttp_id",
            "jenis_uttp",
            "merk",
            "tipe",
            "nomor_seri",
            "kapasitas_tampil",
            "kelas",
            "status_tera",
            "tanggal_tampil",
            "berlaku_tampil",
            "nomor_sertifikat",
        ]
    ].copy()

    view.columns = [
        "ID",
        "Jenis UTTP",
        "Merek",
        "Model / Tipe",
        "Nomor Seri",
        "Kapasitas",
        "Kelas",
        "Status Tera",
        "Tera Terakhir",
        "Berlaku Sampai",
        "Nomor Sertifikat",
    ]

    st.dataframe(
        view,
        use_container_width=True,
        hide_index=True,
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
            f"No. Seri {nomor_seri} | "
            f"ID {int(uttp_id)}"
        )

        pilihan_uttp[
            label
        ] = uttp_id

    pilih = st.selectbox(
        "Pilih UTTP",
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
            render_kpi(
                "Kedaluwarsa",
                total_kedaluwarsa,
                "Perlu tindak lanjut",
                "#DC2626",
            )

        with s4:
            render_kpi(
                "Belum Uji",
                total_belum_uji,
                "Belum ada riwayat",
                "#64748B",
            )

        with s5:
            render_kpi(
                "Data Belum Lengkap",
                total_data_kurang,
                "Perlu verifikasi",
                "#475569",
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

        if (
            mode_dashboard
            == "pemilik"
        ):
        
            render_tabel_ringkasan_pemilik(
                data=fdf,
                title="🏢 Daftar Pemilik / Lokasi UTTP",
                color="#1D4ED8",
            )
        
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
    render_tabel_ringkasan_pemilik(
        data=data_aktif,
        title="✅ Pemilik dengan UTTP Tera Aktif",
        color="#16A34A",
    )
        # =================================================
        # PRIORITAS PENGAWASAN
        # =================================================
        if (
            mode_dashboard
            not in [
                "pemilik",
                "total_uttp",
                "aktif",
                "jatuh_tempo",
            ]
        ):
        
            priority = fdf[
                fdf[
                    "status_tera"
                ].isin(
                    [
                        STATUS_KEDALUWARSA,
                        STATUS_JATUH_TEMPO,
                        STATUS_BELUM_UJI,
                        STATUS_DATA_KURANG,
                    ]
                )
            ].copy()
    
            if not priority.empty:
    
                priority[
                    "prioritas"
                ] = priority[
                    "status_tera"
                ].map({
                    STATUS_KEDALUWARSA: 0,
                    STATUS_JATUH_TEMPO: 1,
                    STATUS_BELUM_UJI: 2,
                    STATUS_DATA_KURANG: 3,
                })
    
                priority[
                    "sisa_sort"
                ] = pd.to_numeric(
                    priority[
                        "sisa_hari"
                    ],
                    errors="coerce",
                ).fillna(
                    999999
                )
    
                priority = (
                    priority
                    .sort_values(
                        [
                            "prioritas",
                            "sisa_sort",
                            "pemilik_display",
                        ]
                    )
                    .head(25)
                )
    
                st.markdown("---")
    
                st.subheader(
                    "🚨 Prioritas Pengawasan"
                )
    
                priority_view = (
                    priority[
                        [
                            "pemilik_display",
                            "jenis_uttp",
                            "status_tera",
                            "sisa_hari",
                        ]
                    ]
                    .copy()
                )
    
                priority_view[
                    "sisa_hari"
                ] = priority_view[
                    "sisa_hari"
                ].apply(
                    format_sisa_hari
                )
    
                priority_view.columns = [
                    "Pemilik",
                    "Jenis UTTP",
                    "Status",
                    "Sisa Waktu",
                ]
    
                st.dataframe(
                    priority_view,
                    use_container_width=True,
                    hide_index=True,
                )

        # =================================================
        # KOMPOSISI JENIS UTTP GLOBAL
        # =================================================
        st.markdown("---")

        st.subheader(
            "📊 Komposisi Jenis UTTP"
        )

        # =================================================
        # SIAPKAN DATA
        # =================================================
        jenis_global = (
            fdf
            .assign(
                jenis_display=(
                    fdf["jenis_uttp"]
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

            # Tinggi dinamis tetapi tetap compact
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
