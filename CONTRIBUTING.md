# CYBER-KATAM Contributing Guidelines

This repository is one shared monorepo for five contributors. `main` must always
stay reviewable, runnable, and honest about data provenance.

## 1. Branch naming

| Prefix | Owner / purpose |
|---|---|
| `feature/arya-...` | Physics and fiscal engines (Arya) |
| `feature/arief-...` | Satellite pipeline and H3 harmonization (Arief) |
| `feature/aqila-...` | AI Core, contracts, optimization, XAI, uncertainty, tests (Aqila) |
| `feature/rifaldi-...` | GIS / WebGL / Deck.gl viewer (Rifaldi) |
| `feature/rafi-...` | Frontend application (Rafi) |
| `fix/...` | Bug fixes (any member) |
| `docs/...` | Documentation only (any member) |

Use short-lived branches. Do not commit directly to `main`.

## 2. Standard workflow

```powershell
# 1. Clone once
git clone <REPOSITORY_URL> cyberkatam
cd cyberkatam

# 2. Always start from an up-to-date main
git checkout main
git pull origin main

# 3. Create your branch
git checkout -b feature/aqila-contract-validator

# 4. Work in small commits
git add <files>
git commit -m "Add contract validator skeleton"

# 5. Push your branch
git push -u origin feature/aqila-contract-validator
```

Then open a Pull Request into `main` and fill in the PR template.

## 3. Commit messages

- Imperative mood: `Add MBSI field`, not `Added MBSI field`.
- Subject under 72 characters.
- Reference issues: `Closes #123`.
- Keep data commits separate from code commits when practical.

## 4. Pull request rules

1. `main` only receives reviewed, tested changes.
2. At least one reviewer from another workstream is required.
3. **Any change to `contracts/` or the shared `grid_cell_contract.json` requires
   explicit review from Arya (contract owner), Aqila (AI Core), Rifaldi (GIS), and
   Rafi (frontend).**
4. CI/tests must pass before merge.
5. Squash-merge or merge-commit is allowed; do not force-push `main`.
6. Never force-push another member's branch.

## 5. Code review expectations

- Contract field names, types, and units stay consistent with
  `docs/contract_governance.md`.
- No breaking change to a shared interface without a migration note.
- Imports must work in `.venv` with `requirements.txt` installed.
- New numerical code needs at least one deterministic unit test.
- Reviewers check that formulas were not duplicated from
  `external/aryas_workresult/`; reuse or wrap them instead.

## 6. Data integrity rules (non-negotiable)

- Never call synthetic data a NASA observation.
- Never fabricate H3 indexes, satellite values, or climatology baselines.
- Every dataset artifact must record collection ID, version, units, resolution,
  date range, QA filtering, and extraction script.
- A script is not "complete" because it prints a success line. It is complete
  when the exported output exists, was opened, and its schema/units were checked.
- H3 resolution 9 is much finer than SMAP (~9 km) and GPM (~0.1°) pixels.
  Do not claim one independent satellite observation per H3 cell. Preserve the
  native resolution and document the aggregation/interpolation method.
- Do not commit `.env`, Earth Engine credentials, service-account JSON, tokens,
  or private keys.

## 7. Shared contract changes

Discuss before coding. Arya coordinates ratification.

- Do not rename fields without consensus.
- Do not change a data type or unit without agreement.
- Do not remove a required field without a replacement and migration path.
- Update `docs/contract_governance.md` and `contracts/` in the same PR.
- Current open issues: `HLS_BSI` vs `MBSI`, LST threshold conventions, and the
  absence of a ratified v1.0 JSON Schema.

## 8. Running the environment and tests

```powershell
# One-time environment setup (Python 3.12)
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Tests
python -m pytest tests/ -v
```

Optional geospatial/NASA packages are separate:

```powershell
python -m pip install -r requirements-optional.txt
```

Record exact versions when you add a dependency, and update `requirements.txt`
in the same PR.

## 9. Keeping your branch current

```powershell
git checkout main
git pull origin main
git checkout feature/your-branch
git merge main          # or: git rebase main
# resolve conflicts, run tests, then push
```

Do not rebase or force-push a branch that someone else has already reviewed
without telling them.

## 10. Definition of done

- Code works on Python 3.12 with the documented requirements.
- Tests pass locally.
- Docs and inventory updated.
- No secrets, no raw large data, no fabricated observations.
- PR template completed and reviewed.
