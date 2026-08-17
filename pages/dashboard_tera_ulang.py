import streamlit as st
from pathlib import Path


# =========================================================
# PATH PROYEK
# File ini berada di folder pages/
# =========================================================
BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"


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

    # Header halaman
    col_logo, col_title = st.columns([1, 5])

    with col_logo:
        if LOGO_PATH.exists():
            st.markdown(
                "<div style='margin-top:-18px;'>",
                unsafe_allow_html=True
            )

            st.image(
                str(LOGO_PATH),
                width=130
            )

            st.markdown(
                "</div>",
                unsafe_allow_html=True
            )

    with col_title:
        st.title("Dashboard Tera Ulang")
        st.markdown("### SMART METRO")
        st.write(
            "Informasi persebaran dan status pelayanan "
            "tera ulang di Kabupaten Tangerang."
        )

    st.divider()

    st.subheader("Pilih Dashboard")
    st.write(
        "Silakan pilih dashboard yang akan ditampilkan:"
    )

    col1, col2 = st.columns(2)

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

    else:
        st.session_state.halaman_dashboard = "home_dashboard"
        st.rerun()
