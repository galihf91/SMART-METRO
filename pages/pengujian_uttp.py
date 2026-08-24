import streamlit as st
from pathlib import Path


# =========================================================
# PATH PROYEK
# File ini diasumsikan berada di folder pages/
# =========================================================
BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"


# =========================================================
# SESSION STATE NAVIGASI PENGUJIAN UTTP
# =========================================================
def init_session_state():
    if "halaman_uttp" not in st.session_state:
        st.session_state.halaman_uttp = "home_uttp"


def pindah_halaman_uttp(nama_halaman):
    """Memindahkan halaman di dalam menu Pengujian UTTP."""
    st.session_state.halaman_uttp = nama_halaman
    st.rerun()


def kembali_ke_smart_metro():
    """
    Kembali ke halaman utama SMART METRO.

    Sesuaikan nilai 'home' apabila router aplikasi utama
    menggunakan nama halaman yang berbeda.
    """
    st.session_state.halaman = "home"
    st.session_state.halaman_uttp = "home_uttp"
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
# HALAMAN UTAMA PENGUJIAN UTTP
# =========================================================
def halaman_home_uttp():
    # Sidebar disembunyikan hanya pada halaman menu Pengujian UTTP
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

    col_back, col_space = st.columns([1, 5])

    with col_back:
        if st.button(
            "← SMART METRO",
            use_container_width=True,
            key="btn_kembali_smart_metro"
        ):
            kembali_ke_smart_metro()

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
        st.title("Pengujian UTTP")
        st.markdown(
            "### SMART METRO"
        )
        st.write(
            "Pelayanan pengujian, pembuatan cerapan, "
            "dan penerbitan sertifikat UTTP."
        )

    st.divider()

    st.subheader("Pilih Jenis UTTP")
    st.write(
        "Silakan pilih jenis UTTP yang akan diuji:"
    )

    # =====================================================
    # BARIS PERTAMA
    # =====================================================
    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            st.markdown("## ⚖️ Timbangan Jembatan")
            st.write(
                "Pengujian Timbangan Jembatan."
            )
            st.write(
                "**Output:** Cerapan PDF dan Sertifikat PDF"
            )

            if st.button(
                "Masuk ke Timbangan Jembatan",
                use_container_width=True,
                key="menu_uttp_tj"
            ):
                pindah_halaman_uttp("tj")

    with col2:
        with st.container(border=True):
            st.markdown("## ⚖️ Timbangan")
            st.write(
                "Pengujian Timbangan Elektronik, Timbangan "
                "Bobot Ingsut, Neraca Obat, Timbangan Sentisimal, "
                "dan Timbangan Pegas."
            )
            st.write(
                "**Output:** Cerapan PDF dan Sertifikat PDF"
            )

            if st.button(
                "Masuk ke Pengujian Timbangan",
                use_container_width=True,
                key="menu_uttp_timbangan"
            ):
                pindah_halaman_uttp("timbangan")

    # =====================================================
    # BARIS KEDUA
    # =====================================================
    col3, col4 = st.columns(2)

    with col3:
        with st.container(border=True):
            st.markdown("## ⛽ PUBBM")
            st.write(
                "Pengujian Pompa Ukur Bahan Bakar Minyak."
            )
            st.write(
                "**Output:** Sertifikat PDF"
            )

            if st.button(
                "Masuk ke PUBBM",
                use_container_width=True,
                key="menu_uttp_pubbm"
            ):
                pindah_halaman_uttp("pubbm")

    with col4:
        with st.container(border=True):
            st.markdown("## ⚡ kWh Meter")
            st.write(
                "Pengujian alat ukur energi listrik."
            )
            st.write(
                "**Output:** Sertifikat PDF"
            )

            if st.button(
                "Masuk ke kWh Meter",
                use_container_width=True,
                key="menu_uttp_kwh"
            ):
                pindah_halaman_uttp("kwh")

    # =====================================================
    # BARIS KETIGA
    # =====================================================
    col5, col6 = st.columns(2)

    with col5:
        with st.container(border=True):
            st.markdown("## 📋 UTTP Umum")
            st.write(
                "Pengujian UTTP umum untuk pembuatan "
                "sertifikat tanpa cerapan."
            )
            st.write(
                "**Output:** Sertifikat PDF"
            )

            if st.button(
                "Masuk ke Pengujian UTTP",
                use_container_width=True,
                key="menu_uttp_umum"
            ):
                pindah_halaman_uttp("uttp")

    with col6:
        with st.container(border=True):
            st.markdown("## 💧 Meter Air")
            st.write(
                "Pengujian Meter Air."
            )
            st.write(
                "**Output:** Cerapan PDF dan Sertifikat PDF"
            )

            if st.button(
                "Masuk ke Meter Air",
                use_container_width=True,
                key="menu_uttp_meter_air"
            ):
                pindah_halaman_uttp("meter_air")
    
    # =====================================================
    # BARIS KEEMPAT
    # =====================================================
    col7, col8 = st.columns(2)

    with col7:
        with st.container(border=True):
            st.markdown("## 🚛 Tangki Ukur Mobil")
            st.write(
                "Pengujian Tangki Ukur Mobil untuk cairan "
                "BBM dan KIMIA."
            )
            st.write(
                "**Output:** Cerapan PDF dan Sertifikat PDF"
            )

            if st.button(
                "Masuk ke Tangki Ukur Mobil",
                use_container_width=True,
                key="menu_uttp_tangki_ukur_mobil"
            ):
                pindah_halaman_uttp("tangki_ukur_mobil")

    with col8:
        st.empty()
        
    st.divider()
    st.caption("SMART METRO — Pengujian UTTP")        

# =========================================================
# ROUTER INTERNAL PENGUJIAN UTTP
# =========================================================
def run():
    init_session_state()
    sembunyikan_navigasi_otomatis()

    halaman_aktif = st.session_state.halaman_uttp

    if halaman_aktif == "home_uttp":
        halaman_home_uttp()

    elif halaman_aktif == "tj":
        from modules.timbangan_jembatan.app_tj import run
        run()


    elif halaman_aktif == "timbangan":
        from modules.timbangan.app_timbangan import run
        run()


    elif halaman_aktif == "pubbm":
        from modules.pubbm.app_pubbm import run
        run()


    elif halaman_aktif == "kwh":
        from modules.kwh_meter.app_kwh import run
        run()
    
    
    elif halaman_aktif == "meter_air":
        from modules.meter_air.app_meter_air import run
        run()
    
    
    elif halaman_aktif == "tangki_ukur_mobil":
        from modules.tangki_ukur_mobil.app_tangki_ukur_mobil import run
        run()
    
    
    elif halaman_aktif == "uttp":
        from modules.uttp.app_uttp import run
        run()
    
    
    else:
        st.session_state.halaman_uttp = "home_uttp"
        st.rerun()
