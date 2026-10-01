# Preparing and using real components

Prepare each reference component in **its own Fusion file**. Put its local
origin at the point where the beam should hit and make **X perpendicular to the
reference optical surface**. For a mirror, a ray travelling along −X reflects
back along +X at normal incidence. Backing extends toward −X. Lens X follows
forward propagation. The router uses this origin and these axes directly.

**Breaking change in 1.7.0:** every assignment uses this convention, including
rebuilt saved routes and imported CSVs. There is no legacy Z-normal mode. Former
reference points and calibration entries are ignored. Opening a route alone
does not move built CAD. Version 1.7.1 provides new explicit component rotations
and assembly-coordinate offsets without restoring that former convention.

The default roll uses the Hybrid assembly's **positive Z**. For horizontal
surface normals, component Z is parallel to assembly Z. For tilted normals,
Z is the projection of assembly Z onto the surface, and Y completes a
right-handed frame. If X is exactly vertical, Z points along assembly −X as
a deterministic fallback. Whole-route rotations are accounted for in both
Preview and Build. This roll does not follow the beam's transported H/V frame.

## Choose and inspect a component

1. In the part's own file, position the geometry relative to the intended
   component's local origin/axes. Moving the occurrence in the setup does not
   prepare its definition. Save the source file.
2. Insert that file into your setup using Fusion's **linked component** workflow.
   Keep this source occurrence available. It may be hidden.
3. Under **Defaults → Default optics & components**, choose **Assigned component**
   and **Choose component…**. Search the occurrence name or full assembly path,
   select the prepared component, then **Use selected component → Save default**.
   Generated route/preview components are excluded. This chooser does not depend
   on clicking a visible face in the viewport. It does not import a file itself.
4. New optics use the saved default. Uncheck **Use default** in Inspector for an
   individual assignment. Default edits are staged until saved.
5. Use **Preview this CAD only**. Red X, green Y and blue Z show the placed axes
   at the placed component origin. Correct alignment in the source file, or use
   **Component rotation & assembly offsets** below the assignment.
6. Plan with **Use assigned CAD in solid preview & build** off for simple optics.
   Enable it when ready to build the assigned parts. Preview and Build use the
   same placement. Save the setup document to retain its defaults and routes.

The preview does not move or change the source occurrence. **Clear** removes
temporary graphics. It supports BRep geometry, not mesh-only source models.
The overview uses optical symbols rather than CAD footprints.

## Axes in the part's own file

All frames are right-handed: **Z = X × Y**. The router preserves actual CAD size;
nominal aperture fields never rescale a custom model.

| Part | Origin | Local +X | Local +Y / +Z |
|---|---|---|---|
| Spherical lens, polarizer, waveplate, ND, generic | Beam centre on chosen interaction plane | Forward optical axis | Y/Z span the surface |
| Cylindrical lens | Beam centre on thin-lens plane | Forward optical axis | Y powered direction; Z cylinder axis |
| Mirror / plate splitter | Chief-ray hit on front reflecting surface | Surface normal toward beam side | Y/Z span the surface; backing toward −X |
| Reflection grating | Chief-ray hit on grooved surface | Surface normal toward beam side | Y dispersion tangent; Z along grooves |
| Tweaker plate | Incoming hit on reference face | Reference-face normal, forward at zero tilt | Y/Z span the face |
| Cube splitter | Hit on internal splitting plane | Transmitted output / entrance-face normal | Z upright; orient its reflected port with explicit Rx |
| Wollaston / Rochon / BD | Main-ray hit at ideal interaction location | Incoming axis / entrance-face normal | Z upright; use Rx for separation/walk-off orientation |
| OAP | Chief-ray hit on off-axis optical surface | **Tangent surface normal toward beam**, not parent-parabola axis | Z upright; orient the parent axis with explicit Rx |

For a cylindrical lens, `h`/`v` chooses the **powered** direction, which is
perpendicular to the physical cylinder axis. For a grating, dispersion is
perpendicular to the grooves. The optical h/v and OAP `_` modifiers change the
beam calculation; they do **not** automatically roll assigned CAD around X.
For vertical cylinder power, vertical grating dispersion, another prism side,
or the alternate OAP parent-axis leg, set explicit component Rx as required by
the source model. Enter the actual OAP design bend in Inspector for its warning.

## Reproducible rotations and offsets

Defaults and local Inspector assignments expose **Component Rx/Ry/Rz · °**.
They rotate the source geometry about its own origin and fixed X, then Y, then Z
axes before optical alignment: `B × Rz × Ry × Rx`. B is the assembly-upright
optical frame. For example, Rz = −90° maps the original +Y surface normal onto
the target +X normal; +90° maps it to −X. A flat mirror's plane is the same,
but its front/back sign matters. Rotation never changes the calculated beam.

**Assembly ΔX/ΔY/ΔZ · mm** translates the placed component in the Hybrid
assembly's axes, not the tilted component or a manually rotated route's axes.
The nominal beam hit stays fixed. The defaults are zero. Preparing the hit
point and normal in the source file is preferred; offsets are useful when the
source definition cannot be changed. Preview and Build use exactly one composed
placement, including nested source components.

The `f` prefix rotates only CAD by **180° around the target X normal**, at
the origin. It does not change the calculated beam. It spins a mirror/lens in
its surface plane; it is not a front/back swap. On asymmetric optics such as
OAPs, check that the represented surface still matches the intended ray paths.
With explicit component corrections, the source is corrected first, then this
surface-normal spin is applied; the world matrix is `B × Rx(180°) × Rz × Ry × Rx`.

The chosen interaction plane is idealized. Lens thickness, prism interfaces
and substrate propagation are not ray-traced. Enter glass length manually
when needed for reference budgets. Reset plates are virtual markers and do
not take a custom component assignment.

## Reusable defaults and migration

Defaults belong to the active setup. Different focal lengths and sizes remain
different parts. Orientation variants reuse a part: `cyl100h`/`cyl100v` share a
default; gratings share by groove density and size, independent of incidence,
order and dispersion plane. BS angles share `bs`, and tweaker tilts share `tp`.
OAP defaults share actual bend magnitude and reflected focal length. Prism
orientation variants retain the same physical specification.

Saved routes pin component identity and reference properties. Checking **Use
default** deliberately reconnects to the current global record. Neither pinned
settings nor old defaults preserve the former Z convention or calibration.
New 1.7.1 rotations/assembly offsets are pinned and round-trip with CSV.
When upgrading, save a backup of the design, prepare each source's X-normal
axes, then inspect and rebuild the routes that use it.

For nested assemblies, the selected component definition is the reference
frame. Preview composes each child's local transform once; Build inserts the
same definition with the same route placement. Selecting an unrelated parent
whose origin/axes differ gives a different placement.

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
source file. Retain the origin/axis convention across revisions and recheck the
placement when its optical geometry changes.

**Make inserted CAD instances unselectable** is on by default. It applies only
to newly placed instances. Every successful build leaves the design root active
so inactive-component shading does not dim the new route. Source instances
remain unchanged. Use Fusion's browser **Selectable**
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
performed before replacing the previous route. The old occurrence is deleted,
then colors are applied to the final bodies using current design appearances.
All native build mutations stay
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
