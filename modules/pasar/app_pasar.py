import os
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from supabase import create_client


# ============================================================
# SMART METRO - MODUL DATA PASAR
# ============================================================
# public.pasar         = master pasar
# public.pasar_tahunan = data kegiatan pasar per tahun
#
# Input tahunan:
# Nama Pasar, Tanggal Pelaksanaan, TP, TM, TE, Sentisimal,
# Bobot Ingsut, Neraca, Total UTTP, Total Pedagang, SIMPEL,
# Jumlah Hari
# ============================================================


# ============================================================
# SUPABASE
# ============================================================
@st.cache_resource
def get_supabase():
    url = None
    key = None

    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_ANON_KEY")
    except Exception:
        pass

    if not url or not key:
        try:
            cfg = st.secrets.get("supabase", {})
            url = url or cfg.get("url")
            key = key or cfg.get("key") or cfg.get("anon_key")
        except Exception:
            pass

    url = url or os.getenv("SUPABASE_URL")
    key = key or os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        st.error(
            "Koneksi Supabase belum tersedia. Pastikan SUPABASE_URL dan "
            "SUPABASE_KEY/SUPABASE_ANON_KEY tersedia."
        )
        st.stop()

    return create_client(url, key)

bulan_indonesia = {
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

def format_tanggal_pelaksanaan(tanggal_mulai, tanggal_selesai):
    bulan_mulai = bulan_indonesia[tanggal_mulai.month]
    bulan_selesai = bulan_indonesia[tanggal_selesai.month]

    if tanggal_mulai == tanggal_selesai:
        return (
            f"{tanggal_mulai.day} "
            f"{bulan_mulai} "
            f"{tanggal_mulai.year}"
        )

    if (
        tanggal_mulai.month == tanggal_selesai.month
        and tanggal_mulai.year == tanggal_selesai.year
    ):
        return (
            f"{tanggal_mulai.day}-{tanggal_selesai.day} "
            f"{bulan_mulai} "
            f"{tanggal_mulai.year}"
        )

    return (
        f"{tanggal_mulai.day} {bulan_mulai} {tanggal_mulai.year} - "
        f"{tanggal_selesai.day} {bulan_selesai} {tanggal_selesai.year}"
    )

@st.cache_data(ttl=60, show_spinner=False)
def load_master_pasar():
    try:
        data = (
            get_supabase()
            .table("pasar")
            .select("id,nama_pasar,alamat,kecamatan,latitude,longitude,status,created_at")
            .order("nama_pasar")
            .execute()
            .data
            or []
        )
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Gagal membaca master pasar: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60, show_spinner=False)
def load_pasar_tahunan():
    try:
        data = (
            get_supabase()
            .table("pasar_tahunan")
            .select("*")
            .order("tahun", desc=True)
            .execute()
            .data
            or []
        )
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Gagal membaca data pasar tahunan: {e}")
        return pd.DataFrame()


def clear_cache_pasar():
    load_master_pasar.clear()
    load_pasar_tahunan.clear()


# ============================================================
# UTILITAS
# ============================================================
def safe_int(v, default=0):
    try:
        if v is None or pd.isna(v):
            return default
        return int(v)
    except Exception:
        return default


def safe_float(v, default=0.0):
    try:
        if v is None or pd.isna(v):
            return default
        return float(v)
    except Exception:
        return default


def safe_text(v, default=""):
    try:
        if v is None or pd.isna(v):
            return default
    except Exception:
        if v is None:
            return default
    return str(v).strip()


def get_existing_record(df, pasar_id, tahun):
    if df.empty or "pasar_id" not in df.columns or "tahun" not in df.columns:
        return None

    tmp = df.copy()
    tmp["pasar_id"] = pd.to_numeric(tmp["pasar_id"], errors="coerce")
    tmp["tahun"] = pd.to_numeric(tmp["tahun"], errors="coerce")

    hit = tmp[
        (tmp["pasar_id"] == int(pasar_id))
        & (tmp["tahun"] == int(tahun))
    ]

    if hit.empty:
        return None

    return hit.iloc[0].to_dict()


# ============================================================
# TAMPILAN
# ============================================================
def render_header():
    st.markdown(
        """
        <div style="
            background:linear-gradient(135deg,#4B0082 0%,#7C3AED 100%);
            color:white;
            padding:24px 28px;
            border-radius:16px;
            margin-bottom:18px;
            box-shadow:0 8px 20px rgba(0,0,0,.12);
        ">
            <div style="font-size:30px;font-weight:800;">🏪 Modul Data Pasar</div>
            <div style="font-size:14px;opacity:.92;margin-top:6px;">
                SMART METRO · Bidang Kemetrologian
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_nav():
    c1, c2, _ = st.columns([1.8, 1.5, 6])

    with c1:
        if st.button(
            "← Pengujian UTTP",
            use_container_width=True,
            key="pasar_back"
        ):
            st.session_state.halaman_uttp = "home_uttp"
            st.rerun()

    with c2:
        if st.button(
            "🏠 Home SMART METRO",
            use_container_width=True,
            key="pasar_home"
        ):
            st.session_state.halaman = "home"
            st.session_state.halaman_uttp = "home_uttp"
            st.rerun()


# ============================================================
# DATA TAHUNAN PASAR
# ============================================================
def render_data_tahunan():
    st.subheader("📅 Data Tahunan Pasar")
    st.caption("Input kegiatan tera ulang pasar untuk satu pasar pada satu tahun.")

    df_pasar = load_master_pasar()
    df_tahunan = load_pasar_tahunan()

    if df_pasar.empty:
        st.warning("Master pasar belum tersedia.")
        return

    if "status" in df_pasar.columns:
        aktif = df_pasar[
            df_pasar["status"]
            .fillna("aktif")
            .astype(str)
            .str.lower()
            .eq("aktif")
        ].copy()
        df_ops = aktif if not aktif.empty else df_pasar.copy()
    else:
        df_ops = df_pasar.copy()

    df_ops = df_ops.sort_values("nama_pasar")

    pasar_map = {
        f"{safe_text(r['nama_pasar'])} — {safe_text(r.get('kecamatan', ''))}": int(r["id"])
        for _, r in df_ops.iterrows()
    }

    c1, c2 = st.columns([2.2, 1])

    with c1:
        pasar_label = st.selectbox(
            "Nama Pasar",
            list(pasar_map.keys()),
            key="pasar_input_nama",
        )

    with c2:
        tahun = st.number_input(
            "Tahun Data",
            min_value=2000,
            max_value=2100,
            value=datetime.now().year,
            step=1,
            key="pasar_input_tahun",
        )

    pasar_id = pasar_map[pasar_label]
    master = df_ops[df_ops["id"] == pasar_id].iloc[0]
    existing = get_existing_record(df_tahunan, pasar_id, int(tahun))

    st.markdown(
        f"""
        <div style="
            background:#F5F3FF;
            padding:14px 16px;
            border-radius:12px;
            border-left:5px solid #7C3AED;
            margin:10px 0 16px 0;
        ">
            <b>{safe_text(master.get('nama_pasar'))}</b><br>
            <span style="font-size:13px;">
                Kecamatan: {safe_text(master.get('kecamatan')) or '-'}<br>
                Alamat: {safe_text(master.get('alamat')) or '-'}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if existing:
        st.info(f"Data tahun {int(tahun)} sudah tersedia. Mode: UPDATE.")
    else:
        st.success(f"Belum ada data tahun {int(tahun)}. Mode: DATA BARU.")

    form_key = f"form_pasar_{pasar_id}_{int(tahun)}"

    with st.form(form_key):
        st.markdown("#### Pelaksanaan")

        tanggal_range = st.date_input(
            "Tanggal Pelaksanaan",
            value=(
                datetime.now().date(),
                datetime.now().date()
            ),
            format="DD/MM/YYYY"
        )

        if isinstance(tanggal_range, (tuple, list)) and len(tanggal_range) == 2:
            tanggal_mulai = tanggal_range[0]
            tanggal_selesai = tanggal_range[1]
        else:
            tanggal_mulai = tanggal_range
            tanggal_selesai = tanggal_range
        
        jumlah_hari_otomatis = (
            tanggal_selesai - tanggal_mulai
        ).days + 1

        st.markdown("#### Jumlah Timbangan")

        c1, c2, c3 = st.columns(3)

        with c1:
            tp = st.number_input(
                "TP",
                min_value=0,
                step=1,
                value=safe_int(existing.get("timb_pegas")) if existing else 0,
                help="Timbangan Pegas",
            )

            sentisimal = st.number_input(
                "Sentisimal",
                min_value=0,
                step=1,
                value=safe_int(existing.get("timb_sentisimal")) if existing else 0,
            )

        with c2:
            tm = st.number_input(
                "TM",
                min_value=0,
                step=1,
                value=safe_int(existing.get("timb_meja")) if existing else 0,
                help="Timbangan Meja",
            )

            bobot_ingsut = st.number_input(
                "Bobot Ingsut",
                min_value=0,
                step=1,
                value=safe_int(existing.get("timb_bobot_ingsut")) if existing else 0,
            )

        with c3:
            te = st.number_input(
                "TE",
                min_value=0,
                step=1,
                value=safe_int(existing.get("timb_elektronik")) if existing else 0,
                help="Timbangan Elektronik",
            )

            neraca = st.number_input(
                "Neraca",
                min_value=0,
                step=1,
                value=safe_int(existing.get("neraca")) if existing else 0,
            )

        total_uttp = int(tp + tm + te + sentisimal + bobot_ingsut + neraca)

        st.markdown("#### Rekap Kegiatan")

        r1, r2, r3, r4 = st.columns(4)

        with r1:
            st.metric("Total UTTP", f"{total_uttp:,}".replace(",", "."))

        with r2:
            total_pedagang = st.number_input(
                "Total Pedagang",
                min_value=0,
                step=1,
                value=safe_int(existing.get("total_pedagang")) if existing else 0,
            )

        with r3:
            simpel = st.checkbox(
                "SIMPEL",
                value=(
                    bool(existing.get("simpel"))
                    if existing and existing.get("simpel") is not None
                    else False
                ),
            )

        with r4:
            st.metric(
                "Jumlah Hari",
                jumlah_hari_otomatis
            )

jumlah_hari = jumlah_hari_otomatis

        simpan = st.form_submit_button(
            "💾 Update Data" if existing else "💾 Simpan Data",
            type="primary",
            use_container_width=True,
        )

    if simpan:
        if not tanggal_pelaksanaan.strip():
            st.error("Tanggal Pelaksanaan wajib diisi.")
            return

        payload = {
            "pasar_id": int(pasar_id),
            "tahun": int(tahun),
            "tanggal_pelaksanaan": tanggal_pelaksanaan.strip(),
            "timb_pegas": int(tp),
            "timb_meja": int(tm),
            "timb_elektronik": int(te),
            "timb_sentisimal": int(sentisimal),
            "timb_bobot_ingsut": int(bobot_ingsut),
            "neraca": int(neraca),
            "total_uttp": int(total_uttp),
            "total_pedagang": int(total_pedagang),
            "simpel": bool(simpel),
            "jumlah_hari": int(jumlah_hari),
            "sumber": "smart_metro",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        sb = get_supabase()

        try:
            if existing:
                (
                    sb.table("pasar_tahunan")
                    .update(payload)
                    .eq("id", int(existing["id"]))
                    .execute()
                )
                st.success("Data tahunan pasar berhasil diperbarui.")
            else:
                sb.table("pasar_tahunan").insert(payload).execute()
                st.success("Data tahunan pasar berhasil disimpan.")

            clear_cache_pasar()
            st.rerun()

        except Exception as e:
            st.error(f"Data gagal disimpan: {e}")

    if not df_tahunan.empty and "pasar_id" in df_tahunan.columns:
        hist = df_tahunan[
            pd.to_numeric(df_tahunan["pasar_id"], errors="coerce")
            == int(pasar_id)
        ].copy()

        if not hist.empty:
            st.markdown("---")
            st.markdown("#### Riwayat Data Tahunan")

            rename_cols = {
                "tahun": "Tahun",
                "tanggal_pelaksanaan": "Tanggal Pelaksanaan",
                "timb_pegas": "TP",
                "timb_meja": "TM",
                "timb_elektronik": "TE",
                "timb_sentisimal": "Sentisimal",
                "timb_bobot_ingsut": "Bobot Ingsut",
                "neraca": "Neraca",
                "total_uttp": "Total UTTP",
                "total_pedagang": "Total Pedagang",
                "simpel": "SIMPEL",
                "jumlah_hari": "Jumlah Hari",
            }

            show_cols = [c for c in rename_cols if c in hist.columns]
            hist = hist[show_cols].rename(columns=rename_cols)

            if "Tahun" in hist.columns:
                hist = hist.sort_values("Tahun", ascending=False)

            st.dataframe(hist, use_container_width=True, hide_index=True)


# ============================================================
# MASTER PASAR
# ============================================================
def render_master_pasar():
    st.subheader("🏪 Master Pasar")
    st.caption("Tambah atau perbarui identitas pasar.")

    df = load_master_pasar()

    mode = st.radio(
        "Mode",
        ["Edit Pasar", "Tambah Pasar Baru"],
        horizontal=True,
        key="pasar_master_mode",
    )

    if mode == "Edit Pasar":
        if df.empty:
            st.info("Belum ada master pasar.")
            return

        df2 = df.sort_values("nama_pasar")

        mapping = {
            f"{safe_text(r['nama_pasar'])} — {safe_text(r.get('kecamatan', ''))}": int(r["id"])
            for _, r in df2.iterrows()
        }

        label = st.selectbox(
            "Pilih Pasar",
            list(mapping.keys()),
            key="pasar_master_select",
        )

        pasar_id = mapping[label]
        row = df2[df2["id"] == pasar_id].iloc[0].to_dict()

    else:
        pasar_id = None
        row = {}

    with st.form(f"form_master_pasar_{pasar_id or 'baru'}"):
        c1, c2 = st.columns(2)

        with c1:
            nama_pasar = st.text_input(
                "Nama Pasar",
                value=safe_text(row.get("nama_pasar")),
            )

            kecamatan = st.text_input(
                "Kecamatan",
                value=safe_text(row.get("kecamatan")),
            )

            latitude = st.number_input(
                "Latitude",
                format="%.6f",
                value=safe_float(row.get("latitude")),
            )

        with c2:
            alamat = st.text_area(
                "Alamat",
                value=safe_text(row.get("alamat")),
                height=102,
            )

            status_ops = ["aktif", "nonaktif"]
            old_status = safe_text(row.get("status"), "aktif").lower() or "aktif"
            status_idx = status_ops.index(old_status) if old_status in status_ops else 0

            status = st.selectbox(
                "Status",
                status_ops,
                index=status_idx,
            )

            longitude = st.number_input(
                "Longitude",
                format="%.6f",
                value=safe_float(row.get("longitude")),
            )

        submit = st.form_submit_button(
            "💾 Update Master" if pasar_id else "➕ Simpan Pasar Baru",
            type="primary",
            use_container_width=True,
        )

    if submit:
        if not nama_pasar.strip():
            st.error("Nama Pasar wajib diisi.")
            return

        if not kecamatan.strip():
            st.error("Kecamatan wajib diisi.")
            return

        payload = {
            "nama_pasar": nama_pasar.strip(),
            "alamat": alamat.strip(),
            "kecamatan": kecamatan.strip(),
            "latitude": float(latitude),
            "longitude": float(longitude),
            "status": status,
        }

        sb = get_supabase()

        try:
            if pasar_id:
                (
                    sb.table("pasar")
                    .update(payload)
                    .eq("id", int(pasar_id))
                    .execute()
                )
                st.success("Master pasar berhasil diperbarui.")

            else:
                cek = (
                    sb.table("pasar")
                    .select("id,nama_pasar")
                    .ilike("nama_pasar", nama_pasar.strip())
                    .execute()
                    .data
                    or []
                )

                if cek:
                    st.warning("Nama pasar tersebut sudah tersedia pada master pasar.")
                    return

                sb.table("pasar").insert(payload).execute()
                st.success("Pasar baru berhasil ditambahkan.")

            clear_cache_pasar()
            st.rerun()

        except Exception as e:
            st.error(f"Master pasar gagal disimpan: {e}")

    if not df.empty:
        st.markdown("---")
        st.markdown("#### Daftar Master Pasar")

        cols = [
            c
            for c in [
                "nama_pasar",
                "kecamatan",
                "alamat",
                "latitude",
                "longitude",
                "status",
            ]
            if c in df.columns
        ]

        table = df[cols].copy().rename(
            columns={
                "nama_pasar": "Nama Pasar",
                "kecamatan": "Kecamatan",
                "alamat": "Alamat",
                "latitude": "Latitude",
                "longitude": "Longitude",
                "status": "Status",
            }
        )

        st.dataframe(table, use_container_width=True, hide_index=True)


# ============================================================
# HALAMAN UTAMA
# ============================================================
def render_modul_pasar():
    render_nav()
    render_header()

    tab1, tab2 = st.tabs(
        [
            "📅 Data Tahunan Pasar",
            "🏪 Master Pasar",
        ]
    )

    with tab1:
        render_data_tahunan()

    with tab2:
        render_master_pasar()


def run():
    render_modul_pasar()


if __name__ == "__main__":
    st.set_page_config(
        page_title="Modul Pasar – SMART METRO",
        page_icon="🏪",
        layout="wide",
    )
    run()
