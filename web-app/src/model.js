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
  { id: 'smap', name: 'SMAP L4', title: 'Kelembapan tanah', resolution: '~9 km', source: 'NASA · SPL4SMGP v8', value: '0,39 m³/m³', period: 'Dekad 19 · 2025', description: 'Kelembapan zona perakaran; satu piksel meliputi banyak sel H3. Data nyata dari pipeline.' },
  { id: 'eco', name: 'ECOSTRESS', title: 'Stres evaporatif & suhu', resolution: '70 m', source: 'NASA · LSTE v2', value: '32,1 °C', period: 'Dekad 19 · 2025', description: 'LST tersedia pada produk LSTE. Sumber ESI terpisah belum dipilih.' },
  { id: 'hls', name: 'HLS v2.0', title: 'Vegetasi & spektral', resolution: '30 m', source: 'NASA · HLS L30/S30 v2', value: 'NDVI 0,77', period: 'Dekad 19 · 2025', description: 'Reflektansi permukaan nyata. NDVI tinggi (>0,6) menunjukkan vegetasi lebat/sehat.' },
  { id: 'gpm', name: 'GPM IMERG', title: 'Curah hujan', resolution: '0,1°', source: 'NASA · IMERG v7', value: '60,5 mm / 10 hari', period: 'Dekad 19 · 2025', description: 'Resolusi asli 0,1°; laju mm/jam harus diagregasikan secara eksplisit.' },
  { id: 'srtm', name: 'SRTM', title: 'Elevasi & topografi', resolution: '~30 m', source: 'NASA / USGS · SRTM', value: 'Belum Tersedia', period: 'Statis (2000)', description: 'Topografi tidak menunjukkan kondisi drainase aktual di petak.' },
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
  // Jika sel memiliki indikator nyata, gunakan indikator tersebut
  const ind = cell?.indicators;
  if (ind) {
    if (activeLayers.includes('smap')) {
      if (ind.smap_wetness !== null && ind.smap_wetness !== undefined) {
        if (ind.smap_wetness < 0.2) return 'stress';     // sangat kering
        if (ind.smap_wetness > 0.5) return 'erosion';    // terlalu basah/risiko genangan
        return 'safe';
      }
    }
    if (activeLayers.includes('hls')) {
      if (ind.ndvi !== null && ind.ndvi !== undefined) {
        if (ind.ndvi < 0.3) return 'stress';    // vegetasi sangat jarang
        if (ind.ndvi > 0.5) return 'safe';      // vegetasi lebat/sehat
        return 'erosion';                        // vegetasi sedang
      }
    }
    if (activeLayers.includes('gpm')) {
      if (ind.gpm_rain_dekad !== null && ind.gpm_rain_dekad !== undefined) {
        if (ind.gpm_rain_dekad > 100) return 'erosion';  // curah hujan sangat tinggi
        if (ind.gpm_rain_dekad < 10)  return 'stress';   // sangat kering
        return 'safe';
      }
    }
    if (activeLayers.includes('eco')) {
      if (ind.pvrs !== null && ind.pvrs !== undefined) {
        if (ind.pvrs >= 0.70) return 'stress';
        if (ind.pvrs >= 0.45) return 'erosion';
        return 'safe';
      }
      if (ind.lst_anomaly !== null && ind.lst_anomaly !== undefined) {
        if (ind.lst_anomaly > 1.5) return 'stress';    // suhu jauh di atas normal
        if (ind.lst_anomaly < -1)  return 'safe';      // suhu di bawah normal (baik)
        return 'erosion';                              // anomali sedang
      }
    }
    if (activeLayers.includes('srtm')) {
      if (ind.srtm_slope !== null && ind.srtm_slope !== undefined) {
        if (ind.srtm_slope > 15) return 'erosion';   // lereng curam, risiko erosi
        if (ind.srtm_slope > 8)  return 'stress';    // lereng sedang
        return 'safe';                               // lereng landai, aman
      }
    }
    if (ind.erosion_alert) return 'erosion';
  }
  // Fallback ke simulasi (untuk sel tanpa indikator nyata atau resolusi 7/8)
  if (!activeLayers.length) return 'unknown';
  const seed = [...(cell?.id || cell)].reduce((sum, char) => sum + char.charCodeAt(0), 0);
  if (activeLayers.includes('eco') && seed % 7 < (result.pvrs > .8 ? 4 : 2)) return 'stress';
  if (activeLayers.includes('gpm') && seed % 5 < (result.erosion > .7 ? 3 : 1)) return 'erosion';
  if (activeLayers.some(id => id !== 'srtm')) return 'safe';
  return 'unknown';
}

export function number(value, decimals = 2) {
  return value.toLocaleString('id-ID', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

/**
 * Format nilai indikator satelit untuk tampilan UI.
 * Mengembalikan string yang siap ditampilkan, atau 'Belum Tersedia' jika null.
 */
export function formatIndicator(key, value) {
  if (value === null || value === undefined) {
    if (key === 'ndvi') return '☁ Tertutup Awan (QA Filter)';
    return 'Belum Tersedia';
  }
  switch (key) {
    case 'pvrs':          return `${number(value, 3)} (${value >= 0.7 ? 'Stres Kritis' : value >= 0.45 ? 'Stres Sedang' : 'Optimal / Aman'})`;
    case 'ndvi':          return `${number(value, 3)} (${value > 0.6 ? 'Subur' : value > 0.3 ? 'Sedang' : 'Jarang'})`;
    case 'bsi':           return number(value, 3);
    case 'smap_wetness':  return `${number(value * 100, 1)}% vol.`;
    case 'gpm_rain_dekad': return `${number(value, 1)} mm`;
    case 'srtm_slope':    return `${number(value, 1)}°`;
    case 'lst_anomaly':   return `${value >= 0 ? '+' : ''}${number(value, 2)} °C`;
    default:              return String(value);
  }
}

/**
 * Mengembalikan label kondisi berdasarkan layer aktif dan indikator sel.
 */
export function indicatorSummaryLabel(ind, activeLayers) {
  if (!ind) return null;
  if (activeLayers.includes('hls') && ind.ndvi != null)
    return ind.ndvi > 0.6 ? '🌿 Vegetasi Lebat' : ind.ndvi > 0.3 ? '🌾 Vegetasi Sedang' : '⚠ Vegetasi Jarang';
  if (activeLayers.includes('smap') && ind.smap_wetness != null)
    return ind.smap_wetness > 0.45 ? '💧 Tanah Sangat Lembap' : ind.smap_wetness > 0.25 ? '💧 Tanah Lembap Optimal' : '🏜 Tanah Kering';
  if (activeLayers.includes('gpm') && ind.gpm_rain_dekad != null)
    return ind.gpm_rain_dekad > 100 ? '⛈ Curah Hujan Sangat Tinggi' : ind.gpm_rain_dekad > 40 ? '🌧 Curah Hujan Sedang' : '☀ Curah Hujan Rendah';
  if (activeLayers.includes('srtm') && ind.srtm_slope != null)
    return ind.srtm_slope > 15 ? '⛰ Lereng Curam (Risiko Erosi)' : ind.srtm_slope > 8 ? '🏔 Lereng Sedang' : '🌾 Lereng Landai (Aman)';
  return null;
}
