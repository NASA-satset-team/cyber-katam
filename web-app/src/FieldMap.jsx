import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Crosshair, Layers3, MapPin, Minus, Plus, Sprout, X } from 'lucide-react';
import { cellCondition, number, formatIndicator, indicatorSummaryLabel } from './model';

// Titik tengah Banyumas, Jawa Tengah
const BANYUMAS_CENTER = [-7.45, 109.17];

const colors = {
  safe: '#486c26',
  stress: '#d94b43',
  erosion: '#ffd600',
  unknown: '#8ca393',
};

function forecastRainColor(rain) {
  if (rain == null) return colors.unknown;
  const t = Math.max(0, Math.min(1, rain / 50));
  return `rgb(${Math.round(186 - 179 * t)}, ${Math.round(230 - 141 * t)}, ${Math.round(253 - 120 * t)})`;
}

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
  forecastDate,
  lang = 'id',
}) {
  const conditionLabels = conditionLabelsByLang[lang] || conditionLabelsByLang.id;
  const en = lang === 'en';
  const cellProvenance = selectedCell?.indicators?.indicator_provenance;
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const geojsonLayerRef = useRef(null);
  const paddyLayerRef = useRef(null);

  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  const [hover, setHover] = useState(null);
  const [showPaddy, setShowPaddy] = useState(true);
  const [forecastRequest, setForecastRequest] = useState(null);
  const forecastMode = Boolean(forecastDate);
  const currentForecastRequest = forecastRequest?.date === forecastDate && forecastRequest?.resolution === resolution
    ? forecastRequest
    : null;
  const forecast = currentForecastRequest?.data;
  const forecastError = currentForecastRequest?.error;
  const selectedForecast = forecast?.cells[selectedCell?.id];
  const forecastValue = (value) => value == null ? '—' : value.toLocaleString(en ? 'en-GB' : 'id-ID', {
    minimumFractionDigits: 1, maximumFractionDigits: 1,
  });

  useEffect(() => {
    setHover(null);
    if (!forecastDate) return;
    const controller = new AbortController();
    setForecastRequest(null);
    fetch(`/api/forecast/map?date=${forecastDate}&resolution=${resolution}`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) {
          const body = await response.json();
          throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${response.status}`);
        }
        return response.json();
      })
      .then((payload) => {
        if (!controller.signal.aborted) {
          setForecastRequest({ date: forecastDate, resolution, data: payload });
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) {
          setForecastRequest({ date: forecastDate, resolution, error: e.message });
        }
      });
    return () => controller.abort();
  }, [forecastDate, resolution]);

  // Inisialisasi Peta Leaflet dengan Google Hybrid (Satelit)
  useEffect(() => {
    if (!mapContainerRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: BANYUMAS_CENTER,
      zoom: 12,
      zoomControl: false, // Kita buat tombol zoom kustom
      attributionControl: true,
    });

    // Google Maps Hybrid (Citra Satelit Beresolusi Tinggi + Label Jalan)
    const googleHybrid = L.tileLayer(
      'https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
      {
        maxZoom: 20,
        subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
        attribution: '&copy; Google Maps',
      }
    );

    googleHybrid.addTo(map);

    // Load layer ROI sawah ESA WorldCover cropland_frac >= 0.9
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
        paddyLayerRef.current = paddyLayer;
        paddyLayer.addTo(map);
      })
      .catch(() => {});

    mapInstanceRef.current = map;
    const timer = setTimeout(() => map.invalidateSize(), 150);
    const onResize = () => map.invalidateSize();
    window.addEventListener('resize', onResize);

    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', onResize);
      map.remove();
      mapInstanceRef.current = null;
      paddyLayerRef.current = null;
    };
  }, []);

  // Toggle visibilitas layer ROI sawah
  useEffect(() => {
    const map = mapInstanceRef.current;
    const paddyLayer = paddyLayerRef.current;
    if (!map || !paddyLayer) return;
    if (showPaddy) {
      if (!map.hasLayer(paddyLayer)) paddyLayer.addTo(map);
    } else if (map.hasLayer(paddyLayer)) {
      map.removeLayer(paddyLayer);
    }
  }, [showPaddy]);

  // Fetch data grid sintetis H3
  useEffect(() => {
    const controller = new AbortController();
    fetch('/demo-grid-levels.json?v=' + Date.now(), { signal: controller.signal })
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

    if (!showGrid || (forecastMode && !forecast)) return;

    const cells = (data.levels[String(resolution)] || []).map((cell) => forecastMode
      ? { id: cell.id, ring: cell.ring, forecast: forecast.cells[cell.id] }
      : cell);

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

    const cellStyle = (feature) => {
      const isSelected = selectedCell?.id === feature.id;
      if (forecastMode) {
        const color = forecastRainColor(feature.properties.forecast?.fc_precip_total_mm);
        return {
          fillColor: color,
          fillOpacity: isSelected ? 0.75 : 0.5,
          color: isSelected ? '#ffffff' : color,
          weight: isSelected ? 2.5 : resolution === 9 ? 0.8 : 1.4,
          dashArray: '',
        };
      }
      const condition = cellCondition(feature.properties, activeLayers, result);
      const isPaddy = feature.properties?.indicators?.paddy_gate_passed !== false;
      return {
        fillColor: isPaddy ? colors[condition] : '#64748b',
        fillOpacity: isSelected ? 0.75 : isPaddy ? 0.32 : 0.08,
        color: isSelected ? '#ffffff' : isPaddy ? colors[condition] : '#94a3b8',
        weight: isSelected ? 2.5 : resolution === 9 ? 0.8 : 1.4,
        dashArray: isSelected ? '' : isPaddy ? '2' : '4',
      };
    };

    const layer = L.geoJSON(geojsonData, {
      style: cellStyle,
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
            e.target.setStyle(cellStyle(feature));
          },
        });
      },
    });

    layer.addTo(map);
    geojsonLayerRef.current = layer;
  }, [data, resolution, activeLayers, result, selectedCell, showGrid, onCell, forecastMode, forecast]);

  // Tombol kontrol navigasi kustom
  const zoomIn = () => mapInstanceRef.current?.zoomIn();
  const zoomOut = () => mapInstanceRef.current?.zoomOut();
  const resetView = () => mapInstanceRef.current?.setView(BANYUMAS_CENTER, 12);

  return (
    <div className="field-map-root">
      {/* Wadah Peta Asli Leaflet */}
      <div ref={mapContainerRef} className="leaflet-canvas-box" />

      {/* Pemilihan Resolusi H3 */}
      <div className="map-resolution" style={{ zIndex: 1000 }}>
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

      {/* Gugus Kontrol Peta (Kompas 3D, ROI Sawah, Zoom In/Out, Reset, Kisi H3) di atas kanan Lapisan Data Satelit */}
      <div className="map-controls-dock" style={{ zIndex: 1000 }}>
        {/* Kompas 3D */}
        <button
          type="button"
          className="map-compass-btn"
          aria-label={en ? 'North compass (Reset orientation)' : 'Kompas Utara (Atur ulang arah peta)'}
          title={en ? 'North (Reset view)' : 'Arah Utara (Atur ulang peta)'}
          onClick={resetView}
        >
          <svg viewBox="0 0 40 40" width="26" height="26" className="compass-3d-svg" aria-hidden="true">
            <defs>
              <linearGradient id="bezel3d" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#ffffff" />
                <stop offset="45%" stopColor="#cbd5e1" />
                <stop offset="100%" stopColor="#475569" />
              </linearGradient>
              <radialGradient id="dial3d" cx="35%" cy="30%" r="70%">
                <stop offset="0%" stopColor="#1e293b" />
                <stop offset="100%" stopColor="#090d16" />
              </radialGradient>
              <filter id="needleShadow" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="1.2" stdDeviation="1" floodColor="#000000" floodOpacity="0.55" />
              </filter>
            </defs>
            {/* Lingkaran Bezel 3D Luar */}
            <circle cx="20" cy="20" r="18" fill="url(#bezel3d)" stroke="#334155" strokeWidth="0.8" />
            <circle cx="20" cy="20" r="15.2" fill="url(#dial3d)" stroke="#94a3b8" strokeWidth="0.6" />
            {/* Garis Derajat Kompas */}
            <line x1="20" y1="5.5" x2="20" y2="8" stroke="#f8fafc" strokeWidth="1.2" />
            <line x1="20" y1="32" x2="20" y2="34.5" stroke="#94a3b8" strokeWidth="1" />
            <line x1="5.5" y1="20" x2="8" y2="20" stroke="#94a3b8" strokeWidth="1" />
            <line x1="32" y1="20" x2="34.5" y2="20" stroke="#94a3b8" strokeWidth="1" />
            {/* Bintang Sekunder 3D */}
            <polygon points="20,13 24.5,15.5 27,20 24.5,24.5 20,27 15.5,24.5 13,20 15.5,15.5" fill="#d97706" opacity="0.65" />
            {/* Jarum Barat & Timur 3D */}
            <polygon points="8.5,20 20,17.2 20,20" fill="#e2e8f0" />
            <polygon points="8.5,20 20,22.8 20,20" fill="#64748b" />
            <polygon points="31.5,20 20,17.2 20,20" fill="#cbd5e1" />
            <polygon points="31.5,20 20,22.8 20,20" fill="#475569" />
            {/* Jarum Kompas 3D (Utara Merah Berfaset & Selatan Perak Berfaset) */}
            <g filter="url(#needleShadow)">
              {/* Utara - Faset Kiri Terang */}
              <polygon points="20,6.2 15.8,20 20,20" fill="#ff5252" />
              {/* Utara - Faset Kanan Gelap */}
              <polygon points="20,6.2 24.2,20 20,20" fill="#b91c1c" />
              {/* Selatan - Faset Kiri Terang */}
              <polygon points="20,33.8 15.8,20 20,20" fill="#f8fafc" />
              {/* Selatan - Faset Kanan Gelap */}
              <polygon points="20,33.8 24.2,20 20,20" fill="#64748b" />
            </g>
            {/* Poros Tengah Emas 3D */}
            <circle cx="20" cy="20" r="2.6" fill="#facc15" stroke="#713f12" strokeWidth="0.7" />
            <circle cx="19.3" cy="19.3" r="0.9" fill="#fef9c3" />
          </svg>
          <span className="compass-badge">{en ? 'N' : 'U'}</span>
        </button>

        {/* Tombol Mandiri ROI Sawah (WorldCover >= 90%) - Ikon Padi */}
        <button
          type="button"
          className={`paddy-toggle-btn ${showPaddy ? 'active' : ''}`}
          aria-label={en ? 'Toggle Paddy ROI Layer (WorldCover >= 90%)' : 'Tampilkan ROI Sawah (WorldCover >= 90%)'}
          title={en ? 'Paddy ROI (WorldCover >= 90%)' : 'ROI Sawah (WorldCover >= 90%)'}
          aria-pressed={showPaddy}
          onClick={() => setShowPaddy((prev) => !prev)}
        >
          <Sprout size={17} />
        </button>

        {/* Tombol Kontrol Peta (Zoom In, Zoom Out, Reset, Kisi H3) */}
        <div className="map-tools">
          <button aria-label={en ? 'Zoom in' : 'Perbesar peta'} title={en ? 'Zoom in' : 'Perbesar peta'} onClick={zoomIn}>
            <Plus size={17} />
          </button>
          <button aria-label={en ? 'Zoom out' : 'Perkecil peta'} title={en ? 'Zoom out' : 'Perkecil peta'} onClick={zoomOut}>
            <Minus size={17} />
          </button>
          <button aria-label={en ? 'Reset map view' : 'Atur ulang peta'} title={en ? 'Reset map view' : 'Atur ulang peta'} onClick={resetView}>
            <Crosshair size={17} />
          </button>
          <button
            aria-label={en ? 'Toggle H3 grid' : 'Tampilkan kisi H3'}
            title={en ? 'Toggle H3 grid' : 'Tampilkan kisi H3'}
            aria-pressed={showGrid}
            onClick={() => setShowGrid(!showGrid)}
            className={showGrid ? 'active' : ''}
          >
            <Layers3 size={17} />
          </button>
        </div>
      </div>

      {forecastMode && (
        <div className="forecast-map-legend">
          <strong>{en ? 'Predicted rainfall' : 'Prediksi hujan'} · {forecast?.horizon_code || forecastDate}</strong>
          <span className="forecast-rain-scale" aria-hidden="true" />
          <span className="forecast-rain-range"><span>0</span><span>{en ? '50+ mm/day' : '50+ mm/hari'}</span></span>
          <small>{en ? 'Model output from weather API + formula' : 'Hasil model dari API cuaca + rumus'}</small>
        </div>
      )}

      {/* Sumber Catatan */}
      <div className="map-source-note" style={{ zIndex: 1000 }}>
        {en ? 'Satellite Imagery & Real Map · Google Maps / OpenStreetMap' : 'Citra Satelit & Peta Nyata · Google Maps / OpenStreetMap'}<br />
        {forecastMode
          ? en
            ? `Meteomatics-based prediction · ${forecastDate} · PSF interpolation, not per-cell observations`
            : `Prediksi berbasis Meteomatics · ${forecastDate} · interpolasi PSF, bukan observasi per sel`
          : en ? 'Synthetic H3 Overlay · Banyumas, Central Java · Indicators: NASA GPM/SMAP/HLS/MODIS/SRTM' : 'Hamparan H3 Sintetis · Banyumas, Jawa Tengah · Indikator: NASA GPM/SMAP/HLS/MODIS/SRTM'}
      </div>

      {/* Tooltip Hover Sel */}
      {hover && forecastMode && (
        <div className="hex-tooltip" role="tooltip" style={{ zIndex: 1000 }}>
          <span>{en ? 'MODEL PREDICTION' : 'PREDIKSI MODEL'} · {forecast?.horizon_code} · H3-{resolution}</span>
          <strong>{hover.id}</strong>
          <p>{en ? 'Rain' : 'Hujan'}: {forecastValue(hover.forecast?.fc_precip_total_mm)} {en ? 'mm/day' : 'mm/hari'}</p>
          <small>{en ? 'Max. temperature' : 'Suhu maks.'}: {forecastValue(hover.forecast?.fc_tmax_c)} °C</small>
          <small>{en ? 'PSF interpolation · click for details' : 'Interpolasi PSF · klik untuk rincian'}</small>
        </div>
      )}
      {hover && !forecastMode && (
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

      {selectedCell && forecastMode && forecast && (
        <div className="cell-detail" style={{ zIndex: 1000 }}>
          <div>
            <span className="micro-label">{en ? 'MODEL PREDICTION' : 'PREDIKSI MODEL'} · {forecast.horizon_code}</span>
            <button aria-label={en ? 'Close cell details' : 'Tutup rincian sel'} onClick={() => onCell(null)}>
              <X size={16} />
            </button>
          </div>
          <h3><MapPin size={15} />{selectedCell.id}</h3>
          <dl>
            <div><dt>{en ? 'Date (WIB)' : 'Tanggal (WIB)'}</dt><dd>{forecastDate}</dd></div>
            <div><dt>{en ? 'Daily rainfall' : 'Curah hujan harian'}</dt><dd>{forecastValue(selectedForecast?.fc_precip_total_mm)} mm</dd></div>
            <div><dt>{en ? 'Peak hourly rain' : 'Puncak hujan per jam'}</dt><dd>{forecastValue(selectedForecast?.fc_precip_max_1h_mm)} {en ? 'mm/h' : 'mm/jam'}</dd></div>
            <div><dt>{en ? 'Mean temperature' : 'Suhu rata-rata'}</dt><dd>{forecastValue(selectedForecast?.fc_tmean_c)} °C</dd></div>
            <div><dt>{en ? 'Max. temperature' : 'Suhu maksimum'}</dt><dd>{forecastValue(selectedForecast?.fc_tmax_c)} °C</dd></div>
            <div><dt>{en ? 'Max. wind speed' : 'Kecepatan angin maks.'}</dt><dd>{forecastValue(selectedForecast?.fc_wind_max_ms)} m/s</dd></div>
          </dl>
          <p>
            {en ? 'Prediction derived from Meteomatics API data via formula (daily aggregation, ETo/SMI). ' : 'Prediksi turunan data API Meteomatics melalui rumus (agregasi harian, ETo/SMI). '}
            {resolution !== 9 && (en
              ? `All values are means over ${selectedForecast?.n_children ?? 0} res-9 child cells. `
              : `Semua nilai merupakan rata-rata ${selectedForecast?.n_children ?? 0} sel anak res-9. `)}
            {en ? 'PSF interpolation, not per-cell observations.' : 'Interpolasi PSF, bukan observasi per sel.'}
          </p>
        </div>
      )}

      {/* Kartu Rincian Sel yang Diklik */}
      {selectedCell && !forecastMode && (
        <div className="cell-detail" style={{ zIndex: 1000 }}>
          <div>
            <span className="micro-label">{en ? `CELL DETAILS · ${selectedCell.indicators ? (cellProvenance === 'NEAREST_NEIGHBOR' ? 'NASA DATA · SPATIAL INTERPOLATION' : 'REAL NASA DATA') : 'SIMULATION DATA'}` : `RINCIAN SEL · ${selectedCell.indicators ? (cellProvenance === 'NEAREST_NEIGHBOR' ? 'DATA NASA · INTERPOLASI SPASIAL' : 'DATA NASA RIIL') : 'DATA SIMULASI'}`}</span>
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
                      ? `🏙️ Non-Paddy / Settlement (${(selectedCell.indicators.paddy_fraction * 100).toFixed(1)}% Sentinel-2)`
                      : `🏙️ Non-Sawah / Pemukiman (${(selectedCell.indicators.paddy_fraction * 100).toFixed(1)}% Sentinel-2)`
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
                <dt>{en ? 'Indicator Provenance' : 'Provenance Indikator'}</dt>
                <dd>
                  {selectedCell.indicators.indicator_provenance === 'NEAREST_NEIGHBOR'
                    ? en
                      ? 'Nearest-neighbor estimate from observed cell'
                      : 'Estimasi tetangga terdekat dari sel terobservasi'
                    : en
                      ? 'NASA observation of this cell'
                      : 'Observasi NASA sel ini'}
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
                <dt>{en ? 'Rootzone Moisture (SMAP)' : 'Kelembapan Zona Akar (SMAP)'}</dt>
                <dd>{formatIndicator('smap_wetness', selectedCell.indicators.smap_wetness)}</dd>
              </div>
              {selectedCell.indicators.smap_surface != null && (
                <div>
                  <dt>{en ? 'Surface Moisture (SMAP)' : 'Kelembapan Permukaan (SMAP)'}</dt>
                  <dd>{(selectedCell.indicators.smap_surface * 100).toFixed(1)}% vol.</dd>
                </div>
              )}
              <div>
                <dt>{en ? 'Dekad Rainfall (GPM 0.1°)' : 'Curah Hujan Dekad (GPM 0,1°)'}</dt>
                <dd>{formatIndicator('gpm_rain_dekad', selectedCell.indicators.gpm_rain_dekad)}</dd>
              </div>
              {selectedCell.indicators.gpm_max_mmhr != null && (
                <div>
                  <dt>{en ? 'Peak Rainfall Rate (GPM)' : 'Intensitas Puncak (GPM)'}</dt>
                  <dd>{selectedCell.indicators.gpm_max_mmhr} mm/jam</dd>
                </div>
              )}
              <div>
                <dt>{en ? 'Slope (SRTM 30m)' : 'Kemiringan Lereng (SRTM 30m)'}</dt>
                <dd>{formatIndicator('srtm_slope', selectedCell.indicators.srtm_slope)}</dd>
              </div>
              {selectedCell.indicators.srtm_elev_m != null && (
                <div>
                  <dt>{en ? 'Elevation (SRTM 30m)' : 'Elevasi (SRTM 30m)'}</dt>
                  <dd>{selectedCell.indicators.srtm_elev_m} m dpl</dd>
                </div>
              )}
              <div>
                <dt>{en ? 'Temp. Anomaly (MODIS LST)' : 'Anomali Suhu (MODIS LST)'}</dt>
                <dd>{formatIndicator('lst_anomaly', selectedCell.indicators.lst_anomaly)}</dd>
              </div>
              {selectedCell.indicators.power_t2m != null && (
                <div>
                  <dt>{en ? 'Air Temp (NASA POWER)' : 'Suhu Udara (NASA POWER)'}</dt>
                  <dd>{selectedCell.indicators.power_t2m} °C</dd>
                </div>
              )}
              {selectedCell.indicators.power_rh2m != null && (
                <div>
                  <dt>{en ? 'Humidity (NASA POWER)' : 'Kelembapan (NASA POWER)'}</dt>
                  <dd>{selectedCell.indicators.power_rh2m} %</dd>
                </div>
              )}
              {selectedCell.indicators.power_vpd != null && (
                <div>
                  <dt>{en ? 'Vapor Pressure Deficit' : 'Defisit Uap Air (VPD)'}</dt>
                  <dd>{selectedCell.indicators.power_vpd} kPa</dd>
                </div>
              )}
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

      {data && !error && forecastMode && (
        forecastError ? (
          <div className="map-load-status" role="alert" style={{ zIndex: 1000 }}>
            {en ? 'Prediction unavailable: ' : 'Prediksi tidak tersedia: '}{forecastError}
          </div>
        ) : !forecast && (
          <div className="map-load-status" role="status" style={{ zIndex: 1000 }}>
            {en ? `Loading prediction for ${forecastDate}…` : `Memuat prediksi ${forecastDate}…`}
          </div>
        )
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
