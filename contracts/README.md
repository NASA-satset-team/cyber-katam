# Shared contracts

This folder is reserved for the **ratified** machine-readable contracts that every
module consumes: JSON Schema files, enum registries, and versioned examples.

## Current status (Task 0)

No official `grid_cell_contract.json` schema exists yet.

The only sample available is:

- `external/aryas_workresult/grid_cell_contract_sample.json`

That file is **not a valid JSON document**. It is a UTF-16 console-log dump that
contains a fiscal report, a Pareto line, and a JSON payload in the middle. It can
therefore be used as a *field reference only*, not as a schema or as a validator
fixture. See `docs/project_file_inventory.md` (KI-05).

`src/contracts/` holds the Python package that will host validators. The schema
itself belongs here once the team ratifies it.

## Rules

1. Field names, types, units, required flags, and enum values are shared API.
2. Changes require review from Arya (contract owner), Aqila (AI Core), Rifaldi
   (GIS), and Rafi (frontend). See `docs/contract_governance.md`.
3. Add new versions as new files (`grid_cell_contract.v1.1.schema.json`); do not
   silently mutate a released schema.
4. Every schema change needs a valid example and a failing-example test.

## Known open contract issues

- `HLS_BSI` (contract) vs `MBSI` (engine) naming discrepancy.
- PVRS and BF-EHSI use different LST threshold conventions.
- `contract_version` is `"1.0"` but no formal v1.0 schema has been ratified.
- Physical indicator values in Arya's contract builder are hardcoded placeholders
  (KI-06); they must become inputs before the contract is used for real output.
