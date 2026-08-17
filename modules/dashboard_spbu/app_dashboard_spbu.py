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

st.set_page_config(
    page_title="Dashboard SPBU – SMART METRO",
    page_icon="⛽",
    layout="wide"
)

# =========================
# KONSTANTA DASHBOARD SPBU
# =========================
FILE_SPBU = "data/Data SPBU Kab. Tangerang.csv"
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
    try:
        if pd.isna(val) or val == "": return np.nan, np.nan
        s = str(val).strip()
        if ',' in s:
            lat, lon = map(float, s.split(',')[:2])
            if abs(lat) > 90: lat, lon = lon, lat
            return lat, lon
        nums = re.findall(r"-?\d+(?:\.\d+)?", s)
        if len(nums) >= 2:
            lat, lon = map(float, nums[:2])
            if abs(lat) > 90: lat, lon = lon, lat
            return lat, lon
    except: pass
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


# =========================
# LOAD DATA SPBU
# =========================
@st.cache_data
def load_spbu_csv(path):
    import csv
    with open(path, 'rb') as f:
        text = f.read().decode('utf-8-sig', errors='ignore')
    if not text.strip():
        return pd.DataFrame()

    # Deteksi delimiter secara manual (lebih stabil)
    first_line = text.splitlines()[0] if text.splitlines() else ''
    count_semi = first_line.count(';')
    count_comma = first_line.count(',')
    sep = ';' if count_semi >= count_comma else ','
    
    # ✅ GUNAKAN io.StringIO, BUKAN pd.StringIO
    df = pd.read_csv(StringIO(text), sep=sep)
    df.columns = [c.strip() for c in df.columns]

    # rename kolom
    rename = {
        'No. SPBU':'nama_spbu','Nama SPBU':'nama_spbu','Alamat':'alamat',
        'Kecamatan':'kecamatan','Koordinat':'koordinat',
        'Media BBM':'media_bbm','Produk BBM':'media_bbm'
    }
    df.rename(columns={k:v for k,v in rename.items() if k in df.columns}, inplace=True)
    
    # pastikan kolom minimal ada
    for col in ['nama_spbu','alamat','kecamatan','koordinat','media_bbm']:
        if col not in df.columns:
            df[col] = ''

    df['nama_spbu'] = df['nama_spbu'].astype(str).str.strip()
    df['kecamatan'] = df['kecamatan'].astype(str).str.strip().str.title()
    df['media_bbm'] = df['media_bbm'].astype(str).str.strip()

    # parse koordinat
    coords = df['koordinat'].apply(parse_coord)
    df['lat'] = pd.to_numeric(coords.apply(lambda x: x[0]), errors='coerce')
    df['lon'] = pd.to_numeric(coords.apply(lambda x: x[1]), errors='coerce')

    # split media menjadi list
    def split_media(x):
        return [m.strip() for m in re.split(r'[;,]', str(x)) if m.strip()] if pd.notna(x) else []
    df['media_list'] = df['media_bbm'].apply(split_media)
    return df


# =========================
# KLIK MARKER -> PENDING
# =========================
def pick_from_click(map_state, df_context, name_col, kec_col, state_prefix):
    if not map_state: return False
    clicked = map_state.get('last_object_clicked')
    if not clicked: return False
    latc, lonc = clicked.get('lat'), clicked.get('lng')
    if None in (latc, lonc): return False
    if not {'lat','lon',name_col,kec_col}.issubset(df_context.columns): return False

    tmp = df_context[['lat','lon',name_col,kec_col]].dropna().copy()
    if tmp.empty: return False
    dist = ((tmp['lat'] - latc)**2 + (tmp['lon'] - lonc)**2).idxmin()
    st.session_state[f"{state_prefix}_pending_pick"] = {
        'name': str(df_context.loc[dist, name_col]),
        'kec': str(df_context.loc[dist, kec_col])
    }
    return True


# =========================
# DASHBOARD SPBU
# =========================
def render_dashboard_spbu():
    df_spbu = load_spbu_csv(FILE_SPBU)
    geo = load_geojson(FILE_GEOJSON) if os.path.exists(FILE_GEOJSON) else None
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

    def _mark_change(which): st.session_state['spbu_last_changed'] = which

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
                popup=folium.Popup(f"<b>{r['nama_spbu']}</b><br>{r['alamat']}<br>Media: {r['media_bbm']}", max_width=280)
            ).add_to(cluster)
        if nama_spbu == '(Semua)' and len(coords) > 1:
            m.fit_bounds([[coords['lat'].min(), coords['lon'].min()],
                          [coords['lat'].max(), coords['lon'].max()]], padding=(30,30))
    folium.LayerControl(collapsed=False).add_to(m)
    map_state = st_folium(m, height=520, use_container_width=True, key="spbu_map")
    if pick_from_click(map_state, base, "nama_spbu", "kecamatan", "spbu"): st.rerun()


# =========================
# JALANKAN DASHBOARD SPBU
# =========================
def run():    
    render_dashboard_spbu()
