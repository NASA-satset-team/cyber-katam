"""
web-app/scripts/log_paddy_history.py
------------------------------------
Logger riwayat 3-harian (Fase 1): menumpuk snapshot fitur + skor per sel sawah
(4.143 sel H3 res-9) ke parquet history sebagai bahan retrain ML.

Setiap snapshot = gabungan fitur cuaca live (mm_ dari ingest_meteomatics_live)
+ skor engine (PVRS/BF-EHSI dari paddy_live_evaluator), diberi kunci waktu
valid_time_utc. Idempoten: snapshot dengan valid_time sama tidak diduplikasi,
sehingga aman dijalankan ulang. Logger TIDAK menghitung ulang engine dan TIDAK
mengarang nilai; ia hanya memotret artefak yang sudah ada (fail-closed bila belum ada).

Mode:
  (default)          snapshot dari artefak yang sudah ada (tanpa panggilan API)
  --run-pipeline     jalankan ingest live + evaluator dulu (biaya API), lalu snapshot
  --status           lapor riwayat terakumulasi, tanpa menulis
  --replace          timpa snapshot bila valid_time sudah ada
  --min-gap-hours N  lewati bila valid_time baru < N jam dari snapshot terakhir
                     (pakai 72 untuk kadens 3-harian pada cron harian)

Kadens 3-harian dicapai dengan menjadwalkan skrip ini tiap 3 hari, atau cron
harian dengan --min-gap-hours 72 (lihat laporan --status untuk riwayat).
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
FEATURES = PROCESSED / "meteomatics_banyumas_h3_paddy_live.parquet"
SCORES = PROCESSED / "paddy_live_scores.parquet"
PROV = PROCESSED / "meteomatics_banyumas_h3_paddy_live_provenance.json"
HISTORY = PROCESSED / "paddy_history_snapshots.parquet"
MANIFEST = PROCESSED / "paddy_history_manifest.json"
INGEST = ROOT / "web-app" / "scripts" / "ingest_meteomatics_live.py"
EVALUATOR = ROOT / "src" / "engines" / "paddy_live_evaluator.py"


def run_pipeline() -> None:
    """Jalankan ingest live lalu evaluator (biaya API). Gagal keras bila salah satu gagal."""
    for script in (INGEST, EVALUATOR):
        if not script.exists():
            raise FileNotFoundError(f"skrip pipeline tidak ada: {script}")
        print(f"[pipeline] menjalankan {script.name} ...")
        res = subprocess.run([sys.executable, str(script)], cwd=str(ROOT))
        if res.returncode != 0:
            raise RuntimeError(f"{script.name} gagal (exit {res.returncode}); snapshot dibatalkan.")


def build_snapshot() -> tuple:
    """Gabungkan fitur mm_ + skor engine per sel, beri metadata snapshot. Fail-closed."""
    missing = [p.name for p in (FEATURES, SCORES, PROV) if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"artefak input belum ada: {', '.join(missing)}. "
            "Jalankan ingest_meteomatics_live.py lalu paddy_live_evaluator.py dulu "
            "(atau pakai --run-pipeline)."
        )
    prov = json.loads(PROV.read_text(encoding="utf-8"))
    valid_time = prov.get("valid_time_utc")
    if not valid_time:
        raise ValueError("provenance live tidak punya valid_time_utc; snapshot butuh kunci waktu.")

    feat = pd.read_parquet(FEATURES)
    scores = pd.read_parquet(SCORES)
    df = scores.merge(feat, on="h3_index", how="inner")
    if df.empty:
        raise ValueError("join fitur+skor kosong: tidak ada sel yang cocok.")

    vt = datetime.fromisoformat(valid_time)
    df.insert(0, "snapshot_id", vt.strftime("%Y%m%dT%H%MZ"))
    df.insert(1, "valid_time_utc", valid_time)
    df.insert(2, "logged_at_utc", datetime.now(timezone.utc).isoformat())
    df.insert(3, "feature_source", prov.get("source", "unknown"))
    return df, valid_time, vt


def write_manifest(combined: pd.DataFrame) -> dict:
    vts = sorted(combined["valid_time_utc"].unique().tolist())
    latest = combined[combined["valid_time_utc"] == vts[-1]]
    manifest = {
        "n_snapshots": len(vts),
        "n_rows_total": int(len(combined)),
        "n_cells_latest": int(latest["h3_index"].nunique()),
        "first_valid_time_utc": vts[0],
        "last_valid_time_utc": vts[-1],
        "valid_times_utc": vts,
        "last_logged_at_utc": datetime.now(timezone.utc).isoformat(),
        "feature_source": str(latest["feature_source"].iloc[0]),
        "cadence_note": "snapshot per valid_time; jadwalkan tiap 3 hari atau cron harian + --min-gap-hours 72",
        "columns": list(combined.columns),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def report_status() -> int:
    if not HISTORY.exists():
        print("Belum ada riwayat. Jalankan logger (default) untuk snapshot pertama.")
        return 0
    hist = pd.read_parquet(HISTORY)
    vts = sorted(hist["valid_time_utc"].unique().tolist())
    print(f"history: {HISTORY.name}")
    print(f"  snapshot: {len(vts)} | baris total: {len(hist)} | sel/snapshot: {hist['h3_index'].nunique()}")
    print(f"  rentang valid_time: {vts[0]} .. {vts[-1]}")
    if len(vts) >= 2:
        gaps = [
            (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() / 3600.0
            for a, b in zip(vts, vts[1:])
        ]
        print(f"  jarak antar-snapshot (jam): min={min(gaps):.1f} median={sorted(gaps)[len(gaps)//2]:.1f} max={max(gaps):.1f}")
    print(f"  kolom ({len(hist.columns)}): {list(hist.columns)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Logger riwayat 3-harian fitur+skor per sel sawah (Fase 1)")
    ap.add_argument("--run-pipeline", action="store_true", help="jalankan ingest live + evaluator dulu (biaya API)")
    ap.add_argument("--status", action="store_true", help="lapor riwayat terakumulasi, tanpa menulis")
    ap.add_argument("--replace", action="store_true", help="timpa snapshot bila valid_time sudah ada")
    ap.add_argument("--min-gap-hours", type=float, default=0.0, help="lewati bila gap < N jam dari snapshot terakhir (72 = 3 hari)")
    args = ap.parse_args()

    if args.status:
        return report_status()

    if args.run_pipeline:
        run_pipeline()

    snap, valid_time, vt = build_snapshot()

    hist = pd.read_parquet(HISTORY) if HISTORY.exists() else None
    if hist is not None and len(hist):
        existing = hist["valid_time_utc"].unique().tolist()
        if valid_time in existing and not args.replace:
            print(f"snapshot valid_time={valid_time} sudah ada; lewati (pakai --replace untuk timpa).")
            return 0
        if args.min_gap_hours > 0 and not args.replace:
            last_vt = max(datetime.fromisoformat(x) for x in existing)
            gap_h = (vt - last_vt).total_seconds() / 3600.0
            if gap_h < args.min_gap_hours:
                print(f"gap {gap_h:.1f} jam < {args.min_gap_hours:.0f} jam; lewati (kadens terjaga).")
                return 0
        if args.replace:
            hist = hist[hist["valid_time_utc"] != valid_time]
        combined = pd.concat([hist, snap], ignore_index=True)
    else:
        combined = snap

    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(HISTORY, index=False)
    manifest = write_manifest(combined)

    print(f"\nSnapshot ditambahkan: valid_time={valid_time} | {len(snap)} sel | {len(snap.columns)} kolom")
    print(f"Riwayat: {manifest['n_snapshots']} snapshot | {manifest['n_rows_total']} baris -> {HISTORY.name}")
    print(f"Manifest -> {MANIFEST.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())