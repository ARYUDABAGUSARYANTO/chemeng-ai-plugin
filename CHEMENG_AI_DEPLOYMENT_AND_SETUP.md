# Panduan Deployment & Integrasi Publik — ChemEng AI v0.1

Dokumen ini memandu langkah akhir (**Tahap 6 hingga Tahap 8**) untuk meng-online-kan server **ChemEng AI**, memasangnya ke ChatGPT (Custom GPT Actions / MCP), dan menyiapkan publikasi resmi.

## 1. Struktur File Paket Rilis (`chemeng_ai_release_v0.1.zip`)

| Nama File | Fungsi Utama |
| :--- | :--- |
| `chemeng_ai_mcp_server.py` | kode utama server FastAPI & 11 tools perhitungan/simulasi/riset teknik kimia |
| `test_chemeng_ai.py` | 11 skenario pengujian otomatis (8 positif + 3 negatif) yang wajib lulus sebelum rilis |
| `chemeng_ai_openapi.json` | Skema OpenAPI 3.1.0 untuk diimpor langsung ke ChatGPT Actions |
| `requirements.txt` | Daftar pustaka Python produksi (`fastapi`, `uvicorn`, `pydantic`, `httpx`) |
| `Dockerfile` | Konfigurasi container untuk deployment di Cloud Run, Railway, Fly.io, atau VPS Docker |
| `render.yaml` | Blueprint otomatis untuk deployment gratis 1-klik di Render.com |

## 2. Cara Meng-online-kan Server (Mendapatkan Endpoint HTTPS Publik)

### Opsi A — Deploy Gratis Tanpa Kartu Kredit via Render.com (Paling Mudah)
1. Buat repositori baru di GitHub (misal `chemeng-ai-plugin`) dan unggah seluruh file dari paket ini.
2. Masuk ke dashboard **Render.com**, pilih **New +** -> **Blueprint**, lalu hubungkan repositori GitHub tersebut.
3. Render akan otomatis membaca `render.yaml`, menginstal pustaka di `requirements.txt`, menjalankan `test_chemeng_ai.py`, dan menyalakan server.
4. Setelah statusnya **Live**, salin URL HTTPS publikmu (contoh: `https://chemeng-ai-mcp-server.onrender.com`).

### Opsi B — Deploy via Docker (VPS / Google Cloud Run / Railway)
Jalankan perintah berikut di server atau terminal lokalmu:
```bash
docker build -t chemeng-ai:v0.1 .
docker run -d -p 8000:8000 --name chemeng-ai chemeng-ai:v0.1
```
Verifikasi bahwa server berjalan dengan membuka `http://localhost:8000/docs` (Swagger UI interaktif) atau `http://localhost:8000/system-instructions`.

## 3. Cara Memasang ke ChatGPT (Tahap 6 — ChatGPT Interface)

1. Buka **ChatGPT** -> **Explore GPTs** -> klik **+ Create** di pojok kanan atas.
2. Pada tab **Configure**, isi identitas produk:
   * **Name**: `ChemEng AI`
   * **Description**: `Tutor, Analis Simulasi (Aspen Plus & HYSYS), dan Mesin Perhitungan Teknik Kimia Berbasis Bukti.`
   * **Instructions**: Salin seluruh isi blok `CORE_SYSTEM_INSTRUCTIONS` di bawah ini:

```text
CHEMENG AI — CORE INSTRUCTIONS v0.1
1. Bertindak sebagai tutor dan konsultan teknik kimia berbasis bukti (evidence-based).
2. Menggunakan bahasa Indonesia sebagai bahasa utama, dengan istilah engineering dalam bahasa Inggris.
3. Menyesuaikan penjelasan dengan tingkat kemampuan pengguna (Mahasiswa, Dosen/Peneliti, Process Engineer).
4. Mengajarkan konsep dasar dan fenomena transport/termodinamika sebelum memberikan prosedur kompleks.
5. Menampilkan persamaan, satuan, basis perhitungan, dan asumsi secara eksplisit pada setiap perhitungan.
6. Tidak mengarang data eksperimen, properti fisik, parameter termodinamika, atau referensi jurnal (DOI wajib terverifikasi).
7. Tidak menganggap simulasi konvergen (Aspen Plus / HYSYS) sebagai simulasi tervalidasi tanpa pemeriksaan kewajaran fisik.
8. Memeriksa neraca massa, neraca energi, dan kewajaran fisik hasil (misal: T_cross, pendekatan suhu minimum, efisiensi < 100%).
9. Memberikan referensi teknik standar (Perry's, Coulson & Richardson, Smith Van Ness, Kern, Seader).
10. Tidak memberikan sertifikasi keselamatan proses (HAZOP/SIL/Relief Valve final sizing) hanya berdasarkan hasil simulasi.
11. Tidak mengklaim mengakses atau menjalankan software lokal (Aspen Plus/HYSYS) tanpa integrasi adapter nyata.
12. Untuk panduan Aspen Plus & HYSYS: berikan maksimal satu langkah UI utama per giliran dengan validasi teknis.
Selalu panggil Action/Tool perhitungan yang tersedia untuk setiap soal numerik; jangan pernah menghitung di luar kepala.
```

3. Gulir ke bawah ke bagian **Actions** -> klik **Create new action**.
4. Klik **Import from URL** atau tempelkan langsung isi file `chemeng_ai_openapi.json` ke kolom **Schema**.
5. Ganti baris `"url": "https://your-chemeng-ai-domain.com"` di bagian atas Schema dengan URL HTTPS publik dari servermu (misal `https://chemeng-ai-mcp-server.onrender.com`).
6. Klik **Test** pada salah satu tool (misal `calculate_mass_balance`) untuk memastikan ChatGPT berhasil berkomunikasi dengan servermu.

## 4. Kebijakan Privasi & Persyaratan Rilis Publik (Tahap 8)

Untuk mempublikasikan plugin/GPT ke **Public Directory**, tempelkan teks kebijakan privasi berikut pada halaman web publik atau endpoint `/privacy` milikmu:

* **Data yang Diproses**: ChemEng AI hanya memproses parameter teknis (laju alir, suhu, tekanan, komposisi kimia, pesan error simulasi, dan kata kunci literatur) yang dikirimkan secara eksplisit pada sesi perhitungan aktif.
* **Penyimpanan Data**: Server perhitungan beroperasi secara *stateless* (tidak menyimpan data proyek rahasia pabrik atau identitas pribadi pengguna ke dalam database permanen tanpa persetujuan eksplisit).
* **Batas Tanggung Jawab Keinsinyuran (Engineering Disclaimer)**: Seluruh hasil perhitungan dan rekomendasi simulasi merupakan *preliminary engineering analysis* untuk tujuan pendidikan dan pendampingan teknis, bukan pengganti dokumen *Detailed Engineering Design* (DED), *Process Hazard Analysis* (PHA/HAZOP) tersertifikasi, atau lisensi perangkat lunak komersial.
