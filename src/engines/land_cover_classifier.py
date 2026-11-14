"""Land-cover record management for H3 cells.

This module does **not** classify satellite imagery and does not infer paddy
fields from NDVI, BSI, LST, a bounding box, or random values. It accepts
land-cover information from an external source, validates it, manages
verification/provenance, and serializes a provisional sidecar keyed by H3 index.

The strict grid-cell contract in ``contracts/grid_cell_contract.schema.json`` is
never modified by this module.
"""

from __future__ import annotations

import copy
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Final

import h3

from src.models.land_cover import (
    MAX_COVERAGE_TOLERANCE,
    MODULE_NAME,
    MODULE_VERSION,
    SIDECAR_SCHEMA_VERSION,
    CoverageFractions,
    LandCoverClass,
    LandCoverConfig,
    LandCoverLayer,
    LandCoverObservation,
    LandCoverRecord,
    Provenance,
    SourceKind,
    VerificationStatus,
)

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
TASK2_GEOJSON_PATH: Final[Path] = (
    REPO_ROOT / "data" / "mock" / "banyumas_h3_synthetic.geojson"
)
ROI_PATH: Final[Path] = (
    REPO_ROOT / "data" / "boundaries" / "banyumas_paddy_roi.geojson"
)
CONTRACT_SCHEMA_PATH: Final[Path] = (
    REPO_ROOT / "contracts" / "grid_cell_contract.schema.json"
)
EXTERNAL_ROOT: Final[Path] = REPO_ROOT / "external"
ALLOWED_OUTPUT_ROOT: Final[Path] = REPO_ROOT / "data" / "land_cover"

_OBSERVATION_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "h3_index",
        "land_cover_class",
        "verification_status",
        "source_kind",
        "coverage",
        "provenance",
        "notes",
    }
)
_COVERAGE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "paddy_fraction",
        "non_paddy_fraction",
        "other_fraction",
        "method",
        "valid_pixel_count",
        "total_pixel_count",
    }
)
_PROVENANCE_FIELDS: Final[tuple[str, ...]] = (
    "source",
    "dataset_id",
    "product_version",
    "observation_date",
    "processing_date",
    "spatial_resolution_m",
    "classification_method",
    "verification_method",
    "verification_date",
    "verification_reference",
    "reference_dataset",
    "license",
    "attribution",
)
_PROVENANCE_FIELD_SET: Final[frozenset[str]] = frozenset(_PROVENANCE_FIELDS)
_STRING_PROVENANCE_FIELDS: Final[tuple[str, ...]] = (
    "source",
    "dataset_id",
    "product_version",
    "classification_method",
    "verification_method",
    "verification_reference",
    "reference_dataset",
    "license",
    "attribution",
)
_DATE_PROVENANCE_FIELDS: Final[tuple[str, ...]] = (
    "observation_date",
    "processing_date",
    "verification_date",
)
_SIDECAR_RECORD_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "h3_index",
        "land_cover_class",
        "verification_status",
        "source_kind",
        "is_synthetic",
        "coverage",
        "provenance",
        "notes",
    }
)
_SIDECAR_TOP_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "status",
        "module",
        "module_version",
        "records",
        "warnings",
    }
)


class LandCoverErrorCode:
    """Stable error codes for land-cover input, validation, and serialization."""

    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    INVALID_H3_INDEX = "INVALID_H3_INDEX"
    UNSUPPORTED_H3_RESOLUTION = "UNSUPPORTED_H3_RESOLUTION"
    UNKNOWN_LAND_COVER_CLASS = "UNKNOWN_LAND_COVER_CLASS"
    UNKNOWN_VERIFICATION_STATUS = "UNKNOWN_VERIFICATION_STATUS"
    UNKNOWN_SOURCE_KIND = "UNKNOWN_SOURCE_KIND"
    MISSING_SOURCE = "MISSING_SOURCE"
    INVALID_COVERAGE = "INVALID_COVERAGE"
    INCOMPLETE_VERIFICATION_PROVENANCE = "INCOMPLETE_VERIFICATION_PROVENANCE"
    SYNTHETIC_CANNOT_BE_VERIFIED = "SYNTHETIC_CANNOT_BE_VERIFIED"
    DUPLICATE_H3_INDEX = "DUPLICATE_H3_INDEX"
    CONFLICTING_LAND_COVER = "CONFLICTING_LAND_COVER"
    DUPLICATE_JSON_KEY = "DUPLICATE_JSON_KEY"
    UNSUPPORTED_SCHEMA_VERSION = "UNSUPPORTED_SCHEMA_VERSION"
    INCONSISTENT_VERIFICATION_STATUS = "INCONSISTENT_VERIFICATION_STATUS"
    INCONSISTENT_SYNTHETIC_FLAG = "INCONSISTENT_SYNTHETIC_FLAG"
    UNSUPPORTED_POLICY = "UNSUPPORTED_POLICY"
    UNSAFE_OUTPUT_PATH = "UNSAFE_OUTPUT_PATH"
    SIDECAR_READ_ERROR = "SIDECAR_READ_ERROR"


class LandCoverWarning:
    """Warning codes emitted for accepted but incomplete inputs."""

    COVERAGE_METHOD_UNKNOWN = "COVERAGE_METHOD_UNKNOWN"
    COVERAGE_EMPTY = "COVERAGE_EMPTY"


class LandCoverError(Exception):
    """Base error with a stable code and optional H3/path context."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        h3_index: str | None = None,
        path: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.h3_index = h3_index
        self.path = path


class LandCoverInputError(LandCoverError):
    """Raised when a payload cannot be parsed into domain observations."""


class LandCoverValidationError(LandCoverError):
    """Raised when a domain observation violates validation rules."""


class LandCoverSerializationError(LandCoverError):
    """Raised when a sidecar cannot be serialized or deserialized safely."""


class UnsupportedPolicyError(LandCoverValidationError):
    """Raised when an unapproved policy is requested."""


@dataclass(frozen=True, slots=True)
class _NormalizedObservation:
    h3_index: str
    land_cover_class: LandCoverClass
    verification_status: VerificationStatus
    source_kind: SourceKind
    is_synthetic: bool | None
    coverage: CoverageFractions | None
    provenance: Provenance | None
    notes: str | None
    warnings: tuple[str, ...]


class _DuplicateJSONKey(ValueError):
    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(key)


def _object_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJSONKey(key)
        result[key] = value
    return result


def _loads_json_strict(
    text: str,
    *,
    error_type: type[LandCoverError],
) -> Any:
    try:
        return json.loads(text, object_pairs_hook=_object_pairs_hook)
    except json.JSONDecodeError as exc:
        raise error_type(
            LandCoverErrorCode.INVALID_PAYLOAD,
            f"Malformed JSON at line {exc.lineno}, column {exc.colno}.",
        ) from exc
    except _DuplicateJSONKey as exc:
        code = (
            LandCoverErrorCode.DUPLICATE_H3_INDEX
            if h3.is_valid_cell(exc.key)
            else LandCoverErrorCode.DUPLICATE_JSON_KEY
        )
        raise error_type(
            code,
            f"Duplicate JSON key: {exc.key!r}.",
        ) from exc


def _coerce_enum(
    value: Any,
    enum_type: type[LandCoverClass]
    | type[VerificationStatus]
    | type[SourceKind],
    code: str,
    field_name: str,
    *,
    h3_index: str | None = None,
    path: str | None = None,
    error_type: type[LandCoverError] = LandCoverInputError,
) -> Any:
    if value is None:
        return None
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        try:
            return enum_type(value)
        except ValueError:
            raise error_type(
                code,
                f"Unknown {field_name}: {value!r}.",
                h3_index=h3_index,
                path=path or field_name,
            ) from None
    raise error_type(
        code,
        f"{field_name} must be a string or {enum_type.__name__}.",
        h3_index=h3_index,
        path=path or field_name,
    )


def _parse_optional_string(
    value: Any,
    field_name: str,
    *,
    h3_index: str | None = None,
    path: str | None = None,
    code: str = LandCoverErrorCode.INVALID_PAYLOAD,
    error_type: type[LandCoverError] = LandCoverInputError,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise error_type(
            code,
            f"{field_name} must be a string or null.",
            h3_index=h3_index,
            path=path or field_name,
        )
    return value


def _parse_optional_number(
    value: Any,
    field_name: str,
    *,
    h3_index: str | None = None,
    path: str | None = None,
    code: str = LandCoverErrorCode.INVALID_PAYLOAD,
    error_type: type[LandCoverError] = LandCoverInputError,
) -> int | float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise error_type(
            code,
            f"{field_name} must be a number or null.",
            h3_index=h3_index,
            path=path or field_name,
        )
    return value


def _parse_optional_int(
    value: Any,
    field_name: str,
    *,
    h3_index: str | None = None,
    path: str | None = None,
    code: str = LandCoverErrorCode.INVALID_PAYLOAD,
    error_type: type[LandCoverError] = LandCoverInputError,
) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise error_type(
            code,
            f"{field_name} must be an integer or null.",
            h3_index=h3_index,
            path=path or field_name,
        )
    return value


def _parse_coverage(
    value: Any,
    *,
    h3_index: str | None = None,
    error_type: type[LandCoverError] = LandCoverInputError,
) -> CoverageFractions | None:
    if value is None:
        return None
    if isinstance(value, CoverageFractions):
        return value
    if not isinstance(value, Mapping):
        raise error_type(
            LandCoverErrorCode.INVALID_COVERAGE,
            "coverage must be an object or null.",
            h3_index=h3_index,
            path="coverage",
        )

    unknown_fields = set(value) - _COVERAGE_FIELDS
    if unknown_fields:
        names = ", ".join(sorted(str(field) for field in unknown_fields))
        raise error_type(
            LandCoverErrorCode.INVALID_COVERAGE,
            f"Unknown coverage field(s): {names}.",
            h3_index=h3_index,
            path="coverage",
        )

    return CoverageFractions(
        paddy_fraction=_parse_optional_number(
            value.get("paddy_fraction"),
            "coverage.paddy_fraction",
            h3_index=h3_index,
            code=LandCoverErrorCode.INVALID_COVERAGE,
            error_type=error_type,
        ),
        non_paddy_fraction=_parse_optional_number(
            value.get("non_paddy_fraction"),
            "coverage.non_paddy_fraction",
            h3_index=h3_index,
            code=LandCoverErrorCode.INVALID_COVERAGE,
            error_type=error_type,
        ),
        other_fraction=_parse_optional_number(
            value.get("other_fraction"),
            "coverage.other_fraction",
            h3_index=h3_index,
            code=LandCoverErrorCode.INVALID_COVERAGE,
            error_type=error_type,
        ),
        method=_parse_optional_string(
            value.get("method"),
            "coverage.method",
            h3_index=h3_index,
            code=LandCoverErrorCode.INVALID_COVERAGE,
            error_type=error_type,
        ),
        valid_pixel_count=_parse_optional_int(
            value.get("valid_pixel_count"),
            "coverage.valid_pixel_count",
            h3_index=h3_index,
            code=LandCoverErrorCode.INVALID_COVERAGE,
            error_type=error_type,
        ),
        total_pixel_count=_parse_optional_int(
            value.get("total_pixel_count"),
            "coverage.total_pixel_count",
            h3_index=h3_index,
            code=LandCoverErrorCode.INVALID_COVERAGE,
            error_type=error_type,
        ),
    )


def _parse_provenance(
    value: Any,
    *,
    h3_index: str | None = None,
    error_type: type[LandCoverError] = LandCoverInputError,
) -> Provenance | None:
    if value is None:
        return None
    if isinstance(value, Provenance):
        return value
    if not isinstance(value, Mapping):
        raise error_type(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "provenance must be an object or null.",
            h3_index=h3_index,
            path="provenance",
        )

    unknown_fields = set(value) - _PROVENANCE_FIELD_SET
    if unknown_fields:
        names = ", ".join(sorted(str(field) for field in unknown_fields))
        raise error_type(
            LandCoverErrorCode.INVALID_PAYLOAD,
            f"Unknown provenance field(s): {names}.",
            h3_index=h3_index,
            path="provenance",
        )

    # coverage.method is intentionally the only coverage-method location.
    field_values = {
        field: _parse_optional_string(
            value.get(field),
            f"provenance.{field}",
            h3_index=h3_index,
            error_type=error_type,
        )
        for field in _STRING_PROVENANCE_FIELDS
    }
    field_values.update(
        {
            field: _parse_optional_string(
                value.get(field),
                f"provenance.{field}",
                h3_index=h3_index,
                error_type=error_type,
            )
            for field in _DATE_PROVENANCE_FIELDS
        }
    )
    field_values["spatial_resolution_m"] = _parse_optional_number(
        value.get("spatial_resolution_m"),
        "provenance.spatial_resolution_m",
        h3_index=h3_index,
        error_type=error_type,
    )
    return Provenance(**field_values)


def _parse_observation_mapping(
    value: Any,
    *,
    key_h3: str | None = None,
    error_type: type[LandCoverError] = LandCoverInputError,
) -> LandCoverObservation:
    if not isinstance(value, Mapping):
        raise error_type(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "Each observation must be an object.",
            path="observation",
        )

    unknown_fields = set(value) - _OBSERVATION_FIELDS
    if unknown_fields:
        names = ", ".join(sorted(str(field) for field in unknown_fields))
        raise error_type(
            LandCoverErrorCode.INVALID_PAYLOAD,
            f"Unknown observation field(s): {names}.",
            path="observation",
        )

    raw_h3 = value.get("h3_index")
    if key_h3 is not None:
        if raw_h3 is None:
            raw_h3 = key_h3
        elif raw_h3 != key_h3:
            raise error_type(
                LandCoverErrorCode.INVALID_PAYLOAD,
                "Observation h3_index does not match its mapping key.",
                h3_index=str(raw_h3),
                path="h3_index",
            )
    if raw_h3 is None:
        raise error_type(
            LandCoverErrorCode.INVALID_H3_INDEX,
            "h3_index is required.",
            path="h3_index",
        )
    if not isinstance(raw_h3, str) or not raw_h3:
        raise error_type(
            LandCoverErrorCode.INVALID_H3_INDEX,
            "h3_index must be a non-empty string.",
            h3_index=str(raw_h3) if raw_h3 is not None else None,
            path="h3_index",
        )

    return LandCoverObservation(
        h3_index=raw_h3,
        land_cover_class=_coerce_enum(
            value.get("land_cover_class"),
            LandCoverClass,
            LandCoverErrorCode.UNKNOWN_LAND_COVER_CLASS,
            "land_cover_class",
            h3_index=raw_h3,
            error_type=error_type,
        ),
        verification_status=_coerce_enum(
            value.get("verification_status"),
            VerificationStatus,
            LandCoverErrorCode.UNKNOWN_VERIFICATION_STATUS,
            "verification_status",
            h3_index=raw_h3,
            error_type=error_type,
        ),
        source_kind=_coerce_enum(
            value.get("source_kind"),
            SourceKind,
            LandCoverErrorCode.UNKNOWN_SOURCE_KIND,
            "source_kind",
            h3_index=raw_h3,
            error_type=error_type,
        ),
        coverage=_parse_coverage(
            value.get("coverage"),
            h3_index=raw_h3,
            error_type=error_type,
        ),
        provenance=_parse_provenance(
            value.get("provenance"),
            h3_index=raw_h3,
            error_type=error_type,
        ),
        notes=_parse_optional_string(
            value.get("notes"),
            "notes",
            h3_index=raw_h3,
            error_type=error_type,
        ),
    )


def parse_land_cover_payload(
    payload: (
        Mapping[str, Any]
        | Sequence[Mapping[str, Any] | LandCoverObservation]
        | LandCoverObservation
        | str
    ),
) -> list[LandCoverObservation]:
    """Parse a single observation, a list, or an H3-keyed mapping.

    Accepted forms:

    - ``LandCoverObservation``
    - observation mapping with ``h3_index``
    - mapping keyed by H3 index
    - list/tuple of observation mappings or observations
    - JSON string of any accepted form

    H3-keyed mapping keys are validated during parsing so the mapping can be
    recognised as an H3-keyed collection. H3 values in single observations and
    list items are fully validated by
    :func:`validate_land_cover_observation` or
    :func:`process_land_cover_observations`.

    Sidecar payloads must be loaded with :func:`deserialize_land_cover_layer`.
    """

    if isinstance(payload, LandCoverObservation):
        return [payload]

    if isinstance(payload, str):
        return parse_land_cover_payload(
            _loads_json_strict(payload, error_type=LandCoverInputError)
        )

    if isinstance(payload, Mapping):
        if "h3_index" in payload:
            return [_parse_observation_mapping(payload)]
        if "records" in payload:
            raise LandCoverInputError(
                LandCoverErrorCode.INVALID_PAYLOAD,
                "Sidecar payloads must be loaded with "
                "deserialize_land_cover_layer().",
                path="records",
            )

        observations: list[LandCoverObservation] = []
        for key, value in payload.items():
            if not isinstance(key, str) or not h3.is_valid_cell(key):
                raise LandCoverInputError(
                    LandCoverErrorCode.INVALID_H3_INDEX,
                    f"Invalid H3 mapping key: {key!r}.",
                    h3_index=str(key),
                    path="h3_index",
                )
            observations.append(
                _parse_observation_mapping(value, key_h3=key)
            )
        return observations

    if isinstance(payload, Sequence) and not isinstance(
        payload, (str, bytes, bytearray)
    ):
        observations = []
        for index, item in enumerate(payload):
            if isinstance(item, LandCoverObservation):
                observations.append(item)
            elif isinstance(item, Mapping):
                observations.append(_parse_observation_mapping(item))
            else:
                raise LandCoverInputError(
                    LandCoverErrorCode.INVALID_PAYLOAD,
                    "Each observation must be an object or "
                    "LandCoverObservation.",
                    path=f"[{index}]",
                )
        return observations

    raise LandCoverInputError(
        LandCoverErrorCode.INVALID_PAYLOAD,
        f"Unsupported payload type: {type(payload).__name__}.",
        path="payload",
    )


def _normalize_config(config: LandCoverConfig | None) -> LandCoverConfig:
    if config is None:
        return LandCoverConfig()
    if not isinstance(config, LandCoverConfig):
        raise LandCoverInputError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "config must be a LandCoverConfig or null.",
            path="config",
        )

    resolution = config.expected_resolution
    if resolution is not None:
        if (
            not isinstance(resolution, int)
            or isinstance(resolution, bool)
            or not 0 <= resolution <= 15
        ):
            raise LandCoverInputError(
                LandCoverErrorCode.INVALID_PAYLOAD,
                "expected_resolution must be an integer from 0 to 15 or null.",
                path="config.expected_resolution",
            )

    tolerance = config.coverage_tolerance
    if (
        not _is_finite_number(tolerance)
        or not 0.0 <= float(tolerance) <= MAX_COVERAGE_TOLERANCE
    ):
        raise LandCoverInputError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "coverage_tolerance must be a finite number from 0 to "
            f"{MAX_COVERAGE_TOLERANCE}.",
            path="config.coverage_tolerance",
        )

    if config.derive_class_from_coverage:
        raise UnsupportedPolicyError(
            LandCoverErrorCode.UNSUPPORTED_POLICY,
            "Coverage-derived land-cover classes are not enabled in v0.1.",
            path="config.derive_class_from_coverage",
        )
    if config.conflict_policy != "ERROR":
        raise UnsupportedPolicyError(
            LandCoverErrorCode.UNSUPPORTED_POLICY,
            "Only conflict_policy='ERROR' is supported in v0.1.",
            path="config.conflict_policy",
        )

    return config


def _output_validation_config() -> LandCoverConfig:
    """Return the validation policy used for sidecar serialization.

    The sidecar validator accepts coverage sums up to the maximum permitted
    tolerance so a layer built with any allowed tolerance can round-trip.
    Expected H3 resolution remains the default resolution 9.
    """

    return LandCoverConfig(coverage_tolerance=MAX_COVERAGE_TOLERANCE)


def _validate_h3(h3_index: str, config: LandCoverConfig) -> None:
    if not isinstance(h3_index, str) or not h3_index:
        raise LandCoverValidationError(
            LandCoverErrorCode.INVALID_H3_INDEX,
            "h3_index must be a non-empty string.",
            path="h3_index",
        )
    if not h3.is_valid_cell(h3_index):
        raise LandCoverValidationError(
            LandCoverErrorCode.INVALID_H3_INDEX,
            "h3_index is not a valid H3 cell index.",
            h3_index=h3_index,
            path="h3_index",
        )
    if (
        config.expected_resolution is not None
        and h3.get_resolution(h3_index) != config.expected_resolution
    ):
        raise LandCoverValidationError(
            LandCoverErrorCode.UNSUPPORTED_H3_RESOLUTION,
            "h3_index resolution "
            f"{h3.get_resolution(h3_index)} does not match expected "
            f"resolution {config.expected_resolution}.",
            h3_index=h3_index,
            path="h3_index",
        )


def _is_finite_number(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def _validate_coverage(
    coverage: CoverageFractions | None,
    config: LandCoverConfig,
    *,
    h3_index: str,
) -> tuple[str, ...]:
    if coverage is None:
        return ()
    if not isinstance(coverage, CoverageFractions):
        raise LandCoverValidationError(
            LandCoverErrorCode.INVALID_COVERAGE,
            "coverage must be a CoverageFractions object or null.",
            h3_index=h3_index,
            path="coverage",
        )

    warnings: list[str] = []
    fractions = (
        ("paddy_fraction", coverage.paddy_fraction),
        ("non_paddy_fraction", coverage.non_paddy_fraction),
        ("other_fraction", coverage.other_fraction),
    )
    total = 0.0
    for field_name, value in fractions:
        if value is None:
            continue
        if not _is_finite_number(value):
            raise LandCoverValidationError(
                LandCoverErrorCode.INVALID_COVERAGE,
                f"coverage.{field_name} must be a finite number or null.",
                h3_index=h3_index,
                path=f"coverage.{field_name}",
            )
        numeric_value = float(value)
        if not 0.0 <= numeric_value <= 1.0:
            raise LandCoverValidationError(
                LandCoverErrorCode.INVALID_COVERAGE,
                f"coverage.{field_name} must be within [0, 1].",
                h3_index=h3_index,
                path=f"coverage.{field_name}",
            )
        total += numeric_value

    if total > 1.0 + float(config.coverage_tolerance):
        raise LandCoverValidationError(
            LandCoverErrorCode.INVALID_COVERAGE,
            "Known coverage fractions must not sum to more than 1.0.",
            h3_index=h3_index,
            path="coverage",
        )

    valid_pixels = coverage.valid_pixel_count
    total_pixels = coverage.total_pixel_count
    if valid_pixels is not None:
        if (
            not isinstance(valid_pixels, int)
            or isinstance(valid_pixels, bool)
            or valid_pixels < 0
        ):
            raise LandCoverValidationError(
                LandCoverErrorCode.INVALID_COVERAGE,
                "coverage.valid_pixel_count must be a non-negative integer "
                "or null.",
                h3_index=h3_index,
                path="coverage.valid_pixel_count",
            )
    if total_pixels is not None:
        if (
            not isinstance(total_pixels, int)
            or isinstance(total_pixels, bool)
            or total_pixels < 0
        ):
            raise LandCoverValidationError(
                LandCoverErrorCode.INVALID_COVERAGE,
                "coverage.total_pixel_count must be a non-negative integer "
                "or null.",
                h3_index=h3_index,
                path="coverage.total_pixel_count",
            )
    if (
        valid_pixels is not None
        and total_pixels is not None
        and valid_pixels > total_pixels
    ):
        raise LandCoverValidationError(
            LandCoverErrorCode.INVALID_COVERAGE,
            "coverage.valid_pixel_count must not exceed total_pixel_count.",
            h3_index=h3_index,
            path="coverage.valid_pixel_count",
        )

    method = coverage.method
    if method is not None:
        if not isinstance(method, str) or not method.strip():
            raise LandCoverValidationError(
                LandCoverErrorCode.INVALID_COVERAGE,
                "coverage.method must be a non-empty string or null.",
                h3_index=h3_index,
                path="coverage.method",
            )
    else:
        warnings.append(LandCoverWarning.COVERAGE_METHOD_UNKNOWN)

    if (
        all(value is None for _, value in fractions)
        and method is None
        and valid_pixels is None
        and total_pixels is None
    ):
        warnings.append(LandCoverWarning.COVERAGE_EMPTY)

    return tuple(warnings)


def _validate_provenance(
    provenance: Provenance | None,
    *,
    h3_index: str,
) -> None:
    if provenance is None:
        return
    if not isinstance(provenance, Provenance):
        raise LandCoverValidationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "provenance must be a Provenance object or null.",
            h3_index=h3_index,
            path="provenance",
        )

    for field_name in _STRING_PROVENANCE_FIELDS:
        value = getattr(provenance, field_name)
        if value is not None and (
            not isinstance(value, str) or not value.strip()
        ):
            raise LandCoverValidationError(
                LandCoverErrorCode.INVALID_PAYLOAD,
                f"provenance.{field_name} must be a non-empty string or null.",
                h3_index=h3_index,
                path=f"provenance.{field_name}",
            )

    for field_name in _DATE_PROVENANCE_FIELDS:
        value = getattr(provenance, field_name)
        if value is None:
            continue
        if not isinstance(value, str):
            raise LandCoverValidationError(
                LandCoverErrorCode.INVALID_PAYLOAD,
                f"provenance.{field_name} must be an ISO date string or null.",
                h3_index=h3_index,
                path=f"provenance.{field_name}",
            )
        try:
            date.fromisoformat(value)
        except ValueError:
            raise LandCoverValidationError(
                LandCoverErrorCode.INVALID_PAYLOAD,
                f"provenance.{field_name} must be an ISO date (YYYY-MM-DD).",
                h3_index=h3_index,
                path=f"provenance.{field_name}",
            ) from None

    resolution = provenance.spatial_resolution_m
    if resolution is not None:
        if not _is_finite_number(resolution) or float(resolution) <= 0.0:
            raise LandCoverValidationError(
                LandCoverErrorCode.INVALID_PAYLOAD,
                "provenance.spatial_resolution_m must be a positive finite "
                "number or null.",
                h3_index=h3_index,
                path="provenance.spatial_resolution_m",
            )


def _validate_verification_completeness(
    status: VerificationStatus,
    provenance: Provenance | None,
    *,
    h3_index: str,
) -> None:
    required_fields: tuple[str, ...] = ()
    if status == VerificationStatus.FIELD_VERIFIED:
        required_fields = (
            "verification_method",
            "verification_date",
            "verification_reference",
        )
    elif status == VerificationStatus.REFERENCE_VALIDATED:
        required_fields = (
            "reference_dataset",
            "verification_method",
            "verification_date",
        )

    if not required_fields:
        return

    missing = [
        field_name
        for field_name in required_fields
        if provenance is None or getattr(provenance, field_name) is None
    ]
    if missing:
        raise LandCoverValidationError(
            LandCoverErrorCode.INCOMPLETE_VERIFICATION_PROVENANCE,
            "Missing verification provenance field(s): "
            + ", ".join(missing)
            + ".",
            h3_index=h3_index,
            path="provenance",
        )


def _derive_is_synthetic(source_kind: SourceKind) -> bool | None:
    if source_kind == SourceKind.SYNTHETIC_MOCK:
        return True
    if source_kind == SourceKind.UNKNOWN_SOURCE:
        return None
    return False


def _normalize_observation(
    observation: LandCoverObservation,
    config: LandCoverConfig,
) -> _NormalizedObservation:
    if not isinstance(observation, LandCoverObservation):
        raise LandCoverInputError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "observation must be a LandCoverObservation; use "
            "parse_land_cover_payload() for raw mappings.",
            path="observation",
        )

    _validate_h3(observation.h3_index, config)

    land_cover_class = _coerce_enum(
        observation.land_cover_class,
        LandCoverClass,
        LandCoverErrorCode.UNKNOWN_LAND_COVER_CLASS,
        "land_cover_class",
        h3_index=observation.h3_index,
        error_type=LandCoverValidationError,
    ) or LandCoverClass.UNKNOWN
    verification_status = _coerce_enum(
        observation.verification_status,
        VerificationStatus,
        LandCoverErrorCode.UNKNOWN_VERIFICATION_STATUS,
        "verification_status",
        h3_index=observation.h3_index,
        error_type=LandCoverValidationError,
    )
    source_kind = _coerce_enum(
        observation.source_kind,
        SourceKind,
        LandCoverErrorCode.UNKNOWN_SOURCE_KIND,
        "source_kind",
        h3_index=observation.h3_index,
        error_type=LandCoverValidationError,
    )

    if observation.notes is not None and not isinstance(
        observation.notes, str
    ):
        raise LandCoverValidationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "notes must be a string or null.",
            h3_index=observation.h3_index,
            path="notes",
        )

    coverage_warnings = _validate_coverage(
        observation.coverage,
        config,
        h3_index=observation.h3_index,
    )
    _validate_provenance(
        observation.provenance,
        h3_index=observation.h3_index,
    )

    if land_cover_class == LandCoverClass.UNKNOWN:
        if verification_status is None:
            verification_status = VerificationStatus.NOT_ASSESSED
        elif verification_status != VerificationStatus.NOT_ASSESSED:
            raise LandCoverValidationError(
                LandCoverErrorCode.INCONSISTENT_VERIFICATION_STATUS,
                "UNKNOWN land cover must use verification_status="
                "NOT_ASSESSED.",
                h3_index=observation.h3_index,
                path="verification_status",
            )
        if source_kind is None:
            source_kind = SourceKind.UNKNOWN_SOURCE
    else:
        if verification_status is None:
            verification_status = VerificationStatus.UNVERIFIED
        if source_kind is None or source_kind == SourceKind.UNKNOWN_SOURCE:
            raise LandCoverValidationError(
                LandCoverErrorCode.MISSING_SOURCE,
                "A non-UNKNOWN land-cover class requires a known source_kind.",
                h3_index=observation.h3_index,
                path="source_kind",
            )
        if (
            observation.provenance is None
            or observation.provenance.source is None
        ):
            raise LandCoverValidationError(
                LandCoverErrorCode.MISSING_SOURCE,
                "A non-UNKNOWN land-cover class requires provenance.source.",
                h3_index=observation.h3_index,
                path="provenance.source",
            )

    if source_kind == SourceKind.SYNTHETIC_MOCK and verification_status in {
        VerificationStatus.FIELD_VERIFIED,
        VerificationStatus.REFERENCE_VALIDATED,
        VerificationStatus.SOURCE_ASSERTED,
    }:
        raise LandCoverValidationError(
            LandCoverErrorCode.SYNTHETIC_CANNOT_BE_VERIFIED,
            "SYNTHETIC_MOCK records may only use NOT_ASSESSED or UNVERIFIED.",
            h3_index=observation.h3_index,
            path="verification_status",
        )

    _validate_verification_completeness(
        verification_status,
        observation.provenance,
        h3_index=observation.h3_index,
    )

    notes = observation.notes
    if (
        land_cover_class == LandCoverClass.UNKNOWN
        and notes is None
        and source_kind == SourceKind.UNKNOWN_SOURCE
        and observation.coverage is None
        and observation.provenance is None
    ):
        notes = "No land-cover information supplied."

    return _NormalizedObservation(
        h3_index=observation.h3_index,
        land_cover_class=land_cover_class,
        verification_status=verification_status,
        source_kind=source_kind,
        is_synthetic=_derive_is_synthetic(source_kind),
        coverage=observation.coverage,
        provenance=observation.provenance,
        notes=notes,
        warnings=coverage_warnings,
    )


def validate_land_cover_observation(
    observation: LandCoverObservation,
    *,
    config: LandCoverConfig | None = None,
) -> tuple[str, ...]:
    """Validate one observation and return derived warnings.

    Raises:
        LandCoverValidationError: For invalid H3, enums, coverage, provenance,
            source, verification, or synthetic/verification conflicts.
        UnsupportedPolicyError: For unapproved coverage/conflict policies.
    """

    active_config = _normalize_config(config)
    return _normalize_observation(observation, active_config).warnings


def process_land_cover_observations(
    observations: Iterable[LandCoverObservation],
    *,
    config: LandCoverConfig | None = None,
) -> LandCoverLayer:
    """Validate observations and build a deterministic H3-keyed layer.

    Duplicate H3 indexes are rejected. Same-class duplicates raise
    ``DUPLICATE_H3_INDEX``; different classes raise
    ``CONFLICTING_LAND_COVER``. No conflict-resolution policy is applied.
    """

    active_config = _normalize_config(config)
    if observations is None or isinstance(
        observations, (str, bytes, bytearray)
    ):
        raise LandCoverInputError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "observations must be an iterable of LandCoverObservation.",
            path="observations",
        )
    if isinstance(observations, LandCoverObservation):
        iterator: Iterable[LandCoverObservation] = [observations]
    else:
        iterator = observations

    records_by_h3: dict[str, LandCoverRecord] = {}
    for observation in iterator:
        normalized = _normalize_observation(observation, active_config)
        existing = records_by_h3.get(normalized.h3_index)
        if existing is not None:
            if existing.land_cover_class == normalized.land_cover_class:
                raise LandCoverValidationError(
                    LandCoverErrorCode.DUPLICATE_H3_INDEX,
                    "Duplicate H3 index with the same land-cover class.",
                    h3_index=normalized.h3_index,
                    path="h3_index",
                )
            raise LandCoverValidationError(
                LandCoverErrorCode.CONFLICTING_LAND_COVER,
                "Conflicting land-cover classes for the same H3 index.",
                h3_index=normalized.h3_index,
                path="land_cover_class",
            )

        records_by_h3[normalized.h3_index] = LandCoverRecord(
            h3_index=normalized.h3_index,
            land_cover_class=normalized.land_cover_class,
            verification_status=normalized.verification_status,
            source_kind=normalized.source_kind,
            is_synthetic=normalized.is_synthetic,
            coverage=normalized.coverage,
            provenance=normalized.provenance,
            notes=normalized.notes,
            warnings=normalized.warnings,
        )

    records = {
        h3_index: records_by_h3[h3_index]
        for h3_index in sorted(records_by_h3)
    }
    warnings = tuple(
        f"{h3_index}: {warning}"
        for h3_index in sorted(records)
        for warning in records[h3_index].warnings
    )
    return LandCoverLayer(
        records=records,
        warnings=warnings,
        schema_version=SIDECAR_SCHEMA_VERSION,
        status="PROVISIONAL",
        module=MODULE_NAME,
        module_version=MODULE_VERSION,
    )


def _coverage_to_dict(
    coverage: CoverageFractions | None,
) -> dict[str, Any] | None:
    if coverage is None:
        return None
    return {
        "paddy_fraction": coverage.paddy_fraction,
        "non_paddy_fraction": coverage.non_paddy_fraction,
        "other_fraction": coverage.other_fraction,
        "method": coverage.method,
        "valid_pixel_count": coverage.valid_pixel_count,
        "total_pixel_count": coverage.total_pixel_count,
    }


def _provenance_to_dict(
    provenance: Provenance | None,
) -> dict[str, Any] | None:
    if provenance is None:
        return None
    return {
        field_name: value
        for field_name in _PROVENANCE_FIELDS
        if (value := getattr(provenance, field_name)) is not None
    }


def _record_to_dict(record: LandCoverRecord) -> dict[str, Any]:
    return {
        "h3_index": record.h3_index,
        "land_cover_class": record.land_cover_class.value,
        "verification_status": record.verification_status.value,
        "source_kind": record.source_kind.value,
        "is_synthetic": record.is_synthetic,
        "coverage": _coverage_to_dict(record.coverage),
        "provenance": _provenance_to_dict(record.provenance),
        "notes": record.notes,
    }


def _normalize_layer_for_output(
    layer: LandCoverLayer,
) -> dict[str, LandCoverRecord]:
    """Validate and normalize a layer before serialization or enrichment.

    The function revalidates every record, not just the layer's initial build.
    This protects against manually constructed layers and layers mutated after
    ``process_land_cover_observations()``.
    """

    if not isinstance(layer, LandCoverLayer):
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "layer must be a LandCoverLayer.",
            path="layer",
        )
    if layer.schema_version != SIDECAR_SCHEMA_VERSION:
        raise LandCoverSerializationError(
            LandCoverErrorCode.UNSUPPORTED_SCHEMA_VERSION,
            f"Unsupported schema_version: {layer.schema_version!r}. Expected "
            f"{SIDECAR_SCHEMA_VERSION!r}.",
            path="schema_version",
        )
    if layer.status != "PROVISIONAL":
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "Layer status must be 'PROVISIONAL' for v0.1.",
            path="status",
        )
    if layer.module != MODULE_NAME:
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            f"Layer module must be {MODULE_NAME!r}.",
            path="module",
        )
    if layer.module_version != MODULE_VERSION:
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            f"Layer module_version must be {MODULE_VERSION!r}.",
            path="module_version",
        )
    if not isinstance(layer.records, Mapping):
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "Layer records must be a mapping keyed by H3 index.",
            path="records",
        )
    if not isinstance(layer.warnings, tuple) or not all(
        isinstance(warning, str) for warning in layer.warnings
    ):
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "Layer warnings must be a tuple of strings.",
            path="warnings",
        )
    if not all(isinstance(h3_index, str) for h3_index in layer.records):
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "Layer record keys must be H3 index strings.",
            path="records",
        )

    config = _output_validation_config()
    normalized_records: dict[str, LandCoverRecord] = {}

    for h3_index in sorted(layer.records):
        record = layer.records[h3_index]
        if not isinstance(record, LandCoverRecord):
            raise LandCoverSerializationError(
                LandCoverErrorCode.INVALID_PAYLOAD,
                "Layer records must be LandCoverRecord objects.",
                h3_index=h3_index,
                path=f"records.{h3_index}",
            )
        if record.h3_index != h3_index:
            raise LandCoverSerializationError(
                LandCoverErrorCode.INVALID_PAYLOAD,
                "Record key does not match record.h3_index.",
                h3_index=h3_index,
                path=f"records.{h3_index}.h3_index",
            )
        if (
            not isinstance(record.land_cover_class, LandCoverClass)
            or not isinstance(record.verification_status, VerificationStatus)
            or not isinstance(record.source_kind, SourceKind)
        ):
            raise LandCoverSerializationError(
                LandCoverErrorCode.INVALID_PAYLOAD,
                "Record enums must use the domain enum types.",
                h3_index=h3_index,
                path=f"records.{h3_index}",
            )
        if record.is_synthetic is not None and not isinstance(
            record.is_synthetic, bool
        ):
            raise LandCoverSerializationError(
                LandCoverErrorCode.INVALID_PAYLOAD,
                "is_synthetic must be a boolean or null.",
                h3_index=h3_index,
                path=f"records.{h3_index}.is_synthetic",
            )
        if not isinstance(record.warnings, tuple) or not all(
            isinstance(warning, str) for warning in record.warnings
        ):
            raise LandCoverSerializationError(
                LandCoverErrorCode.INVALID_PAYLOAD,
                "Record warnings must be a tuple of strings.",
                h3_index=h3_index,
                path=f"records.{h3_index}.warnings",
            )

        observation = LandCoverObservation(
            h3_index=record.h3_index,
            land_cover_class=record.land_cover_class,
            verification_status=record.verification_status,
            source_kind=record.source_kind,
            coverage=record.coverage,
            provenance=record.provenance,
            notes=record.notes,
        )
        try:
            normalized = _normalize_observation(observation, config)
        except LandCoverValidationError as exc:
            raise LandCoverSerializationError(
                exc.code,
                exc.message,
                h3_index=exc.h3_index,
                path=exc.path,
            ) from exc

        if normalized.is_synthetic != record.is_synthetic:
            raise LandCoverSerializationError(
                LandCoverErrorCode.INCONSISTENT_SYNTHETIC_FLAG,
                "is_synthetic does not match source_kind.",
                h3_index=h3_index,
                path=f"records.{h3_index}.is_synthetic",
            )

        normalized_records[h3_index] = LandCoverRecord(
            h3_index=normalized.h3_index,
            land_cover_class=normalized.land_cover_class,
            verification_status=normalized.verification_status,
            source_kind=normalized.source_kind,
            is_synthetic=normalized.is_synthetic,
            coverage=normalized.coverage,
            provenance=normalized.provenance,
            notes=normalized.notes,
            warnings=normalized.warnings,
        )

    return normalized_records


def serialize_land_cover_layer(layer: LandCoverLayer) -> dict[str, Any]:
    """Serialize a layer into the provisional sidecar dictionary.

    Every record is revalidated and normalized before serialization. Records are
    sorted by H3. Warnings are derived from the normalized records so the
    serialized top-level warning list cannot silently go stale.
    """

    normalized_records = _normalize_layer_for_output(layer)

    records: dict[str, Any] = {}
    derived_warnings: list[str] = []
    for h3_index in sorted(normalized_records):
        record = normalized_records[h3_index]
        records[h3_index] = _record_to_dict(record)
        derived_warnings.extend(
            f"{h3_index}: {warning}" for warning in record.warnings
        )

    return {
        "schema_version": layer.schema_version,
        "status": layer.status,
        "module": layer.module,
        "module_version": layer.module_version,
        "records": records,
        "warnings": derived_warnings,
    }


def _deserialize_record(
    h3_index: str,
    value: Any,
) -> LandCoverRecord:
    if not isinstance(value, Mapping):
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "Each sidecar record must be an object.",
            h3_index=h3_index,
            path=f"records.{h3_index}",
        )

    unknown_fields = set(value) - _SIDECAR_RECORD_FIELDS
    if unknown_fields:
        names = ", ".join(sorted(str(field) for field in unknown_fields))
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            f"Unknown sidecar record field(s): {names}.",
            h3_index=h3_index,
            path=f"records.{h3_index}",
        )

    if "h3_index" not in value:
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "Sidecar record must include h3_index.",
            h3_index=h3_index,
            path=f"records.{h3_index}.h3_index",
        )
    if value.get("h3_index") != h3_index:
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "Sidecar record h3_index does not match its mapping key.",
            h3_index=h3_index,
            path=f"records.{h3_index}.h3_index",
        )
    if "is_synthetic" not in value:
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "Sidecar record must include is_synthetic (boolean or null).",
            h3_index=h3_index,
            path=f"records.{h3_index}.is_synthetic",
        )

    stored_synthetic = value.get("is_synthetic")
    if stored_synthetic is not None and not isinstance(stored_synthetic, bool):
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "is_synthetic must be a boolean or null.",
            h3_index=h3_index,
            path=f"records.{h3_index}.is_synthetic",
        )

    observation_payload = {
        field_name: field_value
        for field_name, field_value in value.items()
        if field_name != "is_synthetic"
    }
    try:
        observation = _parse_observation_mapping(
            observation_payload,
            key_h3=h3_index,
            error_type=LandCoverSerializationError,
        )
        normalized = _normalize_observation(
            observation,
            _output_validation_config(),
        )
    except LandCoverValidationError as exc:
        raise LandCoverSerializationError(
            exc.code,
            exc.message,
            h3_index=exc.h3_index,
            path=exc.path,
        ) from exc

    if stored_synthetic != normalized.is_synthetic:
        raise LandCoverSerializationError(
            LandCoverErrorCode.INCONSISTENT_SYNTHETIC_FLAG,
            "is_synthetic does not match the value derived from source_kind.",
            h3_index=h3_index,
            path=f"records.{h3_index}.is_synthetic",
        )

    return LandCoverRecord(
        h3_index=normalized.h3_index,
        land_cover_class=normalized.land_cover_class,
        verification_status=normalized.verification_status,
        source_kind=normalized.source_kind,
        is_synthetic=normalized.is_synthetic,
        coverage=normalized.coverage,
        provenance=normalized.provenance,
        notes=normalized.notes,
        warnings=normalized.warnings,
    )


def deserialize_land_cover_layer(
    payload: Mapping[str, Any] | str,
) -> LandCoverLayer:
    """Deserialize and validate a provisional sidecar.

    Duplicate JSON keys are detected with an object-pairs hook. The schema
    version must equal ``land_cover.sidecar.v0.1``.
    """

    if isinstance(payload, str):
        data = _loads_json_strict(
            payload,
            error_type=LandCoverSerializationError,
        )
    elif isinstance(payload, Mapping):
        data = payload
    else:
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "Sidecar payload must be an object or JSON string.",
            path="payload",
        )

    if not isinstance(data, Mapping):
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "Sidecar payload must be a JSON object.",
            path="payload",
        )

    unknown_top_fields = set(data) - _SIDECAR_TOP_FIELDS
    if unknown_top_fields:
        names = ", ".join(sorted(str(field) for field in unknown_top_fields))
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            f"Unknown sidecar field(s): {names}.",
            path="payload",
        )

    schema_version = data.get("schema_version")
    if schema_version != SIDECAR_SCHEMA_VERSION:
        raise LandCoverSerializationError(
            LandCoverErrorCode.UNSUPPORTED_SCHEMA_VERSION,
            f"Unsupported schema_version: {schema_version!r}. Expected "
            f"{SIDECAR_SCHEMA_VERSION!r}.",
            path="schema_version",
        )

    status = data.get("status", "PROVISIONAL")
    if status != "PROVISIONAL":
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "Sidecar status must be 'PROVISIONAL' for v0.1.",
            path="status",
        )

    module = data.get("module", MODULE_NAME)
    if module != MODULE_NAME:
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            f"Sidecar module must be {MODULE_NAME!r}.",
            path="module",
        )

    module_version = data.get("module_version", MODULE_VERSION)
    if module_version != MODULE_VERSION:
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            f"Sidecar module_version must be {MODULE_VERSION!r}.",
            path="module_version",
        )

    records_payload = data.get("records")
    if not isinstance(records_payload, Mapping):
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "records must be an object keyed by H3 index.",
            path="records",
        )

    records: dict[str, LandCoverRecord] = {}
    for h3_index, record_payload in records_payload.items():
        if not isinstance(h3_index, str) or not h3.is_valid_cell(h3_index):
            raise LandCoverSerializationError(
                LandCoverErrorCode.INVALID_H3_INDEX,
                f"Invalid H3 record key: {h3_index!r}.",
                h3_index=str(h3_index),
                path=f"records.{h3_index}",
            )
        records[h3_index] = _deserialize_record(h3_index, record_payload)

    stored_warnings = data.get("warnings", [])
    if not isinstance(stored_warnings, list) or not all(
        isinstance(item, str) for item in stored_warnings
    ):
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "warnings must be a list of strings.",
            path="warnings",
        )

    sorted_records = {
        h3_index: records[h3_index] for h3_index in sorted(records)
    }
    derived_warnings = tuple(
        f"{h3_index}: {warning}"
        for h3_index in sorted(sorted_records)
        for warning in sorted_records[h3_index].warnings
    )
    return LandCoverLayer(
        records=sorted_records,
        warnings=derived_warnings,
        schema_version=schema_version,
        status=status,
        module=module,
        module_version=module_version,
    )


def _is_unsafe_output_path(path: Path) -> bool:
    """Return True unless path is a .json file under ALLOWED_OUTPUT_ROOT."""

    if path.suffix.lower() != ".json":
        return True
    try:
        relative = path.relative_to(ALLOWED_OUTPUT_ROOT)
    except ValueError:
        return True
    return relative == Path(".")


def write_land_cover_sidecar(
    layer: LandCoverLayer,
    output_path: str | Path,
) -> int:
    """Write a sidecar JSON file and return its UTF-8 byte size.

    Output is restricted to ``data/land_cover/*.json``. Paths outside that
    directory, non-JSON files, and symlink escapes are refused. The serialized
    payload is round-tripped through the deserializer before any file is
    written.
    """

    path = Path(output_path).expanduser().resolve()
    if _is_unsafe_output_path(path):
        raise LandCoverSerializationError(
            LandCoverErrorCode.UNSAFE_OUTPUT_PATH,
            "Land-cover sidecar output must be a .json file under "
            f"{ALLOWED_OUTPUT_ROOT}: {path}.",
            path="output_path",
        )
    if not path.name:
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "output_path must include a file name.",
            path="output_path",
        )
    if path.exists() and path.is_dir():
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            f"output_path is a directory: {path}.",
            path="output_path",
        )

    payload = serialize_land_cover_layer(layer)
    try:
        deserialize_land_cover_layer(payload)
    except LandCoverSerializationError as exc:
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "Serialized land-cover payload failed round-trip validation: "
            f"{exc.code}: {exc.message}",
            path="payload",
        ) from exc

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        path.write_text(text, encoding="utf-8")
    except (OSError, TypeError, ValueError) as exc:
        raise LandCoverSerializationError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            f"Cannot write land-cover sidecar to '{path}': {exc}",
            path="output_path",
        ) from exc

    try:
        return path.stat().st_size
    except OSError as exc:
        raise LandCoverSerializationError(
            LandCoverErrorCode.SIDECAR_READ_ERROR,
            f"Sidecar was written but its size could not be read: {path}: "
            f"{exc}",
            path="output_path",
        ) from exc


def read_land_cover_sidecar(
    input_path: str | Path,
) -> LandCoverLayer:
    """Read and validate a land-cover sidecar JSON file."""

    path = Path(input_path).expanduser().resolve()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise LandCoverSerializationError(
            LandCoverErrorCode.SIDECAR_READ_ERROR,
            f"Cannot read land-cover sidecar at '{path}': {exc}",
            path="input_path",
        ) from exc
    return deserialize_land_cover_layer(text)


def _default_unknown_record(h3_index: str) -> LandCoverRecord:
    return LandCoverRecord(
        h3_index=h3_index,
        land_cover_class=LandCoverClass.UNKNOWN,
        verification_status=VerificationStatus.NOT_ASSESSED,
        source_kind=SourceKind.UNKNOWN_SOURCE,
        is_synthetic=None,
        coverage=None,
        provenance=None,
        notes="No land-cover record supplied.",
        warnings=(),
    )


def enrich_geojson_with_land_cover(
    feature_collection: Mapping[str, Any],
    layer: LandCoverLayer,
    *,
    include_missing_as_unknown: bool = True,
) -> dict[str, Any]:
    """Return a copy of a GeoJSON FeatureCollection with land-cover properties.

    The layer is revalidated before enrichment. The input is not mutated. Only
    ``properties.land_cover_record`` is added; ``properties.contract`` is never
    modified.
    """

    if not isinstance(feature_collection, Mapping):
        raise LandCoverInputError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "feature_collection must be a GeoJSON FeatureCollection object.",
            path="feature_collection",
        )
    if feature_collection.get("type") != "FeatureCollection":
        raise LandCoverInputError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "feature_collection type must be 'FeatureCollection'.",
            path="feature_collection.type",
        )
    features = feature_collection.get("features")
    if not isinstance(features, list):
        raise LandCoverInputError(
            LandCoverErrorCode.INVALID_PAYLOAD,
            "feature_collection.features must be a list.",
            path="feature_collection.features",
        )

    normalized_records = _normalize_layer_for_output(layer)
    enriched = copy.deepcopy(feature_collection)
    enriched_features = enriched["features"]
    for index, feature in enumerate(enriched_features):
        if not isinstance(feature, Mapping):
            raise LandCoverInputError(
                LandCoverErrorCode.INVALID_PAYLOAD,
                "Each GeoJSON feature must be an object.",
                path=f"features[{index}]",
            )
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            raise LandCoverInputError(
                LandCoverErrorCode.INVALID_PAYLOAD,
                "Each GeoJSON feature must have a properties object.",
                path=f"features[{index}].properties",
            )
        h3_index = properties.get("h3_index")
        if not isinstance(h3_index, str) or not h3.is_valid_cell(h3_index):
            raise LandCoverInputError(
                LandCoverErrorCode.INVALID_H3_INDEX,
                "GeoJSON feature must have a valid properties.h3_index.",
                h3_index=h3_index if isinstance(h3_index, str) else None,
                path=f"features[{index}].properties.h3_index",
            )

        record = normalized_records.get(h3_index)
        if record is None:
            if not include_missing_as_unknown:
                continue
            record = _default_unknown_record(h3_index)
        properties["land_cover_record"] = _record_to_dict(record)

    return enriched


__all__ = [
    "ALLOWED_OUTPUT_ROOT",
    "LandCoverError",
    "LandCoverErrorCode",
    "LandCoverInputError",
    "LandCoverSerializationError",
    "LandCoverValidationError",
    "LandCoverWarning",
    "UnsupportedPolicyError",
    "deserialize_land_cover_layer",
    "enrich_geojson_with_land_cover",
    "parse_land_cover_payload",
    "process_land_cover_observations",
    "read_land_cover_sidecar",
    "serialize_land_cover_layer",
    "validate_land_cover_observation",
    "write_land_cover_sidecar",
]
