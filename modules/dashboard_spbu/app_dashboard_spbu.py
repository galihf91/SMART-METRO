import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from datetime import date, datetime
from io import StringIO
import re
import numpy as np
import json
import os
from supabase import create_client

st.set_page_config(
    page_title="Dashboard Pengawasan SPBU – SMART METRO",
    page_icon="⛽",
    layout="wide",
)

# =========================================================
# KONSTANTA
# =========================================================
FILE_SPBU = "data/Data SPBU Kab. Tangerang.csv"
FILE_GEOJSON = "data/batas_kecamatan_tangerang.geojson"
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
# HEADER SEDERHANA — TANPA GAMBAR
# =========================================================
def render_main_header(title, subtitle):
    st.markdown(
        f"""
        <style>
        .main-header {{
            width: 100%;
            padding: 28px 30px;
            margin-bottom: 24px;
            border-radius: 16px;
            background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%);
            box-shadow: 0 8px 20px rgba(15, 23, 42, 0.12);
        }}
        .main-header h1 {{
            color: white;
            font-size: 32px;
            font-weight: 750;
            margin: 0 0 5px 0;
        }}
        .main-header p {{
            color: rgba(255,255,255,0.92);
            font-size: 16px;
            margin: 0;
        }}
        .status-chip {{
            display: inline-block;
            padding: 5px 10px;
            border-radius: 999px;
            color: white;
            font-size: 12px;
            font-weight: 700;
        }}
        </style>
        <div class="main-header">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        "<style>#MainMenu,footer{visibility:hidden;}</style>",
        unsafe_allow_html=True,
    )


# =========================================================
# SUPABASE
# =========================================================
@st.cache_resource
def get_supabase_dashboard_spbu():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


def _fetch_all_rows(table_name, select_columns, page_size=1000):
    """Ambil seluruh row dengan pagination agar tidak mentok limit 1000 row."""
    supabase = get_supabase_dashboard_spbu()
    rows = []
    start = 0

    while True:
        response = (
            supabase
            .table(table_name)
            .select(select_columns)
            .range(start, start + page_size - 1)
            .execute()
        )

        batch = response.data or []
        rows.extend(batch)

        if len(batch) < page_size:
            break

        start += page_size

    return rows


@st.cache_data(ttl=60, show_spinner=False)
def load_supabase_bundle():
    """
    Data pengawasan PUBBM:
    - spbu              : master SPBU
    - pengujian         : header kegiatan tera/tera ulang
    - pengujian_uttp    : detail nozzle + K-Faktor
    - uttp              : identitas master nozzle (merk/tipe/no seri)
    """
    spbu_rows = _fetch_all_rows(
        "spbu",
        "id,nama_spbu,nomor_spbu,alamat,jenis_lokasi,kecamatan,media_bbm,status",
    )

    pengujian_rows = _fetch_all_rows(
        "pengujian",
        "id,spbu_id,perusahaan_id,tanggal_pengujian,tanggal_sertifikat,"
        "jenis_pengujian,hasil,nomor_order,nomor_sertifikat,penera_1,penera_2,"
        "berlaku_sampai,data_pengujian",
    )

    relasi_rows = _fetch_all_rows(
        "pengujian_uttp",
        "id,pengujian_id,uttp_id,no_dispenser,posisi,media,k_faktor,urutan,hasil",
    )

    uttp_rows = _fetch_all_rows(
        "uttp",
        "id,spbu_id,perusahaan_id,jenis_uttp,merk,tipe,nomor_seri,status",
    )

    return (
        pd.DataFrame(spbu_rows),
        pd.DataFrame(pengujian_rows),
        pd.DataFrame(relasi_rows),
        pd.DataFrame(uttp_rows),
    )


# =========================================================
# UTILITAS UMUM
# =========================================================
def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", str(s or "").strip().lower())


def normalize_nomor_spbu(value):
    text = str(value or "").upper().strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return ""

    # Prioritaskan pola nomor SPBU seperti 34-15717 / 34.15717
    match = re.search(r"(\d{2})\D*(\d{4,6})", text)
    if match:
        return f"{match.group(1)}{match.group(2)}"

    digits = re.sub(r"\D", "", text)
    return digits if len(digits) >= 6 else ""


def clean_text(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null"} else text


@st.cache_data
def load_geojson(path):
    with open(path, "r", encoding="utf-8") as f:
        gj = json.load(f)

    for feature in gj.get("features", []):
        properties = feature.get("properties", {})
        nama_kecamatan = properties.get("wadmkc", "")
        properties["kec_norm"] = _norm(nama_kecamatan)
        properties["kec_label"] = nama_kecamatan

    return gj


def parse_coord(val):
    try:
        if pd.isna(val) or val == "":
            return np.nan, np.nan

        s = str(val).strip()

        if "," in s:
            lat, lon = map(float, s.split(",")[:2])
            if abs(lat) > 90:
                lat, lon = lon, lat
            return lat, lon

        nums = re.findall(r"-?\d+(?:\.\d+)?", s)
        if len(nums) >= 2:
            lat, lon = map(float, nums[:2])
            if abs(lat) > 90:
                lat, lon = lon, lat
            return lat, lon

    except Exception:
        pass

    return np.nan, np.nan


def uniq(series, clean=False):
    s = series.dropna().astype(str).str.strip()
    if clean:
        s = s.str.title()
    s = s[~s.str.lower().isin(["", "nan", "none", "null", "na", "n/a", "-", "--"])]
    return sorted(s.unique())


def format_date_id(value):
    if value is None or value == "":
        return "-"
    dt = pd.to_datetime(value, errors="coerce")
    if pd.isna(dt):
        return "-"
    return dt.strftime("%d-%m-%Y")


def format_sisa_hari(value):
    if pd.isna(value):
        return "-"

    try:
        value = int(value)
    except Exception:
        return "-"

    if value < 0:
        return f"Lewat {abs(value)} hari"
    if value == 0:
        return "Hari ini"
    return f"{value} hari"


# =========================================================
# CSV KOORDINAT GITHUB
# =========================================================
@st.cache_data
def load_spbu_csv(path):
    with open(path, "rb") as f:
        text = f.read().decode("utf-8-sig", errors="ignore")

    if not text.strip():
        return pd.DataFrame()

    first_line = text.splitlines()[0] if text.splitlines() else ""
    sep = ";" if first_line.count(";") >= first_line.count(",") else ","
    df = pd.read_csv(StringIO(text), sep=sep)
    df.columns = [c.strip() for c in df.columns]

    # Hindari No. SPBU dan Nama SPBU menjadi nama kolom yang sama.
    rename = {
        "No. SPBU": "nomor_spbu",
        "Nomor SPBU": "nomor_spbu",
        "Nama SPBU": "nama_spbu",
        "Alamat": "alamat",
        "Kecamatan": "kecamatan",
        "Koordinat": "koordinat",
        "Media BBM": "media_bbm",
        "Produk BBM": "media_bbm",
    }
    df.rename(columns={k: v for k, v in rename.items() if k in df.columns}, inplace=True)

    for col in ["nomor_spbu", "nama_spbu", "alamat", "kecamatan", "koordinat", "media_bbm"]:
        if col not in df.columns:
            df[col] = ""

    # Jika CSV lama hanya punya satu kolom identitas, tetap beri fallback.
    df["nomor_spbu"] = df["nomor_spbu"].fillna("").astype(str).str.strip()
    df["nama_spbu"] = df["nama_spbu"].fillna("").astype(str).str.strip()
    df["alamat"] = df["alamat"].fillna("").astype(str).str.strip()
    df["kecamatan"] = df["kecamatan"].fillna("").astype(str).str.strip().str.title()
    df["media_bbm"] = df["media_bbm"].fillna("").astype(str).str.strip()

    coords = df["koordinat"].apply(parse_coord)
    df["lat"] = pd.to_numeric(coords.apply(lambda x: x[0]), errors="coerce")
    df["lon"] = pd.to_numeric(coords.apply(lambda x: x[1]), errors="coerce")

    df["key_nomor"] = df["nomor_spbu"].apply(normalize_nomor_spbu)
    df["key_nama"] = df["nama_spbu"].apply(_norm)

    return df


# =========================================================
# GABUNG MASTER SPBU + KOORDINAT + STATUS PENGUJIAN
# =========================================================
def build_monitoring_data(df_csv, df_spbu, df_pengujian, df_relasi):
    # -------------------------
    # Rapikan master SPBU
    # -------------------------
    if df_spbu.empty:
        master = pd.DataFrame(
            columns=[
                "spbu_id", "nama_spbu", "nomor_spbu", "alamat", "jenis_lokasi",
                "kecamatan", "media_bbm", "status_master"
            ]
        )
    else:
        master = df_spbu.copy()
        master = master.rename(columns={"id": "spbu_id", "status": "status_master"})

        for col in ["nama_spbu", "nomor_spbu", "alamat", "jenis_lokasi", "kecamatan", "media_bbm", "status_master"]:
            if col not in master.columns:
                master[col] = ""
            master[col] = master[col].fillna("").astype(str).str.strip()

        # Tampilkan master aktif; row tanpa status tetap dianggap aktif untuk kompatibilitas data lama.
        mask_aktif = (
            master["status_master"].eq("")
            | master["status_master"].str.lower().eq("aktif")
        )
        master = master[mask_aktif].copy()

        master["key_nomor"] = master["nomor_spbu"].apply(normalize_nomor_spbu)
        master["key_nama"] = master["nama_spbu"].apply(_norm)

    # -------------------------
    # Lookup koordinat GitHub
    # -------------------------
    csv_num_map = {}
    csv_name_map = {}

    if not df_csv.empty:
        for idx, row in df_csv.iterrows():
            if row.get("key_nomor"):
                csv_num_map.setdefault(row["key_nomor"], idx)
            if row.get("key_nama"):
                csv_name_map.setdefault(row["key_nama"], idx)

    records = []
    matched_csv_indexes = set()

    for _, row in master.iterrows():
        csv_row = None
        csv_idx = None

        if row.get("key_nomor") and row["key_nomor"] in csv_num_map:
            csv_idx = csv_num_map[row["key_nomor"]]
        elif row.get("key_nama") and row["key_nama"] in csv_name_map:
            csv_idx = csv_name_map[row["key_nama"]]

        if csv_idx is not None:
            csv_row = df_csv.loc[csv_idx]
            matched_csv_indexes.add(csv_idx)

        nama = clean_text(row.get("nama_spbu"))
        nomor = clean_text(row.get("nomor_spbu"))

        if not nama and csv_row is not None:
            nama = clean_text(csv_row.get("nama_spbu"))
        if not nomor and csv_row is not None:
            nomor = clean_text(csv_row.get("nomor_spbu"))

        records.append({
            "spbu_id": row.get("spbu_id"),
            "nama_spbu": nama,
            "nomor_spbu": nomor,
            "alamat": clean_text(row.get("alamat")) or (clean_text(csv_row.get("alamat")) if csv_row is not None else ""),
            "jenis_lokasi": clean_text(row.get("jenis_lokasi")),
            "kecamatan": clean_text(row.get("kecamatan")) or (clean_text(csv_row.get("kecamatan")) if csv_row is not None else ""),
            "media_bbm": clean_text(row.get("media_bbm")) or (clean_text(csv_row.get("media_bbm")) if csv_row is not None else ""),
            "lat": csv_row.get("lat") if csv_row is not None else np.nan,
            "lon": csv_row.get("lon") if csv_row is not None else np.nan,
            "sumber_master": "Supabase",
        })

    # CSV yang belum punya pasangan master Supabase tetap muncul di peta sebagai belum ada pengujian.
    if not df_csv.empty:
        for idx, row in df_csv.iterrows():
            if idx in matched_csv_indexes:
                continue

            records.append({
                "spbu_id": None,
                "nama_spbu": clean_text(row.get("nama_spbu")) or clean_text(row.get("nomor_spbu")),
                "nomor_spbu": clean_text(row.get("nomor_spbu")),
                "alamat": clean_text(row.get("alamat")),
                "jenis_lokasi": "",
                "kecamatan": clean_text(row.get("kecamatan")),
                "media_bbm": clean_text(row.get("media_bbm")),
                "lat": row.get("lat"),
                "lon": row.get("lon"),
                "sumber_master": "CSV",
            })

    monitor = pd.DataFrame(records)

    if monitor.empty:
        return monitor, df_pengujian, df_relasi

    monitor["kecamatan"] = monitor["kecamatan"].fillna("").astype(str).str.strip().str.title()

    # Label yang enak dibaca di filter/dashboard.
    def make_label(r):
        nama = clean_text(r.get("nama_spbu"))
        nomor = clean_text(r.get("nomor_spbu"))
        if nama and nomor and _norm(nomor) not in _norm(nama):
            return f"{nama} | {nomor}"
        return nama or nomor or "SPBU Tanpa Nama"

    monitor["spbu_label"] = monitor.apply(make_label, axis=1)

    # Pengaman label duplikat.
    dup = monitor["spbu_label"].duplicated(keep=False)
    monitor.loc[dup & monitor["spbu_id"].notna(), "spbu_label"] = monitor.loc[
        dup & monitor["spbu_id"].notna()
    ].apply(lambda r: f"{r['spbu_label']} | ID {int(r['spbu_id'])}", axis=1)

    # -------------------------
    # Siapkan data pengujian PUBBM
    # -------------------------
    peng = df_pengujian.copy() if not df_pengujian.empty else pd.DataFrame()
    rel = df_relasi.copy() if not df_relasi.empty else pd.DataFrame()

    if peng.empty:
        for col in [
            "pengujian_id_terakhir", "tanggal_pengujian", "jenis_pengujian", "hasil_pengujian",
            "nomor_order", "nomor_sertifikat", "penera_1", "penera_2", "berlaku_sampai",
            "sisa_hari", "status_tera", "nozzle_terakhir", "nozzle_acuan",
        ]:
            monitor[col] = None
        monitor["status_tera"] = STATUS_BELUM_UJI
        monitor["nozzle_terakhir"] = 0
        monitor["nozzle_acuan"] = 0
        return monitor, peng, rel

    # Hanya PUBBM yang mempunyai spbu_id.
    if "spbu_id" not in peng.columns:
        peng["spbu_id"] = None
    peng = peng[peng["spbu_id"].notna()].copy()

    if peng.empty:
        monitor["status_tera"] = STATUS_BELUM_UJI
        monitor["nozzle_terakhir"] = 0
        monitor["nozzle_acuan"] = 0
        return monitor, peng, rel

    peng["spbu_id"] = pd.to_numeric(peng["spbu_id"], errors="coerce")
    peng["id_num"] = pd.to_numeric(peng["id"], errors="coerce").fillna(0)
    peng["tanggal_pengujian_dt"] = pd.to_datetime(peng.get("tanggal_pengujian"), errors="coerce")
    peng["berlaku_sampai_dt"] = pd.to_datetime(peng.get("berlaku_sampai"), errors="coerce")

    # Hitung jumlah nozzle berdasarkan pengujian_uttp.
    if not rel.empty and "pengujian_id" in rel.columns:
        counts = (
            rel.groupby("pengujian_id")
            .size()
            .rename("jumlah_nozzle")
            .reset_index()
        )
        peng = peng.merge(counts, left_on="id", right_on="pengujian_id", how="left")
    else:
        peng["jumlah_nozzle"] = 0

    peng["jumlah_nozzle"] = pd.to_numeric(peng["jumlah_nozzle"], errors="coerce").fillna(0).astype(int)

    # Pengujian terakhir = tanggal terbaru, tie-breaker ID terbesar.
    latest = (
        peng.sort_values(["spbu_id", "tanggal_pengujian_dt", "id_num"], na_position="first")
        .groupby("spbu_id", as_index=False)
        .tail(1)
        .copy()
    )

    # Pengujian acuan = jumlah nozzle terbanyak, lalu tanggal terbaru, lalu ID terbesar.
    acuan = (
        peng.sort_values(["spbu_id", "jumlah_nozzle", "tanggal_pengujian_dt", "id_num"], na_position="first")
        .groupby("spbu_id", as_index=False)
        .tail(1)[["spbu_id", "jumlah_nozzle"]]
        .rename(columns={"jumlah_nozzle": "nozzle_acuan"})
    )

    latest = latest.merge(acuan, on="spbu_id", how="left")

    today = pd.Timestamp(date.today())
    latest["sisa_hari"] = (latest["berlaku_sampai_dt"].dt.normalize() - today).dt.days

    def status_from_row(r):
        if pd.isna(r.get("berlaku_sampai_dt")):
            return STATUS_DATA_KURANG
        sisa = r.get("sisa_hari")
        if pd.isna(sisa):
            return STATUS_DATA_KURANG
        if sisa < 0:
            return STATUS_KEDALUWARSA
        if sisa <= BATAS_JATUH_TEMPO_HARI:
            return STATUS_JATUH_TEMPO
        return STATUS_AKTIF

    latest["status_tera"] = latest.apply(status_from_row, axis=1)

    latest_keep = latest[[
        "spbu_id",
        "id",
        "tanggal_pengujian",
        "jenis_pengujian",
        "hasil",
        "nomor_order",
        "nomor_sertifikat",
        "penera_1",
        "penera_2",
        "berlaku_sampai",
        "sisa_hari",
        "status_tera",
        "jumlah_nozzle",
        "nozzle_acuan",
    ]].copy()

    latest_keep = latest_keep.rename(columns={
        "id": "pengujian_id_terakhir",
        "hasil": "hasil_pengujian",
        "jumlah_nozzle": "nozzle_terakhir",
    })

    monitor["spbu_id"] = pd.to_numeric(monitor["spbu_id"], errors="coerce")
    monitor = monitor.merge(latest_keep, on="spbu_id", how="left")

    monitor["status_tera"] = monitor["status_tera"].fillna(STATUS_BELUM_UJI)
    monitor["nozzle_terakhir"] = pd.to_numeric(monitor["nozzle_terakhir"], errors="coerce").fillna(0).astype(int)
    monitor["nozzle_acuan"] = pd.to_numeric(monitor["nozzle_acuan"], errors="coerce").fillna(0).astype(int)

    return monitor, peng, rel


# =========================================================
# DETAIL NOZZLE PENGUJIAN TERAKHIR
# =========================================================
def get_detail_nozzle_latest(row_spbu, df_relasi, df_uttp):
    pengujian_id = row_spbu.get("pengujian_id_terakhir")
    if pd.isna(pengujian_id) or df_relasi.empty:
        return pd.DataFrame()

    rel = df_relasi.copy()
    detail = rel[rel["pengujian_id"] == pengujian_id].copy()
    if detail.empty:
        return detail

    uttp = df_uttp.copy() if not df_uttp.empty else pd.DataFrame()
    if not uttp.empty:
        if "jenis_uttp" in uttp.columns:
            uttp = uttp[
                uttp["jenis_uttp"].fillna("").astype(str).str.strip().eq("Pompa Ukur BBM")
            ].copy()

        keep = [c for c in ["id", "merk", "tipe", "nomor_seri"] if c in uttp.columns]
        if keep:
            uttp = uttp[keep].rename(columns={"id": "uttp_id"})
            detail = detail.merge(uttp, on="uttp_id", how="left")

    for col in ["no_dispenser", "posisi", "media", "k_faktor", "urutan", "merk", "tipe", "nomor_seri"]:
        if col not in detail.columns:
            detail[col] = ""

    detail["urutan_num"] = pd.to_numeric(detail["urutan"], errors="coerce")
    detail = detail.sort_values(["urutan_num", "id"], na_position="last")

    out = detail[[
        "no_dispenser", "posisi", "media", "merk", "tipe", "nomor_seri", "k_faktor"
    ]].copy()

    out.columns = [
        "No. Dispenser", "Posisi", "Media", "Merk", "Tipe", "No. Seri", "K-Faktor"
    ]

    return out.reset_index(drop=True)


# =========================================================
# KLIK MARKER -> PENDING
# =========================================================
def pick_from_click(map_state, df_context, state_prefix):
    if not map_state:
        return False

    clicked = map_state.get("last_object_clicked")
    if not clicked:
        return False

    latc, lonc = clicked.get("lat"), clicked.get("lng")
    if None in (latc, lonc):
        return False

    if not {"lat", "lon", "spbu_label", "kecamatan"}.issubset(df_context.columns):
        return False

    tmp = df_context[["lat", "lon", "spbu_label", "kecamatan"]].dropna(subset=["lat", "lon"]).copy()
    if tmp.empty:
        return False

    idx = ((tmp["lat"] - latc) ** 2 + (tmp["lon"] - lonc) ** 2).idxmin()

    st.session_state[f"{state_prefix}_pending_pick"] = {
        "name": str(df_context.loc[idx, "spbu_label"]),
        "kec": str(df_context.loc[idx, "kecamatan"]),
    }

    return True


# =========================================================
# CARD STATUS TERPILIH
# =========================================================
def render_detail_spbu(info):
    status = info.get("status_tera", STATUS_BELUM_UJI)
    color = STATUS_COLOR.get(status, "#64748B")

    st.markdown("---")
    st.markdown(
        f"""
        <div style="background:#F8FAFC; padding:18px 20px; border-radius:14px; border-left:6px solid {color};">
            <div style="display:flex; justify-content:space-between; gap:12px; align-items:flex-start; flex-wrap:wrap;">
                <div>
                    <div style="font-size:22px; font-weight:800; color:#0F172A;">⛽ {info.get('spbu_label', '-')}</div>
                    <div style="font-size:13px; color:#475569; margin-top:6px;">
                        <b>Kecamatan:</b> {clean_text(info.get('kecamatan')) or '-'}<br>
                        <b>Alamat:</b> {clean_text(info.get('alamat')) or '-'}<br>
                        <b>Media BBM:</b> {clean_text(info.get('media_bbm')) or '-'}
                    </div>
                </div>
                <div class="status-chip" style="background:{color};">{status}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pengujian Terakhir", format_date_id(info.get("tanggal_pengujian")))
    c2.metric("Berlaku Sampai", format_date_id(info.get("berlaku_sampai")))
    c3.metric("Sisa Masa Tera", format_sisa_hari(info.get("sisa_hari")))
    c4.metric("Nozzle Pengujian Terakhir", int(info.get("nozzle_terakhir", 0) or 0))

    st.caption(
        f"Nozzle acuan (pengujian dengan jumlah nozzle terbanyak): "
        f"{int(info.get('nozzle_acuan', 0) or 0)}"
    )


# =========================================================
# DASHBOARD SPBU
# =========================================================
def render_dashboard_spbu():
    # -----------------------------------------------------
    # LOAD DATA
    # -----------------------------------------------------
    try:
        df_csv = load_spbu_csv(FILE_SPBU)
    except Exception as exc:
        st.error(f"Data koordinat SPBU tidak dapat dibaca: {exc}")
        return

    geo = load_geojson(FILE_GEOJSON) if os.path.exists(FILE_GEOJSON) else None

    try:
        df_spbu_db, df_pengujian, df_relasi, df_uttp = load_supabase_bundle()
    except Exception as exc:
        st.error(f"Data Supabase tidak dapat dibaca: {exc}")
        return

    monitor, df_peng_pubbm, df_relasi_all = build_monitoring_data(
        df_csv=df_csv,
        df_spbu=df_spbu_db,
        df_pengujian=df_pengujian,
        df_relasi=df_relasi,
    )

    # -----------------------------------------------------
    # NAVIGASI
    # -----------------------------------------------------
    col_back, col_home, col_space = st.columns([1.4, 1.4, 5])

    with col_back:
        if st.button(
            "← Dashboard Tera Ulang",
            use_container_width=True,
            key="btn_spbu_kembali_dashboard",
        ):
            st.session_state.halaman_dashboard = "home_dashboard"
            st.rerun()

    with col_home:
        if st.button(
            "🏠 Home SMART METRO",
            use_container_width=True,
            key="btn_spbu_kembali_home",
        ):
            st.session_state.halaman = "home"
            st.session_state.halaman_dashboard = "home_dashboard"
            st.rerun()

    render_main_header(
        "⛽ Dashboard Pengawasan SPBU - Kabupaten Tangerang",
        "Monitoring masa berlaku tera, riwayat pengujian, nozzle, dan K-Faktor PUBBM",
    )

    if monitor.empty:
        st.warning("Data SPBU belum tersedia.")
        return

    # -----------------------------------------------------
    # FILTER SIDEBAR
    # -----------------------------------------------------
    st.sidebar.markdown("---")
    st.sidebar.subheader("Filter Pengawasan")

    for key, default in {
        "spbu_last_changed": "kec",
        "spbu_status_sel": "(Semua)",
        "spbu_kec_sel": "(Semua)",
        "spbu_name_sel": "(Semua)",
        "spbu_force_sync": False,
    }.items():
        st.session_state.setdefault(key, default)

    def _mark_change(which):
        st.session_state["spbu_last_changed"] = which

    pending = st.session_state.pop("spbu_pending_pick", None)
    if pending:
        st.session_state.update({
            "spbu_last_changed": "name",
            "spbu_kec_sel": pending["kec"],
            "spbu_name_sel": pending["name"],
            "spbu_force_sync": True,
        })
        st.rerun()

    status_ops = ["(Semua)"] + [s for s in STATUS_ORDER if s in set(monitor["status_tera"])]

    if st.session_state["spbu_force_sync"]:
        st.session_state["spbu_status_w"] = (
            st.session_state["spbu_status_sel"]
            if st.session_state["spbu_status_sel"] in status_ops
            else "(Semua)"
        )
    else:
        st.session_state.setdefault("spbu_status_w", "(Semua)")
        if st.session_state["spbu_status_w"] not in status_ops:
            st.session_state["spbu_status_w"] = "(Semua)"

    status_pick = st.sidebar.selectbox(
        "Status Tera",
        status_ops,
        key="spbu_status_w",
        on_change=_mark_change,
        args=("status",),
    )

    base_status = monitor.copy()
    if status_pick != "(Semua)":
        base_status = base_status[base_status["status_tera"] == status_pick]

    all_kec = uniq(base_status["kecamatan"], clean=True) if not base_status.empty else []
    kec_ops = ["(Semua)"] + all_kec

    if st.session_state["spbu_force_sync"]:
        st.session_state["spbu_kec_w"] = (
            st.session_state["spbu_kec_sel"]
            if st.session_state["spbu_kec_sel"] in kec_ops
            else "(Semua)"
        )
    else:
        st.session_state.setdefault("spbu_kec_w", "(Semua)")
        if st.session_state["spbu_kec_w"] not in kec_ops:
            st.session_state["spbu_kec_w"] = "(Semua)"

    kec_pick = st.sidebar.selectbox(
        "Kecamatan",
        kec_ops,
        key="spbu_kec_w",
        on_change=_mark_change,
        args=("kec",),
    )

    base_kec = base_status.copy()
    if kec_pick != "(Semua)":
        base_kec = base_kec[base_kec["kecamatan"] == kec_pick]

    all_spbu = uniq(base_kec["spbu_label"], clean=False) if not base_kec.empty else []
    spbu_ops = ["(Semua)"] + all_spbu

    if st.session_state["spbu_force_sync"]:
        st.session_state["spbu_name_w"] = (
            st.session_state["spbu_name_sel"]
            if st.session_state["spbu_name_sel"] in spbu_ops
            else "(Semua)"
        )
        st.session_state["spbu_force_sync"] = False
    else:
        st.session_state.setdefault("spbu_name_w", "(Semua)")
        if st.session_state["spbu_name_w"] not in spbu_ops:
            st.session_state["spbu_name_w"] = "(Semua)"

    nama_pick = st.sidebar.selectbox(
        "Nama SPBU",
        spbu_ops,
        key="spbu_name_w",
        on_change=_mark_change,
        args=("name",),
    )

    # Sinkronkan state final.
    new_status = status_pick
    new_kec = kec_pick
    new_name = nama_pick

    if st.session_state["spbu_last_changed"] == "name" and new_name != "(Semua)":
        row = monitor[monitor["spbu_label"] == new_name]
        if not row.empty:
            new_kec = row.iloc[0]["kecamatan"] or "(Semua)"
            new_status = row.iloc[0]["status_tera"] or "(Semua)"

    need_rerun = False
    for state_key, new_value in [
        ("spbu_status_sel", new_status),
        ("spbu_kec_sel", new_kec),
        ("spbu_name_sel", new_name),
    ]:
        if st.session_state[state_key] != new_value:
            st.session_state[state_key] = new_value
            need_rerun = True

    if need_rerun:
        st.session_state["spbu_force_sync"] = True
        st.rerun()

    status_sel = st.session_state["spbu_status_sel"]
    kec_sel = st.session_state["spbu_kec_sel"]
    nama_sel = st.session_state["spbu_name_sel"]

    # KPI memakai lingkup kecamatan/nama, tetapi tidak dipengaruhi filter status.
    kpi_df = monitor.copy()
    if kec_sel != "(Semua)":
        kpi_df = kpi_df[kpi_df["kecamatan"] == kec_sel]
    if nama_sel != "(Semua)":
        kpi_df = kpi_df[kpi_df["spbu_label"] == nama_sel]

    # Data map/table memakai seluruh filter.
    fdf = monitor.copy()
    if status_sel != "(Semua)":
        fdf = fdf[fdf["status_tera"] == status_sel]
    if kec_sel != "(Semua)":
        fdf = fdf[fdf["kecamatan"] == kec_sel]
    if nama_sel != "(Semua)":
        fdf = fdf[fdf["spbu_label"] == nama_sel]

    # -----------------------------------------------------
    # KPI
    # -----------------------------------------------------
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total SPBU", len(kpi_df))
    c2.metric("Tera Aktif", int((kpi_df["status_tera"] == STATUS_AKTIF).sum()))
    c3.metric(f"≤ {BATAS_JATUH_TEMPO_HARI} Hari", int((kpi_df["status_tera"] == STATUS_JATUH_TEMPO).sum()))
    c4.metric("Kedaluwarsa", int((kpi_df["status_tera"] == STATUS_KEDALUWARSA).sum()))
    c5.metric("Belum Ada Pengujian", int((kpi_df["status_tera"] == STATUS_BELUM_UJI).sum()))

    incomplete_count = int((kpi_df["status_tera"] == STATUS_DATA_KURANG).sum())
    if incomplete_count:
        st.caption(f"ℹ️ {incomplete_count} SPBU sudah memiliki pengujian tetapi data masa berlaku belum lengkap.")

    # -----------------------------------------------------
    # PRIORITAS PENGAWASAN
    # -----------------------------------------------------
    if nama_sel == "(Semua)":
        priority = kpi_df[
            kpi_df["status_tera"].isin([STATUS_KEDALUWARSA, STATUS_JATUH_TEMPO])
        ].copy()

        if not priority.empty:
            priority["prioritas"] = priority["status_tera"].map({
                STATUS_KEDALUWARSA: 0,
                STATUS_JATUH_TEMPO: 1,
            })
            priority["sisa_sort"] = pd.to_numeric(priority["sisa_hari"], errors="coerce").fillna(999999)
            priority = priority.sort_values(["prioritas", "sisa_sort", "spbu_label"]).head(15)

            st.subheader("🚨 Prioritas Pengawasan")
            priority_view = priority[[
                "spbu_label", "kecamatan", "status_tera", "berlaku_sampai", "sisa_hari", "nozzle_terakhir"
            ]].copy()
            priority_view["berlaku_sampai"] = priority_view["berlaku_sampai"].apply(format_date_id)
            priority_view["sisa_hari"] = priority_view["sisa_hari"].apply(format_sisa_hari)
            priority_view.columns = [
                "SPBU", "Kecamatan", "Status", "Berlaku Sampai", "Sisa Waktu", "Nozzle Terakhir"
            ]
            st.dataframe(priority_view, use_container_width=True, hide_index=True)

    # -----------------------------------------------------
    # DETAIL SPBU TERPILIH
    # -----------------------------------------------------
    if nama_sel != "(Semua)":
        detail_row = monitor[monitor["spbu_label"] == nama_sel]
        if not detail_row.empty:
            info = detail_row.iloc[0]
            render_detail_spbu(info)

            st.markdown("#### 🧾 Pengujian Terakhir")
            d1, d2 = st.columns(2)
            with d1:
                st.write("**Jenis Pengujian:**", clean_text(info.get("jenis_pengujian")) or "-")
                st.write("**Nomor Sertifikat:**", clean_text(info.get("nomor_sertifikat")) or "-")
                st.write("**Nomor Order:**", clean_text(info.get("nomor_order")) or "-")
            with d2:
                st.write("**Hasil:**", clean_text(info.get("hasil_pengujian")) or "-")
                st.write("**Penera 1:**", clean_text(info.get("penera_1")) or "-")
                st.write("**Penera 2:**", clean_text(info.get("penera_2")) or "-")

            detail_nozzle = get_detail_nozzle_latest(info, df_relasi_all, df_uttp)
            st.markdown("#### 🔧 Nozzle & K-Faktor Pengujian Terakhir")

            if detail_nozzle.empty:
                st.info("Belum ada detail nozzle / K-Faktor untuk pengujian terakhir.")
            else:
                st.dataframe(detail_nozzle, use_container_width=True, hide_index=True)

            # Riwayat pengujian SPBU
            spbu_id = info.get("spbu_id")
            if pd.notna(spbu_id) and not df_peng_pubbm.empty:
                hist = df_peng_pubbm[df_peng_pubbm["spbu_id"] == float(spbu_id)].copy()
                if not hist.empty:
                    hist = hist.sort_values(["tanggal_pengujian_dt", "id_num"], ascending=False)
                    with st.expander("📚 Riwayat Tera / Tera Ulang"):
                        hist_view = hist[[
                            "tanggal_pengujian", "jenis_pengujian", "nomor_sertifikat", "hasil",
                            "berlaku_sampai", "jumlah_nozzle", "penera_1"
                        ]].copy()
                        hist_view["tanggal_pengujian"] = hist_view["tanggal_pengujian"].apply(format_date_id)
                        hist_view["berlaku_sampai"] = hist_view["berlaku_sampai"].apply(format_date_id)
                        hist_view.columns = [
                            "Tanggal", "Jenis", "Nomor Sertifikat", "Hasil",
                            "Berlaku Sampai", "Jumlah Nozzle", "Penera"
                        ]
                        st.dataframe(hist_view, use_container_width=True, hide_index=True)

    # -----------------------------------------------------
    # PETA
    # -----------------------------------------------------
    st.subheader("🗺️ Peta Status Tera SPBU")

    center = [-6.2, 106.55]
    zoom = 10

    coords = fdf[["lat", "lon"]].dropna() if {"lat", "lon"}.issubset(fdf.columns) else pd.DataFrame()

    if not coords.empty:
        if nama_sel != "(Semua)":
            r = fdf.iloc[0]
            if pd.notna(r["lat"]) and pd.notna(r["lon"]):
                center = [float(r["lat"]), float(r["lon"])]
                zoom = 16
        elif len(coords) == 1:
            center = [float(coords.iloc[0]["lat"]), float(coords.iloc[0]["lon"])]
            zoom = 14

    m = folium.Map(location=center, zoom_start=zoom, control_scale=True, tiles=None)
    folium.TileLayer("OpenStreetMap", control=False).add_to(m)

    if geo:
        folium.GeoJson(
            geo,
            name="Batas Kecamatan",
            style_function=lambda x: {"color": "#334155", "weight": 1.5, "fillOpacity": 0},
            tooltip=folium.GeoJsonTooltip(fields=["kec_label"], aliases=["Kecamatan:"]),
        ).add_to(m)

    if not coords.empty:
        cluster = MarkerCluster(name="SPBU").add_to(m)

        for _, r in fdf.iterrows():
            if pd.isna(r["lat"]) or pd.isna(r["lon"]):
                continue

            is_sel = nama_sel != "(Semua)" and r["spbu_label"] == nama_sel
            status = r.get("status_tera", STATUS_BELUM_UJI)
            color = STATUS_COLOR.get(status, "#64748B")

            popup_html = (
                f"<b>{r['spbu_label']}</b><br>"
                f"Kecamatan: {clean_text(r.get('kecamatan')) or '-'}<br>"
                f"Status: <b>{status}</b><br>"
                f"Pengujian terakhir: {format_date_id(r.get('tanggal_pengujian'))}<br>"
                f"Berlaku sampai: {format_date_id(r.get('berlaku_sampai'))}<br>"
                f"Sisa: {format_sisa_hari(r.get('sisa_hari'))}<br>"
                f"Nozzle terakhir: {int(r.get('nozzle_terakhir', 0) or 0)}"
            )

            folium.CircleMarker(
                location=[float(r["lat"]), float(r["lon"])],
                radius=12 if is_sel else 9,
                color=color,
                weight=3 if is_sel else 2,
                fill=True,
                fill_color=color,
                fill_opacity=0.95 if is_sel else 0.78,
                tooltip=r["spbu_label"],
                popup=folium.Popup(popup_html, max_width=330),
            ).add_to(cluster)

        if nama_sel == "(Semua)" and len(coords) > 1:
            m.fit_bounds(
                [
                    [coords["lat"].min(), coords["lon"].min()],
                    [coords["lat"].max(), coords["lon"].max()],
                ],
                padding=(30, 30),
            )

    # Legenda status
    legend_html = """
    <div style="position: fixed; bottom: 35px; left: 35px; z-index: 9999;
                background: white; padding: 10px 12px; border-radius: 8px;
                border: 1px solid #CBD5E1; font-size: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.12);">
        <b>Status Tera</b><br>
        <span style="color:#16A34A;">●</span> Aktif<br>
        <span style="color:#F59E0B;">●</span> Akan jatuh tempo<br>
        <span style="color:#DC2626;">●</span> Kedaluwarsa<br>
        <span style="color:#6B7280;">●</span> Belum ada pengujian / data belum lengkap
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl(collapsed=False).add_to(m)

    map_state = st_folium(
        m,
        height=540,
        use_container_width=True,
        key="spbu_map",
    )

    if pick_from_click(map_state, fdf if not fdf.empty else monitor, "spbu"):
        st.rerun()


# =========================================================
# RUN
# =========================================================
def run():
    render_dashboard_spbu()
