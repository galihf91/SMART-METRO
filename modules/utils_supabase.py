"""Pembacaan Supabase berhalaman untuk modul-modul SMART METRO.

Tempatkan file ini di: modules/utils_supabase.py

Dukungan:
- ambil seluruh baris tanpa terpotong batas respons PostgREST;
- filter .in_() dalam batch kecil;
- filter kesetaraan .eq() yang diterapkan di server;
- pengurutan ID stabil agar halaman tidak bergeser karena urutan acak.

Perhatian: fungsi ini ditujukan untuk daftar/riwayat yang memang perlu
semua baris. Untuk pencarian satu ID, lebih efisien menggunakan .eq().limit(1).
"""


def ambil_semua_baris(
    supabase,
    tabel,
    kolom="*",
    *,
    filter_kolom=None,
    filter_nilai=None,
    filter_eq=None,
    ukuran_halaman=500,
    ukuran_batch=150,
    urut_berdasarkan="id",
):
    """Ambil semua baris terpilih dari Supabase, tanpa limit 1.000 baris.

    filter_kolom/filter_nilai membentuk satu atau beberapa query .in_().
    Jika list filter kosong, hasilnya [] dan bukan seluruh tabel.
    filter_eq adalah dict {nama_kolom: nilai}, ditambahkan ke setiap query.
    """
    if not 1 <= ukuran_halaman <= 1000:
        raise ValueError("ukuran_halaman harus antara 1 dan 1000")
    if ukuran_batch < 1:
        raise ValueError("ukuran_batch harus minimal 1")
    if (filter_kolom is None) != (filter_nilai is None):
        raise ValueError("filter_kolom dan filter_nilai harus dipakai bersama")

    if filter_kolom is not None:
        nilai_unik = list(dict.fromkeys(
            nilai for nilai in filter_nilai if nilai is not None
        ))
        if not nilai_unik:
            return []
        daftar_batch = [
            nilai_unik[pos:pos + ukuran_batch]
            for pos in range(0, len(nilai_unik), ukuran_batch)
        ]
    else:
        daftar_batch = [None]

    hasil = []
    for batch in daftar_batch:
        offset = 0
        while True:
            query = supabase.table(tabel).select(kolom)
            if batch is not None:
                query = query.in_(filter_kolom, batch)
            for nama_kolom, nilai in (filter_eq or {}).items():
                query = query.eq(nama_kolom, nilai)
            respons = (
                query.order(urut_berdasarkan)
                .range(offset, offset + ukuran_halaman - 1)
                .execute()
            )
            baris = respons.data or []
            hasil.extend(baris)
            if len(baris) < ukuran_halaman:
                break
            offset += ukuran_halaman
    return hasil
