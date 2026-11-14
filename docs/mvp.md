# CYBER-KATAM — prototipe interaktif v0.2

Tiga pengalaman frontend berbahasa Indonesia:

1. **Analis / Pembuat Kebijakan** — dasbor gelap, peta skematik, H3-7–9,
   lima sakelar lapisan, diagnostik, grafik Pareto ilustratif, dan kontrol iklim.
2. **Petani / PPL** — tampilan terang, peringatan sederhana, perbandingan tiga
   rotasi, penjelasan istilah, dan ekspor ringkasan kelompok tani.
3. **Sertifikat Penjelasan Keputusan** — empat blok XAI, metadata sumber,
   empat gerbang berurutan, simulasi peran dan tanda tangan PPL, serta abstensi.

Mode petani menjadi tampilan awal pada viewport mobile. Pilihan mode, periode,
rotasi, simulasi, dan audit terhubung melalui state React dalam memori saja.
Tidak ada akun, backend, data pengguna tersimpan, API NASA, atau tanda tangan
digital sah.

## Integritas data

- `public/demo-grid.geojson` tetap mempertahankan geometri dan indeks fixture
  sintetis yang diterima, tanpa atribut satelit acak.
- `web-app/scripts/build_demo_geometry.py` menurunkan parent valid H3-7 dan
  H3-8 dari 1.000 indeks H3-9 tersebut menggunakan pustaka `h3`. Hasilnya
  `public/demo-grid-levels.json`: 30 sel resolusi 7, 159 sel resolusi 8, dan
  1.000 sel resolusi 9. Tidak ada pengamatan lingkungan pada artefak ini.
- Foto lokal Iswanto Arif / Unsplash adalah ilustrasi, bukan citra satelit NASA.
  Garis sungai, jalan, nama lokasi, dan batas petak pada tampilan bersifat
  skematik. Foto tidak diregistrasi secara geografis ke H3.
- Semua warna risiko, nilai PVRS/BF-EHSI, neraca air, skor Pareto, manfaat
  fiskal Rp16,58 miliar, dan penurunan AUTP 18,4% adalah **Data Simulasi**.
- `simulate()` adalah respons UI deterministik sederhana, bukan persamaan
  biofisika atau model iklim. Tidak menyalin rumus engine Arya, tidak memakai
  kontrak bersama yang belum diratifikasi, dan tidak memanggil pipeline NASA.
- Tiga rotasi mengikuti brief UI terbaru: padi–bera, padi–kedelai Anjasmoro,
  dan padi–kacang hijau. Ini bukan parameter baru pada kontrak atau engine.
- Skenario B adalah unggulan dalam demonstrasi saja. Kelulusan keempat gerbang
  tidak mengubah kelengkapan bukti nyata (0%) atau status
  `ABSTAIN_FIELD_AUDIT_REQUIRED`.
- Perubahan periode, rotasi, atau simulasi membatalkan persetujuan demo.
  Kegagalan/perubahan gerbang membatalkan gerbang sesudahnya.
- Resolusi asli ditampilkan: SMAP ~9 km, GPM 0,1°, HLS 30 m, LST 70 m, SRTM
  ~30 m. ECOSTRESS LSTE tidak disamakan dengan ESI; sumber ESI terpisah belum ada.
  Nilai skenario pada panel sel bukan pengukuran spesifik atau independen per sel.
- Tutupan lahan, bukti nyata, topografi aktual, dan batas galat terkalibrasi
  tetap **Belum Tersedia**.

## Interaksi yang tersedia

- Beralih mode dan membuka / kembali dari audit.
- Memilih periode contoh serta rotasi, termasuk melalui titik grafik Pareto.
- Sakelar lapisan mengubah kondisi visual dan legenda.
- Memilih resolusi H3, memilih sel, tooltip hover/fokus, zoom, geser, sembunyikan
  kisi, dan atur ulang peta.
- Slider hujan −30% hingga +30% dan suhu +0 hingga +3°C. Angka diagnostik
  berubah hanya setelah **Jalankan Simulasi**.
- Empat gerbang dengan status belum / lulus / gagal dalam simulasi. Gerbang
  akhir memerlukan peran demo PPL, nama, dan pengakuan bahwa tanda tangan tidak
  sah. Tidak ada verifikasi identitas atau otorisasi operasional.
- Ekspor canvas PNG nyata: pratinjau, ukuran byte, unduh, simulasi berbagi.
  PNG diperiksa di bawah **150.000 byte** sebelum ditawarkan. Tidak ada pesan
  WhatsApp yang dikirim; pengguna mengunduh dan membagikannya sendiri.
- Bantuan, metadata sumber, notifikasi, profil demo, dan tooltip istilah.

## Verifikasi

Instal dependensi hanya melalui `.figma/make/install`. Server Vite disupervisi
oleh Make pada `$PORT`; jangan menjalankan server kedua.

- `pnpm test` — determinisme simulasi, guardrail, gerbang, dan metadata.
- `python -m pytest tests/ -v` — geometri asli dan parent multiresolusi.
- `pnpm test:ui` — interaksi tiga tampilan, responsivitas, dan unduhan PNG.
- `figma make verify-deploy` — pemeriksaan build produksi statis `dist/`.

Google Fonts membutuhkan jaringan, tetapi peta, foto, fixture, simulasi, dan
ekspor gambar tidak membutuhkan API eksternal atau kredensial.

## Prasyarat penggunaan operasional

Tetap diperlukan: ekspor NASA terinspeksi dengan QA/timestamp/manifest; mask
sawah nyata; klimatologi; ESI; parameter air, tanah, agronomi, dan ekonomi
tervalidasi; kontrak integrasi ratifikasi; engine terkalibrasi; serta proses
otorisasi manusia dan jejak audit yang benar-benar dapat diverifikasi.
