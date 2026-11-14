# Pull Request

## Summary

<!-- What changed, in 1–3 sentences? -->

## Area

- [ ] `data-pipeline/` (Arief)
- [ ] `physics-engines/` (Arya)
- [ ] `src/` / AI Core (Aqila)
- [ ] `gis-viewer/` (Rifaldi)
- [ ] `web-app/` (Rafi)
- [ ] `contracts/` (shared contract — requires review)
- [ ] `docs/`
- [ ] `tests/`

## Type of change

- [ ] Feature
- [ ] Bug fix
- [ ] Contract change (breaking or additive)
- [ ] Data extraction / dataset update
- [ ] Documentation only
- [ ] Refactor (no behaviour change)

## Data and provenance

- [ ] This PR does **not** add real NASA credentials, `.env` files, or private keys.
- [ ] Synthetic or mock data added by this PR is explicitly labelled synthetic.
- [ ] Any new dataset records collection ID, version, date range, units, resolution,
      QA filtering, and extraction script.
- [ ] No raw large satellite file is committed to Git.

## Shared contract impact

- [ ] No change to `grid_cell_contract.json` fields, units, types, or enums.
- [ ] If changed: a versioned schema, valid example, migration note, and review
      from Arya + Aqila + Rifaldi + Rafi are included.

## Testing

<!-- Exact commands and results, e.g.:
.venv\Scripts\python.exe -m pytest tests/ -v
-->

```text
paste commands and result summary here
```

## Checklist

- [ ] Branch follows the naming convention (`feature/<member>-...`, `fix/...`, `docs/...`).
- [ ] I ran the test suite locally.
- [ ] I did not edit or delete another member's received source without documenting it.
- [ ] Documentation updated (`README.md`, `docs/`, inventory) where behaviour changed.
- [ ] No secrets or absolute personal paths added.
