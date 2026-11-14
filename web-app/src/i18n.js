import { strategies as baseStrategies, layers as baseLayers, gateDefinitions as baseGates, missingEvidence as baseMissing, decisionState as baseDecisionState } from './model';

export const periodOptionsByLang = {
  id: ['1–10 November 2026', '11–20 November 2026', '21–30 November 2026'],
  en: ['1–10 November 2026', '11–20 November 2026', '21–30 November 2026'],
};

const strategiesEn = {
  A: {
    name: 'Rice – Fallow',
    short: 'Rice – Fallow',
    label: 'Current Pattern',
    crops: ['Rice', 'Fallow'],
    water: 'High water demand',
    nitrogen: 'Chemical fertilizer still required',
    pests: 'Rice pest cycle may persist',
    note: 'Baseline pattern with a fallow period after rice harvest.',
    why: 'Serves as a baseline against current practice. Actual pattern, fallow duration, and residue management still require confirmation.',
    benefit: 'Maintains familiar farming skills and existing equipment.',
    risk: 'Bare soil may be exposed to extreme rainfall and nutrient loss.',
  },
  B: {
    name: 'Rice – Anjasmoro Soybean',
    short: 'Rice – Soybean',
    label: 'Top Recommendation',
    crops: ['Rice', 'Anjasmoro Soybean'],
    water: 'Potentially more water-efficient',
    nitrogen: 'Potential natural nitrogen addition',
    pests: 'Non-host crop to break pest cycles',
    note: 'Leading alternative in the simulation demo, not an official planting advisory.',
    why: 'In this example, combining rice and legumes provides an illustrative balance between water demand, soil health, and host-crop breaks.',
    benefit: 'Legumes can add nitrogen via biological fixation. Diversification helps break pest cycles when coordinated across fields.',
    risk: 'Soybean is sensitive to waterlogging. Drainage, Anjasmoro seeds, inoculants, and market off-takers must be verified.',
  },
  C: {
    name: 'Rice – Mung Bean',
    short: 'Rice – Mung Bean',
    label: 'Alternative Option',
    crops: ['Rice', 'Mung Bean'],
    water: 'Potentially lower water requirement',
    nitrogen: 'Legume supports soil management',
    pests: 'Helps provide a host-crop break',
    note: 'Diversification option that still requires local agronomic assessment.',
    why: 'Mung bean is shown as a legume alternative for dry-season discussion, not a verified optimization output.',
    benefit: 'Potentially diversifies income and increases ground cover during the transition period.',
    risk: 'Check early water availability, harvest timing, disease pressure, and local market access.',
  },
};

const layersEn = {
  smap: {
    title: 'Soil moisture',
    value: '0.39 m³/m³',
    period: 'Dekad 19 · 2025',
    description: 'Root-zone soil moisture; one pixel covers multiple H3 cells. Real pipeline data.',
  },
  eco: {
    title: 'Evaporative stress & temperature',
    value: '32.1 °C',
    period: 'Dekad 19 · 2025',
    description: 'LST available in LSTE product. Separate ESI source not yet selected.',
  },
  hls: {
    title: 'Vegetation & spectral',
    value: 'NDVI 0.77',
    period: 'Dekad 19 · 2025',
    description: 'Real surface reflectance. High NDVI (>0.6) indicates dense/healthy vegetation.',
  },
  gpm: {
    title: 'Precipitation',
    value: '60.5 mm / 10 days',
    period: 'Dekad 19 · 2025',
    description: 'Native resolution 0.1°; mm/hr rate must be explicitly aggregated.',
  },
  srtm: {
    title: 'Elevation & topography',
    value: 'Not Available',
    period: 'Static (2000)',
    description: 'Topography does not reflect actual plot-level drainage conditions.',
  },
};

const gatesEn = [
  {
    title: 'Sensor Validity',
    owner: 'Data analyst',
    description: 'Verify observation age, cloud cover, sensor angle, QA flags, and spatial scale.',
    missing: 'Inspected NASA export, acquisition timestamp, and QA metadata not yet available.',
  },
  {
    title: 'Field Drainage',
    owner: 'Extension officer & farmer',
    description: 'Ensure no waterlogging, blocked canals, or conflicting field conditions.',
    missing: 'Drainage inspection and soil hydraulic profile not yet available.',
  },
  {
    title: 'Seed / Inoculant Availability',
    owner: 'Farmer group',
    description: 'Confirm seeds, inoculants, labor, and operational readiness.',
    missing: 'Actual availability not yet confirmed by the farmer group.',
  },
  {
    title: 'PPL Digital Signature Authorization',
    owner: 'Field extension officer',
    description: 'Authorize only after all evidence and feasibility have been reviewed together.',
    missing: 'No verified identity or digital signature available.',
  },
];

const missingEvidenceEn = [
  'Inspected NASA observations and QA metadata',
  'Real climatology and calibrated error bounds',
  'Actual plot drainage, soil pH, and field conditions',
  'Confirmation of seeds, inoculants, costs, and market',
];

export function getStrategies(lang = 'id') {
  if (lang !== 'en') return baseStrategies;
  return baseStrategies.map((item) => ({
    ...item,
    ...(strategiesEn[item.id] || {}),
  }));
}

export function getLayers(lang = 'id') {
  if (lang !== 'en') return baseLayers;
  return baseLayers.map((layer) => ({
    ...layer,
    ...(layersEn[layer.id] || {}),
  }));
}

export function getGateDefinitions(lang = 'id') {
  if (lang !== 'en') return baseGates;
  return baseGates.map((gate, i) => ({
    ...gate,
    ...(gatesEn[i] || {}),
  }));
}

export function getMissingEvidence(lang = 'id') {
  return lang === 'en' ? missingEvidenceEn : baseMissing;
}

export function getSimulationSummary(rain, temperature, lang = 'id', fallbackSummary = '') {
  if (lang !== 'en') return fallbackSummary;
  if (rain < 0) return 'Drier conditions: prioritize irrigation sufficiency and ground cover.';
  if (rain > 0) return 'Increased rainfall: check waterlogging risk and drainage capacity.';
  if (temperature > 0) return 'Higher temperature: review water demand and planting window with extension officers.';
  return 'Baseline scenario: evaluate legume rotation with drainage and seed availability verification.';
}

export function getDecisionState(gates = [], lang = 'id') {
  const base = baseDecisionState(gates);
  if (lang !== 'en') return base;
  return {
    ...base,
    label: 'Abstain — Insufficient Data',
    reason: gates.includes('gagal')
      ? 'A simulation gate failed. Official recommendations cannot be issued.'
      : 'Real data and verified authorization are not yet available. Demo pass is not field evidence.',
  };
}
