# tests

Shared test suite. Run with:

```powershell
.venv\Scripts\python.exe -m pytest tests/ -v
```

## Layout

- `tests/` — automated pytest tests (currently package marker only).
- `tests/manual/` — exploratory scripts that are **not** collected as pytest
  tests. `test_h3_smoke.py` (moved from the repository root in Task 0) lives here.

## Rules

- Tests must not require Google Earth Engine credentials or network access.
- Use fixtures from `data/mock/` or the synthetic artifacts in
  `external/ariefs_workresult/`.
- A test that asserts values from the synthetic H3 GeoJSON must say so in its
  name or docstring.
