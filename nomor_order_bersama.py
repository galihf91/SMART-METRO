"""
Helper NOMOR ORDER bersama untuk semua modul SMART METRO.

ATURAN:
  Nomor order boleh DIPAKAI ULANG kalau sudah ada pengujian dengan
  nama perusahaan dan tanggal pengujian yang sama.

Karena semua modul (Timbangan, Timbangan Jembatan, PUBBM, UTTP Umum)
menyimpan ke tabel `pengujian` yang sama, aturan ini otomatis berlaku
LINTAS MODUL: satu perusahaan, satu tanggal, satu nomor order.

Semua fungsi di sini menerima `supabase` (client yang sudah dibuat
pemanggil), jadi file ini tidak mengurus koneksi.
"""

from datetime import datetime

import streamlit as st


def _ke_iso_tanggal(nilai_tanggal):
    """Ubah date / datetime / string menjadi format YYYY-MM-DD."""
    if nilai_tanggal is None:
        return None

    if hasattr(nilai_tanggal, "strftime"):
        return nilai_tanggal.strftime("%Y-%m-%d")

    teks = str(nilai_tanggal).strip()
    for pola in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(teks, pola).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return teks


def nomor_order_siap_pakai(nomor):
    """True kalau nomor order sudah terisi dan bukan template 0000."""
    if not nomor:
        return False

    teks = str(nomor).strip()
    if not teks:
        return False

    depan = teks.split("/")[0].strip()
    if not depan.isdigit():
        return False

    return int(depan) > 0


def ambil_nama_perusahaan_form(daftar_kunci):
    """
    Ambil nama perusahaan dari session_state berdasarkan daftar kunci widget.
    Modul yang berbeda cukup mengirim daftar kunci yang berbeda.
    """
    for kunci in daftar_kunci:
        nilai = st.session_state.get(kunci)
        if nilai and str(nilai).strip():
            return str(nilai).strip()

    return ""


def cari_nomor_order_sebelumnya(nama_perusahaan, tanggal_pengujian, supabase):
    """
    Cari nomor order yang sudah ada untuk perusahaan + tanggal pengujian sama.
    Berlaku lintas modul karena membaca tabel `pengujian`.

    Ketemu  : kembalikan nomor order (dipakai ulang)
    Tidak ada: kembalikan None

    Cara mencocokkan baris pengujian ke perusahaan:
      1. kolom pengujian.perusahaan_id (cara utama)
      2. cadangan: lewat uttp.perusahaan_id bila kolom di atas kosong
    """
    try:
        nama = (nama_perusahaan or "").strip()
        tanggal_iso = _ke_iso_tanggal(tanggal_pengujian)

        if not nama or not tanggal_iso:
            return None

        # 1. id perusahaan
        res_perusahaan = (
            supabase.table("perusahaan")
            .select("id")
            .eq("nama_perusahaan", nama)
            .limit(1)
            .execute()
        )
        if not res_perusahaan.data:
            return None

        perusahaan_id = res_perusahaan.data[0]["id"]

        # 2. daftar uttp milik perusahaan ini (untuk jalur cadangan)
        res_uttp = (
            supabase.table("uttp")
            .select("id")
            .eq("perusahaan_id", perusahaan_id)
            .limit(500)
            .execute()
        )
        uttp_ids = {
            baris.get("id")
            for baris in (res_uttp.data or [])
            if baris.get("id") is not None
        }

        # 3. semua pengujian pada tanggal itu
        res_pengujian = (
            supabase.table("pengujian")
            .select("id, nomor_order, perusahaan_id, uttp_id")
            .eq("tanggal_pengujian", tanggal_iso)
            .order("id", desc=False)
            .limit(500)
            .execute()
        )

        for baris in (res_pengujian.data or []):
            nomor = baris.get("nomor_order")
            if not nomor_order_siap_pakai(nomor):
                continue

            id_perusahaan_baris = baris.get("perusahaan_id")
            id_uttp_baris = baris.get("uttp_id")

            milik_perusahaan = (
                id_perusahaan_baris == perusahaan_id
                or (not id_perusahaan_baris and id_uttp_baris in uttp_ids)
            )

            if milik_perusahaan:
                return str(nomor).strip()

    except Exception as e:
        st.warning(f"Gagal mengecek nomor order sebelumnya: {e}")

    return None


def pilih_nomor_order(nama_perusahaan, tanggal_pengujian, supabase, ambil_nomor_baru):
    """
    Tentukan nomor order yang dipakai.

    Mengembalikan (nomor_order, dipakai_ulang):
      (nomor lama, True)  kalau sudah ada untuk perusahaan + tanggal sama
      (nomor baru, False) kalau belum ada, lewat fungsi ambil_nomor_baru
    """
    nomor_lama = cari_nomor_order_sebelumnya(
        nama_perusahaan, tanggal_pengujian, supabase
    )
    if nomor_lama:
        return nomor_lama, True

    return ambil_nomor_baru(tanggal_pengujian), False
