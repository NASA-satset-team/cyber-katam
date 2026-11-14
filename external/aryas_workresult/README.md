# Arya's received work — provenance

Source: `aryas_workresult-20261111T135332Z-1-001.zip` (received 2026-11-11).

The files below were already copied into this folder before Task 0. They are kept
byte-identical to the received versions.

| File | SHA-256 prefix | Role |
|---|---|---|
| `pvrs_engine.py` | `F95920BA9815C5DF` | PVRS + native-support inversion + gates |
| `bf_ehsi_engine.py` | `FC81DF877B00B946` | BF-EHSI + MBSI + risk integral |
| `build_water_balance_banyumas.py` | `7A98FBC2AB931CE9` | 90-day water balance + Excel |
| `fiscal_actuarial.py` | `0359249BE5687E36` | N ledger + fiscal/actuarial + Pareto |
| `grid_cell_contract_sample.json` | `7DC3CB125F1117A9` | Contract field reference (not valid JSON) |
| `water_balance_banyumas.xlsx` | `6AC72A0C6D01ADF1` | Excel output of the simulator |

## Verification performed in Task 0

- All four Python files parse with `ast.parse`.
- All four import successfully under Python 3.12.10 with the core requirements.
- Each `__main__` demo runs in a scratch directory without modifying the
  received outputs.

## Warnings

- Demo inputs are synthetic, not observations.
- `build_grid_cell_contract_json()` hardcodes the physical indicators.
- `grid_cell_contract_sample.json` is a UTF-16 console log, not a JSON document.
- Water-balance and fiscal parameters need agronomic/fiscal validation.
- Do not copy formulas into AI Core; import these modules or wrap them.

Full details: `docs/project_file_inventory.md`.
