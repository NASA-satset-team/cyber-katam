import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Crosshair, Layers3, MapPin, Minus, Plus, X } from 'lucide-react';
import { cellCondition, number } from './model';

// Titik tengah Banyumas, Jawa Tengah
const BANYUMAS_CENTER = [-7.45, 109.17];

const colors = {
  safe: '#486c26',
  stress: '#d94b43',
  erosion: '#ffd600',
  unknown: '#8ca393',
};

const conditionLabels = {
  safe: 'Koridor rotasi relatif aman',
  stress: 'PVRS · risiko stres akar',
  erosion: 'BF-EHSI · risiko erosi',
  unknown: 'Indikator tidak ditampilkan',
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
}) {
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
    L.control
      .layers(
        {
          'Google Satelit': googleHybrid,
          'Google Roads': googleRoads,
          OpenStreetMap: osm,
        },
        null,
        { position: 'topright' }
      )
      .addTo(map);

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
        properties: { id: cell.id },
        geometry: {
          type: 'Polygon',
          coordinates: [cell.ring],
        },
      })),
    };

    const layer = L.geoJSON(geojsonData, {
      style: (feature) => {
        const condition = cellCondition(feature.id, activeLayers, result);
        const isSelected = selectedCell?.id === feature.id;
        return {
          fillColor: colors[condition],
          fillOpacity: isSelected ? 0.75 : 0.28,
          color: isSelected ? '#ffffff' : colors[condition],
          weight: isSelected ? 2.5 : resolution === 9 ? 0.8 : 1.4,
          dashArray: isSelected ? '' : '2',
        };
      },
      onEachFeature: (feature, l) => {
        l.on({
          click: () => {
            setHover(null);
            onCell({ id: feature.id });
          },
          mouseover: (e) => {
            setHover({ id: feature.id });
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
            const condition = cellCondition(feature.id, activeLayers, result);
            e.target.setStyle({
              fillColor: colors[condition],
              fillOpacity: isSelected ? 0.75 : 0.28,
              color: isSelected ? '#ffffff' : colors[condition],
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
        <span className="status-dot" /> BANYUMAS, JAWA TENGAH <span>7°27′ LS · 109°10′ BT</span>
      </div>

      {/* Arah Mata Angin */}
      <div className="map-north">
        <span>↑</span>U
      </div>

      {/* Tombol Kontrol Peta */}
      <div className="map-tools" style={{ zIndex: 1000 }}>
        <button aria-label="Perbesar peta" onClick={zoomIn}>
          <Plus size={17} />
        </button>
        <button aria-label="Perkecil peta" onClick={zoomOut}>
          <Minus size={17} />
        </button>
        <button aria-label="Atur ulang peta" onClick={resetView}>
          <Crosshair size={17} />
        </button>
        <button
          aria-label="Tampilkan kisi H3"
          aria-pressed={showGrid}
          onClick={() => setShowGrid(!showGrid)}
          className={showGrid ? 'active' : ''}
        >
          <Layers3 size={17} />
        </button>
      </div>

      {/* Pemilihan Resolusi H3 */}
      <div className="map-resolution" style={{ zIndex: 1000, right: '110px' }}>
        <span>Resolusi H3</span>
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
        Citra Satelit & Peta Nyata · Google Maps / OpenStreetMap<br />
        Hamparan H3 Sintetis · Banyumas, Jawa Tengah
      </div>

      {/* Tooltip Hover Sel */}
      {hover && (
        <div className="hex-tooltip" role="tooltip" style={{ zIndex: 1000 }}>
          <span>SEL H3-{resolution} · DATA SIMULASI</span>
          <strong>{hover.id}</strong>
          <p>
            <i style={{ background: colors[cellCondition(hover.id, activeLayers, result)] }} />
            {conditionLabels[cellCondition(hover.id, activeLayers, result)]}
          </p>
          <small>Klik untuk rincian · bukan pengukuran independen</small>
        </div>
      )}

      {/* Kartu Rincian Sel yang Diklik */}
      {selectedCell && (
        <div className="cell-detail" style={{ zIndex: 1000 }}>
          <div>
            <span className="micro-label">RINCIAN SEL · DATA SIMULASI</span>
            <button aria-label="Tutup rincian sel" onClick={() => onCell(null)}>
              <X size={16} />
            </button>
          </div>
          <h3>
            <MapPin size={15} />
            {selectedCell.id}
          </h3>
          <dl>
            <div>
              <dt>Tutupan lahan</dt>
              <dd>Belum Tersedia</dd>
            </div>
            <div>
              <dt>PVRS ilustratif</dt>
              <dd>{number(result.pvrs)}</dd>
            </div>
            <div>
              <dt>BF-EHSI ilustratif</dt>
              <dd>{number(result.erosion)}</dd>
            </div>
            <div>
              <dt>Neraca air ilustratif</dt>
              <dd>{result.water} mm</dd>
            </div>
            <div>
              <dt>Status verifikasi</dt>
              <dd className="orange-text">Belum Diverifikasi</dd>
            </div>
          </dl>
          <p>Nilai skenario bersama di peta riil. SMAP asli ~9 km; GPM 0,1°.</p>
        </div>
      )}

      {error && (
        <div className="map-load-status" role="alert" style={{ zIndex: 1000 }}>
          Geometri gagal dimuat. Muat ulang halaman untuk mencoba kembali.
        </div>
      )}
      {!data && !error && (
        <div className="map-load-status" role="status" style={{ zIndex: 1000 }}>
          Memuat citra peta & geometri…
        </div>
      )}
    </div>
  );
}
