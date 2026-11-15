import { useCallback, useEffect, useState } from 'react';
import { CloudSun, RefreshCw } from 'lucide-react';

const fmt = (v, d = 1) => (v == null ? '–' : Number(v).toFixed(d));

export default function LiveWeather({ lang = 'id' }) {
  const en = lang === 'en';
  const [state, setState] = useState({ status: 'loading' });

  const load = useCallback(async () => {
    setState({ status: 'loading' });
    try {
      const r = await fetch('/api/weather');
      const body = await r.json();
      if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
      setState({ status: 'ok', data: body });
    } catch (e) {
      setState({ status: 'error', message: e.message });
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const time =
    state.status === 'ok'
      ? new Date(state.data.fetched_at).toLocaleTimeString(en ? 'en-GB' : 'id-ID', { hour: '2-digit', minute: '2-digit' })
      : null;

  return (
    <div className="live-weather" role="status" title={state.status === 'error' ? state.message : undefined}>
      <CloudSun size={14} />
      {state.status === 'loading' && <small>{en ? 'Loading live weather…' : 'Memuat cuaca live…'}</small>}
      {state.status === 'error' && (
        <small>
          {en ? 'Live weather unavailable' : 'Cuaca live tidak tersedia'}
          {/credentials/.test(state.message) ? (en ? ' · fill .env' : ' · isi .env') : ''}
        </small>
      )}
      {state.status === 'ok' && (
        <>
          <strong>{fmt(state.data.t2m_c)}°C</strong>
          <span>{fmt(state.data.rh2m_pct, 0)}%</span>
          <span>{fmt(state.data.precip_mm)} mm</span>
          <i className="live-dot" />
          <small>LIVE · {time}</small>
        </>
      )}
      <button onClick={load} aria-label={en ? 'Refresh live weather' : 'Segarkan cuaca live'}>
        <RefreshCw size={12} />
      </button>
    </div>
  );
}