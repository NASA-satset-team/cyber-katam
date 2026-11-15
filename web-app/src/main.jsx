import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity,
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Calendar,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  ClipboardCheck,
  CloudRain,
  Droplets,
  FileCheck2,
  Fingerprint,
  FlaskConical,
  Globe2,
  Hexagon,
  Info,
  LayoutDashboard,
  Leaf,
  LockKeyhole,
  MapPin,
  Moon,
  Play,
  Satellite,
  Search,
  Share2,
  ShieldCheck,
  SlidersHorizontal,
  Sprout,
  Sun,
  TriangleAlert,
  Users,
  Wheat,
  X,
} from 'lucide-react';
import {
  number,
  simulate,
  updateGate,
} from './model';
import {
  getDecisionState,
  getGateDefinitions,
  getLayers,
  getMissingEvidence,
  getSimulationSummary,
  getStrategies,
  periodOptionsByLang,
} from './i18n';
import { createInfographic } from './share';
import './styles.css';

const LazyMap = React.lazy(() => import('./FieldMap'));
const initialGates = ['belum', 'belum', 'belum', 'belum'];
const layerIcons = [Droplets, Sun, Leaf, CloudRain, Globe2];
const MIN_HISTORY_DATE = new Date(2021, 0, 1);

function startOfDay(date) {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
}

function addDays(date, days) {
  const d = startOfDay(date);
  d.setDate(d.getDate() + days);
  return d;
}

function isSameDay(a, b) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function formatDailyDate(date, lang = 'id') {
  return new Intl.DateTimeFormat(lang === 'en' ? 'en-GB' : 'id-ID', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(date);
}

function Modal({ title, onClose, closeLabel = 'Tutup dialog', children, className = '' }) {
  const ref = useRef(null);

  useEffect(() => {
    const previous = document.activeElement;
    ref.current?.showModal();
    return () => {
      ref.current?.close();
      previous?.focus();
    };
  }, []);

  return (
    <dialog
      ref={ref}
      className={`modal ${className}`}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      aria-labelledby="modal-title"
    >
      <div className="modal-top">
        <h2 id="modal-title">{title}</h2>
        <button className="icon-button" aria-label={closeLabel} onClick={onClose}>
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}

function DemoBadge({ children, subtle = false, lang = 'id' }) {
  const defaultLabel = lang === 'en' ? 'Simulation Data' : 'Data Simulasi';
  return (
    <span className={`demo-badge ${subtle ? 'subtle' : ''}`}>
      <FlaskConical size={11} />
      {children || defaultLabel}
    </span>
  );
}

function parseRoute(pathname) {
  const clean = (pathname || '/').replace(/\/+$/, '') || '/';
  const segments = clean.split('/').filter(Boolean);
  const defaultMode = window.matchMedia('(max-width: 700px)').matches ? 'farmer' : 'analyst';

  let lang = 'id';
  let theme = 'light';
  let mode = defaultMode;
  let view = 'dashboard';
  let modal = null;

  for (const seg of segments) {
    if (seg === 'en') lang = 'en';
    if (seg === 'id') lang = 'id';
    if (seg === 'dark' || seg === 'gelap') theme = 'dark';
    if (seg === 'light' || seg === 'terang') theme = 'light';
    if (seg === 'petani' || seg === 'farmer') mode = 'farmer';
    if (seg === 'pembuat-kebijakan' || seg === 'policymaker') mode = 'analyst';
  }

  if (clean.endsWith('/audit/bagikan') || clean.endsWith('/audit/share')) {
    view = 'audit';
    modal = 'share';
  } else if (clean.endsWith('/audit')) {
    view = 'audit';
  } else if (clean.endsWith('/data-nasa') || clean.endsWith('/nasa-data') || clean.endsWith('/nasa')) {
    mode = 'analyst';
    view = 'nasa';
  } else if (clean.endsWith('/simulasi') || clean.endsWith('/simulation')) {
    mode = 'analyst';
    view = 'simulasi';
  } else if (clean.endsWith('/pareto')) {
    mode = 'analyst';
    view = 'pareto';
  } else if (clean.endsWith('/diagnostik') || clean.endsWith('/diagnostics')) {
    mode = 'analyst';
    view = 'diagnostik';
  } else if (clean.endsWith('/strategi') || clean.endsWith('/strategy')) {
    mode = 'analyst';
    view = 'strategi';
  } else if (clean.endsWith('/satelit') || clean.endsWith('/satellite')) {
    mode = 'analyst';
    modal = 'sources';
  } else if (clean.endsWith('/periode') || clean.endsWith('/period')) {
    mode = 'farmer';
    modal = 'period';
  } else if (clean.endsWith('/panduan') || clean.endsWith('/guide')) {
    modal = 'help';
  } else if (clean.endsWith('/bagikan') || clean.endsWith('/share')) {
    modal = 'share';
  }

  return { lang, theme, mode, view, modal };
}

function buildRoutePath(mode, view, modal, lang = 'id', theme = 'light') {
  const en = lang === 'en';
  const themeSeg = theme === 'dark' ? (en ? 'dark' : 'gelap') : en ? 'light' : 'terang';
  const modeSeg = mode === 'farmer' ? (en ? 'farmer' : 'petani') : en ? 'policymaker' : 'pembuat-kebijakan';
  const base = `/${lang}/${themeSeg}/${modeSeg}`;

  if (modal === 'sources') return `${base}/${en ? 'satellite' : 'satelit'}`;
  if (modal === 'help') return `${base}/${en ? 'guide' : 'panduan'}`;
  if (modal === 'period') return `${base}/${en ? 'period' : 'periode'}`;
  if (modal === 'share') {
    const shareSeg = en ? 'share' : 'bagikan';
    return view === 'audit' ? `${base}/audit/${shareSeg}` : `${base}/${shareSeg}`;
  }
  if (view === 'audit') return `${base}/audit`;
  if (view === 'nasa') return `${base}/${en ? 'nasa-data' : 'data-nasa'}`;
  if (view === 'simulasi') return `${base}/${en ? 'simulation' : 'simulasi'}`;
  if (view === 'pareto') return `${base}/pareto`;
  if (view === 'diagnostik') return `${base}/${en ? 'diagnostics' : 'diagnostik'}`;
  if (view === 'strategi') return `${base}/${en ? 'strategy' : 'strategi'}`;
  return base;
}

function App() {
  const initialRoute = parseRoute(window.location.pathname);
  const [today] = useState(() => startOfDay(new Date()));
  const maxDate = addDays(today, 3);
  const [selectedDate, setSelectedDate] = useState(() => startOfDay(new Date()));
  const [backClicks, setBackClicks] = useState(0);
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [calViewYear, setCalViewYear] = useState(() => new Date().getFullYear());
  const [calViewMonth, setCalViewMonth] = useState(() => new Date().getMonth());
  const periodWrapRef = useRef(null);

  const [mode, setMode] = useState(initialRoute.mode);
  const [view, setView] = useState(initialRoute.view);
  const [lang, setLang] = useState(initialRoute.lang);
  const [theme, setTheme] = useState(initialRoute.theme);
  const [activeLayers, setActiveLayers] = useState(['smap', 'eco', 'hls', 'gpm']);
  const [resolution, setResolution] = useState(8);
  const [showGrid, setShowGrid] = useState(true);
  const [selectedCell, setSelectedCell] = useState(null);
  const [selectedStrategy, setSelectedStrategy] = useState('B');
  const [rain, setRain] = useState(0);
  const [temperature, setTemperature] = useState(0);
  const [result, setResult] = useState(() => simulate());
  const [hasRun, setHasRun] = useState(false);
  const [diagnostics] = useState(true);
  const [layersOpen, setLayersOpen] = useState(false);
  const [gates, setGates] = useState(initialGates);
  const [activeGate, setActiveGate] = useState(0);
  const [role, setRole] = useState('Analis');
  const [signature, setSignature] = useState('');
  const [signedBy, setSignedBy] = useState('');
  const [acknowledged, setAcknowledged] = useState(false);
  const [modal, setModal] = useState(initialRoute.modal);
  const [share, setShare] = useState(null);
  const [shareFeedback, setShareFeedback] = useState('');
  const [generating, setGenerating] = useState(false);
  const [toast, setToast] = useState('');
  const [term, setTerm] = useState(null);

  const en = lang === 'en';
  const period = formatDailyDate(selectedDate, lang);
  const canGoPrev = selectedDate > MIN_HISTORY_DATE;
  const canGoNext = selectedDate < maxDate;
  const periodOptions = periodOptionsByLang[lang];
  const strategies = getStrategies(lang);
  const layers = getLayers(lang);
  const gateDefinitions = getGateDefinitions(lang);
  const missingEvidence = getMissingEvidence(lang);

  const shareRef = useRef(null);
  const strategy = strategies.find((item) => item.id === selectedStrategy);
  const decision = getDecisionState(gates, lang);
  const analystDashboard =
    mode === 'analyst' && ['dashboard', 'nasa', 'simulasi', 'pareto', 'diagnostik', 'strategi'].includes(view);
  const dirty = result.rain !== rain || result.temperature !== temperature;
  const localizedSummary = getSimulationSummary(result.rain, result.temperature, lang, result.summary);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  useEffect(() => {
    document.body.classList.toggle('dark-theme', theme === 'dark');
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  useEffect(() => {
    if (!toast) return;
    const timeout = setTimeout(() => setToast(''), 4500);
    return () => clearTimeout(timeout);
  }, [toast]);

  useEffect(() => {
    const targetPath = buildRoutePath(mode, view, modal, lang, theme);
    if (window.location.pathname !== targetPath) {
      if (window.location.pathname === '/') {
        window.history.replaceState({}, '', targetPath);
      } else {
        window.history.pushState({}, '', targetPath);
      }
    }
  }, [mode, view, modal, lang, theme]);

  useEffect(() => {
    const onPopState = () => {
      const parsed = parseRoute(window.location.pathname);
      setLang(parsed.lang);
      setTheme(parsed.theme);
      setMode(parsed.mode);
      setView(parsed.view);
      setModal(parsed.modal);
      setTerm(null);
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  useEffect(() => {
    return () => {
      if (shareRef.current) URL.revokeObjectURL(shareRef.current);
    };
  }, []);

  useEffect(() => {
    if (!calendarOpen) return;
    const onPointerDown = (e) => {
      if (periodWrapRef.current && !periodWrapRef.current.contains(e.target)) {
        setCalendarOpen(false);
      }
    };
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [calendarOpen]);

  function changeMode(next) {
    setMode(next);
    setView('dashboard');
    setModal(null);
    setTerm(null);
    window.scrollTo(0, 0);
  }

  function openAudit() {
    setView('audit');
    setModal(null);
    setTerm(null);
    window.scrollTo(0, 0);
  }

  function runSimulation() {
    setResult(simulate(rain, temperature));
    setHasRun(true);
    setGates(initialGates);
    setSignedBy('');
    setSignature('');
    setAcknowledged(false);
    setActiveGate(0);
    setToast(
      en
        ? 'Simulation updated. This is a demo response, not a real climate model or forecast.'
        : 'Simulasi diperbarui. Ini respons demo, bukan model iklim atau prakiraan nyata.'
    );
  }

  function applyDateChange(nextDate) {
    const cleanDate = startOfDay(nextDate);
    setSelectedDate(cleanDate);
    setGates(initialGates);
    setSignedBy('');
    setSignature('');
    setActiveGate(0);
  }

  function handlePrevDay() {
    if (selectedDate <= MIN_HISTORY_DATE) return;
    const nextDate = addDays(selectedDate, -1);
    applyDateChange(nextDate);
    setCalViewYear(nextDate.getFullYear());
    setCalViewMonth(nextDate.getMonth());
    const nextClicks = backClicks + 1;
    setBackClicks(nextClicks);
    if (nextClicks > 5) {
      setCalendarOpen(true);
    }
  }

  function handleNextDay() {
    if (selectedDate >= maxDate) return;
    const nextDate = addDays(selectedDate, 1);
    applyDateChange(nextDate);
    setBackClicks(0);
    setCalendarOpen(false);
  }

  function handleSelectCalendarDate(dayDate) {
    const clean = startOfDay(dayDate);
    if (clean < MIN_HISTORY_DATE || clean > today) return;
    applyDateChange(clean);
    setCalViewYear(clean.getFullYear());
    setCalViewMonth(clean.getMonth());
    setBackClicks(0);
    setCalendarOpen(false);
  }

  function selectStrategy(id) {
    setSelectedStrategy(id);
    setGates(initialGates);
    setSignedBy('');
    setSignature('');
    setAcknowledged(false);
    setActiveGate(0);
  }

  function verifyGate(status) {
    setGates((current) => updateGate(current, activeGate, status));
    setSignedBy(activeGate === 3 && status === 'lulus' ? signature.trim() : '');
    if (status === 'lulus' && activeGate < 3) setActiveGate(activeGate + 1);
    setToast(
      status === 'gagal'
        ? en
          ? 'Gate marked as failed in simulation. System remains in abstention.'
          : 'Gerbang ditandai gagal dalam simulasi. Sistem tetap abstain.'
        : en
        ? 'Demo verification recorded for this session. Not a field validation.'
        : 'Verifikasi demo dicatat untuk sesi ini. Bukan validasi lapangan.'
    );
  }

  async function openShare() {
    setGenerating(true);
    setShareFeedback('');
    try {
      const artifact = await createInfographic({ strategy, result, period });
      if (shareRef.current) URL.revokeObjectURL(shareRef.current);
      shareRef.current = artifact.url;
      setShare(artifact);
      setModal('share');
    } catch (error) {
      setToast(error.message);
    } finally {
      setGenerating(false);
    }
  }

  function downloadShare() {
    const anchor = document.createElement('a');
    anchor.href = share.url;
    anchor.download = 'CYBER-KATAM-ringkasan-simulasi.png';
    anchor.click();
    setShareFeedback(
      en
        ? 'PNG image downloaded. Share as discussion material, not an official planting advisory.'
        : 'Gambar PNG diunduh. Bagikan sebagai bahan diskusi, bukan anjuran tanam.'
    );
  }

  const commonAuditButton = (
    <button className="button primary" onClick={openAudit}>
      <FileCheck2 size={16} />
      {en ? 'View Decision Explanation' : 'Lihat Penjelasan Keputusan'}
      <ArrowUpRight size={15} />
    </button>
  );

  return (
    <div className={`platform ${theme === 'dark' ? 'dark-theme' : 'light-theme'} ${view === 'audit' ? 'audit-theme' : ''}`}>
      <a className="skip-link" href="#content">
        {en ? 'Skip to main content' : 'Lewati ke konten utama'}
      </a>

      {/* HEADER UTAMA */}
      <header className="app-header">
        <span className="header-logo">
          <img src="/Group 3.png" alt="Logo CYBER-KATAM" />
        </span>

        <div className="header-divider" />

        <span className="header-region">
          <MapPin size={15} />
          <span>
            Banyumas
            <small>{en ? 'Central Java, Indonesia' : 'Jawa Tengah, Indonesia'}</small>
          </span>
        </span>

        <div className="header-end">
          <div className="mode-switch" aria-label={en ? 'Select user mode' : 'Pilih mode pengguna'}>
            <button
              className={mode === 'analyst' ? 'active' : ''}
              aria-pressed={mode === 'analyst'}
              onClick={() => changeMode('analyst')}
            >
              <Activity size={14} />
              <span>
                <span className="long-label">{en ? 'Policymaker' : 'Pembuat Kebijakan'}</span>
              </span>
            </button>
            <button
              className={mode === 'farmer' ? 'active' : ''}
              aria-pressed={mode === 'farmer'}
              onClick={() => changeMode('farmer')}
            >
              <Sprout size={14} />
              <span className="long-label">{en ? 'Farmer' : 'Petani'}</span>
            </button>
          </div>

          <div className="header-Divider-small" />

          {/* Toggle Bahasa ID / EN */}
          <div className="lang-switch" role="group" aria-label={en ? 'Select language' : 'Pilih bahasa'}>
            <button
              className={lang === 'id' ? 'active' : ''}
              aria-pressed={lang === 'id'}
              onClick={() => setLang('id')}
              title="Bahasa Indonesia"
            >
              ID
            </button>
            <button
              className={lang === 'en' ? 'active' : ''}
              aria-pressed={lang === 'en'}
              onClick={() => setLang('en')}
              title="English"
            >
              EN
            </button>
          </div>

          {/* Toggle Tema Light / Dark */}
          <button
            className="theme-toggle"
            aria-label={
              theme === 'dark'
                ? en
                  ? 'Switch to Light Mode'
                  : 'Ganti ke Mode Terang'
                : en
                ? 'Switch to Dark Mode'
                : 'Ganti ke Mode Gelap'
            }
            title={
              theme === 'dark'
                ? en
                  ? 'Light Mode'
                  : 'Mode Terang'
                : en
                ? 'Dark Mode'
                : 'Mode Gelap'
            }
            onClick={() => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))}
          >
            {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
          </button>
        </div>
      </header>

      {/* SIDEBAR ANALIS */}
      {mode === 'analyst' && (
        <nav className="analyst-rail" aria-label={en ? 'Analyst navigation' : 'Navigasi analis'}>
          <button
            className={view === 'dashboard' && !modal ? 'active' : ''}
            aria-label={en ? 'Geospatial dashboard' : 'Dasbor geospasial'}
            onClick={() => {
              setView('dashboard');
              setModal(null);
            }}
          >
            <LayoutDashboard size={20} />
            <span>{en ? 'Dashboard' : 'Dasbor'}</span>
          </button>
          <button
            className={view === 'audit' && !modal ? 'active' : ''}
            aria-label={en ? 'Decision audit' : 'Audit keputusan'}
            onClick={openAudit}
          >
            <FileCheck2 size={20} />
            <span>Audit</span>
          </button>
          <button
            className={view === 'nasa' && !modal ? 'active' : ''}
            aria-label={en ? 'NASA satellite data layers' : 'Lapisan Data NASA'}
            onClick={() => {
              setView((prev) => (prev === 'nasa' ? 'dashboard' : 'nasa'));
              setModal(null);
            }}
          >
            <Satellite size={19} />
            <span>{en ? 'NASA Data' : 'Data NASA'}</span>
          </button>
          <button
            className={view === 'simulasi' && !modal ? 'active' : ''}
            aria-label={en ? 'Climate scenario simulation' : 'Simulasi Skenario Iklim'}
            onClick={() => {
              setView((prev) => (prev === 'simulasi' ? 'dashboard' : 'simulasi'));
              setModal(null);
            }}
          >
            <SlidersHorizontal size={19} />
            <span>{en ? 'Simulation' : 'Simulasi'}</span>
          </button>
          <button
            className={view === 'pareto' && !modal ? 'active' : ''}
            aria-label={en ? 'Pareto comparison' : 'Perbandingan Pareto'}
            onClick={() => {
              setView((prev) => (prev === 'pareto' ? 'dashboard' : 'pareto'));
              setModal(null);
            }}
          >
            <Activity size={19} />
            <span>Pareto</span>
          </button>
          <button
            className={view === 'diagnostik' && !modal ? 'active' : ''}
            aria-label={en ? 'Biophysical & Fiscal Diagnostics' : 'Diagnostik Biofisika & Fiskal'}
            onClick={() => {
              setView((prev) => (prev === 'diagnostik' ? 'dashboard' : 'diagnostik'));
              setModal(null);
            }}
          >
            <Droplets size={19} />
            <span>{en ? 'Diagnostics' : 'Diagnostik'}</span>
          </button>
          <button
            className={view === 'strategi' && !modal ? 'active' : ''}
            aria-label={en ? 'Crop Rotation Strategies' : 'Strategi Rotasi Tanaman'}
            onClick={() => {
              setView((prev) => (prev === 'strategi' ? 'dashboard' : 'strategi'));
              setModal(null);
            }}
          >
            <Sprout size={19} />
            <span>{en ? 'Strategy' : 'Strategi'}</span>
          </button>
          <div className="rail-bottom">
            <button
              className={modal === 'help' ? 'active' : ''}
              aria-label={en ? 'Platform guide' : 'Panduan platform'}
              onClick={() => setModal('help')}
            >
              <CircleHelp size={21} />
              <span>{en ? 'Guide' : 'Panduan'}</span>
            </button>
          </div>
        </nav>
      )}

      {/* PETA FULL-SCREEN SEBAGAI BACKGROUND (MODE ANALIS) */}
      {analystDashboard && (
        <div className="map-bg-stage">
          <React.Suspense fallback={<div className="map-fallback">{en ? 'Loading schematic map…' : 'Memuat peta skematik…'}</div>}>
            <LazyMap
              activeLayers={activeLayers}
              result={result}
              resolution={resolution}
              setResolution={setResolution}
              selectedCell={selectedCell}
              showGrid={showGrid}
              setShowGrid={setShowGrid}
              onCell={setSelectedCell}
              lang={lang}
            />
          </React.Suspense>
        </div>
      )}

      {/* KONTEN UTAMA */}
      <main id="content" className={analystDashboard ? 'analyst-main' : view === 'audit' ? 'audit-main' : 'farmer-main'}>
        {/* ======================= VIEW: DASHBOARD & DRAWER SAMPING (MODE ANALIS) ======================= */}
        {analystDashboard && (
          <>
            <div className="analyst-heading">
              <div className="analysis-period" ref={periodWrapRef}>
                <div className="daily-period-bar">
                  <button
                    type="button"
                    className="period-nav-btn"
                    aria-label={en ? 'Previous day' : 'Hari sebelumnya'}
                    title={en ? 'Previous day' : 'Mundur 1 hari'}
                    disabled={!canGoPrev}
                    onClick={handlePrevDay}
                  >
                    <ChevronLeft size={16} />
                  </button>

                  <span className="period-date-display">
                    {period}
                  </span>

                  <button
                    type="button"
                    className="period-nav-btn"
                    aria-label={en ? 'Next day (up to 3 days ahead)' : 'Hari berikutnya (maks. 3 hari ke depan)'}
                    title={
                      canGoNext
                        ? en
                          ? 'Next day (max +3 days from today)'
                          : 'Maju 1 hari (maks. 3 hari dari hari ini)'
                        : en
                        ? 'Maximum +3 days from today reached'
                        : 'Batas maksimal 3 hari ke depan tercapai'
                    }
                    disabled={!canGoNext}
                    onClick={handleNextDay}
                  >
                    <ChevronRight size={16} />
                  </button>
                </div>

                {calendarOpen && (
                  <HistoryCalendarPopover
                    lang={lang}
                    today={today}
                    minDate={MIN_HISTORY_DATE}
                    selectedDate={selectedDate}
                    viewYear={calViewYear}
                    viewMonth={calViewMonth}
                    setViewYear={setCalViewYear}
                    setViewMonth={setCalViewMonth}
                    onSelectDate={handleSelectCalendarDate}
                    onClose={() => setCalendarOpen(false)}
                  />
                )}
              </div>
            </div>

            {/* PANEL DRAWER MUNCUL DARI SAMPING KIRI SAAT MENU DIKLIK */}
            {view !== 'dashboard' && (
              <div className="side-menu-drawer" key={view}>
                {/* 1. MENU DATA NASA */}
                {view === 'nasa' && (
                  <aside className="diagnostic-sidebar side-drawer-card">
                    <div className="diagnostic-heading">
                      <h2>
                        <Satellite size={17} />
                        {en ? 'NASA Data' : 'Data NASA'}
                      </h2>
                      <div className="drawer-header-actions">
                        <button className="metadata-link-btn" onClick={() => setModal('sources')}>
                          Metadata
                          <ArrowUpRight size={12} />
                        </button>
                        <button
                          type="button"
                          className="drawer-close-btn"
                          aria-label={en ? 'Close panel' : 'Tutup panel'}
                          onClick={() => setView('dashboard')}
                        >
                          <X size={16} />
                        </button>
                      </div>
                    </div>
                    <div className="diagnostic-content">
                      <p className="satellite-subtitle" style={{ marginTop: 0, marginBottom: 12 }}>
                        {en ? 'Select visual context for exploration.' : 'Pilih konteks visual untuk eksplorasi.'}
                      </p>
                      <div className="drawer-layer-list">
                        {layers.map((layer, index) => {
                          const Icon = layerIcons[index];
                          const isEnabled = activeLayers.includes(layer.id);
                          return (
                            <button
                              key={layer.id}
                              className={`layer-row ${isEnabled ? 'enabled' : ''}`}
                              role="switch"
                              aria-checked={isEnabled}
                              aria-label={`${en ? 'Layer' : 'Lapisan'} ${layer.name}`}
                              onClick={() =>
                                setActiveLayers((current) =>
                                  current.includes(layer.id)
                                    ? current.filter((id) => id !== layer.id)
                                    : [...current, layer.id]
                                )
                              }
                            >
                              <span className={`layer-icon ${layer.id}`}>
                                <Icon size={16} />
                              </span>
                              <span className="layer-description">
                                <strong>
                                  {layer.name}
                                  <small>{layer.resolution}</small>
                                </strong>
                                <span>{layer.title}</span>
                                <small>
                                  {layer.source} · {layer.id === 'srtm' ? (en ? 'Not available' : 'Belum tersedia') : (en ? 'Illustrative' : 'Ilustratif')}
                                </small>
                              </span>
                              <span className="toggle-track">
                                <i />
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </aside>
                )}

                {/* 2. MENU SIMULASI SKENARIO IKLIM */}
                {view === 'simulasi' && (
                  <aside className="diagnostic-sidebar side-drawer-card">
                    <div className="diagnostic-heading">
                      <h2>
                        <SlidersHorizontal size={17} />
                        {en ? 'Climate Scenario Simulation' : 'Simulasi Skenario Iklim'}
                      </h2>
                      <button
                        type="button"
                        className="drawer-close-btn"
                        aria-label={en ? 'Close panel' : 'Tutup panel'}
                        onClick={() => setView('dashboard')}
                      >
                        <X size={16} />
                      </button>
                    </div>
                    <div className="diagnostic-content">
                      <div className="drawer-climate-controls">
                        <Slider
                          label={en ? 'Rainfall anomaly' : 'Anomali curah hujan'}
                          unit="%"
                          value={rain}
                          setValue={setRain}
                          min={-30}
                          max={30}
                          step={5}
                          icon={CloudRain}
                        />
                        <Slider
                          label={en ? 'Temperature rise' : 'Kenaikan suhu'}
                          unit="°C"
                          value={temperature}
                          setValue={setTemperature}
                          min={0}
                          max={3}
                          step={0.5}
                          icon={Sun}
                        />
                        <button className="button primary run-button" style={{ width: '100%' }} onClick={runSimulation}>
                          <Play size={15} fill="currentColor" />
                          {en ? 'Run Simulation' : 'Jalankan Simulasi'}
                        </button>
                      </div>

                      <div className="simulation-summary" aria-live="polite" style={{ marginTop: 14, paddingBottom: 0 }}>
                        <span className="summary-status">
                          <i />
                          {dirty
                            ? en
                              ? 'Changes not yet run'
                              : 'Perubahan belum dijalankan'
                            : hasRun
                            ? en
                              ? 'Simulation updated'
                              : 'Simulasi diperbarui'
                            : en
                            ? 'Baseline scenario active'
                            : 'Skenario dasar aktif'}
                        </span>
                      </div>
                    </div>
                  </aside>
                )}

                {/* 3. MENU PERBANDINGAN PARETO */}
                {view === 'pareto' && (
                  <aside className="diagnostic-sidebar side-drawer-card">
                    <div className="diagnostic-heading">
                      <h2>
                        <Activity size={17} />
                        {en ? 'Pareto Comparison' : 'Perbandingan Pareto'}
                      </h2>
                      <button
                        type="button"
                        className="drawer-close-btn"
                        aria-label={en ? 'Close panel' : 'Tutup panel'}
                        onClick={() => setView('dashboard')}
                      >
                        <X size={16} />
                      </button>
                    </div>
                    <div className="diagnostic-content">
                      <Pareto selected={selectedStrategy} onSelect={selectStrategy} strategies={strategies} lang={lang} embedded />
                    </div>
                  </aside>
                )}

                {/* 4. MENU DIAGNOSTIK BIOFISIKA & FISKAL */}
                {view === 'diagnostik' && (
                  <aside className="diagnostic-sidebar side-drawer-card">
                    <div className="diagnostic-heading">
                      <h2>
                        <Droplets size={17} />
                        {en ? 'Biophysical & Fiscal Diagnostics' : 'Diagnostik Biofisika & Fiskal'}
                      </h2>
                      <button
                        type="button"
                        className="drawer-close-btn"
                        aria-label={en ? 'Close panel' : 'Tutup panel'}
                        onClick={() => setView('dashboard')}
                      >
                        <X size={16} />
                      </button>
                    </div>

                    <div className="diagnostic-content">
                      <div className="diagnostic-kpis">
                        <RiskMetric
                          name="PVRS"
                          explanation={en ? 'Root stress risk (PVRSEngine)' : 'Risiko stres akar (PVRSEngine)'}
                          value={selectedCell?.indicators?.pvrs ?? result.pvrs}
                          color="red"
                          sourceNote={
                            selectedCell?.indicators?.pvrs != null
                              ? en
                                ? 'Real PVRSEngine'
                                : 'PVRSEngine Riil'
                              : en
                              ? 'Simulation Data'
                              : 'Data Simulasi'
                          }
                          lang={lang}
                        />
                        <RiskMetric
                          name="BF-EHSI"
                          explanation={en ? 'Fallow land erosion risk' : 'Risiko erosi lahan bera'}
                          value={result.erosion}
                          color="orange"
                          sourceNote={en ? 'Simulation Data' : 'Data Simulasi'}
                          lang={lang}
                        />
                      </div>

                      <div className="water-ledger no-border-bottom">
                        <span>
                          <Droplets size={15} />
                          {en ? 'Illustrative water balance' : 'Neraca air ilustratif'}
                        </span>
                        <strong>
                          {result.water > 0 ? '+' : ''}
                          {result.water}
                          <small> mm</small>
                        </strong>
                      </div>
                    </div>
                  </aside>
                )}

                {/* 5. MENU STRATEGI ROTASI TANAMAN */}
                {view === 'strategi' && (
                  <aside className="diagnostic-sidebar side-drawer-card">
                    <div className="diagnostic-heading">
                      <h2>
                        <Sprout size={17} />
                        {en ? 'Crop Rotation Strategies' : 'Strategi Rotasi Tanaman'}
                      </h2>
                      <button
                        type="button"
                        className="drawer-close-btn"
                        aria-label={en ? 'Close panel' : 'Tutup panel'}
                        onClick={() => setView('dashboard')}
                      >
                        <X size={16} />
                      </button>
                    </div>

                    <div className="diagnostic-content">
                      <div className="compact-scenarios">
                        {strategies.map((item) => (
                          <button
                            key={item.id}
                            className={`compact-scenario ${item.id === 'B' ? 'recommended' : ''} ${
                              selectedStrategy === item.id ? 'selected' : ''
                            }`}
                            aria-pressed={selectedStrategy === item.id}
                            onClick={() => selectStrategy(item.id)}
                          >
                            <span className="scenario-letter">{item.id}</span>
                            <span>
                              <strong>{item.name}</strong>
                              <small>
                                {item.id === 'B' ? (
                                  <>
                                    <span className="status-dot" />
                                    {en ? 'Featured in demo' : 'Unggulan dalam demo'}
                                  </>
                                ) : item.id === 'A' ? (
                                  en ? 'Existing pattern · baseline' : 'Pola eksisting · pembanding'
                                ) : (
                                  en ? 'Diversification alternative' : 'Alternatif diversifikasi'
                                )}
                              </small>
                            </span>
                            <span className="scenario-radio">
                              {selectedStrategy === item.id && <Check size={11} />}
                            </span>
                          </button>
                        ))}
                      </div>

                      <div className="fiscal-card">
                        <div>
                          <span className="fiscal-icon">
                            <Leaf size={17} />
                          </span>
                          <span>{en ? 'POTENTIAL UREA SUBSIDY SAVINGS' : 'POTENSI PENGHEMATAN SUBSIDI UREA'}</span>
                        </div>
                        <h3>
                          Rp16,58 <span>{en ? 'Billion' : 'Miliar'}</span>
                        </h3>
                        <p>{en ? 'per H3-7 cluster · conceptual budget illustration' : 'per kluster H3-7 · ilustrasi anggaran konsep'}</p>
                        <div>
                          <span>
                            <ShieldCheck size={13} />
                            {en ? 'AUTP risk reduction' : 'Penurunan risiko AUTP'}
                          </span>
                          <strong>
                            {number(result.insurance, 1)}%<small> {en ? 'illustrative' : 'ilustratif'}</small>
                          </strong>
                        </div>
                        <small className="fiscal-caveat">
                          {en
                            ? 'Not verified fiscal output. Cluster area and actual benefits are not yet established.'
                            : 'Bukan hasil fiskal terverifikasi. Luas kluster dan manfaat aktual belum ditetapkan.'}
                        </small>
                      </div>

                      <div className="diagnostic-cta">
                        <div>
                          <LockKeyhole size={13} />
                          {en ? 'Awaiting field verification' : 'Menunggu verifikasi lapangan'}
                        </div>
                        {commonAuditButton}
                      </div>
                    </div>
                  </aside>
                )}
              </div>
            )}
          </>
        )}

        {/* ======================= VIEW: DASHBOARD (MODE PETANI) ======================= */}
        {view === 'dashboard' && mode === 'farmer' && (
          <>
            <div className="farmer-greeting">
              <div>
                <h1>
                  {en ? 'Good morning, Farmer!' : 'Selamat pagi, Pak/Bu!'}
                  <Sprout size={32} />
                </h1>
                <p>
                  {en
                    ? 'Let’s understand your land conditions and explore planting options together.'
                    : 'Mari kenali kondisi lahan dan pertimbangkan pilihan tanam bersama.'}
                </p>
              </div>
            </div>

            <div className="farmer-demo-notice">
              <FlaskConical size={17} />
              <p>
                <strong>{en ? 'You are in the simulation room.' : 'Anda berada di ruang simulasi.'}</strong>{' '}
                {en
                  ? 'The following information is an example, not a measurement of your actual land.'
                  : 'Informasi berikut adalah contoh, bukan hasil pengukuran lahan Anda.'}
              </p>
              <button onClick={() => setModal('help')}>
                {en ? 'Learn more' : 'Pelajari'}
                <ArrowUpRight size={14} />
              </button>
            </div>

            {/* Peringatan Air */}
            <section className="farmer-warning">
              <div className="warning-water">
                <Droplets size={32} />
              </div>
              <div className="warning-copy">
                <h2>{en ? 'Roots Starting to Thirst' : 'Akar Mulai Kehausan'}</h2>
                <p>
                  <button
                    className="term-link"
                    aria-expanded={term === 'water'}
                    onClick={() => setTerm(term === 'water' ? null : 'water')}
                  >
                    {en ? 'Soil water reserve' : 'Cadangan air tanah'}
                    <Info size={12} />
                  </button>{' '}
                  {en ? (
                    <>
                      in this example is estimated at <strong>{result.moisture}%</strong>. Consider more water-efficient planting options with your extension officer (PPL).
                    </>
                  ) : (
                    <>
                      dalam contoh diperkirakan tinggal <strong>{result.moisture}%</strong>. Pertimbangkan pilihan tanam yang lebih hemat air bersama PPL.
                    </>
                  )}
                </p>
                {term === 'water' && (
                  <div className="term-popover" role="tooltip">
                    {en
                      ? 'Soil water reserve is the moisture still stored in the soil that plant roots can absorb.'
                      : 'Cadangan air tanah adalah air yang masih tersimpan di tanah dan dapat dimanfaatkan akar tanaman.'}
                  </div>
                )}
                <small>
                  {en
                    ? 'First step: check irrigation water and drainage before changing cropping patterns.'
                    : 'Langkah awal: cek air irigasi dan drainase sebelum mengubah pola tanam.'}
                </small>
              </div>

              <div className="water-gauge">
                <svg viewBox="0 0 100 100">
                  <circle cx="50" cy="50" r="42" fill="none" stroke="#f0e9c8" strokeWidth="7" />
                  <circle
                    cx="50"
                    cy="50"
                    r="42"
                    fill="none"
                    stroke="#ffd600"
                    strokeWidth="7"
                    strokeDasharray={`${result.moisture * 2.64} 264`}
                    transform="rotate(-90 50 50)"
                    strokeLinecap="round"
                  />
                </svg>
                <div>
                  <strong>
                    {result.moisture}
                    <small>%</small>
                  </strong>
                  <span>{en ? 'illustrative water' : 'air ilustratif'}</span>
                </div>
              </div>
            </section>

            {/* Opsi Rotasi Tanaman */}
            <section className="farmer-rotations">
              <div className="farmer-section-heading">
                <div>
                  <div className="eyebrow">{en ? 'OPTIONS FOR DISCUSSION' : 'PILIHAN YANG BISA DIDISKUSIKAN'}</div>
                  <h2>{en ? 'Compare Planting Options!' : 'Yuk, Bandingkan Pilihan Tanam!'}</h2>
                  <p>
                    {en
                      ? 'Understand the benefits and trade-offs. No single pattern fits every field.'
                      : 'Kenali manfaat dan pertimbangannya. Tidak ada satu pola yang cocok untuk semua lahan.'}
                  </p>
                </div>
                <DemoBadge lang={lang} />
              </div>

              <div className="farmer-scenarios">
                {strategies.map((item) => (
                  <article
                    key={item.id}
                    className={`farmer-scenario ${item.id === 'B' ? 'recommended' : ''} ${
                      selectedStrategy === item.id ? 'selected' : ''
                    }`}
                  >
                    <div className="farmer-scenario-top">
                      <span className="scenario-letter">{item.id}</span>
                      <span className="crop-badge">
                        {item.id === 'B' && <Sprout size={12} />}
                        {item.label}
                        {item.id === 'B' && <small> · demo</small>}
                      </span>
                    </div>

                    <div className="crop-illustration">
                      <Wheat size={34} strokeWidth={1.4} />
                      <span className="crop-arrow">
                        <ArrowRight size={18} />
                      </span>
                      {item.id === 'A' ? <Sun size={32} strokeWidth={1.4} /> : <Sprout size={36} strokeWidth={1.4} />}
                    </div>

                    <h3>{item.name}</h3>
                    <p>{item.note}</p>

                    <ul>
                      <li>
                        <Droplets size={18} />
                        <span>{item.water}</span>
                      </li>
                      <li>
                        <Leaf size={18} />
                        <span>{item.nitrogen}</span>
                      </li>
                      <li>
                        <ShieldCheck size={18} />
                        <span>{item.pests}</span>
                      </li>
                    </ul>

                    <button
                      className={`button ${selectedStrategy === item.id ? 'primary' : 'secondary'}`}
                      aria-pressed={selectedStrategy === item.id}
                      onClick={() => selectStrategy(item.id)}
                    >
                      {selectedStrategy === item.id ? <Check size={16} /> : <Search size={16} />}
                      {selectedStrategy === item.id
                        ? en
                          ? 'Selected for discussion'
                          : 'Dipilih untuk diskusi'
                        : en
                        ? 'Compare this option'
                        : 'Bandingkan pilihan ini'}
                    </button>
                  </article>
                ))}
              </div>
              <p className="farmer-caption">
                <Info size={14} />
                {en
                  ? 'Qualitative comparisons and potential benefits have not been validated in the field.'
                  : 'Perbandingan kualitatif dan manfaat potensial belum divalidasi di lapangan.'}
              </p>
            </section>

            {/* Rekomendasi Lahan */}
            <section className="farmer-recommendation">
              <div className="recommendation-story">
                <img
                  src="/indonesia-fields.jpg"
                  alt={
                    en
                      ? 'Illustrative photo of agricultural landscape in Indonesia, not user’s land'
                      : 'Foto ilustratif bentang pertanian di Indonesia, bukan lahan pengguna'
                  }
                />
                <div>
                  <span>{en ? 'LOCAL KNOWLEDGE COMES FIRST' : 'PENGETAHUAN LOKAL TETAP UTAMA'}</span>
                  <h2>
                    {en ? (
                      <>
                        Every field is different.
                        <br />
                        So are its considerations.
                      </>
                    ) : (
                      <>
                        Lahan berbeda.
                        <br />
                        Pertimbangan pun berbeda.
                      </>
                    )}
                  </h2>
                  <p>
                    {en
                      ? 'The best decisions are made together with farmers and extension officers who know the land.'
                      : 'Keputusan terbaik dibuat bersama petani dan penyuluh yang mengenal lahannya.'}
                  </p>
                  <small>{en ? 'Photo: Iswanto Arif / Unsplash · illustration' : 'Foto: Iswanto Arif / Unsplash · ilustrasi'}</small>
                </div>
              </div>

              <div className="recommendation-content">
                <div className="recommendation-title">
                  <span className="round-leaf">
                    <Sprout size={22} />
                  </span>
                  <span>
                    <small>{en ? 'SIMULATION DISCUSSION OPTION' : 'PILIHAN DISKUSI SIMULASI'}</small>
                    <h2>{en ? 'Recommendation for Your Land' : 'Rekomendasi untuk Lahan Anda'}</h2>
                  </span>
                </div>

                <h3>{strategy.name}</h3>
                <p>{strategy.why}</p>

                <div className="farmer-reasons">
                  <div>
                    <Check size={17} />
                    <p>
                      <strong>{en ? 'Potential benefits' : 'Manfaat yang berpotensi didapat'}</strong>
                      {strategy.benefit}
                    </p>
                  </div>
                  <div>
                    <TriangleAlert size={17} />
                    <p>
                      <strong>{en ? 'Things to watch out for' : 'Yang perlu diperhatikan'}</strong>
                      {strategy.risk}
                    </p>
                  </div>
                  <div>
                    <ClipboardCheck size={17} />
                    <p>
                      <strong>{en ? 'Still needs checking' : 'Masih perlu diperiksa'}</strong>
                      {en
                        ? 'Drainage, soil pH, water supply, seeds, costs, and farmer group agreement.'
                        : 'Drainase, pH tanah, persediaan air, benih, biaya, dan kesepakatan kelompok tani.'}
                    </p>
                  </div>
                </div>

                <div className="recommendation-actions">
                  <button className="button primary" onClick={openAudit}>
                    <BookOpen size={16} />
                    {en ? 'View Recommendation Reasoning' : 'Lihat Alasan Rekomendasi'}
                  </button>
                </div>

                <span className="withheld-note">
                  <LockKeyhole size={12} />
                  {en
                    ? 'Official advisory is withheld until evidence and verification are available.'
                    : 'Anjuran resmi ditahan sampai bukti dan verifikasi tersedia.'}
                </span>
              </div>
            </section>

            {/* Banner WhatsApp */}
            <div className="whatsapp-banner">
              <span className="share-round">
                <Share2 size={23} />
              </span>
              <div>
                <h3>
                  {en
                    ? 'Planting decisions are better discussed together.'
                    : 'Keputusan tanam lebih baik dibicarakan bersama.'}
                </h3>
                <p>
                  {en
                    ? 'Prepare a lightweight summary card for discussion with your farmer group and PPL.'
                    : 'Siapkan kartu ringan untuk bahan diskusi dengan kelompok tani dan PPL.'}
                </p>
              </div>
              <button className="button primary" onClick={openShare} disabled={generating}>
                <Share2 size={16} />
                {generating
                  ? en
                    ? 'Preparing image…'
                    : 'Menyiapkan gambar…'
                  : en
                  ? 'Share Summary via WhatsApp'
                  : 'Bagikan Ringkasan via WhatsApp'}
              </button>
            </div>
          </>
        )}

        {/* ======================= VIEW: AUDIT ======================= */}
        {view === 'audit' && (
          <>
            <button
              className="back-button"
              onClick={() => {
                setView('dashboard');
                window.scrollTo(0, 0);
              }}
            >
              <ArrowLeft size={15} />
              {en
                ? `Back to ${mode === 'analyst' ? 'analyst dashboard' : 'farmer mode'}`
                : `Kembali ke ${mode === 'analyst' ? 'dasbor analis' : 'mode petani'}`}
            </button>

            <div className="audit-page-heading">
              <div>
                <h1>{en ? 'Decision Explanation Certificate' : 'Sertifikat Penjelasan Keputusan'}</h1>
              </div>
              <div className="certificate-seal">
                <Hexagon size={64} strokeWidth={1} />
                <ShieldCheck size={28} />
                <span>{en ? 'SIMULATION DRAFT' : 'DRAF SIMULASI'}</span>
              </div>
            </div>

            {/* Sertifikat Header */}
            <section className="certificate-header">
              <div className="certificate-identity">
                <span className="certificate-icon">
                  <FileCheck2 size={28} />
                </span>
                <div>
                  <span className="micro-label">{en ? 'DEMO RECOMMENDATION ID' : 'ID REKOMENDASI DEMO'}</span>
                  <h2>CK-BMS-2026-{selectedStrategy}01</h2>
                </div>
                <div className="certificate-status">
                  <LockKeyhole size={15} />
                  <strong>{en ? 'Abstain — Insufficient Data' : 'Abstain — Data Belum Memadai'}</strong>
                </div>
              </div>

              <div className="certificate-meta">
                <div>
                  <span>{en ? 'Analysis region' : 'Wilayah analisis'}</span>
                  <strong>{en ? 'Banyumas, Central Java' : 'Banyumas, Jawa Tengah'}</strong>
                </div>
                <div>
                  <span>{en ? 'Sample analysis period' : 'Periode analisis contoh'}</span>
                  <strong>{period}</strong>
                </div>
                <div>
                  <span>{en ? 'Evaluated rotation' : 'Rotasi yang dikaji'}</span>
                  <strong>{strategy.name}</strong>
                </div>
                <div>
                  <span>{en ? 'Data status' : 'Status data'}</span>
                  <DemoBadge lang={lang}>{en ? 'Illustrative Data · Unverified' : 'Data Ilustratif · Belum Diverifikasi'}</DemoBadge>
                </div>
              </div>
            </section>

            {/* Grid Penjelasan Keputusan (XAI) */}
            <div className="xai-grid">
              {/* Blok 01 */}
              <section className="xai-block evidence-block">
                <BlockTitle
                  index="01"
                  icon={Satellite}
                  title={en ? 'NASA Satellite Quantitative Evidence' : 'Bukti Kuantitatif Satelit NASA'}
                  subtitle={en ? 'Sample indicators, not verified observation evidence.' : 'Contoh indikator, bukan bukti observasi nyata.'}
                  lang={lang}
                />
                <div className="evidence-table">
                  <div className="evidence-table-heading">
                    <span>{en ? 'INDICATOR / SOURCE' : 'INDIKATOR / SUMBER'}</span>
                    <span>{en ? 'VALUE / RESOLUTION' : 'NILAI / RESOLUSI'}</span>
                  </div>
                  {layers.map((layer) => (
                    <div className="evidence-row" key={layer.id}>
                      <div>
                        <strong>{layer.title}</strong>
                        <span>{layer.source}</span>
                        <small>
                          {en ? 'Period' : 'Periode'}: {layer.id === 'srtm' ? (en ? 'Not Available' : 'Belum Tersedia') : period}
                        </small>
                      </div>
                      <div>
                        <strong>
                          {layer.id === 'eco' ? `${number(32.1 + result.temperature, 1)} °C` : layer.value}
                        </strong>
                        <span>
                          {en ? 'Native' : 'Asli'} {layer.resolution}
                        </span>
                        <small>{layer.id === 'srtm' ? (en ? 'Not Available' : 'Belum Tersedia') : (en ? 'Simulation Data' : 'Data Simulasi')}</small>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="block-footnote">
                  <Info size={13} />
                  {en
                    ? 'LSTE is not ESI. ESI source and full real exports are not yet available. SMAP/GPM are not independent per H3 cell.'
                    : 'LSTE bukan ESI. Sumber ESI dan seluruh ekspor nyata belum tersedia. SMAP/GPM tidak independen per sel H3.'}
                </div>
              </section>

              {/* Blok 02 */}
              <section className="xai-block benefits-block">
                <BlockTitle
                  index="02"
                  icon={Sprout}
                  title={en ? 'Multi-Dimensional Benefits' : 'Manfaat Multi-Dimensi'}
                  subtitle={en ? 'Conditional potential, not yet measured in the field.' : 'Potensi bersyarat, belum terukur di lahan.'}
                  lang={lang}
                />
                <div className="benefit-list">
                  {[
                    { icon: Droplets, title: en ? 'Water efficiency' : 'Efisiensi air', text: strategy.water, width: strategy.waterScore },
                    {
                      icon: Leaf,
                      title: en ? 'Soil health' : 'Kesehatan tanah',
                      text: en ? 'Residue management and ground cover must be reviewed.' : 'Pengelolaan residu dan penutup tanah perlu ditinjau.',
                      width: strategy.soilScore,
                    },
                    {
                      icon: Sprout,
                      title: en ? 'Fertilizer savings' : 'Penghematan pupuk',
                      text: en ? 'Nitrogen fixation does not automatically equal fertilizer dose reduction.' : 'Fiksasi nitrogen tidak sama dengan pengurangan dosis pupuk.',
                      width: 65,
                    },
                    { icon: ShieldCheck, title: en ? 'Pest cycle disruption' : 'Pemutusan siklus hama', text: strategy.pests, width: strategy.pestScore },
                    {
                      icon: Sun,
                      title: en ? 'Climate resilience' : 'Ketahanan iklim',
                      text: en ? 'Diversification remains dependent on local conditions.' : 'Diversifikasi tetap bergantung pada kondisi lokal.',
                      width: 74,
                    },
                  ].map(({ icon: Icon, title, text, width }) => (
                    <div className="benefit-item" key={title}>
                      <span>
                        <Icon size={19} />
                      </span>
                      <div>
                        <strong>{title}</strong>
                        <p>{text}</p>
                        <div className="impact-track">
                          <i style={{ width: `${width}%` }} />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="block-footnote">
                  <FlaskConical size={13} />
                  {en
                    ? 'Bar length is a visual illustration, not a quantified benefit or probability.'
                    : 'Panjang indikator adalah ilustrasi visual, bukan besaran manfaat atau probabilitas.'}
                </div>
              </section>

              {/* Blok 03 */}
              <section className="xai-block gap-block">
                <BlockTitle
                  index="03"
                  icon={Info}
                  title={en ? 'Satellite Information Limitations' : 'Batasan Informasi Satelit'}
                  subtitle={en ? 'Cannot be determined from satellites alone.' : 'Tidak dapat dipastikan dari satelit saja.'}
                  lang={lang}
                />
                <ul className="audit-list">
                  {(en
                    ? [
                        'Micro-scale local soil pH',
                        'Tertiary irrigation gate condition',
                        'Actual seed and inoculant availability',
                        'Plot-level drainage and waterlogging condition',
                        'Farmer labor, cost, and equipment constraints',
                      ]
                    : [
                        'pH tanah lokal pada skala mikro',
                        'Kondisi pintu air irigasi tersier',
                        'Ketersediaan benih dan inokulan aktual',
                        'Kondisi drainase dan genangan di petak',
                        'Kendala tenaga kerja, biaya, dan alat petani',
                      ]
                  ).map((text) => (
                    <li key={text}>
                      <span className="unknown-icon">?</span>
                      <span>{text}</span>
                      <small>{en ? 'Field check required' : 'Perlu cek lapangan'}</small>
                    </li>
                  ))}
                </ul>
              </section>

              {/* Blok 04 */}
              <section className="xai-block risk-block">
                <BlockTitle
                  index="04"
                  icon={TriangleAlert}
                  title={en ? 'Local Risks' : 'Risiko Lokal'}
                  subtitle={en ? 'Assumptions and uncertainties that must be reviewed.' : 'Asumsi dan ketidakpastian yang harus ditinjau.'}
                  lang={lang}
                />
                <ul className="audit-list">
                  {(en
                    ? [
                        'Uncertain rainfall and shifting planting windows',
                        'Soil texture variation and waterlogging risk',
                        'Pest outbreaks and cross-field migration',
                        'Seed / inoculant supply mismatch with plans',
                        'Capital, market, and execution constraints',
                      ]
                    : [
                        'Hujan tidak pasti dan perubahan waktu tanam',
                        'Variasi tekstur tanah serta risiko genangan',
                        'Ledakan hama dan migrasi antarhamparan',
                        'Pasokan benih / inokulan tidak sesuai rencana',
                        'Keterbatasan modal, pasar, dan pelaksanaan',
                      ]
                  ).map((text) => (
                    <li key={text}>
                      <TriangleAlert size={15} />
                      <span>{text}</span>
                    </li>
                  ))}
                </ul>
                <div className="risk-callout">
                  {en
                    ? 'Do not change fertilizer doses or planting schedules based solely on this example.'
                    : 'Jangan mengubah dosis pupuk atau waktu tanam hanya berdasarkan contoh ini.'}
                </div>
              </section>
            </div>

            {/* Gerbang Validasi */}
            <section className="gatekeeper-panel">
              <div className="gatekeeper-heading">
                <div>
                  <div className="eyebrow">
                    {en ? 'CONTROLLED ABSTENTION · HUMAN-IN-THE-LOOP' : 'ABSTENSI TERKENDALI · KENDALI MANUSIA'}
                  </div>
                  <h2>{en ? 'Recommendation Validation Gates' : 'Gerbang Validasi Rekomendasi'}</h2>
                  <p>
                    {en
                      ? 'Four sequential steps. Passing in simulation does not replace real field evidence.'
                      : 'Empat langkah berurutan. Kelulusan simulasi tidak menggantikan bukti nyata.'}
                  </p>
                </div>
                <label className="role-select">
                  {en ? 'Demo role' : 'Peran demo'}
                  <select aria-label={en ? 'Demo verification role' : 'Peran verifikasi demo'} value={role} onChange={(e) => setRole(e.target.value)}>
                    <option value="Analis">{en ? 'Analyst' : 'Analis'}</option>
                    <option value="PPL">PPL</option>
                  </select>
                </label>
              </div>

              <div className="gate-sequence">
                {gateDefinitions.map((gate, index) => (
                  <button
                    key={gate.title}
                    className={`gate-step ${activeGate === index ? 'active' : ''} ${gates[index]}`}
                    onClick={() => setActiveGate(index)}
                    aria-pressed={activeGate === index}
                  >
                    <span className="gate-number">
                      {gates[index] === 'lulus' ? (
                        <Check size={18} />
                      ) : gates[index] === 'gagal' ? (
                        <X size={18} />
                      ) : (
                        `0${index + 1}`
                      )}
                    </span>
                    <span>
                      <strong>{gate.title}</strong>
                      <small>
                        {gates[index] === 'lulus'
                          ? en
                            ? 'Passed · Simulation'
                            : 'Lulus · Simulasi'
                          : gates[index] === 'gagal'
                          ? en
                            ? 'Failed · Simulation'
                            : 'Gagal · Simulasi'
                          : en
                          ? 'Unverified'
                          : 'Belum Diverifikasi'}
                      </small>
                    </span>
                    {index < 3 && <ArrowRight className="gate-arrow" size={15} />}
                  </button>
                ))}
              </div>

              <div className="gate-detail">
                <div className="gate-detail-copy">
                  <span className="micro-label">
                    {en ? 'GATE' : 'GERBANG'} 0{activeGate + 1} · {gateDefinitions[activeGate].owner.toUpperCase()}
                  </span>
                  <h3>{gateDefinitions[activeGate].title}</h3>
                  <p>{gateDefinitions[activeGate].description}</p>
                  <div className="gate-evidence-gap">
                    <Info size={14} />
                    {gateDefinitions[activeGate].missing}
                  </div>
                </div>

                <div className="gate-actions">
                  {activeGate > 0 && gates.slice(0, activeGate).some((gate) => gate !== 'lulus') ? (
                    <div className="locked-gate">
                      <LockKeyhole size={22} />
                      <p>
                        {en
                          ? 'Complete the previous gates in demo to try this stage.'
                          : 'Selesaikan gerbang sebelumnya dalam demo untuk mencoba tahap ini.'}
                      </p>
                    </div>
                  ) : activeGate === 3 ? (
                    <>
                      <label>
                        {en ? 'PPL name for simulation' : 'Nama PPL untuk simulasi'}
                        <input
                          aria-label={en ? 'PPL name for simulation' : 'Nama PPL untuk simulasi'}
                          value={signature}
                          onChange={(e) => setSignature(e.target.value)}
                          placeholder={en ? 'Example: Siti Rahma' : 'Contoh: Siti Rahma'}
                          maxLength={70}
                        />
                      </label>
                      <label className="signature-ack">
                        <input
                          type="checkbox"
                          checked={acknowledged}
                          onChange={(e) => setAcknowledged(e.target.checked)}
                        />
                        {en
                          ? 'I understand this is not a legally binding digital signature.'
                          : 'Saya memahami ini bukan tanda tangan digital yang sah.'}
                      </label>
                      <button
                        className="button primary"
                        disabled={role !== 'PPL' || !signature.trim() || !acknowledged}
                        onClick={() => verifyGate('lulus')}
                      >
                        <Fingerprint size={17} />
                        {en ? 'Simulate PPL Signature' : 'Simulasikan Tanda Tangan PPL'}
                      </button>
                      {role !== 'PPL' && (
                        <small className="signature-help">
                          {en ? 'Select the PPL demo role to test signing.' : 'Pilih peran demo PPL untuk mencoba tanda tangan.'}
                        </small>
                      )}
                      {signedBy && (
                        <span className="signature-record">
                          <Check size={13} />
                          {en ? `Simulated by ${signedBy} · this session only` : `Simulasi oleh ${signedBy} · hanya sesi ini`}
                        </span>
                      )}
                    </>
                  ) : (
                    <>
                      <DemoBadge lang={lang} />
                      <button className="button primary" onClick={() => verifyGate('lulus')}>
                        <Check size={16} />
                        {en ? 'Simulate Pass' : 'Simulasikan Lulus'}
                      </button>
                      <button className="button danger-outline" onClick={() => verifyGate('gagal')}>
                        <X size={16} />
                        {en ? 'Simulate Fail' : 'Simulasikan Gagal'}
                      </button>
                      <small>{en ? 'Does not upload evidence or save permanent records.' : 'Tidak mengunggah bukti atau menyimpan catatan.'}</small>
                    </>
                  )}
                </div>
              </div>

              <div className="verification-meter">
                <div>
                  <span>{en ? 'Demo gates passed' : 'Gerbang demo yang lulus'}</span>
                  <strong>{decision.passed}/4</strong>
                  <div className="meter-track">
                    <i style={{ width: `${decision.passed * 25}%` }} />
                  </div>
                </div>
                <div>
                  <span>{en ? 'Real evidence completeness' : 'Kelengkapan bukti nyata'}</span>
                  <strong>0%</strong>
                  <div className="meter-track empty" />
                  <small>{en ? 'All indicators remain illustrative.' : 'Seluruh indikator masih ilustratif.'}</small>
                </div>
                <div>
                  <span>{en ? 'Analytical confidence / error bounds' : 'Keyakinan / batas galat analitis'}</span>
                  <strong className="not-calibrated">{en ? 'Not calibrated' : 'Belum terkalibrasi'}</strong>
                  <small>
                    {en
                      ? 'No valid confidence percentage exists. Confidence is not a guarantee of truth.'
                      : 'Tidak ada persentase keyakinan yang sah. Keyakinan bukan jaminan kebenaran.'}
                  </small>
                </div>
              </div>

              <div className="abstention-banner" role="status">
                <span className="abstention-icon">
                  <LockKeyhole size={24} />
                </span>
                <div>
                  <span>{en ? 'DECISION STATUS' : 'STATUS KEPUTUSAN'}</span>
                  <h3>{decision.label}</h3>
                  <p>{decision.reason}</p>
                </div>
                <span className="withheld-pill">{en ? 'Official advisory withheld' : 'Anjuran resmi ditahan'}</span>
              </div>

              <details className="missing-evidence">
                <summary>
                  {en ? 'Evidence still required' : 'Bukti yang masih diperlukan'}
                  <span>
                    {missingEvidence.length} {en ? 'evidence groups' : 'kelompok bukti'}
                    <ChevronDown size={14} />
                  </span>
                </summary>
                <ul>
                  {missingEvidence.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </details>
            </section>

            <div className="audit-bottom">
              <span>
                <ShieldCheck size={16} />
                {en ? 'Simulation draft · Has no authorization force' : 'Draf simulasi · Tidak memiliki kekuatan otorisasi'}
              </span>
              <button
                className="button secondary"
                onClick={() => {
                  setGates(initialGates);
                  setActiveGate(0);
                  setSignedBy('');
                  setSignature('');
                  setAcknowledged(false);
                  setToast(en ? 'Simulation gates reset.' : 'Gerbang simulasi diatur ulang.');
                }}
              >
                {en ? 'Reset verification' : 'Atur ulang verifikasi'}
              </button>
              <button className="button primary" onClick={openShare} disabled={generating}>
                <ArrowDownToLine size={16} />
                {en ? 'Summary for discussion' : 'Ringkasan untuk diskusi'}
              </button>
            </div>
          </>
        )}
      </main>

      {/* TOAST NOTIFIKASI */}
      {toast && (
        <div className="toast" role="status">
          <Info size={18} />
          {toast}
          <button aria-label={en ? 'Close notification' : 'Tutup pemberitahuan'} onClick={() => setToast('')}>
            <X size={15} />
          </button>
        </div>
      )}

      {/* MODAL: SHARE RINGKASAN */}
      {modal === 'share' && share && (
        <Modal
          title={en ? 'Farmer Group Summary Preview' : 'Pratinjau Ringkasan Kelompok Tani'}
          closeLabel={en ? 'Close dialog' : 'Tutup dialog'}
          onClose={() => setModal(null)}
          className="share-modal"
        >
          <p className="modal-description">
            {en
              ? 'PNG card generated in browser. Review before downloading or testing share simulation.'
              : 'Kartu PNG dibuat di peramban. Tinjau sebelum mengunduh atau mencoba simulasi berbagi.'}
          </p>
          <div className="share-preview">
            <img
              src={share.url}
              alt={
                en
                  ? `Simulation Data summary card ${strategy.name} for Banyumas with abstention status`
                  : `Kartu ringkasan Data Simulasi ${strategy.name} untuk Banyumas dengan status abstain`
              }
            />
          </div>
          <div className="share-file-info">
            <span>
              <FileCheck2 size={15} />
              PNG · {number(share.size / 1000, 1)} KB
            </span>
            <span>
              <Check size={13} />
              {en ? 'Under 150 KB' : 'Di bawah 150 KB'}
            </span>
          </div>
          <div className="share-actions">
            <button className="button secondary" onClick={downloadShare}>
              <ArrowDownToLine size={16} />
              {en ? 'Download PNG Card' : 'Unduh Kartu PNG'}
            </button>
            <button
              className="button primary"
              onClick={() =>
                setShareFeedback(
                  en
                    ? 'Share simulation complete. No WhatsApp message was sent. Download the card to share manually.'
                    : 'Simulasi berbagi selesai. Tidak ada pesan WhatsApp yang dikirim. Unduh kartu untuk berbagi sendiri.'
                )
              }
            >
              <Share2 size={16} />
              {en ? 'Simulate Share' : 'Simulasikan Berbagi'}
            </button>
          </div>
          {shareFeedback && (
            <p className="share-feedback" role="status">
              <Check size={15} />
              {shareFeedback}
            </p>
          )}
          <p className="share-disclaimer">
            {en
              ? 'Not connected to WhatsApp. No messages or farmer data are transmitted.'
              : 'Tidak terhubung ke WhatsApp. Tidak ada pesan atau data petani yang dikirim.'}
          </p>
        </Modal>
      )}

      {/* MODAL: SUMBER & RESOLUSI DATA */}
      {modal === 'sources' && (
        <Modal
          title={en ? 'Data Sources & Resolution' : 'Sumber & Resolusi Data'}
          closeLabel={en ? 'Close dialog' : 'Tutup dialog'}
          onClose={() => setModal(null)}
        >
          <div className="source-modal-intro">
            <DemoBadge lang={lang} />
            {en
              ? 'All values in this prototype are simulated. No verified live NASA observations.'
              : 'Seluruh nilai dalam prototipe adalah simulasi. Tidak ada observasi NASA terverifikasi.'}
          </div>
          {layers.map((layer) => (
            <div className="source-modal-row" key={layer.id}>
              <div>
                <strong>{layer.name}</strong>
                <span>{layer.source}</span>
              </div>
              <span className="source-resolution">{layer.resolution}</span>
              <p>{layer.description}</p>
              <small>
                {en
                  ? 'Real data: Not Available · observation period: Not Available'
                  : 'Data nyata: Belum Tersedia · periode observasi: Belum Tersedia'}
              </small>
            </div>
          ))}
          <p className="modal-description">
            {en
              ? 'Agricultural photos and plot boundaries are illustrative. H3-7–9 are derived from valid synthetic H3 indices, not paddy masks.'
              : 'Foto pertanian dan batas petak bersifat ilustratif. H3-7–9 diturunkan dari indeks H3 sintetis valid, bukan mask sawah.'}
          </p>
        </Modal>
      )}

      {/* MODAL: TENTANG PROTOTIPE */}
      {modal === 'help' && (
        <Modal
          title={en ? 'About CYBER-KATAM' : 'Tentang CYBER-KATAM'}
          closeLabel={en ? 'Close dialog' : 'Tutup dialog'}
          onClose={() => setModal(null)}
        >
          <div className="about-symbol">
            <Sprout size={36} />
          </div>
          <h3>{en ? 'From observation to explainable decisions.' : 'Dari observasi menuju keputusan yang dapat dijelaskan.'}</h3>
          <p className="modal-description">
            {en
              ? 'This prototype demonstrates crop rotation exploration, deterministic climate simulation, and four audit gates. No live climate models, calibrated AI, NASA APIs, or digital signature services are connected.'
              : 'Prototipe ini memperagakan eksplorasi rotasi, simulasi iklim deterministik, dan empat gerbang audit. Tidak ada model iklim, AI terkalibrasi, API NASA, atau layanan tanda tangan digital yang terhubung.'}
          </p>
          <p className="modal-description">
            {en
              ? 'Colors, Pareto scores, biophysical values, and fiscal benefits are Simulation Data. Valid H3 geometry does not mean land cover or indicators are verified. Data resides only in this session’s memory.'
              : 'Warna, skor Pareto, nilai biofisika, dan manfaat fiskal adalah Data Simulasi. Geometri H3 valid tidak berarti tutupan lahan atau indikatornya terverifikasi. Data hanya berada di memori sesi ini.'}
          </p>
          <div className="modal-callout">
            {en
              ? 'Farmers and extension officers retain the final decision. The system withholds official advisories because real field evidence is not yet available.'
              : 'Petani dan PPL tetap memegang keputusan akhir. Sistem menahan anjuran resmi karena bukti nyata belum tersedia.'}
          </div>
        </Modal>
      )}

      {/* MODAL: PILIH PERIODE */}
      {modal === 'period' && (
        <Modal
          title={en ? 'Select Analysis Date' : 'Pilih Tanggal Analisis'}
          closeLabel={en ? 'Close dialog' : 'Tutup dialog'}
          onClose={() => setModal(null)}
        >
          <p className="modal-description">
            {en
              ? 'Select a daily date (up to 3 days ahead of today or historical dates since 2021).'
              : 'Pilih tanggal harian (maksimal 3 hari ke depan dari hari ini atau data historis hingga 2021).'}
          </p>
          <div className="period-options">
            {[-2, -1, 0, 1, 2, 3].map((offset) => {
              const d = addDays(today, offset);
              const label = formatDailyDate(d, lang);
              const active = isSameDay(d, selectedDate);
              return (
                <button
                  className="button secondary"
                  key={offset}
                  onClick={() => {
                    applyDateChange(d);
                    setModal(null);
                  }}
                >
                  {label}
                  {active && <Check size={16} />}
                </button>
              );
            })}
          </div>
        </Modal>
      )}
    </div>
  );
}

function HistoryCalendarPopover({
  lang = 'id',
  today,
  minDate,
  selectedDate,
  viewYear,
  viewMonth,
  setViewYear,
  setViewMonth,
  onSelectDate,
  onClose,
}) {
  const en = lang === 'en';
  const minYear = minDate.getFullYear();
  const maxYear = today.getFullYear();
  const years = [];
  for (let y = maxYear; y >= minYear; y--) {
    years.push(y);
  }

  const monthNames = en
    ? ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    : ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'];

  const dayHeaders = en
    ? ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']
    : ['Min', 'Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab'];

  const firstDayOfWeek = new Date(viewYear, viewMonth, 1).getDay();
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();

  const canPrevMonth = viewYear > minYear || (viewYear === minYear && viewMonth > 0);
  const canNextMonth = viewYear < maxYear || (viewYear === maxYear && viewMonth < today.getMonth());

  const stepMonth = (delta) => {
    let nextMonth = viewMonth + delta;
    let nextYear = viewYear;
    if (nextMonth < 0) {
      nextMonth = 11;
      nextYear -= 1;
    } else if (nextMonth > 11) {
      nextMonth = 0;
      nextYear += 1;
    }
    if (nextYear < minYear) return;
    if (nextYear > maxYear || (nextYear === maxYear && nextMonth > today.getMonth())) return;
    setViewYear(nextYear);
    setViewMonth(nextMonth);
  };

  const cells = [];
  for (let i = 0; i < firstDayOfWeek; i++) {
    cells.push(null);
  }
  for (let day = 1; day <= daysInMonth; day++) {
    cells.push(new Date(viewYear, viewMonth, day));
  }

  return (
    <div className="history-calendar-popover" role="dialog" aria-label={en ? 'Historical calendar' : 'Kalender historis'}>
      <div className="history-cal-header">
        <span className="history-cal-title">
          <Calendar size={13} />
          {en ? 'History Calendar (2021 – Today)' : 'Kalender Historis (2021 – Hari Ini)'}
        </span>
        <button type="button" className="history-cal-close" onClick={onClose} aria-label={en ? 'Close calendar' : 'Tutup kalender'}>
          <X size={14} />
        </button>
      </div>

      <div className="history-cal-controls">
        <button
          type="button"
          className="cal-step-btn"
          disabled={!canPrevMonth}
          onClick={() => stepMonth(-1)}
          aria-label={en ? 'Previous month' : 'Bulan sebelumnya'}
        >
          <ChevronLeft size={14} />
        </button>

        <div className="cal-selects">
          <select
            aria-label={en ? 'Select month' : 'Pilih bulan'}
            value={viewMonth}
            onChange={(e) => setViewMonth(Number(e.target.value))}
          >
            {monthNames.map((mName, idx) => {
              const disabledMonth = viewYear === maxYear && idx > today.getMonth();
              return (
                <option key={mName} value={idx} disabled={disabledMonth}>
                  {mName}
                </option>
              );
            })}
          </select>

          <select
            aria-label={en ? 'Select year' : 'Pilih tahun'}
            value={viewYear}
            onChange={(e) => {
              const nextY = Number(e.target.value);
              setViewYear(nextY);
              if (nextY === maxYear && viewMonth > today.getMonth()) {
                setViewMonth(today.getMonth());
              }
            }}
          >
            {years.map((yr) => (
              <option key={yr} value={yr}>
                {yr}
              </option>
            ))}
          </select>
        </div>

        <button
          type="button"
          className="cal-step-btn"
          disabled={!canNextMonth}
          onClick={() => stepMonth(1)}
          aria-label={en ? 'Next month' : 'Bulan berikutnya'}
        >
          <ChevronRight size={14} />
        </button>
      </div>

      <div className="history-cal-weekdays">
        {dayHeaders.map((d) => (
          <span key={d}>{d}</span>
        ))}
      </div>

      <div className="history-cal-grid">
        {cells.map((cellDate, idx) => {
          if (!cellDate) {
            return <span key={`empty-${idx}`} className="cal-day-empty" />;
          }
          const isFuture = cellDate > today;
          const isBeforeMin = cellDate < minDate;
          const disabled = isFuture || isBeforeMin;
          const isSelected = isSameDay(cellDate, selectedDate);
          const isToday = isSameDay(cellDate, today);

          return (
            <button
              key={cellDate.toISOString()}
              type="button"
              disabled={disabled}
              className={`cal-day-btn ${isSelected ? 'selected' : ''} ${isToday ? 'today' : ''}`}
              onClick={() => onSelectDate(cellDate)}
            >
              {cellDate.getDate()}
            </button>
          );
        })}
      </div>

      <div className="history-cal-footer">
        <button
          type="button"
          className="cal-today-btn"
          onClick={() => onSelectDate(today)}
        >
          {en ? 'Back to Today' : 'Kembali ke Hari Ini'}
        </button>
      </div>
    </div>
  );
}

function Slider({ label, unit, value, setValue, min, max, step, icon: Icon }) {
  return (
    <label className={`climate-slider ${unit === '%' ? 'rain-slider' : 'temperature-slider'}`}>
      <span>
        <Icon size={15} />
        {label}
        <strong>
          {value > 0 || unit === '°C' ? '+' : ''}
          {number(value, value % 1 ? 1 : 0)}
          {unit}
        </strong>
      </span>
      <input
        aria-label={label}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => setValue(Number(e.target.value))}
      />
      <span className="range-labels">
        <small>
          {min > 0 || unit === '°C' ? '+' : ''}
          {min}
          {unit}
        </small>
        <small>+{max}{unit}</small>
      </span>
    </label>
  );
}

function RiskMetric({ name, explanation, value, color, sourceNote = 'Data Simulasi', lang = 'id' }) {
  const en = lang === 'en';
  const level =
    value >= 0.7
      ? en
        ? 'High'
        : 'Tinggi'
      : value >= 0.45
      ? en
        ? 'Medium'
        : 'Sedang'
      : en
      ? 'Low / Optimal'
      : 'Rendah / Optimal';
  return (
    <div className={`risk-metric ${color}`}>
      <div>
        <span>{name}</span>
        <span className="risk-level">{level}</span>
      </div>
      <strong>{number(value)}</strong>
      <span className="risk-metric-description">{explanation}</span>
      <div className="risk-meter">
        <i style={{ width: `${Math.min(100, Math.max(0, value * 100))}%` }} />
      </div>
      <small>{sourceNote}</small>
    </div>
  );
}

function Pareto({ selected, onSelect, strategies, lang = 'id', embedded = false }) {
  const en = lang === 'en';
  return (
    <section className={embedded ? 'pareto-embedded' : 'pareto-panel'}>
      {!embedded && (
        <div className="pareto-title">
          <h3>{en ? 'Pareto Comparison' : 'Perbandingan Pareto'}</h3>
        </div>
      )}
      <div className="pareto-chart">
        <span className="chart-y-label">{en ? 'Soil benefit ↑' : 'Manfaat tanah ↑'}</span>
        <svg
          viewBox="0 0 290 138"
          aria-label={
            en
              ? 'Illustrative Pareto chart. B balances soil benefit score and water efficiency; not an optimization result.'
              : 'Grafik Pareto ilustratif. B menyeimbangkan skor manfaat tanah dan efisiensi air; bukan hasil optimasi.'
          }
        >
          <g stroke="#dfe8d9" strokeWidth="1" strokeDasharray="2 4">
            <path d="M32 18H270M32 52H270M32 86H270M32 120H270M32 18V120M90 18V120M148 18V120M206 18V120M264 18V120" />
          </g>
          <path d="M150 40Q185 12 220 31T263 72" stroke="#486c26" strokeWidth="1.2" strokeDasharray="4 4" fill="none" />
          {strategies.map((item) => {
            const x = 32 + item.waterScore * 2.45;
            const y = 122 - item.soilScore * 1.05;
            const pointColor = item.id === 'B' ? '#486c26' : item.id === 'C' ? '#ffd600' : '#889e85';
            return (
              <g
                className="pareto-point"
                key={item.id}
                role="button"
                aria-label={`${en ? 'Compare scenario' : 'Bandingkan skenario'} ${item.id}`}
                tabIndex="0"
                onClick={() => onSelect(item.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') onSelect(item.id);
                }}
              >
                <circle cx={x} cy={y} r={selected === item.id ? 13 : 8} fill={pointColor} fillOpacity=".16" />
                <circle cx={x} cy={y} r="4.5" fill={pointColor} />
                <text x={x + 10} y={y - 7} fill="#314f3c" fontSize="10" fontWeight="600">
                  {item.id}
                </text>
              </g>
            );
          })}
          <g fill="#6b8270" fontSize="8">
            <text x="27" y="134">0</text>
            <text x="251" y="134">100</text>
          </g>
        </svg>
        <span className="chart-x-label">{en ? 'Water efficiency →' : 'Efisiensi air →'}</span>
      </div>
      <div className="pareto-objectives">
        <span>{en ? 'Pest break' : 'Jeda hama'}</span>
        {strategies.map((item) => (
          <span key={item.id}>
            {item.id}
            <i>
              <b style={{ width: `${item.pestScore}%` }} />
            </i>
            {item.pestScore}
          </span>
        ))}
      </div>
    </section>
  );
}

function BlockTitle({ index, icon: Icon, title, subtitle, lang = 'id' }) {
  const en = lang === 'en';
  return (
    <div className="block-title">
      <span className="block-icon">
        <Icon size={21} />
      </span>
      <div>
        <span className="micro-label">
          {en ? 'BLOCK' : 'BLOK'} {index}
        </span>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
      <span className="block-index">{index}</span>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
