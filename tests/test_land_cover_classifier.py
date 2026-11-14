"""Unit tests for the H3 land-cover record module.

All data are in-memory mock fixtures. No Task 2 generated file, NASA dataset, or
Google Earth Engine call is required.
"""

from __future__ import annotations

import copy
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

import h3
import pytest

import src.engines.land_cover_classifier as land_cover_module
from src.engines.land_cover_classifier import (
    ALLOWED_OUTPUT_ROOT,
    CONTRACT_SCHEMA_PATH,
    EXTERNAL_ROOT,
    ROI_PATH,
    TASK2_GEOJSON_PATH,
    LandCoverErrorCode,
    LandCoverInputError,
    LandCoverSerializationError,
    LandCoverValidationError,
    LandCoverWarning,
    UnsupportedPolicyError,
    deserialize_land_cover_layer,
    enrich_geojson_with_land_cover,
    parse_land_cover_payload,
    process_land_cover_observations,
    read_land_cover_sidecar,
    serialize_land_cover_layer,
    validate_land_cover_observation,
    write_land_cover_sidecar,
)
from src.models.land_cover import (
    MAX_COVERAGE_TOLERANCE,
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

H3_A = h3.latlng_to_cell(-7.45, 109.17, 9)
H3_B = h3.latlng_to_cell(-7.46, 109.18, 9)
H3_C = h3.latlng_to_cell(-7.44, 109.16, 9)
H3_RES8 = h3.latlng_to_cell(-7.45, 109.17, 8)
INVALID_H3 = "000000000000000"


def _unknown(h3_index: str = H3_A) -> LandCoverObservation:
    return LandCoverObservation(h3_index=h3_index)


def _official_paddy(
    h3_index: str = H3_A,
    *,
    coverage: CoverageFractions | None = None,
) -> LandCoverObservation:
    return LandCoverObservation(
        h3_index=h3_index,
        land_cover_class=LandCoverClass.PADDY_FIELD,
        verification_status=VerificationStatus.SOURCE_ASSERTED,
        source_kind=SourceKind.OFFICIAL_DATASET,
        coverage=coverage,
        provenance=Provenance(
            source="Mock official land-cover dataset",
            dataset_id="MOCK-LC-001",
        ),
    )


def _derived_non_paddy(h3_index: str = H3_A) -> LandCoverObservation:
    return LandCoverObservation(
        h3_index=h3_index,
        land_cover_class=LandCoverClass.NON_PADDY,
        verification_status=VerificationStatus.UNVERIFIED,
        source_kind=SourceKind.DERIVED_CLASSIFICATION,
        provenance=Provenance(
            source="Mock derived classification",
            classification_method="mock classifier",
        ),
    )


def _mixed(h3_index: str = H3_A) -> LandCoverObservation:
    return LandCoverObservation(
        h3_index=h3_index,
        land_cover_class=LandCoverClass.MIXED,
        verification_status=VerificationStatus.SOURCE_ASSERTED,
        source_kind=SourceKind.OFFICIAL_DATASET,
        coverage=CoverageFractions(
            paddy_fraction=0.5,
            non_paddy_fraction=0.5,
            method="SOURCE_PROVIDED",
        ),
        provenance=Provenance(source="Mock mixed land-cover dataset"),
    )


def _field_verified(h3_index: str = H3_A) -> LandCoverObservation:
    return LandCoverObservation(
        h3_index=h3_index,
        land_cover_class=LandCoverClass.PADDY_FIELD,
        verification_status=VerificationStatus.FIELD_VERIFIED,
        source_kind=SourceKind.FIELD_OBSERVATION,
        provenance=Provenance(
            source="Mock field survey",
            verification_method="field survey",
            verification_date="2026-01-15",
            verification_reference="SURVEY-001",
        ),
    )


def _reference_validated(h3_index: str = H3_A) -> LandCoverObservation:
    return LandCoverObservation(
        h3_index=h3_index,
        land_cover_class=LandCoverClass.PADDY_FIELD,
        verification_status=VerificationStatus.REFERENCE_VALIDATED,
        source_kind=SourceKind.DERIVED_CLASSIFICATION,
        provenance=Provenance(
            source="Mock derived classification",
            reference_dataset="REF-LC-001",
            verification_method="reference comparison",
            verification_date="2026-01-16",
        ),
    )


def _synthetic(
    h3_index: str = H3_A,
    *,
    land_cover_class: LandCoverClass = LandCoverClass.PADDY_FIELD,
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED,
) -> LandCoverObservation:
    return LandCoverObservation(
        h3_index=h3_index,
        land_cover_class=land_cover_class,
        verification_status=verification_status,
        source_kind=SourceKind.SYNTHETIC_MOCK,
        provenance=Provenance(source="Mock synthetic fixture"),
    )


def _valid_record(h3_index: str = H3_A) -> LandCoverRecord:
    return process_land_cover_observations(
        [_official_paddy(h3_index)]
    ).records[h3_index]


@pytest.fixture
def allowed_output_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    root = (tmp_path / "land_cover").resolve()
    monkeypatch.setattr(land_cover_module, "ALLOWED_OUTPUT_ROOT", root)
    return root


def _error_code(exc_info: pytest.ExceptionInfo[Any]) -> str:
    return exc_info.value.code


def _collect_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for child in value.values():
            keys |= _collect_keys(child)
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for child in value:
            keys |= _collect_keys(child)
        return keys
    return set()


# ---------------------------------------------------------------------------
# Domain enums and defaults
# ---------------------------------------------------------------------------


def test_enum_values_are_exact() -> None:
    assert [item.value for item in LandCoverClass] == [
        "PADDY_FIELD",
        "NON_PADDY",
        "MIXED",
        "UNKNOWN",
    ]
    assert [item.value for item in VerificationStatus] == [
        "FIELD_VERIFIED",
        "REFERENCE_VALIDATED",
        "SOURCE_ASSERTED",
        "UNVERIFIED",
        "NOT_ASSESSED",
    ]
    assert [item.value for item in SourceKind] == [
        "OFFICIAL_DATASET",
        "DERIVED_CLASSIFICATION",
        "FIELD_OBSERVATION",
        "SYNTHETIC_MOCK",
        "UNKNOWN_SOURCE",
    ]


def test_missing_information_defaults_to_unknown() -> None:
    layer = process_land_cover_observations([_unknown()])
    record = layer.records[H3_A]

    assert record.land_cover_class is LandCoverClass.UNKNOWN
    assert record.verification_status is VerificationStatus.NOT_ASSESSED
    assert record.source_kind is SourceKind.UNKNOWN_SOURCE
    assert record.is_synthetic is None
    assert record.coverage is None
    assert record.provenance is None
    assert record.notes == "No land-cover information supplied."


@pytest.mark.parametrize(
    ("observation", "expected_class"),
    [
        pytest.param(_official_paddy(), LandCoverClass.PADDY_FIELD, id="paddy"),
        pytest.param(_derived_non_paddy(), LandCoverClass.NON_PADDY, id="non-paddy"),
        pytest.param(_mixed(), LandCoverClass.MIXED, id="mixed"),
    ],
)
def test_source_provided_classes_are_accepted(
    observation: LandCoverObservation,
    expected_class: LandCoverClass,
) -> None:
    layer = process_land_cover_observations([observation])

    assert layer.records[observation.h3_index].land_cover_class is expected_class


# ---------------------------------------------------------------------------
# H3 validation
# ---------------------------------------------------------------------------


def test_invalid_h3_is_rejected() -> None:
    with pytest.raises(LandCoverValidationError) as exc_info:
        validate_land_cover_observation(_unknown(INVALID_H3))

    assert _error_code(exc_info) == LandCoverErrorCode.INVALID_H3_INDEX


def test_wrong_h3_resolution_is_rejected() -> None:
    with pytest.raises(LandCoverValidationError) as exc_info:
        validate_land_cover_observation(_unknown(H3_RES8))

    assert _error_code(exc_info) == LandCoverErrorCode.UNSUPPORTED_H3_RESOLUTION


def test_expected_resolution_is_configurable() -> None:
    validate_land_cover_observation(
        _unknown(H3_RES8),
        config=LandCoverConfig(expected_resolution=8),
    )
    validate_land_cover_observation(
        _unknown(H3_RES8),
        config=LandCoverConfig(expected_resolution=None),
    )


def test_invalid_expected_resolution_config_is_rejected() -> None:
    with pytest.raises(LandCoverInputError) as exc_info:
        validate_land_cover_observation(
            _unknown(),
            config=LandCoverConfig(expected_resolution=16),
        )

    assert _error_code(exc_info) == LandCoverErrorCode.INVALID_PAYLOAD


# ---------------------------------------------------------------------------
# Duplicates and conflicts
# ---------------------------------------------------------------------------


def test_duplicate_h3_same_class_is_rejected() -> None:
    with pytest.raises(LandCoverValidationError) as exc_info:
        process_land_cover_observations([_official_paddy(), _official_paddy()])

    assert _error_code(exc_info) == LandCoverErrorCode.DUPLICATE_H3_INDEX


def test_conflicting_h3_classes_are_rejected() -> None:
    with pytest.raises(LandCoverValidationError) as exc_info:
        process_land_cover_observations(
            [_official_paddy(), _derived_non_paddy()]
        )

    assert _error_code(exc_info) == LandCoverErrorCode.CONFLICTING_LAND_COVER


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


def test_valid_coverage_is_accepted() -> None:
    observation = _official_paddy(
        coverage=CoverageFractions(
            paddy_fraction=0.6,
            non_paddy_fraction=0.3,
            other_fraction=0.1,
            method="PIXEL_AREA_FRACTION",
            valid_pixel_count=60,
            total_pixel_count=100,
        )
    )

    assert validate_land_cover_observation(observation) == ()
    record = process_land_cover_observations([observation]).records[H3_A]
    assert record.coverage is not None
    assert record.coverage.paddy_fraction == 0.6
    assert record.coverage.method == "PIXEL_AREA_FRACTION"


@pytest.mark.parametrize(
    "coverage",
    [
        pytest.param(CoverageFractions(paddy_fraction=-0.1), id="negative"),
        pytest.param(CoverageFractions(non_paddy_fraction=1.1), id="above-one"),
        pytest.param(
            CoverageFractions(
                paddy_fraction=0.7,
                non_paddy_fraction=0.4,
            ),
            id="sum-above-one",
        ),
        pytest.param(
            CoverageFractions(paddy_fraction="0.5"),  # type: ignore[arg-type]
            id="string",
        ),
        pytest.param(
            CoverageFractions(paddy_fraction=True),  # type: ignore[arg-type]
            id="boolean",
        ),
        pytest.param(
            CoverageFractions(valid_pixel_count=-1),
            id="negative-pixels",
        ),
        pytest.param(
            CoverageFractions(
                valid_pixel_count=10,
                total_pixel_count=5,
            ),
            id="valid-exceeds-total",
        ),
        pytest.param(CoverageFractions(method=""), id="empty-method"),
    ],
)
def test_invalid_coverage_is_rejected(
    coverage: CoverageFractions,
) -> None:
    observation = replace(_official_paddy(), coverage=coverage)

    with pytest.raises(LandCoverValidationError) as exc_info:
        validate_land_cover_observation(observation)

    assert _error_code(exc_info) == LandCoverErrorCode.INVALID_COVERAGE


def test_missing_coverage_stays_none_and_zero_is_preserved() -> None:
    missing_payload = serialize_land_cover_layer(
        process_land_cover_observations([_unknown()])
    )
    assert missing_payload["records"][H3_A]["coverage"] is None

    zero_observation = replace(
        _unknown(),
        coverage=CoverageFractions(
            paddy_fraction=0.0,
            method="SOURCE_PROVIDED",
        ),
    )
    zero_payload = serialize_land_cover_layer(
        process_land_cover_observations([zero_observation])
    )
    zero_coverage = zero_payload["records"][H3_A]["coverage"]
    assert zero_coverage is not None
    assert zero_coverage["paddy_fraction"] == 0.0
    assert zero_coverage["non_paddy_fraction"] is None


def test_coverage_without_method_emits_warning() -> None:
    observation = replace(
        _official_paddy(),
        coverage=CoverageFractions(paddy_fraction=0.5),
    )

    warnings = validate_land_cover_observation(observation)
    assert LandCoverWarning.COVERAGE_METHOD_UNKNOWN in warnings

    layer = process_land_cover_observations([observation])
    assert layer.records[H3_A].warnings == (
        LandCoverWarning.COVERAGE_METHOD_UNKNOWN,
    )
    payload = serialize_land_cover_layer(layer)
    assert payload["warnings"] == [
        f"{H3_A}: {LandCoverWarning.COVERAGE_METHOD_UNKNOWN}"
    ]


def test_coverage_does_not_change_land_cover_class() -> None:
    observation = replace(
        _unknown(),
        coverage=CoverageFractions(
            paddy_fraction=0.9,
            method="SOURCE_PROVIDED",
        ),
    )

    record = process_land_cover_observations([observation]).records[H3_A]

    assert record.land_cover_class is LandCoverClass.UNKNOWN
    assert record.coverage is not None


def test_coverage_method_lives_only_in_coverage() -> None:
    assert not hasattr(Provenance(), "coverage_method")

    with pytest.raises(LandCoverInputError) as exc_info:
        parse_land_cover_payload(
            {
                "h3_index": H3_A,
                "provenance": {"coverage_method": "PIXEL_AREA_FRACTION"},
            }
        )

    assert _error_code(exc_info) == LandCoverErrorCode.INVALID_PAYLOAD


# ---------------------------------------------------------------------------
# Provenance and verification
# ---------------------------------------------------------------------------


def test_non_unknown_class_requires_source_provenance() -> None:
    cases = [
        replace(_official_paddy(), provenance=None),
        replace(_official_paddy(), provenance=Provenance(source=None)),
        replace(_official_paddy(), source_kind=SourceKind.UNKNOWN_SOURCE),
    ]

    for observation in cases:
        with pytest.raises(LandCoverValidationError) as exc_info:
            validate_land_cover_observation(observation)
        assert _error_code(exc_info) == LandCoverErrorCode.MISSING_SOURCE


def test_field_verified_with_complete_evidence_is_accepted() -> None:
    record = process_land_cover_observations(
        [_field_verified()]
    ).records[H3_A]

    assert record.verification_status is VerificationStatus.FIELD_VERIFIED
    assert record.is_synthetic is False


def test_field_verified_without_evidence_is_rejected() -> None:
    observation = replace(
        _field_verified(),
        provenance=Provenance(source="Mock field survey"),
    )

    with pytest.raises(LandCoverValidationError) as exc_info:
        validate_land_cover_observation(observation)

    assert (
        _error_code(exc_info)
        == LandCoverErrorCode.INCOMPLETE_VERIFICATION_PROVENANCE
    )


def test_reference_validated_with_complete_evidence_is_accepted() -> None:
    record = process_land_cover_observations(
        [_reference_validated()]
    ).records[H3_A]

    assert (
        record.verification_status
        is VerificationStatus.REFERENCE_VALIDATED
    )


def test_reference_validated_without_reference_dataset_is_rejected() -> None:
    observation = replace(
        _reference_validated(),
        provenance=Provenance(
            source="Mock derived classification",
            verification_method="reference comparison",
            verification_date="2026-01-16",
        ),
    )

    with pytest.raises(LandCoverValidationError) as exc_info:
        validate_land_cover_observation(observation)

    assert (
        _error_code(exc_info)
        == LandCoverErrorCode.INCOMPLETE_VERIFICATION_PROVENANCE
    )


@pytest.mark.parametrize(
    "verification_status",
    [
        VerificationStatus.FIELD_VERIFIED,
        VerificationStatus.REFERENCE_VALIDATED,
        VerificationStatus.SOURCE_ASSERTED,
    ],
)
def test_synthetic_cannot_claim_verification(
    verification_status: VerificationStatus,
) -> None:
    observation = replace(
        _synthetic(),
        verification_status=verification_status,
        provenance=Provenance(
            source="Mock synthetic fixture",
            reference_dataset="REF-LC-001",
            verification_method="mock verification",
            verification_date="2026-01-15",
            verification_reference="SURVEY-001",
        ),
    )

    with pytest.raises(LandCoverValidationError) as exc_info:
        validate_land_cover_observation(observation)

    assert (
        _error_code(exc_info)
        == LandCoverErrorCode.SYNTHETIC_CANNOT_BE_VERIFIED
    )


def test_synthetic_unverified_is_accepted() -> None:
    record = process_land_cover_observations([_synthetic()]).records[H3_A]

    assert record.is_synthetic is True
    assert record.source_kind is SourceKind.SYNTHETIC_MOCK
    assert record.verification_status is VerificationStatus.UNVERIFIED


def test_mock_mislabeled_as_official_is_trusted_as_caller_assertion() -> None:
    """Document the trust boundary: source_kind is caller-asserted.

    The module cannot prove that a caller who labels mock data as
    OFFICIAL_DATASET and FIELD_VERIFIED is telling the truth. This test records
    the current behaviour so the limitation is explicit; it does not claim
    provenance detection that the module does not have.
    """

    observation = replace(
        _field_verified(),
        source_kind=SourceKind.OFFICIAL_DATASET,
    )

    record = process_land_cover_observations([observation]).records[H3_A]

    assert record.source_kind is SourceKind.OFFICIAL_DATASET
    assert record.verification_status is VerificationStatus.FIELD_VERIFIED
    assert record.is_synthetic is False


@pytest.mark.parametrize(
    ("observation", "expected"),
    [
        pytest.param(_unknown(), None, id="unknown-source"),
        pytest.param(_synthetic(), True, id="synthetic"),
        pytest.param(_official_paddy(), False, id="official"),
        pytest.param(_derived_non_paddy(), False, id="derived"),
        pytest.param(_field_verified(), False, id="field"),
    ],
)
def test_is_synthetic_is_derived_from_source_kind(
    observation: LandCoverObservation,
    expected: bool | None,
) -> None:
    record = process_land_cover_observations([observation]).records[
        observation.h3_index
    ]

    assert record.is_synthetic is expected


def test_unknown_class_cannot_use_non_not_assessed_status() -> None:
    observation = replace(
        _unknown(),
        verification_status=VerificationStatus.UNVERIFIED,
    )

    with pytest.raises(LandCoverValidationError) as exc_info:
        validate_land_cover_observation(observation)

    assert (
        _error_code(exc_info)
        == LandCoverErrorCode.INCONSISTENT_VERIFICATION_STATUS
    )


def test_unknown_class_with_not_assessed_is_valid() -> None:
    observation = replace(
        _unknown(),
        verification_status=VerificationStatus.NOT_ASSESSED,
    )

    validate_land_cover_observation(observation)


def test_unknown_verification_status_is_rejected() -> None:
    observation = replace(
        _official_paddy(),
        verification_status="VERIFIED",  # type: ignore[arg-type]
    )

    with pytest.raises(LandCoverValidationError) as exc_info:
        validate_land_cover_observation(observation)

    assert (
        _error_code(exc_info)
        == LandCoverErrorCode.UNKNOWN_VERIFICATION_STATUS
    )


def test_unknown_source_kind_is_rejected() -> None:
    observation = replace(
        _official_paddy(),
        source_kind="SATELLITE",  # type: ignore[arg-type]
    )

    with pytest.raises(LandCoverValidationError) as exc_info:
        validate_land_cover_observation(observation)

    assert _error_code(exc_info) == LandCoverErrorCode.UNKNOWN_SOURCE_KIND


def test_invalid_provenance_date_and_resolution_are_rejected() -> None:
    bad_date = replace(
        _official_paddy(),
        provenance=Provenance(
            source="Mock dataset",
            observation_date="not-a-date",
        ),
    )
    bad_resolution = replace(
        _official_paddy(),
        provenance=Provenance(
            source="Mock dataset",
            spatial_resolution_m=0.0,
        ),
    )

    for observation in (bad_date, bad_resolution):
        with pytest.raises(LandCoverValidationError) as exc_info:
            validate_land_cover_observation(observation)
        assert _error_code(exc_info) == LandCoverErrorCode.INVALID_PAYLOAD


def test_missing_optional_provenance_is_not_invented() -> None:
    payload = serialize_land_cover_layer(
        process_land_cover_observations([_official_paddy()])
    )
    provenance = payload["records"][H3_A]["provenance"]

    assert provenance["source"] == "Mock official land-cover dataset"
    assert "observation_date" not in provenance
    assert "processing_date" not in provenance
    assert "spatial_resolution_m" not in provenance


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_parse_single_list_keyed_and_json_forms() -> None:
    single = parse_land_cover_payload(
        {"h3_index": H3_A, "land_cover_class": "PADDY_FIELD"}
    )
    listed = parse_land_cover_payload(
        [
            {"h3_index": H3_A, "land_cover_class": "PADDY_FIELD"},
            {"h3_index": H3_B, "land_cover_class": "NON_PADDY"},
        ]
    )
    keyed = parse_land_cover_payload(
        {H3_A: {"land_cover_class": "MIXED"}}
    )
    json_form = parse_land_cover_payload(
        json.dumps({"h3_index": H3_A, "land_cover_class": "PADDY_FIELD"})
    )

    assert len(single) == 1 and single[0].h3_index == H3_A
    assert [item.h3_index for item in listed] == [H3_A, H3_B]
    assert keyed[0].h3_index == H3_A
    assert json_form[0].h3_index == H3_A


def test_parse_unknown_class_is_rejected() -> None:
    with pytest.raises(LandCoverInputError) as exc_info:
        parse_land_cover_payload(
            {"h3_index": H3_A, "land_cover_class": "PADDY"}
        )

    assert _error_code(exc_info) == LandCoverErrorCode.UNKNOWN_LAND_COVER_CLASS


def test_parse_rejects_is_synthetic_as_input() -> None:
    with pytest.raises(LandCoverInputError) as exc_info:
        parse_land_cover_payload(
            {"h3_index": H3_A, "is_synthetic": True}
        )

    assert _error_code(exc_info) == LandCoverErrorCode.INVALID_PAYLOAD


def test_parse_rejects_h3_key_mismatch() -> None:
    with pytest.raises(LandCoverInputError) as exc_info:
        parse_land_cover_payload(
            {H3_A: {"h3_index": H3_B}}
        )

    assert _error_code(exc_info) == LandCoverErrorCode.INVALID_PAYLOAD


def test_parse_rejects_sidecar_payload() -> None:
    with pytest.raises(LandCoverInputError) as exc_info:
        parse_land_cover_payload({"records": {}})

    assert _error_code(exc_info) == LandCoverErrorCode.INVALID_PAYLOAD


def test_parse_keyed_mapping_validates_h3_key_during_parse() -> None:
    with pytest.raises(LandCoverInputError) as exc_info:
        parse_land_cover_payload(
            {INVALID_H3: {"land_cover_class": "UNKNOWN"}}
        )

    assert _error_code(exc_info) == LandCoverErrorCode.INVALID_H3_INDEX


def test_parse_list_defers_h3_validation_to_validation_stage() -> None:
    observations = parse_land_cover_payload(
        [{"h3_index": INVALID_H3}]
    )

    with pytest.raises(LandCoverValidationError) as exc_info:
        validate_land_cover_observation(observations[0])

    assert _error_code(exc_info) == LandCoverErrorCode.INVALID_H3_INDEX


def test_duplicate_json_h3_key_is_detected() -> None:
    text = (
        '{"'
        + H3_A
        + '": {"h3_index": "'
        + H3_A
        + '"}, "'
        + H3_A
        + '": {"h3_index": "'
        + H3_A
        + '"}}'
    )

    with pytest.raises(LandCoverInputError) as exc_info:
        parse_land_cover_payload(text)

    assert _error_code(exc_info) == LandCoverErrorCode.DUPLICATE_H3_INDEX


def test_duplicate_json_non_h3_key_is_detected() -> None:
    text = '{"h3_index": "%s", "h3_index": "%s"}' % (H3_A, H3_A)

    with pytest.raises(LandCoverInputError) as exc_info:
        parse_land_cover_payload(text)

    assert _error_code(exc_info) == LandCoverErrorCode.DUPLICATE_JSON_KEY


# ---------------------------------------------------------------------------
# Serialization and deserialization
# ---------------------------------------------------------------------------


def _sample_layer() -> LandCoverLayer:
    return process_land_cover_observations(
        [
            _official_paddy(H3_A),
            _synthetic(H3_B),
            _unknown(H3_C),
        ]
    )


def test_sidecar_round_trip_and_sorted_records() -> None:
    layer = _sample_layer()
    payload = serialize_land_cover_layer(layer)
    restored = deserialize_land_cover_layer(payload)

    assert list(payload["records"]) == sorted([H3_A, H3_B, H3_C])
    assert restored == layer
    for h3_index, record in payload["records"].items():
        assert record["h3_index"] == h3_index


@pytest.mark.parametrize(
    ("record", "expected_code"),
    [
        pytest.param(
            replace(_valid_record(), h3_index=INVALID_H3),
            LandCoverErrorCode.INVALID_H3_INDEX,
            id="invalid-h3",
        ),
        pytest.param(
            replace(
                _valid_record(),
                coverage=CoverageFractions(paddy_fraction=5.0),
            ),
            LandCoverErrorCode.INVALID_COVERAGE,
            id="invalid-coverage",
        ),
        pytest.param(
            replace(_valid_record(), provenance=None),
            LandCoverErrorCode.MISSING_SOURCE,
            id="missing-provenance",
        ),
        pytest.param(
            replace(
                _valid_record(),
                verification_status=VerificationStatus.FIELD_VERIFIED,
            ),
            LandCoverErrorCode.INCOMPLETE_VERIFICATION_PROVENANCE,
            id="incomplete-verification",
        ),
        pytest.param(
            replace(_valid_record(), notes=12345),  # type: ignore[arg-type]
            LandCoverErrorCode.INVALID_PAYLOAD,
            id="invalid-notes-type",
        ),
        pytest.param(
            replace(
                _valid_record(),
                land_cover_class="PADDY_FIELD",  # type: ignore[arg-type]
            ),
            LandCoverErrorCode.INVALID_PAYLOAD,
            id="string-enum",
        ),
        pytest.param(
            replace(
                _valid_record(),
                warnings=("ok", 123),  # type: ignore[arg-type]
            ),
            LandCoverErrorCode.INVALID_PAYLOAD,
            id="invalid-warnings",
        ),
        pytest.param(
            replace(_valid_record(), is_synthetic=True),
            LandCoverErrorCode.INCONSISTENT_SYNTHETIC_FLAG,
            id="inconsistent-synthetic",
        ),
    ],
)
def test_serialize_rejects_manual_invalid_records(
    record: LandCoverRecord,
    expected_code: str,
) -> None:
    layer = LandCoverLayer(records={record.h3_index: record})

    with pytest.raises(LandCoverSerializationError) as exc_info:
        serialize_land_cover_layer(layer)

    assert _error_code(exc_info) == expected_code


@pytest.mark.parametrize(
    ("layer", "expected_code"),
    [
        pytest.param(
            replace(_sample_layer(), schema_version="bad"),
            LandCoverErrorCode.UNSUPPORTED_SCHEMA_VERSION,
            id="schema-version",
        ),
        pytest.param(
            replace(_sample_layer(), status="FINAL"),
            LandCoverErrorCode.INVALID_PAYLOAD,
            id="status",
        ),
        pytest.param(
            replace(_sample_layer(), module="other"),
            LandCoverErrorCode.INVALID_PAYLOAD,
            id="module",
        ),
        pytest.param(
            replace(_sample_layer(), module_version="9.9"),
            LandCoverErrorCode.INVALID_PAYLOAD,
            id="module-version",
        ),
        pytest.param(
            replace(_sample_layer(), warnings="bad"),  # type: ignore[arg-type]
            LandCoverErrorCode.INVALID_PAYLOAD,
            id="warnings-type",
        ),
        pytest.param(
            replace(_sample_layer(), records=[]),  # type: ignore[arg-type]
            LandCoverErrorCode.INVALID_PAYLOAD,
            id="records-type",
        ),
    ],
)
def test_serialize_rejects_invalid_layer_metadata(
    layer: LandCoverLayer,
    expected_code: str,
) -> None:
    with pytest.raises(LandCoverSerializationError) as exc_info:
        serialize_land_cover_layer(layer)

    assert _error_code(exc_info) == expected_code


def test_serialize_rejects_layer_mutated_after_process() -> None:
    layer = _sample_layer()
    layer.records[H3_A] = replace(
        layer.records[H3_A],
        coverage=CoverageFractions(paddy_fraction=5.0),
    )

    with pytest.raises(LandCoverSerializationError) as exc_info:
        serialize_land_cover_layer(layer)

    assert _error_code(exc_info) == LandCoverErrorCode.INVALID_COVERAGE


def test_serialize_rejects_wrong_resolution_record() -> None:
    record = process_land_cover_observations(
        [_unknown(H3_RES8)],
        config=LandCoverConfig(expected_resolution=None),
    ).records[H3_RES8]
    layer = LandCoverLayer(records={H3_RES8: record})

    with pytest.raises(LandCoverSerializationError) as exc_info:
        serialize_land_cover_layer(layer)

    assert (
        _error_code(exc_info)
        == LandCoverErrorCode.UNSUPPORTED_H3_RESOLUTION
    )


def test_enrichment_rejects_invalid_layer_without_mutating_input() -> None:
    layer = LandCoverLayer(
        records={
            H3_A: replace(
                _valid_record(),
                coverage=CoverageFractions(paddy_fraction=5.0),
            )
        }
    )
    feature_collection = _feature_collection()
    original = copy.deepcopy(feature_collection)

    with pytest.raises(LandCoverSerializationError) as exc_info:
        enrich_geojson_with_land_cover(feature_collection, layer)

    assert _error_code(exc_info) == LandCoverErrorCode.INVALID_COVERAGE
    assert feature_collection == original


def test_write_rejects_invalid_layer_without_creating_file(
    allowed_output_root: Path,
) -> None:
    layer = LandCoverLayer(
        records={
            H3_A: replace(
                _valid_record(),
                coverage=CoverageFractions(paddy_fraction=5.0),
            )
        }
    )
    output_path = allowed_output_root / "invalid.json"

    with pytest.raises(LandCoverSerializationError):
        write_land_cover_sidecar(layer, output_path)

    assert not output_path.exists()


def test_sidecar_has_required_shape_and_no_forbidden_fields() -> None:
    payload = serialize_land_cover_layer(_sample_layer())

    assert payload["schema_version"] == "land_cover.sidecar.v0.1"
    assert payload["status"] == "PROVISIONAL"
    assert payload["module"] == "land_cover_classifier"
    assert payload["module_version"] == "0.1.0"
    assert isinstance(payload["records"], dict)
    assert isinstance(payload["warnings"], list)

    keys = _collect_keys(payload)
    assert "contract" not in keys
    assert "confidence" not in keys
    assert "accuracy" not in keys
    assert "quality_score" not in keys


def test_is_synthetic_serializes_as_bool_and_null() -> None:
    payload = serialize_land_cover_layer(_sample_layer())

    assert payload["records"][H3_A]["is_synthetic"] is False
    assert payload["records"][H3_B]["is_synthetic"] is True
    assert payload["records"][H3_C]["is_synthetic"] is None


def test_unknown_schema_version_is_rejected() -> None:
    payload = serialize_land_cover_layer(_sample_layer())
    payload["schema_version"] = "land_cover.sidecar.v99"

    with pytest.raises(LandCoverSerializationError) as exc_info:
        deserialize_land_cover_layer(payload)

    assert _error_code(exc_info) == LandCoverErrorCode.UNSUPPORTED_SCHEMA_VERSION


@pytest.mark.parametrize(
    ("field", "value"),
    [
        pytest.param("status", "FINAL", id="status"),
        pytest.param("module", "other", id="module"),
        pytest.param("module_version", "9.9", id="module-version"),
    ],
)
def test_sidecar_metadata_mismatch_is_rejected(
    field: str,
    value: str,
) -> None:
    payload = serialize_land_cover_layer(_sample_layer())
    payload[field] = value

    with pytest.raises(LandCoverSerializationError) as exc_info:
        deserialize_land_cover_layer(payload)

    assert _error_code(exc_info) == LandCoverErrorCode.INVALID_PAYLOAD


def test_sidecar_record_without_is_synthetic_is_rejected() -> None:
    payload = serialize_land_cover_layer(_sample_layer())
    del payload["records"][H3_A]["is_synthetic"]

    with pytest.raises(LandCoverSerializationError) as exc_info:
        deserialize_land_cover_layer(payload)

    assert _error_code(exc_info) == LandCoverErrorCode.INVALID_PAYLOAD


def test_mismatched_record_key_is_rejected() -> None:
    payload = serialize_land_cover_layer(_sample_layer())
    payload["records"][H3_A]["h3_index"] = H3_B

    with pytest.raises(LandCoverSerializationError) as exc_info:
        deserialize_land_cover_layer(payload)

    assert _error_code(exc_info) == LandCoverErrorCode.INVALID_PAYLOAD


def test_inconsistent_synthetic_flag_is_rejected() -> None:
    payload = serialize_land_cover_layer(_sample_layer())
    payload["records"][H3_B]["is_synthetic"] = False

    with pytest.raises(LandCoverSerializationError) as exc_info:
        deserialize_land_cover_layer(payload)

    assert (
        _error_code(exc_info)
        == LandCoverErrorCode.INCONSISTENT_SYNTHETIC_FLAG
    )


def test_duplicate_h3_json_key_in_sidecar_is_detected() -> None:
    payload = serialize_land_cover_layer(_sample_layer())
    record_text = json.dumps(payload["records"][H3_A])
    text = (
        '{"schema_version": "land_cover.sidecar.v0.1", '
        '"status": "PROVISIONAL", '
        '"module": "land_cover_classifier", '
        '"module_version": "0.1.0", '
        '"records": {'
        f'"{H3_A}": {record_text}, "{H3_A}": {record_text}'
        '}, "warnings": []}'
    )

    with pytest.raises(LandCoverSerializationError) as exc_info:
        deserialize_land_cover_layer(text)

    assert _error_code(exc_info) == LandCoverErrorCode.DUPLICATE_H3_INDEX


def test_warnings_are_preserved_through_round_trip() -> None:
    observation = replace(
        _official_paddy(),
        coverage=CoverageFractions(paddy_fraction=0.5),
    )
    layer = process_land_cover_observations([observation])
    restored = deserialize_land_cover_layer(
        serialize_land_cover_layer(layer)
    )

    assert restored.warnings == layer.warnings
    assert (
        f"{H3_A}: {LandCoverWarning.COVERAGE_METHOD_UNKNOWN}"
        in restored.warnings
    )


# ---------------------------------------------------------------------------
# GeoJSON enrichment
# ---------------------------------------------------------------------------


def _feature_collection() -> dict[str, Any]:
    contract_a = {"contract_version": "1.0", "marker": "A"}
    contract_b = {"contract_version": "1.0", "marker": "B"}
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [109.17, -7.45]},
                "properties": {
                    "h3_index": H3_A,
                    "contract": contract_a,
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [109.18, -7.46]},
                "properties": {
                    "h3_index": H3_B,
                    "contract": contract_b,
                },
            },
        ],
    }


def test_enrichment_does_not_mutate_input_or_contract() -> None:
    feature_collection = _feature_collection()
    original = copy.deepcopy(feature_collection)
    layer = process_land_cover_observations([_official_paddy(H3_A)])

    enriched = enrich_geojson_with_land_cover(feature_collection, layer)

    assert feature_collection == original
    assert enriched is not feature_collection
    assert enriched["features"][0]["properties"]["contract"] == original[
        "features"
    ][0]["properties"]["contract"]
    assert enriched["features"][1]["properties"]["contract"] == original[
        "features"
    ][1]["properties"]["contract"]
    assert (
        enriched["features"][0]["properties"]["land_cover_record"][
            "land_cover_class"
        ]
        == "PADDY_FIELD"
    )


def test_enrichment_adds_unknown_for_missing_record() -> None:
    layer = process_land_cover_observations([_official_paddy(H3_A)])

    enriched = enrich_geojson_with_land_cover(
        _feature_collection(),
        layer,
        include_missing_as_unknown=True,
    )
    missing_record = enriched["features"][1]["properties"][
        "land_cover_record"
    ]

    assert missing_record["land_cover_class"] == "UNKNOWN"
    assert missing_record["verification_status"] == "NOT_ASSESSED"
    assert missing_record["source_kind"] == "UNKNOWN_SOURCE"
    assert missing_record["is_synthetic"] is None


def test_enrichment_can_leave_missing_records_absent() -> None:
    layer = process_land_cover_observations([_official_paddy(H3_A)])

    enriched = enrich_geojson_with_land_cover(
        _feature_collection(),
        layer,
        include_missing_as_unknown=False,
    )

    assert "land_cover_record" in enriched["features"][0]["properties"]
    assert "land_cover_record" not in enriched["features"][1]["properties"]


# ---------------------------------------------------------------------------
# File I/O and configuration
# ---------------------------------------------------------------------------


def test_write_and_read_sidecar_under_allowed_root(
    allowed_output_root: Path,
) -> None:
    layer = _sample_layer()
    output_path = allowed_output_root / "nested" / "land_cover_sidecar.json"

    size = write_land_cover_sidecar(layer, output_path)
    restored = read_land_cover_sidecar(output_path)

    assert output_path.exists()
    assert output_path.parent.exists()
    assert size == output_path.stat().st_size
    assert restored == layer


@pytest.mark.parametrize(
    "path",
    [
        pytest.param(Path(".git/config"), id="git-config"),
        pytest.param(Path("src/engines/synthetic_h3_generator.py"), id="src"),
        pytest.param(Path("tests/test_contract_validator.py"), id="tests"),
        pytest.param(Path("docs/synthetic_h3_generator_design.md"), id="docs"),
        pytest.param(Path("contracts/README.md"), id="contracts-readme"),
        pytest.param(Path("data/mock/README.md"), id="mock-readme"),
        pytest.param(
            Path("data/boundaries/README.md"), id="boundaries-readme"
        ),
        pytest.param(Path("README.md"), id="root-readme"),
        pytest.param(
            EXTERNAL_ROOT / "ariefs_workresult" / "should-not-write.json",
            id="external-root",
        ),
        pytest.param(Path("web-app/README.md"), id="web-app"),
        pytest.param(Path("gis-viewer/README.md"), id="gis-viewer"),
        pytest.param(
            Path("data-pipeline/README.md"), id="data-pipeline"
        ),
        pytest.param(
            Path("physics-engines/README.md"), id="physics-engines"
        ),
        pytest.param(TASK2_GEOJSON_PATH, id="task2-output"),
        pytest.param(ROI_PATH, id="roi"),
        pytest.param(CONTRACT_SCHEMA_PATH, id="contract-schema"),
        pytest.param(
            ALLOWED_OUTPUT_ROOT / "sidecar.txt", id="non-json-extension"
        ),
        pytest.param(ALLOWED_OUTPUT_ROOT / "sidecar", id="no-extension"),
        pytest.param(
            ALLOWED_OUTPUT_ROOT / ".." / "mock" / "foo.json",
            id="dotdot-to-mock",
        ),
        pytest.param(
            ALLOWED_OUTPUT_ROOT / ".." / "src" / "foo.json",
            id="dotdot-to-src",
        ),
        pytest.param(
            Path("src\\engines\\synthetic_h3_generator.py"),
            id="windows-separator",
        ),
        pytest.param(
            Path("SRC/ENGINES/SYNTHETIC_H3_GENERATOR.PY"),
            id="case-variation",
        ),
    ],
)
def test_disallowed_output_paths_are_rejected(path: Path) -> None:
    with pytest.raises(LandCoverSerializationError) as exc_info:
        write_land_cover_sidecar(_sample_layer(), path)

    assert _error_code(exc_info) == LandCoverErrorCode.UNSAFE_OUTPUT_PATH


def test_existing_file_outside_allowed_root_is_not_overwritten(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text("ORIGINAL", encoding="utf-8")

    with pytest.raises(LandCoverSerializationError) as exc_info:
        write_land_cover_sidecar(_sample_layer(), outside)

    assert _error_code(exc_info) == LandCoverErrorCode.UNSAFE_OUTPUT_PATH
    assert outside.read_text(encoding="utf-8") == "ORIGINAL"


def test_allowed_output_requires_json_extension(
    allowed_output_root: Path,
) -> None:
    for suffix in (".txt", ""):
        path = allowed_output_root / f"sidecar{suffix}"
        with pytest.raises(LandCoverSerializationError) as exc_info:
            write_land_cover_sidecar(_sample_layer(), path)
        assert _error_code(exc_info) == LandCoverErrorCode.UNSAFE_OUTPUT_PATH


def test_directory_output_path_inside_allowed_root_is_rejected(
    allowed_output_root: Path,
) -> None:
    path = allowed_output_root / "directory.json"
    path.mkdir(parents=True)

    with pytest.raises(LandCoverSerializationError) as exc_info:
        write_land_cover_sidecar(_sample_layer(), path)

    assert _error_code(exc_info) == LandCoverErrorCode.INVALID_PAYLOAD


def test_allowed_output_path_normalizes_dotdot_and_case(
    allowed_output_root: Path,
) -> None:
    path = allowed_output_root / "nested" / ".." / "sidecar.JSON"

    write_land_cover_sidecar(_sample_layer(), path)

    assert (allowed_output_root / "sidecar.JSON").exists()


def _create_directory_link(link: Path, target: Path) -> None:
    if os.name == "nt":
        import subprocess

        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.skip(
                "Cannot create a Windows junction: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        return

    try:
        os.symlink(target, link, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Cannot create a directory symlink: {exc}")


def test_symlink_escape_outside_allowed_root_is_rejected(
    allowed_output_root: Path,
    tmp_path: Path,
) -> None:
    allowed_output_root.mkdir(parents=True, exist_ok=True)
    outside_directory = tmp_path / "outside"
    outside_directory.mkdir()
    link = allowed_output_root / "escape"
    _create_directory_link(link, outside_directory)

    try:
        with pytest.raises(LandCoverSerializationError) as exc_info:
            write_land_cover_sidecar(
                _sample_layer(), link / "sidecar.json"
            )
        assert _error_code(exc_info) == LandCoverErrorCode.UNSAFE_OUTPUT_PATH
        assert not (outside_directory / "sidecar.json").exists()
    finally:
        if link.is_symlink():
            link.unlink()
        elif link.exists():
            link.rmdir()


def test_missing_sidecar_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(LandCoverSerializationError) as exc_info:
        read_land_cover_sidecar(tmp_path / "missing.json")

    assert _error_code(exc_info) == LandCoverErrorCode.SIDECAR_READ_ERROR


def test_coverage_derived_class_policy_is_not_enabled() -> None:
    with pytest.raises(UnsupportedPolicyError) as exc_info:
        validate_land_cover_observation(
            _unknown(),
            config=LandCoverConfig(derive_class_from_coverage=True),
        )

    assert _error_code(exc_info) == LandCoverErrorCode.UNSUPPORTED_POLICY


def test_conflict_priority_policy_is_not_enabled() -> None:
    with pytest.raises(UnsupportedPolicyError) as exc_info:
        validate_land_cover_observation(
            _unknown(),
            config=LandCoverConfig(conflict_policy="PRIORITY"),
        )

    assert _error_code(exc_info) == LandCoverErrorCode.UNSUPPORTED_POLICY


@pytest.mark.parametrize(
    "tolerance",
    [
        pytest.param(-1.0, id="negative"),
        pytest.param(1.0, id="one"),
        pytest.param(2.0, id="two"),
        pytest.param(
            MAX_COVERAGE_TOLERANCE + 1e-9,
            id="above-max",
        ),
    ],
)
def test_invalid_coverage_tolerance_is_rejected(tolerance: float) -> None:
    with pytest.raises(LandCoverInputError) as exc_info:
        validate_land_cover_observation(
            _unknown(),
            config=LandCoverConfig(coverage_tolerance=tolerance),
        )

    assert _error_code(exc_info) == LandCoverErrorCode.INVALID_PAYLOAD


@pytest.mark.parametrize(
    "tolerance",
    [
        pytest.param(0.0, id="zero"),
        pytest.param(MAX_COVERAGE_TOLERANCE, id="max"),
    ],
)
def test_allowed_coverage_tolerance_values_are_accepted(
    tolerance: float,
) -> None:
    observation = replace(
        _official_paddy(),
        coverage=CoverageFractions(
            paddy_fraction=0.5,
            non_paddy_fraction=0.5,
            method="SOURCE_PROVIDED",
        ),
    )

    validate_land_cover_observation(
        observation,
        config=LandCoverConfig(coverage_tolerance=tolerance),
    )


def test_coverage_sum_boundaries() -> None:
    config = LandCoverConfig(
        coverage_tolerance=MAX_COVERAGE_TOLERANCE
    )

    exact_one = replace(
        _official_paddy(),
        coverage=CoverageFractions(
            paddy_fraction=0.5,
            non_paddy_fraction=0.5,
            method="SOURCE_PROVIDED",
        ),
    )
    exact_one_plus_tolerance = replace(
        _official_paddy(),
        coverage=CoverageFractions(
            paddy_fraction=0.5,
            non_paddy_fraction=0.501,
            method="SOURCE_PROVIDED",
        ),
    )
    above_tolerance = replace(
        _official_paddy(),
        coverage=CoverageFractions(
            paddy_fraction=0.5,
            non_paddy_fraction=0.501,
            other_fraction=0.000001,
            method="SOURCE_PROVIDED",
        ),
    )

    validate_land_cover_observation(exact_one, config=config)
    validate_land_cover_observation(exact_one_plus_tolerance, config=config)

    with pytest.raises(LandCoverValidationError) as exc_info:
        validate_land_cover_observation(above_tolerance, config=config)

    assert _error_code(exc_info) == LandCoverErrorCode.INVALID_COVERAGE


def test_coverage_tolerance_zero_rejects_sum_above_one() -> None:
    observation = replace(
        _official_paddy(),
        coverage=CoverageFractions(
            paddy_fraction=0.5,
            non_paddy_fraction=0.501,
            method="SOURCE_PROVIDED",
        ),
    )

    with pytest.raises(LandCoverValidationError) as exc_info:
        validate_land_cover_observation(
            observation,
            config=LandCoverConfig(coverage_tolerance=0.0),
        )

    assert _error_code(exc_info) == LandCoverErrorCode.INVALID_COVERAGE


def test_serialize_round_trip_with_max_tolerance_coverage() -> None:
    observation = replace(
        _official_paddy(),
        coverage=CoverageFractions(
            paddy_fraction=0.5,
            non_paddy_fraction=0.501,
            method="SOURCE_PROVIDED",
        ),
    )
    layer = process_land_cover_observations(
        [observation],
        config=LandCoverConfig(
            coverage_tolerance=MAX_COVERAGE_TOLERANCE
        ),
    )

    restored = deserialize_land_cover_layer(
        serialize_land_cover_layer(layer)
    )

    assert restored == layer


def test_process_rejects_non_observation_iterables() -> None:
    with pytest.raises(LandCoverInputError):
        process_land_cover_observations(None)  # type: ignore[arg-type]
    with pytest.raises(LandCoverInputError):
        process_land_cover_observations("not observations")  # type: ignore[arg-type]
    with pytest.raises(LandCoverInputError):
        process_land_cover_observations([{"h3_index": H3_A}])  # type: ignore[list-item]


def test_no_automatic_classification_from_coverage() -> None:
    observation = replace(
        _unknown(),
        coverage=CoverageFractions(
            paddy_fraction=0.9,
            method="SOURCE_PROVIDED",
        ),
    )

    record = process_land_cover_observations([observation]).records[H3_A]

    assert record.land_cover_class is LandCoverClass.UNKNOWN
    assert record.verification_status is VerificationStatus.NOT_ASSESSED
