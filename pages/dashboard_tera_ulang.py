import streamlit as st
from pathlib import Path


# =========================================================
# PATH PROYEK
# File ini berada di folder pages/
# =========================================================
BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "logo_smartmetro.png"


# =========================================================
# SESSION STATE DASHBOARD TERA ULANG
# =========================================================
def init_session_state():
    if "halaman_dashboard" not in st.session_state:
        st.session_state.halaman_dashboard = "home_dashboard"


def pindah_halaman_dashboard(nama_halaman):
    """Memindahkan halaman di dalam menu Dashboard Tera Ulang."""
    st.session_state.halaman_dashboard = nama_halaman
    st.rerun()


def kembali_ke_smart_metro():
    """Kembali ke halaman utama SMART METRO."""
    st.session_state.halaman = "home"
    st.session_state.halaman_dashboard = "home_dashboard"
    st.rerun()


# =========================================================
# SEMBUNYIKAN NAVIGASI OTOMATIS STREAMLIT
# =========================================================
def sembunyikan_navigasi_otomatis():
    st.markdown(
        """
        <style>
            [data-testid="stSidebarNav"] {
                display: none !important;
            }

            [data-testid="stSidebarNavItems"] {
                display: none !important;
            }

            [data-testid="stSidebarNavSeparator"] {
                display: none !important;
            }
        </style>
        """,
        unsafe_allow_html=True
    )


# =========================================================
# HALAMAN UTAMA DASHBOARD TERA ULANG
# =========================================================
def halaman_home_dashboard():
    # Sidebar disembunyikan pada halaman pilihan dashboard
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"] {
                display: none !important;
            }

            [data-testid="collapsedControl"] {
                display: none !important;
            }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Tombol kembali ke halaman utama SMART METRO
    col_back, col_space = st.columns([1, 5])

    with col_back:
        if st.button(
            "← SMART METRO",
            use_container_width=True,
            key="btn_kembali_smart_metro_dashboard"
        ):
            kembali_ke_smart_metro()

    # Header halaman (logo + judul, jarak diatur presisi)
    if LOGO_PATH.exists():
        import base64

        logo_base64 = base64.b64encode(
            LOGO_PATH.read_bytes()
        ).decode("utf-8")

        gambar_logo = (
            '<img src="data:image/png;base64,'
            + logo_base64
            + '" style="width: 260px; flex-shrink: 0;" />'
        )
    else:
        gambar_logo = ""

    st.markdown(
        f"""
        <div style="
            display: flex;
            align-items: center;
            gap: 16px;
            margin-top: -10px;
            margin-bottom: 10px;
        ">
            {gambar_logo}
            <div>
                <h1 style="
                    margin: 0;
                    font-size: 2.2rem;
                    font-weight: 700;
                ">
                    Dashboard Tera Ulang
                </h1>
                <h3 style="
                    margin: 4px 0 0 0;
                    font-size: 1.3rem;
                    font-weight: 600;
                ">
                    SMART METRO
                </h3>
                <p style="
                    margin: 8px 0 0 0;
                    font-size: 1rem;
                ">
                    Informasi persebaran dan status pelayanan
                    tera ulang di Kabupaten Tangerang.
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


    st.divider()

    st.subheader("Pilih Dashboard")
    st.write(
        "Silakan pilih dashboard yang akan ditampilkan:"
    )

    col1, col2, col3 = st.columns(3)
    # =====================================================
    # DASHBOARD PASAR
    # =====================================================
    with col1:
        with st.container(border=True):
            st.markdown("## 🏪 Dashboard Pasar")

            st.write(
                "Menampilkan data pasar, jumlah timbangan, "
                "status tera ulang, persebaran lokasi, "
                "dan perkembangan pelayanan dari tahun ke tahun."
            )

            st.write(
                "**Informasi utama:** Pasar, pedagang, "
                "jenis timbangan, dan lokasi pelayanan."
            )

            if st.button(
                "Masuk ke Dashboard Pasar",
                use_container_width=True,
                key="menu_dashboard_pasar"
            ):
                pindah_halaman_dashboard("pasar")

    # =====================================================
    # DASHBOARD SPBU
    # =====================================================
    with col2:
        with st.container(border=True):
            st.markdown("## ⛽ Dashboard SPBU")

            st.write(
                "Menampilkan lokasi SPBU, persebaran SPBU "
                "per kecamatan, alamat, dan media BBM "
                "yang tersedia."
            )

            st.write(
                "**Informasi utama:** SPBU, kecamatan, "
                "media BBM, dan lokasi pada peta."
            )

            if st.button(
                "Masuk ke Dashboard SPBU",
                use_container_width=True,
                key="menu_dashboard_spbu"
            ):
                pindah_halaman_dashboard("spbu")

    st.divider()
    st.caption("SMART METRO — Dashboard Tera Ulang")

    # =====================================================
    # DASHBOARD UTTP
    # =====================================================
    with col3:
        with st.container(border=True):
            st.markdown("## ⚖️ Dashboard UTTP")
    
            st.write(
                "Menampilkan data kepemilikan UTTP perusahaan, "
                "status masa berlaku tera, jenis UTTP, "
                "serta riwayat pengujian."
            )
    
            st.write(
                "**Informasi utama:** Pemilik UTTP, jenis alat, "
                "status tera, masa berlaku, dan pengujian terakhir."
            )
    
            if st.button(
                "Masuk ke Dashboard UTTP",
                use_container_width=True,
                key="menu_dashboard_uttp"
            ):
                pindah_halaman_dashboard("uttp")
# =========================================================
# ROUTER INTERNAL DASHBOARD TERA ULANG
# =========================================================
def run():
    init_session_state()
    sembunyikan_navigasi_otomatis()

    halaman_aktif = st.session_state.halaman_dashboard

    if halaman_aktif == "home_dashboard":
        halaman_home_dashboard()

    elif halaman_aktif == "pasar":
        from modules.dashboard_pasar.app_dashboard_pasar import (
            run as run_dashboard_pasar
        )

        run_dashboard_pasar()


    elif halaman_aktif == "spbu":
        from modules.dashboard_spbu.app_dashboard_spbu import (
            run as run_dashboard_spbu
        )

        run_dashboard_spbu()
    elif halaman_aktif == "uttp":
        from modules.dashboard_uttp.app_dashboard_uttp import (
            run as run_dashboard_uttp
        )
    
        run_dashboard_uttp()
    else:
        st.session_state.halaman_dashboard = "home_dashboard"
        st.rerun()
