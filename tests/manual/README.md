# Manual checks

These scripts are **not** pytest tests and are excluded from collection by
`conftest.py`.

- `test_h3_smoke.py` — moved here unchanged from the repository root in Task 0.
  It is a historical exploratory script that targets the h3-py v3 API
  (`h3.geo_to_h3`); under h3 v4 it falls into its exception branch and prints a
  fallback message. Kept for provenance, not as a working test.

Run a script manually with:

```powershell
.venv\Scripts\python.exe tests\manual\test_h3_smoke.py
```
