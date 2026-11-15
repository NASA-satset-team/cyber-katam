"""
web-app/scripts/build_roi_layer.py
----------------------------------
Menyegarkan lapisan hijau "sawah" peta (public/banyumas_paddy_mask.geojson)
dari ROI terbaru: data/boundaries/banyumas_paddy90_roi.geojson
(4.143 sel H3 res-9, ESA WorldCover v200 cropland_frac >= 0.9).

Hanya lapisan visual. Grid data/analisis tetap banyumas_h3_paddy_grid.geojson.
"""

import argparse
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]

DEFAULT_SRC = root / "data" / "boundaries" / "banyumas_paddy90_roi.geojson"
OUT = root / "public" / "banyumas_paddy_mask.geojson"


def main() -> int:
    ap = argparse.ArgumentParser(description="Bangun lapisan hijau peta dari ROI sawah >= 90%")
    ap.add_argument("--src", type=str, default=str(DEFAULT_SRC), help="geojson ROI sawah")
    args = ap.parse_args()

    src_path = Path(args.src)
    if not src_path.exists():
        print(f"ERROR: sumber tidak ditemukan: {src_path}")
        return 2

    payload = json.loads(src_path.read_text(encoding="utf-8"))
    OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    props = payload["features"][0].get("properties", {})
    print(f"{props.get('n_cells', '?')} sel ROI -> {len(payload['features'])} fitur -> {OUT.name} "
          f"({OUT.stat().st_size:,} byte)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
