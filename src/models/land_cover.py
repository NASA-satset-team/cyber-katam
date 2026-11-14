"""Domain models for H3 land-cover records.

The module defines data structures only. It does not classify satellite imagery
and does not infer paddy fields from NDVI, BSI, LST, or any other indicator.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final, Mapping

SIDECAR_SCHEMA_VERSION = "land_cover.sidecar.v0.1"
MODULE_NAME = "land_cover_classifier"
MODULE_VERSION = "0.1.0"
MAX_COVERAGE_TOLERANCE: Final[float] = 0.001


class LandCoverClass(str, Enum):
    """Land-cover class supplied by an external source."""

    PADDY_FIELD = "PADDY_FIELD"
    NON_PADDY = "NON_PADDY"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class VerificationStatus(str, Enum):
    """How far a land-cover claim has been verified.

    ``SOURCE_ASSERTED`` means the data producer asserts the class; it does not
    mean CYBER-KATAM performed field or independent verification.
    """

    FIELD_VERIFIED = "FIELD_VERIFIED"
    REFERENCE_VALIDATED = "REFERENCE_VALIDATED"
    SOURCE_ASSERTED = "SOURCE_ASSERTED"
    UNVERIFIED = "UNVERIFIED"
    NOT_ASSESSED = "NOT_ASSESSED"


class SourceKind(str, Enum):
    """Origin of a land-cover claim."""

    OFFICIAL_DATASET = "OFFICIAL_DATASET"
    DERIVED_CLASSIFICATION = "DERIVED_CLASSIFICATION"
    FIELD_OBSERVATION = "FIELD_OBSERVATION"
    SYNTHETIC_MOCK = "SYNTHETIC_MOCK"
    UNKNOWN_SOURCE = "UNKNOWN_SOURCE"


@dataclass(frozen=True, slots=True)
class CoverageFractions:
    """Optional source-provided coverage fractions.

    Fractions are in ``[0.0, 1.0]``. ``None`` means unavailable, while ``0.0``
    is a real zero. ``method`` is the only place where the coverage method is
    stored.
    """

    paddy_fraction: float | None = None
    non_paddy_fraction: float | None = None
    other_fraction: float | None = None
    method: str | None = None
    valid_pixel_count: int | None = None
    total_pixel_count: int | None = None


@dataclass(frozen=True, slots=True)
class Provenance:
    """Metadata supplied by the land-cover source.

    Unavailable fields remain ``None``. The module never invents dates, dataset
    identifiers, licenses, or resolution values.
    """

    source: str | None = None
    dataset_id: str | None = None
    product_version: str | None = None
    observation_date: str | None = None
    processing_date: str | None = None
    spatial_resolution_m: float | None = None
    classification_method: str | None = None
    verification_method: str | None = None
    verification_date: str | None = None
    verification_reference: str | None = None
    reference_dataset: str | None = None
    license: str | None = None
    attribution: str | None = None


@dataclass(frozen=True, slots=True)
class LandCoverObservation:
    """Input record for one H3 cell.

    ``is_synthetic`` is intentionally absent: it is derived from ``source_kind``.
    """

    h3_index: str
    land_cover_class: LandCoverClass | None = None
    verification_status: VerificationStatus | None = None
    source_kind: SourceKind | None = None
    coverage: CoverageFractions | None = None
    provenance: Provenance | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class LandCoverRecord:
    """Validated output record for one H3 cell."""

    h3_index: str
    land_cover_class: LandCoverClass
    verification_status: VerificationStatus
    source_kind: SourceKind
    is_synthetic: bool | None
    coverage: CoverageFractions | None
    provenance: Provenance | None
    notes: str | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LandCoverLayer:
    """A collection of land-cover records keyed by H3 index."""

    records: Mapping[str, LandCoverRecord]
    warnings: tuple[str, ...] = ()
    schema_version: str = SIDECAR_SCHEMA_VERSION
    status: str = "PROVISIONAL"
    module: str = MODULE_NAME
    module_version: str = MODULE_VERSION


@dataclass(frozen=True, slots=True)
class LandCoverConfig:
    """Validation and processing configuration.

    ``coverage_tolerance`` is limited to ``[0.0, MAX_COVERAGE_TOLERANCE]`` so
    the coverage invariant cannot be loosened arbitrarily.
    ``derive_class_from_coverage`` must remain ``False`` in v0.1. Coverage is
    descriptive only until classification thresholds are approved by the team.
    """

    expected_resolution: int | None = 9
    coverage_tolerance: float = 1e-6
    derive_class_from_coverage: bool = False
    conflict_policy: str = "ERROR"


__all__ = [
    "CoverageFractions",
    "LandCoverClass",
    "LandCoverConfig",
    "LandCoverLayer",
    "LandCoverObservation",
    "LandCoverRecord",
    "MAX_COVERAGE_TOLERANCE",
    "MODULE_NAME",
    "MODULE_VERSION",
    "Provenance",
    "SIDECAR_SCHEMA_VERSION",
    "SourceKind",
    "VerificationStatus",
]
