import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, ArrowDownToLine, ArrowLeft, ArrowRight, ArrowUpRight, Bell, BookOpen, Check, ChevronDown, CircleHelp, ClipboardCheck, CloudRain, Droplets, FileCheck2, Fingerprint, FlaskConical, Globe2, Hexagon, Info, LayoutDashboard, Leaf, LockKeyhole, MapPin, PanelRightClose, PanelRightOpen, Play, Satellite, Search, Share2, ShieldCheck, SlidersHorizontal, Sprout, Sun, TriangleAlert, Users, Wheat, X } from 'lucide-react';
import { decisionState, gateDefinitions, layers, missingEvidence, number, simulate, strategies, updateGate } from './model';
import { createInfographic } from './share';
import './styles.css';

const LazyMap = React.lazy(() => import('./FieldMap'));
const periodOptions = ['1–10 November 2026', '11–20 November 2026', '21–30 November 2026'];
const initialGates = ['belum', 'belum', 'belum', 'belum'];
const layerIcons = [Droplets, Sun, Leaf, CloudRain, Globe2];

function Modal({ title, onClose, children, className = '' }) {
  const ref = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    ref.current.showModal();
    return () => { ref.current?.close(); previous?.focus(); };
  }, []);
  return <dialog ref={ref} className={`modal ${className}`} onCancel={e => { e.preventDefault(); onClose(); }} onClick={e => { if (e.target === e.currentTarget) onClose(); }} aria-labelledby="modal-title">
    <div className="modal-top"><h2 id="modal-title">{title}</h2><button className="icon-button" aria-label="Tutup dialog" onClick={onClose}><X size={20} /></button></div>{children}
  </dialog>;
}

function DemoBadge({ children = 'Data Simulasi', subtle = false }) {
  return <span className={`demo-badge ${subtle ? 'subtle' : ''}`}><FlaskConical size={11} />{children}</span>;
}

function App() {
  const [mode, setMode] = useState(() => window.matchMedia('(max-width: 700px)').matches ? 'farmer' : 'analyst');
  const [view, setView] = useState('dashboard');
  const [period, setPeriod] = useState(periodOptions[0]);
  const [activeLayers, setActiveLayers] = useState(['smap', 'eco', 'hls', 'gpm']);
  const [resolution, setResolution] = useState(8);
  const [showGrid, setShowGrid] = useState(true);
  const [selectedCell, setSelectedCell] = useState(null);
  const [selectedStrategy, setSelectedStrategy] = useState('B');
  const [rain, setRain] = useState(0);
  const [temperature, setTemperature] = useState(0);
  const [result, setResult] = useState(() => simulate());
  const [hasRun, setHasRun] = useState(false);
  const [diagnostics, setDiagnostics] = useState(true);
  const [layersOpen, setLayersOpen] = useState(true);
  const [gates, setGates] = useState(initialGates);
  const [activeGate, setActiveGate] = useState(0);
  const [role, setRole] = useState('Analis');
  const [signature, setSignature] = useState('');
  const [signedBy, setSignedBy] = useState('');
  const [acknowledged, setAcknowledged] = useState(false);
  const [modal, setModal] = useState(null);
  const [share, setShare] = useState(null);
  const [shareFeedback, setShareFeedback] = useState('');
  const [generating, setGenerating] = useState(false);
  const [toast, setToast] = useState('');
  const [term, setTerm] = useState(null);
  const shareRef = useRef(null);
  const strategy = strategies.find(item => item.id === selectedStrategy);
  const decision = decisionState(gates);
  const dark = mode === 'analyst' && view === 'dashboard';
  const dirty = result.rain !== rain || result.temperature !== temperature;

  useEffect(() => { document.documentElement.lang = 'id'; }, []);
  useEffect(() => {
    if (!toast) return;
    const timeout = setTimeout(() => setToast(''), 4500);
    return () => clearTimeout(timeout);
  }, [toast]);
  useEffect(() => () => { if (shareRef.current) URL.revokeObjectURL(shareRef.current); }, []);

  function changeMode(next) { setMode(next); setView('dashboard'); setTerm(null); window.scrollTo(0, 0); }
  function openAudit() { setView('audit'); setTerm(null); window.scrollTo(0, 0); }
  function runSimulation() {
    setResult(simulate(rain, temperature)); setHasRun(true);
    setGates(initialGates); setSignedBy(''); setSignature(''); setAcknowledged(false); setActiveGate(0);
    setToast('Simulasi diperbarui. Ini respons demo, bukan model iklim atau prakiraan nyata.');
  }
  function changePeriod(next) {
    setPeriod(next); setGates(initialGates); setSignedBy(''); setSignature(''); setActiveGate(0);
    setToast('Periode contoh diubah. Tidak ada observasi nyata yang diambil.');
  }
  function selectStrategy(id) {
    setSelectedStrategy(id); setGates(initialGates); setSignedBy(''); setSignature(''); setAcknowledged(false); setActiveGate(0);
  }
  function verifyGate(status) {
    setGates(current => updateGate(current, activeGate, status));
    setSignedBy(activeGate === 3 && status === 'lulus' ? signature.trim() : '');
    if (status === 'lulus' && activeGate < 3) setActiveGate(activeGate + 1);
    setToast(status === 'gagal' ? 'Gerbang ditandai gagal dalam simulasi. Sistem tetap abstain.' : 'Verifikasi demo dicatat untuk sesi ini. Bukan validasi lapangan.');
  }
  async function openShare() {
    setGenerating(true);
    setShareFeedback('');
    try {
      const artifact = await createInfographic({ strategy, result, period });
      if (shareRef.current) URL.revokeObjectURL(shareRef.current);
      shareRef.current = artifact.url; setShare(artifact); setModal('share');
    } catch (error) { setToast(error.message); }
    finally { setGenerating(false); }
  }
  function downloadShare() {
    const anchor = document.createElement('a');
    anchor.href = share.url; anchor.download = 'CYBER-KATAM-ringkasan-simulasi.png'; anchor.click();
    setShareFeedback('Gambar PNG diunduh. Bagikan sebagai bahan diskusi, bukan anjuran tanam.');
  }

  const commonAuditButton = <button className="button primary" onClick={openAudit}><FileCheck2 size={16} />Lihat Penjelasan Keputusan<ArrowUpRight size={15} /></button>;

  return <div className={`platform ${dark ? 'dark-theme' : 'light-theme'} ${view === 'audit' ? 'audit-theme' : ''}`}>
    <a className="skip-link" href="#content">Lewati ke konten utama</a>
    <header className="app-header">
      <button className="wordmark" onClick={() => { setView('dashboard'); window.scrollTo(0, 0); }} aria-label="Beranda CYBER-KATAM"><span className="logo-mark"><Sprout size={22} /></span><span>CYBER<span className="logo-light">-KATAM</span><small>INTELIJEN PERTANIAN BERBASIS BUMI</small></span></button>
      <div className="header-divider" /><span className="header-region"><MapPin size={15} /><span>Banyumas<small>Jawa Tengah, Indonesia</small></span></span>
      <div className="header-end"><span className="header-demo"><i />PROTOTIPE INTERAKTIF</span><div className="mode-switch" aria-label="Pilih mode pengguna"><button className={mode === 'analyst' ? 'active' : ''} aria-pressed={mode === 'analyst'} onClick={() => changeMode('analyst')}><Activity size={14} /><span>Analis <span className="long-label">/ Pembuat Kebijakan</span></span></button><button className={mode === 'farmer' ? 'active' : ''} aria-pressed={mode === 'farmer'} onClick={() => changeMode('farmer')}><Sprout size={14} />Petani / PPL</button></div><button className="notification-button" aria-label="Lihat pemberitahuan" onClick={() => setModal('notification')}><Bell size={18} /><i /></button><button className="avatar" aria-label="Informasi profil demo" onClick={() => setModal('profile')}>AP</button></div>
    </header>

    {dark && <nav className="analyst-rail" aria-label="Navigasi analis"><button className="active" aria-label="Dasbor geospasial" onClick={() => setView('dashboard')}><LayoutDashboard size={20} /><span>Dasbor</span></button><button aria-label="Buka metadata sumber" onClick={() => setModal('sources')}><Satellite size={21} /><span>Satelit</span></button><button aria-label="Buka audit rekomendasi" onClick={openAudit}><ClipboardCheck size={21} /><span>Audit</span></button><div className="rail-bottom"><button aria-label="Panduan platform" onClick={() => setModal('help')}><CircleHelp size={21} /><span>Panduan</span></button><span className="rail-version">v0.2</span></div></nav>}

    <main id="content" className={dark ? 'analyst-main' : view === 'audit' ? 'audit-main' : 'farmer-main'}>
      {view === 'dashboard' && mode === 'analyst' && <>
        <div className="analyst-heading"><div><div className="eyebrow"><span className="tiny-line" /> PUSAT INTELIJEN AGROKLIMAT</div><h1>Memahami lahan. Merencanakan ketahanan.</h1><p>Eksplorasi rotasi tanaman berbasis konteks lingkungan dan pengetahuan lokal.</p></div><div className="analysis-period"><label htmlFor="period">PERIODE ANALISIS CONTOH</label><div><select id="period" aria-label="Periode analisis" value={period} onChange={e => changePeriod(e.target.value)}>{periodOptions.map(option => <option key={option}>{option}</option>)}</select><ChevronDown size={14} /></div></div></div>
        <div className="analyst-status-strip"><span><i className="status-dot" /> Ruang kerja Banyumas <span className="strip-separator">/</span> Eksplorasi skenario</span><div><DemoBadge /><span className="no-evidence"><LockKeyhole size={12} />0 observasi terverifikasi</span><button className="diagnostic-toggle" aria-expanded={diagnostics} onClick={() => setDiagnostics(!diagnostics)}>{diagnostics ? <PanelRightClose size={16} /> : <PanelRightOpen size={16} />}<span>Diagnostik</span></button></div></div>
        <div className={`analyst-workspace ${!diagnostics ? 'sidebar-collapsed' : ''}`}>
          <section className="map-and-simulation">
            <div className="map-card">
              <div className="map-card-heading"><h2><Globe2 size={16} />Peta Intelijen Lahan</h2><span><i /> DATA ILUSTRATIF · BUKAN OBSERVASI</span></div>
              <div className="map-stage">
                <React.Suspense fallback={<div className="map-fallback">Memuat peta skematik…</div>}><LazyMap {...{ activeLayers, result, resolution, setResolution, selectedCell, showGrid, setShowGrid }} onCell={setSelectedCell} /></React.Suspense>
                <div className={`satellite-panel ${!layersOpen ? 'collapsed' : ''}`}><button className="satellite-title" onClick={() => setLayersOpen(!layersOpen)} aria-expanded={layersOpen}><Satellite size={16} /><span>Lapisan Data Satelit NASA</span><ChevronDown size={14} /></button>
                  {layersOpen && <><p className="satellite-subtitle">Pilih konteks visual untuk eksplorasi.</p><div className="layer-list">{layers.map((layer, index) => { const Icon = layerIcons[index]; return <button key={layer.id} className={`layer-row ${activeLayers.includes(layer.id) ? 'enabled' : ''}`} role="switch" aria-checked={activeLayers.includes(layer.id)} aria-label={`Lapisan ${layer.name}`} onClick={() => setActiveLayers(current => current.includes(layer.id) ? current.filter(id => id !== layer.id) : [...current, layer.id])}><span className={`layer-icon ${layer.id}`}><Icon size={16} /></span><span className="layer-description"><strong>{layer.name}<small>{layer.resolution}</small></strong><span>{layer.title}</span><small>{layer.source} · {layer.id === 'srtm' ? 'Belum tersedia' : 'Ilustratif'}</small></span><span className="toggle-track"><i /></span></button>; })}</div><div className="layer-foot"><Info size={12} /><span>Tampilan simulasi. Tidak mengambil data NASA.</span></div></>}
                </div>
                <div className="map-legend"><span className="legend-title">KLASIFIKASI SIMULASI</span><div>{activeLayers.includes('eco') && <span><i className="red-dot" />Stres akar (PVRS)</span>}{activeLayers.includes('gpm') && <span><i className="orange-dot" />Erosi lahan bera</span>}{activeLayers.some(id => id !== 'srtm') && <span><i className="green-dot" />Koridor relatif aman</span>}{!activeLayers.some(id => id !== 'srtm') && <span><i className="gray-dot" />Indikator disembunyikan</span>}</div><small className="active-context">Konteks: {activeLayers.length ? layers.filter(layer => activeLayers.includes(layer.id)).map(layer => layer.name).join(' · ') : 'Tidak ada lapisan aktif'}</small><small>Warna buatan untuk demo · bukan klasifikasi lahan nyata</small></div>
              </div>
              <div className="native-resolution-note"><Info size={13} /><p>H3 bukan resolusi sensor. <strong>SMAP ~9 km · GPM 0,1° · HLS 30 m · LST 70 m.</strong> Nilai kasar tidak mewakili pengukuran independen tiap sel.</p><button onClick={() => setModal('sources')}>Metadata<ArrowUpRight size={12} /></button></div>
            </div>
            <section className="climate-panel"><div className="climate-title"><div><SlidersHorizontal size={17} /><h2>Simulasi Skenario Iklim</h2></div><span>DEMO DETERMINISTIK · BUKAN MODEL IKLIM</span></div><div className="climate-controls"><Slider label="Anomali curah hujan" unit="%" value={rain} setValue={setRain} min={-30} max={30} step={5} icon={CloudRain} /><Slider label="Kenaikan suhu" unit="°C" value={temperature} setValue={setTemperature} min={0} max={3} step={.5} icon={Sun} /><button className="button primary run-button" onClick={runSimulation}><Play size={15} fill="currentColor" />Jalankan Simulasi</button></div><div className="simulation-summary" aria-live="polite"><span className="summary-status"><i />{dirty ? 'Perubahan belum dijalankan' : hasRun ? 'Simulasi diperbarui' : 'Skenario dasar aktif'}</span><p>{result.summary}</p></div></section>
          </section>
          {diagnostics && <aside className="diagnostic-sidebar"><div className="diagnostic-heading"><h2>Diagnostik Biofisika & Fiskal</h2><Info size={15} /></div><div className="diagnostic-content">
            <div className="diagnostic-kpis"><RiskMetric name="PVRS" explanation="Risiko stres akar" value={result.pvrs} color="red" /><RiskMetric name="BF-EHSI" explanation="Risiko erosi lahan bera" value={result.erosion} color="orange" /></div>
            <div className="water-ledger"><span><Droplets size={15} />Neraca air ilustratif</span><strong>{result.water > 0 ? '+' : ''}{result.water}<small> mm</small></strong></div>
            <div className="diagnostic-section-title"><span>STRATEGI ROTASI TANAMAN</span><span>3 SKENARIO</span></div>
            <div className="compact-scenarios">{strategies.map(item => <button key={item.id} className={`compact-scenario ${item.id === 'B' ? 'recommended' : ''} ${selectedStrategy === item.id ? 'selected' : ''}`} aria-pressed={selectedStrategy === item.id} onClick={() => selectStrategy(item.id)}><span className="scenario-letter">{item.id}</span><span><strong>{item.name}</strong><small>{item.id === 'B' ? <><span className="status-dot" />Unggulan dalam demo</> : item.id === 'A' ? 'Pola eksisting · pembanding' : 'Alternatif diversifikasi'}</small></span><span className="scenario-radio">{selectedStrategy === item.id && <Check size={11} />}</span></button>)}</div>
            <Pareto selected={selectedStrategy} onSelect={selectStrategy} />
            <div className="fiscal-card"><div><span className="fiscal-icon"><Leaf size={17} /></span><span>POTENSI PENGHEMATAN SUBSIDI UREA</span></div><h3>Rp16,58 <span>Miliar</span></h3><p>per kluster H3-7 · ilustrasi anggaran konsep</p><div><span><ShieldCheck size={13} />Penurunan risiko AUTP</span><strong>{number(result.insurance, 1)}%<small> ilustratif</small></strong></div><small className="fiscal-caveat">Bukan hasil fiskal terverifikasi. Luas kluster dan manfaat aktual belum ditetapkan.</small></div>
            <div className="diagnostic-cta"><div><LockKeyhole size={13} />Menunggu verifikasi lapangan</div>{commonAuditButton}</div>
          </div></aside>}
        </div>
        <div className="analyst-bottom"><span><ShieldCheck size={13} />Keputusan akhir tetap pada petani dan penyuluh.</span><span>Semua angka adalah Data Simulasi. Tidak untuk keputusan operasional.</span><button onClick={() => setModal('help')}>Tentang prototipe<ArrowUpRight size={12} /></button></div>
      </>}

      {view === 'dashboard' && mode === 'farmer' && <>
        <div className="farmer-greeting"><div><div className="eyebrow">TEMAN MERENCANAKAN MUSIM TANAM</div><h1>Selamat pagi, Pak/Bu!<Sprout size={32} /></h1><p>Mari kenali kondisi lahan dan pertimbangkan pilihan tanam bersama.</p><div className="farm-location"><MapPin size={15} />Banyumas, Jawa Tengah<span />Luas lahan: <strong>Belum dicatat</strong></div></div><button className="farmer-period" onClick={() => setModal('period')}><Sun size={20} /><span>Periode contoh<strong>{period}</strong></span><ChevronDown size={14} /></button></div>
        <div className="farmer-demo-notice"><FlaskConical size={17} /><p><strong>Anda berada di ruang simulasi.</strong> Informasi berikut adalah contoh, bukan hasil pengukuran lahan Anda.</p><button onClick={() => setModal('help')}>Pelajari<ArrowUpRight size={14} /></button></div>
        <section className="farmer-warning"><div className="warning-water"><Droplets size={32} /></div><div className="warning-copy"><span className="warning-severity"><i />PERINGATAN ILUSTRATIF · PERLU DICEK</span><h2>Akar Mulai Kehausan</h2><p><button className="term-link" aria-expanded={term === 'water'} onClick={() => setTerm(term === 'water' ? null : 'water')}>Cadangan air tanah<Info size={12} /></button> dalam contoh diperkirakan tinggal <strong>{result.moisture}%</strong>. Pertimbangkan pilihan tanam yang lebih hemat air bersama PPL.</p>{term === 'water' && <div className="term-popover" role="tooltip">Cadangan air tanah adalah air yang masih tersimpan di tanah dan dapat dimanfaatkan akar tanaman.</div>}<small>Langkah awal: cek air irigasi dan drainase sebelum mengubah pola tanam.</small></div><div className="water-gauge"><svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="42" fill="none" stroke="#eadac2" strokeWidth="7" /><circle cx="50" cy="50" r="42" fill="none" stroke="#c99545" strokeWidth="7" strokeDasharray={`${result.moisture * 2.64} 264`} transform="rotate(-90 50 50)" strokeLinecap="round" /></svg><div><strong>{result.moisture}<small>%</small></strong><span>air ilustratif</span></div></div></section>
        <section className="farmer-rotations"><div className="farmer-section-heading"><div><div className="eyebrow">PILIHAN YANG BISA DIDISKUSIKAN</div><h2>Yuk, Bandingkan Pilihan Tanam!</h2><p>Kenali manfaat dan pertimbangannya. Tidak ada satu pola yang cocok untuk semua lahan.</p></div><DemoBadge /></div><div className="farmer-scenarios">{strategies.map(item => <article key={item.id} className={`farmer-scenario ${item.id === 'B' ? 'recommended' : ''} ${selectedStrategy === item.id ? 'selected' : ''}`}><div className="farmer-scenario-top"><span className="scenario-letter">{item.id}</span><span className="crop-badge">{item.id === 'B' && <Sprout size={12} />}{item.label}{item.id === 'B' && <small> · demo</small>}</span></div><div className="crop-illustration"><Wheat size={34} strokeWidth={1.4} /><span className="crop-arrow"><ArrowRight size={18} /></span>{item.id === 'A' ? <Sun size={32} strokeWidth={1.4} /> : <Sprout size={36} strokeWidth={1.4} />}</div><h3>{item.name}</h3><p>{item.note}</p><ul><li><Droplets size={18} /><span>{item.water}</span></li><li><Leaf size={18} /><span>{item.nitrogen}</span></li><li><ShieldCheck size={18} /><span>{item.pests}</span></li></ul><button className={`button ${selectedStrategy === item.id ? 'primary' : 'secondary'}`} aria-pressed={selectedStrategy === item.id} onClick={() => selectStrategy(item.id)}>{selectedStrategy === item.id ? <Check size={16} /> : <Search size={16} />}{selectedStrategy === item.id ? 'Dipilih untuk diskusi' : 'Bandingkan pilihan ini'}</button></article>)}</div><p className="farmer-caption"><Info size={14} />Perbandingan kualitatif dan manfaat potensial belum divalidasi di lapangan.</p></section>
        <section className="farmer-recommendation"><div className="recommendation-story"><img src="/indonesia-fields.jpg" alt="Foto ilustratif bentang pertanian di Indonesia, bukan lahan pengguna" /><div><span>PENGETAHUAN LOKAL TETAP UTAMA</span><h2>Lahan berbeda.<br />Pertimbangan pun berbeda.</h2><p>Keputusan terbaik dibuat bersama petani dan penyuluh yang mengenal lahannya.</p><small>Foto: Iswanto Arif / Unsplash · ilustrasi</small></div></div><div className="recommendation-content"><div className="recommendation-title"><span className="round-leaf"><Sprout size={22} /></span><span><small>PILIHAN DISKUSI SIMULASI</small><h2>Rekomendasi untuk Lahan Anda</h2></span></div><h3>{strategy.name}</h3><p>{strategy.why}</p><div className="farmer-reasons"><div><Check size={17} /><p><strong>Manfaat yang berpotensi didapat</strong>{strategy.benefit}</p></div><div><TriangleAlert size={17} /><p><strong>Yang perlu diperhatikan</strong>{strategy.risk}</p></div><div><ClipboardCheck size={17} /><p><strong>Masih perlu diperiksa</strong>Drainase, pH tanah, persediaan air, benih, biaya, dan kesepakatan kelompok tani.</p></div></div><div className="recommendation-actions"><button className="button primary" onClick={openAudit}><BookOpen size={16} />Lihat Alasan Rekomendasi</button><button className="button secondary" onClick={openShare} disabled={generating}><Users size={16} />Bagikan ke Kelompok Tani</button></div><span className="withheld-note"><LockKeyhole size={12} />Anjuran resmi ditahan sampai bukti dan verifikasi tersedia.</span></div></section>
        <div className="whatsapp-banner"><span className="share-round"><Share2 size={23} /></span><div><h3>Keputusan tanam lebih baik dibicarakan bersama.</h3><p>Siapkan kartu ringan untuk bahan diskusi dengan kelompok tani dan PPL.</p></div><button className="button primary" onClick={openShare} disabled={generating}><Share2 size={16} />{generating ? 'Menyiapkan gambar…' : 'Bagikan Ringkasan via WhatsApp'}</button></div>
        <footer className="farmer-footer"><span><Sprout size={16} />CYBER-KATAM · Dari bumi, untuk petani.</span><span>Prototipe simulasi. Bukan pengganti keahlian agronomi.</span><button onClick={openAudit}>Audit Rekomendasi<ArrowUpRight size={13} /></button></footer>
      </>}

      {view === 'audit' && <>
        <button className="back-button" onClick={() => { setView('dashboard'); window.scrollTo(0, 0); }}><ArrowLeft size={15} />Kembali ke {mode === 'analyst' ? 'dasbor analis' : 'mode petani'}</button>
        <div className="audit-page-heading"><div><div className="eyebrow">JEJAK KEPUTUSAN YANG DAPAT DITELUSURI</div><h1>Sertifikat Penjelasan Keputusan</h1><p>Transparansi bukti, manfaat, keterbatasan, dan risiko rekomendasi.</p></div><div className="certificate-seal"><Hexagon size={64} strokeWidth={1} /><ShieldCheck size={28} /><span>DRAF SIMULASI</span></div></div>
        <section className="certificate-header"><div className="certificate-identity"><span className="certificate-icon"><FileCheck2 size={28} /></span><div><span className="micro-label">ID REKOMENDASI DEMO</span><h2>CK-BMS-2026-{selectedStrategy}01</h2><span>Dokumen eksplorasi · bukan sertifikat otorisasi</span></div><div className="certificate-status"><LockKeyhole size={15} /><strong>Abstain — Data Belum Memadai</strong></div></div><div className="certificate-meta"><div><span>Wilayah analisis</span><strong>Banyumas, Jawa Tengah</strong></div><div><span>Periode analisis contoh</span><strong>{period}</strong><small>Tanggal contoh: {period.split('–')[1]}</small></div><div><span>Rotasi yang dikaji</span><strong>{strategy.name}</strong></div><div><span>Status data</span><DemoBadge>Data Ilustratif · Belum Diverifikasi</DemoBadge></div></div></section>
        <div className="xai-grid">
          <section className="xai-block evidence-block"><BlockTitle index="01" icon={Satellite} title="Bukti Kuantitatif Satelit NASA" subtitle="Contoh indikator, bukan bukti observasi nyata." /><div className="evidence-table"><div className="evidence-table-heading"><span>INDIKATOR / SUMBER</span><span>NILAI / RESOLUSI</span></div>{layers.map(layer => <div className="evidence-row" key={layer.id}><div><strong>{layer.title}</strong><span>{layer.source}</span><small>Periode: {layer.id === 'srtm' ? 'Belum Tersedia' : period}</small></div><div><strong>{layer.id === 'eco' ? `${number(32.1 + result.temperature, 1)} °C` : layer.value}</strong><span>Asli {layer.resolution}</span><small>{layer.id === 'srtm' ? 'Belum Tersedia' : 'Data Simulasi'}</small></div></div>)}</div><div className="block-footnote"><Info size={13} />LSTE bukan ESI. Sumber ESI dan seluruh ekspor nyata belum tersedia. SMAP/GPM tidak independen per sel H3.</div></section>
          <section className="xai-block benefits-block"><BlockTitle index="02" icon={Sprout} title="Manfaat Multi-Dimensi" subtitle="Potensi bersyarat, belum terukur di lahan." /><div className="benefit-list">{[{ icon: Droplets, title: 'Efisiensi air', text: strategy.water, width: strategy.waterScore }, { icon: Leaf, title: 'Kesehatan tanah', text: 'Pengelolaan residu dan penutup tanah perlu ditinjau.', width: strategy.soilScore }, { icon: Sprout, title: 'Penghematan pupuk', text: 'Fiksasi nitrogen tidak sama dengan pengurangan dosis pupuk.', width: 65 }, { icon: ShieldCheck, title: 'Pemutusan siklus hama', text: strategy.pests, width: strategy.pestScore }, { icon: Sun, title: 'Ketahanan iklim', text: 'Diversifikasi tetap bergantung pada kondisi lokal.', width: 74 }].map(({ icon: Icon, title, text, width }) => <div className="benefit-item" key={title}><span><Icon size={19} /></span><div><strong>{title}</strong><p>{text}</p><div className="impact-track"><i style={{ width: `${width}%` }} /></div></div></div>)}</div><div className="block-footnote"><FlaskConical size={13} />Panjang indikator adalah ilustrasi visual, bukan besaran manfaat atau probabilitas.</div></section>
          <section className="xai-block gap-block"><BlockTitle index="03" icon={Info} title="Batasan Informasi Satelit" subtitle="Tidak dapat dipastikan dari satelit saja." /><ul className="audit-list">{['pH tanah lokal pada skala mikro', 'Kondisi pintu air irigasi tersier', 'Ketersediaan benih dan inokulan aktual', 'Kondisi drainase dan genangan di petak', 'Kendala tenaga kerja, biaya, dan alat petani'].map(text => <li key={text}><span className="unknown-icon">?</span><span>{text}</span><small>Perlu cek lapangan</small></li>)}</ul></section>
          <section className="xai-block risk-block"><BlockTitle index="04" icon={TriangleAlert} title="Risiko Lokal" subtitle="Asumsi dan ketidakpastian yang harus ditinjau." /><ul className="audit-list">{['Hujan tidak pasti dan perubahan waktu tanam', 'Variasi tekstur tanah serta risiko genangan', 'Ledakan hama dan migrasi antarhamparan', 'Pasokan benih / inokulan tidak sesuai rencana', 'Keterbatasan modal, pasar, dan pelaksanaan'].map(text => <li key={text}><TriangleAlert size={15} /><span>{text}</span></li>)}</ul><div className="risk-callout">Jangan mengubah dosis pupuk atau waktu tanam hanya berdasarkan contoh ini.</div></section>
        </div>
        <section className="gatekeeper-panel"><div className="gatekeeper-heading"><div><div className="eyebrow">ABSTENSI TERKENDALI · KENDALI MANUSIA</div><h2>Gerbang Validasi Rekomendasi</h2><p>Empat langkah berurutan. Kelulusan simulasi tidak menggantikan bukti nyata.</p></div><label className="role-select">Peran demo<select aria-label="Peran verifikasi demo" value={role} onChange={e => setRole(e.target.value)}><option>Analis</option><option>PPL</option></select></label></div><div className="gate-sequence">{gateDefinitions.map((gate, index) => <button key={gate.title} className={`gate-step ${activeGate === index ? 'active' : ''} ${gates[index]}`} onClick={() => setActiveGate(index)} aria-pressed={activeGate === index}><span className="gate-number">{gates[index] === 'lulus' ? <Check size={18} /> : gates[index] === 'gagal' ? <X size={18} /> : `0${index + 1}`}</span><span><strong>{gate.title}</strong><small>{gates[index] === 'lulus' ? 'Lulus · Simulasi' : gates[index] === 'gagal' ? 'Gagal · Simulasi' : 'Belum Diverifikasi'}</small></span>{index < 3 && <ArrowRight className="gate-arrow" size={15} />}</button>)}</div>
          <div className="gate-detail"><div className="gate-detail-copy"><span className="micro-label">GERBANG 0{activeGate + 1} · {gateDefinitions[activeGate].owner.toUpperCase()}</span><h3>{gateDefinitions[activeGate].title}</h3><p>{gateDefinitions[activeGate].description}</p><div className="gate-evidence-gap"><Info size={14} />{gateDefinitions[activeGate].missing}</div></div><div className="gate-actions">
            {activeGate > 0 && gates.slice(0, activeGate).some(gate => gate !== 'lulus') ? <div className="locked-gate"><LockKeyhole size={22} /><p>Selesaikan gerbang sebelumnya dalam demo untuk mencoba tahap ini.</p></div> : activeGate === 3 ? <><label>Nama PPL untuk simulasi<input aria-label="Nama PPL untuk simulasi" value={signature} onChange={e => setSignature(e.target.value)} placeholder="Contoh: Siti Rahma" maxLength={70} /></label><label className="signature-ack"><input type="checkbox" checked={acknowledged} onChange={e => setAcknowledged(e.target.checked)} />Saya memahami ini bukan tanda tangan digital yang sah.</label><button className="button primary" disabled={role !== 'PPL' || !signature.trim() || !acknowledged} onClick={() => verifyGate('lulus')}><Fingerprint size={17} />Simulasikan Tanda Tangan PPL</button>{role !== 'PPL' && <small className="signature-help">Pilih peran demo PPL untuk mencoba tanda tangan.</small>}{signedBy && <span className="signature-record"><Check size={13} />Simulasi oleh {signedBy} · hanya sesi ini</span>}</> : <><DemoBadge /><button className="button primary" onClick={() => verifyGate('lulus')}><Check size={16} />Simulasikan Lulus</button><button className="button danger-outline" onClick={() => verifyGate('gagal')}><X size={16} />Simulasikan Gagal</button><small>Tidak mengunggah bukti atau menyimpan catatan.</small></>}
          </div></div>
          <div className="verification-meter"><div><span>Gerbang demo yang lulus</span><strong>{decision.passed}/4</strong><div className="meter-track"><i style={{ width: `${decision.passed * 25}%` }} /></div></div><div><span>Kelengkapan bukti nyata</span><strong>0%</strong><div className="meter-track empty" /><small>Seluruh indikator masih ilustratif.</small></div><div><span>Keyakinan / batas galat analitis</span><strong className="not-calibrated">Belum terkalibrasi</strong><small>Tidak ada persentase keyakinan yang sah. Keyakinan bukan jaminan kebenaran.</small></div></div>
          <div className="abstention-banner" role="status"><span className="abstention-icon"><LockKeyhole size={24} /></span><div><span>STATUS KEPUTUSAN</span><h3>{decision.label}</h3><p>{decision.reason}</p></div><span className="withheld-pill">Anjuran resmi ditahan</span></div>
          <details className="missing-evidence"><summary>Bukti yang masih diperlukan<span>{missingEvidence.length} kelompok bukti<ChevronDown size={14} /></span></summary><ul>{missingEvidence.map(item => <li key={item}>{item}</li>)}</ul></details>
        </section><div className="audit-bottom"><span><ShieldCheck size={16} />Draf simulasi · Tidak memiliki kekuatan otorisasi</span><button className="button secondary" onClick={() => { setGates(initialGates); setActiveGate(0); setSignedBy(''); setSignature(''); setAcknowledged(false); setToast('Gerbang simulasi diatur ulang.'); }}>Atur ulang verifikasi</button><button className="button primary" onClick={openShare} disabled={generating}><ArrowDownToLine size={16} />Ringkasan untuk diskusi</button></div>
      </>}
    </main>

    {toast && <div className="toast" role="status"><Info size={18} />{toast}<button aria-label="Tutup pemberitahuan" onClick={() => setToast('')}><X size={15} /></button></div>}
    {modal === 'share' && share && <Modal title="Pratinjau Ringkasan Kelompok Tani" onClose={() => setModal(null)} className="share-modal"><p className="modal-description">Kartu PNG dibuat di peramban. Tinjau sebelum mengunduh atau mencoba simulasi berbagi.</p><div className="share-preview"><img src={share.url} alt={`Kartu ringkasan Data Simulasi ${strategy.name} untuk Banyumas dengan status abstain`} /></div><div className="share-file-info"><span><FileCheck2 size={15} />PNG · {number(share.size / 1000, 1)} KB</span><span><Check size={13} />Di bawah 150 KB</span></div><div className="share-actions"><button className="button secondary" onClick={downloadShare}><ArrowDownToLine size={16} />Unduh Kartu PNG</button><button className="button primary" onClick={() => setShareFeedback('Simulasi berbagi selesai. Tidak ada pesan WhatsApp yang dikirim. Unduh kartu untuk berbagi sendiri.')}><Share2 size={16} />Simulasikan Berbagi</button></div>{shareFeedback && <p className="share-feedback" role="status"><Check size={15} />{shareFeedback}</p>}<p className="share-disclaimer">Tidak terhubung ke WhatsApp. Tidak ada pesan atau data petani yang dikirim.</p></Modal>}
    {modal === 'sources' && <Modal title="Sumber & Resolusi Data" onClose={() => setModal(null)}><div className="source-modal-intro"><DemoBadge />Seluruh nilai dalam prototipe adalah simulasi. Tidak ada observasi NASA terverifikasi.</div>{layers.map(layer => <div className="source-modal-row" key={layer.id}><div><strong>{layer.name}</strong><span>{layer.source}</span></div><span className="source-resolution">{layer.resolution}</span><p>{layer.description}</p><small>Data nyata: Belum Tersedia · periode observasi: Belum Tersedia</small></div>)}<p className="modal-description">Foto pertanian dan batas petak bersifat ilustratif. H3-7–9 diturunkan dari indeks H3 sintetis valid, bukan mask sawah.</p></Modal>}
    {modal === 'help' && <Modal title="Tentang CYBER-KATAM" onClose={() => setModal(null)}><div className="about-symbol"><Sprout size={36} /></div><h3>Dari observasi menuju keputusan yang dapat dijelaskan.</h3><p className="modal-description">Prototipe ini memperagakan eksplorasi rotasi, simulasi iklim deterministik, dan empat gerbang audit. Tidak ada model iklim, AI terkalibrasi, API NASA, atau layanan tanda tangan digital yang terhubung.</p><p className="modal-description">Warna, skor Pareto, nilai biofisika, dan manfaat fiskal adalah Data Simulasi. Geometri H3 valid tidak berarti tutupan lahan atau indikatornya terverifikasi. Data hanya berada di memori sesi ini.</p><div className="modal-callout">Petani dan PPL tetap memegang keputusan akhir. Sistem menahan anjuran resmi karena bukti nyata belum tersedia.</div></Modal>}
    {modal === 'notification' && <Modal title="Pemberitahuan" onClose={() => setModal(null)}><div className="notification-item"><TriangleAlert size={22} /><div><h3>Verifikasi belum lengkap</h3><p>Observasi nyata dan pemeriksaan lapangan belum tersedia. Tinjau gerbang validasi sebelum menafsirkan hasil demo.</p><button className="button primary" onClick={() => { setModal(null); openAudit(); }}>Buka Audit Rekomendasi<ArrowRight size={15} /></button></div></div></Modal>}
    {modal === 'profile' && <Modal title="Profil Ruang Simulasi" onClose={() => setModal(null)}><div className="profile-demo"><span className="avatar">AP</span><h3>Pengguna demo</h3><p>Peran saat ini: {mode === 'analyst' ? 'Analis / Pembuat Kebijakan' : 'Petani / PPL'}</p></div><p className="modal-description">Tidak ada akun, identitas, atau data lahan tersimpan. Verifikasi dan tanda tangan hanya simulasi dalam sesi peramban ini.</p></Modal>}
    {modal === 'period' && <Modal title="Pilih Periode Contoh" onClose={() => setModal(null)}><p className="modal-description">Pilihan ini mengubah periode contoh pada audit dan ringkasan, bukan mengambil observasi nyata.</p><div className="period-options">{periodOptions.map(option => <button className="button secondary" key={option} onClick={() => { changePeriod(option); setModal(null); }}>{option}{period === option && <Check size={16} />}</button>)}</div></Modal>}
  </div>;
}

function Slider({ label, unit, value, setValue, min, max, step, icon: Icon }) {
  return <label className={`climate-slider ${unit === '%' ? 'rain-slider' : 'temperature-slider'}`}><span><Icon size={15} />{label}<strong>{value > 0 || unit === '°C' ? '+' : ''}{number(value, value % 1 ? 1 : 0)}{unit}</strong></span><input aria-label={label} type="range" min={min} max={max} step={step} value={value} onChange={e => setValue(Number(e.target.value))} /><span className="range-labels"><small>{min > 0 || unit === '°C' ? '+' : ''}{min}{unit}</small><small>+{max}{unit}</small></span></label>;
}

function RiskMetric({ name, explanation, value, color }) {
  return <div className={`risk-metric ${color}`}><div><span>{name}</span><span className="risk-level">{value >= .7 ? 'Tinggi' : 'Sedang'}</span></div><strong>{number(value)}</strong><span className="risk-metric-description">{explanation}</span><div className="risk-meter"><i style={{ width: `${value * 100}%` }} /></div><small>Data Simulasi</small></div>;
}

function Pareto({ selected, onSelect }) {
  return <section className="pareto-panel"><div className="pareto-title"><h3>Perbandingan Pareto</h3><span>SKOR ILUSTRATIF</span></div><div className="pareto-chart"><span className="chart-y-label">Manfaat tanah ↑</span><svg viewBox="0 0 290 138" aria-label="Grafik Pareto ilustratif. B menyeimbangkan skor manfaat tanah dan efisiensi air; bukan hasil optimasi."><g stroke="#293947" strokeWidth="1" strokeDasharray="2 4"><path d="M32 18H270M32 52H270M32 86H270M32 120H270M32 18V120M90 18V120M148 18V120M206 18V120M264 18V120" /></g><path d="M150 40Q185 12 220 31T263 72" stroke="#699c6a" strokeWidth="1" strokeDasharray="4 4" fill="none" />{strategies.map(item => { const x = 32 + item.waterScore * 2.45; const y = 122 - item.soilScore * 1.05; return <g className="pareto-point" key={item.id} role="button" aria-label={`Bandingkan skenario ${item.id}`} tabIndex="0" onClick={() => onSelect(item.id)} onKeyDown={e => { if (e.key === 'Enter') onSelect(item.id); }}><circle cx={x} cy={y} r={selected === item.id ? 13 : 8} fill={item.id === 'B' ? '#a3de72' : item.id === 'C' ? '#62b9c2' : '#9ca7af'} fillOpacity=".12" /><circle cx={x} cy={y} r="4.5" fill={item.id === 'B' ? '#a3de72' : item.id === 'C' ? '#62b9c2' : '#9ca7af'} /><text x={x + 10} y={y - 7} fill="#b3c1c9" fontSize="10">{item.id}</text></g>; })}<g fill="#637886" fontSize="8"><text x="27" y="134">0</text><text x="251" y="134">100</text></g></svg><span className="chart-x-label">Efisiensi air →</span></div><div className="pareto-caption"><span><i />B · keseimbangan contoh</span><span>Skor 0–100, bukan hasil solver</span></div><div className="pareto-objectives"><span>Jeda hama</span>{strategies.map(item => <span key={item.id}>{item.id}<i><b style={{ width: `${item.pestScore}%` }} /></i>{item.pestScore}</span>)}</div></section>;
}

function BlockTitle({ index, icon: Icon, title, subtitle }) {
  return <div className="block-title"><span className="block-icon"><Icon size={21} /></span><div><span className="micro-label">BLOK {index}</span><h2>{title}</h2><p>{subtitle}</p></div><span className="block-index">{index}</span></div>;
}

createRoot(document.getElementById('root')).render(<App />);
