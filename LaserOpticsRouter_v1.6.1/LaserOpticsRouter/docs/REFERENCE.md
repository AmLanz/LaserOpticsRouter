# Optical and command reference

For installation and the visual workflow, see [README](../README.md) and [Quick start](../QUICKSTART.md). For source-part axes, links and protection, see [Component preparation](COMPONENTS.md).

## Command language

Use **spaces** between commands. Commands are case-insensitive. Distances,
diameters and focal lengths are in **millimetres**; angles are in **degrees**.
Decimal and scientific notation are accepted. A `#` starts a comment through
the rest of that path line. `+` is a size prefix, never a separator.

| Command | Meaning |
|---|---|
| `p50` | Propagate 50 mm along the current direction. Nonnegative distances only. |
| `l50` | Positive thin lens, focal length +50 mm, normal diameter. |
| `l-50` | Negative thin lens, focal length −50 mm, normal diameter. |
| `+l-50` | Large negative lens. |
| `-l50` | Small positive lens. |
| `g`, `+g`, `-g` | Generic placeholder: disc, cube or ball; manual budget and optional outgoing beam color in Inspector. |
| `laha`, `laqu` | Half-wave / quarter-wave plate discs; spatial envelope and display color unchanged. |
| `nd` | Slightly thicker ND filter disc; manual loss, GDD and glass properties. |
| `tp30d0.5` | Tweaker plate: 30° incidence from its normal, explicit 0.5 mm parallel displacement. |
| `pol`, `+pol`, `-pol` | Grey polarizer disc; spatial beam envelope unchanged. |
| `r90` | Mirror adding +90° azimuth. |
| `r90v30` | Mirror adding +90° azimuth and +30° elevation. |
| `r0v30` | Mirror changing elevation only. |
| `bs30`, `bs30v15` | Plate splitter with the indicated reflected direction. Main line continues straight. |
| `bsc`, `bsc-` | Cube splitter with a true 90° reflected branch; the trailing minus reverses the reflected port. Its card sets branch roll. |
| `-bsc`, `-bsc-`, `+bsc-` | Small cube; small reversed cube; large reversed cube. The leading sign still selects size. |
| `wp20h`, `wp20v` | Wollaston: 20° total separation, −10° main and +10° secondary in the local horizontal/vertical plane. |
| `rp10.6`, `rp10.6v` | Rochon: straight main ray, secondary at 10.6°. Default plane is horizontal. |
| `bd4h`, `bd4v` | Straight main ray and parallel secondary displaced by 4 mm. |
| `bd4v-` | Reverse the vertical displacement; the leading sign still sets size. |
| `_bd4h` | Combine a matching active pair, reversing the displacer walk-off. |
| `r90f50` | OAP, reflected focal length 50 mm; incoming leg is the parent-axis leg. |
| `_r90f50` | OAP with outgoing leg along its parent axis. |
| `r90v30f50` | Combined 3D OAP command. |
| `+_r90f50` | Large OAP with swapped parent-axis leg. `_+r90f50` is also accepted. |
| `fl50`, `f+l-50`, `fr90`, `fpol`, `fbs30`, `fbsc` | Rotate the CAD optic 180° about local Z at its datum. Beam calculations are unchanged. |
| `f_r90f50`, `+fr90f50` | Combine the CAD flip with the OAP or size modifiers. |

All optic commands act at the current position. **Only `p` adds path length.**
Standalone `f`, `e` and `c` commands are removed. Convert `f50` to `l50 p50`,
`f-50` to `l-50 p50`, and `e50` to `p50`. Set initial collimation in Source or
use an actual lens/OAP in the sequence. The `f` suffix remains part of an OAP
command, and OAP focal lengths must be positive. The new **prefix** `f` only
modifies an optic; standalone `f50` and `fp50` remain invalid.

**Z rotation is not a front/back swap.** For a lens with its optical axis along
local Z, a 180° rotation around Z spins it in its own plane. The command does
exactly that. For a custom component, it adds 180° to the final fixed-local-Z
rotation about the selected datum; XYZ shifts stay in the unflipped optic
frame. Symmetric built-in discs/lenses may look unchanged. An asymmetric
component shows the rotation. For an OAP, `_` continues to control which beam
leg follows the parent axis; `f` changes only CAD orientation and can misalign
the represented surface with the ideal calculated rays, so an OAP warning is
shown.

Size prefixes apply to lenses, mirrors, OAPs, polarizers, plate splitters and
cube splitters, Wollaston/Rochon prisms, beam displacers, waveplates, ND filters, tweaker plates and generic optics. Each family has its own editable defaults:

| Prefix | Default | Interpretation |
|---|---:|---|
| `-` | 12.7 mm | Small optic |
| none | 25.4 mm | Normal optic |
| `+` | 50.8 mm | Large optic |

The dimension is an optic diameter, or **edge length for a cube**. Individual
optic cards can override the nominal dimension. Custom CAD components keep
their actual size; changing the nominal aperture does not rescale the CAD.

## Direction and reflection

Azimuth is measured from global +X toward +Y. Elevation is measured above the
global XY plane. `r` and `v` add to these two angles; they are not sequential
Euler rotations about a moving frame. Thus:

```text
p50 r90v30 p100 r-90v-30 p100
```

restores the original beam direction. Elevation is restricted to −90°…+90°.
At exactly vertical incidence, azimuth is undefined; its last value is retained
to determine the next turn and is marked as such in the status display.

Mirror normals are calculated from the incoming and outgoing unit vectors.
`bs30` changes the reflected beam direction by 30° for a horizontal input;
its incidence angle from the normal is 75°. In general, a 3D bend is not equal
to the azimuth increment. Optic cards display the actual bend and incidence.

The suffix in `bsc-` adds 180° to its card's roll. `bsc` and `bsc-` share the same component default for a given size. Cube roll rotates its reflected port about the incoming beam without changing
the 90° split. For horizontal +X incidence: 0° = +Y/left, 90° = +Z/up,
180° = −Y/right, 270° = −Z/down. For inclined incidence, these are the
corresponding local left/up directions.

## Passive waveplates, ND filters and tweaker plates

`laha` and `laqu` denote λ/2 and λ/4 waveplates. Their built-in placeholders are
1 mm thick discs; `nd` is a 2.5 mm thick disc. They do not change the spatial
envelope, direction, wavelength or beam display color. Their manually assigned
loss, signed GDD and effective glass path enter the reference budget. No
polarization or wavelength-dependent attenuation is calculated. Placeholder
thickness is visual and does not set the glass-path entry automatically.

`tp30d0.5` tilts the plate normal by +30° from the incident beam toward local
left (+Y for a +X beam) and displaces the transmitted parallel ray by +0.5 mm
toward that side. `tp-30d0.5` tilts/shifts toward the opposite side. Negative
`d` reverses the displacement; at zero angle, positive `d` is local left.
The incidence must be strictly between −90° and +90°. `d` can be omitted for
zero displacement. This is an explicit geometric offset, not a Snell-law
calculation from thickness/index; it does not focus or add path length.

Plate and cube splitters expose **Transmitted displacement · mm** in their
global defaults and local optic properties. It is zero initially. A positive
value shifts transmission away from the reflected branch in the incidence
plane; negative reverses the side. At 180° reflection, local right is used
because the reflection plane is undefined. Reflection always starts at the
original incoming hit point. Transmission keeps its incoming direction and
envelope. The optic's datum remains at the original hit point. Both CAD shifts
and rotations only position the model; they do not infer a beam displacement.

Only `p` contributes geometric distance. Include all intended glass propagation
in your entered distances and supply effective glass path and GDD separately.
Grating dispersion/beam widening is outside this release.

## Wollaston, Rochon and beam displacers

```text
p20 wp20h p100
p20 rp10.6v p100
p20 bd4h p50 _bd4h p50
bd4v- p50 _bd4v- p50
```

`wp20h` creates two rays at −10° and +10° relative to the incoming ray: 20° is
**total separation**. `rp10.6` keeps the main ray straight and deflects the
secondary by 10.6°. `bd4h` keeps the main ray straight and offsets the parallel
secondary by 4 mm. `h` is local left, `v` local up; at +X these mean +Y and +Z.
Omitting the plane selects `h`. A trailing minus reverses the side for all three.
At an exactly vertical input, the retained azimuth defines this transverse frame.

`p` automatically advances **both** rays by the entered distance along their own
axes. Subsequent optics act on the main ray; use the secondary output endpoint
in its own line to give it independent optics. **Previous line end** carries the
pair across lines. A copied endpoint carries one ray only. One active pair is
supported per line chain; start from an individual endpoint before another
splitting prism/displacer. This makes the selected optic's target explicit.

`bd4h p50 _bd4h` combines its active rays. Position and direction must match the
required displaced input within 0.001 mm and 0.001°. Using `_bd4h-` instead warns
**beam displacer orientation wrong** and leaves both rays separate. A combining
command cannot recover an omitted second ray from a single copied endpoint.
Equal envelopes are drawn once after combination; different envelopes stay
visible on the common axis. Endpoints for both **budget arms** are retained.
The calculator follows one arm at a time; it does not sum two parallel path
lengths or infer interference or combined power. A later lens or mirror on the
common axis updates both coincident envelopes.

| Built-in normal representation | Crystal | Tube outer diameter | Tube length |
|---|---|---:|---:|
| Wollaston / Rochon | 10 × 10 × 10 mm | 25.4 mm | 14 mm |
| BD with displacement ≤2.7 mm | 10 × 10 mm cross-section | 25.4 mm | 28 mm |
| BD with displacement >2.7 mm | 10 × 10 mm cross-section | 25.4 mm | 41 mm |

These are reference shapes using the requested dimensions, not detailed product
models. WP/RP include a subtle diagonal interface; BD has a walk-off-side mark.
The built-in BD aperture is centred between the two beam axes; its optical datum
remains on the straight ray. Prefix sizes scale these dimensions together.
Per-optic tube-length and crystal-width fields override the built-in dimensions.
Custom CAD uses its actual geometry and is never rescaled.

All three support origin/point selection, XYZ shifts, Rx/Ry/Rz, `f` and saved
component defaults. Defaults share the same angle/displacement and size across
h/v, side signs and `_bd`. Local Z follows the input axis; local X points toward
the secondary output/walk-off. `_bd` rotates this physical frame 180° around Z.
Calibrate your part to that frame and use the ordinary-ray interaction point as
the BD datum. Use a shift if the component origin lies at the mount centre.

The specified angle/offset is fixed. There is no polarization or wavelength-based
birefringence calculation. Crystal propagation is idealized at one plane; only
`p` adds geometric length. Enter n and effective glass thickness deliberately for
reference OPL. Built-in prism/displacer split defaults are adjustable 49%/49%
examples, with zero GDD; custom defaults begin at ideal 50%/50%. These are assumed
power fractions, not predictions. A combining BD uses per-arm loss (built-in 1%,
custom 0%) and GDD without dividing power again. Actual properties must be entered.

## OAP orientation

`r…f…` selects nominal focusing orientation. The parent/blank axis is parallel
to the incoming leg, with the incoming beam travelling along local −Z.
`_r…f…` selects nominal collimating orientation; the outgoing beam follows +Z.
The underscore preserves the requested central-ray directions. It does not
force an arbitrary incident beam to become collimated.

The generic surface is derived from the parent paraboloid using the true 3D
bend and reflected focal length. For a 90° bend and 50 mm reflected focal
length, the parent focal length is 25 mm. The substrate is cut along that
parent axis. Its surface uses narrow conical bands sampled from the paraboloid,
with a nominal 0.01 mm sag tolerance and a finite section cap. The chief-ray
interaction point is a sample boundary. It is a layout representation, not a
manufacturing prescription. Beam solids meet the tangent plane at that point;
they do not reproduce the exact curved-surface footprint.

Example, equal-focal-length relay:

```text
p50 r90f50 p100 _r-90f50 p100
```

For collimated geometric input this returns a collimated beam of the original
diameter, parallel to the initial direction.

## Custom components and reference points

The global **Use assigned CAD in solid preview & build** option controls whether assignments are instanced. With it off, simple optics are built and assignments remain saved. **Preview this CAD only** copies just the selected part over a draft route.

Set reusable parts on **Defaults → Default optics & components**. Choose an
optic, or add another focal length/size with its command. Choose **Assigned
component** and select its existing occurrence from the active design. Set the
datum, XYZ offsets, Rx/Ry/Rz and reference properties, then **Save default**.
Default edits are staged until saved; **Discard edits** restores the saved
record. **Restore built-in fallback** removes that part's saved record.

Every new optic has **Use default** checked. Its component, datum, calibration
and reference properties read the global record. If none is assigned, the
built-in shape and family budget are used. Uncheck the box to copy the current
choice for local editing, using **Built-in optic** or **Assigned component**.
Rechecking follows the global record again and discards the local customization.
The checkbox never saves or deletes a global default.

The component file's origin is the initial datum; no point pick is needed.
**Pick datum…** / **Pick point / circle centre…** accepts a vertex, construction
or sketch point, circular edge, or sketch circle/arc. A circle contributes its
centre, not its orientation. **Use component origin** restores the zero point.
XYZ shifts use the target optic frame; rotations are degrees about fixed local
X, then Y, then Z, around the datum. All six controls remain available after
picking a point. Save the Fusion document to persist global defaults.

Use **Preview this CAD only** to inspect one assigned part even while planning
with simple shapes. Enable **Use assigned CAD in solid preview & build** when
ready to instance all assigned parts. Simple builds retain the assignments.

Matching includes the command and size: `l50`, `l-50`, `+l50` and `-l50` are
independent. Case and numerical spelling are normalized: `L5e1` matches `l50`.
The `f` prefix is excluded, so `fl50` reuses the `l50` component and adds
its CAD rotation afterwards. OAP defaults use size, **actual 3D bend magnitude**
and reflected focal length. `r90f50`, `r-90f50`, `_r90f50` and `_r-90f50` share
one component, datum and calibration. Configure any one of them, save it, and
the other placements use the corresponding intrinsic optical frame. A truly
different design bend or size remains a separate part. For inclined input the
actual bend need not equal the azimuth increment in the command.

Old signed/underscore presets are read through the shared key. A canonical,
unflipped entry takes precedence when old entries conflict. Existing built
routes retain pinned choices. Loading does not rewrite defaults; the first
save that merges old keys retains the old table in document attributes
(`component_defaults_before_1_2_0`).

All plate-splitter angles/signs share the physical key `bs` for each size:
`bs30`, `bs-90` and `fbs60v20` use the same component and calibration. Tweaker
plates share `tp` regardless of tilt/displacement. A canonical key wins old
collisions; otherwise legacy angle keys merge deterministically in lexical
order. Review the retained default when an older document had several different
splitter models. Old tables are backed up on the first merging save.

Global changes do not rebuild existing geometry. Saved route configurations pin
the component and calibration used at build time; their individual Use default
box is unchecked. Recheck deliberately to adopt a changed default. Defaults
are document-specific because their CAD references belong to that document.

The source component is instanced, retaining its geometry and scale. Its
original occurrence is not moved. Geometry edits to the shared component
definition will affect all its instances, as with Fusion's normal Copy/Paste.

Preview and Build use the same component-origin-to-optic transform. Build
passes it when inserting the instance and checks the result. Only if placement
differs does it release automatic grounding to the parent on that new instance
and set its root-context proxy placement, including the route transform exactly
once. Nested corrections are captured as positions; initial-position editing is
reserved for top-level occurrences. It never reads `isGrounded` on nested
occurrences. Source occurrences remain untouched. See [TESTING.md](../TESTING.md)
for portable coverage and native Undo/save/reopen acceptance checks.

The selected datum maps to the nominal beam hit plus the XYZ correction in the
optic frame. Rotations occur about that datum around fixed local X, then Y,
then Z axes (`Rz · Ry · Rx`). The interface reports these axes in design
coordinates. Lens/polarizer Z follows the beam; mirror/plate Z is the
reflecting-face normal; cube Z is transmission and X is reflection.

**Custom OAP alignment is explicit.** Rotate the model so its parent/blank axis
matches local +Z and the off-axis radial direction matches local +X. Pick its
chief-ray interaction point. LaserOpticsRouter cannot infer optical axes from
arbitrary CAD. Enter the actual part's design bend; a mismatch is reported.
The `_` modifier changes the target optical frame after this calibration.

Offsets and rotations adjust the CAD representation. They do not change the
calculated beam path, which remains controlled by the commands. If a model has
no selectable point at the desired datum, use a circular-edge centre, create a
construction/sketch point in Fusion or compensate with the XYZ controls.

Visual insertions and moves retain stable step identities, including repeated
identical optics. Duplication creates a new identity and independent local
settings. Changing focal length, nominal size or physical prism/displacer
specification resets only that step's local component/property assignment;
orientation variants retain their calibration. Review the selected part after
changing its specification. Matching saved component defaults remain available.

Command-text edits preserve unchanged ordered optics during distance edits,
and retain unique unchanged optic matches in a rewritten sequence. Ambiguous
repeated matches and changed specifications lose their affected local assignments
with a notice. Use the visual move/duplicate controls when two identical command
tokens represent different calibrated CAD parts. Draft Undo can recover an edit.

## Endpoints and stepwise builds

Every line supplies **Copy endpoint**. Every BS/BSC also supplies **Copy
reflected** and **New line**. The two splitter ports originate at the same
interaction point and have the same spatial beam envelope; their directions
and reference budgets differ. For BS/BSC the primary line follows transmission. WP/RP/BD also save the two
output ports and both propagated ends; see the paired-ray conventions above.

A copied `LOR2:` endpoint contains:

- XYZ, azimuth/elevation, beam model and accumulated path length;
- signed ray height and slope for geometric propagation, or complex beam
  parameter, wavelength and M² for the Gaussian envelope;
- accumulated reference loss, GDD, glass-length correction and contribution history;
- source document/route/port identity and revision for tracked continuations;
- the reflecting interface normal, when the snapshot lies at a reflector,
  so a continuation can trim its initial beam end consistently.

It preserves both direction angles, divergence, convergence and the sign
needed after a geometric focus. The UI displays the direction as azimuth /
elevation and as an XYZ unit vector. Old `LOR1:` packets are accepted; they already contained direction angles,
but no reference budgets or source tracking. Only new contributions are known
when continuing one of those legacy packets. Rebuild old routes to populate
calculator records. Earlier add-in versions cannot read the new LOR2 packets.

For a continuation in a later run:

1. Choose **Build** to save the route and keep the window open.
2. In **Saved paths & endpoints**, select **Start new run here** at the desired
   end or reflected port. Alternatively, copy its endpoint and use **Paste
   endpoint…** in a new path line. **Build & close** remains available when wanted.
3. Enter the next commands and build another component.

Saved endpoint records belong to the route component in the Fusion document;
you do not need to maintain a separate text list. Copy/paste also works between
documents. Refresh the endpoint list after Undo, deletion or a component move.
Moving or rotating an entire route transforms its retrieved endpoints.
Moving individual beam bodies, optics or custom instances does not reroute the
beam. Exporting only STEP geometry does not preserve Fusion attribute records.

Copy buttons use the native Windows Unicode clipboard or macOS `pbcopy` through
the add-in. If native copying is unavailable, a panel shows the selected text
for Ctrl+C / Command+C. A success message appears only after native copying
succeeds. Endpoint and diagnostic-copy buttons use the same mechanism.

Copied starts are **snapshots**, not live links. A line started from the
previous line within the current build follows that line dynamically. A copied
branch keeps its captured state until **Refresh beam** or an explicit endpoint
replacement. Refresh beam rebuilds the beam while preserving the route and its
optics. The optional following operation below moves whole continuation components.

## Edit, rename or delete saved paths

Open **Saved paths & endpoints**. Each route group offers:

- **Edit paths…**: load its stored source, lines and optic placements. Edit
  commands and line names, add lines, or use × to remove a line. Choose
  **Replace route & close** to rebuild only that route. The old occurrence is
  deleted only after the replacement geometry and records are prepared.
- **Refresh beam…**: find current endpoints at the saved start position and
  direction, choose the source if ambiguous, and rebuild the beam while retaining
  all existing optics and their placements. It also updates endpoint packets and
  reference totals. Refresh upstream routes first. If this route is open in the
  editor, its saved settings replace the editor draft after a successful refresh.
- **Rename…**: rename the route component and its stored run name without
  rebuilding. To rename an individual line/endpoint, edit its line name and
  replace the route.
- **Delete route…**: confirm deletion of this route's occurrence, geometry and
  saved endpoint records. This does not delete independently built continuations.

Replacement is a full rebuild: manual edits to geometry or individual optics
inside the old route are replaced. Whole-route translation and rotation are
preserved. While editing a moved route, source XYZ/angles and commands use its
original route frame. Displayed endpoints, direction vectors and copied packets
are in the current design frame. Pasted endpoints are converted into the route
frame automatically. **New run** exits without replacing the route.

Continuation packets are snapshots. **Keep following saved paths in place**
is checked by default: upstream edits keep their geometry as a manual reference.
Uncheck it to try moving connected saved routes rigidly to the revised starts.
Independent starts, incompatible multiple starts or changed beam envelopes leave
the continuation fixed for review. A matching connection with a changed beam
offers Refresh beam; a moved/disconnected start requires editing. Within the current draft, the
Previous line end start mode remains dynamic; copied starts remain snapshots. Route
management operates on top-level route occurrences; nested route instances
still expose their transformed endpoints for copying. Build, rename, delete
and default-save operations run through Fusion commands for its normal Undo
workflow; native Undo behavior remains part of the Fusion acceptance checks.

## Connection status and beam refresh

The list compares start **position and direction**, using tolerances of 0.001 mm
and 0.001°. A tracked start with no matching existing endpoint is **Disconnected**
(red). Built beams keep their source/generic-optic colors and configured opacity;
connection warnings never dim geometry or change source CAD. When a matching endpoint
exists but its beam model, diameter, divergence, reference totals or history
changed, the route shows **Beam update available** (amber). A revision-only change
with identical state does not mark a route outdated. Restoring an endpoint to its
original geometry clears a disconnection on the next status scan.

**Refresh beam…** prefers the original endpoint if still compatible. Otherwise it
uses a unique compatible replacement or asks you to select among matching sources.
It never silently chooses among ambiguous matches. Candidates from descendants
are excluded to avoid loops. External source routes must be current; refresh
upstream routes first. Earlier lines in the same route are recalculated in order.
The matched input is snapped to the original start pose within the tolerance,
keeping every nominal optic in place. Refresh replaces only the Beam group and
saved records, and runs in a Fusion command for Undo. It does not change optical
properties on already configured optics or interpret manual edits to CAD bodies.

The top **Refresh** button rescans status. It also restores legacy clear beams
to their saved colors and opacity once, without rebuilding them; opening the
palette requests the same repair if needed. Normal routes require no appearance
writes. Closing the palette removes previews and leaves built geometry colored. Beam refresh needs a
single top-level route instance and an identifiable Beam group. A route reused
as multiple component instances must be made independent before refreshing its
shared definition. Untracked snapshots from other documents remain independent
unless a matching endpoint is deliberately selected in this document.

## Window contrast

All pages, tables and tab surfaces have explicit opaque white backgrounds to
avoid dark Fusion-host backgrounds showing through. The palette uses an explicit
light colour scheme with dark text, strong control
borders, a dark-blue primary action and readable disabled controls. The checked
text/background pairs exceed 7:1 contrast; control boundaries exceed 3:1.
Focus outlines and status text supplement colour. Native browser rendering
still needs an in-Fusion visual check.

## Beam models and reported values

**Geometric:** a signed ray height `y` and slope `u` obey `y ← y + uL` and
`u ← u − y/f`. Diameter is `2|y|`. Real point foci are permitted; the CAD envelope
is split into separate cones there. Positive/negative lens body shapes are
recognizable symbols; their curvature is not inferred from a lens prescription.

**Simplified Gaussian:** enable it in Source and enter wavelength, **M²**,
and 1/e² intensity diameter. If a specification gives M = 1.2, enter M² = 1.44.
The default zero initial slope represents a flat
wavefront at a waist; a large Rayleigh range gives the expected approximately
collimated layout. The effective isotropic paraxial model uses
`1/q = 1/R − i M² λ/(π w²)`, `q ← q + L` and `1/q ← 1/q − 1/f`.

The finite waist follows from these inputs rather than clamping the radius at
an arbitrary cutoff. CAD uses adaptively sampled conical sections and includes
the waist position. Only rendering radii below 0.05 µm are limited for practical
CAD tolerance, with a warning; reported optical values remain unchanged.

The status display provides endpoint XYZ, azimuth/elevation, direction vector,
diameter, state, line length and cumulative source-to-end length. Local half-angle
inputs and readouts are hidden throughout the window. Divergence is still retained
in the model, saved settings, endpoint packets and exported data; editing other
source fields does not reset a previously stored value.
“Near collimated” uses a 1 µrad local-slope tolerance. Gaussian mode additionally
reports waist diameter, signed distance to the waist and far-field divergence
half-angle. A waist is labelled separately because zero local expansion does
not imply zero far-field divergence.

Spatial geometry remains an **air-layout model**. It omits uncommanded glass displacement (BD uses its explicit entered offset),
pulse/group delay, detailed ray aberrations, polarization and aperture
diffraction. Manually entered glass length, intensity splitting and GDD are
separate reference bookkeeping; they never change the CAD beam envelope. OAPs use ideal focusing power in the unfolded
beam path. No claim of aberration correction is made for arbitrary conjugates.
Nominal aperture warnings do not truncate the beam; a Gaussian diameter is not
a hard beam edge. Beam solids have CAD volume and participate in mass/interference
calculations; hide/exclude their **Beam** component as appropriate.

Mirror joints below 10° bend or too close to a geometric focus use an untrimmed
fallback with a warning. Coincident reflectors can overlap; normally place
positive propagation between separate physical optics.

## Troubleshooting and development

- **Nothing opens:** verify the folder/entry-point/manifest names match, stop
  and restart the add-in, and use the desktop Design workspace.
- **Build disabled:** correct the marked command or select the missing custom
  component. Obsolete `c/f/e` syntax is rejected with a replacement hint.
- **Custom component cannot be found:** reselect it; saved entity tokens can
  become invalid after deletion or structural changes.
- **Preview is right but Build fails:** verify that the whole add-in folder was
  installed and the badge reads **1.6.1**. Check the document type and selected
  component references, then copy the failing stage from the error message.
- **Further native error:** use **Copy last build error**. The system temporary
  directory contains `LaserOpticsRouter-build.log` (Windows: `%TEMP%`) with build
  stages and Python tracebacks. Include a minimal route when reporting an issue;
  remove private paths and component names. [TESTING.md](../TESTING.md) records
  regression coverage, earlier failures and outstanding native checks.

## Reference calculator: loss, GDD and glass length

Choose routes from the same named, grouped endpoint cards used in Saved paths.
Each card shows its commands, start position and endpoint direction/diameter and
budget. Filter by route, endpoint or command; hidden selections remain selected.
The selection count and Clear selection button make this explicit. Saved routes
are the default source; Current route is available for the draft.

These are **simple approximations for reference, not quantitative optical
results**. Their purpose includes comparing rough GDD budgets between arms.
There is no temporal pulse-duration, polarization or coating simulation.

Every optic card has **Reference loss, GDD & glass length**, independently of
its built-in/custom representation. Generic starter values near 800 nm are:

| Built-in optic | Reference power | GDD (fs²) |
|---|---:|---:|
| Lens | 1% loss | +100 |
| Mirror | 1% loss | 0 |
| OAP | 2% loss | 0 |
| Polarizer | 5% loss for the intended input polarization | +100 |
| Half-wave / quarter-wave plate | 1% loss | +50 |
| ND filter | 90% loss (illustrative OD 1) | +100 |
| Tweaker plate | 1% loss | +100 |
| Plate splitter | T = 49%, R = 49% | T: +100, R: 0 |
| Cube splitter | T = 49%, R = 49% | T: +300, R: +300 |

These illustrative defaults are adjustable in **Reference budget defaults**.
They are not a specification for an arbitrary optic, wavelength or incidence.
Custom optics start at zero loss and zero GDD unless a saved default supplies
values. Custom splitters start at an ideal 50/50 division with zero excess loss
and zero GDD. Built route snapshots pin the values used at build time.

Loss combines as `100 × [1 − product(1 − loss / 100)]`; it is not a sum of
percentages. For splitters, T and R are percentages of incoming power. They
must sum to at most 100%. The remainder is excess loss. An arm's loss includes
power sent into the other port. The two ports can have different signed GDD,
refractive indices and effective glass thicknesses. GDD contributions add
algebraically at each encounter.

Both refractive index **n** and **effective glass thickness** default to **0**.
Zero thickness disables the glass correction; nonzero thickness requires n > 0.
The reported glass-adjusted phase optical path is:

`geometric path + sum[(n − 1) × effective glass thickness]`

The entered thickness is the total distance travelled inside glass, including
oblique incidence or multiple passes, already occupying that much of the
geometric beam path. The add-in does not infer it from CAD thickness or bend
angles. This is not group optical length or pulse delay. Glass entries do not
automatically calculate GDD; enter GDD separately.

Open **Budget & export**, choose Current route or Saved paths, and select
successive paths along one arm. If a selected continuation starts at a splitter's
reflected port, selecting the parent path's normal end automatically uses the
parent only up to that splitter, including its reflected loss/GDD/glass values.
The result names any shortened parent path. Its transmitted continuation is
excluded from this calculation. You may still select the reflected port directly.
**Calculate selected paths** returns the geometric and glass-adjusted lengths, total percentage loss
and accumulated GDD of the selected contributions. Shared sections count once.
Independent paths also join when start/end positions and forward directions
match within 0.001 mm / 0.001°. A unique chain of available intermediate paths
is included automatically and listed with editable highlight colors. Ambiguous
connections require selecting an intermediate explicitly; unrelated arms are
rejected. Local contributions from separate placed copies count separately.
If independent beam envelopes differ, a note explains that this is a sum of
local budgets and does not recalculate propagation. Known stale tracked links
remain errors even when their positions coincide. Selecting only a continuation reports only that continuation's local
contribution; its normal endpoint overview still shows cumulative values.

For example, build `p100 bsc p200`, then continue the reflected port with `p40`.
Select both paths' ends in the saved-path calculator: the resulting geometric
length is **140 mm**. With the standard cube defaults, the loss is **51%** and
GDD is **+300 fs²**. The splitter contribution is counted once.

## Following a changed start

LOR2 snapshots retain source document, route and endpoint identities. See
**Connection status and beam refresh** above for the position/direction-based
status rules and per-route beam refresh. Untracked snapshots from other documents
cannot be monitored for edits to the original document.

The default Keep following saved paths checkbox leaves continuations in place.
Unchecked, it attempts one rigid translation/rotation per connected route and
updates its captured starts and reference budgets. It cannot satisfy incompatible
starts or rebuild a changed envelope. Use Refresh beam for a changed envelope at
a matching start, or Edit paths for a moved connection that needs a new layout.
Neither operation infers optical geometry from manual CAD changes.

## Document export, CSV import/export and SVG projections

**Export all paths…** in Saved paths, or **Export all document paths (ZIP)…**
in Budget & export, saves all built LaserOpticsRouter routes in one file.
It reads saved records independently of the current draft and includes disconnected
routes and routes needing beam refresh with separate status flags. The ZIP contains:

- `all_paths.csv`: combined commands, optic properties and endpoint summaries,
  with route/instance identifiers. Summary positions and directions use the
  current design-root frame; commands remain in their route-local frame.
- `all_paths_XY.svg`, `all_paths_XZ.svg`, `all_paths_YZ.svg`: combined projections
  of every saved route at its current placement.
- `document.json`: saved route settings, placement matrices, complete endpoint
  states and dependency links.
- `routes/*.csv`: an individually importable CSV for each saved route.

This is a documentation bundle. To load a route draft, extract and import its
CSV from `routes`; the combined overview is not an import file. Whole-document
restore is not provided. Custom CAD components are referenced rather than
embedded, so keep the Fusion design for the actual models. An unbuilt draft
can be exported separately using Export current route CSV.

**Export current route CSV** writes a UTF-8 file with settings, path command
rows, per-optic calibration and reference fields, and read-only endpoint summary
rows. To export a saved route, open it with Edit paths first. No build is needed.

**Import CSV** opens a new draft; it never overwrites geometry. Edit the path
name/commands and numeric optic-budget columns in a spreadsheet if wanted.
Keep the record type, IDs and `data_json` columns. Source and CAD calibration
settings round-trip in `data_json`; summary rows are recalculated on import.
CSV coordinates and commands use the route’s original local frame; importing
creates a new route there, without copying a manually moved whole-route placement.
Changing optic commands may require reassigning components. In Excel, import
as a comma-delimited UTF-8 file; semicolon-delimited resaves are also accepted.
Text beginning with spreadsheet formula characters is protected as text.
Custom references from another document are cleared for explicit reselection;
component models themselves are not embedded in CSV.

**Export current route SVG** writes the router schematic in XY, XZ or YZ, with
oriented optical symbols, polarization reference marks, beam colors, arrows,
labels and a millimetre grid. It fits the entire route independently of the
current on-screen zoom/selection. Symbols are not to scale. SVG display units
are pixels; `data-world-start` / `data-world-end` attributes preserve each beam
segment’s XYZ endpoints in millimetres.
It is a layout drawing, not an export of the CAD solids or a perspective view.
A moved route uses its current design placement.
The `examples` folder includes a reference-budget CSV and its XY SVG. Its
transmitted arm has 46% loss / +60 fs²; its reflected continuation has 73%
loss / +120 fs². Import the CSV to inspect or edit this example. Projected coincident segments
can overlap, as expected for an orthographic drawing.

## Development

The Python modules need only Fusion's Python environment and the standard
library. `core.py` handles calculations; `fusion_backend.py` owns CAD operations
and document records; `exports.py` handles CSV and document ZIPs;
`schematic_svg.py` produces standalone SVGs with symbols tested against `schematic.js`;
`clipboard_support.py` handles native text copying. The offline palette
uses local HTML/CSS/JavaScript. There is no direct connection from this package
to any external service.

Run `python -m unittest discover -s tests -q` and
`node --test tests/*.cjs` from this add-in directory for the
portable checks. Native Fusion checks are listed in [TESTING.md](../TESTING.md).
