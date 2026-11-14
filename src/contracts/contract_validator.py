"""Provisional validator for CYBER-KATAM grid-cell contracts.

The validator uses a layered design:

1. Strict JSON parsing (with non-finite number rejection).
2. JSON Schema Draft 2020-12 structural validation.
3. Opt-in semantic checks that are explicitly labelled provisional.

No observation-quality claim is made by this module. Passing structural
validation only means the payload matches the current provisional schema; it does
not prove that any NASA-derived indicator is physically correct.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, NoReturn

import h3
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from .validation_errors import (
    ContractParsingError,
    ErrorCode,
    SchemaConfigurationError,
    ValidationError,
    ValidationResult,
)

# Resolve the repository root from this file, never from the current working
# directory: src/contracts/contract_validator.py -> parents[2] is the repo root.
DEFAULT_SCHEMA_PATH: Final[Path] = (
    Path(__file__).resolve().parents[2] / "contracts" / "grid_cell_contract.schema.json"
)

_ADDITIONAL_PROPERTY_RE: Final[re.Pattern[str]] = re.compile(
    r"'([^']+)'(?: was unexpected| is not allowed)?"
)
_REQUIRED_PROPERTY_RE: Final[re.Pattern[str]] = re.compile(
    r"'([^']+)' is a required property"
)
_DRAFT_2020_12_URI: Final[str] = "https://json-schema.org/draft/2020-12/schema"


class _NonFiniteJSONConstant(ValueError):
    """Internal signal used when json.loads encounters NaN or Infinity."""


def _reject_non_finite_constant(value: str) -> NoReturn:
    """Reject the non-standard JSON constants NaN, Infinity, and -Infinity."""

    raise _NonFiniteJSONConstant(value)


def _pointer(parts: list[Any] | tuple[Any, ...]) -> str:
    """Convert path segments to an RFC 6901 JSON Pointer."""

    if not parts:
        return ""
    escaped = [
        str(part).replace("~", "~0").replace("/", "~1") for part in parts
    ]
    return "/" + "/".join(escaped)


def _json_type_name(value: Any) -> str:
    """Return the JSON type name for a Python value without exposing the value."""

    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _split_pointer(path: str) -> list[str]:
    """Split a JSON Pointer into unescaped segments."""

    if path in ("", "/"):
        return []
    return [
        segment.replace("~1", "/").replace("~0", "~")
        for segment in path.lstrip("/").split("/")
    ]


def _scan_payload(value: Any, path: str = "") -> list[ValidationError]:
    """Find non-finite numbers and non-string keys in a Python mapping.

    JSON does not allow NaN, Infinity, -Infinity, or non-string object keys.
    Python dictionaries can contain all three, so this check is required before
    handing the payload to ``jsonschema``. The function does not coerce or
    otherwise modify the payload.
    """

    errors: list[ValidationError] = []

    def visit(current: Any, current_path: str, seen: set[int]) -> None:
        if isinstance(current, float) and not math.isfinite(current):
            errors.append(
                ValidationError(
                    code=ErrorCode.NON_FINITE_NUMBER,
                    message="Non-finite numeric values (NaN/Infinity) are not allowed.",
                    path=current_path,
                    validator="json_parser",
                    layer="parsing",
                )
            )
            return

        if isinstance(current, Mapping):
            object_id = id(current)
            if object_id in seen:
                errors.append(
                    ValidationError(
                        code=ErrorCode.INVALID_JSON,
                        message="Input contains a circular reference and is not valid JSON.",
                        path=current_path,
                        validator="json_parser",
                        layer="parsing",
                    )
                )
                return
            seen.add(object_id)
            for key, child in current.items():
                if not isinstance(key, str):
                    errors.append(
                        ValidationError(
                            code=ErrorCode.INVALID_OBJECT_KEY,
                            message="JSON object keys must be strings.",
                            path=current_path,
                            validator="json_parser",
                            layer="parsing",
                        )
                    )
                    continue
                visit(child, _pointer([*_split_pointer(current_path), key]), seen)
            seen.discard(object_id)
            return

        if isinstance(current, (list, tuple)):
            object_id = id(current)
            if object_id in seen:
                errors.append(
                    ValidationError(
                        code=ErrorCode.INVALID_JSON,
                        message="Input contains a circular reference and is not valid JSON.",
                        path=current_path,
                        validator="json_parser",
                        layer="parsing",
                    )
                )
                return
            seen.add(object_id)
            for index, child in enumerate(current):
                visit(
                    child,
                    _pointer([*_split_pointer(current_path), index]),
                    seen,
                )
            seen.discard(object_id)

    visit(value, path, set())
    return errors


def parse_contract_payload(payload: Mapping[str, Any] | str) -> dict[str, Any]:
    """Strictly parse a contract payload without changing its values.

    Args:
        payload: A JSON object already decoded into a Python mapping, or a JSON
            string. No coercion of numeric strings, no default insertion, and no
            clipping is performed.

    Returns:
        The decoded JSON object as a plain dictionary.

    Raises:
        ContractParsingError: Carries one or more parsing errors. Callers that
            want a :class:`ValidationResult` should use
            :meth:`ContractValidator.validate` instead.
    """

    if payload is None:
        raise ContractParsingError(
            [
                ValidationError(
                    code=ErrorCode.EMPTY_INPUT,
                    message="Input is empty. Provide a JSON object or JSON string.",
                    path="",
                    validator="json_parser",
                    layer="parsing",
                )
            ]
        )

    if isinstance(payload, str):
        if not payload.strip():
            raise ContractParsingError(
                [
                    ValidationError(
                        code=ErrorCode.EMPTY_INPUT,
                        message="Input is empty. Provide a JSON object or JSON string.",
                        path="",
                        validator="json_parser",
                        layer="parsing",
                    )
                ]
            )

        try:
            document = json.loads(
                payload,
                parse_constant=_reject_non_finite_constant,
            )
        except _NonFiniteJSONConstant:
            raise ContractParsingError(
                [
                    ValidationError(
                        code=ErrorCode.NON_FINITE_NUMBER,
                        message=(
                            "JSON contains NaN, Infinity, or -Infinity, which are "
                            "not permitted by the contract format."
                        ),
                        path="",
                        validator="json_parser",
                        layer="parsing",
                    )
                ]
            ) from None
        except json.JSONDecodeError as exc:
            raise ContractParsingError(
                [
                    ValidationError(
                        code=ErrorCode.INVALID_JSON,
                        message=(
                            f"Malformed JSON at line {exc.lineno}, "
                            f"column {exc.colno}."
                        ),
                        path="",
                        validator="json_parser",
                        layer="parsing",
                    )
                ]
            ) from exc

        scan_errors = _scan_payload(document)
        if scan_errors:
            raise ContractParsingError(scan_errors)

        if not isinstance(document, dict):
            raise ContractParsingError(
                [
                    ValidationError(
                        code=ErrorCode.ROOT_NOT_OBJECT,
                        message=(
                            "Top-level JSON value must be an object, "
                            f"not {_json_type_name(document)}."
                        ),
                        path="",
                        validator="json_parser",
                        layer="parsing",
                    )
                ]
            )
        if not document:
            raise ContractParsingError(
                [
                    ValidationError(
                        code=ErrorCode.EMPTY_INPUT,
                        message="Input JSON object is empty.",
                        path="",
                        validator="json_parser",
                        layer="parsing",
                    )
                ]
            )
        return document

    if isinstance(payload, Mapping):
        if not payload:
            raise ContractParsingError(
                [
                    ValidationError(
                        code=ErrorCode.EMPTY_INPUT,
                        message="Input object is empty.",
                        path="",
                        validator="json_parser",
                        layer="parsing",
                    )
                ]
            )

        scan_errors = _scan_payload(payload)
        if scan_errors:
            raise ContractParsingError(scan_errors)
        return dict(payload)

    raise ContractParsingError(
        [
            ValidationError(
                code=ErrorCode.UNSUPPORTED_INPUT_TYPE,
                message=(
                    "Unsupported input type "
                    f"'{type(payload).__name__}'. Expected a mapping or JSON string."
                ),
                path="",
                validator="json_parser",
                layer="parsing",
            )
        ]
    )


def load_contract_schema(
    schema_path: str | Path | None = None,
) -> dict[str, Any]:
    """Load and validate the JSON Schema file.

    Args:
        schema_path: Optional explicit schema path. When omitted, the repository
            schema at ``contracts/grid_cell_contract.schema.json`` is used. The
            default is resolved from this module's location, not the current
            working directory.

    Returns:
        The parsed schema as a dictionary.

    Raises:
        SchemaConfigurationError: If the file cannot be read, is not valid JSON,
            is not a JSON object, or fails
            :meth:`Draft202012Validator.check_schema`.
    """

    path = (
        Path(schema_path).expanduser().resolve()
        if schema_path is not None
        else DEFAULT_SCHEMA_PATH
    )

    try:
        raw_schema = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SchemaConfigurationError(
            f"Cannot read contract schema at '{path}': {exc}",
            code=ErrorCode.SCHEMA_LOAD_ERROR,
        ) from exc

    try:
        schema = json.loads(
            raw_schema,
            parse_constant=_reject_non_finite_constant,
        )
    except _NonFiniteJSONConstant:
        raise SchemaConfigurationError(
            f"Contract schema at '{path}' contains NaN or Infinity.",
            code=ErrorCode.SCHEMA_NON_FINITE_NUMBER,
        ) from None
    except json.JSONDecodeError as exc:
        raise SchemaConfigurationError(
            (
                f"Contract schema at '{path}' is not valid JSON at line "
                f"{exc.lineno}, column {exc.colno}."
            ),
            code=ErrorCode.SCHEMA_PARSE_ERROR,
        ) from exc

    if not isinstance(schema, dict):
        raise SchemaConfigurationError(
            f"Contract schema at '{path}' must be a JSON object.",
            code=ErrorCode.SCHEMA_NOT_OBJECT,
        )

    declared_draft = schema.get("$schema")
    if declared_draft != _DRAFT_2020_12_URI:
        raise SchemaConfigurationError(
            (
                f"Contract schema at '{path}' must declare "
                f"\"$schema\": \"{_DRAFT_2020_12_URI}\"."
            ),
            code=ErrorCode.SCHEMA_INVALID,
        )

    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise SchemaConfigurationError(
            f"Contract schema at '{path}' is invalid: {exc.message}",
            code=ErrorCode.SCHEMA_INVALID,
        ) from exc

    return schema


def _convert_schema_error(
    error: JsonSchemaValidationError,
) -> list[ValidationError]:
    """Convert a jsonschema error into one or more stable validation errors."""

    keyword = error.validator
    base_path = list(error.absolute_path)
    base_pointer = _pointer(base_path)
    validator_value = error.validator_value

    if keyword == "required":
        match = _REQUIRED_PROPERTY_RE.search(error.message)
        if match:
            missing_name = match.group(1)
            return [
                ValidationError(
                    code=ErrorCode.REQUIRED_FIELD,
                    message=f"Required property '{missing_name}' is missing.",
                    path=_pointer([*base_path, missing_name]),
                    validator="required",
                    layer="schema",
                )
            ]
        return [
            ValidationError(
                code=ErrorCode.REQUIRED_FIELD,
                message="A required property is missing.",
                path=base_pointer,
                validator="required",
                layer="schema",
            )
        ]

    if keyword == "additionalProperties":
        unexpected_names = _ADDITIONAL_PROPERTY_RE.findall(error.message)
        if unexpected_names:
            return [
                ValidationError(
                    code=ErrorCode.ADDITIONAL_PROPERTY,
                    message=(
                        f"Additional property '{name}' is not allowed by the "
                        "contract."
                    ),
                    path=_pointer([*base_path, name]),
                    validator="additionalProperties",
                    layer="schema",
                )
                for name in unexpected_names
            ]
        return [
            ValidationError(
                code=ErrorCode.ADDITIONAL_PROPERTY,
                message="Additional properties are not allowed by the contract.",
                path=base_pointer,
                validator="additionalProperties",
                layer="schema",
            )
        ]

    if keyword == "type":
        expected = validator_value
        if isinstance(expected, list):
            expected_text = " or ".join(f"'{item}'" for item in expected)
        else:
            expected_text = f"'{expected}'"
        return [
            ValidationError(
                code=ErrorCode.TYPE_MISMATCH,
                message=(
                    f"Expected JSON type {expected_text} but found "
                    f"'{_json_type_name(error.instance)}'."
                ),
                path=base_pointer,
                validator="type",
                layer="schema",
            )
        ]

    if keyword == "enum":
        allowed = json.dumps(validator_value, ensure_ascii=True)
        return [
            ValidationError(
                code=ErrorCode.ENUM_MISMATCH,
                message=f"Value is not one of the allowed enum values: {allowed}.",
                path=base_pointer,
                validator="enum",
                layer="schema",
            )
        ]

    if keyword == "const":
        expected = json.dumps(validator_value, ensure_ascii=True)
        return [
            ValidationError(
                code=ErrorCode.CONST_MISMATCH,
                message=f"Value must equal the contract constant {expected}.",
                path=base_pointer,
                validator="const",
                layer="schema",
            )
        ]

    if keyword == "minimum":
        return [
            ValidationError(
                code=ErrorCode.BELOW_MINIMUM,
                message=f"Value is below the allowed minimum of {validator_value}.",
                path=base_pointer,
                validator="minimum",
                layer="schema",
            )
        ]

    if keyword == "maximum":
        return [
            ValidationError(
                code=ErrorCode.ABOVE_MAXIMUM,
                message=f"Value is above the allowed maximum of {validator_value}.",
                path=base_pointer,
                validator="maximum",
                layer="schema",
            )
        ]

    if keyword == "exclusiveMinimum":
        return [
            ValidationError(
                code=ErrorCode.BELOW_EXCLUSIVE_MINIMUM,
                message=(
                    "Value must be strictly greater than "
                    f"{validator_value}."
                ),
                path=base_pointer,
                validator="exclusiveMinimum",
                layer="schema",
            )
        ]

    if keyword == "exclusiveMaximum":
        return [
            ValidationError(
                code=ErrorCode.ABOVE_EXCLUSIVE_MAXIMUM,
                message=(
                    "Value must be strictly less than "
                    f"{validator_value}."
                ),
                path=base_pointer,
                validator="exclusiveMaximum",
                layer="schema",
            )
        ]

    if keyword == "minLength":
        return [
            ValidationError(
                code=ErrorCode.STRING_TOO_SHORT,
                message=(
                    "String is shorter than the minimum length of "
                    f"{validator_value}."
                ),
                path=base_pointer,
                validator="minLength",
                layer="schema",
            )
        ]

    if keyword == "maxLength":
        return [
            ValidationError(
                code=ErrorCode.STRING_TOO_LONG,
                message=(
                    "String is longer than the maximum length of "
                    f"{validator_value}."
                ),
                path=base_pointer,
                validator="maxLength",
                layer="schema",
            )
        ]

    if keyword == "pattern":
        return [
            ValidationError(
                code=ErrorCode.STRING_PATTERN_MISMATCH,
                message=(
                    "String does not match the required pattern "
                    f"'{validator_value}'."
                ),
                path=base_pointer,
                validator="pattern",
                layer="schema",
            )
        ]

    if keyword == "minItems":
        return [
            ValidationError(
                code=ErrorCode.ARRAY_TOO_SHORT,
                message=(
                    "Array has fewer than the minimum of "
                    f"{validator_value} item(s)."
                ),
                path=base_pointer,
                validator="minItems",
                layer="schema",
            )
        ]

    if keyword == "maxItems":
        return [
            ValidationError(
                code=ErrorCode.ARRAY_TOO_LONG,
                message=(
                    "Array has more than the maximum of "
                    f"{validator_value} item(s)."
                ),
                path=base_pointer,
                validator="maxItems",
                layer="schema",
            )
        ]

    return [
        ValidationError(
            code=ErrorCode.SCHEMA_VALIDATION_ERROR,
            message=f"Schema validation failed for keyword '{keyword}'.",
            path=base_pointer,
            validator=str(keyword),
            layer="schema",
        )
    ]


class ContractValidator:
    """Validate one provisional grid-cell contract.

    The schema is loaded once per validator instance. Semantic rules are opt-in
    because the corresponding contract decisions have not been ratified.

    Args:
        schema_path: Optional explicit schema path. Defaults to the repository
            schema resolved from ``__file__``.
        enable_provisional_semantics: When True, run the clearly labelled
            provisional semantic checks (H3 validity, H3 parent consistency, and
            unique rotation scenario ids). Defaults to False because these rules
            are not ratified yet.

    Raises:
        SchemaConfigurationError: If the schema cannot be loaded or is invalid.
    """

    def __init__(
        self,
        schema_path: str | Path | None = None,
        *,
        enable_provisional_semantics: bool = False,
    ) -> None:
        self.schema_path: Path = (
            Path(schema_path).expanduser().resolve()
            if schema_path is not None
            else DEFAULT_SCHEMA_PATH
        )
        self._schema = load_contract_schema(self.schema_path)
        # No format checker is attached: the contract does not define any JSON
        # Schema "format" values, and format checks must not replace type/domain
        # checks.
        self._validator = Draft202012Validator(self._schema)
        self.enable_provisional_semantics = enable_provisional_semantics

    def validate(self, payload: Mapping[str, Any] | str) -> ValidationResult:
        """Validate a payload through all enabled layers.

        Parsing errors and structural errors are reported as a normal
        :class:`ValidationResult`. Semantic checks run only when structural
        validation succeeds, which avoids cascading type errors.

        Args:
            payload: A mapping or JSON string.

        Returns:
            A deterministic validation result with ordered errors.
        """

        try:
            document = parse_contract_payload(payload)
        except ContractParsingError as exc:
            return ValidationResult.build(exc.errors)

        structural_errors = self._validate_structure(document)
        if structural_errors:
            return ValidationResult.build(structural_errors)

        semantic_errors = self._validate_semantics(document)
        return ValidationResult.build(semantic_errors)

    def _validate_structure(
        self, document: Mapping[str, Any]
    ) -> list[ValidationError]:
        """Run JSON Schema validation and convert jsonschema errors."""

        errors: list[ValidationError] = []
        for schema_error in self._validator.iter_errors(document):
            errors.extend(_convert_schema_error(schema_error))
        return errors

    def _validate_semantics(
        self, document: Mapping[str, Any]
    ) -> list[ValidationError]:
        """Run only explicitly provisional, definitional semantic checks.

        No business thresholds are applied here. In particular, this method does
        not infer erosion alerts, nullable indicators, scenario counts, or
        cross-engine thresholds that the team has not ratified.
        """

        if not self.enable_provisional_semantics:
            return []

        errors: list[ValidationError] = []
        h3_index = document["h3_index"]
        h3_index_is_valid = h3.is_valid_cell(h3_index)

        if not h3_index_is_valid:
            errors.append(
                ValidationError(
                    code=ErrorCode.H3_INVALID_INDEX,
                    message="h3_index is not a valid H3 cell index.",
                    path="/h3_index",
                    validator="h3.is_valid_cell",
                    layer="semantic",
                )
            )

        parent = document.get("h3_parent_res7")
        if parent is not None:
            if not h3.is_valid_cell(parent):
                errors.append(
                    ValidationError(
                        code=ErrorCode.H3_INVALID_PARENT_INDEX,
                        message="h3_parent_res7 is not a valid H3 cell index.",
                        path="/h3_parent_res7",
                        validator="h3.is_valid_cell",
                        layer="semantic",
                    )
                )
            elif h3_index_is_valid:
                expected_parent = h3.cell_to_parent(h3_index, 7)
                if parent != expected_parent:
                    errors.append(
                        ValidationError(
                            code=ErrorCode.H3_PARENT_MISMATCH,
                            message=(
                                "h3_parent_res7 is not the resolution-7 parent "
                                "of h3_index."
                            ),
                            path="/h3_parent_res7",
                            validator="h3.cell_to_parent",
                            layer="semantic",
                        )
                    )

        seen_scenario_ids: set[str] = set()
        for index, scenario in enumerate(document["rotation_scenarios"]):
            scenario_id = scenario["id"]
            if scenario_id in seen_scenario_ids:
                errors.append(
                    ValidationError(
                        code=ErrorCode.DUPLICATE_SCENARIO_ID,
                        message=(
                            f"Rotation scenario id '{scenario_id}' is duplicated; "
                            "scenario ids must be unique."
                        ),
                        path=f"/rotation_scenarios/{index}/id",
                        validator="semantic.unique_scenario_ids",
                        layer="semantic",
                    )
                )
            else:
                seen_scenario_ids.add(scenario_id)

        return errors


def validate_contract(
    payload: Mapping[str, Any] | str,
    *,
    schema_path: str | Path | None = None,
    enable_provisional_semantics: bool = False,
) -> ValidationResult:
    """Validate one contract payload using the provisional schema.

    This convenience function creates a :class:`ContractValidator` per call. For
    batch or pipeline use, instantiate the validator once and reuse it.

    Args:
        payload: A mapping or JSON string.
        schema_path: Optional explicit schema path.
        enable_provisional_semantics: Enable the unratified definitional semantic
            checks. Defaults to False.

    Returns:
        A deterministic :class:`ValidationResult`.

    Raises:
        SchemaConfigurationError: If the schema cannot be loaded or is invalid.
    """

    validator = ContractValidator(
        schema_path,
        enable_provisional_semantics=enable_provisional_semantics,
    )
    return validator.validate(payload)
