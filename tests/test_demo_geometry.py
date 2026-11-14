"""The UI fixture is synthetic geometry, never field observations."""
import json
from pathlib import Path

import h3


def test_synthetic_ui_geometry_has_no_satellite_attributes():
    root = Path(__file__).resolve().parents[1]
    fixture = json.loads((root / "public/demo-grid.geojson").read_text())
    assert fixture["synthetic"] is True
    assert fixture["generator_version"] == "repository-fixture-sanitizer-v1"
    assert "not" in fixture["warning"]
    assert len(fixture["features"]) == 1000
    indexes = []
    for feature in fixture["features"]:
        assert set(feature["properties"]) == {"h3_index", "synthetic"}
        assert feature["properties"]["synthetic"] is True
        index = feature["properties"]["h3_index"]
        indexes.append(index)
        assert h3.is_valid_cell(index)
        assert h3.get_resolution(index) == 9
        ring = feature["geometry"]["coordinates"][0]
        assert ring[0] == ring[-1]
    assert len(set(indexes)) == 1000


def test_synthetic_ui_geometry_preserves_received_polygons():
    root = Path(__file__).resolve().parents[1]
    fixture = json.loads((root / "public/demo-grid.geojson").read_text())
    source = json.loads(
        (root / "external/ariefs_workresult/banyumas_h3_precomputed.geojson").read_text()
    )
    assert [f["geometry"] for f in fixture["features"]] == [
        f["geometry"] for f in source["features"]
    ]


def test_synthetic_multiresolution_parents_are_valid_and_not_observations():
    root = Path(__file__).resolve().parents[1]
    fixture = json.loads((root / "public/demo-grid-levels.json").read_text())
    source = json.loads((root / "public/demo-grid.geojson").read_text())
    assert fixture["synthetic"] is True
    indexes = [f["properties"]["h3_index"] for f in source["features"]]
    for resolution in (7, 8, 9):
        cells = fixture["levels"][str(resolution)]
        expected = {h3.cell_to_parent(index, resolution) for index in indexes}
        assert {cell["id"] for cell in cells} == expected
        for cell in cells:
            assert set(cell) == {"id", "ring"}
            assert h3.get_resolution(cell["id"]) == resolution
            assert cell["ring"] == [
                [lng, lat] for lat, lng in h3.cell_to_boundary(cell["id"])
            ]
