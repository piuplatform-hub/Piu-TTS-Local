# Handoff — integrating docs into Windows Antigravity workspace

**Important:** This package was authored separately from the user's PC and has not modified the actual Antigravity workspace. Treat it as a proposed patch, not evidence of successful merge.

1. Inspect actual repository git state and `docs/` content read-only; protect user-created and uncommitted changes. Confirm intended root (`D:\C\Dev\du an\TTS` in Gemini's R1 report, **verify before using**).
2. Take a safe git branch/commit or non-destructive backup of existing docs. Compare R1.1 Markdown to current repo files with a diff; never overwrite changed files blindly.
3. Copy/merge the **contents** of this bundle's `docs/` folder into `<repo-root>/docs/`. Keep `docs/archive/r1-original` read-only as historical reference. If the PC has newer versions, reconcile semantically rather than clobber.
4. Audit relative links, headings, decision statuses, duplicated contradictory APIs/SQL and file encodings. Keep design proposals marked proposed until owner approves.
5. Record a documentation-only commit, with commit hash, changed files and diff summary. **Do not** install packages, download models, modify Windows settings or start services.
6. Report any conflicts and open decisions. Wait for separate owner authorization before Phase 1 source implementation.
