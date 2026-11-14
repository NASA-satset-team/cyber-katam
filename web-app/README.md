# web-app

Owner: **Rafi** — React/Next.js frontend application.

## Current status

A React/Vite exploration MVP lives in `src/`, with the package manifest and
Vite entry point at repository root. See `docs/mvp.md` for flows, commands,
provenance rules, and remaining operational blockers.

Versi 0.2 memiliki tiga tampilan berbahasa Indonesia: dasbor geospasial analis,
mode Petani/PPL, dan sertifikat audit empat gerbang. Simulasi, verifikasi peran,
serta tanda tangan bersifat lokal dalam memori. Ekspor PNG benar-benar dibuat
di peramban dan diperiksa berukuran di bawah 150 KB.

This is not an operational recommendation system. No verified NASA exports
are connected. All planning and verification selections are session-only.

Contract consumption rules are defined in `docs/contract_governance.md` and
`contracts/README.md`. Do not build against the unratified sample payload.
