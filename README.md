# creative-tooling

Shared bus for Travis's creative-workflow projects.
- **Staged on:** Windows PC (Hermes coding agent)
- **Built/tested on:** Mac (workhorse, Adobe apps)
- **Flow:** agent branches here → commits staged work → Travis pulls on Mac → builds/tests → pushes back.

## Layout
- `adobe/` — Photoshop/Illustrator/etc panels & scripts (CEP + UXP)
- `chrome/` — Chrome MV3 extensions
- `r1/` — the 4 R1 vanilla-JS creations (mirrored from their own repos)
- `handoffs/` — HANDOFF_TO_CODEX.md escalation files

## Conventions
- Branch per task: `feat/<slug>`, `fix/<slug>`. Never work on `main` directly.
- Each chunk committed separately + verifiable.
