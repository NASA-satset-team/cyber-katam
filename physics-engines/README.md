# physics-engines

Owner: **Arya** — PVRS, BF-EHSI, water balance, nitrogen ledger, and fiscal-actuarial engines.

## Current status (Task 0)

Arya's reference implementations are preserved unchanged in:

`external/aryas_workresult/`

They import successfully with the Task 0 core environment and each `__main__`
demo runs in a scratch directory. Do **not** copy their formulas into AI Core
modules; import or wrap them instead.

| File | Role |
|---|---|
| `pvrs_engine.py` | PVRS, native-support inversion, Lipschitz error bound, gates 1–2 |
| `bf_ehsi_engine.py` | MBSI, bare fraction, desiccation cracks, BF-EHSI, risk integral |
| `build_water_balance_banyumas.py` | 90-day root-zone water balance + Excel export |
| `fiscal_actuarial.py` | Three-tier N ledger, APBN/AUTP clearing, Pareto solver, contract builder |

## Warnings

- The demo inputs are synthetic, not observations.
- The water-balance series is generated with `np.random` yet columns are labelled
  "GPM IMERG" and "NASA POWER" (KI-09).
- `build_grid_cell_contract_json()` hardcodes physical indicators (KI-06).
- Agronomic, fiscal, and nitrogen parameters need agronomic validation (KI-10).
