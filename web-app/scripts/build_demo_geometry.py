"""Derive valid H3 parents from the existing synthetic geometry; never EO values."""
import json
from pathlib import Path

import h3

root = Path(__file__).resolve().parents[2]
source = json.loads((root / "public/demo-grid.geojson").read_text())
indexes = [f["properties"]["h3_index"] for f in source["features"]]
levels = {}
for resolution in (7, 8, 9):
    cells = sorted({h3.cell_to_parent(index, resolution) for index in indexes})
    levels[str(resolution)] = [
        {
            "id": cell,
            "ring": [[lng, lat] for lat, lng in h3.cell_to_boundary(cell)],
        }
        for cell in cells
    ]
artifact = {
    "synthetic": True,
    "source": "public/demo-grid.geojson",
    "generator": "web-app/scripts/build_demo_geometry.py",
    "warning": "Geometri sintetis, bukan batas petak atau pengamatan NASA.",
    "levels": levels,
}
(root / "public/demo-grid-levels.json").write_text(
    json.dumps(artifact, separators=(",", ":")) + "\n"
)
