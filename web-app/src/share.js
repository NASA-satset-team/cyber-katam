import { number } from './model';

export async function createInfographic({ strategy, result, period }) {
  const canvas = document.createElement('canvas');
  canvas.width = 720;
  canvas.height = 960;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Peramban tidak mendukung pembuatan gambar.');
  ctx.fillStyle = '#f6f7ef';
  ctx.fillRect(0, 0, 720, 960);
  ctx.fillStyle = '#123e31';
  ctx.fillRect(0, 0, 720, 178);
  const text = (value, x, y, size, color = '#173c30', weight = 400) => {
    ctx.font = `${weight} ${size}px Arial, sans-serif`;
    ctx.fillStyle = color;
    ctx.fillText(value, x, y);
  };
  text('CYBER-KATAM', 42, 62, 31, '#ffffff', 700);
  text('RINGKASAN DISKUSI KELOMPOK TANI', 42, 101, 17, '#b6d7bf');
  text('DATA SIMULASI · BUKAN ANJURAN TANAM', 42, 139, 16, '#ffe29a', 700);
  text('Banyumas, Jawa Tengah', 42, 224, 26, '#173c30', 700);
  text(`Periode contoh: ${period}`, 42, 261, 20, '#6b7a68');
  ctx.fillStyle = '#fff0d7';
  ctx.fillRect(36, 296, 648, 135);
  text('AKAR MULAI KEHAUSAN', 58, 337, 23, '#956621', 700);
  text(`Cadangan air ilustratif: ${result.moisture}%`, 58, 378, 25, '#956621');
  text('Bukan hasil pengukuran lahan Anda.', 58, 407, 18, '#956621');
  text('Pilihan diskusi dalam demo', 42, 486, 20, '#6b7a68');
  text(strategy.short, 42, 533, 32, '#1d6b43', 700);
  const lines = [
    'Periksa drainase dan kecukupan air.',
    'Konfirmasi benih, inokulan, dan pasar.',
    'Diskusikan risiko dengan petani dan PPL.',
    `Contoh PVRS ${number(result.pvrs)}; bukan bukti NASA.`,
    'Manfaat air, pupuk, dan hama belum divalidasi.',
  ];
  lines.forEach((line, i) => text(`•  ${line}`, 42, 591 + i * 39, 20));
  ctx.fillStyle = '#e5ebdd';
  ctx.fillRect(36, 809, 648, 109);
  text('ABSTAIN — DATA BELUM MEMADAI', 56, 850, 22, '#365b3f', 700);
  text('Belum ada bukti NASA atau tanda tangan PPL sah.', 56, 884, 18, '#62755c');
  const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
  if (!blob || blob.size >= 150_000) throw new Error('Gambar belum memenuhi batas 150 KB. Silakan coba lagi.');
  return { blob, url: URL.createObjectURL(blob), size: blob.size };
}
