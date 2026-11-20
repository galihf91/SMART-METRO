import html
import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from datetime import datetime
from io import StringIO
import re
import numpy as np
import json
import glob
import base64
import os


# =========================
# KONSTANTA DASHBOARD SPBU
# =========================
FILE_GEOJSON = "data/batas_kecamatan_tangerang.geojson"

# =========================
# FUNGSI BASE64 UNTUK HEADER
# =========================
def get_base64_of_image(image_path):
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except:
        return None

def render_main_header(title, subtitle, image_path="assets/background_header.jpeg"):
    if not os.path.exists(image_path):
        st.warning(f"⚠️ File header tidak ditemukan: `{os.path.abspath(image_path)}`. Gunakan fallback.")
        img_b64 = None
    else:
        img_b64 = get_base64_of_image(image_path)

    mime = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"

    if img_b64:
        st.markdown(f"""
        <style>
        .main-header {{
            width: 100%; height: 280px;
            background-image: linear-gradient(rgba(0,0,0,0.5), rgba(0,0,0,0.5)), url("data:{mime};base64,{img_b64}");
            background-size: cover; background-position: center 30%; background-repeat: no-repeat;
            border-radius: 16px; margin-bottom: 30px; display: flex; flex-direction: column;
            justify-content: center; align-items: center; text-align: center;
            box-shadow: 0 8px 20px rgba(0,0,0,0.2); background-color: #4B0082;
        }}
        .main-header h1 {{ color: white; font-size: 38px; font-weight: 700; text-shadow: 2px 2px 8px black; padding: 0 20px; }}
        .main-header p {{ color: rgba(255,255,255,0.95); font-size: 18px; text-shadow: 1px 1px 4px black; padding: 0 20px; }}
        </style>
        <div class="main-header"><h1>{title}</h1><p>{subtitle}</p></div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="background: linear-gradient(90deg, #4B0082, #8000FF); padding: 30px 25px; border-radius: 16px;
                    margin-bottom: 30px; text-align: center; box-shadow: 0 8px 16px rgba(0,0,0,0.15);">
            <h1 style="color: white; font-size: 32px;">{title}</h1>
            <p style="color: rgba(255,255,255,0.9); font-size: 18px;">{subtitle}</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<style>#MainMenu,footer{visibility:hidden;}</style>", unsafe_allow_html=True)

# =========================
# FUNGSI UTILITAS UMUM
# =========================
def _norm(s):
    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(s).strip().lower()
    )
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
    """Baca koordinat CSV secara toleran, lalu validasi lintang/bujur."""
    try:
        if val is None or pd.isna(val):
            return np.nan, np.nan
        teks = str(val).strip().strip("()[]")
        if not teks:
            return np.nan, np.nan
        # CSV umum: "-6.123, 106.456" atau "106.456, -6.123".
        # Regex juga menerima spasi, titik koma, dan tanda kurung.
        angka = re.findall(r"[-+]?\d+(?:\.\d+)?", teks)
        if len(angka) < 2:
            return np.nan, np.nan
        lat, lon = float(angka[0]), float(angka[1])
        if abs(lat) > 90 and abs(lon) <= 90:
            lat, lon = lon, lat
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return np.nan, np.nan
        if lat == 0 and lon == 0:
            return np.nan, np.nan
        return lat, lon
    except (TypeError, ValueError, OverflowError):
        return np.nan, np.nan

def uniq(series, clean=False):
    s = series.dropna().astype(str).str.strip()
    if clean: s = s.str.title()
    s = s[~s.str.lower().isin(["", "nan", "none", "null", "na", "n/a", "-", "--"])]
    return sorted(s.unique())

def marker_color(year, selected_year):
    if year is None or year == 0: return "gray"
    if year == selected_year: return "green"
    if year == selected_year - 1: return "orange"
    return "red"



# ==========================================
# LOAD DATA SPBU DARI SUPABASE
# ==========================================
@st.cache_resource
def get_supabase_spbu():
    from supabase import create_client

    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]

    return create_client(url, key)


@st.cache_data(ttl=60, show_spinner=False)
def load_spbu_supabase():
    sb = get_supabase_spbu()

    rows = []
    offset = 0
    page_size = 500

    # Ambil semua data dengan pagination
    while True:
        response = (
            sb.table("spbu")
            .select("*")
            .order("id")
            .range(offset, offset + page_size - 1)
            .execute()
        )

        batch = response.data or []
        rows.extend(batch)

        if len(batch) < page_size:
            break

        offset += page_size

    columns = [
        "id", "nama_spbu", "nomor_spbu",
        "alamat", "kecamatan", "media_bbm",
        "lat", "lon", "media_list"
    ]

    if not rows:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(rows)

    for col in [
        "nama_spbu", "nomor_spbu",
        "alamat", "kecamatan", "media_bbm"
    ]:
        if col not in df.columns:
            df[col] = ""

        df[col] = df[col].fillna("").astype(str).str.strip()

    # Pertahankan nomor SPBU sebagai teks
    # Gunakan nomor sebagai label jika tersedia
    df["nama_spbu"] = df["nomor_spbu"].where(
        df["nomor_spbu"].ne(""),
        df["nama_spbu"]
    )

    # Bedakan SPBU dengan label identik
    duplicate = df["nama_spbu"].duplicated(keep=False)
    df.loc[duplicate, "nama_spbu"] = df.loc[duplicate].apply(
        lambda r: f"{r['nama_spbu']} (ID {r['id']})",
        axis=1
    )

    df = df[df["nama_spbu"].ne("")].copy()
    df["kecamatan"] = df["kecamatan"].str.title()

    # Media BBM per SPBU
    def parse_media(value):
        if isinstance(value, list):
            return [str(x).strip() for x in value if str(x).strip()]

        if isinstance(value, dict):
            return [str(x).strip() for x in value.values() if str(x).strip()]

        text = str(value or "").strip()

        if text.startswith("["):
            try:
                items = json.loads(text)
                if isinstance(items, list):
                    return [
                        str(x).strip() for x in items
                        if str(x).strip()
                    ]
            except (ValueError, TypeError):
                pass

        return [
            x.strip() for x in re.split(r"[;,]", text)
            if x.strip()
        ]

    df["media_list"] = df["media_bbm"].apply(parse_media)
    df["media_bbm"] = df["media_list"].apply(
        lambda items: ", ".join(items)
    )

    # Koordinat dari Supabase
    def get_numeric(*names):
        for name in names:
            if name in df.columns:
                values = pd.to_numeric(df[name], errors="coerce")
                if values.notna().any():
                    return values

        return pd.Series(np.nan, index=df.index)

    lat = get_numeric("latitude", "lat")
    lon = get_numeric("longitude", "lon", "lng")

    # Alternatif format koordinat teks
    for col in ["koordinat", "koordinat_spbu", "coordinates"]:
        if col in df.columns:
            coords = df[col].apply(parse_coord)
            lat = lat.fillna(coords.apply(lambda p: p[0]))
            lon = lon.fillna(coords.apply(lambda p: p[1]))

    valid = (
        lat.between(-90, 90)
        & lon.between(-180, 180)
        & ~((lat == 0) & (lon == 0))
    )

    df["lat"] = lat.where(valid, np.nan)
    df["lon"] = lon.where(valid, np.nan)

    return df



# =========================
# KLIK MARKER -> PENDING
# =========================
def pick_from_click(map_state, df_context, name_col, kec_col, state_prefix):
    """Pilih marker hanya sekali per klik dan hanya di titik yang terlihat."""
    if not map_state:
        return False
    clicked = map_state.get("last_object_clicked")
    if not isinstance(clicked, dict):
        return False
    try:
        latc = float(clicked.get("lat"))
        lonc = float(clicked.get("lng"))
    except (ValueError, TypeError):
        return False

    kolom = {"lat", "lon", name_col, kec_col}
    if not kolom.issubset(df_context.columns):
        return False
    tmp = df_context[["lat", "lon", name_col, kec_col]].dropna().copy()
    if tmp.empty:
        return False

    d2 = (tmp["lat"] - latc) ** 2 + (tmp["lon"] - lonc) ** 2
    idx = d2.idxmin()
    # Klik pada background peta tidak boleh memilih SPBU terdekat.
    if float(d2.loc[idx]) > 0.005 ** 2:
        return False

    sig = (round(latc, 6), round(lonc, 6), str(tmp.loc[idx, name_col]))
    sig_key = f"{state_prefix}_last_click_sig"
    if st.session_state.get(sig_key) == sig:
        return False
    st.session_state[sig_key] = sig
    st.session_state[f"{state_prefix}_pending_pick"] = {
        "name": str(tmp.loc[idx, name_col]),
        "kec": str(tmp.loc[idx, kec_col]),
    }
    return True

# =========================
# DASHBOARD SPBU
# =========================
def render_dashboard_spbu():
    try:
        df_spbu = load_spbu_supabase()
    except Exception as exc:
        st.error(f"Gagal membaca data SPBU dari Supabase: {exc}")
        return

    if df_spbu.empty:
        st.warning("Belum ada data SPBU di Supabase.")
        return

    try:
        geo = (
            load_geojson(FILE_GEOJSON)
            if os.path.exists(FILE_GEOJSON)
            else None
        )
    except (OSError, ValueError) as exc:
        st.warning(
            f"Batas kecamatan tidak dapat dibaca: {exc}. "
            "Peta titik SPBU tetap ditampilkan."
        )
        geo = None

    # =====================================================
    # NAVIGASI
    # =====================================================
    col_back, col_home, col_space = st.columns([1.4, 1.4, 5])

    with col_back:
        if st.button(
            "← Dashboard Tera Ulang",
            use_container_width=True,
            key="btn_spbu_kembali_dashboard"
        ):
            st.session_state.halaman_dashboard = "home_dashboard"
            st.rerun()

    with col_home:
        if st.button(
            "🏠 Home SMART METRO",
            use_container_width=True,
            key="btn_spbu_kembali_home"
        ):
            st.session_state.halaman = "home"
            st.session_state.halaman_dashboard = "home_dashboard"
            st.rerun()
    render_main_header("⛽ Dashboard SPBU - Kabupaten Tangerang",
                       "Dinas Perindustrian dan Perdagangan - Bidang Kemetrologian")

    # --- helper darken color (hanya di sini) ---
    def darken(hex_color, percent):
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        r = max(0, int(r * (1 - percent/100)))
        g = max(0, int(g * (1 - percent/100)))
        b = max(0, int(b * (1 - percent/100)))
        return f'#{r:02x}{g:02x}{b:02x}'

    # --- filter sidebar ---
    st.sidebar.markdown("---"); st.sidebar.subheader("Filter SPBU")
    all_media = sorted({m for lst in df_spbu['media_list'] for m in lst}) if 'media_list' in df_spbu else []
    media_pick = st.sidebar.multiselect("Media BBM", all_media, key='spbu_media_pick')

    base = df_spbu.copy()
    if media_pick and 'media_list' in base.columns:
        base = base[base['media_list'].apply(lambda L: all(m in L for m in media_pick))]

    # --- state management ---
    for key in ['spbu_last_changed','spbu_kec_sel','spbu_name_sel','spbu_force_sync']:
        st.session_state.setdefault(key, "kec" if key=='spbu_last_changed' else "(Semua)" if 'sel' in key else False)

    def _mark_change(which):
        st.session_state['spbu_last_changed'] = which
        st.session_state.pop('spbu_last_click_sig', None)

    pending = st.session_state.pop('spbu_pending_pick', None)
    if pending:
        st.session_state.update({'spbu_last_changed':'name','spbu_kec_sel':pending['kec'],
                                 'spbu_name_sel':pending['name'],'spbu_force_sync':True})
        st.rerun()

    all_kec = uniq(base['kecamatan'], clean=True) if not base.empty else []
    all_spbu = uniq(base['nama_spbu'], clean=False) if not base.empty else []
    kec_ops = ['(Semua)'] + all_kec

    # sinkronisasi widget
    if st.session_state['spbu_force_sync']:
        st.session_state['spbu_kec_w'] = st.session_state['spbu_kec_sel'] if st.session_state['spbu_kec_sel'] in kec_ops else '(Semua)'
        st.session_state['spbu_name_w'] = st.session_state['spbu_name_sel'] if st.session_state['spbu_name_sel'] in (['(Semua)']+all_spbu) else '(Semua)'
        st.session_state['spbu_force_sync'] = False
    else:
        for w in ['spbu_kec_w','spbu_name_w']: st.session_state.setdefault(w, '(Semua)')
        if st.session_state['spbu_kec_w'] not in kec_ops: st.session_state['spbu_kec_w'] = '(Semua)'
        if st.session_state['spbu_name_w'] not in (['(Semua)']+all_spbu): st.session_state['spbu_name_w'] = '(Semua)'

    kec_pick = st.sidebar.selectbox("Kecamatan", kec_ops, key='spbu_kec_w', on_change=_mark_change, args=('kec',))
    if kec_pick != '(Semua)':
        spbu_in_kec = uniq(base[base['kecamatan']==kec_pick]['nama_spbu'], clean=False)
        spbu_ops = ['(Semua)'] + spbu_in_kec
        if st.session_state['spbu_name_sel'] != '(Semua)' and st.session_state['spbu_name_sel'] not in spbu_in_kec:
            spbu_ops.append(st.session_state['spbu_name_sel'])
    else:
        spbu_ops = ['(Semua)'] + all_spbu
    nama_pick = st.sidebar.selectbox("Nama SPBU", spbu_ops, key='spbu_name_w', on_change=_mark_change, args=('name',))

    # aturan sinkronisasi
    new_kec, new_name = kec_pick, nama_pick
    if st.session_state['spbu_last_changed'] == 'name' and new_name != '(Semua)':
        kc = base[base['nama_spbu']==new_name]['kecamatan'].dropna()
        if not kc.empty: new_kec = kc.iloc[0]
    if st.session_state['spbu_last_changed'] == 'kec' and new_kec != '(Semua)' and new_name != '(Semua)':
        if base[(base['kecamatan']==new_kec)&(base['nama_spbu']==new_name)].empty:
            new_name = '(Semua)'

    need_rerun = False
    if st.session_state['spbu_kec_sel'] != new_kec:
        st.session_state['spbu_kec_sel'] = new_kec; need_rerun = True
    if st.session_state['spbu_name_sel'] != new_name:
        st.session_state['spbu_name_sel'] = new_name; need_rerun = True
    if need_rerun:
        st.session_state['spbu_force_sync'] = True; st.rerun()

    kec, nama_spbu = st.session_state['spbu_kec_sel'], st.session_state['spbu_name_sel']
    fdf = base.copy()
    if kec != '(Semua)': fdf = fdf[fdf['kecamatan'] == kec]
    if nama_spbu != '(Semua)': fdf = fdf[fdf['nama_spbu'] == nama_spbu]

    # --- KPI & CARD ---
    if nama_spbu == '(Semua)':
        if kec == '(Semua)':
            c1,c2,c3 = st.columns(3)
            with c1: st.metric("Total Kecamatan", fdf['kecamatan'].nunique() if not fdf.empty else 0)
            with c2: st.metric("Total SPBU", fdf['nama_spbu'].nunique() if not fdf.empty else 0)
            varian = len(media_pick) if media_pick else len({m for L in fdf['media_list'] for m in L}) if not fdf.empty else 0
            with c3: st.metric("Varian Media BBM", varian)
        else:
            total_spbu = fdf['nama_spbu'].nunique() if not fdf.empty else 0
            media_list = sorted({m for L in fdf['media_list'] for m in L}) if not fdf.empty else []
            col1,col2 = st.columns(2)
            with col1:
                st.markdown(f"""
                <div style="background:linear-gradient(135deg,#667eea,#764ba2); color:white; padding:20px; border-radius:12px; text-align:center;">
                    <div style="font-size:14px; opacity:0.9; margin-bottom:5px;">Total SPBU di</div>
                    <div style="font-size:20px; font-weight:700; letter-spacing:0.5px;">{kec.upper()}</div>
                    <div style="font-size:32px; font-weight:700;">{total_spbu}</div>
                    <div style="font-size:14px; opacity:0.9; margin-bottom:5px;">SPBU</div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                # Header card media BBM
                st.markdown(f"""
                <div style="background:linear-gradient(135deg,#f093fb,#f5576c); color:white; padding:20px; border-radius:12px; margin-bottom:25px;">
                    <div style="font-size:14px; opacity:0.9; margin-bottom:5px;">Media BBM Tersedia di</div>
                    <div style="font-size:20px; font-weight:700; letter-spacing:0.5px;">{kec.upper()}</div>
                </div>
                """, unsafe_allow_html=True)

                if media_list:
                    # Warna-warna untuk card
                    colors = ['#FF6B6B','#4ECDC4','#FFD166','#06D6A0','#118AB2',
                              '#EF476F','#073B4C','#7209B7','#F3722C','#90BE6D','#43AA8B','#577590']
                    # Ikon untuk tiap jenis BBM
                    icon_map = {
                        'Pertalite': '⛽', 'Pertamax': '⚡', 'Solar': '🛢️', 
                        'Diesel': '🚛', 'Super': '🌟', 'V-Power': '💎',
                        'BP 92': '🅱️', 'BP Ultimate': '💎', 'Pertamina Dex': '🛢️'
                    }

                    # Tentukan jumlah kolom per baris (maks 4, minimal 2)
                    per_row = min(4, len(media_list))
                    per_row = max(per_row, 2)  # minimal 2 kolom agar tidak terlalu lebar

                    # Loop per baris
                    for row_start in range(0, len(media_list), per_row):
                        row_media = media_list[row_start:row_start + per_row]
                        cols = st.columns(len(row_media))

                        for i, media in enumerate(row_media):
                            with cols[i]:
                                color = colors[(row_start + i) % len(colors)]
                                darkened = darken(color, 20)
                                icon = icon_map.get(media, '⛽')

                                st.markdown(f"""
                                <div style="
                                    background: linear-gradient(135deg, {color} 0%, {darkened} 100%);
                                    color: white;
                                    padding: 20px 12px;
                                    border-radius: 14px;
                                    text-align: center;
                                    min-height: 120px;
                                    display: flex;
                                    flex-direction: column;
                                    justify-content: center;
                                    align-items: center;
                                    box-shadow: 0 8px 16px rgba(0,0,0,0.15);
                                    border: 1px solid rgba(255,255,255,0.3);
                                    margin-bottom: 0;  /* jarak antar baris diatur dengan div terpisah */
                                ">
                                    <div style="font-size: 24px; margin-bottom: 8px;">{icon}</div>
                                    <div style="font-size: 14px; font-weight: 700; margin-bottom: 10px; 
                                                text-shadow: 0 2px 4px rgba(0,0,0,0.3);">{media}</div>
                                    <div style="
                                        background-color: rgba(255,255,255,0.3);
                                        padding: 6px 16px;
                                        border-radius: 30px;
                                        font-size: 11px;
                                        font-weight: 700;
                                        letter-spacing: 1px;
                                        backdrop-filter: blur(4px);
                                        border: 1px solid rgba(255,255,255,0.4);
                                    ">
                                        TERSEDIA
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

                        # Beri jarak antar baris
                        if row_start + per_row < len(media_list):
                            st.markdown('<div style="margin-bottom: 25px;"></div>', unsafe_allow_html=True)

                else:
                    st.markdown("""
                    <div style="background:rgba(255,255,255,0.1); padding:40px 20px; border-radius:12px; 
                                text-align:center; border:2px dashed rgba(255,255,255,0.3); margin-top:20px;">
                        <div style="font-size:48px; opacity:0.5; margin-bottom:15px;">⛽</div>
                        <div style="font-size:16px; font-weight:600; color:white;">Tidak ada data media BBM</div>
                    </div>
                    """, unsafe_allow_html=True)
    else:
        # detail SPBU
        info = base[base['nama_spbu']==nama_spbu].iloc[0]
        st.markdown("---")
        st.markdown(f"""
        <div style="background:#f3e8ff; padding:14px 16px; border-radius:12px; border-left:5px solid #8000FF;">
            <h4 style="color:#4B0082;">⛽ {nama_spbu}</h4>
            <p style="font-size:13px;"><b>Kecamatan:</b> {kec}<br>
            <b>Alamat:</b> {info['alamat']}<br><b>Media BBM:</b> {info['media_bbm']}</p>
        </div>
        """, unsafe_allow_html=True)

        media_list = fdf.iloc[0]['media_list'] if not fdf.empty and 'media_list' in fdf.columns else []
        if media_list:
                st.markdown("#### 📋 Media BBM Tersedia")
                
                # Warna untuk card
                colors = ["#8000FF","#4B0082","#6A5ACD","#9370DB","#8A2BE2",
                          "#FF6B6B","#4ECDC4","#FFD166","#06D6A0","#118AB2"]
                # Ikon untuk tiap jenis BBM
                icon_map = {
                    'Pertalite': '⛽', 'Pertamax': '⚡', 'Solar': '🛢️', 
                    'Diesel': '🚛', 'Super': '🌟', 'V-Power': '💎',
                    'BP 92': '🅱️', 'BP Ultimate': '💎', 'Pertamina Dex': '🛢️'
                }

                # Tentukan jumlah kolom per baris (maks 4)
                per_row = min(4, len(media_list))
                
                # Loop per baris
                for row_start in range(0, len(media_list), per_row):
                    row_media = media_list[row_start:row_start + per_row]
                    cols = st.columns(len(row_media))

                    for i, media in enumerate(row_media):
                        with cols[i]:
                            color_idx = (row_start + i) % len(colors)
                            color = colors[color_idx]
                            darkened = darken(color, 20)
                            icon = icon_map.get(media, '⛽')

                            st.markdown(f"""
                            <div style="
                                background: linear-gradient(135deg, {color} 0%, {darkened} 100%);
                                color: white;
                                padding: 22px 12px;
                                border-radius: 16px;
                                min-height: 130px;
                                display: flex;
                                flex-direction: column;
                                justify-content: center;
                                align-items: center;
                                text-align: center;
                                box-shadow: 0 8px 16px rgba(0,0,0,0.2);
                                border: 1px solid rgba(255,255,255,0.3);
                                margin-bottom: 0;
                            ">
                                <div style="font-size: 28px; margin-bottom: 10px;">{icon}</div>
                                <div style="font-size: 15px; font-weight: 800; margin-bottom: 12px; 
                                            text-shadow: 0 2px 4px rgba(0,0,0,0.3);">{media}</div>
                                <div style="
                                    background-color: rgba(255,255,255,0.3);
                                    padding: 6px 18px;
                                    border-radius: 30px;
                                    font-size: 12px;
                                    font-weight: 700;
                                    letter-spacing: 1px;
                                    backdrop-filter: blur(4px);
                                    border: 1px solid rgba(255,255,255,0.4);
                                ">
                                    TERSEDIA
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                    # Beri jarak antar baris
                    if row_start + per_row < len(media_list):
                        st.markdown('<div style="margin-bottom: 25px;"></div>', unsafe_allow_html=True)

        else:
            st.info("SPBU ini belum memiliki data Media BBM.")

    # --- PETA SPBU ---
    st.subheader("🗺️ Peta Lokasi SPBU")
    center, zoom = [-6.2,106.55], 10
    coords = fdf[['lat','lon']].dropna() if {'lat','lon'}.issubset(fdf.columns) else pd.DataFrame()
    if not coords.empty:
        if nama_spbu != '(Semua)':
            r = fdf[fdf['nama_spbu']==nama_spbu].iloc[0]
            center = [float(r['lat']), float(r['lon'])]; zoom = 16
        elif len(coords) == 1:
            center = [coords.iloc[0]['lat'], coords.iloc[0]['lon']]; zoom = 14
    m = folium.Map(location=center, zoom_start=zoom, control_scale=True, tiles=None)
    folium.TileLayer("OpenStreetMap", control=False).add_to(m)
    if geo:
        folium.GeoJson(geo, name="Batas Kecamatan",
                       style_function=lambda x: {"color":"#8000FF","weight":2,"fillOpacity":0},
                       tooltip=folium.GeoJsonTooltip(fields=["kec_label"], aliases=["Kecamatan:"])).add_to(m)
    if not coords.empty:
        cluster = MarkerCluster(name="SPBU").add_to(m)
        for _, r in fdf.iterrows():
            if pd.isna(r['lat']) or pd.isna(r['lon']): continue
            is_sel = nama_spbu != '(Semua)' and r['nama_spbu'].strip().lower() == nama_spbu.strip().lower()
            folium.CircleMarker(
                location=[float(r['lat']), float(r['lon'])],
                radius=12 if is_sel else 9,
                color="#8000FF", fill=True, fill_opacity=0.9 if is_sel else 0.65,
                tooltip=r['nama_spbu'],
                popup=folium.Popup(f"<b>{html.escape(str(r['nama_spbu']))}</b><br>{html.escape(str(r['alamat']))}<br>Media: {html.escape(str(r['media_bbm']))}", max_width=280)
            ).add_to(cluster)
        if nama_spbu == '(Semua)' and len(coords) > 1:
            m.fit_bounds([[coords['lat'].min(), coords['lon'].min()],
                          [coords['lat'].max(), coords['lon'].max()]], padding=(30,30))
    folium.LayerControl(collapsed=False).add_to(m)
    map_state = st_folium(m, height=520, use_container_width=True, key="spbu_map")
    if pick_from_click(map_state, fdf, "nama_spbu", "kecamatan", "spbu"): st.rerun()


# =========================
# JALANKAN DASHBOARD SPBU
# =========================
def run():    
    render_dashboard_spbu()


if __name__ == "__main__":
    run()
