# data/raw

Raw NASA / third-party downloads live here **locally only**. The contents are
gitignored because raw satellite granules are large and reproducible.

Expected layout (create when extraction actually succeeds):

```text
data/raw/
├── smap/
├── ecostress/
├── gpm/
├── hls/
└── power/
```

Every extraction must record:

- exact collection ID and version,
- date range and ROI,
- source resolution,
- units,
- QA/quality filtering applied,
- extraction script path and commit,
- checksum and file size.

If a dataset has not been exported and inspected, it is **not** "done".
See `docs/nasa_data_inventory.md`.
