import streamlit as st
from pathlib import Path
import importlib


# =========================================================
# KONFIGURASI UTAMA
# Hanya dipanggil satu kali di seluruh aplikasi
# =========================================================
st.set_page_config(
    page_title="SMART METRO",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =========================================================
# PATH PROYEK
# =========================================================
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"


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

            #MainMenu {
                visibility: hidden;
            }

            footer {
                visibility: hidden;
            }
        </style>
        """,
        unsafe_allow_html=True
    )


# =========================================================
# SESSION STATE NAVIGASI UTAMA
# =========================================================
def init_session_state():
    if "halaman" not in st.session_state:
        st.session_state.halaman = "home"


def pindah_halaman(nama_halaman):
    """
    Memindahkan halaman utama SMART METRO.

    Session state internal setiap kelompok menu diatur ulang
    supaya selalu dimulai dari halaman pilihannya.
    """
    if nama_halaman == "pengujian_uttp":
        st.session_state.halaman_uttp = "home_uttp"

    elif nama_halaman == "dashboard_tera_ulang":
        st.session_state.halaman_dashboard = "home_dashboard"

    st.session_state.halaman = nama_halaman
    st.rerun()


# =========================================================
# CSS HALAMAN UTAMA
# =========================================================
def render_home_css():
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"] {
                display: none !important;
            }

            [data-testid="collapsedControl"] {
                display: none !important;
            }

            .block-container {
                max-width: 1180px;
                padding-top: 2rem;
                padding-bottom: 3rem;
            }

            .smart-hero {
                background:
                    radial-gradient(circle at top right,
                    rgba(255, 255, 255, 0.20), transparent 35%),
                    linear-gradient(135deg, #312e81 0%, #6d28d9 55%, #7c3aed 100%);
                border-radius: 24px;
                padding: 38px 42px;
                color: white;
                box-shadow: 0 16px 38px rgba(76, 29, 149, 0.25);
                margin-bottom: 28px;
            }

            .smart-hero h1 {
                font-size: 48px;
                line-height: 1.05;
                margin: 0 0 10px 0;
                font-weight: 800;
                letter-spacing: 0.5px;
            }

            .smart-hero h3 {
                font-size: 22px;
                margin: 0 0 12px 0;
                font-weight: 600;
                color: rgba(255, 255, 255, 0.96);
            }

            .smart-hero p {
                font-size: 16px;
                line-height: 1.65;
                margin: 0;
                max-width: 820px;
                color: rgba(255, 255, 255, 0.88);
            }

            .section-title {
                font-size: 25px;
                font-weight: 750;
                color: #312e81;
                margin-bottom: 3px;
            }

            .section-subtitle {
                font-size: 15px;
                color: #64748b;
                margin-bottom: 16px;
            }

            .menu-card {
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 20px;
                padding: 25px;
                min-height: 315px;
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.07);
                transition: transform 0.2s ease, box-shadow 0.2s ease;
            }

            .menu-card:hover {
                transform: translateY(-3px);
                box-shadow: 0 14px 30px rgba(76, 29, 149, 0.13);
            }

            .menu-icon {
                width: 58px;
                height: 58px;
                border-radius: 16px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 30px;
                margin-bottom: 18px;
                background: linear-gradient(135deg, #ede9fe, #ddd6fe);
            }

            .menu-card h2 {
                font-size: 25px;
                color: #312e81;
                margin: 0 0 10px 0;
            }

            .menu-card p {
                color: #475569;
                font-size: 15px;
                line-height: 1.6;
            }

            .menu-list {
                margin: 15px 0 4px 0;
                padding-left: 20px;
                color: #334155;
                font-size: 14px;
                line-height: 1.8;
            }

            .status-strip {
                margin-top: 28px;
                padding: 16px 20px;
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 14px;
                color: #475569;
                font-size: 14px;
                text-align: center;
            }

            div.stButton > button {
                border-radius: 12px;
                min-height: 48px;
                font-weight: 700;
                border: 1px solid #6d28d9;
                transition: all 0.2s ease;
            }

            div.stButton > button:hover {
                border-color: #4c1d95;
                color: #4c1d95;
                transform: translateY(-1px);
            }
        </style>
        """,
        unsafe_allow_html=True
    )


# =========================================================
# HALAMAN HOME SMART METRO
# =========================================================
def home():
    render_home_css()

    col_logo, col_hero = st.columns([1, 6], vertical_alignment="center")

    with col_logo:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=145)
        else:
            st.markdown(
                """
                <div style="
                    width:125px;
                    height:125px;
                    border-radius:28px;
                    background:linear-gradient(135deg,#6d28d9,#312e81);
                    display:flex;
                    align-items:center;
                    justify-content:center;
                    font-size:58px;
                    box-shadow:0 12px 28px rgba(76,29,149,.25);
                ">
                    ⚖️
                </div>
                """,
                unsafe_allow_html=True
            )

    with col_hero:
        st.markdown(
            """
            <div class="smart-hero">
                <h1>SMART METRO</h1>
                <h3>Smart Metrology Digital Service</h3>
                <p>
                    Digitalisasi Pelayanan Tera dan Tera Ulang
                    Berbasis Dashboard dan Generative AI
                    dalam Mewujudkan Pelayanan Kemetrologian
                    Modern, Cepat, Akurat dan Berintegritas
                    pada Dinas Perindustrian dan Perdagangan
                    Kabupaten Tangerang
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown(
        """
        <div class="section-title">Pilih Layanan</div>
        <div class="section-subtitle">
            Masuk ke layanan pengujian UTTP atau dashboard informasi tera ulang.
        </div>
        """,
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2, gap="large")

    # =====================================================
    # MENU PENGUJIAN UTTP
    # =====================================================
    with col1:
        st.markdown(
            """
            <div class="menu-card">
                <div class="menu-icon">⚖️</div>
                <h2>Pengujian UTTP</h2>
                <p>
                    Pengisian data pengujian serta pembuatan dokumen
                    hasil pengujian UTTP.
                </p>
                <ul class="menu-list">
                    <li>Timbangan Jembatan</li>
                    <li>Timbangan</li>
                    <li>PUBBM</li>
                    <li>Meter kWh</li>
                    <li>UTTP Umum</li>
                    <li>Meter air</li>
                    <li>Tangki Ukur Mobil</li>
                </ul>
                <p>
                    <b>Output:</b> Cerapan dan/atau sertifikat PDF
                    sesuai jenis UTTP.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        if st.button(
            "Masuk ke Pengujian UTTP",
            use_container_width=True,
            type="primary",
            key="btn_home_pengujian_uttp"
        ):
            pindah_halaman("pengujian_uttp")

    # =====================================================
    # MENU DASHBOARD TERA ULANG
    # =====================================================
    with col2:
        st.markdown(
            """
            <div class="menu-card">
                <div class="menu-icon">📊</div>
                <h2>Dashboard Tera Ulang</h2>
                <p>
                    Informasi persebaran lokasi, data pelayanan,
                    dan status tera ulang.
                </p>
                <ul class="menu-list">
                    <li>Dashboard Pasar</li>
                    <li>Dashboard SPBU</li>
                </ul>
                <p>
                    <b>Informasi:</b> Peta lokasi, data kecamatan,
                    jenis UTTP, dan media BBM.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        if st.button(
            "Masuk ke Dashboard Tera Ulang",
            use_container_width=True,
            type="primary",
            key="btn_home_dashboard_tera_ulang"
        ):
            pindah_halaman("dashboard_tera_ulang")

    st.markdown(
        """
        <div class="status-strip">
            SMART METRO • Dinas Perindustrian dan Perdagangan
            Kabupaten Tangerang • Bidang Kemetrologian
        </div>
        """,
        unsafe_allow_html=True
    )


# =========================================================
# PEMANGGIL MODUL DENGAN PENANGANAN ERROR
# =========================================================
def jalankan_modul(module_path, function_name="run"):
    """
    Memuat modul hanya ketika halaman dipilih.

    Hal ini mencegah seluruh modul dimuat bersamaan saat
    aplikasi pertama kali dibuka.
    """
    try:
        module = importlib.import_module(module_path)
        run_function = getattr(module, function_name)
        run_function()

    except ModuleNotFoundError as error:
        st.error(
            "Modul halaman belum ditemukan atau struktur folder "
            "belum sesuai."
        )

        st.code(
            f"Modul yang dicari: {module_path}\n"
            f"Detail: {error}",
            language="text"
        )

        if st.button(
            "← Kembali ke Home",
            key=f"kembali_module_not_found_{module_path}"
        ):
            pindah_halaman("home")

    except AttributeError:
        st.error(
            f"Fungsi `{function_name}()` belum ditemukan "
            f"di modul `{module_path}`."
        )

        st.info(
            f"Tambahkan fungsi berikut pada file tersebut:\n\n"
            f"def {function_name}():\n"
            f"    ..."
        )

        if st.button(
            "← Kembali ke Home",
            key=f"kembali_attribute_error_{module_path}"
        ):
            pindah_halaman("home")

    except Exception as error:
        st.error("Terjadi kesalahan saat membuka halaman.")

        with st.expander("Lihat detail kesalahan"):
            st.exception(error)

        if st.button(
            "← Kembali ke Home",
            key=f"kembali_general_error_{module_path}"
        ):
            pindah_halaman("home")


# =========================================================
# ROUTER UTAMA
# =========================================================
def main():
    init_session_state()
    sembunyikan_navigasi_otomatis()

    halaman_aktif = st.session_state.halaman

    if halaman_aktif == "home":
        home()

    elif halaman_aktif == "pengujian_uttp":
        jalankan_modul(
            "pages.pengujian_uttp",
            "run"
        )

    elif halaman_aktif == "dashboard_tera_ulang":
        jalankan_modul(
            "pages.dashboard_tera_ulang",
            "run"
        )

    else:
        st.session_state.halaman = "home"
        st.rerun()


# =========================================================
# MENJALANKAN APLIKASI
# =========================================================
if __name__ == "__main__":
    main()
