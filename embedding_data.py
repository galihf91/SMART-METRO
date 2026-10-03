import os
from supabase import create_client
from sentence_transformers import SentenceTransformer
import streamlit as st

# 1. Koneksi ke Supabase
# Ganti dengan URL dan KEY dari proyek Supabase Anda
SUPABASE_URL = "https://xxxxx.supabase.co"
SUPABASE_KEY = "eyJhbGciOi..." # Gunakan anon key atau service_role key
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 2. Muat Model Embedding
# Model ini sangat baik untuk bahasa Indonesia
model = SentenceTransformer('aisingapore/SEA-LION-E5-Embedding-600M')

# 3. Ambil Data dari Tabel Sumber di Supabase
# Ganti 'nama_tabel_anda' dengan nama tabel yang berisi data SMART METRO
# Contoh: 'uttp_data', 'pasar_data', 'spbu_data'
response = supabase.table('nama_tabel_anda').select('*').execute()
data_mentah = response.data

# 4. Proses dan Simpan ke Tabel 'documents'
for item in data_mentah:
    # Ubah setiap baris data menjadi teks
    # Contoh: "Jenis UTTP: Timbangan, Lokasi: Pasar Cikupa, Jumlah: 45"
    teks_konten = f"Jenis UTTP: {item.get('jenis')}, Lokasi: {item.get('lokasi')}, Jumlah: {item.get('jumlah')}"
    
    # Buat vektor dari teks
    vektor = model.encode(teks_konten).tolist()
    
    # Simpan ke tabel 'documents'
    data_untuk_disimpan = {
        'content': teks_konten,
        'metadata': {'sumber': 'nama_tabel_anda', 'id_asli': item.get('id')},
        'embedding': vektor
    }
    supabase.table('documents').insert(data_untuk_disimpan).execute()
    print(f"Berhasil memproses: {teks_konten}")

print("Selesai! Semua data telah di-embedding dan disimpan ke Supabase.")