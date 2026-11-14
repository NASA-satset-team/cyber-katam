// UI-only fixtures. These values are not NASA observations or engine outputs.
export const strategies = [
  {
    id: 'A', name: 'Padi – Bera', short: 'Padi – Bera', label: 'Pola Saat Ini',
    crops: ['Padi', 'Bera'], water: 'Kebutuhan air tinggi', nitrogen: 'Pupuk kimia tetap diperlukan',
    pests: 'Siklus hama padi dapat berlanjut', waterScore: 35, soilScore: 30, pestScore: 28,
    note: 'Pola pembanding dengan jeda lahan bera setelah panen padi.',
    why: 'Menjadi pembanding terhadap praktik saat ini. Pola aktual, durasi bera, dan pengelolaan residu tetap perlu dikonfirmasi.',
    benefit: 'Mempertahankan keterampilan dan peralatan yang sudah dikenal petani.',
    risk: 'Lahan terbuka dapat terpapar hujan ekstrem dan kehilangan hara.',
  },
  {
    id: 'B', name: 'Padi – Kedelai Anjasmoro', short: 'Padi – Kedelai', label: 'Rekomendasi Utama',
    crops: ['Padi', 'Kedelai Anjasmoro'], water: 'Berpotensi lebih hemat air',
    nitrogen: 'Potensi tambahan nitrogen alami', pests: 'Tanaman non-inang untuk jeda hama',
    waterScore: 82, soilScore: 88, pestScore: 80,
    note: 'Alternatif unggulan dalam contoh simulasi, bukan anjuran tanam resmi.',
    why: 'Pada contoh ini, kombinasi padi dan legum memberikan keseimbangan ilustratif antara kebutuhan air, kesehatan tanah, dan jeda tanaman inang.',
    benefit: 'Legum berpotensi menambah nitrogen melalui fiksasi biologis. Diversifikasi dapat membantu memutus siklus hama bila dikoordinasikan satu hamparan.',
    risk: 'Kedelai peka terhadap genangan. Drainase, benih Anjasmoro, inokulan, dan pembeli hasil perlu dipastikan.',
  },
  {
    id: 'C', name: 'Padi – Kacang Hijau', short: 'Padi – Kacang Hijau', label: 'Pilihan Alternatif',
    crops: ['Padi', 'Kacang Hijau'], water: 'Potensi kebutuhan air lebih rendah',
    nitrogen: 'Legum mendukung pengelolaan tanah', pests: 'Membantu memberi jeda tanaman inang',
    waterScore: 90, soilScore: 67, pestScore: 73,
    note: 'Pilihan diversifikasi yang tetap memerlukan kajian agronomi setempat.',
    why: 'Kacang hijau ditampilkan sebagai alternatif legum untuk diskusi musim kering, bukan hasil optimasi terverifikasi.',
    benefit: 'Berpotensi mendiversifikasi pendapatan dan menambah penutup tanah selama periode transisi.',
    risk: 'Periksa kecukupan air awal, waktu panen, penyakit, dan akses pasar lokal.',
  },
];

export const layers = [
  { id: 'smap', name: 'SMAP L4', title: 'Kelembapan tanah', resolution: '~9 km', source: 'NASA · SPL4SMGP v8', value: '0,19 m³/m³', period: '1–10 Nov 2026', description: 'Kelembapan zona perakaran; satu piksel meliputi banyak sel H3.' },
  { id: 'eco', name: 'ECOSTRESS', title: 'Stres evaporatif & suhu', resolution: '70 m', source: 'NASA · LSTE v2', value: '32,1 °C', period: 'Contoh akuisisi 8 Nov 2026', description: 'LST tersedia pada produk LSTE. Sumber ESI terpisah belum dipilih.' },
  { id: 'hls', name: 'HLS v2.0', title: 'Vegetasi & spektral', resolution: '30 m', source: 'NASA · HLS L30/S30 v2', value: 'NDVI 0,64', period: '1–10 Nov 2026', description: 'Reflektansi permukaan; memerlukan penyaringan awan dan Fmask.' },
  { id: 'gpm', name: 'GPM IMERG', title: 'Curah hujan', resolution: '0,1°', source: 'NASA · IMERG v7', value: '54 mm / 7 hari', period: '4–10 Nov 2026', description: 'Resolusi asli 0,1°; laju mm/jam harus diagregasikan secara eksplisit.' },
  { id: 'srtm', name: 'SRTM', title: 'Elevasi & topografi', resolution: '~30 m', source: 'NASA / USGS · SRTM', value: 'Belum Tersedia', period: 'Belum Tersedia', description: 'Topografi tidak menunjukkan kondisi drainase aktual di petak.' },
];

export const gateDefinitions = [
  { title: 'Validitas Sensor', owner: 'Analis data', description: 'Periksa usia observasi, awan, sudut sensor, QA, dan skala spasial.', missing: 'Ekspor NASA terinspeksi, waktu akuisisi, dan metadata QA belum tersedia.' },
  { title: 'Drainase Lapangan', owner: 'PPL & petani', description: 'Pastikan tidak ada genangan, saluran tersumbat, atau konflik kondisi lapangan.', missing: 'Inspeksi drainase dan profil hidraulik tanah belum tersedia.' },
  { title: 'Ketersediaan Benih/Inokulan', owner: 'Kelompok tani', description: 'Konfirmasi benih, inokulan, tenaga kerja, dan kesiapan operasional.', missing: 'Ketersediaan aktual belum dikonfirmasi oleh kelompok tani.' },
  { title: 'Otorisasi Tanda Tangan Digital PPL', owner: 'Penyuluh lapangan', description: 'Otorisasi hanya setelah seluruh bukti dan kelayakan ditinjau bersama.', missing: 'Tidak ada identitas atau tanda tangan digital yang terverifikasi.' },
];

export const missingEvidence = [
  'Observasi NASA dan metadata QA yang telah diperiksa',
  'Klimatologi riil dan batas galat yang terkalibrasi',
  'Drainase, pH, dan kondisi petak aktual',
  'Konfirmasi benih, inokulan, biaya, dan pasar',
];

export function simulate(rain = 0, temperature = 0) {
  // Deliberately simple UI responses, NOT PVRS/BF-EHSI or climate equations.
  const moisture = Math.round(Math.max(10, Math.min(65, 28 + rain * 0.45 - temperature * 3)));
  return {
    rain, temperature, moisture,
    pvrs: Math.max(.2, Math.min(.98, .78 - rain * .004 + temperature * .035)),
    erosion: Math.max(.2, Math.min(.98, .64 + rain * .005 + temperature * .015)),
    water: Math.round(-42 + rain * 1.2 - temperature * 8),
    savings: 16.58, insurance: 18.4,
    summary: rain < 0 ? 'Kondisi lebih kering: prioritaskan kecukupan irigasi dan penutup tanah.' : rain > 0 ? 'Curah hujan meningkat: periksa genangan dan kapasitas drainase.' : temperature > 0 ? 'Suhu meningkat: tinjau kebutuhan air dan jendela tanam bersama PPL.' : 'Skenario dasar: kaji rotasi legum dengan verifikasi drainase dan ketersediaan benih.',
  };
}

export function decisionState(gates = []) {
  const passed = gates.filter(gate => gate === 'lulus').length;
  return {
    status: 'ABSTAIN_FIELD_AUDIT_REQUIRED',
    label: 'Abstain — Data Belum Memadai',
    passed,
    completeness: 0,
    reason: gates.includes('gagal')
      ? 'Ada gerbang simulasi yang gagal. Rekomendasi resmi tidak dapat diterbitkan.'
      : 'Data nyata dan otorisasi terverifikasi belum tersedia. Kelulusan demo bukan bukti lapangan.',
  };
}

export function updateGate(gates, index, status) {
  if (index < 0 || index > 3 || !['lulus', 'gagal', 'belum'].includes(status)) return gates;
  if (index > 0 && gates.slice(0, index).some(gate => gate !== 'lulus')) return gates;
  return gates.map((gate, i) => i < index ? gate : i === index ? status : 'belum');
}

export function cellCondition(cell, activeLayers, result) {
  if (!activeLayers.length) return 'unknown';
  const seed = [...cell].reduce((sum, char) => sum + char.charCodeAt(0), 0);
  if (activeLayers.includes('eco') && seed % 7 < (result.pvrs > .8 ? 4 : 2)) return 'stress';
  if (activeLayers.includes('gpm') && seed % 5 < (result.erosion > .7 ? 3 : 1)) return 'erosion';
  if (activeLayers.some(id => id !== 'srtm')) return 'safe';
  return 'unknown';
}

export function number(value, decimals = 2) {
  return value.toLocaleString('id-ID', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}
