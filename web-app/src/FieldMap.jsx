import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Crosshair, Layers3, MapPin, Minus, Plus, X } from 'lucide-react';
import { cellCondition, number, formatIndicator, indicatorSummaryLabel } from './model';

// Titik tengah Banyumas, Jawa Tengah
const BANYUMAS_CENTER = [-7.45, 109.17];

const colors = {
  safe: '#486c26',
  stress: '#d94b43',
  erosion: '#ffd600',
  unknown: '#8ca393',
};

const conditionLabelsByLang = {
  id: {
    safe: 'Koridor rotasi relatif aman',
    stress: 'PVRS · risiko stres akar',
    erosion: 'BF-EHSI · risiko erosi',
    unknown: 'Indikator tidak ditampilkan',
  },
  en: {
    safe: 'Relatively safe rotation corridor',
    stress: 'PVRS · root stress risk',
    erosion: 'BF-EHSI · erosion risk',
    unknown: 'Indicator not shown',
  },
};

export default function FieldMap({
  activeLayers,
  result,
  resolution,
  setResolution,
  onCell,
  selectedCell,
  showGrid,
  setShowGrid,
  lang = 'id',
}) {
  const conditionLabels = conditionLabelsByLang[lang] || conditionLabelsByLang.id;
  const en = lang === 'en';
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const geojsonLayerRef = useRef(null);

  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  const [hover, setHover] = useState(null);

  // Inisialisasi Peta Leaflet dengan Google Hybrid + OSM
  useEffect(() => {
    if (!mapContainerRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: BANYUMAS_CENTER,
      zoom: 12,
      zoomControl: false, // Kita buat tombol zoom kustom
      attributionControl: true,
    });

    // 1. Google Maps Hybrid (Citra Satelit Beresolusi Tinggi + Label Jalan)
    const googleHybrid = L.tileLayer(
      'https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
      {
        maxZoom: 20,
        subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
        attribution: '&copy; Google Maps',
      }
    );

    // 2. Google Maps Street (Peta jalan standar)
    const googleRoads = L.tileLayer(
      'https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
      {
        maxZoom: 20,
        attribution: '&copy; Google Maps',
      }
    );

    // 3. OpenStreetMap
    const osm = L.tileLayer(
      'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors',
      }
    );

    // Pasang Google Hybrid secara default
    googleHybrid.addTo(map);

    // Tambahkan kontrol basemap di pojok kanan atas
    const baseLayers = {
      'Google Satelit': googleHybrid,
      'Google Roads': googleRoads,
      OpenStreetMap: osm,
    };
    const layerControl = L.control.layers(baseLayers, null, { position: 'topright' }).addTo(map);

    // Load layer petak sawah riil Copernicus Sentinel-2
    fetch('/banyumas_paddy_mask.geojson')
      .then((r) => (r.ok ? r.json() : null))
      .then((geo) => {
        if (!geo || !mapInstanceRef.current) return;
        const paddyLayer = L.geoJSON(geo, {
          style: {
            color: '#10b981',
            weight: 1.2,
            fillColor: '#059669',
            fillOpacity: 0.22,
          },
        });
        paddyLayer.addTo(map);
        layerControl.addOverlay(paddyLayer, '🌾 Sawah Riil (Sentinel-2)');
      })
      .catch(() => {});

    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Fetch data grid sintetis H3
  useEffect(() => {
    const controller = new AbortController();
    fetch('/demo-grid-levels.json', { signal: controller.signal })
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.json();
      })
      .then(setData)
      .catch((e) => {
        if (e.name !== 'AbortError') setError(true);
      });
    return () => controller.abort();
  }, []);

  // Render Poligon H3 ke peta Leaflet
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !data) return;

    // Bersihkan poligon sebelumnya
    if (geojsonLayerRef.current) {
      map.removeLayer(geojsonLayerRef.current);
      geojsonLayerRef.current = null;
    }

    if (!showGrid) return;

    const cells = data.levels[String(resolution)] || [];

    // Konversi ring koordinat [lng, lat] ke GeoJSON Polygon format
    const geojsonData = {
      type: 'FeatureCollection',
      features: cells.map((cell) => ({
        type: 'Feature',
        id: cell.id,
        properties: cell,
        geometry: {
          type: 'Polygon',
          coordinates: [cell.ring],
        },
      })),
    };

    const layer = L.geoJSON(geojsonData, {
      style: (feature) => {
        const condition = cellCondition(feature.properties, activeLayers, result);
        const isSelected = selectedCell?.id === feature.id;
        const isPaddy = feature.properties?.indicators?.paddy_gate_passed !== false;
        return {
          fillColor: isPaddy ? colors[condition] : '#64748b',
          fillOpacity: isSelected ? 0.75 : isPaddy ? 0.32 : 0.08,
          color: isSelected ? '#ffffff' : isPaddy ? colors[condition] : '#94a3b8',
          weight: isSelected ? 2.5 : resolution === 9 ? 0.8 : 1.4,
          dashArray: isSelected ? '' : isPaddy ? '2' : '4',
        };
      },
      onEachFeature: (feature, l) => {
        l.on({
          click: () => {
            setHover(null);
            onCell(feature.properties);
          },
          mouseover: (e) => {
            setHover(feature.properties);
            const target = e.target;
            target.setStyle({
              fillOpacity: 0.65,
              weight: 2.2,
              color: '#ffffff',
            });
            if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) {
              target.bringToFront();
            }
          },
          mouseout: (e) => {
            setHover(null);
            const isSelected = selectedCell?.id === feature.id;
            const condition = cellCondition(feature.properties, activeLayers, result);
            const isPaddy = feature.properties?.indicators?.paddy_gate_passed !== false;
            e.target.setStyle({
              fillColor: isPaddy ? colors[condition] : '#64748b',
              fillOpacity: isSelected ? 0.75 : isPaddy ? 0.32 : 0.08,
              color: isSelected ? '#ffffff' : isPaddy ? colors[condition] : '#94a3b8',
              weight: isSelected ? 2.5 : resolution === 9 ? 0.8 : 1.4,
            });
          },
        });
      },
    });

    layer.addTo(map);
    geojsonLayerRef.current = layer;
  }, [data, resolution, activeLayers, result, selectedCell, showGrid, onCell]);

  // Tombol kontrol navigasi kustom
  const zoomIn = () => mapInstanceRef.current?.zoomIn();
  const zoomOut = () => mapInstanceRef.current?.zoomOut();
  const resetView = () => mapInstanceRef.current?.setView(BANYUMAS_CENTER, 12);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', minHeight: '603px' }}>
      {/* Wadah Peta Asli Leaflet */}
      <div ref={mapContainerRef} style={{ width: '100%', height: '100%', zIndex: 1 }} />

      {/* Indikator Koordinat */}
      <div className="map-coordinate">
        <span className="status-dot" /> {en ? 'BANYUMAS, CENTRAL JAVA' : 'BANYUMAS, JAWA TENGAH'} <span>{en ? '7°27′ S · 109°10′ E' : '7°27′ LS · 109°10′ BT'}</span>
      </div>

      {/* Arah Mata Angin */}
      <div className="map-north">
        <span>↑</span>{en ? 'N' : 'U'}
      </div>

      {/* Tombol Kontrol Peta */}
      <div className="map-tools" style={{ zIndex: 1000 }}>
        <button aria-label={en ? 'Zoom in' : 'Perbesar peta'} onClick={zoomIn}>
          <Plus size={17} />
        </button>
        <button aria-label={en ? 'Zoom out' : 'Perkecil peta'} onClick={zoomOut}>
          <Minus size={17} />
        </button>
        <button aria-label={en ? 'Reset map view' : 'Atur ulang peta'} onClick={resetView}>
          <Crosshair size={17} />
        </button>
        <button
          aria-label={en ? 'Toggle H3 grid' : 'Tampilkan kisi H3'}
          aria-pressed={showGrid}
          onClick={() => setShowGrid(!showGrid)}
          className={showGrid ? 'active' : ''}
        >
          <Layers3 size={17} />
        </button>
      </div>

      {/* Pemilihan Resolusi H3 */}
      <div className="map-resolution" style={{ zIndex: 1000, right: '110px' }}>
        <span>{en ? 'H3 Resolution' : 'Resolusi H3'}</span>
        {[7, 8, 9].map((level) => (
          <button
            key={level}
            aria-pressed={resolution === level}
            className={resolution === level ? 'active' : ''}
            onClick={() => {
              setResolution(level);
              onCell(null);
            }}
          >
            {level}
          </button>
        ))}
      </div>

      {/* Sumber Catatan */}
      <div className="map-source-note" style={{ zIndex: 1000 }}>
        {en ? 'Satellite Imagery & Real Map · Google Maps / OpenStreetMap' : 'Citra Satelit & Peta Nyata · Google Maps / OpenStreetMap'}<br />
        {en ? 'Synthetic H3 Overlay · Banyumas, Central Java · Indicators: NASA GPM/SMAP/HLS/MODIS/SRTM' : 'Hamparan H3 Sintetis · Banyumas, Jawa Tengah · Indikator: NASA GPM/SMAP/HLS/MODIS/SRTM'}
      </div>

      {/* Tooltip Hover Sel */}
      {hover && (
        <div className="hex-tooltip" role="tooltip" style={{ zIndex: 1000 }}>
          <span>{en ? `CELL H3-${resolution} · ${hover.indicators ? 'NASA DATA' : 'SIMULATION DATA'}` : `SEL H3-${resolution} · ${hover.indicators ? 'DATA NASA' : 'DATA SIMULASI'}`}</span>
          <strong>{hover.id}</strong>
          <p>
            <i style={{ background: colors[cellCondition(hover, activeLayers, result)] }} />
            {conditionLabels[cellCondition(hover, activeLayers, result)]}
          </p>
          {hover.indicators?.ndvi != null && (
            <small>NDVI: {hover.indicators.ndvi.toFixed(3)} · {en ? 'Rain' : 'Hujan'}: {hover.indicators.gpm_rain_dekad?.toFixed(1)} mm</small>
          )}
          {!hover.indicators && (
            <small>{en ? 'Click for details · not an independent measurement' : 'Klik untuk rincian · bukan pengukuran independen'}</small>
          )}
        </div>
      )}

      {/* Kartu Rincian Sel yang Diklik */}
      {selectedCell && (
        <div className="cell-detail" style={{ zIndex: 1000 }}>
          <div>
            <span className="micro-label">{en ? `CELL DETAILS · ${selectedCell.indicators ? 'REAL NASA DATA' : 'SIMULATION DATA'}` : `RINCIAN SEL · ${selectedCell.indicators ? 'DATA NASA RIIL' : 'DATA SIMULASI'}`}</span>
            <button aria-label={en ? 'Close cell details' : 'Tutup rincian sel'} onClick={() => onCell(null)}>
              <X size={16} />
            </button>
          </div>
          <h3>
            <MapPin size={15} />
            {selectedCell.id}
          </h3>
          {selectedCell.indicators ? (
            <dl>
              <div>
                <dt>{en ? 'Land Status' : 'Status Lahan'}</dt>
                <dd className={selectedCell.indicators.paddy_gate_passed ? '' : 'orange-text'}>
                  {selectedCell.indicators.paddy_fraction != null
                    ? selectedCell.indicators.paddy_gate_passed
                      ? en
                        ? `✅ Verified Paddy (${(selectedCell.indicators.paddy_fraction * 100).toFixed(1)}% Sentinel-2)`
                        : `✅ Terverifikasi Sawah (${(selectedCell.indicators.paddy_fraction * 100).toFixed(1)}% Sentinel-2)`
                      : en
                      ? '🏙️ Non-Paddy / Settlement (Sentinel-2)'
                      : '🏙️ Non-Sawah / Pemukiman (Sentinel-2)'
                    : selectedCell.indicators.paddy_gate_passed
                    ? en
                      ? '✅ Verified Paddy'
                      : '✅ Terverifikasi Sawah'
                    : en
                    ? '⚠ Unverified'
                    : '⚠ Belum Terverifikasi'}
                </dd>
              </div>
              <div>
                <dt>{en ? 'PVRS Score (Root Stress)' : 'Skor PVRS (Stres Akar)'}</dt>
                <dd><strong>{formatIndicator('pvrs', selectedCell.indicators.pvrs)}</strong></dd>
              </div>
              {selectedCell.indicators.optical_lag > 0 && (
                <div>
                  <dt>Optical Lag</dt>
                  <dd>{selectedCell.indicators.optical_lag} {en ? 'days before leaf symptoms' : 'hari sebelum gejala daun'}</dd>
                </div>
              )}
              <div>
                <dt>{en ? 'Vegetation (NDVI · HLS 30m)' : 'Vegetasi (NDVI · HLS 30m)'}</dt>
                <dd>{formatIndicator('ndvi', selectedCell.indicators.ndvi)}</dd>
              </div>
              <div>
                <dt>{en ? 'Soil Moisture (SMAP ~9km)' : 'Kelembapan Tanah (SMAP ~9km)'}</dt>
                <dd>{formatIndicator('smap_wetness', selectedCell.indicators.smap_wetness)}</dd>
              </div>
              <div>
                <dt>{en ? 'Dekad Rainfall (GPM 0.1°)' : 'Curah Hujan Dekad (GPM 0,1°)'}</dt>
                <dd>{formatIndicator('gpm_rain_dekad', selectedCell.indicators.gpm_rain_dekad)}</dd>
              </div>
              <div>
                <dt>{en ? 'Slope (SRTM 30m)' : 'Kemiringan Lereng (SRTM 30m)'}</dt>
                <dd>{formatIndicator('srtm_slope', selectedCell.indicators.srtm_slope)}</dd>
              </div>
              <div>
                <dt>{en ? 'Temp. Anomaly (MODIS LST)' : 'Anomali Suhu (MODIS LST)'}</dt>
                <dd>{formatIndicator('lst_anomaly', selectedCell.indicators.lst_anomaly)}</dd>
              </div>
              <div>
                <dt>{en ? 'Erosion Alert' : 'Peringatan Erosi'}</dt>
                <dd className={selectedCell.indicators.erosion_alert ? 'orange-text' : ''}>
                  {selectedCell.indicators.erosion_alert ? (en ? '⚠ Detected' : '⚠ Terdeteksi') : (en ? 'Not Detected' : 'Tidak Terdeteksi')}
                </dd>
              </div>
              {selectedCell.indicators.confidence_pct && (
                <div>
                  <dt>{en ? 'Model Confidence' : 'Keyakinan Model'}</dt>
                  <dd>{number(selectedCell.indicators.confidence_pct, 1)}%</dd>
                </div>
              )}
              {selectedCell.indicators.dekad_year && (
                <div>
                  <dt>{en ? 'Data Period' : 'Periode Data'}</dt>
                  <dd>{en ? 'Dekad' : 'Dekad'} {selectedCell.indicators.dekad} · {selectedCell.indicators.dekad_year}</dd>
                </div>
              )}
            </dl>
          ) : (
            <dl>
              <div>
                <dt>{en ? 'Land cover' : 'Tutupan lahan'}</dt>
                <dd>{en ? 'Not Available' : 'Belum Tersedia'}</dd>
              </div>
              <div>
                <dt>{en ? 'Illustrative PVRS' : 'PVRS ilustratif'}</dt>
                <dd>{number(result.pvrs)}</dd>
              </div>
              <div>
                <dt>{en ? 'Illustrative BF-EHSI' : 'BF-EHSI ilustratif'}</dt>
                <dd>{number(result.erosion)}</dd>
              </div>
              <div>
                <dt>{en ? 'Illustrative water balance' : 'Neraca air ilustratif'}</dt>
                <dd>{result.water} mm</dd>
              </div>
              <div>
                <dt>{en ? 'Verification status' : 'Status verifikasi'}</dt>
                <dd className="orange-text">{en ? 'Unverified' : 'Belum Diverifikasi'}</dd>
              </div>
            </dl>
          )}
          <p>
            {selectedCell.indicators
              ? en
                ? 'Source: NASA GPM/SMAP/HLS/MODIS/SRTM. Native SMAP ~9 km; GPM 0.1° — not independent observations per cell.'
                : 'Sumber: NASA GPM/SMAP/HLS/MODIS/SRTM. SMAP asli ~9 km; GPM 0,1° — bukan observasi independen per sel.'
              : en
              ? 'Shared scenario values on real map. Native SMAP ~9 km; GPM 0.1°.'
              : 'Nilai skenario bersama di peta riil. SMAP asli ~9 km; GPM 0,1°.'}
          </p>
        </div>
      )}

      {error && (
        <div className="map-load-status" role="alert" style={{ zIndex: 1000 }}>
          {en ? 'Failed to load geometry. Reload page to try again.' : 'Geometri gagal dimuat. Muat ulang halaman untuk mencoba kembali.'}
        </div>
      )}
      {!data && !error && (
        <div className="map-load-status" role="status" style={{ zIndex: 1000 }}>
          {en ? 'Loading map imagery & NASA satellite data…' : 'Memuat citra peta & data satelit NASA…'}
        </div>
      )}
    </div>
  );
}
