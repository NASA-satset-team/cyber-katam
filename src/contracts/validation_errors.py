"""Error types and validation result objects for grid-cell contracts.

This module deliberately keeps error definitions separate from validation logic so
that parsing, schema, semantic, and configuration failures can be distinguished
by callers and by automated tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal

ErrorLayer = Literal["parsing", "schema", "semantic", "configuration"]


class ErrorCode:
    """Stable error-code strings returned by the contract validator."""

    # Parsing-layer failures.
    EMPTY_INPUT = "EMPTY_INPUT"
    INVALID_JSON = "INVALID_JSON"
    NON_FINITE_NUMBER = "NON_FINITE_NUMBER"
    ROOT_NOT_OBJECT = "ROOT_NOT_OBJECT"
    UNSUPPORTED_INPUT_TYPE = "UNSUPPORTED_INPUT_TYPE"
    INVALID_OBJECT_KEY = "INVALID_OBJECT_KEY"

    # Structural (JSON Schema) failures.
    REQUIRED_FIELD = "REQUIRED_FIELD"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    ENUM_MISMATCH = "ENUM_MISMATCH"
    CONST_MISMATCH = "CONST_MISMATCH"
    BELOW_MINIMUM = "BELOW_MINIMUM"
    ABOVE_MAXIMUM = "ABOVE_MAXIMUM"
    BELOW_EXCLUSIVE_MINIMUM = "BELOW_EXCLUSIVE_MINIMUM"
    ABOVE_EXCLUSIVE_MAXIMUM = "ABOVE_EXCLUSIVE_MAXIMUM"
    STRING_TOO_SHORT = "STRING_TOO_SHORT"
    STRING_TOO_LONG = "STRING_TOO_LONG"
    STRING_PATTERN_MISMATCH = "STRING_PATTERN_MISMATCH"
    ADDITIONAL_PROPERTY = "ADDITIONAL_PROPERTY"
    ARRAY_TOO_SHORT = "ARRAY_TOO_SHORT"
    ARRAY_TOO_LONG = "ARRAY_TOO_LONG"
    SCHEMA_VALIDATION_ERROR = "SCHEMA_VALIDATION_ERROR"

    # Semantic failures (only emitted when the caller opts in to provisional rules).
    H3_INVALID_INDEX = "H3_INVALID_INDEX"
    H3_INVALID_PARENT_INDEX = "H3_INVALID_PARENT_INDEX"
    H3_PARENT_MISMATCH = "H3_PARENT_MISMATCH"
    DUPLICATE_SCENARIO_ID = "DUPLICATE_SCENARIO_ID"

    # Configuration failures (raised, not returned as a normal result).
    SCHEMA_LOAD_ERROR = "SCHEMA_LOAD_ERROR"
    SCHEMA_PARSE_ERROR = "SCHEMA_PARSE_ERROR"
    SCHEMA_NOT_OBJECT = "SCHEMA_NOT_OBJECT"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    SCHEMA_NON_FINITE_NUMBER = "SCHEMA_NON_FINITE_NUMBER"


@dataclass(frozen=True, slots=True)
class ValidationError:
    """One deterministic, machine-readable validation failure.

    Attributes:
        code: Stable error code from :class:`ErrorCode`.
        message: Human-readable explanation that does not dump the whole payload.
        path: JSON Pointer (RFC 6901) to the offending field, or ``""`` for root.
        validator: Layer or rule that produced the error, such as ``"type"``,
            ``"json_parser"``, or ``"h3.is_valid_cell"``.
        layer: High-level failure category.
    """

    code: str
    message: str
    path: str
    validator: str
    layer: ErrorLayer = "schema"

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-serialisable representation of this error."""
        return {
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "validator": self.validator,
            "layer": self.layer,
        }


def _pointer_sort_key(path: str) -> tuple[tuple[int, object], ...]:
    """Build a natural sort key from a JSON Pointer path.

    Numeric array segments sort numerically so that ``/items/2`` precedes
    ``/items/10``. The key is used to make error ordering deterministic.
    """

    if path in ("", "/"):
        return ()
    segments = path.lstrip("/").split("/")
    key: list[tuple[int, object]] = []
    for segment in segments:
        segment = segment.replace("~1", "/").replace("~0", "~")
        if segment.isdigit():
            key.append((0, int(segment)))
        else:
            key.append((1, segment))
    return tuple(key)


def _error_sort_key(error: ValidationError) -> tuple[object, ...]:
    """Return the deterministic ordering key for a validation error."""

    return (
        _pointer_sort_key(error.path),
        error.layer,
        error.code,
        error.validator,
        error.message,
    )


@dataclass(slots=True)
class ValidationResult:
    """Consistent result returned for parsing, schema, and semantic failures.

    Attributes:
        is_valid: True only when no errors were produced.
        errors: Ordered validation errors.
        error_count: Number of entries in ``errors``.
    """

    is_valid: bool
    errors: list[ValidationError]
    error_count: int

    @classmethod
    def build(cls, errors: Iterable[ValidationError] = ()) -> "ValidationResult":
        """Create a result and order all errors deterministically by path."""

        ordered = sorted(errors, key=_error_sort_key)
        return cls(
            is_valid=not ordered,
            errors=ordered,
            error_count=len(ordered),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of the result."""

        return {
            "is_valid": self.is_valid,
            "errors": [error.to_dict() for error in self.errors],
            "error_count": self.error_count,
        }


class ContractParsingError(ValueError):
    """Raised when a payload cannot be parsed as a strict JSON object.

    The exception carries all parsing-layer errors found so callers can inspect
    every problem without losing the distinction between parsing and schema
    validation. :meth:`ContractValidator.validate` converts these into a normal
    validation result.
    """

    def __init__(self, errors: list[ValidationError]) -> None:
        if not errors:
            raise ValueError("ContractParsingError requires at least one error.")
        self.errors = errors
        super().__init__(errors[0].message)

    def to_result(self) -> ValidationResult:
        """Return a validation result containing the parsing errors."""

        return ValidationResult.build(self.errors)


class SchemaConfigurationError(RuntimeError):
    """Raised when the JSON Schema cannot be loaded or is itself invalid.

    This is a configuration/programming failure, not an invalid contract payload.
    Keeping it distinct prevents a broken schema from being reported as bad input
    data and prevents callers from caching a false "payload is invalid" result.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str = ErrorCode.SCHEMA_LOAD_ERROR,
        path: str = "",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path
        self.validator = "schema_loader"
        self.layer: ErrorLayer = "configuration"

    def to_error(self) -> ValidationError:
        """Convert this exception into a :class:`ValidationError`."""

        return ValidationError(
            code=self.code,
            message=self.message,
            path=self.path,
            validator=self.validator,
            layer=self.layer,
        )
