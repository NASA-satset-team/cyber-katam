"""Unit tests for the deterministic synthetic H3 generator.

All fixtures are synthetic mock/test data. No NASA observation is used, and no
test asserts real-world indicator distributions.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import h3
import pytest

import src.engines.synthetic_h3_generator as generator_module
from src.contracts import ContractValidator, ErrorCode, load_contract_schema
from src.engines.synthetic_h3_generator import (
    DEFAULT_ROI_PATH,
    GENERATOR_NAME,
    GENERATOR_VERSION,
    PRECOMPUTED_GEOJSON_PATH,
    SELECTION_METHOD,
    SYSTEM_STATES,
    ContractCompatibilityError,
    GenerationConfig,
    GenerationResult,
    InsufficientCellsError,
    InvalidConfigurationError,
    OutputWriteError,
    ROIFileNotFoundError,
    ROIParseError,
    UnsupportedGeometryError,
    build_synthetic_contract,
    generate_and_write,
    generate_candidate_cells,
    generate_feature_collection,
    load_roi_geometry,
    point_in_geometry,
    select_representative_cells,
    write_geojson,
)

MOCK_TINY_CELL = "898d8d654cbffff"


def _write_feature_collection(
    path: Path, geometry: dict[str, Any], *, feature_count: int = 1
) -> Path:
    """Write a temporary GeoJSON FeatureCollection for controlled tests."""

    features = [
        {
            "type": "Feature",
            "properties": {"mock": True},
            "geometry": geometry,
        }
        for _ in range(feature_count)
    ]
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": features,
            }
        ),
        encoding="utf-8",
    )
    return path


def _tiny_square_geometry(cell: str, padding: float = 0.001) -> dict[str, Any]:
    """Return a small valid square around a mock H3 cell center."""

    latitude, longitude = h3.cell_to_latlng(cell)
    ring = [
        [longitude - padding, latitude - padding],
        [longitude + padding, latitude - padding],
        [longitude + padding, latitude + padding],
        [longitude - padding, latitude + padding],
        [longitude - padding, latitude - padding],
    ]
    return {"type": "Polygon", "coordinates": [ring]}


@pytest.fixture(scope="module")
def roi_geometry() -> dict[str, Any]:
    """Actual bounding-box ROI geometry, loaded read-only."""

    return load_roi_geometry(DEFAULT_ROI_PATH)


@pytest.fixture(scope="module")
def candidate_cells(roi_geometry: dict[str, Any]) -> list[str]:
    """All resolution-9 candidate cells for the actual ROI."""

    return generate_candidate_cells(roi_geometry, 9)


@pytest.fixture(scope="module")
def full_result() -> GenerationResult:
    """Full 1,000-cell generation using the real ROI and default seed."""

    return generate_feature_collection(
        GenerationConfig(target_count=1000),
        validate_contracts=True,
    )


def _feature_center(feature: dict[str, Any]) -> tuple[float, float]:
    """Return (longitude, latitude) for a feature's H3 cell center."""

    latitude, longitude = h3.cell_to_latlng(feature["properties"]["h3_index"])
    return longitude, latitude


# ---------------------------------------------------------------------------
# Geometry and selection
# ---------------------------------------------------------------------------


def test_roi_can_supply_at_least_1000_cells(
    candidate_cells: list[str],
) -> None:
    assert len(candidate_cells) >= 1000
    assert len(candidate_cells) == len(set(candidate_cells))


def test_candidate_cells_are_sorted_and_valid(
    candidate_cells: list[str],
) -> None:
    assert candidate_cells == sorted(candidate_cells)
    assert all(h3.is_valid_cell(cell) for cell in candidate_cells)
    assert all(h3.get_resolution(cell) == 9 for cell in candidate_cells)


def test_exactly_1000_features_are_generated(
    full_result: GenerationResult,
) -> None:
    features = full_result.feature_collection["features"]

    assert len(features) == 1000
    assert full_result.selected_count == 1000
    assert full_result.candidate_count >= 1000


def test_every_h3_index_is_valid_resolution_9_and_unique(
    full_result: GenerationResult,
) -> None:
    indexes = [
        feature["properties"]["h3_index"]
        for feature in full_result.feature_collection["features"]
    ]

    assert len(indexes) == 1000
    assert len(indexes) == len(set(indexes))
    assert all(h3.is_valid_cell(cell) for cell in indexes)
    assert all(h3.get_resolution(cell) == 9 for cell in indexes)


def test_every_geometry_is_a_closed_polygon(
    full_result: GenerationResult,
) -> None:
    for feature in full_result.feature_collection["features"]:
        geometry = feature["geometry"]
        assert geometry["type"] == "Polygon"
        assert len(geometry["coordinates"]) == 1

        ring = geometry["coordinates"][0]
        assert len(ring) >= 4
        assert ring[0] == ring[-1]


def test_geojson_coordinate_order_is_longitude_latitude(
    full_result: GenerationResult,
) -> None:
    for feature in full_result.feature_collection["features"]:
        cell = feature["properties"]["h3_index"]
        ring = feature["geometry"]["coordinates"][0]
        first_latitude, first_longitude = h3.cell_to_boundary(cell)[0]

        assert ring[0] == [float(first_longitude), float(first_latitude)]
        assert 100.0 < ring[0][0] < 115.0
        assert -10.0 < ring[0][1] < 0.0


def test_every_cell_center_is_inside_the_roi(
    full_result: GenerationResult,
    roi_geometry: dict[str, Any],
) -> None:
    for feature in full_result.feature_collection["features"]:
        longitude, latitude = _feature_center(feature)
        assert point_in_geometry(longitude, latitude, roi_geometry)


def test_selection_is_deterministic_and_covers_all_res7_parents(
    full_result: GenerationResult,
    candidate_cells: list[str],
) -> None:
    selected = list(full_result.cells)
    expected = select_representative_cells(candidate_cells, 1000)

    assert selected == expected

    candidate_parents = {
        h3.cell_to_parent(cell, 7) for cell in candidate_cells
    }
    selected_parents = {
        h3.cell_to_parent(cell, 7) for cell in selected
    }
    assert selected_parents == candidate_parents


def test_selection_method_is_recorded(full_result: GenerationResult) -> None:
    generator = full_result.feature_collection["generator"]

    assert generator["selection_method"] == SELECTION_METHOD
    assert generator["selection_details"]["group_resolution"] == 7
    assert generator["selection_details"]["selected_group_count"] > 400


def test_insufficient_candidate_cells_raise_instead_of_fabricating(
    tmp_path: Path,
) -> None:
    tiny_roi = _write_feature_collection(
        tmp_path / "tiny_roi.geojson",
        _tiny_square_geometry(MOCK_TINY_CELL),
    )

    with pytest.raises(InsufficientCellsError) as exc_info:
        generate_feature_collection(
            GenerationConfig(roi_path=tiny_roi, target_count=1000)
        )

    assert exc_info.value.candidate_count < 1000
    assert exc_info.value.target_count == 1000


def test_empty_candidate_list_raises_insufficient_cells() -> None:
    with pytest.raises(InsufficientCellsError):
        select_representative_cells([], 1)


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


def test_same_seed_produces_identical_output() -> None:
    config = GenerationConfig(target_count=25, seed=12345)

    first = generate_feature_collection(config)
    second = generate_feature_collection(config)

    assert first.feature_collection == second.feature_collection


def test_different_seed_changes_attributes_not_geometry() -> None:
    first = generate_feature_collection(
        GenerationConfig(target_count=25, seed=1)
    )
    second = generate_feature_collection(
        GenerationConfig(target_count=25, seed=2)
    )

    assert first.cells == second.cells

    first_geometries = [
        feature["geometry"]
        for feature in first.feature_collection["features"]
    ]
    second_geometries = [
        feature["geometry"]
        for feature in second.feature_collection["features"]
    ]
    assert first_geometries == second_geometries

    first_contracts = [
        feature["properties"]["contract"]
        for feature in first.feature_collection["features"]
    ]
    second_contracts = [
        feature["properties"]["contract"]
        for feature in second.feature_collection["features"]
    ]
    assert first_contracts != second_contracts


def test_seed_does_not_change_selected_h3_ids() -> None:
    first = generate_feature_collection(
        GenerationConfig(target_count=10, seed=0)
    )
    second = generate_feature_collection(
        GenerationConfig(target_count=10, seed=999)
    )

    assert first.cells == second.cells


def test_system_state_cycle_is_deterministic() -> None:
    result = generate_feature_collection(
        GenerationConfig(target_count=6, seed=3)
    )
    states = [
        feature["properties"]["contract"]["system_state"]
        for feature in result.feature_collection["features"]
    ]

    assert states == [SYSTEM_STATES[i % len(SYSTEM_STATES)] for i in range(6)]


# ---------------------------------------------------------------------------
# Contract compatibility
# ---------------------------------------------------------------------------


def test_every_generated_contract_validates(
    full_result: GenerationResult,
) -> None:
    validator = ContractValidator(enable_provisional_semantics=True)

    for feature in full_result.feature_collection["features"]:
        contract = feature["properties"]["contract"]
        result = validator.validate(contract)
        assert result.is_valid is True, result.errors
        assert result.error_count == 0


def test_contracts_contain_schema_required_fields(
    full_result: GenerationResult,
) -> None:
    schema = load_contract_schema()
    top_required = set(schema["required"])
    top_allowed = set(schema["properties"])

    for feature in full_result.feature_collection["features"][:20]:
        contract = feature["properties"]["contract"]
        assert top_required.issubset(contract)
        assert set(contract).issubset(top_allowed)

        for block in (
            "physical_indicators",
            "operational_flags",
            "xai_decision_block",
            "fiscal_metrics",
        ):
            block_required = set(schema["properties"][block]["required"])
            assert block_required.issubset(contract[block])
            assert set(contract[block]).issubset(
                set(schema["properties"][block]["properties"])
            )


def test_invalid_contract_value_is_rejected(
    full_result: GenerationResult,
) -> None:
    contract = copy.deepcopy(
        full_result.feature_collection["features"][0]["properties"]["contract"]
    )
    contract["physical_indicators"]["PVRS"] = 2.0

    result = ContractValidator().validate(contract)

    assert result.is_valid is False
    assert result.errors[0].code == ErrorCode.ABOVE_MAXIMUM
    assert result.errors[0].path == "/physical_indicators/PVRS"


def test_contract_compatibility_failure_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invalid_builder(
        h3_index: str,
        rng: Any,
        *,
        ordinal: int = 0,
    ) -> dict[str, Any]:
        return {"contract_version": "1.0"}

    monkeypatch.setattr(
        generator_module, "build_synthetic_contract", invalid_builder
    )

    with pytest.raises(ContractCompatibilityError):
        generate_feature_collection(
            GenerationConfig(target_count=1),
            validate_contracts=True,
        )


def test_synthetic_provenance_is_outside_strict_contract(
    full_result: GenerationResult,
) -> None:
    for feature in full_result.feature_collection["features"][:10]:
        properties = feature["properties"]
        contract = properties["contract"]

        assert properties["is_synthetic"] is True
        assert properties["data_source"] == "synthetic"
        assert properties["generator_name"] == GENERATOR_NAME
        assert properties["generator_version"] == GENERATOR_VERSION
        assert properties["selection_method"] == SELECTION_METHOD
        assert properties["contract_schema_status"] == "PROVISIONAL"

        assert "is_synthetic" not in contract
        assert "data_source" not in contract
        assert "generator_name" not in contract
        assert "land_cover" not in contract


# ---------------------------------------------------------------------------
# Scientific honesty and provenance
# ---------------------------------------------------------------------------


def test_every_feature_is_explicitly_synthetic(
    full_result: GenerationResult,
) -> None:
    collection = full_result.feature_collection

    assert collection["is_synthetic"] is True
    assert collection["data_source"] == "synthetic"
    assert collection["generator"]["name"] == GENERATOR_NAME
    assert collection["generator"]["version"] == GENERATOR_VERSION
    assert collection["generator"]["contract_schema_status"] == "PROVISIONAL"

    for feature in collection["features"]:
        properties = feature["properties"]
        assert properties["is_synthetic"] is True
        assert properties["data_source"] == "synthetic"
        assert properties["generator_name"] == GENERATOR_NAME
        assert properties["generator_version"] == GENERATOR_VERSION
        assert properties["random_seed"] == collection["generator"]["random_seed"]
        assert properties["h3_resolution"] == 9


def test_no_feature_is_labelled_paddy_field(
    full_result: GenerationResult,
) -> None:
    collection = full_result.feature_collection
    land_covers = {
        feature["properties"]["land_cover"]
        for feature in collection["features"]
    }

    assert land_covers == {"unverified"}
    assert "Paddy Field" not in land_covers
    warning_text = " ".join(collection["warnings"]).lower()
    assert "bounding box" in warning_text
    assert "paddy mask" in warning_text


def test_no_nasa_source_is_claimed(
    full_result: GenerationResult,
) -> None:
    collection = full_result.feature_collection
    warning_text = " ".join(collection["warnings"])

    assert "not NASA observations" in warning_text
    for feature in collection["features"][:10]:
        properties = feature["properties"]
        assert properties["data_source"] == "synthetic"
        assert "nasa" not in properties["data_source"].lower()
        assert (
            "no satellite observation"
            in properties["contract"]["xai_decision_block"]["information_gaps"]
        )


def test_variable_manifest_marks_test_only_and_engine_independence(
    full_result: GenerationResult,
) -> None:
    manifest = full_result.feature_collection[
        "synthetic_variable_manifest"
    ]

    assert manifest["physical_indicators.PVRS"]["test_only"] is True
    assert (
        manifest["physical_indicators.PVRS"]["classification"]
        == "derived_indicator_test_placeholder"
    )
    assert "NOT computed" in manifest["physical_indicators.PVRS"]["notes"]

    assert manifest["physical_indicators.BF_EHSI"]["test_only"] is True
    assert "NOT computed" in manifest["physical_indicators.BF_EHSI"]["notes"]

    assert manifest["operational_flags.missing_observation"]["test_only"] is True
    assert manifest["rotation_scenarios"]["test_only"] is True
    assert manifest["system_state"]["test_only"] is True


def test_missing_observation_flag_is_not_used_as_imputation(
    full_result: GenerationResult,
) -> None:
    for feature in full_result.feature_collection["features"]:
        contract = feature["properties"]["contract"]
        assert contract["operational_flags"]["missing_observation"] is False
        assert all(
            value is not None
            for value in contract["physical_indicators"].values()
        )


# ---------------------------------------------------------------------------
# Input and configuration errors
# ---------------------------------------------------------------------------


def test_missing_roi_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ROIFileNotFoundError):
        load_roi_geometry(tmp_path / "missing.geojson")


def test_roi_directory_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ROIFileNotFoundError):
        load_roi_geometry(tmp_path)


def test_malformed_roi_json_raises(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.geojson"
    malformed.write_text("{", encoding="utf-8")

    with pytest.raises(ROIParseError):
        load_roi_geometry(malformed)


def test_unsupported_roi_geometry_raises(tmp_path: Path) -> None:
    point_roi = _write_feature_collection(
        tmp_path / "point.geojson",
        {"type": "Point", "coordinates": [109.17, -7.45]},
    )

    with pytest.raises(UnsupportedGeometryError):
        load_roi_geometry(point_roi)


def test_multiple_roi_features_are_rejected(tmp_path: Path) -> None:
    multi_roi = _write_feature_collection(
        tmp_path / "multiple.geojson",
        _tiny_square_geometry(MOCK_TINY_CELL),
        feature_count=2,
    )

    with pytest.raises(UnsupportedGeometryError):
        load_roi_geometry(multi_roi)


def test_unclosed_ring_is_rejected(tmp_path: Path) -> None:
    open_ring = {
        "type": "Polygon",
        "coordinates": [
            [
                [109.16, -7.46],
                [109.18, -7.46],
                [109.18, -7.44],
                [109.16, -7.44],
            ]
        ],
    }
    roi_file = _write_feature_collection(
        tmp_path / "open_ring.geojson", open_ring
    )

    with pytest.raises(ROIParseError):
        load_roi_geometry(roi_file)


@pytest.mark.parametrize(
    "resolution",
    [
        pytest.param(8, id="unsupported-res-8"),
        pytest.param(16, id="out-of-range-16"),
        pytest.param(True, id="boolean"),
        pytest.param(9.5, id="float"),
        pytest.param("9", id="string"),
    ],
)
def test_invalid_generation_resolution_raises(resolution: Any) -> None:
    with pytest.raises(InvalidConfigurationError):
        GenerationConfig(resolution=resolution)


@pytest.mark.parametrize(
    "resolution",
    [
        pytest.param(16, id="out-of-range-16"),
        pytest.param(True, id="boolean"),
        pytest.param(9.5, id="float"),
        pytest.param("9", id="string"),
    ],
)
def test_invalid_candidate_resolution_raises(
    resolution: Any, roi_geometry: dict[str, Any]
) -> None:
    with pytest.raises(InvalidConfigurationError):
        generate_candidate_cells(roi_geometry, resolution)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "seed",
    [
        pytest.param(-1, id="negative"),
        pytest.param(1.5, id="float"),
        pytest.param(True, id="boolean"),
        pytest.param("1", id="string"),
    ],
)
def test_invalid_seed_raises(seed: Any) -> None:
    with pytest.raises(InvalidConfigurationError):
        GenerationConfig(seed=seed)


@pytest.mark.parametrize(
    "target_count",
    [
        pytest.param(0, id="zero"),
        pytest.param(-1, id="negative"),
        pytest.param(1.5, id="float"),
        pytest.param(True, id="boolean"),
        pytest.param("1000", id="string"),
    ],
)
def test_invalid_target_count_raises(target_count: Any) -> None:
    with pytest.raises(InvalidConfigurationError):
        GenerationConfig(target_count=target_count)


def test_invalid_output_path_is_rejected(
    tmp_path: Path, full_result: GenerationResult
) -> None:
    with pytest.raises(OutputWriteError):
        write_geojson(
            full_result.feature_collection,
            tmp_path,
        )


def test_precomputed_geojson_is_protected(
    full_result: GenerationResult,
) -> None:
    with pytest.raises(OutputWriteError):
        write_geojson(
            full_result.feature_collection,
            PRECOMPUTED_GEOJSON_PATH,
        )


def test_roi_file_is_protected(full_result: GenerationResult) -> None:
    with pytest.raises(OutputWriteError):
        write_geojson(
            full_result.feature_collection,
            DEFAULT_ROI_PATH,
        )


# ---------------------------------------------------------------------------
# Output writing and point-in-polygon helper
# ---------------------------------------------------------------------------


def test_generate_and_write_outputs_valid_geojson(tmp_path: Path) -> None:
    output_path = tmp_path / "synthetic_h3.geojson"
    result = generate_and_write(
        GenerationConfig(
            target_count=10,
            seed=42,
            output_path=output_path,
        )
    )

    assert output_path.exists()
    assert result.output_path == output_path
    assert result.file_size_bytes == output_path.stat().st_size
    assert result.file_size_bytes > 0

    document = json.loads(output_path.read_text(encoding="utf-8"))
    assert document["type"] == "FeatureCollection"
    assert document["is_synthetic"] is True
    assert len(document["features"]) == 10
    assert result.contracts_validated == 10


def test_point_in_geometry_handles_polygon_holes() -> None:
    geometry = {
        "type": "Polygon",
        "coordinates": [
            [
                [0.0, 0.0],
                [10.0, 0.0],
                [10.0, 10.0],
                [0.0, 10.0],
                [0.0, 0.0],
            ],
            [
                [4.0, 4.0],
                [6.0, 4.0],
                [6.0, 6.0],
                [4.0, 6.0],
                [4.0, 4.0],
            ],
        ],
    }

    assert point_in_geometry(1.0, 1.0, geometry) is True
    assert point_in_geometry(5.0, 5.0, geometry) is False


def test_point_in_geometry_handles_multipolygon() -> None:
    geometry = {
        "type": "MultiPolygon",
        "coordinates": [
            [
                [
                    [0.0, 0.0],
                    [2.0, 0.0],
                    [2.0, 2.0],
                    [0.0, 2.0],
                    [0.0, 0.0],
                ]
            ],
            [
                [
                    [5.0, 5.0],
                    [7.0, 5.0],
                    [7.0, 7.0],
                    [5.0, 7.0],
                    [5.0, 5.0],
                ]
            ],
        ],
    }

    assert point_in_geometry(1.0, 1.0, geometry) is True
    assert point_in_geometry(6.0, 6.0, geometry) is True
    assert point_in_geometry(3.0, 3.0, geometry) is False


def test_point_in_geometry_rejects_unsupported_type() -> None:
    with pytest.raises(UnsupportedGeometryError):
        point_in_geometry(0.0, 0.0, {"type": "Point", "coordinates": [0, 0]})


def test_tiny_roi_point_is_outside_actual_roi(
    roi_geometry: dict[str, Any],
) -> None:
    assert (
        point_in_geometry(109.17, -7.45, roi_geometry) is True
    )
    assert (
        point_in_geometry(110.50, -7.45, roi_geometry) is False
    )
