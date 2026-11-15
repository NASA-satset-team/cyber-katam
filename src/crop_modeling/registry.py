"""Crop parameter registry loader and validation.

The registry is data-only. It must not compute values or fill missing entries.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .models import (
    CropRecord,
    EvidenceStatus,
    ParameterValue,
    SourceRecord,
    UnitRecord,
)

DEFAULT_REGISTRY_PATH = Path("data/registry/crop_parameter_registry.json")


class RegistryValidationError(ValueError):
    pass


class CropRegistry:
    def __init__(
        self,
        sources: Mapping[str, SourceRecord],
        units: Mapping[str, UnitRecord],
        crops: Mapping[str, CropRecord],
        schema_version: str,
        registry_version: str,
    ) -> None:
        self.sources = dict(sources)
        self.units = dict(units)
        self.crops = dict(crops)
        self.schema_version = schema_version
        self.registry_version = registry_version

    @classmethod
    def from_file(cls, path: str | Path = DEFAULT_REGISTRY_PATH) -> "CropRegistry":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Crop registry not found: {path}")
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "CropRegistry":
        sources_raw = raw.get("sources")
        units_raw = raw.get("units")
        crops_raw = raw.get("crops")
        if not isinstance(sources_raw, list) or not isinstance(units_raw, list) or not isinstance(crops_raw, list):
            raise RegistryValidationError("Registry requires list fields: sources, units, crops")

        sources: dict[str, SourceRecord] = {}
        for item in sources_raw:
            record = SourceRecord(
                source_id=str(item["source_id"]),
                type=str(item["type"]),
                citation=str(item["citation"]),
                url=item.get("url"),
                location=item.get("location"),
                scope_note=str(item.get("scope_note", "")),
            )
            if record.source_id in sources:
                raise RegistryValidationError(f"Duplicate source_id: {record.source_id}")
            sources[record.source_id] = record

        units: dict[str, UnitRecord] = {}
        for item in units_raw:
            record = UnitRecord(
                unit_id=str(item["unit_id"]),
                symbol=str(item["symbol"]),
                dimension=str(item["dimension"]),
                description=str(item["description"]),
            )
            if record.unit_id in units:
                raise RegistryValidationError(f"Duplicate unit_id: {record.unit_id}")
            units[record.unit_id] = record

        crops: dict[str, CropRecord] = {}
        for item in crops_raw:
            crop_id = str(item["crop_id"])
            if crop_id in crops:
                raise RegistryValidationError(f"Duplicate crop_id: {crop_id}")
            parameters: dict[str, ParameterValue] = {}
            for key, p_raw in item.get("parameters", {}).items():
                status_raw = str(p_raw.get("status", "missing"))
                try:
                    status = EvidenceStatus(status_raw)
                except ValueError as exc:
                    raise RegistryValidationError(f"{crop_id}.{key}: invalid status '{status_raw}'") from exc

                unit = str(p_raw.get("unit", ""))
                if unit not in units:
                    raise RegistryValidationError(f"{crop_id}.{key}: unknown unit '{unit}'")

                value = p_raw.get("value")
                source_id = p_raw.get("source_id")
                if status is EvidenceStatus.MISSING:
                    if value is not None:
                        raise RegistryValidationError(f"{crop_id}.{key}: missing status requires value=None")
                else:
                    if value is None:
                        raise RegistryValidationError(f"{crop_id}.{key}: status '{status.value}' requires value")
                    if not source_id or source_id not in sources:
                        raise RegistryValidationError(f"{crop_id}.{key}: status '{status.value}' requires known source_id")

                parameters[key] = ParameterValue(
                    value=value,
                    unit=unit,
                    status=status,
                    source_id=source_id,
                    location=p_raw.get("location"),
                    product_basis=p_raw.get("product_basis"),
                    time_origin=p_raw.get("time_origin"),
                    required_for=tuple(p_raw.get("required_for", ())),
                    notes=str(p_raw.get("notes", "")),
                )

            crops[crop_id] = CropRecord(
                crop_id=crop_id,
                common_name=str(item["common_name"]),
                scientific_name=item.get("scientific_name"),
                variety=item.get("variety"),
                category=item.get("category"),
                region=item.get("region"),
                record_status=str(item.get("record_status", "incomplete")),
                parameters=parameters,
                identity_source_ids=tuple(item.get("identity_source_ids", ())),
            )

        return cls(
            sources=sources,
            units=units,
            crops=crops,
            schema_version=str(raw.get("schema_version", "unknown")),
            registry_version=str(raw.get("registry_version", "unknown")),
        )

    def crop(self, crop_id: str) -> CropRecord:
        if crop_id not in self.crops:
            raise KeyError(f"Unknown crop_id '{crop_id}'")
        return self.crops[crop_id]

    def value(self, crop_id: str, parameter: str) -> Any:
        return self.crop(crop_id).value(parameter)
