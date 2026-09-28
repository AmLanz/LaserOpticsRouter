# Verification record — 1.6.1

239 Python tests and 107 JavaScript tests pass. Python compilation,
JavaScript syntax, HTML identifiers and packaged local asset references are
checked. The portable tests use small Fusion/DOM doubles; they do not execute
Fusion's native BRep kernel, browser or transaction system.

Commands from the add-in directory:

```text
python -m unittest discover -s tests -q
node --test tests/*.cjs
node --check editor.js
node --check schematic.js
node --check studio.js
node --check palette.js
```

## 1.6.1 portable coverage

- OAP concavity faces the projected optical normal and its front surface meets
  the ray datum, across signed bends, underscore variants and all projections.
- Only automatically created `p100` starters open replacement; manual/confirmed
  distances open Inspector. Replacement preserves the continuation endpoint,
  supports generic shapes and undo/redo, and rejects stale targets. Cancellation
  leaves the draft unchanged; built snapshots retire the starter marker.
- Commands opens by default, retains a manual collapse on rerender and opens
  new rows independently. Direct text edits consume the starter marker.
- Connected/disconnected status transitions leave built colors and opacity
  unchanged without material lookup or geometry construction. Legacy clear-beam
  repair caches appearances by color, runs once, leaves CAD finishes unchanged
  and remains retryable after a material failure. Palette bootstrap requests
  repairs through a native command only when legacy display markers exist.
- GitHub citation text/BibTeX and public file/version/link consistency checked.

## Native 1.6.1 acceptance (requires desktop Fusion)

1. Preview and export `p100 l50 p25 r90 p75 _r90f50 p50`. The OAP's concave
   face must point into the incident/reflected beam wedge in the overview and SVG.
2. Create a new line/run; click its starter `p100`, cancel, then replace it with
   a lens or generic shape. Confirm there is no extra 100 mm segment. Undo/redo
   must restore the right step. Manually insert `p100`: it opens Inspector.
   Collapse Commands, edit another field, and confirm it remains collapsed.
3. Build connected routes including a generic outgoing beam-color change. Close
   the palette, reopen it, refresh status and move/reconnect the upstream route.
   Persistent colors and user-set opacity must remain, while Saved paths warns
   about disconnected/outdated inputs. Source CAD finishes must be unchanged.
4. Open a design with a legacy clear-beam marker. Verify automatic restoration
   in a native command, then save/reopen and Undo/Redo. Repeat Refresh: normal
   routes should cause no appearance changes. Check model versus preview colors
   with Fusion's component-color cycling disabled and the root component active.
5. Verify the **1.6.1** badge and both About citation copy actions include
   `https://github.com/AmLanz/LaserOpticsRouter`. Check on Windows and macOS.

## Previous 1.6.0 portable coverage

- Nested native CAD assemblies with noncommuting child rotations, `Rz = 90°`,
  nonzero datum/offset and source-geometry preservation; refused transforms.
- Live global defaults, local copy/rejoin, built-in fallback, old partial
  overrides, pinned saved routes and angle-independent BS migration.
- Waveplate/ND passivity in geometric and Gaussian models; manual budgets,
  native disc dimensions, token round-trip and CSV persistence.
- Signed tweaker offsets, incidence normals, splitter T-only displacement,
  unchanged reflected hit point, direction/budget preservation and trim reset.
- Independent contiguous budgets, unique bridge inclusion, ambiguous branches,
  position/direction tolerance, reflected-prefix trimming and copied instances.
- Saved overview route highlighting without editing, global default controls,
  automatic-connector cards/colors, pointer and keyboard selection.
- Python/JavaScript symbol parity for all element families, shape variants and
  projections; standalone export grid, world coordinates and transformed frames.

## Native 1.6.0 acceptance (requires desktop Fusion)

1. With the reported CAD assembly, set Rz to 90° and a nonzero XYZ offset.
   Compare **Preview this CAD only**, full solid preview and Build, including a
   rotated saved route and a source with two nested component levels. Verify
   optical datum, post direction and unchanged source geometry.
2. Save a `bs` component/calibration on Defaults. Insert `bs30` and `bs-90`:
   both start with Use default checked and read it. Uncheck one, change its
   rotation, then change the global default; only the checked optic follows.
   Recheck it, save/reopen the design and confirm the intended choices persist.
3. Build `p50 laha p50 laqu p50 nd p50`. Verify thin waveplate discs, thicker
   ND disc, unchanged beam appearance and the manual budget values. Assign a
   CAD model to each while retaining planning mode, then inspect one at a time.
4. Test `p50 tp30d0.5 p50` and `p50 tp-30d0.5 p50`: output remains parallel,
   displaced +0.5 / −0.5 mm in Y for a +X source. A splitter with 0.5 mm
   transmission displacement reflects at the incoming hit, with T shifted away
   from the reflected branch. At zero displacement, existing layouts match.
5. Build independent paths from (0,0,0), (20,0,0), (50,0,0) with lengths
   20, 30 and 40 mm along +X. Select the first/last: total 90 mm with the middle
   path listed and highlighted. A second alternative middle path requires an
   explicit choice. Verify connected reflection paths use the R budget.
6. On Saved paths, highlight a route/path, zoom and pan, then Edit highlighted
   route. Highlighting alone must not open an editor or mutate the document.
   Export all XY/XZ/YZ schematics and compare symbols, colors and current poses.
7. Confirm “by A. P. Lanz”, the current version badge, About text, citation copy actions,
   global/default field enablement, staged Save/Discard behavior and narrow
   palette layout. Exercise native Undo/cancellation with assigned CAD as below.

## Previous 1.5.0 portable coverage

- Generic tokens, shapes, dimensions, budgets and independent paired-ray colors;
  CSV/endpoint persistence, legacy colorless packets and stable trace hashes.
- Exact branch command prefixes, combined-ray event identities, resolved
  calculator selections, retained colors and full measured endpoint traces.
- The reported long route has 5 mm endpoints with the default source; its real
  intermediate ideal focus remains zero and is labeled distinctly.
- Schematic zoom anchors, pan/fit, degenerate extents, mirror and cube orientation,
  lens/prism/generic symbols, escaped labels and click-versus-drag behavior.
- Saved upstream route matching uses position and full direction; ambiguous
  sources are not guessed. Selection colors do not mutate optical settings.
- Useful and adaptive presets, generic insertion, per-optic shapes/colors,
  About/Cite requests and the component guide controls.
- Planning geometry never resolves assigned CAD; saved settings retain its
  calibration and link metadata. Older routes retain their CAD build behavior.
- Single-component preview copies only the selected source over draft lines,
  preserves source bodies and cleans graphics on cancellation. Oversize CAD
  preview rejection happens before copying an over-limit body.
- External references are required on linked insertion results. Selection
  protection changes the new instance only and reports unsupported setters.
- Sequential component insertion yields between parts; generated solids use
  batches of at most 40, including correct body indexing in direct mode.
- Progress cancellation/document changes close the dialog. Native command
  failure requests rollback and reports completion only after destruction.

The actual `docs/overview.svg` and an optical-symbol strip were rendered with
Inkscape and visually inspected. This verifies the SVG output, not the embedded
Fusion browser. No local-address browser access was used.

## Native Fusion acceptance checks — outstanding

1. **Document intent:** build the reported route in a Part document through
   Switch to Hybrid & build. Check Hybrid, eight optics, correct placements,
   preserved modeling mode, Undo and save/reopen. Repeat a small Assembly build.
2. **Overview:** inspect a 45° mirror (`r90`), a 15° mirror (`r30`), opposite cube
   ports, lenses and prism symbols. Drag, scroll/pinch, Fit, switch projection,
   and select main/secondary endpoints. Check the full highlighted measured arm.
3. **Budget:** build `p100 bsc p200`, then continue its reflected port through
   a lens. Select parent end and continuation. The resolved parent must end at
   `bsc [R]`, exclude `p200`, and retain its selected color. Inspect encounter list.
4. **Generic:** build disc/cube/ball placeholders, change a downstream color,
   set loss/GDD/glass values, save/reopen and export/reimport the route CSV.
5. **Single-part CAD:** use an asymmetric source with a visible datum. Assign it
   to two optics; plan/build with simple optics; verify assignments persist.
   Preview each part individually, checking X/Y/Z axes, OAP modifiers and moved
   route coordinates. Confirm source geometry, placement and visibility unchanged.
6. **Real CAD and links:** enable assigned CAD, build, verify preview agreement,
   external-link status and per-instance unselectability. Update a linked source
   deliberately in Fusion and verify all placed instances. Check that successful
   protected builds leave the root active and source selectability unchanged.
7. **Progress/Undo:** build enough beam sections to cross a 40-body batch and
   several CAD instances. Cancel during preparation and native insertion. Confirm
   no partial route remains, previous route survives, source parts are intact,
   and success is one Undo step. Repeat in direct and parametric modes.
8. **UI:** check readable layout at narrow/wide palette widths, presets/custom
   focus, keyboard navigation, source/color controls and About/Cite on Windows
   and macOS. Actual clipboard, CEF rendering and native CAD remain unverified here.

A single native Fusion operation cannot be interrupted by the progress callback.
Selection protection is not an absolute edit lock or a guarantee that automatic
cut/join participants exclude these parts. See [Component preparation](docs/COMPONENTS.md).

## New 1.4.1 coverage

- Exact reported route parses and plans with eight optics; the restriction is
  reproduced by a Part-document API double rejecting component creation.
- Explicit Part/Assembly conversion precedes component creation, in both
  modeling modes. Hybrid and legacy builds do not convert. Read-only planning
  exposes document context without mutating it.
- Missing or stale conversion choices, unreadable/unknown document types,
  rejected/ignored setters and beam refresh fail before creating components.
- HTML preflight occurs before geometry preparation; it only queues conversion.
  Native execute receives the displayed intent, and failure uses executeFailed.
  The palette receives the document type again after command destruction.
- Conversion labels, payloads, build-close behavior, preview isolation,
  successful replacement state and analysis updates are covered with DOM doubles.

## Focused 1.4.1 checks in Fusion (outstanding)

1. In a Part document, enter the reported sequence:
   `p100 l50 p25 p75 l50 p50 p50 r90 p50 _r90f50 p50 pol p50 l50 p50 wp20 p50 r-80 p50`.
   Check the Hybrid notice. Preview should keep the document as Part.
2. Choose **Switch to Hybrid & build**. Verify the document becomes Hybrid and
   the route, Beam and Optics components are created. Save/reopen, edit the
   route, and verify **Replace route** replaces only that route.
3. Check Fusion Undo/Redo and the resulting document type. A portable test
   cannot establish whether a native failure/Undo also restores design intent.
   Reopen the palette if necessary to re-read the current document type.
4. Repeat in an Assembly document and in a Hybrid document, with parametric
   and direct modeling. Hybrid should use the usual Build label. Existing
   geometry and the original modeling mode must remain intact.

API references: [Design.designIntent](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_Design_designIntent.htm),
[Design intent workflows](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/DesignIntent_UM.htm).

## 1.4.0 coverage

- The JavaScript visual editor's command round-trips are compared with the real
  Python parser. An inserted/duplicated labelled sequence is then planned by
  Python with its intended CAD assignments and multiplied reference losses.
- Stable optic and splitter-port IDs through inserted steps; independent
  duplicates; repeated-optic ambiguity handling; OAP sign/underscore reuse;
  physical-specification reset; step labels and CSV round-trips.
- Draft history grouping, redo branching, count/memory bounds, numeric-field
  gating, stale analysis rejection and one calculation request in flight.
- Current document defaults on recovery, token changes resolved by route ID,
  ambiguous edit targets recovered as new drafts, and discarded old-document
  replies. Native mutation is not invoked by draft Undo.
- Atomic draft write/replace, interrupted-write preservation, invalid-command
  draft recovery, document isolation and damaged/oversize file rejection.
- Pure-plan cache reuse, mutation isolation and recovery after invalid input.
- Draft line geometry includes geometric focus crossings and finite Gaussian
  waists. API doubles verify cm conversion, three line groups, no BRep access,
  and preservation of a moved route's transform.
- Completed command event handlers are removed without releasing handlers
  belonging to other commands. Existing build/rollback regressions still pass.
- Static HTML identifiers, local script ordering and references are checked.
  DOM/controller tests use substitutes; **no browser-rendering or click-through
  pass is claimed**. The user's local-address browser permission was denied,
  and that address was not used for final verification.

## Focused 1.4.0 checks in Fusion (outstanding)

1. Check selection, catalogue insertion, numbers and inspector navigation at a
   wide window and at 780 px. Check readable reference/default/calculator tabs.
2. Assign custom components to two identical lenses. Move/duplicate the steps;
   confirm each CAD assignment, datum and budget. Change one focal length and
   check only that step resets. Undo and redo the draft edits.
3. Compare fast and solid previews on a Gaussian focus, a 3D fold, a custom OAP,
   and a displacer pair. Fast preview shows nominal rings, not custom geometry.
4. Build/replace a moved route. Save/reopen, then Fusion Undo/Redo. Verify custom
   placements and split/secondary endpoints using the existing native checks.
5. Make an unbuilt edit and wait one second. Reopen the palette and restore it.
   Switch between two saved designs; their drafts must remain separate.
6. Use Build without closing several times; then preview, edit, save and Undo.
   Confirm command-handler cleanup does not change native transaction behavior.

## Coverage relevant to this release

- Total Wollaston split angles, straight Rochon output, BD side/plane signs,
  local transverse frames including vertical inputs, tube threshold/scaling,
  custom default normalization and representation dimensions.
- Recombination and wrong/missing/mismatched displacers; Gaussian envelopes,
  paired Previous-line propagation, per-arm budgets after combination and
  independent secondary endpoints. CSV round-trip and SVG include both rays.
- Prism body generation invokes the existing cylinder/box/boolean helpers with
  the requested dimensions. This checks construction inputs, not native BReps.
- Revision-only changes remain current; envelope changes are amber updates;
  missing/recovered positions and opposite directions control disconnection.
  Unique replacement sources, explicit ambiguous choices, upstream ordering,
  internal reflected starts, and descendant exclusion are covered.
- Beam refresh preserves the route and optics, supports translated/rotated
  routes, rejects changed inputs during preparation and shared route definitions,
  and retains old groups on native creation failure for transaction rollback.
- Grouped calculator cards show names/commands/coordinates/direction/budgets;
  filtering retains selections. Refresh choice dialogs send explicit source
  identities and successful refresh safely reloads an active editor.

- Parent-end plus reflected-continuation selections use the correct splitter
  port, even if the parent transmission contains more commands than the chosen
  arm. Covers reflected loss/GDD/glass, repeated selections, cascaded splitters,
  missing intermediate paths, two continuing arms and moved saved sources.
- All-document ZIP contains every readable saved route, current world endpoint
  coordinates, three combined SVG projections, full JSON records and route CSVs
  that still import individually. Includes stale flags and spreadsheet-safe names.
  The native file bridge works independently of an invalid current draft.
- Refresh with no edit target and Refresh during editing do not mutate a null
  target or rename the draft. All endpoint and diagnostic copy buttons use the
  native copy request, with an honest visible manual fallback on failure.
- Windows clipboard doubles check Unicode bytes, bounded
  busy retries and memory ownership on success/failure; macOS checks UTF-8 stdin.
- Build/Build & close send distinct close flags. Command completion honours
  them; an open successful build becomes the next replacement target. Hidden
  local divergence survives ordinary source edits without being printed.
- Strict occurrence doubles reproduce the reported nested-native transform
  error. Successful placement uses proxies with full paths from the root.
- Preview/build agreement for custom optics after a position capture, including
  replacement of an already translated and rotated route. Transform composition
  in the test double is independent of the adapter's composition helper.
- Already-correct nested insertions require neither a move nor a capture.
  A missing proxy or failed capture leaves the old route intact for transaction
  rollback; the reported error identifies the failing build stage.
- Regression for the exact throwing nested `isGrounded` getter; custom-instance
  placement compared with preview geometry under an inherited insertion offset.
- Placement preservation, active component restoration on failure, original source
  immutability, datum picking and single-owner failure rollback boundaries.
- Build failure reporting after command destruction, with the correct separate
  reply type for saved-route management.
- OAP calibration starting from each signed/underscore orientation; datum
  positions and represented surface normals agree in all four variants.
- Cube reverse suffix at each size, without changing transmission or size keys.
- Percentage-loss products, signed GDD sums, optional glass correction,
  independent splitter budgets, and unchanged spatial ray/beam results.
- LOR2 round-trip and legacy LOR1 reading; connected-arm sums, shared-section
  deduplication, unresolved-gap detection and rejection of mixed branches.
- Continuations held fixed and marked stale; opt-in rigid following; deleted
  sources and changed envelopes offering separate statuses; internal branch identity.
- CSV round-trip including custom calibration, negative GDD, formula-like text,
  and component reselection across documents. SVG XML/projection structure.
- Interface representation choices, named budget fields, propagation-only edit
  preservation and reset of ambiguous optic assignments.
- Prior lens, Gaussian, reflection, endpoint, frame, Windows URL and persistence
  regressions remain included.

## Native limitations

Autodesk Fusion is unavailable in this execution environment. Native BRep
creation, Undo, grounding behavior, file dialogs, material assignment, selection,
save/reopen and palette rendering require an in-Fusion check. Browser access to
the earlier local QA page was denied; no browser workflow pass is claimed.
Native Windows/macOS clipboard operations have not been executed here; their
control flow is covered with operating-system API substitutes.

The user's earlier logs establish the nested grounding error and a later ASM/Undo
crash. The subsequent reported message establishes a rejected transform override;
the local Windows diagnostic file itself was not supplied for that update. The
user then confirmed that 1.2.1 built successfully and looked good. This release
retains its placement and rollback implementation; command-handler lifetime is
now bounded at command destruction. Portable tests cannot
establish the complete native Undo/save/reopen behavior.

## Earlier native failure evidence — September 2026

- **1.2.0:** a nested `isGrounded` access produced an API exception. Later
  application logs showed repeated `leaked ASM Entity` warnings followed by an
  ASM/BRep crash during `onLoadFromUndoStream` / `UndoCmd::onExecute`. This does
  not identify one initiating Python call or establish that every native crash
  has been eliminated.
- The build lifecycle removes previews before the model command, prepares
  transient geometry first, retains bodies until command destruction, and uses
  `executeFailed` for one native rollback rather than deleting partial geometry
  before Undo. Success/failure unlocks the palette after command destruction.
- **1.2.1:** the reported root-proxy transform exception was reproduced by a
  stricter API double. Nested placement now uses root-context proxies and
  composes the route transform once; captured positions are verified before
  deleting a replaced route. The user subsequently confirmed a successful build.
  Full native Undo/save/reopen coverage still requires the checks above.
- Original application logs and machine-specific paths are not distributed.
  Current errors retain stage markers and tracebacks in the temporary diagnostic
  log. Portable regressions preserve the triggering geometry and API constraints.

## Focused checks for 1.3.0 in Fusion

1. Update the whole registered add-in folder, restart Fusion and verify the
   1.3.0 badge. Preview/build `p20 wp20h p100`: output azimuths are 350° and
   10°. `wp20v` gives elevations −10°/+10°. `rp10.6 p100` keeps one beam at
   azimuth 0° and sends the other to 10.6°.
2. Preview/build `bd4h p50 _bd4h p50`. There should be two parallel beams
   between displacers and one continuing envelope afterward. Both budget-arm
   endpoints remain selectable. Repeat with `bd4v- p50 _bd4v- p50`.
3. Try `bd4h p50 _bd4h- p50`: verify the orientation warning and separate rays.
   Normal housing lengths are 28 mm for bd2.7 and 41 mm for bd4. WP/RP have
   14 mm housings and 10 mm crystals. Inspect the subtle orientation markers.
4. On Defaults, save the part for a custom BD corresponding to `bd4v-`; reuse it as `bd4h` and `_bd4h`.
   Check the indicated local axes, selected datum and six placement controls.
   Compare preview/build and check Undo/save/reopen with these new shapes.
5. Build a parent `p100`, continue from its endpoint with `p40 l50 p50`, and
   manually adjust a downstream custom optic. Change only the parent source
   diameter and replace it. The continuation must show Beam update available,
   retaining its pose and beam appearance. Refresh beam must update the beam
   and saved statistics, retaining that same optic instance and its manual pose.
6. Move the parent away: the continuation becomes Disconnected after a status
   scan. Restore the parent to its original pose: it becomes current or offers
   a beam update. A same-position endpoint facing the other way must not match.
7. With two replacement endpoints at the same suitable pose, Refresh beam asks
   for a source choice. Check the named route/endpoint list. Refresh upstream
   routes before downstream routes marked Refresh upstream first.
8. In Calculator, select named route/endpoint cards, filter the list and check
   that hidden selections remain counted. Parent plus reflected continuation
   must still trim the parent at the splitter. A prism secondary continuation
   counts the selected parent along that secondary arm.
9. Export all paths: CSV/JSON distinguish disconnection from a beam update, and
   the SVGs include both prism/displacer rays. Import a prism route CSV as a draft.

## Existing workflow checks for 1.2.2 in Fusion

1. Build `p100 bsc p200` using **Build**. The window stays open and the button
   becomes **Replace route**. Build again after a distance edit: only that route
   should be replaced. **Build & close** closes the window after success.
2. Use Start new run here on the saved reflected port and build `p40`. Select
   both routes' normal ends in Calculator: geometric length is 140 mm, loss 51%
   and GDD +300 fs² with standard defaults. The result identifies the parent cut.
3. Click Refresh before editing anything and while editing a route. Check the
   list/status updates, no null-name error appears and the draft name stays intact.
4. Copy a current end, current reflected port, saved end and diagnostic text;
   paste into a text editor. Endpoint packets must also work in Paste endpoint.
5. Export all document paths. Check all saved routes in `all_paths.csv`, current
   placement in the three SVGs and an individual route CSV import as a draft.
6. Check the Source panel, live outputs, command details, saved endpoints and
   command reference: local half-angle controls/readouts are absent. Gaussian
   far-field divergence and the underlying copied beam state remain available.

## Previous Fusion acceptance sequence

1. Restart Fusion after replacing all add-in files. Preview/build a simple
   `p100 l50 p25 r90 p75` route; check Preview and Build agree. Expected end:
   (125, 75, 0) mm, diameter 5 mm, geometric length 200 mm. Check normal Undo.
2. On an asymmetric custom component whose original occurrence is moved and
   rotated, set a nonzero datum and all six adjustments. Preview/build, save,
   reopen and verify placement. Repeat with an active subcomponent. Then move
   and rotate the whole built route, edit it and build the replacement: the
   custom optics and beam must retain the moved route's coordinate frame.
3. On Defaults, calibrate the `r90f50` part for `_r-90f50`, save the default, and use `r90f50`, `r-90f50`
   and `_r90f50`. Check parent-axis orientation and the same chief-ray datum.
4. Check `bsc`, `bsc-`, `-bsc`, `-bsc-` and `+bsc-`; repeat at a nonzero roll.
5. Give a lens 10% loss, +80 fs², n=1.5 and 4 mm effective glass thickness.
   Follow with a splitter having T=60%, R=30%, transmitted GDD=-20 fs² and
   reflected GDD=+40 fs². Check total transmitted loss 46% and GDD +60 fs²;
   reflected loss 73% and GDD +120 fs². Geometry must be unchanged.
6. Continue a reflected port in another route. Select that port and continuation
   in Calculator: shared sections count once. Selecting the parent line end
   instead must give the same result. Selecting continuations along both outgoing
   arms must still be rejected.
7. Edit the upstream route with Keep following saved paths checked. Check the
   downstream route stays fixed, gains a Disconnected label when no endpoint matches and a clear/transparent
   beam. Repeat unchecked with unchanged input envelope: all continuation optics
   move rigidly and their endpoints/reference totals update. A changed envelope
   at a matching start must offer Refresh beam instead.
8. Move an entire upstream route manually and click Saved paths → Refresh.
   Check stale status and appearance; delete/Undo and refresh again.
9. Export CSV, change one budget column, import as a draft and verify the value.
   Import in another document and confirm custom components need reselection.
10. Export each SVG projection; check orientation, labels, scale and the current
    placement of a moved route.
11. Inspect all four tabs, help text, disabled controls and dialogs using the
    normal Fusion theme. Check the Command reference no longer exposes the
    dark host background.

If a native failure remains, attach the local LaserOpticsRouter-build.log and
relevant Fusion AppLog files with the route commands and exact Fusion version.
