# CYBER-KATAM setup

- No application credentials are needed by the active exploration MVP.
- Bootstrap verifies the React/Vite app on the supervised port, not the original
  directory server. Python 3.12, Node 22, and pnpm 10.11.0 are pinned.
- Production deployment uses Vite's static `dist/` output and the static adapter.
- Deploy-preview verification returns the previously recorded `skipped` state
  even after a valid static preview script is added. The attempted script was
  removed and skip was preserved; deploy-preview has **not** passed. Production
  deployment verification and the supervised development preview are separate.
- The v0.2 schematic map uses local geometry and an explicitly illustrative
  local photo, so no tile API or map credentials are needed. Only Google Fonts
  use an external runtime network request; system sans-serif is the fallback.
  The sandbox Chromium trust store can reject third-party HTTPS certificates.
  Application TLS and origin checks are not disabled.
- No verified NASA observations, calibrated predictions, or authorized field
  recommendations are connected. This is not an environment-secret problem.
