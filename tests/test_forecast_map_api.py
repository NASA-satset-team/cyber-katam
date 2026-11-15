import h3
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api import predict_server as server


@pytest.fixture
def forecast_client(monkeypatch, tmp_path):
    parent = h3.cell_to_parent("898d8996bc3ffff", 8)
    sibling = next(p for p in h3.cell_to_children(h3.cell_to_parent(parent, 7), 8) if p != parent)
    indexes = sorted(h3.cell_to_children(parent, 9))[:2] + sorted(h3.cell_to_children(sibling, 9))[:1]
    rows = []
    for offset in (1, 2, 3):
        for index, rain in zip(indexes, (10, 20, 60)):
            lat, lon = h3.cell_to_latlng(index)
            rows.append({
                "h3_index": index,
                "h3_parent_res7": h3.cell_to_parent(index, 7),
                "centroid_lat": lat,
                "centroid_lon": lon,
                "day_offset": offset,
                "horizon_code": f"H+{offset}",
                "forecast_date": f"2026-11-{15 + offset}",
                "forecast_source_mode": "TEST_FORECAST",
                **{field: 1.0 for field in server._FC_FIELDS},
                "fc_precip_total_mm": rain * offset,
            })
    path = tmp_path / "forecast.parquet"
    path.touch()
    monkeypatch.setattr(server, "FORECAST_PATH", path)
    monkeypatch.setattr(pd, "read_parquet", lambda _: pd.DataFrame(rows))
    monkeypatch.setattr(server, "_load_and_validate", lambda: None)
    monkeypatch.setattr(server, "_FC_STATE", {
        "cells": {}, "summaries": [], "by_date": {}, "meta": {}, "ready": False, "error": None,
    })
    with TestClient(server.app) as client:
        yield client, indexes, parent


@pytest.mark.parametrize("offset", (1, 2, 3))
@pytest.mark.parametrize("resolution,count", ((7, 1), (8, 2), (9, 3)))
def test_daily_forecast_map_uses_exact_h3_parents(forecast_client, offset, resolution, count):
    client, indexes, parent = forecast_client
    response = client.get("/api/forecast/map", params={"date": f"2026-11-{15 + offset}", "resolution": resolution})
    assert response.status_code == 200
    payload = response.json()
    assert payload["horizon_code"] == f"H+{offset}"
    assert payload["resolution"] == resolution
    assert payload["n_cells"] == count
    assert set(payload["cells"]) == {h3.cell_to_parent(index, resolution) for index in indexes}
    if resolution == 9:
        cell = payload["cells"][indexes[0]]
        assert cell["fc_precip_total_mm"] == 10 * offset
        assert cell["n_children"] == 1
    else:
        cell = payload["cells"][h3.cell_to_parent(parent, resolution)]
        assert cell["fc_precip_total_mm"] == (15 if resolution == 8 else 30) * offset
        assert cell["n_children"] == (2 if resolution == 8 else 3)


@pytest.mark.parametrize("params,status", (
    ({"date": "2026-11-19"}, 404),
    ({"date": "invalid"}, 422),
    ({"date": "2026-11-16", "resolution": 6}, 422),
    ({"date": "2026-11-16", "resolution": 10}, 422),
))
def test_forecast_map_rejects_unavailable_dates_and_resolutions(forecast_client, params, status):
    client, _, _ = forecast_client
    response = client.get("/api/forecast/map", params=params)
    assert response.status_code == status
    if status == 404:
        assert "2026-11-16" in response.json()["detail"]


def test_forecast_map_does_not_replace_existing_endpoints(forecast_client):
    client, indexes, _ = forecast_client
    assert client.get("/api/forecast/health").json()["n_cells"] == 3
    assert client.get("/api/forecast").json()["total"] == 3
    assert len(client.get(f"/api/forecast/{indexes[0]}").json()["forecast"]) == 3
