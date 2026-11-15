import { number } from './model';

function loadLogoImage(src) {
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = src;
  });
}

export async function createInfographic({ strategy, result, period }) {
  const canvas = document.createElement('canvas');
  canvas.width = 720;
  canvas.height = 960;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Peramban tidak mendukung pembuatan gambar.');
  ctx.fillStyle = '#f5f5f5';
  ctx.fillRect(0, 0, 720, 960);
  ctx.fillStyle = '#486c26';
  ctx.fillRect(0, 0, 720, 164);
  const text = (value, x, y, size, color = '#1f3322', weight = 400) => {
    ctx.font = `${weight} ${size}px Poppins, -apple-system, sans-serif`;
    ctx.fillStyle = color;
    ctx.fillText(value, x, y);
  };

  const logoImg = await loadLogoImage('/Group 3.png');
  if (logoImg && logoImg.naturalWidth > 0) {
    const targetH = 48;
    const targetW = Math.round((logoImg.naturalWidth / logoImg.naturalHeight) * targetH);
    const offscreen = document.createElement('canvas');
    offscreen.width = targetW;
    offscreen.height = targetH;
    const offCtx = offscreen.getContext('2d');
    if (offCtx) {
      offCtx.drawImage(logoImg, 0, 0, targetW, targetH);
      offCtx.globalCompositeOperation = 'source-in';
      offCtx.fillStyle = '#ffffff';
      offCtx.fillRect(0, 0, targetW, targetH);
      ctx.drawImage(offscreen, 42, 34);
    } else {
      ctx.drawImage(logoImg, 42, 34, targetW, targetH);
    }
  } else {
    text('Ciber Katam', 42, 70, 31, '#ffffff', 700);
  }

  text('DATA SIMULASI · BUKAN ANJURAN TANAM', 42, 126, 16, '#ffd600', 700);
  text('Banyumas, Jawa Tengah', 42, 224, 26, '#1f3322', 700);
  text(`Periode contoh: ${period}`, 42, 261, 20, '#5f785b');
  ctx.fillStyle = '#fffbe6';
  ctx.fillRect(36, 296, 648, 135);
  text('AKAR MULAI KEHAUSAN', 58, 337, 23, '#856404', 700);
  text(`Cadangan air ilustratif: ${result.moisture}%`, 58, 378, 25, '#856404');
  text('Bukan hasil pengukuran lahan Anda.', 58, 407, 18, '#856404');
  text('Pilihan diskusi dalam demo', 42, 486, 20, '#5f785b');
  text(strategy.short, 42, 533, 32, '#486c26', 700);
  const lines = [
    'Periksa drainase dan kecukupan air.',
    'Konfirmasi benih, inokulan, dan pasar.',
    'Diskusikan risiko dengan petani dan PPL.',
    `Contoh PVRS ${number(result.pvrs)}; bukan bukti NASA.`,
    'Manfaat air, pupuk, dan hama belum divalidasi.',
  ];
  lines.forEach((line, i) => text(`•  ${line}`, 42, 591 + i * 39, 20));
  ctx.fillStyle = '#ebfff3';
  ctx.fillRect(36, 809, 648, 109);
  text('ABSTAIN — DATA BELUM MEMADAI', 56, 850, 22, '#486c26', 700);
  text('Belum ada bukti NASA atau tanda tangan PPL sah.', 56, 884, 18, '#5f785b');
  const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
  if (!blob || blob.size >= 150_000) throw new Error('Gambar belum memenuhi batas 150 KB. Silakan coba lagi.');
  return { blob, url: URL.createObjectURL(blob), size: blob.size };
}
