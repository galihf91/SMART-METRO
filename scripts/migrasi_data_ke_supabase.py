from pathlib import Path
import re
import os
import math

import pandas as pd
from supabase import create_client


# =========================================================
# LOKASI PROJECT
# =========================================================
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"


# =========================================================
# AMBIL SUPABASE CREDENTIAL
#
# Prioritas:
# 1. environment variable
# 2. .streamlit/secrets.toml
# =========================================================
def load_supabase_config():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if url and key:
        return url, key

    secrets_path = (
        PROJECT_ROOT
        / ".streamlit"
        / "secrets.toml"
    )

    if not secrets_path.exists():
        raise RuntimeError(
            "SUPABASE_URL dan SUPABASE_KEY tidak ditemukan."
        )

    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    with open(
        secrets_path,
        "rb"
    ) as f:
        secrets = tomllib.load(f)

    url = secrets.get(
        "SUPABASE_URL"
    )

    key = secrets.get(
        "SUPABASE_KEY"
    )

    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL / SUPABASE_KEY "
            "belum tersedia di secrets.toml."
        )

    return url, key


SUPABASE_URL, SUPABASE_KEY = (
    load_supabase_config()
)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# =========================================================
# HELPER
# =========================================================
def clean_text(value):
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    text = str(
        value
    ).strip()

    if text.lower() in {
        "nan",
        "none",
        "null",
    }:
        return ""

    if text.endswith(".0"):
        bagian_awal = text[:-2]

        if bagian_awal.isdigit():
            return bagian_awal

    return text


def clean_number(
    value,
    default=None
):
    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    try:
        if isinstance(
            value,
            str
        ):
            value = (
                value
                .replace(".", "")
                .replace(",", ".")
                .strip()
            )

        return float(
            value
        )

    except (
        TypeError,
        ValueError
    ):
        return default


def clean_int(
    value,
    default=0
):
    angka = clean_number(
        value,
        None
    )

    if angka is None:
        return default

    return int(
        angka
    )


def parse_coordinate(value):
    text = clean_text(
        value
    )

    if not text:
        return None, None

    angka = re.findall(
        r"-?\d+(?:\.\d+)?",
        text
    )

    if len(angka) < 2:
        return None, None

    try:
        lat = float(
            angka[0]
        )

        lon = float(
            angka[1]
        )

        # Jaga-jaga posisi lon,lat terbalik
        if abs(lat) > 90:
            lat, lon = (
                lon,
                lat
            )

        return lat, lon

    except ValueError:
        return None, None


def extract_nomor_spbu(value):
    text = clean_text(
        value
    )

    if not text:
        return ""

    # Contoh:
    # SPBU 34-15717
    # 34.15717
    # 34-15717
    match = re.search(
        r"(?:SPBU\s*)?"
        r"(\d{2}[\.\-]\d{4,6})",
        text,
        re.IGNORECASE,
    )

    if match:
        return (
            match.group(1)
            .replace(".", "-")
        )

    return ""


def tentukan_jenis_lokasi(
    nama
):
    nama_upper = clean_text(
        nama
    ).upper()

    if "PERTASHOP" in nama_upper:
        return "PERTASHOP"

    if "SHELL" in nama_upper:
        return "SHELL"

    if (
        "BP AKR" in nama_upper
        or nama_upper.startswith("BP ")
    ):
        return "BP AKR"

    if "VIVO" in nama_upper:
        return "VIVO"

    if "SPBU" in nama_upper:
        return "SPBU"

    return ""


def read_csv_auto(
    path
):
    with open(
        path,
        "rb"
    ) as f:
        raw = f.read()

    text = raw.decode(
        "utf-8-sig",
        errors="ignore"
    )

    if not text.strip():
        return pd.DataFrame()

    first_line = (
        text.splitlines()[0]
        if text.splitlines()
        else ""
    )

    separator = (
        ";"
        if first_line.count(";")
        >= first_line.count(",")
        else ","
    )

    from io import StringIO

    df = pd.read_csv(
        StringIO(text),
        sep=separator,
    )

    df.columns = [
        str(c).strip()
        for c in df.columns
    ]

    return df


# =========================================================
# STATISTIK
# =========================================================
stat = {
    "perusahaan_insert": 0,
    "perusahaan_update": 0,
    "perusahaan_skip": 0,

    "penera_insert": 0,
    "penera_update": 0,
    "penera_skip": 0,

    "bejana_insert": 0,
    "bejana_update": 0,
    "bejana_skip": 0,

    "media_insert": 0,
    "media_update": 0,

    "pasar_insert": 0,
    "pasar_update": 0,

    "pasar_legacy_insert": 0,
    "pasar_legacy_update": 0,
}


# =========================================================
# PERUSAHAAN
# =========================================================
def cari_perusahaan(
    nama=None,
    nomor_spbu=None,
):
    if nomor_spbu:
        response = (
            supabase
            .table("perusahaan")
            .select("*")
            .eq(
                "nomor_spbu",
                nomor_spbu
            )
            .limit(1)
            .execute()
        )

        if response.data:
            return response.data[0]

    if nama:
        response = (
            supabase
            .table("perusahaan")
            .select("*")
            .ilike(
                "nama_perusahaan",
                nama
            )
            .limit(1)
            .execute()
        )

        if response.data:
            return response.data[0]

    return None


def simpan_perusahaan(
    nama,
    alamat="",
    nomor_spbu="",
    jenis_lokasi="",
    kecamatan="",
    latitude=None,
    longitude=None,
    media_bbm="",
):
    nama = clean_text(
        nama
    )

    alamat = clean_text(
        alamat
    )

    nomor_spbu = clean_text(
        nomor_spbu
    )

    jenis_lokasi = clean_text(
        jenis_lokasi
    )

    kecamatan = clean_text(
        kecamatan
    )

    media_bbm = clean_text(
        media_bbm
    )

    if not nama:
        return None

    existing = cari_perusahaan(
        nama=nama,
        nomor_spbu=nomor_spbu,
    )

    payload = {
        "nama_perusahaan": nama,
    }

    if alamat:
        payload[
            "alamat"
        ] = alamat

    if nomor_spbu:
        payload[
            "nomor_spbu"
        ] = nomor_spbu

    if jenis_lokasi:
        payload[
            "jenis_lokasi"
        ] = jenis_lokasi

    if kecamatan:
        payload[
            "kecamatan"
        ] = kecamatan

    if latitude is not None:
        payload[
            "latitude"
        ] = latitude

    if longitude is not None:
        payload[
            "longitude"
        ] = longitude

    if media_bbm:
        payload[
            "media_bbm"
        ] = media_bbm

    if existing:
        perusahaan_id = (
            existing["id"]
        )

        update_payload = {}

        for key, value in (
            payload.items()
        ):
            if key == "nama_perusahaan":
                continue

            nilai_lama = (
                existing.get(
                    key
                )
            )

            # Data migrasi hanya mengisi / memperkaya.
            # Tidak menghapus data existing.
            if value not in (
                "",
                None,
            ):
                if str(
                    nilai_lama
                    or ""
                ).strip() != str(
                    value
                ).strip():
                    update_payload[
                        key
                    ] = value

        if update_payload:
            (
                supabase
                .table("perusahaan")
                .update(
                    update_payload
                )
                .eq(
                    "id",
                    perusahaan_id
                )
                .execute()
            )

            stat[
                "perusahaan_update"
            ] += 1

        else:
            stat[
                "perusahaan_skip"
            ] += 1

        return perusahaan_id

    response = (
        supabase
        .table("perusahaan")
        .insert(
            payload
        )
        .execute()
    )

    stat[
        "perusahaan_insert"
    ] += 1

    return (
        response.data[0]["id"]
        if response.data
        else None
    )


# =========================================================
# MIGRASI data_perusahaan.xlsx
# =========================================================
def migrasi_perusahaan():
    path = (
        DATA_DIR
        / "data_perusahaan.xlsx"
    )

    if not path.exists():
        print(
            "SKIP: data_perusahaan.xlsx tidak ditemukan"
        )
        return

    print(
        "\n=== MIGRASI PERUSAHAAN ==="
    )

    df = pd.read_excel(
        path,
        engine="openpyxl"
    )

    df.columns = [
        str(c).strip()
        for c in df.columns
    ]

    for _, row in df.iterrows():
        nama = clean_text(
            row.get(
                "Nama Perusahaan"
            )
        )

        alamat = clean_text(
            row.get(
                "Alamat"
            )
        )

        if not nama:
            continue

        simpan_perusahaan(
            nama=nama,
            alamat=alamat,
        )


# =========================================================
# MIGRASI PENERA
# =========================================================
def migrasi_penera():
    path = (
        DATA_DIR
        / "data_penera.xlsx"
    )

    if not path.exists():
        print(
            "SKIP: data_penera.xlsx tidak ditemukan"
        )
        return

    print(
        "\n=== MIGRASI PENERA ==="
    )

    df = pd.read_excel(
        path,
        engine="openpyxl"
    )

    df.columns = [
        str(c).strip()
        for c in df.columns
    ]

    for _, row in df.iterrows():

        nama = clean_text(
            row.get(
                "Nama"
            )
        )

        nip = clean_text(
            row.get(
                "NIP"
            )
        )

        golongan = clean_text(
            row.get(
                "Golongan"
            )
        )

        if not nama:
            continue

        existing = None

        if nip:
            response = (
                supabase
                .table("penera")
                .select("*")
                .eq(
                    "nip",
                    nip
                )
                .limit(1)
                .execute()
            )

            if response.data:
                existing = (
                    response.data[0]
                )

        if existing is None:
            response = (
                supabase
                .table("penera")
                .select("*")
                .ilike(
                    "nama",
                    nama
                )
                .limit(1)
                .execute()
            )

            if response.data:
                existing = (
                    response.data[0]
                )

        payload = {
            "nama": nama,
            "nip": (
                nip
                if nip
                else None
            ),
            "golongan": golongan,
            "status": "aktif",
        }

        if existing:
            (
                supabase
                .table("penera")
                .update(
                    payload
                )
                .eq(
                    "id",
                    existing["id"]
                )
                .execute()
            )

            stat[
                "penera_update"
            ] += 1

        else:
            (
                supabase
                .table("penera")
                .insert(
                    payload
                )
                .execute()
            )

            stat[
                "penera_insert"
            ] += 1


# =========================================================
# MIGRASI BEJANA
# =========================================================
def migrasi_bejana():
    path = (
        DATA_DIR
        / "data_bejana.xlsx"
    )

    if not path.exists():
        print(
            "SKIP: data_bejana.xlsx tidak ditemukan"
        )
        return

    print(
        "\n=== MIGRASI BEJANA ==="
    )

    df = pd.read_excel(
        path,
        engine="openpyxl"
    )

    df.columns = [
        str(c).strip()
        for c in df.columns
    ]

    for _, row in df.iterrows():

        nomor_seri = clean_text(
            row.get(
                "Nomor Seri"
            )
        )

        payload = {
            "standar_volume": clean_text(
                row.get(
                    "Standar Volume"
                )
            ),

            "merk": clean_text(
                row.get(
                    "Merk"
                )
            ),

            "tipe": clean_text(
                row.get(
                    "Tipe"
                )
            ),

            "nomor_seri": (
                nomor_seri
                if nomor_seri
                else None
            ),

            "kelas": clean_text(
                row.get(
                    "Kelas"
                )
            ),

            "kapasitas": clean_number(
                row.get(
                    "Kapasitas"
                )
            ),

            "daya_baca": clean_number(
                row.get(
                    "Daya Baca"
                )
            ),

            "telusuran": clean_text(
                row.get(
                    "Telusuran"
                )
            ),

            "status": "aktif",
        }

        existing = None

        if nomor_seri:
            response = (
                supabase
                .table("bejana")
                .select("id")
                .eq(
                    "nomor_seri",
                    nomor_seri
                )
                .limit(1)
                .execute()
            )

            if response.data:
                existing = (
                    response.data[0]
                )

        if existing:
            (
                supabase
                .table("bejana")
                .update(
                    payload
                )
                .eq(
                    "id",
                    existing["id"]
                )
                .execute()
            )

            stat[
                "bejana_update"
            ] += 1

        else:
            (
                supabase
                .table("bejana")
                .insert(
                    payload
                )
                .execute()
            )

            stat[
                "bejana_insert"
            ] += 1


# =========================================================
# MIGRASI MEDIA SPBU
# =========================================================
def migrasi_media_spbu():
    path = (
        DATA_DIR
        / "data_media_spbu.xlsx"
    )

    if not path.exists():
        print(
            "SKIP: data_media_spbu.xlsx tidak ditemukan"
        )
        return

    print(
        "\n=== MIGRASI MEDIA SPBU ==="
    )

    df = pd.read_excel(
        path,
        engine="openpyxl"
    )

    df.columns = [
        str(c).strip()
        for c in df.columns
    ]

    for _, row in df.iterrows():

        kategori = clean_text(
            row.get(
                "NAMA SPBU"
            )
        )

        media = clean_text(
            row.get(
                "MEDIA"
            )
        )

        if not kategori:
            continue

        response = (
            supabase
            .table("media_spbu")
            .select("id")
            .ilike(
                "kategori_spbu",
                kategori
            )
            .limit(1)
            .execute()
        )

        payload = {
            "kategori_spbu": (
                kategori
            ),
            "media": (
                media
            ),
            "status": "aktif",
        }

        if response.data:
            (
                supabase
                .table("media_spbu")
                .update(
                    payload
                )
                .eq(
                    "id",
                    response.data[0]["id"]
                )
                .execute()
            )

            stat[
                "media_update"
            ] += 1

        else:
            (
                supabase
                .table("media_spbu")
                .insert(
                    payload
                )
                .execute()
            )

            stat[
                "media_insert"
            ] += 1


# =========================================================
# MIGRASI data_spbu.csv
#
# Format lama:
# Nama SPBU | Alamat
# =========================================================
def migrasi_data_spbu():
    path = (
        DATA_DIR
        / "data_spbu.csv"
    )

    if not path.exists():
        print(
            "SKIP: data_spbu.csv tidak ditemukan"
        )
        return

    print(
        "\n=== MIGRASI DATA SPBU LEGACY ==="
    )

    df = read_csv_auto(
        path
    )

    for _, row in df.iterrows():

        nama = clean_text(
            row.get(
                "Nama SPBU"
            )
        )

        alamat = clean_text(
            row.get(
                "Alamat"
            )
        )

        if not nama:
            continue

        nomor_spbu = (
            extract_nomor_spbu(
                nama
            )
        )

        jenis_lokasi = (
            tentukan_jenis_lokasi(
                nama
            )
            or "SPBU"
        )

        simpan_perusahaan(
            nama=nama,
            alamat=alamat,
            nomor_spbu=nomor_spbu,
            jenis_lokasi=jenis_lokasi,
        )


# =========================================================
# MIGRASI Data SPBU Kab. Tangerang.csv
#
# Dashboard lama mengenali:
# No. SPBU / Nama SPBU
# Alamat
# Kecamatan
# Koordinat
# Media BBM / Produk BBM
# =========================================================
def migrasi_dashboard_spbu():
    path = (
        DATA_DIR
        / "Data SPBU Kab. Tangerang.csv"
    )

    if not path.exists():
        print(
            "SKIP: Data SPBU Kab. Tangerang.csv tidak ditemukan"
        )
        return

    print(
        "\n=== MIGRASI DASHBOARD SPBU ==="
    )

    df = read_csv_auto(
        path
    )

    for _, row in df.iterrows():

        nama_raw = (
            clean_text(
                row.get(
                    "Nama SPBU"
                )
            )
            or clean_text(
                row.get(
                    "No. SPBU"
                )
            )
        )

        if not nama_raw:
            continue

        nomor_spbu = (
            extract_nomor_spbu(
                nama_raw
            )
        )

        # Kalau kolom hanya berisi 34-XXXXX,
        # buat nama yang tetap jelas.
        if (
            nomor_spbu
            and nama_raw.replace(
                ".",
                "-"
            ) == nomor_spbu
        ):
            nama = (
                f"SPBU {nomor_spbu}"
            )
        else:
            nama = nama_raw

        alamat = clean_text(
            row.get(
                "Alamat"
            )
        )

        kecamatan = clean_text(
            row.get(
                "Kecamatan"
            )
        )

        koordinat = clean_text(
            row.get(
                "Koordinat"
            )
        )

        media_bbm = (
            clean_text(
                row.get(
                    "Media BBM"
                )
            )
            or clean_text(
                row.get(
                    "Produk BBM"
                )
            )
        )

        lat, lon = (
            parse_coordinate(
                koordinat
            )
        )

        jenis_lokasi = (
            tentukan_jenis_lokasi(
                nama
            )
            or "SPBU"
        )

        simpan_perusahaan(
            nama=nama,
            alamat=alamat,
            nomor_spbu=nomor_spbu,
            jenis_lokasi=jenis_lokasi,
            kecamatan=kecamatan,
            latitude=lat,
            longitude=lon,
            media_bbm=media_bbm,
        )


# =========================================================
# MASTER PASAR
# =========================================================
def get_or_create_pasar(
    nama_pasar,
    alamat,
    kecamatan,
    latitude,
    longitude,
    total_pedagang,
):
    response = (
        supabase
        .table("pasar")
        .select("*")
        .ilike(
            "nama_pasar",
            nama_pasar
        )
        .limit(1)
        .execute()
    )

    payload = {
        "nama_pasar": (
            nama_pasar
        ),

        "alamat": (
            alamat
        ),

        "kecamatan": (
            kecamatan
        ),

        "latitude": (
            latitude
        ),

        "longitude": (
            longitude
        ),

        "total_pedagang": (
            total_pedagang
        ),

        "status": "aktif",
    }

    if response.data:
        pasar_id = (
            response.data[0]["id"]
        )

        (
            supabase
            .table("pasar")
            .update(
                payload
            )
            .eq(
                "id",
                pasar_id
            )
            .execute()
        )

        stat[
            "pasar_update"
        ] += 1

        return pasar_id

    response_insert = (
        supabase
        .table("pasar")
        .insert(
            payload
        )
        .execute()
    )

    stat[
        "pasar_insert"
    ] += 1

    return (
        response_insert
        .data[0]["id"]
    )


# =========================================================
# MIGRASI DATA DASHBOARD PASAR
# =========================================================
def migrasi_dashboard_pasar():
    path = (
        DATA_DIR
        / "DATA_DASHBOARD_PASAR.xlsx"
    )

    if not path.exists():
        print(
            "SKIP: DATA_DASHBOARD_PASAR.xlsx tidak ditemukan"
        )
        return

    print(
        "\n=== MIGRASI DASHBOARD PASAR ==="
    )

    df = pd.read_excel(
        path,
        engine="openpyxl"
    )

    df.columns = [
        str(c).strip()
        for c in df.columns
    ]

    for _, row in df.iterrows():

        nama_pasar = clean_text(
            row.get(
                "Nama Pasar"
            )
        )

        if not nama_pasar:
            continue

        alamat = clean_text(
            row.get(
                "Alamat"
            )
        )

        kecamatan = clean_text(
            row.get(
                "Kecamatan"
            )
        )

        lat, lon = (
            parse_coordinate(
                row.get(
                    "Koordinat"
                )
            )
        )

        total_pedagang = clean_int(
            row.get(
                "Total Pedagang"
            ),
            0
        )

        tahun = clean_int(
            row.get(
                "Tahun Tera Ulang"
            ),
            0
        )

        if tahun <= 0:
            continue

        total_uttp = clean_int(
            row.get(
                "Total UTTP"
            ),
            0
        )

        pasar_id = (
            get_or_create_pasar(
                nama_pasar=nama_pasar,
                alamat=alamat,
                kecamatan=kecamatan,
                latitude=lat,
                longitude=lon,
                total_pedagang=total_pedagang,
            )
        )

        legacy_payload = {
            "pasar_id": (
                pasar_id
            ),

            "tahun": (
                tahun
            ),

            "total_uttp": (
                total_uttp
            ),

            "timb_pegas": clean_int(
                row.get(
                    "Timb. Pegas"
                ),
                0
            ),

            "timb_meja": clean_int(
                row.get(
                    "Timb. Meja"
                ),
                0
            ),

            "timb_elektronik": clean_int(
                row.get(
                    "Timb. Elektronik"
                ),
                0
            ),

            "timb_sentisimal": clean_int(
                row.get(
                    "Timb. Sentisimal"
                ),
                0
            ),

            "timb_bobot_ingsut": clean_int(
                row.get(
                    "Timb. Bobot Ingsut"
                ),
                0
            ),

            "neraca": clean_int(
                row.get(
                    "Neraca"
                ),
                0
            ),

            "dacin": clean_int(
                row.get(
                    "Dacin"
                ),
                0
            ),

            "sumber": (
                "DATA_DASHBOARD_PASAR.xlsx"
            ),
        }

        response_existing = (
            supabase
            .table(
                "pasar_tera_ulang_legacy"
            )
            .select("id")
            .eq(
                "pasar_id",
                pasar_id
            )
            .eq(
                "tahun",
                tahun
            )
            .limit(1)
            .execute()
        )

        if response_existing.data:
            (
                supabase
                .table(
                    "pasar_tera_ulang_legacy"
                )
                .update(
                    legacy_payload
                )
                .eq(
                    "id",
                    response_existing
                    .data[0]["id"]
                )
                .execute()
            )

            stat[
                "pasar_legacy_update"
            ] += 1

        else:
            (
                supabase
                .table(
                    "pasar_tera_ulang_legacy"
                )
                .insert(
                    legacy_payload
                )
                .execute()
            )

            stat[
                "pasar_legacy_insert"
            ] += 1


# =========================================================
# MAIN
# =========================================================
def main():
    print(
        "========================================"
    )
    print(
        " MIGRASI DATA SMART METRO → SUPABASE"
    )
    print(
        "========================================"
    )

    # Urutannya penting:
    # perusahaan umum dulu,
    # baru SPBU memperkaya data.
    migrasi_perusahaan()

    migrasi_penera()

    migrasi_bejana()

    migrasi_media_spbu()

    migrasi_data_spbu()

    migrasi_dashboard_spbu()

    migrasi_dashboard_pasar()

    print(
        "\n========================================"
    )
    print(
        " MIGRASI SELESAI"
    )
    print(
        "========================================"
    )

    for key, value in (
        stat.items()
    ):
        print(
            f"{key:30} : {value}"
        )


if __name__ == "__main__":
    main()