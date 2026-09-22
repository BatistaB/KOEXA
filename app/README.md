# app/

Home of the AOED interactive application.

`web/` — React + TypeScript + Vite frontend (Milestone 7). AFED's
interface/UX patterns remain the design benchmark (see
`docs/decisions/0002-afed-audit.md`), but the implementation is
JS-native, not the MIT-licensed AFED Shiny code — see
`docs/decisions/0005-milestone7-frontend-stack.md` for why, and
`web/README.md` for how to run it. Started ahead of Milestone 7's formal
gate as a UX spike; now reads real data exported from
`database/atlas.duckdb` (`atlas app export-web`, part of the standardized
`atlas refresh` pipeline — see the repo root CLI and `web/README.md`),
though Milestones 1-6 (acquisition, QC, database) still aren't formally
complete/validated.
