import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

const WEATHER_PARAMS = 't_2m:C,relative_humidity_2m:p,precip_1h:mm';

function meteomaticsProxy() {
  return {
    name: 'meteomatics-live-proxy',
    configureServer(server) {
      server.middlewares.use('/api/weather', async (req, res) => {
        const send = (code, obj) => {
          res.statusCode = code;
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify(obj));
        };
        if (req.method !== 'GET') return send(405, { error: 'method not allowed' });
        try {
          const q = new URL(req.url, 'http://localhost').searchParams;
          const lat = Number(q.get('lat') ?? -7.45);
          const lon = Number(q.get('lon') ?? 109.17);
          if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) {
            return send(400, { error: 'invalid coordinates' });
          }
          // Dibaca per request agar .env yang baru diisi langsung terpakai tanpa restart.
          const env = loadEnv(server.config.mode, server.config.root, '');
          const user = env.METEOMATICS_USERNAME;
          const pass = env.METEOMATICS_PASSWORD;
          if (!user || !pass) {
            return send(503, { error: 'missing credentials: fill .env (METEOMATICS_USERNAME / METEOMATICS_PASSWORD)' });
          }
          const valid = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
          const target = `https://api.meteomatics.com/${valid}/${WEATHER_PARAMS}/${lat},${lon}/json`;
          const r = await fetch(target, {
            headers: { Authorization: `Basic ${Buffer.from(`${user}:${pass}`).toString('base64')}` },
            signal: AbortSignal.timeout(15000),
          });
          if (!r.ok) return send(502, { error: `meteomatics HTTP ${r.status}` });
          const body = await r.json();
          const values = {};
          for (const p of body.data ?? []) {
            values[p.parameter] = p.coordinates?.[0]?.dates?.[0]?.value ?? null;
          }
          send(200, {
            source: 'meteomatics',
            fetched_at: new Date().toISOString(),
            valid_time: valid,
            lat,
            lon,
            t2m_c: values['t_2m:C'],
            rh2m_pct: values['relative_humidity_2m:p'],
            precip_mm: values['precip_1h:mm'],
          });
        } catch (e) {
          send(502, { error: e.message });
        }
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), meteomaticsProxy()],
  server: {
    host: '0.0.0.0',
    // /api/predict & /api/forecast diteruskan ke backend FastAPI (uvicorn src.api.predict_server:app --port 8000).
    proxy: {
      '/api/predict': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/api/forecast': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
    ...(process.env.FIGMA && process.env.FIGMA_PUBLIC_URL
      ? { allowedHosts: [new URL(process.env.FIGMA_PUBLIC_URL).hostname] }
      : {}),
  },
  test: { include: ['web-app/src/**/*.test.js'] },
});