import { useEffect, useMemo, useRef, useState } from 'react';
import { Crosshair, Layers3, MapPin, Minus, Plus, X } from 'lucide-react';
import { cellCondition, number } from './model';

const colors = { safe: '#6fdc6a', stress: '#f4716c', erosion: '#eda65b', unknown: '#83968f' };
const conditionLabels = { safe: 'Koridor rotasi relatif aman', stress: 'PVRS · risiko stres akar', erosion: 'BF-EHSI · risiko erosi', unknown: 'Indikator tidak ditampilkan' };

export default function FieldMap({ activeLayers, result, resolution, setResolution, onCell, selectedCell, showGrid, setShowGrid }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [hover, setHover] = useState(null);
  const drag = useRef(null);
  useEffect(() => {
    const controller = new AbortController();
    fetch('/demo-grid-levels.json', { signal: controller.signal })
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(setData).catch(e => { if (e.name !== 'AbortError') setError(true); });
    return () => controller.abort();
  }, []);
  const cells = data?.levels[String(resolution)] || [];
  const polygons = useMemo(() => cells.map(cell => ({
    ...cell,
    points: cell.ring.map(([lng, lat]) => `${480 + (lng - 109.17) * 4300},${315 - (lat + 7.45) * 4300}`).join(' '),
  })), [cells]);
  const select = cell => { setHover(null); onCell(cell); };
  return <div className={`geo-canvas ${activeLayers.includes('hls') ? 'vegetation-layer' : ''} ${activeLayers.includes('srtm') ? 'terrain-layer' : ''}`}>
    <div className="aerial-background" />
    <svg className="geospatial-svg" viewBox="0 0 960 650" aria-label={`Peta skematik Banyumas, H3 resolusi ${resolution}; seluruh warna adalah Data Simulasi`} onPointerDown={e => { if (e.target.tagName !== 'polygon') { drag.current = { x: e.clientX - pan.x, y: e.clientY - pan.y }; e.currentTarget.setPointerCapture(e.pointerId); } }} onPointerMove={e => { if (drag.current) setPan({ x: e.clientX - drag.current.x, y: e.clientY - drag.current.y }); }} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
      <defs><pattern id="cartographic-grid" width="80" height="80" patternUnits="userSpaceOnUse"><path d="M 80 0 L 0 0 0 80" fill="none" stroke="#bdd6c2" strokeOpacity=".09" strokeWidth=".6" /></pattern></defs>
      <rect width="960" height="650" fill="url(#cartographic-grid)" />
      <g className="schematic-context" transform={`translate(${pan.x} ${pan.y}) translate(480 325) scale(${zoom}) translate(-480 -325)`}>
        <g fill="none" stroke="#9bbab0" strokeOpacity=".15" strokeWidth="1">
          <path d="M-60 100Q230 30 310 150T700 180T1000 70M-50 120Q220 50 300 170T690 200T980 90M-30 140Q210 70 290 190T680 220T960 110M-20 160Q200 90 280 210T670 240T950 130" />
          <path d="M30 620Q180 360 450 460T950 350M40 640Q190 380 460 480T960 370M50 660Q200 400 470 500T970 390" />
        </g>
        <path className="river-outline" d="M-10 440 C150 350 180 495 360 450 S550 430 600 505 S820 510 1000 450" />
        <path className="river-path" d="M-10 440 C150 350 180 495 360 450 S550 430 600 505 S820 510 1000 450" />
        <g stroke="#d5ceb7" strokeOpacity=".34" fill="none"><path d="M90 80L180 250L430 280L750 230L970 180M180 250L140 510M430 280L500 540M750 230L850 520" strokeWidth="2" /><path d="M30 370L290 330L560 350L910 300" strokeDasharray="4 5" /></g>
        <g className="map-place"><text x="103" y="211">AJIBARANG</text><text x="545" y="223">PURWOKERTO</text><text x="744" y="420">SOKARAJA</text><text x="530" y="583">BANYUMAS</text><text x="177" y="558">WANGON</text><text x="640" y="502" className="river-label">Sungai Serayu · skematik</text></g>
        <g className="hexagons" style={{ opacity: showGrid ? 1 : 0, pointerEvents: showGrid ? 'auto' : 'none' }}>{polygons.map(cell => {
          const condition = cellCondition(cell.id, activeLayers, result);
          const selected = selectedCell?.id === cell.id;
          return <polygon key={cell.id} points={cell.points} fill={colors[condition]} fillOpacity={selected ? .8 : .24} stroke={selected ? '#f5ffd8' : colors[condition]} strokeOpacity={selected ? 1 : .8} strokeWidth={selected ? 2.3 : resolution === 9 ? .65 : 1.2} role="button" tabIndex={showGrid ? 0 : -1} aria-label={`Pilih sel ${cell.id}`} onFocus={() => setHover(cell)} onBlur={() => setHover(null)} onMouseEnter={() => setHover(cell)} onMouseLeave={() => setHover(null)} onClick={() => select(cell)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(cell); } }} />;
        })}</g>
      </g>
    </svg>
    <div className="map-coordinate"><span className="status-dot" /> BANYUMAS, JAWA TENGAH <span>7°27′ LS · 109°10′ BT</span></div>
    <div className="map-north"><span>↑</span>U</div>
    <div className="map-tools">
      <button aria-label="Perbesar peta" disabled={zoom >= 2.2} onClick={() => setZoom(z => Math.min(2.2, z + .2))}><Plus size={17} /></button>
      <button aria-label="Perkecil peta" disabled={zoom <= .6} onClick={() => setZoom(z => Math.max(.6, z - .2))}><Minus size={17} /></button>
      <button aria-label="Atur ulang peta" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}><Crosshair size={17} /></button>
      <button aria-label="Tampilkan kisi H3" aria-pressed={showGrid} onClick={() => setShowGrid(!showGrid)} className={showGrid ? 'active' : ''}><Layers3 size={17} /></button>
    </div>
    <div className="map-resolution"><span>Resolusi H3</span>{[7, 8, 9].map(level => <button key={level} aria-pressed={resolution === level} className={resolution === level ? 'active' : ''} onClick={() => { setResolution(level); onCell(null); }}>{level}</button>)}</div>
    <div className="map-source-note">Foto & batas petak ilustratif · Bukan citra NASA atau peta persil<br />Foto: Iswanto Arif / Unsplash · Geometri H3 sintetis valid</div>
    {hover && <div className="hex-tooltip" role="tooltip"><span>SEL H3-{resolution} · DATA SIMULASI</span><strong>{hover.id}</strong><p><i style={{ background: colors[cellCondition(hover.id, activeLayers, result)] }} />{conditionLabels[cellCondition(hover.id, activeLayers, result)]}</p><small>Klik untuk rincian · bukan pengukuran independen</small></div>}
    {selectedCell && <div className="cell-detail"><div><span className="micro-label">RINCIAN SEL · DATA SIMULASI</span><button aria-label="Tutup rincian sel" onClick={() => onCell(null)}><X size={16} /></button></div><h3><MapPin size={15} />{selectedCell.id}</h3><dl><div><dt>Tutupan lahan</dt><dd>Belum Tersedia</dd></div><div><dt>PVRS ilustratif</dt><dd>{number(result.pvrs)}</dd></div><div><dt>BF-EHSI ilustratif</dt><dd>{number(result.erosion)}</dd></div><div><dt>Neraca air ilustratif</dt><dd>{result.water} mm</dd></div><div><dt>Status verifikasi</dt><dd className="orange-text">Belum Diverifikasi</dd></div></dl><p>Nilai skenario bersama, bukan observasi spesifik sel. SMAP asli ~9 km; GPM 0,1°.</p></div>}
    {error && <div className="map-load-status" role="alert">Geometri gagal dimuat. Muat ulang halaman untuk mencoba kembali.</div>}
    {!data && !error && <div className="map-load-status" role="status">Memuat geometri sintetis…</div>}
  </div>;
}
