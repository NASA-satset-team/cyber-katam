"""Shared contract validation package for CYBER-KATAM.

The package currently exposes the provisional grid-cell contract validator. The
JSON Schema is stored at ``contracts/grid_cell_contract.schema.json`` and is
resolved relative to this package, not the current working directory.
"""

from .contract_validator import (
    DEFAULT_SCHEMA_PATH,
    ContractValidator,
    load_contract_schema,
    parse_contract_payload,
    validate_contract,
)
from .validation_errors import (
    ContractParsingError,
    ErrorCode,
    SchemaConfigurationError,
    ValidationError,
    ValidationResult,
)

__all__ = [
    "DEFAULT_SCHEMA_PATH",
    "ContractValidator",
    "ContractParsingError",
    "ErrorCode",
    "SchemaConfigurationError",
    "ValidationError",
    "ValidationResult",
    "load_contract_schema",
    "parse_contract_payload",
    "validate_contract",
]
