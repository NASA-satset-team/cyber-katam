"""
web-app/scripts/ingest_meteomatics_forecast_3d.py
-------------------------------------------------
Ingestor FORECAST 3 hari ke depan (H+1, H+2, H+3) Meteomatics -> grid H3 sawah 4.143 sel res-9.

Port dari (prediction)meteomatics_3day_forecast_h3.py milik tim data yang masih memakai grid
lama 1.000 sel (disk k-ring). Di sini sumber grid diganti data-driven ke
banyumas_h3_paddy_grid.geojson (4.143 sel sawah otoritatif), sehingga ID H3 sinkron dengan
pipeline live/evaluator kita. Operator PSF Gaussian (sum_i W_ji = 1 per sel halus) dan
agregasi jam->hari dengan koreksi interval dipertahankan dari skrip asal.

Skema keluaran 17 kolom identik dengan meteomatics_forecast_3d_h3_1000.parquet tim data
agar dapat dikonsumsi langsung oleh tactical_3day_forecaster.py setelah di-port.

Kredensial dibaca dari .env (METEOMATICS_USERNAME / METEOMATICS_PASSWORD); tidak pernah
hardcoded dan tidak pernah dicetak. Semua permintaan dihitung untuk audit kuota.

Mode:
  (default)   ingest forecast live penuh, tulis parquet + CSV + JSON provenance
  --dry-run   tanpa API: bangun titik kasar + bobot PSF, lapor geometri & estimasi request
  --limit N   batasi jumlah titik kasar ke N (uji hemat kuota)
"""

import argparse
import base64
import io
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

PADDY_GRID = root / "data" / "processed" / "banyumas_h3_paddy_grid.geojson"
OUT_PARQUET = root / "data" / "processed" / "meteomatics_forecast_3d_h3_paddy.parquet"

PSF_FWHM_KM = 2.5
FORECAST_DAYS = 3
CHUNK_COORDS = 25
KM_PER_DEG_LAT = 111.0
WIB = timezone(timedelta(hours=7))

CORE_PARAMS = ["t_2m:C", "precip_1h:mm", "wind_speed_10m:ms", "relative_humidity_2m:p"]

SCHEMA = [
    "h3_index", "h3_parent_res8", "h3_parent_res7", "centroid_lat", "centroid_lon",
    "day_offset", "horizon_code", "forecast_date",
    "fc_tmean_c", "fc_tmax_c", "fc_precip_total_mm", "fc_precip_max_1h_mm",
    "fc_eto_total_mm", "fc_smi_mean", "fc_wind_max_ms",
    "h7_cluster_fc_rain_mm", "forecast_source_mode",
]
METRIC_COLS = [
    "fc_tmean_c", "fc_tmax_c", "fc_precip_total_mm", "fc_precip_max_1h_mm",
    "fc_eto_total_mm", "fc_smi_mean", "fc_wind_max_ms",
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
    """Klien REST minimal Basic Auth; menghitung request untuk audit kuota."""

    def __init__(self, user: str, password: str):
        self._token = base64.b64encode(f"{user}:{password}".encode()).decode()
        self.requests = 0

    def get_text(self, url: str, retries: int = 2) -> str:
        last_err = None
        for attempt in range(retries + 1):
            self.requests += 1
            req = urllib.request.Request(url, headers={"Authorization": f"Basic {self._token}"})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    return r.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")
                if 400 <= e.code < 500:
                    raise RuntimeError(f"Meteomatics HTTP {e.code}: {body[:500]}") from e
                last_err = RuntimeError(f"Meteomatics HTTP {e.code}: {body[:200]}")
            except (urllib.error.URLError, TimeoutError) as e:
                last_err = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"Meteomatics gagal setelah {retries + 1} percobaan: {last_err}")


def load_fine_cells() -> pd.DataFrame:
    gj = json.loads(PADDY_GRID.read_text(encoding="utf-8"))
    rows = []
    for ft in gj["features"]:
        idx = ft["properties"]["h3_index"]
        lat, lon = h3.cell_to_latlng(idx)
        rows.append({
            "h3_index": idx,
            "h3_parent_res8": h3.cell_to_parent(idx, 8),
            "h3_parent_res7": h3.cell_to_parent(idx, 7),
            "centroid_lat": lat,
            "centroid_lon": lon,
        })
    return pd.DataFrame(rows)


def build_coarse_h8(fine: pd.DataFrame) -> np.ndarray:
    """Titik kasar = centroid kluster induk H3-8 dari sel sawah (data-driven, bukan disk)."""
    g = (
        fine.groupby("h3_parent_res8", as_index=False)
        .agg(lat=("centroid_lat", "mean"), lon=("centroid_lon", "mean"))
        .sort_values(["lat", "lon"])
        .reset_index(drop=True)
    )
    return g[["lat", "lon"]].to_numpy(dtype=float)


def latlon_to_km(lat, lon, ref_lat: float) -> np.ndarray:
    coslat = math.cos(math.radians(ref_lat))
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    return np.column_stack([lon * KM_PER_DEG_LAT * coslat, lat * KM_PER_DEG_LAT])


def psf_weights(coarse_km: np.ndarray, fine_km: np.ndarray, fwhm_km: float = PSF_FWHM_KM):
    sigma = fwhm_km / (2.0 * math.sqrt(2.0 * math.log(2.0)))
    diff = fine_km[:, None, :] - coarse_km[None, :, :]
    dist_sq = (diff ** 2).sum(axis=-1)
    k = np.exp(-dist_sq / (2.0 * sigma ** 2))
    row_sums = k.sum(axis=1, keepdims=True)
    row_sums = np.where(row_sums == 0.0, 1.0, row_sums)
    return k / row_sums


def assign_wib_day_offset(df: pd.DataFrame, now_utc: datetime) -> pd.DataFrame:
    df = df.copy()
    df["validdate"] = pd.to_datetime(df["validdate"], utc=True)
    hours_ahead = (df["validdate"] - now_utc).dt.total_seconds() / 3600.0
    df["day_offset"] = np.clip(np.ceil(hours_ahead / 24.0).astype(int), 1, FORECAST_DAYS)
    base_date_wib = now_utc.astimezone(WIB).date()
    date_map = {d: (base_date_wib + timedelta(days=d)).isoformat() for d in (1, 2, 3)}
    df["forecast_date"] = df["day_offset"].map(date_map)
    return df


def complete_derived_agro_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Turunkan tmax/ET/SMI secara fisis bila tier akun hanya mengembalikan 4 parameter inti."""
    df = df.copy()
    if "t_max_2m_24h:C" not in df.columns:
        df["t_max_2m_24h:C"] = df.groupby(["lat", "lon", "day_offset"])["t_2m:C"].transform("max")
    if "evapotranspiration_1h:mm" not in df.columns:
        rh = df["relative_humidity_2m:p"] if "relative_humidity_2m:p" in df.columns else 75.0
        vpd = np.clip((100.0 - rh) / 100.0, 0.05, 0.85)
        df["evapotranspiration_1h:mm"] = np.round(
            np.clip(0.015 * np.maximum(df["t_2m:C"] - 10.0, 0.0) * vpd, 0.03, 0.68), 4
        )
    if "soil_moisture_index_-15cm:idx" not in df.columns:
        net = df["precip_1h:mm"] - df["evapotranspiration_1h:mm"]
        df["soil_moisture_index_-15cm:idx"] = np.round(
            np.clip(0.27 + 0.020 * np.tanh(net / 4.5), 0.12, 0.46), 4
        )
    return df


def fetch_forecast(client: MeteomaticsClient, coarse: np.ndarray, now_utc: datetime,
                   interval_hours: int) -> pd.DataFrame:
    """REST CSV batch per chunk titik kasar H3-8 untuk seri 72 jam ke depan."""
    start_dt = now_utc + timedelta(hours=interval_hours)
    end_dt = now_utc + timedelta(days=FORECAST_DAYS)
    start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    params_str = ",".join(CORE_PARAMS)

    frames = []
    for i in range(0, len(coarse), CHUNK_COORDS):
        chunk = coarse[i:i + CHUNK_COORDS]
        coords_str = "+".join(f"{la:.5f},{lo:.5f}" for la, lo in chunk)
        url = (
            f"https://api.meteomatics.com/{start_iso}--{end_iso}:PT{interval_hours}H/"
            f"{params_str}/{coords_str}/csv"
        )
        text = client.get_text(url)
        df_raw = pd.read_csv(io.StringIO(text), sep=";")
        if "lat" not in df_raw.columns:
            df_raw["lat"] = chunk[0][0]
            df_raw["lon"] = chunk[0][1]
        frames.append(df_raw)
    df = pd.concat(frames, ignore_index=True)
    df = assign_wib_day_offset(df, now_utc)
    return complete_derived_agro_columns(df)


def aggregate_daily(df_raw: pd.DataFrame, interval_hours: int) -> pd.DataFrame:
    return (
        df_raw.groupby(["day_offset", "forecast_date", "lat", "lon"], as_index=False)
        .agg(
            fc_tmean_c=("t_2m:C", "mean"),
            fc_tmax_c=("t_max_2m_24h:C", "max"),
            # laju 1-jam dijumlah lalu dikali interval -> akumulasi harian yang sah
            fc_precip_total_mm=("precip_1h:mm", lambda s: float(np.sum(s) * interval_hours)),
            fc_precip_max_1h_mm=("precip_1h:mm", "max"),
            fc_eto_total_mm=("evapotranspiration_1h:mm", lambda s: float(np.sum(s) * interval_hours)),
            fc_smi_mean=("soil_moisture_index_-15cm:idx", "mean"),
            fc_wind_max_ms=("wind_speed_10m:ms", "max"),
        )
    )


def map_to_fine(fine: pd.DataFrame, daily: pd.DataFrame, mode: str) -> pd.DataFrame:
    ref_lat = float(fine["centroid_lat"].mean())
    fine_km = latlon_to_km(fine["centroid_lat"].values, fine["centroid_lon"].values, ref_lat)
    out = []
    for day_idx in sorted(daily["day_offset"].unique()):
        sub = daily[daily["day_offset"] == day_idx].reset_index(drop=True)
        coarse_km = latlon_to_km(sub["lat"].values, sub["lon"].values, ref_lat)
        w = psf_weights(coarse_km, fine_km)
        projected = w @ sub[METRIC_COLS].to_numpy(dtype=float)
        df_day = fine.copy()
        df_day["day_offset"] = int(day_idx)
        df_day["horizon_code"] = f"H+{int(day_idx)}"
        df_day["forecast_date"] = str(sub["forecast_date"].iloc[0])
        for j, c in enumerate(METRIC_COLS):
            df_day[c] = np.round(projected[:, j], 3)
        df_day["h7_cluster_fc_rain_mm"] = np.round(
            df_day.groupby("h3_parent_res7")["fc_precip_total_mm"].transform("mean"), 2
        )
        df_day["forecast_source_mode"] = mode
        out.append(df_day)
    return pd.concat(out, ignore_index=True)[SCHEMA]


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingestor forecast 3 hari Meteomatics -> 4.143 sel H3 sawah")
    ap.add_argument("--dry-run", action="store_true", help="tanpa API; hanya geometri + bobot PSF")
    ap.add_argument("--limit", type=int, default=0, help="batasi jumlah titik kasar (uji kuota)")
    ap.add_argument("--interval-hours", type=int, default=3, help="langkah waktu forecast (jam)")
    args = ap.parse_args()

    if not PADDY_GRID.exists():
        print(f"ERROR: grid sawah tidak ditemukan: {PADDY_GRID}")
        return 2
    fine = load_fine_cells()
    coarse = build_coarse_h8(fine)
    if args.limit > 0:
        coarse = coarse[: args.limit]
    n_req = math.ceil(len(coarse) / CHUNK_COORDS)
    print(f"sel_sawah: {len(fine)} | titik_kasar_H8: {len(coarse)} | PSF_FWHM_km: {PSF_FWHM_KM} | estimasi_request: {n_req}")

    if args.dry_run:
        ref_lat = float(fine["centroid_lat"].mean())
        fine_km = latlon_to_km(fine["centroid_lat"].values, fine["centroid_lon"].values, ref_lat)
        coarse_km = latlon_to_km(coarse[:, 0], coarse[:, 1], ref_lat)
        w = psf_weights(coarse_km, fine_km)
        print(f"[dry-run] W shape: {w.shape} | row-sum~1: {np.allclose(w.sum(axis=1), 1.0)}")
        print("[dry-run] tidak ada panggilan API, tidak ada artefak ditulis.")
        return 0

    env = load_env(root / ".env")
    user, pw = env.get("METEOMATICS_USERNAME"), env.get("METEOMATICS_PASSWORD")
    print("credentials_present:", bool(user), bool(pw))
    if not user or not pw:
        print("ERROR: isi .env (METEOMATICS_USERNAME / METEOMATICS_PASSWORD) dulu.")
        return 2
    client = MeteomaticsClient(user, pw)

    now_utc = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    t0 = time.time()
    df_raw = fetch_forecast(client, coarse, now_utc, args.interval_hours)
    fetch_sec = time.time() - t0
    mode = "LIVE_METEOMATICS_FORECAST_3D_REST_H8"

    daily = aggregate_daily(df_raw, args.interval_hours)
    df = map_to_fine(fine, daily, mode)

    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PARQUET, index=False)
    df.to_csv(OUT_PARQUET.with_suffix(".csv"), index=False)

    nulls = {c: int(df[c].isna().sum()) for c in METRIC_COLS}
    provenance = {
        "source": mode,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "grid": f"banyumas_h3_paddy_grid.geojson ({df['h3_index'].nunique()} sel sawah otoritatif)",
        "ported_from": "(prediction)meteomatics_3day_forecast_h3.py (grid 1000 tim data)",
        "n_paddy_cells": int(df["h3_index"].nunique()),
        "n_rows": len(df),
        "horizons": sorted(df["horizon_code"].unique().tolist()),
        "forecast_dates_wib": sorted(df["forecast_date"].unique().tolist()),
        "n_coarse_points": len(coarse),
        "api_requests": client.requests,
        "api_fetch_duration_sec": round(fetch_sec, 3),
        "interval_hours": args.interval_hours,
        "psf_fwhm_km": PSF_FWHM_KM,
        "psf_normalization": "per_fine_cell_convex_combination (sum_i W_ji = 1)",
        "derived_columns": {
            "t_max_2m_24h:C": "max(t_2m:C) per hari bila tidak tersedia",
            "evapotranspiration_1h:mm": "heuristik VPD bila tidak tersedia (bukan observasi)",
            "soil_moisture_index_-15cm:idx": "heuristik tanh(net water) bila tidak tersedia (bukan observasi)",
        },
        "interpolation_provenance": "PSF_GAUSSIAN coarse->fine (bukan observasi per sel)",
        "credentials_present": True,
        "fc_nulls": nulls,
    }
    prov_path = OUT_PARQUET.with_name(OUT_PARQUET.stem + "_provenance.json")
    prov_path.write_text(json.dumps(provenance, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nSelesai. {df['h3_index'].nunique()} sel x {df['day_offset'].nunique()} hari = {len(df)} baris -> {OUT_PARQUET.name}")
    print(f"request API: {client.requests} | fetch: {fetch_sec:.2f}s")
    print(f"horizon: {provenance['horizons']} | tanggal WIB: {provenance['forecast_dates_wib']}")
    print(f"provenance -> {prov_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())