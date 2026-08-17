# 📋 Aplikasi Automasi Sertifikat Tera Timbangan

Aplikasi ini dirancang untuk mengotomatisasi proses pembuatan **Cerapan** dan **Sertifikat Tera** bagi Penera Timbangan di Dinas Perindustrian dan Perdagangan.

## 🎯 Fitur Utama

✅ **Input Data Pengujian** - Form interaktif untuk memasukkan data hasil pengujian timbangan
✅ **Generate Cerapan PDF** - Otomatis membuat dokumen Cerapan Peneraan
✅ **Generate Sertifikat PDF** - Otomatis membuat Sertifikat Tera
✅ **Sinkronisasi Data** - Data pengujian otomatis ditarik ke Sertifikat tanpa copy-paste
✅ **Download Dokumen** - Dokumen siap cetak dalam format PDF
✅ **Riwayat Pengujian** - Lihat data pengujian dan statistik

## 📋 Kebutuhan Sistem

- Python 3.8+
- pip (Python package manager)
- Windows, macOS, atau Linux

## 🚀 Instalasi

### 1. Download/Clone Project
```bash
# Jika menggunakan git
git clone [repository-url]
cd aplikasi-sertifikat-tera
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Jalankan Aplikasi
```bash
streamlit run app.py
```

Aplikasi akan otomatis membuka di browser (biasanya `http://localhost:8501`)

## 💻 Cara Menggunakan

### Step 1: Input Data Pengujian
1. Klik tab **"📝 Input Data Pengujian"**
2. Isi informasi pemilik/perusahaan:
   - Nama Pemilik/Perusahaan
   - Alamat lengkap
   
3. Isi spesifikasi alat:
   - Merek/Buatan (Contoh: FINE/KOREA)
   - Model/Tipe (Contoh: FS-8000)
   - No. Seri (Contoh: 2123176)
   
4. Isi kapasitas & skala:
   - Kapasitas Maksimum (kg)
   - Kapasitas Minimum (kg)
   - Daya Baca (kg)
   - Interval Skala Verifikasi (kg)
   
5. Isi data pengujian:
   - Tanggal pengujian
   - Kelas timbangan (I, II, III, IIII)
   - Suhu ruangan
   - Kelembaban
   - Metode pengujian
   
6. Isi data penera:
   - Nama penera
   - NIP penera
   
7. Masukkan hasil pengujian kebenaran:
   - Tentukan jumlah data pengujian
   - Isi setiap baris dengan:
     - Muatan (kg)
     - Penunjukan (kg)
     - ΔL
     - P=I+0.5e-ΔL
     - Kesalahan (kg)
     - Hasil (SAH/TIDAK SAH)

8. Klik **"💾 Simpan Data"** untuk menyimpan

### Step 2: Generate Dokumen
1. Klik tab **"📄 Generate Dokumen"**
2. Verifikasi preview data yang ditampilkan
3. Masukkan Nomor Sertifikat (Format: 500.2.3.15 / 0308 / BID-K / IV / 2026)
4. Masukkan Nomor Order (Opsional)
5. Pilih salah satu:
   - **"📝 Generate Cerapan PDF"** - Hanya membuat Cerapan
   - **"🎫 Generate Sertifikat PDF"** - Hanya membuat Sertifikat
   - **"📦 Generate Kedua Dokumen"** - Membuat keduanya sekaligus
6. Klik tombol yang dipilih
7. Dokumen akan dibuat dan siap didownload
8. Klik tombol **"⬇️ Download"** untuk mengunduh file PDF

### Step 3: Lihat Riwayat Pengujian
1. Klik tab **"📊 Riwayat Pengujian"**
2. Lihat detail data pengujian terbaru
3. Lihat tabel hasil pengujian
4. Lihat statistik (Hasil SAH, Rata-rata Kesalahan, Kesalahan Maksimum)

## 📁 Struktur File

```
aplikasi-sertifikat-tera/
├── app.py                    # Aplikasi utama Streamlit
├── cerapan_generator.py      # Module untuk generate Cerapan PDF
├── sertifikat_generator.py   # Module untuk generate Sertifikat PDF
├── requirements.txt          # Dependencies Python
├── README.md                 # File ini
└── output/                   # Folder untuk menyimpan PDF yang dihasilkan
    ├── Cerapan_*.pdf
    └── Sertifikat_*.pdf
```

## 🔄 Alur Kerja

```
┌─────────────────────────────────────────┐
│  PENERA: INPUT DATA PENGUJIAN           │
│  (Form: Pemilik, Alat, Hasil Pengujian) │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│  APLIKASI: SIMPAN DATA                  │
│  (Stored di Session State)              │
└──────────────────┬──────────────────────┘
                   │
          ┌────────┴─────────┐
          │                  │
          ▼                  ▼
    ┌──────────────┐  ┌──────────────────┐
    │  CERAPAN PDF │  │ SERTIFIKAT PDF   │
    │  (Generate)  │  │ (Generate)       │
    └──────────────┘  └──────────────────┘
          │                  │
          └────────┬─────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │ DOWNLOAD PDF FILES   │
        │ (Ready to Print)     │
        └──────────────────────┘
```

## ⚙️ Konfigurasi Lanjutan

### Mengubah Template Sertifikat
Edit file `sertifikat_generator.py`:
- Ubah header/kop surat sesuai kebutuhan
- Sesuaikan posisi teks dengan merubah nilai `y` (sumbu vertikal)
- Sesuaikan ukuran font dengan merubah parameter `c.setFont()`

### Menambahkan Logo/Watermark
1. Buka file `sertifikat_generator.py` atau `cerapan_generator.py`
2. Tambahkan kode untuk import image:
```python
from reportlab.platypus import Image
# Tambahkan gambar ke PDF
img = Image("logo.png", width=2*cm, height=2*cm)
```

### Mengubah Folder Output
Di file `app.py`, ubah baris:
```python
output_path = Path("./output")
```
Ganti dengan path yang diinginkan.

## 🐛 Troubleshooting

### Error: "ModuleNotFoundError: No module named 'streamlit'"
**Solusi:**
```bash
pip install streamlit==1.28.0
```

### Error: "ModuleNotFoundError: No module named 'reportlab'"
**Solusi:**
```bash
pip install reportlab==4.0.4
```

### PDF tidak menampilkan dengan benar
**Solusi:**
- Pastikan Anda menggunakan PDF reader yang support (Adobe Reader, Chrome, etc)
- Coba regenerate dokumen
- Pastikan semua field sudah terisi dengan data yang valid

### Aplikasi berjalan lambat
**Solusi:**
- Tutup tab browser lain yang tidak perlu
- Restart aplikasi: Tekan `Ctrl+C` di terminal dan jalankan `streamlit run app.py` kembali

## 📞 Support

Jika mengalami masalah:
1. Pastikan semua dependencies sudah terinstall dengan benar
2. Check bahwa semua file ada di folder yang sama
3. Restart aplikasi
4. Hubungi developer jika masalah persisten

## 📝 Lisensi

Aplikasi ini dikembangkan untuk Dinas Perindustrian dan Perdagangan Kabupaten Tangerang.

---

**Versi:** 1.0  
**Dibuat:** 2026  
**Status:** Aktif
