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
| `cyl100h`, `cyl-100v` | Cylindrical thin lens, signed focal length; h/v powered plane. |
| `gr600a30m1h` | Reflection grating: lines/mm, signed incidence, integer order, h/v dispersion. |
| `resetd5finf`, `resetd5f50` | Set 5 mm beam, collimated / focused 50 mm ahead. |
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
| `fl50`, `f+l-50`, `fr90`, `fpol`, `fbs30`, `fbsc` | Rotate the CAD optic 180° about its prepared X normal at the origin. Beam calculations are unchanged. |
| `f_r90f50`, `+fr90f50` | Combine the CAD flip with the OAP or size modifiers. |

All optic commands act at the current position. **Only `p` adds path length.**
Standalone `f`, `e` and `c` commands are removed. Convert `f50` to `l50 p50`,
`f-50` to `l-50 p50`, and `e50` to `p50`. Set initial collimation in Source or
use a lens/OAP or a virtual `resetd…f…` plate in the sequence. The `f` suffix remains part of an OAP
command, and OAP focal lengths must be positive. The new **prefix** `f` only
modifies an optic; standalone `f50` and `fp50` remain invalid.

**The `f` prefix rotates CAD around the surface-normal X axis.** It spins a
lens/mirror in its own plane, not front-to-back. The component origin remains
at the beam hit and optical calculations are unchanged. An OAP `_` still swaps
the parent-axis leg; `f` may misalign asymmetric CAD with the modeled rays, so
an OAP warning is shown. This X convention applies to rebuilt old routes too.

Size prefixes apply to spherical/cylindrical lenses, gratings, reset markers, mirrors, OAPs, polarizers, plate splitters and
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
envelope. The optic's datum remains at the original hit point. Preparing the source geometry determines CAD placement; it does not infer a beam displacement.

Only `p` contributes geometric distance. Include all intended glass propagation
in your entered distances and supply effective glass path and GDD separately.
Reflection-grating dispersion and anamorphic width are described below.

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

All three use the prepared component origin and X-normal convention. Defaults
share the same angle/displacement and size across h/v, side signs and `_bd`.
Local X follows the input axis; local Y points toward the secondary output or
walk-off. `_bd` reverses that transverse frame by 180° about X. Place the BD
origin at the ordinary-ray interaction point in its own source file.

The specified angle/offset is fixed. There is no polarization or wavelength-based
birefringence calculation. Crystal propagation is idealized at one plane; only
`p` adds geometric length. Enter n and effective glass thickness deliberately for
reference OPL. Built-in prism/displacer split defaults are adjustable 49%/49%
examples, with zero GDD; custom defaults begin at ideal 50%/50%. These are assumed
power fractions, not predictions. A combining BD uses per-arm loss (built-in 1%,
custom 0%) and GDD without dividing power again. Actual properties must be entered.

## OAP orientation

`r…f…` selects nominal focusing orientation. The parent/blank axis is parallel
to the incoming leg. `_r…f…` selects nominal collimating orientation with the
outgoing leg along the parent axis. The custom component's X axis is the
tangent **surface normal** at the hit, not the parent axis.
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

## Prepared custom components

Put each reference part in its own file, with **origin at the beam hit and X
normal to the reference surface**. The [component guide](COMPONENTS.md) gives
Z-up placement and explicit corrections, including OAPs, cylinders and grooves. A mirror aligned
this way reflects a normally incident −X ray back along +X.

Insert the source into the active setup, preferably linked. **Choose component…**
lists existing occurrences by full assembly path, including hidden references
and excluding generated routes. Search, select, and confirm. No viewport face
selection is required. Defaults are staged until **Save default**. Uncheck
**Use default** for a local choice; checking it again follows the global record.

The global **Use assigned CAD in solid preview & build** option controls
instancing. With it off, simple shapes are used and assignments are retained.
**Preview this CAD only** uses the same placement as Build over a draft route.
The source occurrence is not moved, edited or rescaled. Local definitions remain
shared; linked definitions use Fusion's explicit version/update workflow.

**All old saved assignments also use X-normal when rebuilt.** Old datum points,
offsets and rotations are ignored; there is no legacy Z-normal option. New
**Component rotation & assembly offsets** controls use fixed source-axis rotations
before alignment and assembly-axis translations. They are saved independently
of former calibration. Z is upright for horizontal normals, projected onto
tilted surfaces. Existing built geometry is untouched until
replaced. Component identities and reference budgets remain pinned unless you
recheck **Use default** to adopt current defaults.

Physical keys distinguish signed focal length and size. `l50`, `l-50`, `+l50`
and `cyl50h` are separate. Cylindrical h/v orientations reuse the same part.
Gratings share density/size across incidence, order and h/v. BS angles share
`bs`; tweaker tilt/displacement share `tp`. OAPs share actual 3D bend magnitude
and reflected focal length. Canonical defaults win when older keys collide.

Visual moves preserve stable step identities. Duplicates have independent
settings. Changed physical specifications reset that step's local assignment;
compatible orientation changes retain it. Raw command edits preserve unique
matches, and report ambiguous repeated matches instead of guessing. Draft Undo
can recover an edit. Local corrections affect CAD placement only; optical
geometry and reference budgets are unchanged.

## Cylindrical lenses and elliptical envelopes

`cyl100h` focuses the horizontal transverse direction with f = +100 mm;
`cyl-100v` diverges the vertical direction with f = −100 mm. Omitted axis means
h. The other direction has zero lens power. The chief-ray position and direction
do not change at a cylinder. Here h is local horizontal left of the incoming
ray (world +Y for a +X ray), and v completes the right-handed transverse frame.
The physical cylinder axis is perpendicular to the powered direction.

The first cylinder or grating promotes the circular envelope to a 4×4 paraxial
second-moment matrix for (h, v, h′, v′). Free-space propagation and lens power
transform both transverse dimensions and their correlations. Mirrors transport
the transverse frame by reflection, and route moves rotate it rigidly. A later
spherical lens/OAP acts on both directions. Other routes keep the scalar model.

Endpoint statistics include H/V projected diameters, major/minor principal
diameters, ellipse angle and signed distances to projected waists. H/V are
defined in the endpoint's local beam frame; a rotated saved route recomputes
them in the design frame. After crossed cylinders and 3D folds, projected waists
need not coincide with principal axes. The scalar diameter is the major diameter.

Draft preview draws ellipse rails. Solid preview/Build use closed faceted
elliptical skins with adaptive longitudinal sampling and 48 sides per ring.
Displayed minor radii below 1 µm are floored for CAD validity, with a warning;
reported optical widths retain ideal zeros. Anisotropic solids have transverse
end faces and are not trimmed to tilted mirrors. They are layout envelopes,
not manufactured optical surfaces. Ordinary circular solids are unchanged.

## Reflection gratings and wavelength modes

`gr600a30m1h` specifies groove density G = 600 lines/mm, signed incidence α = 30°
from the normal, order m = +1 and horizontal dispersion. Use v for vertical,
negative m for the opposite order, and m = 0 for specular reflection. Groove
density must be positive, |α| < 89.9°, and m must be an integer from −100 to 100.
The prepared CAD uses X front normal, Y dispersion tangent, Z grooves.

In air, the ideal reflection equation is **sin β = m λ G × 10⁻⁶ − sin α**, with
λ in nm. The outgoing ray uses the reflected-side principal solution. At α = β
(Littrow), it returns along the incident line. Evanescent and exactly grazing
orders are rejected. The transverse width along dispersion changes by
**cos β / cos α**, and the paraxial slope transforms reciprocally. Groove-parallel
width is unchanged. This anamorphism is included in the elliptical envelope.

Choose wavelength under Source, independently of geometric/Gaussian spatial mode:

| Mode | Sampling |
|---|---|
| Central wavelength | One ray at λ₀; default for existing routes |
| Two sidebands | Central ray and λ₀ − Δλ, λ₀ + Δλ; Δλ is a positive offset in nm |
| Gaussian spectrum | Intensity FWHM in nm; 3–21 odd samples over λ₀ ± 3σ, σ = FWHM / √(8 ln 2) |

Gaussian sample weights are exp(−Δλ²/(2σ²)), relative to the peak. They affect
display intensity and are exported with endpoints. Sidebands are unit-weight
boundary probes. Neither is a normalized allocation of total beam power, and
sample endpoints must not be added as independent full-power budgets.

The first grating creates the wavelength samples. Every later optic acts on
those same samples; later gratings do not resample or multiply them. `pL`
defines the **central ray's next station**. Sample rays intersect that station
and the actual fixed interaction plane of the following optic, so their path
lengths and hit positions can differ from the central ray. Mirrors reflect in
the fixed surface normal. Spherical/cylindrical lenses and OAPs apply ideal
paraxial power to the sample's displacement and direction about the central
optical axis. Splitters and prisms retain spectral states in both output ports.
Uncombined prism companions retain the existing main-only optic convention.

At a grating, momentum along its grooves is conserved and `mλG` is added
along its fixed dispersion tangent. This vector equation also handles rays
with a groove-parallel direction component after 3D folds. Nonpropagating or
grazing samples fail the route rather than silently disappearing. Samples
outside the nominal aperture generate warnings and are not clipped.

Two parallel gratings can cancel angular dispersion; a four-encounter return
train can recombine the rays spatially. See the importable
[compressor examples](../examples/README.md). **Reuse matching coplanar grating
surfaces on return passes** is on by default: density, size, plane, groove axis
and assignment/corrections must match, and the later hit must lie inside the
first grating aperture. Only the first encounter places the physical CAD part;
every encounter still diffracts the beam and adds its reference budget. Disable
the option to create separate parts. Single-part inspection of a return
encounter previews the first physical grating.

The central end/port packet carries the complete wavelength bundle. Copy it
to continue all samples in a later route, or choose an individual wavelength
endpoint for an independent single-ray route. Previous-line continuation
also retains the bundle. Wavelength-resolved geometric path lengths are
reported, but temporal compression is not calculated.

Changing sample wavelength preserves the incident radius and wavefront
curvature; Gaussian diffraction scales with wavelength. All sampled wavelengths
must be positive and their selected orders propagating. Transmission gratings,
blaze, efficiency, polarization, material phase, pulse width and automatic
grating GDD are not calculated. Enter measured/reference loss and GDD manually.

Equation and anamorphic convention:
[Newport, Diffraction Grating Physics](https://www.newport.com/n/the-physics-of-diffraction-gratings).
Vector/conical convention: [Newport, The Grating Equation](https://www.newport.com/n/the-grating-equation).

## Virtual reset plates

`resetd5finf` sets a circular 5 mm collimated envelope at the current point.
`resetd5f50` sets a circular 5 mm envelope focused 50 mm ahead. The signed focus
distance may be negative for a waist behind the plate; zero is invalid. Diameter
must be positive. The plate preserves position, direction, wavelength, M²,
spectral settings, color and accumulated path/loss/GDD. It discards earlier
astigmatism. The marker itself contributes zero path/loss/GDD and no custom CAD.

In geometric mode, radius = d/2 and slope = −(d/2)/f, or zero for finf.
Gaussian finf creates a waist/flat wavefront at this plane; diffraction still
occurs downstream. A finite Gaussian reset solves for a waist exactly f mm
ahead at the requested present diameter, choosing the smaller-waist solution.
Impossible diameter/focus combinations are rejected rather than clamped.
The reset is an imposed boundary condition, not a prediction for a real optic.

Saved elliptical or spectral states use LOR3 endpoint packets. Scalar states
without new data still use LOR2; v1.7.1 reads LOR1/LOR2/LOR3. Earlier versions
cannot read LOR3 or the new commands. Export CSV retains the new settings.

## Endpoints and stepwise builds

Every line supplies **Copy endpoint**. Every BS/BSC also supplies **Copy
reflected** and **New line**. The two splitter ports originate at the same
interaction point and have the same spatial beam envelope; their directions
and reference budgets differ. For BS/BSC the primary line follows transmission. WP/RP/BD also save the two
output ports and both propagated ends; see the paired-ray conventions above.

A copied `LOR2:` endpoint, or `LOR3:` when elliptical/spectral data is present, contains:

- XYZ, azimuth/elevation, beam model and accumulated path length;
- signed ray height and slope for geometric propagation, or complex beam
  parameter, wavelength and M² for the Gaussian envelope;
- accumulated reference loss, GDD, glass-length correction and contribution history;
- source document/route/port identity and revision for tracked continuations;
- the reflecting interface normal, when the snapshot lies at a reflector,
  so a continuation can trim its initial beam end consistently.

LOR3 additionally retains the 4×4 envelope matrix, spectral settings and sample
weight as applicable. Version 1.7.1 adds a bounded bundle of noncentral ray
states to the central packet, including individual geometry, moments and
histories. These bundle packets require 1.7.1; older scalar and elliptical
packets still load. Anisotropic solids use untrimmed transverse end faces.

It preserves both direction angles, divergence, convergence and the sign
needed after a geometric focus. The UI displays the direction as azimuth /
elevation and as an XYZ unit vector. Old `LOR1:` packets are accepted; they already contained direction angles,
but no reference budgets or source tracking. Only new contributions are known
when continuing one of those legacy packets. Rebuild old routes to populate
calculator records. Scalar LOR2 compatibility is unchanged.

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
  installed and the badge reads **1.7.1**. Check the document type and selected
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
rows, per-optic assignments and reference fields, and read-only endpoint summary
rows. To export a saved route, open it with Edit paths first. No build is needed.

**Import CSV** opens a new draft; it never overwrites geometry. Edit the path
name/commands and numeric optic-budget columns in a spreadsheet if wanted.
Keep the record type, IDs and `data_json` columns. Source and CAD assignment
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
