# LaTeX Resume Preview Design

## Goal

Remove the hard dependency on LibreOffice for resume preview while preserving the existing structured resume model and Chinese typography.

## Design

- Keep `ResumeDocument` as the single source of truth.
- Add a LaTeX renderer that escapes user content and emits UTF-8 CJK-compatible XeLaTeX source.
- Prefer `xelatex`/`tectonic` when available to produce PDF and page images.
- If no TeX compiler exists, return a clear capability response and let the web client render a lightweight HTML preview instead of showing a dead error state.
- Keep DOCX export available as an optional format; this change does not silently delete existing exports.
- Education matching remains deterministic and is recalculated against the active resume whenever a match report is requested.

## Safety

User-authored text is escaped before entering LaTeX. Compiler execution uses a temporary directory, no shell, a timeout, and restricted interaction mode.

## Acceptance

1. LaTeX source can be downloaded for any resume.
2. XeLaTeX PDF preview works when a compiler is installed.
3. Missing compiler produces a non-blocking HTML preview fallback.
4. Education evidence is refreshed from current structured education entries.
