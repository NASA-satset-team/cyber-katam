# CYBER-KATAM Contract Governance

This document governs the shared `grid_cell_contract.json` interface used across all CYBER-KATAM modules.

## Shared Interface

The `grid_cell_contract.json` is a shared interface consumed by:
- Frontend React/Next.js (Rafi)
- WebGL Deck.gl (Rifaldi)
- AI Core optimization and XAI modules

Any changes to this file must be agreed upon by all contributor teams before merging.

## Change Approval Process

All changes to `grid_cell_contract.json` must follow this process:

1. **Proposal**: Contributor submits a change proposal describing the modification
2. **Discussion**: All teams (Arya, Arief, Aqila, Rifaldi, Rafi) review the proposal
3. **Consensus**: Changes require agreement across teams, especially:
   - Field names
   - Data types
   - Units
   - Required/optional flags
   - Enum values
   - Nested structures

4. **Implementation**: Arya coordinates the contract ratification and updates all engine integrations
5. **Documentation**: Update this document and `CONTRIBUTING.md` if needed

## Areas Requiring Coordination

The following must be discussed before any contract change is merged:

### Field Names
- Current: `HLS_BSI` vs `MBSI` naming discrepancy
- Proposed changes must maintain backward compatibility or require explicit migration plan

### Data Types
- Current numeric types (float, int) and string enums
- Changes must not break JSON serialization/deserialization

### Units
- Physical indicators must specify units (e.g., `LST_anomaly` in Celsius)
- Contract must be consistent with engine input/output specifications

### Required/Optional Fields
- Mark fields as `required` or `optional` in the contract schema
- Removing a required field breaks all consumers

### Enum Values
- Any enum values must be agreed upon across teams
- New enum values must not conflict with existing values

### Nested Structures
- `physical_indicators`, `operational_flags`, `rotation_scenarios`, `fiscal_metrics`, `xai_decision_block`
- Changes to nested object structure must be backward-compatible

## Arya's Responsibility

Arya is responsible for:
- Coordinating contract ratification across all contributor teams
- Maintaining the contract schema specification
- Updating all engine integrations (`pvrs_engine.py`, `bf_ehsi_engine.py`, `fiscal_actuarial.py`) when the contract changes
- Ensuring the `build_grid_cell_contract_json()` function produces valid output per the agreed schema

## Current Contract Version

- `contract_version: "1.0"` (as seen in `grid_cell_contract_sample.json`)
- Specified by the `build_grid_cell_contract_json()` function in `fiscal_actuarial.py`

## Pending Resolutions

- MBSI vs HLS_BSI field name consistency
- LST threshold conventions across PVRS and BF-EHSI modules
- Finalization of field units and data types