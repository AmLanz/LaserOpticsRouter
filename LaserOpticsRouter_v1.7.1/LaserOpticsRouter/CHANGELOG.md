# Changelog

## 1.7.1 — 2026-10-01

- Correct assigned-component roll: X follows the optical normal and Z follows
  positive Hybrid assembly Z, projected onto tilted surfaces. A vertical X has
  a deterministic fallback. Preview and Build account for whole-route rotation.
- Restore explicit fixed source-axis Rx/Ry/Rz and assembly-axis ΔX/ΔY/ΔZ
  corrections in Defaults and Inspector. New fields are pinned and CSV-persisted;
  former Z-normal calibration remains ignored. Optical modifiers do not impose
  automatic CAD roll. The f spin remains about the target surface normal.
- Place cylinders directly below lenses and gratings just above generic optics.
- Replacement deletes the old route before reacquiring final body handles and
  reasserting appearance colors. Successful builds always activate the root.
  Native Fusion appearance acceptance remains outstanding.
- Spectral samples now intersect fixed surfaces and continue through mirrors,
  lenses, cylinders, OAPs, splitters, prisms, resets and subsequent gratings.
  Reflectors and gratings use fixed geometric normals; focusing is paraxial.
  Samples retain individual lengths, envelopes and budgets. No pulse width,
  material phase or automatic grating GDD calculation is added.
- Central end/port packets retain spectral bundles for copy/paste, Previous line,
  transformed routes and CSV cloning. Later gratings use existing samples.
- Coplanar return grating encounters reuse the first physical part by default;
  inspection of a return encounter uses that original placement.
- Stabilize second-moment propagation through nearly exact geometric foci.
- Add the requested 3D OAP/cylindrical/Wollaston route and four-pass grating
  compressor examples with a vertically separated roof-mirror return.

## 1.7.0 — 2026-10-01

- Searchable component chooser lists inserted reference occurrences, including
  hidden ones, and excludes generated routes. Prepare each component in its
  own file: origin at the beam hit, X normal to the reference surface.
- **Breaking CAD change:** all assignments, including rebuilt saved routes,
  use X-normal. Former datum points, offsets and rotation calibration are ignored
  and their controls removed. There is no saved-route Z convention. The `f`
  prefix now rotates CAD around the prepared X normal.
- Cylindrical lenses (`cyl100h`, `cyl100v`, signed f), transported elliptical
  paraxial envelopes, H/V and principal diameters, and faceted CAD envelope skins.
- Reflection gratings (`gr600a30m1h`) with anamorphic width and central,
  sideband or sampled Gaussian wavelength modes. Spectral fans propagate in
  free space up to the next optic; their endpoints support independent routing.
  Efficiency and GDD remain manual; no full polychromatic train is claimed.
- Virtual reset plates: `resetd5finf` for 5 mm collimated; `resetd5f50` for
  5 mm focused 50 mm ahead. Preserve the chief ray and accumulated budgets.
- Numeric Inspector fields survive asynchronous analysis without being replaced
  during decimal/sign/exponent entry. Incomplete values cannot build a stale plan.
- LOR3 endpoint packets retain elliptical/spectral state; LOR1/LOR2 still load.
  CSV, SVG and document exports include the new shapes and spectral metadata.
- Ordinary routes retain their existing scalar optics. Solid preview now uses
  the chosen optic opacity consistently with Build. New example CSVs and guides
  explain model limits and source-file preparation.

Portable verification and outstanding desktop Fusion checks are in
[TESTING.md](TESTING.md).


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
