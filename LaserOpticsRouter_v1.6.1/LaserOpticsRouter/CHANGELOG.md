# Changelog

## 1.6.1 — 2026-09-28

First public release of LaserOpticsRouter. The version number continues the
pre-publication development series; its regression history remains in
[TESTING.md](TESTING.md).

- Visual step editing, useful presets, direct commands, draft undo/recovery,
  and navigable XY/XZ/YZ optical schematics with matching SVG exports.
- Common lenses, mirrors, OAPs, splitters, polarization-reference prisms,
  waveplates, ND/tweaker plates and configurable generic placeholders.
- Reusable CAD defaults with calibrated placement, planning placeholders,
  individual-part inspection, sequential builds and source-part safeguards.
- Saved routes and endpoint continuation, connected loss/GDD/glass budgets,
  selected-path highlighting and CSV/document exports.
- Concave OAP symbols face the beam. The automatic `p100` starter opens a
  replacement picker; ordinary distance steps retain their Inspector. Commands
  starts expanded and preserves a user's collapse choice during editing.
- Built beam colors persist independently of connection status and palette
  visibility. Legacy clear beams receive a one-time color restoration; normal
  status scans do no material updates or geometry rebuilding.
- Apache-2.0 licensing, author attribution, GitHub-linked software citations
  and consolidated public documentation.

Native Fusion verification requirements and portable test results are recorded
in [TESTING.md](TESTING.md).
