# Verification record — 1.7.1

**308 Python tests and 120 JavaScript tests pass.** Tests use the real portable
planner plus Fusion API and DOM/bridge doubles. They do not run Fusion's native
kernel, embedded browser, transaction system or Windows/macOS UI.

Run from this add-in directory:

```sh
python -m unittest discover -s tests -q
node --test tests/*.cjs
python -m compileall -q .
node --check editor.js
node --check schematic.js
node --check studio.js
node --check palette.js
```

## New regression coverage

- Cylindrical h/v power, signed focal lengths, line foci, finite Gaussian
  waists, crossed cylinders, spherical-lens compatibility and 3D frame transport.
- Second-moment positivity, seeded routes through folds/foci, inverse rigid
  transforms and roundoff at exact geometric line foci.
- Reflection-grating equation, Littrow retroreflection, specular m=0,
  opposite orders, anamorphic width and rejection of nonpropagating orders.
- Central/sideband/Gaussian spectral samples, bandwidth validation, wavelength
  dependent Gaussian propagation and relative weights through fixed surfaces.
- Two-grating angular-dispersion cancellation and four-encounter spatial
  recombination, with independent wavelength path lengths, finite envelopes,
  and a 10 mm separated roof-mirror return in geometric/Gaussian modes.
- Decentered spectral lens power, cylindrical/3D mirror trains, grating
  resampling avoidance, both splitter/prism ports, displacer combination and
  absence of fictitious spectral loss for an invalid combiner.
- Reset diameter and signed focus distance, geometric collimation, Gaussian
  waist solving, impossible input rejection, astigmatism clearing and preservation
  of chief ray, color, wavelength and accumulated reference budgets.
- X-normal component origins for all optic families; legacy calibration ignored;
  assembly-upright Z, projected-up vertical tilts and right-handed vertical fallback.
- Fixed component-axis rotations, assembly-axis offsets under whole-route
  rotation, source immutability, preview/build placement equality and a target-X
  CAD flip after source correction. Staged/default numeric corrections persist.
- Replacement deletes the old route before assigning final-body colors, reapplies
  existing appearance color properties and always activates the design root.
- Four grating encounters produce two physical parts; selected return-part
  inspection uses the original physical part. Reuse can be disabled.
- Searchable component choices include hidden references and exclude generated
  routes/children. Confirmed selection is resolved against the current design.
- LOR1/LOR2/LOR3 packets, ordinary scalar fingerprints, CSV round-trips,
  spectral-bundle cloning/rebinding, transformed bundle geometry, Previous-line
  and snapshot continuation, and malformed/oversized bundle rejection.
- Closed ellipse skins: edge incidence, positive volume, line-focus tolerance,
  adaptive sampling and bounded geometry. This validates mesh construction,
  not native BRep kernel acceptance.
- Python/JavaScript round-trips for new syntax; physical-part identity retained
  through cylinder plane/grating angle changes and reset on focal/density changes.
- Numeric input identity and raw decimal/sign/exponent spelling during analysis;
  incomplete entries do not overwrite prior values or build stale geometry.
- Component filtering, escaped names, staged defaults, local assignment and
  cancellation; independent spatial/spectral modes; finite/collimated reset controls.

## Existing behavior retained

The prior lens, mirror, OAP, splitter, prism/displacer, passive-plate and generic
optic regressions remain. Tests cover route identity, draft undo/recovery,
connected budgets, source refresh, CSV/document export, source immutability,
nested placement, preview/build transforms, transaction failure boundaries,
clipboard control flow, schematic navigation and persistent beam appearances.
Tests of former calibration placement were updated to the explicitly requested
X-normal convention; old Z-normal placement is intentionally not preserved.

The default geometric route `p100 l50 p25 r90 p75` still ends at (125, 75, 0) mm,
has 200 mm geometric length and a 5 mm endpoint diameter. Routes without new
optics retain their scalar calculations and circular CAD geometry.

Python compilation, JavaScript syntax and packaged local references are checked.
The new example schematic SVGs are rendered and visually inspected separately.
No desktop Fusion or embedded-browser click-through pass is claimed.

## Native acceptance checks still required

1. Install the complete folder in desktop Fusion, restart, and verify **1.7.1**.
   Preview/build the ordinary route above, then Build again. There must be one
   current route, with original colors and the design root active. Check
   appearance, save/reopen and Undo/Redo in both selection-protection modes.
2. Prepare an asymmetric mirror in its own file: origin on the front-surface
   hit, X normal toward the beam, backing toward −X. Insert it linked, hide the
   reference occurrence, and select it by assembly path. Compare its axes and
   surface alignment in single-part preview, full preview and Build.
3. Repeat with a nested source, a moved/rotated route, spherical/cylindrical lens,
   grating and both OAP parent-axis orientations. Horizontal surfaces must keep
   Z parallel to positive assembly Z; r90v45/r90v90 must use projected assembly
   up. Test explicit Rx, Rz = −90° for an original Y normal, assembly offsets,
   and the `f` CAD spin. Compare one-part/full Preview and Build.
   Verify source geometry, placement, visibility and external links are unchanged.
4. Open a legacy route with nonzero reference/offset/rotation entries. Confirm
   old calibration is ignored and rebuilt CAD uses X-normal. New correction
   controls start at zero and retain explicitly saved 1.7.1 values. Prepare
   the source file before replacing important existing geometry.
5. Preview/build `cyl100h p100 p50`, its vertical/negative variants and crossed
   cylinders. Verify line foci, H/V diameters and faceted solids; repeat with
   Gaussian source, 3D folds and route transforms. Very small displayed radii
   use the documented tolerance floor; statistics must remain unchanged.
6. Import each grating and compressor example. Check direction, grooves,
   spectral weights and copyable endpoints in all projections. Confirm two
   physical gratings for the compressor's four encounters and a recombined
   output at (0,0,10) mm along −X. Add a lens/mirror after propagation: every
   sample must continue through it. Copy the central end into a new route and
   verify all samples survive. Invalid orders must report useful errors.
7. Build `l50 p30 resetd5f50 p50 resetd5finf p100`. Check unchanged chief ray,
   focus at 50 mm after the first reset, then 5 mm geometric collimation. Repeat
   with Gaussian input and an impossible small-diameter/far-waist request.
8. Type decimals, a leading minus and exponent notation into a local generic
   element's depth, diameter and GDD fields during live analysis. Focus/caret
   must remain stable; blank/invalid values block Preview and Build. Repeat for
   cylinder focal length, grating incidence and reset focus fields.
9. Save/reopen, copy/paste LOR3 endpoints, export/reimport CSV and export all
   document paths after moving a route. Check H/V widths, λ/weights, references,
   three SVG projections and the distinction between route-local and design axes.
10. Check linked source updates, selection protection, cancellation during a
    multi-batch build, single Undo/Redo, replacement failure and previous-route
    preservation in direct/parametric and Hybrid/converted documents.
11. Check readable palette/modal layouts at narrow/wide widths on Windows and
    macOS, keyboard search/cancel, clipboard and file dialogs. Confirm numeric
    behavior in Fusion's embedded browser as well as the portable DOM tests.

Autodesk Fusion is unavailable in this environment. In particular, the new
faceted BRep construction and cylindrical/grating placeholders require native
acceptance. A single Fusion call cannot be interrupted by the Cancel callback.
Selection protection is a safeguard, not an absolute geometry edit lock.

The earlier 1.2.1 build was reported successful by the user. That is historical
evidence, not native validation of this release. Prior release notes remain in
[CHANGELOG.md](CHANGELOG.md). If a native failure occurs, include the minimal
route, exact Fusion version and LaserOpticsRouter-build.log with private paths
removed.
