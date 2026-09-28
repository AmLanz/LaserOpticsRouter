# Preparing and using real components

Assign real hardware once, plan with simple optics, and inspect one assigned
part when checking orientation. The 2D overview always uses schematic symbols;
it is not a CAD footprint or clearance calculation.

## Planning and inspection

1. Open the part's own Fusion file. Position its optical datum and axes as
   described below, then save it.
2. In the setup document, insert that design as a **linked component** using
   Fusion's normal insert workflow. Select the optical component you intend
   to place, rather than an unrelated parent assembly. Keep this source
   instance available; hide it manually if it clutters the setup.
3. Open **Defaults → Default optics & components**, select the optic, choose
   **Assigned component**, then **Select component…**. Set its datum, XYZ offsets
   and rotations, and **Save default**. New optics have **Use default** checked.
   For an individual assignment, uncheck it in Inspector and choose **Assigned
   component** there. The component origin is used without a point pick.
4. Leave **Use assigned CAD in solid preview & build** off while planning.
   Solid preview and Build use the built-in optics; the assignment, datum,
   calibration and budgets remain saved. New drafts default to this mode;
   old saved routes retain their previous CAD build behavior.
5. Use **Preview this CAD only** in Inspector. It copies only this part's
   visible BRep bodies into temporary graphics, with the rest of the route
   shown as fast draft lines. Red/green/blue axes show calibrated local X/Y/Z
   at the selected datum. Previewing another part replaces this preview.
6. When ready, enable **Use assigned CAD in solid preview & build**, preview
   as needed, and Build. Unassigned built-in optics remain simple shapes.

The selected preview works while full CAD is disabled. It never moves, edits,
renames or changes the source component's visibility. **Clear** removes temporary
graphics. Mesh-only models cannot be inspected with this BRep preview.

## Coordinate convention in the part's own file

Use the component's **local** origin and axes, not the setup document axes or
its current occurrence placement. Source geometry is never rescaled by the
router's nominal-diameter field. Fusion handles the part's physical units.

| Component | Origin / optical datum | Local +Z | Local +X and +Y |
|---|---|---|---|
| Lens | Beam centre on the ideal thin-lens interaction plane | Forward propagation | X/Y span the optic plane |
| Polarizer, λ/2, λ/4, ND or generic placeholder | Beam centre at the chosen interaction plane | Forward propagation | X/Y span the optic plane |
| Tweaker plate | Incoming chief-ray hit on the plate | Plate normal toward transmission at zero incidence | X/Y span the plate; `tp` tilts the target normal |
| Mirror / plate splitter | Chief-ray hit on the front reflecting surface | Surface normal toward the beam side; backing extends toward −Z | X/Y lie in the surface |
| Cube splitter | Cube centre, where the chief ray meets the internal splitting plane | Transmitted output | +X is the 90° reflected output; +Y completes the frame. Internal plane is Z = X |
| Wollaston / Rochon / BD | Main-ray datum at the ideal interaction location | Incoming beam direction | +X is the secondary separation / walk-off direction; +Y completes the frame |
| OAP | Chief-ray hit on the off-axis optical surface | Parent-parabola axis toward the parent focus | +X points radially outward from the parent axis toward the off-axis segment; +Y completes the frame |

All frames are right-handed: **Y = Z × X**. The Inspector displays each frame
in design coordinates. For a normally incident lens with an incoming +X
world-direction beam, local Z maps to world +X; this is intentional.

The datum is a modeling convention. Lens thickness, prism entrance/exit
surfaces and substrate optical path are not traced. Use a consistently chosen
interaction plane and enter glass path length manually when needed.

### OAP example: 90° bend, 50 mm reflected focal length

The parent focal length is 25 mm. With the chief-ray hit at the local origin,
the corresponding parent vertex is **(−50, 0, −25) mm** and the focus is
**(−50, 0, 0) mm**. These coordinates describe the ideal parabola, not a
manufacturer's mounting datum.

For `r90f50`, the incoming beam travels along local −Z and the outgoing beam
along local −X. For `_r90f50`, the incoming beam travels along +X and the
outgoing beam along +Z. Both use the same prepared part and reference point;
the router changes the target frame. A negative bend chooses the other turn
side. Enter the actual part's design bend in Inspector so a mismatch is visible.

Do not use the blank's rear centre or the parent vertex as the chief-ray datum
unless you supply the appropriate reference point/calibration. Verify the
surface and both ray directions with the single-part preview. The `f` prefix
is a 180° **CAD rotation about local Z**, not a front/back swap and not a beam
transformation.

## Existing vendor CAD with a different origin

Reworking the source file is optional:

- **Pick point / circle centre…** accepts a vertex, construction/sketch point,
  circular edge, or sketch circle/arc. It uses the position or circle centre;
  it does not infer the optical axis from that entity.
- XYZ shifts are in the target optic frame. Rx, Ry, Rz rotate about fixed local
  axes in that order, around the selected datum. The `f` prefix adds 180° to Rz.
- **Use component origin** restores a zero reference point. Neither it nor a
  preview changes the source model.
- **Defaults → Save default** stores the component and calibration in this setup
  document. Different physical sizes/focal lengths remain separate defaults.
  All plate-splitter angles/signs share `bs` for each size; tweaker angles and
  offsets share `tp`. Supported OAP/prism orientation variants reuse calibration.
  The individual **Use default** checkbox reads this record; it never writes it.
  Unchecking copies the current choice for local editing. Rechecking follows
  the global record again. A missing default uses the built-in optic.

Placement adjustments affect only the representation. Commands still determine
the beam path. If an adjustment moves the optical surface away from the beam,
the router does not redirect the beam to compensate.

## Preview and built rotation

Preview copies native bodies from the selected component definition. For a
nested assembly, each immediate child's local transform is composed once into
that definition frame, then the same placement used by Build is applied. This
avoids mixing root-context occurrence matrices with local child coordinates.
`Rz = 90°` remains a rotation about the fixed local Z axis; it is not reinterpreted
as a rotation about a document axis. A refused temporary-body transform now
cancels preview with an error instead of leaving an untransformed copy visible.

Nested, noncommuting rotations and a nonzero datum/offset are covered by portable
regressions. Recheck your real assembly in Fusion using **Preview this CAD only**
and Build; native Fusion execution is not part of the portable tests.

## Source links and accidental editing

The add-in instances the existing component definition. It does not make an
independent geometry copy, break a link, or write features into the source.
If the selected occurrence is externally linked, the build checks that the
new instance still reports an external reference and fails if it does not.
A source inserted without a link remains a local shared component; the add-in
cannot turn that into an externally linked file merely by assigning it.

Edit linked parts in their own files, save them, then use Fusion's normal
linked-component version/update controls in the setup. Updates are deliberate;
the add-in neither automatically fetches a newer version nor writes back to the
source file. Retain the datum/axis convention across revisions and recheck the
placement when its optical geometry changes.

**Make inserted CAD instances unselectable** is on by default. It applies only
to newly placed instances and leaves the design root active after a successful
build. Source instances remain unchanged. Use Fusion's browser **Selectable**
control to enable selection deliberately, or disable the option for subsequent
builds.

**This is a selection safeguard, not an edit lock.** It does not promise to
exclude a component from every automatic extrusion, cut, join or other modeling
operation. Local instances share editable geometry. Fusion's linked-component
workflow separates source editing, but explicit Edit In Place/break-link actions
are still available. When making unrelated geometry, use a separate active
component, select New Body/New Component as appropriate, and review feature
participants. Grounding constrains motion; it does not protect geometry.

## Build performance and cancellation

Build inserts assigned components **sequentially**, reusing their definitions.
Generated beam/optic solids are added in batches of at most 40; each base feature
is closed before the event loop is serviced. Placement capture/verification is
performed before replacing the previous route. All native build mutations stay
inside the existing command transaction for a single Undo operation.

Preparation and Build show progress with Cancel. Cancellation is checked between
native operations and marks the command failed so Fusion can roll it back.
No source component is edited. A single slow import/insert/kernel operation
cannot be interrupted by this progress mechanism; the UI can still pause until
Fusion returns. This is not a crash-proof guarantee.

For large setups, keep planning mode enabled, inspect one component at a time,
and remove unnecessary threads, screws and highly tessellated detail in a
simplified source model. The temporary CAD preview stops above 1,000 visible
bodies or 100,000 faces per component. Build keeps the existing 5,000 beam-section
limit. Several short named routes can be easier to revise than one huge route.

Native behavior to verify on your Fusion version is listed in
[TESTING.md](../TESTING.md), including linked-source updates and cancellation/Undo.

## API references for maintainers

- [Occurrence insertion](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_Occurrences_addExistingComponent.htm)
- [External reference status](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_Occurrence_isReferencedComponent.htm)
- [Occurrence selection](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_Occurrence_isSelectable.htm)
- [Progress dialog](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_ProgressDialog.htm)
