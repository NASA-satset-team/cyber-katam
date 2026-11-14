"""Deterministic synthetic H3 fixture generator for the Banyumas ROI.

This module is a **synthetic-data generator**, not a NASA extraction pipeline,
not an agronomic model, and not an implementation of Arya's physics engines.

It creates exactly 1,000 valid H3 resolution-9 cells from the actual bounding-box
ROI in ``data/boundaries/banyumas_paddy_roi.geojson``, selects them
deterministically across H3 resolution-7 parents, and attaches explicitly
labelled synthetic contract fixtures that validate against the provisional
Task 1 schema.

The ROI is a bounding box, not a verified paddy mask. No output from this module
may be described as a satellite observation, a paddy-field classification, or a
physics-engine result.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final

import h3
import numpy as np

from src.contracts import ContractValidator, SchemaConfigurationError

GENERATOR_NAME: Final[str] = "synthetic_h3_generator"
GENERATOR_VERSION: Final[str] = "1.0.0"
DEFAULT_RESOLUTION: Final[int] = 9
DEFAULT_TARGET_COUNT: Final[int] = 1000
DEFAULT_SEED: Final[int] = 20261114
SELECTION_METHOD: Final[str] = (
    "deterministic_stratified_round_robin_by_h3_res7_parent"
)

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
DEFAULT_ROI_PATH: Final[Path] = (
    REPO_ROOT / "data" / "boundaries" / "banyumas_paddy_roi.geojson"
)
DEFAULT_OUTPUT_PATH: Final[Path] = (
    REPO_ROOT / "data" / "mock" / "banyumas_h3_synthetic.geojson"
)
CONTRACT_SCHEMA_PATH: Final[Path] = (
    REPO_ROOT / "contracts" / "grid_cell_contract.schema.json"
)
PRECOMPUTED_GEOJSON_PATH: Final[Path] = (
    REPO_ROOT
    / "external"
    / "ariefs_workresult"
    / "banyumas_h3_precomputed.geojson"
)
CONTRACT_SCHEMA_DISPLAY_PATH: Final[str] = "contracts/grid_cell_contract.schema.json"

SYSTEM_STATES: Final[tuple[str, ...]] = (
    "ACTIVE_RECOMMENDATION",
    "ABSTAIN_AUDIT_REQUIRED",
    "ABSTAIN_FIELD_AUDIT_REQUIRED",
)

# Test-only upper bound for GPM_rain_7d. The contract has a minimum of 0 but no
# ratified maximum. This is an arbitrary synthetic cap, not a rainfall
# distribution or a physical threshold.
GPM_RAIN_7D_TEST_MAX_MM: Final[float] = 100.0


class SyntheticH3GeneratorError(Exception):
    """Base class for generator failures."""


class ROIError(SyntheticH3GeneratorError):
    """Base class for ROI loading and geometry failures."""


class ROIFileNotFoundError(ROIError):
    """Raised when the ROI file does not exist or is not a file."""


class ROIParseError(ROIError):
    """Raised when the ROI file is not valid JSON or has invalid coordinates."""


class UnsupportedGeometryError(ROIError):
    """Raised when the ROI geometry type or feature structure is unsupported."""


class InsufficientCellsError(SyntheticH3GeneratorError):
    """Raised when the ROI cannot supply the requested number of H3 cells."""

    def __init__(self, candidate_count: int, target_count: int) -> None:
        self.candidate_count = candidate_count
        self.target_count = target_count
        super().__init__(
            f"ROI produced {candidate_count} H3 candidate cell(s), but "
            f"{target_count} are required. Cells outside the ROI will not be "
            "fabricated."
        )


class InvalidConfigurationError(SyntheticH3GeneratorError):
    """Raised for invalid resolution, seed, count, or output configuration."""


class OutputWriteError(SyntheticH3GeneratorError):
    """Raised when the GeoJSON output cannot be written safely."""


class ContractCompatibilityError(SyntheticH3GeneratorError):
    """Raised when a generated contract fixture fails Task 1 validation."""


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    """Configuration for one deterministic synthetic generation run.

    Args:
        roi_path: Actual ROI GeoJSON path. Defaults to the repository bbox file.
        output_path: Target GeoJSON path used by :func:`generate_and_write`.
        resolution: H3 resolution. The synthetic contract fixture is res-9 only.
        target_count: Number of cells to select.
        seed: Non-negative NumPy seed for synthetic attributes only.

    Raises:
        InvalidConfigurationError: If any value is invalid.
    """

    roi_path: Path = DEFAULT_ROI_PATH
    output_path: Path = DEFAULT_OUTPUT_PATH
    resolution: int = DEFAULT_RESOLUTION
    target_count: int = DEFAULT_TARGET_COUNT
    seed: int = DEFAULT_SEED

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "roi_path", Path(self.roi_path).expanduser().resolve()
        )
        object.__setattr__(
            self, "output_path", Path(self.output_path).expanduser().resolve()
        )
        _validate_resolution(self.resolution)
        if self.resolution != DEFAULT_RESOLUTION:
            raise InvalidConfigurationError(
                "Synthetic contract fixtures require H3 resolution "
                f"{DEFAULT_RESOLUTION}; received {self.resolution}."
            )
        _validate_target_count(self.target_count)
        _validate_seed(self.seed)
        if not self.output_path.name:
            raise InvalidConfigurationError(
                "output_path must include a file name."
            )


@dataclass(frozen=True, slots=True)
class GenerationResult:
    """In-memory result of one generation run."""

    feature_collection: dict[str, Any]
    cells: tuple[str, ...]
    candidate_count: int
    selected_count: int
    roi_source: str
    contracts_validated: int
    output_path: Path | None = None
    file_size_bytes: int | None = None


def _validate_resolution(resolution: Any) -> None:
    """Validate an H3 resolution without accepting booleans."""

    if not isinstance(resolution, int) or isinstance(resolution, bool):
        raise InvalidConfigurationError("H3 resolution must be an integer.")
    if not 0 <= resolution <= 15:
        raise InvalidConfigurationError(
            "H3 resolution must be between 0 and 15."
        )


def _validate_target_count(target_count: Any) -> None:
    """Validate a positive target cell count without accepting booleans."""

    if (
        not isinstance(target_count, int)
        or isinstance(target_count, bool)
        or target_count <= 0
    ):
        raise InvalidConfigurationError(
            "target_count must be a positive integer."
        )


def _validate_seed(seed: Any) -> None:
    """Validate a non-negative NumPy seed without accepting booleans."""

    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise InvalidConfigurationError(
            "seed must be a non-negative integer."
        )


def _display_path(path: Path) -> str:
    """Return a repository-relative POSIX path when possible."""

    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def load_roi_geometry(roi_path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate the actual ROI geometry without modifying it.

    Args:
        roi_path: ROI path. Defaults to
            ``data/boundaries/banyumas_paddy_roi.geojson``.

    Returns:
        The GeoJSON geometry object (``Polygon`` or ``MultiPolygon``).

    Raises:
        ROIFileNotFoundError: If the file is missing or is not a file.
        ROIParseError: If JSON or coordinate structure is invalid.
        UnsupportedGeometryError: If the feature/geometry type is unsupported.
    """

    path = (
        Path(roi_path).expanduser().resolve()
        if roi_path is not None
        else DEFAULT_ROI_PATH
    )
    if not path.exists():
        raise ROIFileNotFoundError(f"ROI file does not exist: {path}")
    if not path.is_file():
        raise ROIFileNotFoundError(f"ROI path is not a file: {path}")

    try:
        raw_text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise ROIParseError(f"Cannot read ROI file '{path}': {exc}") from exc

    try:
        document = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ROIParseError(
            f"ROI file '{path}' is not valid JSON at line {exc.lineno}, "
            f"column {exc.colno}."
        ) from exc

    if not isinstance(document, dict):
        raise ROIParseError(f"ROI file '{path}' must contain a JSON object.")

    geometry = _extract_geometry(document, path)
    _validate_geometry(geometry, source=str(path))
    return geometry


def _extract_geometry(
    document: Mapping[str, Any], source_path: Path
) -> dict[str, Any]:
    """Extract one Polygon/MultiPolygon geometry from a GeoJSON document."""

    document_type = document.get("type")

    if document_type == "FeatureCollection":
        features = document.get("features")
        if not isinstance(features, list) or len(features) != 1:
            count = len(features) if isinstance(features, list) else "unknown"
            raise UnsupportedGeometryError(
                f"ROI FeatureCollection at '{source_path}' must contain exactly "
                f"one feature; found {count}."
            )
        feature = features[0]
        if not isinstance(feature, Mapping) or feature.get("type") != "Feature":
            raise UnsupportedGeometryError(
                f"ROI FeatureCollection at '{source_path}' must contain a "
                "GeoJSON Feature."
            )
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict):
            raise UnsupportedGeometryError(
                f"ROI Feature at '{source_path}' has no geometry object."
            )
        return geometry

    if document_type == "Feature":
        geometry = document.get("geometry")
        if not isinstance(geometry, dict):
            raise UnsupportedGeometryError(
                f"ROI Feature at '{source_path}' has no geometry object."
            )
        return geometry

    if document_type in ("Polygon", "MultiPolygon"):
        return dict(document)

    raise UnsupportedGeometryError(
        f"Unsupported ROI geometry type at '{source_path}': "
        f"{document_type!r}. Expected Polygon or MultiPolygon."
    )


def _validate_geometry(
    geometry: Mapping[str, Any], *, source: str | None = None
) -> None:
    """Validate Polygon/MultiPolygon coordinates without changing them."""

    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    source_text = f" in '{source}'" if source else ""

    if geometry_type == "Polygon":
        _validate_polygon(coordinates, source_text)
        return

    if geometry_type == "MultiPolygon":
        if not isinstance(coordinates, list) or not coordinates:
            raise UnsupportedGeometryError(
                f"MultiPolygon coordinates must be a non-empty list{source_text}."
            )
        for polygon in coordinates:
            _validate_polygon(polygon, source_text)
        return

    raise UnsupportedGeometryError(
        f"Unsupported geometry type{source_text}: {geometry_type!r}. "
        "Expected Polygon or MultiPolygon."
    )


def _validate_polygon(polygon: Any, source_text: str) -> None:
    """Validate one polygon's rings."""

    if not isinstance(polygon, list) or not polygon:
        raise ROIParseError(
            f"Polygon coordinates must be a non-empty list of rings{source_text}."
        )
    for ring in polygon:
        _validate_ring(ring, source_text)


def _validate_ring(ring: Any, source_text: str) -> None:
    """Validate one closed linear ring with finite lon/lat coordinates."""

    if not isinstance(ring, list) or len(ring) < 4:
        raise ROIParseError(
            f"Each polygon ring must contain at least four positions"
            f"{source_text}."
        )

    positions: list[tuple[float, float]] = []
    for position in ring:
        if not isinstance(position, (list, tuple)) or len(position) not in (2, 3):
            raise ROIParseError(
                f"Each coordinate must be a [lon, lat] pair{source_text}."
            )
        longitude, latitude = position[0], position[1]
        if (
            not isinstance(longitude, (int, float))
            or isinstance(longitude, bool)
            or not math.isfinite(float(longitude))
        ):
            raise ROIParseError(
                f"Longitude must be a finite number{source_text}."
            )
        if (
            not isinstance(latitude, (int, float))
            or isinstance(latitude, bool)
            or not math.isfinite(float(latitude))
        ):
            raise ROIParseError(
                f"Latitude must be a finite number{source_text}."
            )
        if not -180.0 <= float(longitude) <= 180.0:
            raise ROIParseError(
                f"Longitude {longitude!r} is outside [-180, 180]{source_text}."
            )
        if not -90.0 <= float(latitude) <= 90.0:
            raise ROIParseError(
                f"Latitude {latitude!r} is outside [-90, 90]{source_text}."
            )
        if len(position) == 3:
            altitude = position[2]
            if (
                not isinstance(altitude, (int, float))
                or isinstance(altitude, bool)
                or not math.isfinite(float(altitude))
            ):
                raise ROIParseError(
                    f"Altitude must be a finite number{source_text}."
                )
        positions.append((float(longitude), float(latitude)))

    if positions[0] != positions[-1]:
        raise ROIParseError(
            "Polygon ring is not closed; coordinates are not modified "
            f"automatically{source_text}."
        )


def point_in_geometry(
    longitude: float, latitude: float, geometry: Mapping[str, Any]
) -> bool:
    """Return True when a lon/lat point is inside a Polygon or MultiPolygon.

    Boundary points are treated as inside. This is a local GeoJSON test helper;
    it is not a geodesic or projection-aware geometry engine.
    """

    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")

    if geometry_type == "Polygon":
        return _polygon_contains(longitude, latitude, coordinates)

    if geometry_type == "MultiPolygon":
        if not isinstance(coordinates, list):
            return False
        return any(
            _polygon_contains(longitude, latitude, polygon)
            for polygon in coordinates
        )

    raise UnsupportedGeometryError(
        f"Unsupported geometry type for point-in-polygon: {geometry_type!r}."
    )


def _polygon_contains(
    longitude: float, latitude: float, polygon: Any
) -> bool:
    """Return True when a point is inside one polygon, respecting holes."""

    if not isinstance(polygon, list) or not polygon:
        return False

    if not _ring_contains(longitude, latitude, polygon[0]):
        return False

    for hole in polygon[1:]:
        if _ring_contains(longitude, latitude, hole):
            return False

    return True


def _ring_contains(longitude: float, latitude: float, ring: Any) -> bool:
    """Ray-casting point-in-ring test for a list of [lon, lat] positions."""

    if not isinstance(ring, list) or len(ring) < 3:
        return False

    inside = False
    previous_index = len(ring) - 1

    for index, current in enumerate(ring):
        previous = ring[previous_index]
        x1, y1 = float(previous[0]), float(previous[1])
        x2, y2 = float(current[0]), float(current[1])

        if _point_on_segment(longitude, latitude, x1, y1, x2, y2):
            return True

        if (y1 > latitude) != (y2 > latitude):
            intersection_x = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
            if longitude < intersection_x:
                inside = not inside

        previous_index = index

    return inside


def _point_on_segment(
    x: float,
    y: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    tolerance: float = 1e-12,
) -> bool:
    """Return True when a point lies on a line segment."""

    cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
    if abs(cross) > tolerance:
        return False
    return (
        min(x1, x2) - tolerance <= x <= max(x1, x2) + tolerance
        and min(y1, y2) - tolerance <= y <= max(y1, y2) + tolerance
    )


def generate_candidate_cells(
    roi_geometry: Mapping[str, Any],
    resolution: int = DEFAULT_RESOLUTION,
) -> list[str]:
    """Return all valid H3 cells selected by ``h3.geo_to_cells`` for the ROI.

    H3 v4's ``geo_to_cells`` uses cell-center containment semantics. The return
    value is sorted, unique, and contains no cell outside that candidate set.
    The ROI geometry is validated but never modified.

    Args:
        roi_geometry: GeoJSON Polygon/MultiPolygon geometry.
        resolution: H3 resolution from 0 to 15.

    Returns:
        Sorted unique valid H3 index strings.

    Raises:
        InvalidConfigurationError: If the resolution is invalid.
        UnsupportedGeometryError: If the geometry is not Polygon/MultiPolygon.
        SyntheticH3GeneratorError: If H3 returns an invalid result.
    """

    _validate_resolution(resolution)
    if not isinstance(roi_geometry, Mapping):
        raise UnsupportedGeometryError(
            "ROI geometry must be a GeoJSON Polygon or MultiPolygon mapping."
        )
    _validate_geometry(roi_geometry)

    try:
        candidate_set = h3.geo_to_cells(roi_geometry, resolution)
    except Exception as exc:  # External H3 library boundary; keep the cause.
        raise SyntheticH3GeneratorError(
            f"h3.geo_to_cells failed: {exc}"
        ) from exc

    cells = sorted(set(candidate_set))
    for cell in cells:
        if not isinstance(cell, str) or not h3.is_valid_cell(cell):
            raise SyntheticH3GeneratorError(
                f"h3.geo_to_cells returned an invalid H3 index: {cell!r}."
            )
        if h3.get_resolution(cell) != resolution:
            raise SyntheticH3GeneratorError(
                f"h3.geo_to_cells returned resolution "
                f"{h3.get_resolution(cell)} for a resolution-{resolution} "
                "request."
            )

    return cells


def select_representative_cells(
    candidates: Sequence[str],
    target_count: int = DEFAULT_TARGET_COUNT,
    *,
    group_resolution: int = 7,
) -> list[str]:
    """Select a deterministic, spatially distributed subset of H3 cells.

    Candidates are grouped by H3 parent at ``group_resolution``. Groups and cells
    are sorted by H3 index, then cells are taken in round-robin order, one per
    group per round, until ``target_count`` is reached. For the Banyumas ROI this
    ensures every resolution-7 parent is represented.

    Args:
        candidates: Unique H3 cell indexes.
        target_count: Exact number of cells to return.
        group_resolution: H3 parent resolution used for stratification.

    Returns:
        Sorted list of exactly ``target_count`` unique H3 indexes.

    Raises:
        InsufficientCellsError: If there are fewer candidates than requested.
        InvalidConfigurationError: If a parameter is invalid.
        SyntheticH3GeneratorError: If candidates are invalid or duplicated.
    """

    _validate_target_count(target_count)
    _validate_resolution(group_resolution)

    cells = list(candidates)
    if len(set(cells)) != len(cells):
        raise SyntheticH3GeneratorError(
            "Candidate cell list contains duplicate H3 indexes."
        )
    for cell in cells:
        if not isinstance(cell, str) or not h3.is_valid_cell(cell):
            raise SyntheticH3GeneratorError(
                f"Candidate list contains an invalid H3 index: {cell!r}."
            )

    cell_resolutions = {h3.get_resolution(cell) for cell in cells}
    if len(cell_resolutions) > 1:
        raise InvalidConfigurationError(
            "Candidate cells must all have the same H3 resolution."
        )

    cells.sort()
    if len(cells) < target_count:
        raise InsufficientCellsError(len(cells), target_count)
    if len(cells) == target_count:
        return cells

    cell_resolution = h3.get_resolution(cells[0])
    if group_resolution > cell_resolution:
        raise InvalidConfigurationError(
            "group_resolution cannot be greater than the candidate resolution."
        )

    groups: dict[str, list[str]] = {}
    for cell in cells:
        parent = h3.cell_to_parent(cell, group_resolution)
        groups.setdefault(parent, []).append(cell)

    group_keys = sorted(groups)
    selected: list[str] = []
    round_index = 0

    while len(selected) < target_count:
        added_in_round = False
        for key in group_keys:
            group = groups[key]
            if round_index < len(group):
                selected.append(group[round_index])
                added_in_round = True
                if len(selected) == target_count:
                    break
        if not added_in_round:
            break
        round_index += 1

    if len(selected) != target_count:
        raise SyntheticH3GeneratorError(
            f"Selection produced {len(selected)} cells instead of "
            f"{target_count}."
        )

    return sorted(selected)


def build_synthetic_contract(
    h3_index: str,
    rng: np.random.Generator,
    *,
    ordinal: int = 0,
) -> dict[str, Any]:
    """Build one contract fixture using only synthetic test placeholders.

    PVRS and BF-EHSI are **not** computed by Arya's engines. They are uniform
    placeholders within the provisional schema bounds. ``LST_anomaly`` is a
    constant placeholder because the schema defines no bound. Rotation
    scenarios are empty; fiscal metrics are zero placeholders; XAI text says that
    it is a synthetic test fixture.

    Args:
        h3_index: Valid resolution-9 H3 index.
        rng: NumPy ``Generator`` used only for synthetic attributes.
        ordinal: Deterministic index used to cycle the system-state enum.

    Returns:
        A contract dictionary compatible with the provisional schema.

    Raises:
        InvalidConfigurationError: If the H3 index or RNG is invalid.
    """

    if not h3.is_valid_cell(h3_index):
        raise InvalidConfigurationError(
            f"h3_index is not a valid H3 cell: {h3_index!r}."
        )
    if h3.get_resolution(h3_index) != DEFAULT_RESOLUTION:
        raise InvalidConfigurationError(
            f"Synthetic contract fixtures require resolution "
            f"{DEFAULT_RESOLUTION}; received {h3.get_resolution(h3_index)}."
        )
    if not isinstance(rng, np.random.Generator):
        raise InvalidConfigurationError(
            "rng must be a numpy.random.Generator."
        )

    # Attribute-generation order is part of generator version 1.0.0. Changing it
    # changes seeded outputs and requires a version bump.
    pvrs = round(float(rng.uniform(0.0, 1.0)), 4)
    bf_ehsi = round(float(rng.uniform(0.0, 2.5)), 4)
    smap_wetness = round(float(rng.uniform(0.0, 1.0)), 4)
    ecostress_esi = round(float(rng.uniform(0.0, 1.0)), 4)
    hls_bsi = round(float(rng.uniform(-1.0, 1.0)), 4)
    hls_ndvi = round(float(rng.uniform(-1.0, 1.0)), 4)
    gpm_rain_7d = round(float(rng.uniform(0.0, GPM_RAIN_7D_TEST_MAX_MM)), 2)
    srtm_slope = round(float(rng.uniform(0.0, 90.0)), 2)
    optical_lag_days = int(rng.integers(0, 15))
    erosion_alert = bool(rng.integers(0, 2))
    system_state = SYSTEM_STATES[ordinal % len(SYSTEM_STATES)]

    return {
        "contract_version": "1.0",
        "h3_index": h3_index,
        "h3_parent_res7": h3.cell_to_parent(h3_index, 7),
        "physical_indicators": {
            "PVRS": pvrs,
            "BF_EHSI": bf_ehsi,
            "SMAP_wetness": smap_wetness,
            "ECOSTRESS_ESI": ecostress_esi,
            # No schema bound exists. Constant placeholder is safer than
            # inventing a temperature-anomaly distribution.
            "LST_anomaly": 0.0,
            "HLS_BSI": hls_bsi,
            "HLS_NDVI": hls_ndvi,
            "GPM_rain_7d": gpm_rain_7d,
            "SRTM_slope": srtm_slope,
        },
        "operational_flags": {
            # The provisional schema requires non-null indicators. A true flag
            # with fully populated indicators would be contradictory.
            "missing_observation": False,
            "optical_lag_days": optical_lag_days,
            "erosion_alert": erosion_alert,
        },
        # Empty is valid under the provisional schema (minItems: 0). Generating
        # rotation candidates would imply an agronomic recommendation.
        "rotation_scenarios": [],
        "xai_decision_block": {
            "why_suggested": (
                "SYNTHETIC TEST FIXTURE: no recommendation was generated."
            ),
            "multi_benefits": (
                "SYNTHETIC TEST FIXTURE: no agronomic benefit was calculated."
            ),
            "information_gaps": (
                "SYNTHETIC TEST FIXTURE: no satellite observation exists for "
                "this feature."
            ),
            "local_risks_and_gates": (
                "SYNTHETIC TEST FIXTURE: no field verification was performed."
            ),
        },
        "fiscal_metrics": {
            # Zero placeholders, not fiscal_actuarial.py outputs.
            "urea_subsidy_saved_idr": 0.0,
            "autp_risk_reduction_pct": 0.0,
        },
        "system_state": system_state,
    }


def build_synthetic_variable_manifest() -> dict[str, dict[str, Any]]:
    """Return a fresh provenance manifest for every generated variable."""

    def entry(
        *,
        meaning: str,
        unit: str,
        classification: str,
        generation: str,
        evidence: str,
        test_only: bool,
        notes: str,
    ) -> dict[str, Any]:
        return {
            "meaning": meaning,
            "unit": unit,
            "classification": classification,
            "generation": generation,
            "evidence": evidence,
            "test_only": test_only,
            "notes": notes,
        }

    return {
        "h3_index": entry(
            meaning="H3 resolution-9 cell index",
            unit="none",
            classification="geometry_identity",
            generation=(
                "h3.geo_to_cells on the actual ROI, then deterministic "
                "res-7-parent round-robin selection"
            ),
            evidence=(
                "data/boundaries/banyumas_paddy_roi.geojson; h3==4.1.2"
            ),
            test_only=True,
            notes=(
                "Mathematically valid H3 cell, not a verified paddy parcel."
            ),
        ),
        "h3_parent_res7": entry(
            meaning="H3 resolution-7 parent cell",
            unit="none",
            classification="geometry_derived",
            generation="h3.cell_to_parent(h3_index, 7)",
            evidence="h3==4.1.2",
            test_only=True,
            notes="Used only for parent-consistency testing.",
        ),
        "contract_version": entry(
            meaning="Contract version",
            unit="none",
            classification="contract_constant",
            generation="constant '1.0'",
            evidence="contracts/grid_cell_contract.schema.json",
            test_only=False,
            notes="Provisional contract constant; schema is not ratified.",
        ),
        "physical_indicators.PVRS": entry(
            meaning="Pre-Visual Root-Stress Score placeholder",
            unit="dimensionless, schema [0, 1]",
            classification="derived_indicator_test_placeholder",
            generation="uniform over provisional schema bounds [0, 1]",
            evidence=(
                "contracts/grid_cell_contract.schema.json; PVRS is derived by "
                "external/aryas_workresult/pvrs_engine.py in real operation"
            ),
            test_only=True,
            notes=(
                "NOT computed by Arya's engine. Schema-constrained placeholder "
                "only; not an empirical distribution."
            ),
        ),
        "physical_indicators.BF_EHSI": entry(
            meaning="Bare-Field Erosion and Heat Shock Index placeholder",
            unit="dimensionless, schema [0, 2.5]",
            classification="derived_indicator_test_placeholder",
            generation="uniform over provisional schema bounds [0, 2.5]",
            evidence=(
                "contracts/grid_cell_contract.schema.json; BF-EHSI is derived "
                "by external/aryas_workresult/bf_ehsi_engine.py in real operation"
            ),
            test_only=True,
            notes=(
                "NOT computed by Arya's engine. Schema-constrained placeholder "
                "only; not an empirical distribution."
            ),
        ),
        "physical_indicators.SMAP_wetness": entry(
            meaning="Root-zone volumetric soil-moisture placeholder",
            unit="m3/m3, schema [0, 1]",
            classification="source_like_test_placeholder",
            generation="uniform over provisional schema bounds [0, 1]",
            evidence=(
                "contracts/grid_cell_contract.schema.json; "
                "docs/nasa_data_inventory.md documents SMAP sm_rootzone in "
                "m3/m3 over 0-100 cm"
            ),
            test_only=True,
            notes=(
                "Not a SMAP observation. No native-resolution aggregation or "
                "downscaling is claimed."
            ),
        ),
        "physical_indicators.ECOSTRESS_ESI": entry(
            meaning="Evaporative Stress Index placeholder",
            unit="dimensionless, schema [0, 1]",
            classification="source_like_test_placeholder",
            generation="uniform over provisional schema bounds [0, 1]",
            evidence=(
                "contracts/grid_cell_contract.schema.json; "
                "external/aryas_workresult/pvrs_engine.py documents ESI [0, 1]; "
                "docs/nasa_data_inventory.md notes the ESI source is not selected"
            ),
            test_only=True,
            notes=(
                "Not an ECOSTRESS observation. No real ESI product or "
                "observation timestamp exists."
            ),
        ),
        "physical_indicators.LST_anomaly": entry(
            meaning="Land-surface temperature anomaly placeholder",
            unit="degrees Celsius",
            classification="derived_indicator_test_placeholder",
            generation="constant 0.0",
            evidence=(
                "contracts/grid_cell_contract.schema.json has no bound; "
                "external/aryas_workresult/pvrs_engine.py derives an anomaly "
                "from observed LST and a baseline"
            ),
            test_only=True,
            notes=(
                "Constant placeholder. No temperature anomaly was modeled and "
                "no missing observation is being represented as zero."
            ),
        ),
        "physical_indicators.HLS_BSI": entry(
            meaning="Bare-soil index placeholder using the contract field name",
            unit="dimensionless, schema [-1, 1]",
            classification="source_like_test_placeholder",
            generation="uniform over provisional schema bounds [-1, 1]",
            evidence=(
                "contracts/grid_cell_contract.schema.json; "
                "external/aryas_workresult/bf_ehsi_engine.py defines MBSI "
                "[-1, 1]; HLS_BSI vs MBSI naming is unresolved"
            ),
            test_only=True,
            notes=(
                "Not an HLS observation. The MBSI/HLS_BSI naming decision is "
                "still pending."
            ),
        ),
        "physical_indicators.HLS_NDVI": entry(
            meaning="Normalized Difference Vegetation Index placeholder",
            unit="dimensionless, schema [-1, 1]",
            classification="source_like_test_placeholder",
            generation="uniform over provisional schema bounds [-1, 1]",
            evidence=(
                "contracts/grid_cell_contract.schema.json; "
                "external/aryas_workresult/pvrs_engine.py documents NDVI "
                "[-1, 1]; docs/nasa_data_inventory.md notes no verified HLS export"
            ),
            test_only=True,
            notes=(
                "Not an HLS observation. No cloud masking or QA is represented."
            ),
        ),
        "physical_indicators.GPM_rain_7d": entry(
            meaning="Seven-day rainfall accumulation placeholder",
            unit="mm",
            classification="source_like_test_placeholder",
            generation=(
                f"uniform over test-only [0, {GPM_RAIN_7D_TEST_MAX_MM:g}] mm cap"
            ),
            evidence=(
                "contracts/grid_cell_contract.schema.json has minimum 0 and no "
                "maximum; docs/nasa_data_inventory.md documents GPM as mm/hr "
                "and notes no verified export"
            ),
            test_only=True,
            notes=(
                "Not a GPM observation. The 100 mm upper cap is an arbitrary "
                "test-only bound, not a rainfall distribution or threshold."
            ),
        ),
        "physical_indicators.SRTM_slope": entry(
            meaning="Slope placeholder",
            unit="degrees, schema [0, 90]",
            classification="source_like_test_placeholder",
            generation="uniform over provisional schema bounds [0, 90]",
            evidence=(
                "contracts/grid_cell_contract.schema.json; docs/nasa_data_inventory.md "
                "notes SRTM has not been extracted"
            ),
            test_only=True,
            notes=(
                "Not an SRTM observation. Uniform values are schema-constrained "
                "test values, not a terrain distribution."
            ),
        ),
        "operational_flags.missing_observation": entry(
            meaning="Missing-observation flag",
            unit="boolean",
            classification="test_only_constant",
            generation="constant false",
            evidence=(
                "contracts/grid_cell_contract.schema.json requires non-null "
                "indicators; docs/contract_validator_design.md records the "
                "nullable policy as unresolved"
            ),
            test_only=True,
            notes=(
                "The provisional schema cannot represent realistic missingness. "
                "Indicators are always populated, so this flag is always false."
            ),
        ),
        "operational_flags.optical_lag_days": entry(
            meaning="Optical-lag day placeholder",
            unit="days, schema [0, 14]",
            classification="derived_indicator_test_placeholder",
            generation="uniform integer [0, 14]",
            evidence=(
                "contracts/grid_cell_contract.schema.json; "
                "external/aryas_workresult/pvrs_engine.py computes 0..14"
            ),
            test_only=True,
            notes=(
                "NOT computed by PVRS. Schema-constrained placeholder only."
            ),
        ),
        "operational_flags.erosion_alert": entry(
            meaning="Erosion-alert flag placeholder",
            unit="boolean",
            classification="derived_indicator_test_placeholder",
            generation="uniform boolean {false, true}",
            evidence=(
                "contracts/grid_cell_contract.schema.json; the contract has no "
                "ratified BF-EHSI/D_i alert mapping"
            ),
            test_only=True,
            notes=(
                "NOT derived from BF-EHSI or D_i. Arbitrary test-only flag."
            ),
        ),
        "rotation_scenarios": entry(
            meaning="Rotation scenario list",
            unit="not applicable",
            classification="test_only_empty",
            generation="empty list",
            evidence=(
                "contracts/grid_cell_contract.schema.json allows minItems 0; "
                "scenario generation is outside Task 2"
            ),
            test_only=True,
            notes=(
                "No agronomic recommendation or crop type is generated."
            ),
        ),
        "xai_decision_block.why_suggested": entry(
            meaning="Explainability text placeholder",
            unit="text",
            classification="test_only_placeholder",
            generation="constant synthetic-fixture sentence",
            evidence=(
                "contracts/grid_cell_contract.schema.json requires non-empty "
                "strings; docs/ai_core_readiness.md warns against fabricated claims"
            ),
            test_only=True,
            notes="Not a factual explanation and not a recommendation.",
        ),
        "xai_decision_block.multi_benefits": entry(
            meaning="Explainability text placeholder",
            unit="text",
            classification="test_only_placeholder",
            generation="constant synthetic-fixture sentence",
            evidence=(
                "contracts/grid_cell_contract.schema.json; "
                "docs/ai_core_readiness.md"
            ),
            test_only=True,
            notes="No agronomic benefit was calculated.",
        ),
        "xai_decision_block.information_gaps": entry(
            meaning="Explainability text placeholder",
            unit="text",
            classification="test_only_placeholder",
            generation="constant synthetic-fixture sentence",
            evidence=(
                "contracts/grid_cell_contract.schema.json; "
                "docs/ai_core_readiness.md"
            ),
            test_only=True,
            notes="Explicitly states that no satellite observation exists.",
        ),
        "xai_decision_block.local_risks_and_gates": entry(
            meaning="Explainability text placeholder",
            unit="text",
            classification="test_only_placeholder",
            generation="constant synthetic-fixture sentence",
            evidence=(
                "contracts/grid_cell_contract.schema.json; "
                "docs/ai_core_readiness.md"
            ),
            test_only=True,
            notes="No field verification or gate result was produced.",
        ),
        "fiscal_metrics.urea_subsidy_saved_idr": entry(
            meaning="Urea subsidy saving placeholder",
            unit="IDR per hectare",
            classification="derived_indicator_test_placeholder",
            generation="constant 0.0",
            evidence=(
                "contracts/grid_cell_contract.schema.json; fiscal values are "
                "derived by external/aryas_workresult/fiscal_actuarial.py in "
                "real operation"
            ),
            test_only=True,
            notes="NOT calculated by Arya's fiscal engine.",
        ),
        "fiscal_metrics.autp_risk_reduction_pct": entry(
            meaning="AUTP risk-reduction placeholder",
            unit="percent, schema [0, 100]",
            classification="derived_indicator_test_placeholder",
            generation="constant 0.0",
            evidence=(
                "contracts/grid_cell_contract.schema.json; fiscal/actuarial "
                "values are derived by Arya's engine in real operation"
            ),
            test_only=True,
            notes="NOT calculated by Arya's fiscal engine.",
        ),
        "fiscal_metrics.cluster_h3_7_gross_saving_idr": entry(
            meaning="Optional H3-7 cluster gross-saving field",
            unit="IDR",
            classification="omitted_optional_field",
            generation="not generated",
            evidence="contracts/grid_cell_contract.schema.json marks it optional",
            test_only=True,
            notes=(
                "Omitted because cluster fiscal calculations are outside Task 2."
            ),
        ),
        "fiscal_metrics.cluster_h3_7_net_saving_s_net_idr": entry(
            meaning="Optional H3-7 cluster net-saving field",
            unit="IDR",
            classification="omitted_optional_field",
            generation="not generated",
            evidence="contracts/grid_cell_contract.schema.json marks it optional",
            test_only=True,
            notes=(
                "Omitted because cluster fiscal calculations are outside Task 2."
            ),
        ),
        "system_state": entry(
            meaning="System state for UI testing",
            unit="enum string",
            classification="test_only_pattern",
            generation=(
                "deterministic cycle across the three provisional enum values"
            ),
            evidence=(
                "contracts/grid_cell_contract.schema.json; the final abstention "
                "spelling is unresolved"
            ),
            test_only=True,
            notes=(
                "Not a recommendation policy. Both abstention spellings appear "
                "only to exercise the provisional enum."
            ),
        ),
    }


def build_feature(
    h3_index: str,
    contract: Mapping[str, Any],
    config: GenerationConfig,
    ordinal: int,
) -> dict[str, Any]:
    """Build one GeoJSON Feature with geometry and provenance metadata."""

    boundary = h3.cell_to_boundary(h3_index)
    ring: list[list[float]] = [
        [float(longitude), float(latitude)] for latitude, longitude in boundary
    ]
    if not ring:
        raise SyntheticH3GeneratorError(
            f"h3.cell_to_boundary returned no coordinates for {h3_index!r}."
        )
    if ring[0] != ring[-1]:
        ring.append(list(ring[0]))
    if len(ring) < 4:
        raise SyntheticH3GeneratorError(
            f"H3 boundary for {h3_index!r} produced an invalid ring."
        )

    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [ring],
        },
        "properties": {
            "h3_index": h3_index,
            "is_synthetic": True,
            "data_source": "synthetic",
            "generator_name": GENERATOR_NAME,
            "generator_version": GENERATOR_VERSION,
            "random_seed": config.seed,
            "h3_resolution": config.resolution,
            "roi_source": _display_path(config.roi_path),
            "selection_method": SELECTION_METHOD,
            "selection_ordinal": ordinal,
            # The ROI is a bbox, not a verified paddy mask.
            "land_cover": "unverified",
            "contract_schema": CONTRACT_SCHEMA_DISPLAY_PATH,
            "contract_schema_status": "PROVISIONAL",
            "contract": dict(contract),
        },
    }


def generate_feature_collection(
    config: GenerationConfig | None = None,
    *,
    validate_contracts: bool = True,
) -> GenerationResult:
    """Generate the deterministic synthetic GeoJSON FeatureCollection.

    Args:
        config: Generation configuration. Defaults are 1,000 res-9 cells and the
            repository ROI/output paths.
        validate_contracts: Validate every nested contract fixture with Task 1's
            validator, including provisional H3/parent semantics.

    Returns:
        An in-memory :class:`GenerationResult`.

    Raises:
        SyntheticH3GeneratorError: For ROI, selection, contract, or config errors.
    """

    active_config = config or GenerationConfig()
    roi_geometry = load_roi_geometry(active_config.roi_path)
    candidates = generate_candidate_cells(
        roi_geometry, active_config.resolution
    )
    selected = select_representative_cells(
        candidates, active_config.target_count
    )

    rng = np.random.default_rng(active_config.seed)
    validator: ContractValidator | None = None
    if validate_contracts:
        validator = ContractValidator(
            schema_path=CONTRACT_SCHEMA_PATH,
            enable_provisional_semantics=True,
        )

    features: list[dict[str, Any]] = []
    for ordinal, cell in enumerate(selected):
        contract = build_synthetic_contract(cell, rng, ordinal=ordinal)
        if validator is not None:
            validation = validator.validate(contract)
            if not validation.is_valid:
                first_error = validation.errors[0]
                raise ContractCompatibilityError(
                    f"Synthetic contract for {cell} failed validation: "
                    f"{first_error.code} at {first_error.path}: "
                    f"{first_error.message}"
                )
        features.append(
            build_feature(cell, contract, active_config, ordinal)
        )

    candidate_parents = {
        h3.cell_to_parent(cell, 7) for cell in candidates
    }
    selected_parents = {
        h3.cell_to_parent(cell, 7) for cell in selected
    }
    warnings = [
        (
            "All attribute values are synthetic test placeholders, not NASA "
            "observations."
        ),
        (
            "The ROI is a bounding box, not a verified paddy mask; land_cover "
            "is 'unverified'."
        ),
        (
            "PVRS and BF_EHSI are schema-constrained placeholders and were NOT "
            "computed by Arya's engines."
        ),
        (
            "missing_observation is always false because the provisional schema "
            "requires non-null indicators; realistic missingness cannot be "
            "represented."
        ),
        (
            "rotation_scenarios is empty and fiscal metrics are 0.0 placeholders; "
            "no agronomic or fiscal recommendation is generated."
        ),
        (
            "SMAP, GPM, ECOSTRESS, HLS, and SRTM values are not independent "
            "per-cell observations; no native-resolution aggregation is claimed."
        ),
        (
            "system_state cycles across the provisional enum for UI testing; "
            "this is not a recommendation policy."
        ),
        (
            "The contract schema is PROVISIONAL and has not been ratified."
        ),
    ]

    feature_collection: dict[str, Any] = {
        "type": "FeatureCollection",
        "name": f"CYBER_KATAM_SYNTHETIC_H3_{active_config.target_count}",
        "is_synthetic": True,
        "data_source": "synthetic",
        "warnings": warnings,
        "generator": {
            "name": GENERATOR_NAME,
            "version": GENERATOR_VERSION,
            "random_seed": active_config.seed,
            "h3_resolution": active_config.resolution,
            "target_count": active_config.target_count,
            "candidate_count": len(candidates),
            "selected_count": len(selected),
            "roi_source": _display_path(active_config.roi_path),
            "selection_method": SELECTION_METHOD,
            "selection_details": {
                "group_resolution": 7,
                "candidate_group_count": len(candidate_parents),
                "selected_group_count": len(selected_parents),
                "description": (
                    "Cells are grouped by H3 res-7 parent, groups and cells are "
                    "sorted by H3 index, and one cell per group is taken per "
                    "round until the target count is reached."
                ),
            },
            "contract_schema": CONTRACT_SCHEMA_DISPLAY_PATH,
            "contract_schema_status": "PROVISIONAL",
            "contract_payloads_validated": validator is not None,
            "contracts_validated": len(selected) if validator else 0,
        },
        "synthetic_variable_manifest": build_synthetic_variable_manifest(),
        "features": features,
    }

    return GenerationResult(
        feature_collection=feature_collection,
        cells=tuple(selected),
        candidate_count=len(candidates),
        selected_count=len(selected),
        roi_source=_display_path(active_config.roi_path),
        contracts_validated=len(selected) if validator else 0,
    )


def write_geojson(
    feature_collection: Mapping[str, Any], output_path: str | Path
) -> int:
    """Write a GeoJSON FeatureCollection and return its UTF-8 byte size.

    The received ``banyumas_h3_precomputed.geojson`` and the ROI file are
    protected from accidental overwrite.

    Args:
        feature_collection: GeoJSON FeatureCollection mapping.
        output_path: Destination path.

    Returns:
        File size in bytes.

    Raises:
        OutputWriteError: If the path is protected, invalid, or unwritable.
    """

    path = Path(output_path).expanduser().resolve()
    if path == PRECOMPUTED_GEOJSON_PATH:
        raise OutputWriteError(
            "Refusing to overwrite the received precomputed GeoJSON at "
            f"'{PRECOMPUTED_GEOJSON_PATH}'."
        )
    if path == DEFAULT_ROI_PATH:
        raise OutputWriteError(
            f"Refusing to overwrite the ROI at '{DEFAULT_ROI_PATH}'."
        )
    if not path.name:
        raise OutputWriteError("Output path must include a file name.")
    if path.exists() and path.is_dir():
        raise OutputWriteError(f"Output path is a directory: {path}")
    if feature_collection.get("type") != "FeatureCollection":
        raise OutputWriteError(
            "Output must be a GeoJSON FeatureCollection."
        )
    if not isinstance(feature_collection.get("features"), list):
        raise OutputWriteError(
            "GeoJSON FeatureCollection must contain a features list."
        )

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(
            feature_collection,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        path.write_text(text, encoding="utf-8")
    except (OSError, TypeError, ValueError) as exc:
        raise OutputWriteError(
            f"Cannot write GeoJSON to '{path}': {exc}"
        ) from exc

    try:
        return path.stat().st_size
    except OSError as exc:
        raise OutputWriteError(
            f"GeoJSON was written but its size could not be read: {path}: {exc}"
        ) from exc


def generate_and_write(
    config: GenerationConfig | None = None,
    *,
    validate_contracts: bool = True,
) -> GenerationResult:
    """Generate the fixture, write it, and return the completed result."""

    active_config = config or GenerationConfig()
    result = generate_feature_collection(
        active_config, validate_contracts=validate_contracts
    )
    file_size_bytes = write_geojson(
        result.feature_collection, active_config.output_path
    )
    return replace(
        result,
        output_path=active_config.output_path,
        file_size_bytes=file_size_bytes,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Generate a deterministic, explicitly synthetic 1,000-cell H3 "
            "GeoJSON fixture from the Banyumas bounding-box ROI."
        )
    )
    parser.add_argument(
        "--roi",
        type=Path,
        default=DEFAULT_ROI_PATH,
        help=f"ROI GeoJSON path (default: {DEFAULT_ROI_PATH})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Output GeoJSON path (default: {DEFAULT_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Synthetic-attribute seed (default: {DEFAULT_SEED})",
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=DEFAULT_RESOLUTION,
        help=f"H3 resolution; synthetic fixtures require 9 (default: {DEFAULT_RESOLUTION})",
    )
    parser.add_argument(
        "--target-count",
        type=int,
        default=DEFAULT_TARGET_COUNT,
        help=f"Exact number of cells (default: {DEFAULT_TARGET_COUNT})",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the generator CLI and print a provenance summary."""

    args = build_arg_parser().parse_args(argv)
    try:
        config = GenerationConfig(
            roi_path=args.roi,
            output_path=args.output,
            resolution=args.resolution,
            target_count=args.target_count,
            seed=args.seed,
        )
        result = generate_and_write(config)
    except (SyntheticH3GeneratorError, SchemaConfigurationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("CYBER-KATAM synthetic H3 generator")
    print(f"  ROI source        : {result.roi_source}")
    print(f"  Candidate cells   : {result.candidate_count}")
    print(f"  Selected cells    : {result.selected_count}")
    print(f"  H3 resolution     : {config.resolution}")
    print(f"  Random seed       : {config.seed}")
    print(f"  Contracts checked : {result.contracts_validated}")
    print(f"  Output            : {result.output_path}")
    print(
        "  Output size       : "
        f"{result.file_size_bytes if result.file_size_bytes is not None else 'unknown'} bytes"
    )
    print("  Status            : SYNTHETIC TEST FIXTURE - NOT NASA DATA")
    for warning in result.feature_collection.get("warnings", []):
        print(f"  WARNING           : {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
