"""
web-app/scripts/ingest_meteomatics_live.py
------------------------------------------
Ingestor LIVE Meteomatics -> grid H3 sawah (4.143 sel res-9).

Mengambil observasi cuaca kasar dari titik kasar (coarse) Meteomatics, lalu memproyeksikannya
ke seluruh sel sawah memakai operator Point-Spread Function (PSF) Gaussian berpenormalan
massa per sel halus (bobot sum_i W_ji = 1). Skema keluaran 17 kolom identik dengan
meteomatics_banyumas_h3_1000.parquet dari tim perancang rumus, sehingga langsung dapat
dikonsumsi oleh PVRSEngine.evaluate_meteomatics_h3_cohort / BFEHSIEngine.

Jendela agregasi = 24 jam terakhir (cocok dengan semantik snapshot tim rumus):
  mm_t2m_mean_c      = t_mean_2m_24h:C            (rata-rata suhu 2 m 24 jam)
  mm_tmax_p95_c      = persentil-95 t_2m:C        (seri per jam 24 jam)
  mm_precip_total_mm = precip_24h:mm              (total hujan 24 jam)
  mm_precip_max_1h_mm= maksimum precip_1h:mm      (seri per jam 24 jam)
  mm_et_total_mm     = evapotranspiration_24h:mm  (ET 24 jam)
  mm_smi_mean        = volumetric_soil_water_mean_-50cm_24h:m3m3 (lengas zona akar, m3/m3)
  mm_wind_mean_ms    = wind_speed_mean_10m_24h:ms

mm_lst_anomaly_c BUKAN medan Meteomatics (tidak ada LST di API cuaca). Diisi dari
klimatologi satelit statis (LST MODIS dekad terkini - mu multi-tahun) dan ditandai
provenance "static_satellite_climatology"; pipeline satelit tim data yang akan
menggantinya dengan anomali LST live. Engine memakai medan ini hanya untuk kontrak/UI.

Mode:
  (default)   jalankan ingest live penuh, tulis parquet + CSV + JSON provenance
  --dry-run   tanpa panggilan API: bangun titik kasar + bobot PSF + field struktural,
              cuaca = NaN, tidak menulis artefak final (hanya lapor geometri)
  --probe     ambil 1 titik kasar, cetak nilai (verifikasi cepat, 2 request)
  --limit N   batasi jumlah titik kasar ke N (uji hemat kuota)
  --valid-time ISO  waktu valid UTC (default: jam UTC sekarang)

Kredensial dibaca dari .env (METEOMATICS_USERNAME / METEOMATICS_PASSWORD); nilai
tidak pernah dicetak. Semua permintaan dihitung dan dilaporkan untuk audit kuota.
"""

import argparse
import base64
import json
import math
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import h3
import numpy as np
import pandas as pd

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))

PADDY_GRID = root / "data" / "processed" / "banyumas_h3_paddy_grid.geojson"
WIDE_PADDY = root / "data" / "processed" / "banyumas_indicators_wide_paddy.parquet"
CLIM_PADDY = root / "data" / "processed" / "climatology_baseline_banyumas_paddy.parquet"
SNAPSHOT = root / "data" / "processed" / "meteomatics_banyumas_h3_1000.parquet"
OUT_PARQUET = root / "data" / "processed" / "meteomatics_banyumas_h3_paddy_live.parquet"

PSF_FWHM_KM = 9.0          # dukungan antena L-band, sama dengan engine
COARSE_SPACING_KM = 9.0    # spasi titik kasar ~ FWHM agar interpolasi well-posed
COARSE_KEEP_KM = 13.5      # buang titik kasar > 1.5x FWHM dari sel sawah mana pun
WINDOW_HOURS = 24
KM_PER_DEG_LAT = 111.0

# Request A: agregat 24 jam pada satu waktu valid (5 medan langsung).
PARAMS_AGG = [
    "t_mean_2m_24h:C",
    "precip_24h:mm",
    "evapotranspiration_24h:mm",
    # Engine memakai mm_smi_mean sebagai sm_root_actual (m3/m3, 0-100 cm). Indeks SMI
    # (idx) bisa >1 dan melebihi porositas tanah, jadi dipakai air tanah volumetrik zona akar.
    "volumetric_soil_water_mean_-50cm_24h:m3m3",
    "wind_speed_mean_10m_24h:ms",
]
# Request B: seri per jam 24 jam untuk p95 suhu & maksimum hujan per jam.
PARAMS_HOURLY = ["t_2m:C", "precip_1h:mm"]

SCHEMA = [
    "h3_index", "h3_parent_res8", "h3_parent_res7", "centroid_lat", "centroid_lon",
    "mm_t2m_mean_c", "mm_tmax_p95_c", "mm_precip_max_1h_mm", "mm_precip_total_mm",
    "mm_et_total_mm", "mm_smi_mean", "mm_wind_mean_ms",
    "source_coarse_lat", "source_coarse_lon", "psf_nearest_dist_km",
    "mm_lst_anomaly_c", "h7_cluster_precip_mm",
]


def load_env(path: Path) -> dict:
    env = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


class MeteomaticsClient:
    """Klien REST minimal dengan Basic Auth; menghitung request untuk audit kuota."""

    def __init__(self, user: str, password: str):
        self._token = base64.b64encode(f"{user}:{password}".encode()).decode()
        self.requests = 0

    def get_json(self, url: str, retries: int = 2) -> dict:
        last_err = None
        for attempt in range(retries + 1):
            self.requests += 1
            req = urllib.request.Request(url, headers={"Authorization": f"Basic {self._token}"})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")
                # 4xx (parameter/URL salah) tidak berguna di-retry; lempar langsung.
                if 400 <= e.code < 500:
                    raise RuntimeError(f"Meteomatics HTTP {e.code}: {body[:500]} | url={url}") from e
                last_err = RuntimeError(f"Meteomatics HTTP {e.code}: {body[:200]}")
            except (urllib.error.URLError, TimeoutError) as e:
                last_err = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"Meteomatics gagal setelah {retries + 1} percobaan: {last_err}")


def _series_values(payload: dict, parameter: str) -> list:
    for p in payload.get("data", []):
        if p.get("parameter") == parameter:
            dates = p.get("coordinates", [{}])[0].get("dates", [])
            out = []
            for d in dates:
                v = d.get("value")
                if v is None:
                    continue
                v = float(v)
                # Meteomatics menandai data hilang dengan sentinel -666 / -999.
                if v < -600.0:
                    continue
                out.append(v)
            return out
    return []


def _agg_value(payload: dict, parameter: str):
    vals = _series_values(payload, parameter)
    return float(vals[0]) if vals else None


def fetch_coarse(client: MeteomaticsClient, lat: float, lon: float, valid: datetime) -> dict:
    """Dua request per titik kasar: agregat 24 jam + seri per jam 24 jam."""
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    vt = valid.strftime(fmt)
    start = (valid - timedelta(hours=WINDOW_HOURS)).strftime(fmt)
    base = f"https://api.meteomatics.com"
    loc = f"{lat:.5f},{lon:.5f}"

    url_a = f"{base}/{vt}/{','.join(PARAMS_AGG)}/{loc}/json"
    agg = client.get_json(url_a)

    url_b = f"{base}/{start}--{vt}:PT1H/{','.join(PARAMS_HOURLY)}/{loc}/json"
    hourly = client.get_json(url_b)

    t_hourly = _series_values(hourly, "t_2m:C")
    p_hourly = _series_values(hourly, "precip_1h:mm")

    return {
        "mm_t2m_mean_c": _agg_value(agg, "t_mean_2m_24h:C"),
        "mm_precip_total_mm": _agg_value(agg, "precip_24h:mm"),
        "mm_et_total_mm": _agg_value(agg, "evapotranspiration_24h:mm"),
        "mm_smi_mean": _agg_value(agg, "volumetric_soil_water_mean_-50cm_24h:m3m3"),
        "mm_wind_mean_ms": _agg_value(agg, "wind_speed_mean_10m_24h:ms"),
        "mm_tmax_p95_c": float(np.percentile(t_hourly, 95)) if t_hourly else None,
        "mm_precip_max_1h_mm": float(max(p_hourly)) if p_hourly else None,
    }


def load_fine_cells() -> pd.DataFrame:
    gj = json.loads(PADDY_GRID.read_text(encoding="utf-8"))
    rows = []
    for ft in gj["features"]:
        idx = ft["properties"]["h3_index"]
        lat, lon = h3.cell_to_latlng(idx)
        rows.append({"h3_index": idx, "centroid_lat": lat, "centroid_lon": lon})
    return pd.DataFrame(rows)


def build_coarse_points(fine: pd.DataFrame) -> np.ndarray:
    """Grid kasar reguler ~9 km di atas bbox sawah, dipangkas agar hanya yang berpengaruh."""
    ref_lat = float(fine["centroid_lat"].mean())
    coslat = math.cos(math.radians(ref_lat))
    step_lat = COARSE_SPACING_KM / KM_PER_DEG_LAT
    step_lon = COARSE_SPACING_KM / (KM_PER_DEG_LAT * coslat)
    margin = 0.04
    lats = np.arange(fine["centroid_lat"].min() - margin, fine["centroid_lat"].max() + margin, step_lat)
    lons = np.arange(fine["centroid_lon"].min() - margin, fine["centroid_lon"].max() + margin, step_lon)
    cand = np.array([[la, lo] for la in lats for lo in lons])

    fine_km = latlon_to_km(fine["centroid_lat"].values, fine["centroid_lon"].values, ref_lat)
    keep = []
    for la, lo in cand:
        ckm = latlon_to_km(np.array([la]), np.array([lo]), ref_lat)[0]
        d = np.sqrt(((fine_km - ckm) ** 2).sum(axis=1)).min()
        if d <= COARSE_KEEP_KM:
            keep.append([la, lo])
    return np.array(keep)


def latlon_to_km(lat, lon, ref_lat: float) -> np.ndarray:
    """Proyeksi equirectangular lokal (km) konsisten dengan koordinat km engine."""
    coslat = math.cos(math.radians(ref_lat))
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    return np.column_stack([lon * KM_PER_DEG_LAT * coslat, lat * KM_PER_DEG_LAT])


def psf_coarse_to_fine(coarse_km: np.ndarray, fine_km: np.ndarray, fwhm_km: float = PSF_FWHM_KM):
    """Bobot interpolasi Gaussian W (N_fine x M_coarse), normalisasi per sel halus.

    Arah coarse->fine (kebalikan operator forward H engine): setiap sel halus adalah
    kombinasi konveks observasi kasar, sum_i W_ji = 1 (kekekalan massa per sel).
    """
    sigma = fwhm_km / (2.0 * math.sqrt(2.0 * math.log(2.0)))
    diff = fine_km[:, None, :] - coarse_km[None, :, :]
    dist_sq = (diff ** 2).sum(axis=-1)
    k = np.exp(-dist_sq / (2.0 * sigma ** 2))
    row_sums = k.sum(axis=1, keepdims=True)
    row_sums = np.where(row_sums == 0.0, 1.0, row_sums)
    w = k / row_sums
    nearest_idx = dist_sq.argmin(axis=1)
    nearest_dist = np.sqrt(dist_sq.min(axis=1))
    return w, nearest_idx, nearest_dist


def static_lst_anomaly(fine: pd.DataFrame) -> pd.Series:
    """Anomali LST statis dari klimatologi satelit (bukan live; ditandai provenance)."""
    nan = pd.Series(np.nan, index=fine.index)
    if not WIDE_PADDY.exists() or not CLIM_PADDY.exists():
        return nan
    wide = pd.read_parquet(WIDE_PADDY, columns=["h3_index", "year", "dekad", "LST_MODIS_C"])
    clim = pd.read_parquet(CLIM_PADDY, columns=["h3_index", "LST_MODIS_C_mu"])
    curr = wide[(wide["year"] == 2026) & (wide["dekad"] == 30)][["h3_index", "LST_MODIS_C"]]
    merged = curr.merge(clim, on="h3_index", how="inner")
    merged["anom"] = merged["LST_MODIS_C"] - merged["LST_MODIS_C_mu"]
    lookup = dict(zip(merged["h3_index"], merged["anom"]))
    return fine["h3_index"].map(lookup).astype(float)


def assemble(fine: pd.DataFrame, coarse: np.ndarray, obs: list, lst_anom: pd.Series) -> pd.DataFrame:
    ref_lat = float(fine["centroid_lat"].mean())
    fine_km = latlon_to_km(fine["centroid_lat"].values, fine["centroid_lon"].values, ref_lat)
    coarse_km = latlon_to_km(coarse[:, 0], coarse[:, 1], ref_lat)
    w, nearest_idx, nearest_dist = psf_coarse_to_fine(coarse_km, fine_km)

    df = fine.copy()
    df["h3_parent_res8"] = df["h3_index"].map(lambda x: h3.cell_to_parent(x, 8))
    df["h3_parent_res7"] = df["h3_index"].map(lambda x: h3.cell_to_parent(x, 7))

    weather_fields = [
        "mm_t2m_mean_c", "mm_tmax_p95_c", "mm_precip_max_1h_mm", "mm_precip_total_mm",
        "mm_et_total_mm", "mm_smi_mean", "mm_wind_mean_ms",
    ]
    obs_df = pd.DataFrame(obs)
    for field in weather_fields:
        y = obs_df[field].to_numpy(dtype=float)
        valid = np.isfinite(y)
        if not valid.any():
            df[field] = np.nan
        elif valid.all():
            df[field] = w @ y
        else:
            # Renormalisasi bobot hanya atas coarse valid; sel tanpa dukungan -> NaN.
            wv = w[:, valid]
            rs = wv.sum(axis=1)
            vals = np.full(len(df), np.nan)
            good = rs > 0
            vals[good] = (wv[good] / rs[good, None]) @ y[valid]
            df[field] = vals

    df["source_coarse_lat"] = coarse[nearest_idx, 0]
    df["source_coarse_lon"] = coarse[nearest_idx, 1]
    df["psf_nearest_dist_km"] = np.round(nearest_dist, 3)
    df["mm_lst_anomaly_c"] = np.round(lst_anom.values, 3)
    df["h7_cluster_precip_mm"] = np.round(
        df.groupby("h3_parent_res7")["mm_precip_total_mm"].transform("mean"), 2
    )
    return df[SCHEMA]


def validate(df: pd.DataFrame) -> dict:
    report = {"n_cells": len(df), "schema_matches_snapshot": False, "overlap_with_snapshot": 0}
    report["schema_matches_snapshot"] = list(df.columns) == SCHEMA
    if SNAPSHOT.exists():
        snap = pd.read_parquet(SNAPSHOT, columns=["h3_index"])
        report["overlap_with_snapshot"] = int(df["h3_index"].isin(snap["h3_index"]).sum())
    ranges = {}
    for c in ["mm_t2m_mean_c", "mm_tmax_p95_c", "mm_precip_total_mm", "mm_precip_max_1h_mm",
              "mm_et_total_mm", "mm_smi_mean", "mm_wind_mean_ms", "psf_nearest_dist_km"]:
        s = df[c].dropna()
        ranges[c] = {"min": round(float(s.min()), 3), "max": round(float(s.max()), 3),
                     "nulls": int(df[c].isna().sum())} if len(s) else {"nulls": int(df[c].isna().sum())}
    report["value_ranges"] = ranges
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingestor live Meteomatics -> 4.143 sel H3 sawah")
    ap.add_argument("--dry-run", action="store_true", help="tanpa API; hanya geometri + bobot PSF")
    ap.add_argument("--probe", action="store_true", help="ambil 1 titik kasar, cetak nilai")
    ap.add_argument("--limit", type=int, default=0, help="batasi jumlah titik kasar (uji kuota)")
    ap.add_argument("--valid-time", type=str, default="", help="waktu valid UTC ISO (default: sekarang)")
    args = ap.parse_args()

    if not PADDY_GRID.exists():
        print(f"ERROR: grid sawah tidak ditemukan: {PADDY_GRID}")
        return 2
    fine = load_fine_cells()
    coarse = build_coarse_points(fine)
    if args.limit > 0:
        coarse = coarse[: args.limit]
    print(f"sel_sawah: {len(fine)} | titik_kasar: {len(coarse)} | PSF_FWHM_km: {PSF_FWHM_KM}")

    valid = (
        datetime.fromisoformat(args.valid_time.replace("Z", "+00:00"))
        if args.valid_time
        else datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    )

    if args.dry_run:
        ref_lat = float(fine["centroid_lat"].mean())
        fine_km = latlon_to_km(fine["centroid_lat"].values, fine["centroid_lon"].values, ref_lat)
        coarse_km = latlon_to_km(coarse[:, 0], coarse[:, 1], ref_lat)
        w, nearest_idx, nearest_dist = psf_coarse_to_fine(coarse_km, fine_km)
        print(f"[dry-run] bobot W shape: {w.shape} | row-sum~1: {np.allclose(w.sum(axis=1), 1.0)}")
        print(f"[dry-run] jarak coarse terdekat km: min={nearest_dist.min():.2f} "
              f"median={np.median(nearest_dist):.2f} max={nearest_dist.max():.2f}")
        print(f"[dry-run] request API yang akan dipakai (live): {2 * len(coarse)}")
        print("[dry-run] tidak ada panggilan API, tidak ada artefak ditulis.")
        return 0

    env = load_env(root / ".env")
    user, pw = env.get("METEOMATICS_USERNAME"), env.get("METEOMATICS_PASSWORD")
    print("credentials_present:", bool(user), bool(pw))
    if not user or not pw:
        print("ERROR: isi .env (METEOMATICS_USERNAME / METEOMATICS_PASSWORD) dulu.")
        return 2
    client = MeteomaticsClient(user, pw)

    if args.probe:
        obs = fetch_coarse(client, float(coarse[0, 0]), float(coarse[0, 1]), valid)
        print(f"[probe] titik kasar {coarse[0].tolist()} valid={valid.isoformat()}")
        for k, v in obs.items():
            print(f"  {k} = {v}")
        print(f"[probe] request dipakai: {client.requests}")
        return 0

    print(f"Memulai ingest live {len(coarse)} titik kasar (2 request/titik)...")
    obs = []
    t0 = time.time()
    for i, (la, lo) in enumerate(coarse):
        obs.append(fetch_coarse(client, float(la), float(lo), valid))
        if (i + 1) % 10 == 0 or i + 1 == len(coarse):
            print(f"  coarse {i + 1}/{len(coarse)} | request={client.requests} | {time.time() - t0:.1f}s")
    fetch_sec = time.time() - t0

    lst_anom = static_lst_anomaly(fine)
    df = assemble(fine, coarse, obs, lst_anom)
    report = validate(df)

    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PARQUET, index=False)
    df.to_csv(OUT_PARQUET.with_suffix(".csv"), index=False)

    provenance = {
        "source": "LIVE_METEOMATICS_REST",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "valid_time_utc": valid.isoformat(),
        "window_hours": WINDOW_HOURS,
        "n_paddy_cells": len(fine),
        "n_coarse_points": len(coarse),
        "api_requests": client.requests,
        "api_fetch_duration_sec": round(fetch_sec, 3),
        "psf_fwhm_km": PSF_FWHM_KM,
        "psf_normalization": "per_fine_cell_convex_combination (sum_i W_ji = 1)",
        "aggregations": {
            "mm_t2m_mean_c": "t_mean_2m_24h:C",
            "mm_tmax_p95_c": "percentile95(t_2m:C hourly 24h)",
            "mm_precip_total_mm": "precip_24h:mm",
            "mm_precip_max_1h_mm": "max(precip_1h:mm hourly 24h)",
            "mm_et_total_mm": "evapotranspiration_24h:mm",
            "mm_smi_mean": "volumetric_soil_water_mean_-50cm_24h:m3m3 (zona akar, m3/m3)",
            "mm_wind_mean_ms": "wind_speed_mean_10m_24h:ms",
            "mm_lst_anomaly_c": "static_satellite_climatology (LST MODIS 2026 dekad30 - mu); NOT live",
        },
        "interpolation_provenance": "NEAREST_NEIGHBOR_PSF (bukan observasi per sel; akurasi menurun dgn jarak)",
        "credentials_present": True,
        "validation": report,
    }
    prov_path = OUT_PARQUET.with_name(OUT_PARQUET.stem + "_provenance.json")
    prov_path.write_text(json.dumps(provenance, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nSelesai. {len(df)} sel -> {OUT_PARQUET.name}")
    print(f"request API: {client.requests} | fetch: {fetch_sec:.2f}s")
    print(f"schema cocok snapshot: {report['schema_matches_snapshot']} | "
          f"overlap snapshot: {report['overlap_with_snapshot']} sel")
    print(f"provenance -> {prov_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())